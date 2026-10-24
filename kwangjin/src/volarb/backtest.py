"""전략 명세(Spec)와 실행기(Backtester): 신호 계산 → 엔진 → 성과 지표, 결과 캐시."""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, replace
from typing import Dict, List, Optional, Tuple

from .config import ENTRY_THRESHOLDS, WINDOWS, Params
from .data import Dataset
from .engine import BacktestResult, run_engine, to_equity
from .indicators import add_signals, compute_indicators, robust_z, rolling_z
from .metrics import compute_metrics, newey_west_t
from .strategies import calendar_builder, make_skew_builder, vrp_builder


@dataclass(frozen=True)
class Spec:
    """전략 한 가지의 정의.

    strategy : 'skew' | 'calendar' | 'vrp'
    signal   : z-score를 계산할 지표 키 (None이면 전략 기본 지표)
               skew 계열: 'skew' | 'skew_sma3' | 'skew25' | 'skew25_sma3'
    legs     : (skew) 'moneyness' = 0.90/1.10, 'delta25' = 25-delta 행사가
    min_dte  : (skew) 잔존일 필터
    robust   : True면 중앙값·MAD 기반 z-score
    """
    strategy: str
    signal: Optional[str] = None
    legs: str = "moneyness"
    min_dte: Optional[int] = None
    robust: bool = False

    @property
    def signal_key(self) -> str:
        return self.signal or {"skew": "skew", "calendar": "term_slope", "vrp": "vrp"}[self.strategy]

    def builder(self):
        if self.strategy == "skew":
            return make_skew_builder(self.legs, self.min_dte)
        return {"calendar": calendar_builder, "vrp": vrp_builder}[self.strategy]


@dataclass
class Run:
    spec: Spec
    params: Params
    result: BacktestResult
    equity: List[float]
    metrics: dict


class Backtester:
    def __init__(self, ds: Dataset):
        self.ds = ds
        self.rows = add_signals(compute_indicators(ds), ds)
        self.dates = [r["date"] for r in self.rows]
        self.rows_by_date = {r["date"]: r for r in self.rows}
        self._z: Dict[tuple, list] = {}
        self._runs: Dict[tuple, Run] = {}

    def z(self, key: str, window: int, robust: bool = False) -> list:
        k = (key, window, robust)
        if k not in self._z:
            self._z[k] = (robust_z if robust else rolling_z)(self.rows, key, window)
        return self._z[k]

    def run(self, spec: Spec, p: Params) -> Run:
        k = (spec, p)
        if k not in self._runs:
            z = self.z(spec.signal_key, p.z_window, spec.robust)
            res = run_engine(self.dates, self.rows_by_date, z, self.ds.smiles_by_day, spec.builder(), p)
            eq = to_equity(self.dates, res.daily)
            self._runs[k] = Run(spec, p, res, eq, compute_metrics(eq, res.trades, res.detail))
        return self._runs[k]

    def grid(self, spec: Spec, base: Params, windows=WINDOWS, entries=ENTRY_THRESHOLDS) -> List[Run]:
        """윈도우 × 진입 임계값 격자 (base의 나머지 파라미터 고정)."""
        return [self.run(spec, replace(base, z_window=w, z_entry=e)) for w in windows for e in entries]

    def ensemble(self, spec: Spec, base: Params, windows=WINDOWS, entries=ENTRY_THRESHOLDS) -> dict:
        """격자 셀들의 일별 손익 평균 = 하나의 '사전 지정 앙상블' 전략.
        특정 셀을 사후 선택하지 않고 전체 평균을 보기 위한 용도."""
        runs = self.grid(spec, base, windows, entries)
        acc = defaultdict(float)
        for r in runs:
            for d, v in r.result.daily.items():
                acc[d] += v / len(runs)
        eq = to_equity(self.dates, dict(acc))
        trades = [t for r in runs for t in r.result.trades]
        detail = [d for r in runs for d in r.result.detail]
        m = compute_metrics(eq, trades, detail)
        series = [eq[i + 1] - eq[i] for i in range(len(self.dates))]
        m["nw_mean_daily_pct"], m["nw_t"] = (lambda mt: (100 * mt[0], mt[1]))(newey_west_t(series, 5))
        m["pos_cells"], m["n_cells"] = sum(1 for r in runs if r.metrics["total_return_pct"] > 0), len(runs)
        m["mean_cell_return_pct"] = sum(r.metrics["total_return_pct"] for r in runs) / len(runs)
        m["mean_cell_sharpe"] = _nanmean([r.metrics["sharpe"] for r in runs])
        m["mean_cell_mdd_pct"] = sum(r.metrics["mdd_pct"] for r in runs) / len(runs)
        mdds = [r.metrics["mdd_pct"] for r in runs]
        m["worst_cell_mdd_pct"], m["best_cell_mdd_pct"] = min(mdds), max(mdds)
        m["cell_mdd_list"] = " ".join(f"{x:.2f}" for x in mdds)      # (W,E) 순서: 20/1.0 … 60/2.0
        m["mean_cell_eff_trades"] = sum(r.metrics["effective_trades"] for r in runs) / len(runs)
        return dict(equity=eq, metrics=m, runs=runs)


def _nanmean(xs):
    xs = [x for x in xs if x == x]
    return sum(xs) / len(xs) if xs else float("nan")
