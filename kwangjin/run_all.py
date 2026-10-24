#!/usr/bin/env python3
"""전체 실험 실행 → 그림(results/figures), 표(results/tables), 요약(results/summary.txt) 생성.

사용 예
  python run_all.py --data-dir data                 # 전부 실행
  python run_all.py --parts baseline,signals        # 일부만
  python run_all.py --quick                         # 순열검정 횟수를 줄여 빠르게
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

import pandas as pd  # noqa: E402

from volarb import experiments as X  # noqa: E402
from volarb import plots, report, stats_tests  # noqa: E402
from volarb.backtest import Backtester  # noqa: E402
from volarb.data import load_dataset  # noqa: E402

ALL_PARTS = ["indicators", "baseline", "execution", "cost", "combos", "signals", "stats"]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data-dir", default="data")
    ap.add_argument("--out", default="results")
    ap.add_argument("--parts", default="all", help="쉼표 구분: " + ",".join(ALL_PARTS))
    ap.add_argument("--cache", default=".cache", help="일별 스마일 캐시 폴더 ('' 이면 캐시 안 씀)")
    ap.add_argument("--quick", action="store_true", help="순열검정 300회 (기본 2000회)")
    args = ap.parse_args()
    parts = ALL_PARTS if args.parts == "all" else [p.strip() for p in args.parts.split(",")]
    out = Path(args.out)
    figs, tabs = out / "figures", out / "tables"
    tabs.mkdir(parents=True, exist_ok=True)
    R = report.Reporter()
    t0 = time.time()

    ds = load_dataset(args.data_dir, cache_dir=args.cache or None)
    bt = Backtester(ds)
    dates = bt.dates
    R.header("데이터 요약")
    R.say(f"분석 가능 일수 {len(dates)}일  ({dates[0]} ~ {dates[-1]})")
    avail = {k: sum(1 for r in bt.rows if r[k] is not None) for k in ("skew", "skew25", "skew_sma3", "skew25_sma3", "term_slope", "vrp")}
    R.say("지표별 유효 일수: " + ", ".join(f"{k} {v}" for k, v in avail.items()))
    R.say("\n[지표 읽는 법]\n" + report.METRIC_LEGEND)
    take = []

    if "indicators" in parts:
        plots.indicators(bt.rows, ds.spot, figs)

    if "baseline" in parts:
        R.header("1. 세 전략 기본 백테스트 (W=40, |z|≥1.5, 청산 |z|<0.3, 최대보유 15일, 비용 0.5 IV-pt, 당일 종가 체결)")
        res = X.baseline(bt)
        res["table"].to_csv(tabs / "baseline_metrics.csv", index=False)
        res["trades"].to_csv(tabs / "baseline_trades.csv", index=False)
        R.table(report.single_view(res["table"]))
        plots.baseline(res["curves"], dates, figs)
        d = res["table"][res["table"].hedge == "daily"].set_index("name")
        for s in ("skew", "calendar", "vrp"):
            r = d.loc[s]
            take.append(f"[기본/일별헤지] {s}: 수익률 {report.f(r.total_return_pct)}%, MDD {r.mdd_pct:.2f}%p, 유효거래 {int(r.effective_trades)}건")

    if "execution" in parts:
        R.header("2. 체결 가정 민감도 (lag0=신호 당일 종가 체결, lag1=다음날 종가 체결 / hold=최대 보유일) — 앙상블")
        res = X.execution(bt)
        res["table"].to_csv(tabs / "execution_ensemble.csv", index=False)
        res["cells"].to_csv(tabs / "execution_cells.csv", index=False)
        R.table(report.ens_view(res["table"], ["name", "lag", "hold"]))
        plots.execution(res["curves"], res["cells"], dates, figs)
        t = res["table"]
        for s in X.STRATEGIES:
            a = t[(t.name == s) & (t.lag == 0) & (t.hold == 5)].iloc[0]
            b = t[(t.name == s) & (t.lag == 1) & (t.hold == 5)].iloc[0]
            take.append(f"[체결] {s}: 셀 평균수익률 당일체결 {report.f(a.mean_cell_return_pct)}% → 익일체결 {report.f(b.mean_cell_return_pct)}% (hold 5)")

    if "cost" in parts:
        R.header("3. 거래비용 민감도 (익일 체결, 보유 ≤5일) — 앙상블")
        res = X.cost(bt)
        res["table"].to_csv(tabs / "cost_sensitivity.csv", index=False)
        R.table(report.ens_view(res["table"], ["name", "cost_iv_pt"]))
        plots.cost(res["table"], figs)
        for n in ("BASE", "D25S"):
            be = report.breakeven_cost(res["table"], n)
            take.append(f"[비용] {n}: 손익분기 비용 " + (f"약 {be:.2f} IV-pt" if be is not None else "구간 내 없음(전 구간 같은 부호)"))

    if "combos" in parts:
        R.header("4. 스큐 변형 3종 조합 (S=손절 z +1.0, D=잔존 10일 미만 진입금지, M=중앙값/MAD z) — 앙상블, 보유 ≤5일")
        res = X.combos(bt)
        res["table"].to_csv(tabs / "skew_combos.csv", index=False)
        R.table(report.ens_view(res["table"], ["name", "lag"]))
        plots.combos(res["table"], figs)
        t = res["table"]
        for lag in (1, 0):
            base = t[(t.name == "BASE") & (t.lag == lag)].iloc[0].mean_cell_return_pct
            for n in ("S", "D", "M", "SDM"):
                v = t[(t.name == n) & (t.lag == lag)].iloc[0].mean_cell_return_pct
                take.append(f"[조합 lag{lag}] {n}: 셀 평균수익률 {report.f(v)}% (BASE 대비 {report.f(v - base)}%p)")

    if "signals" in parts:
        R.header("5. 신호 노이즈 저감: 25-delta 정의 × 3일 평활 (보유 ≤5일) — 앙상블")
        R.say("BASE=IV(.90)-IV(1.10) | SMA3=3일평균 | D25=25Δ 풋-콜 IV | D25L=신호D25+레그 25Δ | D25S=D25 3일평균 | D25SL=D25S+레그 25Δ")
        res = X.signals(bt)
        res["table"].to_csv(tabs / "signal_variants.csv", index=False)
        R.table(report.ens_view(res["table"], ["setting", "name"]))
        plots.signals(res["curves"], dates, figs)
        t = res["table"]
        a = t[t.setting == "lag1, cost 0.5"].sort_values("mean_cell_return_pct", ascending=False).iloc[0]
        take.append(f"[신호] 익일체결·비용0.5 최고: {a['name']} 셀 평균 {report.f(a.mean_cell_return_pct)}%, NW t {a.nw_t:+.2f}  (사후 선택이므로 낙관 편향 있음)")
        for n in ("BASE", "D25S"):
            l0 = t[(t.setting == "lag0, cost 0.5") & (t.name == n)].iloc[0].mean_cell_return_pct
            l1 = t[(t.setting == "lag1, cost 0.5") & (t.name == n)].iloc[0].mean_cell_return_pct
            take.append(f"[신호] {n}: 체결 지연 민감도 (당일 {report.f(l0)}% → 익일 {report.f(l1)}%, 차이 {report.f(l1 - l0)}%p)")

    if "stats" in parts:
        R.header("6. 스큐 평균회귀 통계검증:  Δskew(t→t+h) = a + b·z_t + e   (H1: b<0, 사전 지정 사양: W=40, h=10, 동일만기 쌍)")
        mr = stats_tests.mean_reversion_table(bt.rows, n_perm=300 if args.quick else 2000)
        mr.to_csv(tabs / "skew_mean_reversion.csv", index=False)
        show = mr[["W", "h", "same_expiry", "n_pairs", "n_nonoverlap", "b", "nw_t", "p_nw", "p_perm", "b_nonoverlap", "p_nonoverlap",
                   "r2", "dskew_z_gt1", "n_hi", "dskew_z_lt_m1", "n_lo", "primary"]]
        R.table(show, {"p_nw": "{:.3f}".format, "p_perm": "{:.3f}".format, "p_nonoverlap": "{:.3f}".format, "r2": "{:.3f}".format})
        R.say("\n[견고성] 진입 지연·잔존일 통제")
        rb = stats_tests.robustness_table(bt.rows)
        rb.to_csv(tabs / "skew_robustness.csv", index=False)
        R.table(rb, {"p_one_sided": "{:.3f}".format})
        nd = stats_tests.noise_diagnostics(bt.rows)
        R.say(f"\n[노이즈 진단] corr(skew, 잔존일) = {nd['corr_skew_dte']:+.3f}   |   일별 스큐 변화 1차 자기상관 = {nd['ac1_daily_change']:+.3f} (n={nd['ac1_n']})")
        R.table(nd["tenor_table"])
        prim = mr[mr.primary]
        if len(prim):
            p = prim.iloc[0]
            take.append(f"[통계] 사전지정 사양(W40,h10,동일만기): b={p.b:+.3f}, NW t={p.nw_t:+.2f}, p(NW)={p.p_nw:.3f}, p(순열)={p.p_perm:.3f}, p(비중첩)={p.p_nonoverlap:.3f}")
            plots.stats(*stats_tests.scatter_data(bt.rows, 40, 10), p, figs)
        take.append(f"[통계] 일별 스큐 변화 1차 자기상관 {nd['ac1_daily_change']:+.3f} (음수면 하루짜리 반등 성분)")

    R.header("핵심 결과 (모두 위 표에서 계산한 값)")
    for line in take:
        R.say(line)
    R.say("\n※ 다중비교·단일 사이클·소표본 한계가 있으므로 개별 셀의 수치를 근거로 삼지 말고 앙상블과 부호 패턴을 보세요.")
    R.say(f"\n실행 시간 {time.time() - t0:.0f}초.  그림: {figs}  /  표: {tabs}")
    R.save(out / "summary.txt")


if __name__ == "__main__":
    main()
