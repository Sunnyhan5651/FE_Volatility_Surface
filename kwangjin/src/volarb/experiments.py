"""오늘 진행한 실험 세트. 각 함수는 {'table': DataFrame, 'curves': {...}, ...} 형태로 결과를 돌려준다.

  baseline   세 전략 기본 백테스트 (정적 헤지 vs 일별 재헤지)
  execution  체결 가정(당일/익일 체결 × 보유 15/5일) 민감도
  cost       거래비용 민감도
  combos     스큐 변형 3종(손절 S · 잔존일 필터 D · 중앙값 z M) 7가지 조합
  signals    신호 노이즈 저감(25-delta 정의 × 3일 평활) 6개 변형
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import replace

import pandas as pd

from .backtest import Backtester, Spec
from .config import Params
from .engine import to_equity
from .metrics import compute_metrics

BASE = Params(z_window=40, z_entry=1.5, z_exit=0.3, max_hold=15, entry_lag=0, rehedge=True, cost_iv_pt=0.5)
STRATEGIES = ("skew", "calendar", "vrp")
STOP_DZ = 1.0
MIN_DTE_FILTER = 10

SIGNAL_VARIANTS = {
    "BASE": Spec("skew"),
    "SMA3": Spec("skew", signal="skew_sma3"),
    "D25": Spec("skew", signal="skew25"),
    "D25L": Spec("skew", signal="skew25", legs="delta25"),
    "D25S": Spec("skew", signal="skew25_sma3"),
    "D25SL": Spec("skew", signal="skew25_sma3", legs="delta25"),
}
COMBOS = [("BASE", 0, 0, 0), ("S", 1, 0, 0), ("D", 0, 1, 0), ("M", 0, 0, 1),
          ("SD", 1, 1, 0), ("SM", 1, 0, 1), ("DM", 0, 1, 1), ("SDM", 1, 1, 1)]


def _row(name, m, **extra):
    return dict(name=name, **extra, **m)


# ----------------------------------------------------------------------------- baseline
def baseline(bt: Backtester) -> dict:
    rows, curves, trade_logs = [], {}, []
    for hedge, rehedge in (("static", False), ("daily", True)):
        pooled, comb_trades, comb_detail = defaultdict(float), [], []
        for s in STRATEGIES:
            run = bt.run(Spec(s), replace(BASE, rehedge=rehedge))
            curves[f"{s}|{hedge}"] = run.equity
            rows.append(_row(s, run.metrics, hedge=hedge))
            for d, v in run.result.daily.items():
                pooled[d] += v / 3
            comb_trades += [t / 3 for t in run.result.trades]
            comb_detail += run.result.detail
            for d0, d1, tag, pnl, hold in run.result.detail:
                trade_logs.append(dict(strategy=s, hedge=hedge, entry=d0, exit=d1, side=tag, pnl_pct=100 * pnl, hold_days=hold))
        eq = to_equity(bt.dates, dict(pooled))
        curves[f"combined|{hedge}"] = eq
        rows.append(_row("combined (1/3 each)", compute_metrics(eq, comb_trades, comb_detail), hedge=hedge))
    return dict(table=pd.DataFrame(rows), curves=curves, trades=pd.DataFrame(trade_logs))


# ----------------------------------------------------------------------------- execution
EXEC_SETTINGS = [(0, 15), (0, 5), (1, 15), (1, 5)]       # (entry_lag, max_hold)


def execution(bt: Backtester) -> dict:
    rows, cells, curves = [], [], {}
    for s in STRATEGIES:
        for lag, hold in EXEC_SETTINGS:
            ens = bt.ensemble(Spec(s), replace(BASE, entry_lag=lag, max_hold=hold))
            m = ens["metrics"]
            rows.append(_row(s, m, lag=lag, hold=hold))
            curves[f"{s}|lag{lag}|hold{hold}"] = ens["equity"]
            for r in ens["runs"]:
                cells.append(dict(strategy=s, lag=lag, hold=hold, W=r.params.z_window, E=r.params.z_entry,
                                  **{k: r.metrics[k] for k in ("total_return_pct", "sharpe", "mdd_pct", "effective_trades",
                                                              "win_rate_pct", "avg_trade_pct")}))
    return dict(table=pd.DataFrame(rows), cells=pd.DataFrame(cells), curves=curves)


# ----------------------------------------------------------------------------- cost
COSTS = (0.0, 0.25, 0.5, 1.0)


def cost(bt: Backtester) -> dict:
    rows = []
    for label, spec in (("BASE", SIGNAL_VARIANTS["BASE"]), ("D25S", SIGNAL_VARIANTS["D25S"])):
        for c in COSTS:
            ens = bt.ensemble(spec, replace(BASE, entry_lag=1, max_hold=5, cost_iv_pt=c))
            rows.append(_row(label, ens["metrics"], cost_iv_pt=c))
    return dict(table=pd.DataFrame(rows))


# ----------------------------------------------------------------------------- combos
def combos(bt: Backtester) -> dict:
    rows, curves = [], {}
    for lag in (1, 0):
        for label, s, d, mflag in COMBOS:
            spec = Spec("skew", min_dte=MIN_DTE_FILTER if d else None, robust=bool(mflag))
            p = replace(BASE, entry_lag=lag, max_hold=5, stop_dz=STOP_DZ if s else None)
            ens = bt.ensemble(spec, p)
            rows.append(_row(label, ens["metrics"], lag=lag, stop=bool(s), dte_filter=bool(d), median_z=bool(mflag)))
            curves[f"{label}|lag{lag}"] = ens["equity"]
    return dict(table=pd.DataFrame(rows), curves=curves)


# ----------------------------------------------------------------------------- signals
SIGNAL_SETTINGS = [("lag1, cost 0.5", 1, 0.5), ("lag1, cost 0", 1, 0.0), ("lag0, cost 0.5", 0, 0.5)]


def signals(bt: Backtester) -> dict:
    rows, curves = [], {}
    for setting, lag, c in SIGNAL_SETTINGS:
        for name, spec in SIGNAL_VARIANTS.items():
            ens = bt.ensemble(spec, replace(BASE, entry_lag=lag, max_hold=5, cost_iv_pt=c))
            rows.append(_row(name, ens["metrics"], setting=setting, lag=lag, cost_iv_pt=c))
            curves[f"{name}|{setting}"] = ens["equity"]
    return dict(table=pd.DataFrame(rows), curves=curves)
