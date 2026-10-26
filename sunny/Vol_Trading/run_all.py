#!/usr/bin/env python3
"""IV 기반 변동성 트레이딩 백테스트 실행.

사용 예
  python run_all.py                              # minjae 데이터 자동 탐색
  python run_all.py --data-dir ../../../minjae   # 데이터 경로 직접 지정
  python run_all.py --no-cache                   # 캐시 무시하고 재계산
"""
from __future__ import annotations

import argparse
import sys
import time
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from voltrading.config   import Params, WINDOWS, ENTRY_THRESHOLDS
from voltrading.data     import load_dataset
from voltrading.engine   import run_engine, to_equity
from voltrading.metrics  import compute_metrics, newey_west_t
from voltrading.plots    import (plot_iv_hv, plot_vrp_dist, plot_term_structure,
                                  plot_strategy_equity, plot_summary)
from voltrading.signals  import compute_indicators, rolling_z, robust_z
from voltrading.strategies import vrp_builder, longvol_builder, shortvol_builder


# ── 데이터 경로 후보 (스크립트 위치 기준 절대경로로 탐색) ──
_HERE = Path(__file__).parent.resolve()

DATA_CANDIDATES = [
    _HERE / "data",                        # 스크립트 옆 data/ 폴더 (최우선)
    _HERE / "../../../minjae",             # 레포 내 minjae 폴더
    _HERE / "../../minjae",
    Path("data"),                          # 현재 작업 디렉터리의 data/
]


def find_data_dir(cli_arg: str | None) -> str:
    if cli_arg:
        return cli_arg
    for c in DATA_CANDIDATES:
        p = Path(c).resolve()
        if (p / "kospi200_spot.csv").exists() or (p / "kospi200_options_regular.csv.gz").exists():
            return str(p)
    raise FileNotFoundError(
        "데이터 폴더를 찾을 수 없습니다. --data-dir 옵션으로 지정하세요.\n"
        "필요 파일: kospi200_options_regular.csv[.gz], "
        "kospi200_futures_regular.csv[.gz], kospi200_spot.csv"
    )


def run_strategy(name: str, tag: str, builder, rows, rows_by_date,
                 smiles_by_day, dates, base_params: Params,
                 windows=WINDOWS, entries=ENTRY_THRESHOLDS):
    """앙상블: windows × entries 격자 평균."""
    from collections import defaultdict
    acc_same = defaultdict(float)
    acc_next = defaultdict(float)
    all_trades, all_detail = [], []
    cells = len(windows) * len(entries)
    for w in windows:
        for e in entries:
            for lag, acc in ((0, acc_same), (1, acc_next)):
                p = replace(base_params, z_window=w, z_entry=e, entry_lag=lag)
                z = rolling_z(rows, "vrp", w)
                res = run_engine(dates, rows_by_date, z, smiles_by_day, builder, p)
                for d, v in res.daily.items():
                    acc[d] += v / cells
                if lag == 0:
                    all_trades.extend(res.trades)
                    all_detail.extend(res.detail)
    eq_same = to_equity(dates, dict(acc_same))
    eq_next = to_equity(dates, dict(acc_next))
    m_same  = compute_metrics(eq_same, all_trades, all_detail)
    m_next  = compute_metrics(eq_next, all_trades, all_detail)
    series  = [eq_same[i+1] - eq_same[i] for i in range(len(dates))]
    nw_mean, nw_t = newey_west_t(series)
    m_same["nw_mean_daily_pct"] = 100 * nw_mean
    m_same["nw_t"] = nw_t
    return dict(name=name, tag=tag,
                equity_same=eq_same, equity_next=eq_next,
                metrics_same=m_same, metrics_next=m_next)


_CJK_RANGES = (
    (0xAC00, 0xD7A3), (0x1100, 0x11FF), (0x3130, 0x318F),
    (0x4E00, 0x9FFF), (0x3400, 0x4DBF),
)


def _wlen(s: str) -> int:
    """터미널 표시 너비 (한글/CJK = 2, 나머지 = 1)."""
    return sum(2 if any(lo <= ord(c) <= hi for lo, hi in _CJK_RANGES) else 1
               for c in s)


def _pad(s: str, w: int, align: str = "<") -> str:
    p = max(0, w - _wlen(s))
    if align == "<":  return s + " " * p
    if align == ">":  return " " * p + s
    left = p // 2;    return " " * left + s + " " * (p - left)   # ^


def _nf(v: float, fmt: str) -> str:
    if v != v: return "N/A"          # NaN
    try:       return fmt % v
    except (OverflowError, ValueError): return "N/A"


def print_comparison(results: list[dict]) -> None:
    """세 전략 성과 지표를 나란히 비교 출력."""
    ms    = [r["metrics_same"] for r in results]
    heads = ["VRP 양방향", "Short Vol", "Long Vol"]

    WL, WV = 14, 13  # 라벨 / 값 열 표시 너비

    def hline(l: str, m: str, r: str) -> str:
        return l + "─" * (WL + 2) + (m + "─" * (WV + 2)) * 3 + r

    def row(label: str, *vals: str) -> str:
        return ("│ " + _pad(label, WL) + " │ "
                + " │ ".join(_pad(v, WV, ">") for v in vals) + " │")

    def hrow(label: str, *vals: str) -> str:
        return ("│ " + _pad(label, WL) + " │ "
                + " │ ".join(_pad(v, WV, "^") for v in vals) + " │")

    TOTAL = 4 + WL + (WV + 3) * 3
    data = [
        ("누적수익률",   [f"{m['total_return_pct']:+.2f} %p"  for m in ms]),
        ("연환산수익률", [f"{m['ann_return_pct']:+.2f} %p"    for m in ms]),
        ("연환산변동성", [f"{m['ann_vol_pct']:.2f} %p"        for m in ms]),
        ("Sharpe",       [f"{m['sharpe']:+.3f}"               for m in ms]),
        ("MDD",          [f"{m['mdd_pct']:.2f} %p"            for m in ms]),
        ("MDD 기간",     [f"{m['mdd_days']} 일"               for m in ms]),
        ("Calmar",       [_nf(m["calmar"], "%+.3f")            for m in ms]),
        ("유효거래수",   [f"{m['effective_trades']} 건"        for m in ms]),
        ("승률",         [f"{m['win_rate_pct']:.1f} %"         for m in ms]),
        ("평균거래",     [f"{m['avg_trade_pct']:+.3f} %p"      for m in ms]),
        ("최악거래",     [f"{m['worst_trade_pct']:+.3f} %p"    for m in ms]),
        ("평균보유",     [f"{m['avg_hold_days']:.1f} 일"       for m in ms]),
    ]
    if all("nw_t" in m for m in ms):
        data.append(("NW t통계량", [f"{m['nw_t']:+.3f}" for m in ms]))

    print(f"\n\n{'═' * TOTAL}")
    print(f"  전략별 성과 비교  (당일 체결 · 앙상블 평균)")
    print(f"{'═' * TOTAL}")
    print(hline("┌", "┬", "┐"))
    print(hrow("지표", *heads))
    print(hline("├", "┼", "┤"))
    for label, vals in data:
        print(row(label, *vals))
    print(hline("└", "┴", "┘"))


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data-dir", default=None, help="데이터 폴더 경로")
    ap.add_argument("--out",      default=str(_HERE / "results"))
    ap.add_argument("--cache",    default=str(_HERE / ".cache"))
    ap.add_argument("--no-cache", action="store_true")
    args = ap.parse_args()

    t0 = time.time()
    data_dir = find_data_dir(args.data_dir)
    print(f"[데이터] {data_dir}")
    ds = load_dataset(data_dir, cache_dir=(None if args.no_cache else args.cache))

    rows       = compute_indicators(ds)
    dates      = [r["date"] for r in rows]
    rows_by_date = {r["date"]: r for r in rows}
    smiles_by_day = ds.smiles_by_day

    n_valid = {k: sum(1 for r in rows if r[k] is not None)
               for k in ("atm_iv", "rv20", "vrp", "term_slope")}
    print(f"\n[데이터 요약]")
    print(f"  분석 가능 일수: {len(dates)}일  ({dates[0]} ~ {dates[-1]})")
    for k, v in n_valid.items():
        print(f"  {k}: {v}일")

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    print("\n[그림 1-3] 지표 시각화 중...")
    plot_iv_hv(rows, out_dir)
    plot_vrp_dist(rows, out_dir)
    plot_term_structure(rows, out_dir)

    base = Params(z_exit=0.3, max_hold=15, rehedge=True, cost_iv_pt=0.5)
    strategies = [
        ("VRP 전략 (Short/Long ATM 스트래들, 양방향)",  "04_VRP_양방향",   vrp_builder),
        ("Short Volatility 전략 (VRP 수취, 매도 전용)", "05_Short_Vol",    shortvol_builder),
        ("Long Volatility 전략 (위기 헤지, 매수 전용)", "06_Long_Vol",     longvol_builder),
    ]

    results = []
    for i, (name, tag, builder) in enumerate(strategies, 1):
        print(f"\n[백테스트 {i}/{len(strategies)}] {name} ...")
        res = run_strategy(name, tag, builder, rows, rows_by_date,
                           smiles_by_day, dates, base)
        results.append(res)
        print(f"  완료  누적수익률 {res['metrics_same']['total_return_pct']:+.2f} %p"
              f"  Sharpe {res['metrics_same']['sharpe']:+.3f}")

    print_comparison(results)

    print("\n[그림 4-7] 전략별 손익 곡선 저장 중...")
    plot_strategy_equity(results, dates, out_dir)
    plot_summary(results, dates, out_dir)

    print(f"\n실행 완료: {time.time() - t0:.0f}초  |  결과 폴더: {out_dir.absolute()}")


if __name__ == "__main__":
    main()
