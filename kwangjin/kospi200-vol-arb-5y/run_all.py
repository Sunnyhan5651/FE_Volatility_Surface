#!/usr/bin/env python3
"""스큐 기반 전략 15개의 결과표·통계검정을 출력하고, 전략별 누적수익률 그래프(1장씩)를 화면에 띄운다.
5년 판: 데이터 폴더의 기간별 원자료 파일(2021-08 ~ )을 모두 읽어 이어 붙인다.

사용 예
  python run_all.py                    # 표 출력 + 그래프 15장 표시
  python run_all.py --no-plot          # 표만
  python run_all.py --save figures     # 그래프를 figures/ 에 PNG 로도 저장
  python run_all.py --by-year          # 연도별 손익 표 추가
  python run_all.py --quick            # 순열검정 횟수를 줄여 빠르게
  python run_all.py --data-dir D:\\data # 데이터 폴더 직접 지정 (기본: 자동 탐색)

Spyder: 이 파일을 열고 F5. 그래프는 Plots 창에 전략별로 한 장씩 나온다.
"""

import argparse
import statistics as st
import sys
from pathlib import Path

PKG = "volarb5y"
REPO = "kospi200-vol-arb-5y"


def _candidate_roots():
    """스크립트 위치, 현재 작업 폴더, 바탕화면·다운로드·문서 폴더(OneDrive/한글 이름 포함)."""
    try:
        here = Path(__file__).resolve().parent
    except NameError:                      # 일부 IDE에서 __file__ 이 없을 때
        here = Path.cwd()
    home = Path.home()
    names = ["Desktop", "바탕 화면", "바탕화면", "Downloads", "다운로드", "Documents", "문서"]
    spots = [home / n for n in names] + [home / "OneDrive" / n for n in names]
    return [here, Path.cwd()] + [p for p in spots if p.is_dir()]


def find_repo_root() -> Path:
    roots = _candidate_roots()
    for r in roots:
        for c in (r, r / REPO, r / REPO / REPO):
            if (c / "src" / PKG).is_dir():
                return c
    for r in roots[2:]:
        try:
            subs = list(r.iterdir())
        except OSError:
            continue
        for sub in subs:
            if sub.is_dir() and (sub / "src" / PKG).is_dir():
                return sub
    raise FileNotFoundError(f"src/{PKG} 폴더를 찾지 못했습니다.")


def _has_data(d: Path) -> bool:
    """kospi200*options_regular.csv(.gz) 와 kospi200*spot.csv(.gz) 가 함께 있는 폴더."""
    try:
        names = [p.name for p in d.iterdir()]
    except OSError:
        return False
    has = lambda tail: any(n.startswith("kospi200") and (n.endswith(tail) or n.endswith(tail + ".gz"))  # noqa: E731
                           for n in names)
    return has("options_regular.csv") and has("spot.csv")


def find_data_dir(root: Path) -> Path:
    """원자료 CSV 폴더: 저장소/data → 저장소 → 바탕화면·다운로드·문서 → 그 하위 폴더(2단계까지) 순."""
    roots = _candidate_roots()
    spots = [root / "data", root]
    for r in roots:
        spots += [r, r / "data"]
    for d in spots:
        if _has_data(d):
            return d
    for r in roots[2:]:                        # 바탕화면 등의 하위 폴더 (예: 바탕화면/변동성 표면)
        try:
            subs = sorted(p for p in r.iterdir() if p.is_dir() and not p.name.startswith("."))
        except OSError:
            continue
        for s in subs:
            try:
                kids = sorted(p for p in s.iterdir() if p.is_dir() and not p.name.startswith("."))
                for d in [s, s / "data"] + kids:
                    if _has_data(d):
                        return d
            except OSError:                    # 접근 권한 없는 폴더는 건너뜀
                continue
    raise FileNotFoundError(
        "원자료 CSV를 찾지 못했습니다. 기간별 kospi200_*_options_regular / futures_regular / spot 파일을 "
        f"{root / 'data'} 에 넣거나, --data-dir 로 폴더를 지정하세요.")


ROOT = find_repo_root()
sys.path.insert(0, str(ROOT / "src"))

from volarb5y import config as C  # noqa: E402
from volarb5y import experiments as X  # noqa: E402
from volarb5y import report, stats_tests  # noqa: E402
from volarb5y.backtest import Backtester  # noqa: E402
from volarb5y.data import load_dataset  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data-dir", default=None, help="원자료 폴더 (생략하면 자동 탐색)")
    ap.add_argument("--no-plot", action="store_true", help="그래프를 띄우지 않음")
    ap.add_argument("--save", default=None, help="그래프를 PNG 로 저장할 폴더")
    ap.add_argument("--by-year", action="store_true", help="연도별 손익 표도 출력")
    ap.add_argument("--quick", action="store_true", help="순열검정 300회 (기본 2000회)")
    args, _ = ap.parse_known_args()          # Spyder 등이 넘기는 인자는 무시
    data_dir = Path(args.data_dir) if args.data_dir else find_data_dir(ROOT)

    ds = load_dataset(data_dir, cache_dir=ROOT / ".cache")
    bt = Backtester(ds)
    results = X.run_all(bt)

    sp = dict(ds.spot)
    d0, d1 = bt.dates[0], bt.dates[-1]
    iv = [r["near_atm"] for r in bt.rows if r["near_atm"] is not None]
    rv = [r["rv20"] for r in bt.rows if r["rv20"] is not None]
    print("\n" + "=" * 100)
    print(f"전략별 결과  |  {d0} ~ {d1} ({len(bt.dates)}일)  |  데이터: {data_dir}")
    print("=" * 100)
    print(f"시장: KOSPI200 {sp[d0]:.2f} → {sp[d1]:.2f} ({100 * (sp[d1] / sp[d0] - 1):+.1f}%), "
          f"근월 ATM IV 평균 {st.mean(iv):.1f}% / 20일 실현변동성 평균 {st.mean(rv):.1f}%")
    print("각 전략 = 윈도우 {20,40,60} × 진입|z| {1.0,1.5,2.0} 9개 셀 평균 | 보유 ≤5일, 비용 0.5 IV-pt, 일별 델타 재헤지")
    print(f"선물 헤지 비용 1단위당 {C.FUT_COST_PT}pt | 보유 레그 잔존 {C.MIN_EXIT_DTE}일 미만이 된 날 종가 청산")
    print("S=손절  D=잔존 10일 미만 금지  M=중앙값 z  SMA3=3일 평활  D25=25델타 신호  L=25델타 행사가로 거래")
    print("수익률은 거래별 진입 선물가 기준 %, MDD는 잔고(1 + 누적손익) 고점 대비 최대 낙폭(%), 거래수는 셀당 평균 유효 거래 수")
    print("NW_t = 일별손익 평균의 Newey-West t (|t|≥2 가 대략 유의)\n")
    report.show(report.strategy_table(results))

    if args.by_year:
        print("\n" + "=" * 100)
        print("연도별 손익 % (진입 선물가 기준 단순 합산)")
        print("=" * 100)
        for y in sorted({d[:4] for d in bt.dates}):
            dd = [r for r in bt.rows if r["date"][:4] == y]
            ivs = [r["near_atm"] for r in dd if r["near_atm"] is not None]
            rvs = [r["rv20"] for r in dd if r["rv20"] is not None]
            print(f"  {y}: KOSPI200 {100 * (sp[dd[-1]['date']] / sp[dd[0]['date']] - 1):+.1f}%, "
                  f"근월 ATM IV 평균 {st.mean(ivs):.1f}% / RV20 평균 {st.mean(rvs):.1f}%")
        print()
        report.show(report.yearly_table(results, bt.dates))

    print("\n" + "=" * 100)
    print("통계검정: 스큐 평균회귀  Δskew(t→t+h) = a + b·z_t + e   (H1: b<0, 같은 만기 쌍, * = 사전지정 사양)")
    print("=" * 100)
    mr = stats_tests.mean_reversion_table(bt.rows, n_perm=300 if args.quick else 2000)
    rb = stats_tests.robustness_table(bt.rows)
    a, fa, b, fb = report.stats_tables(mr, rb)
    report.show(a, fa)
    print("\n진입을 하루·이틀 미루거나 잔존일을 통제했을 때 (W=40)")
    report.show(b, fb)
    nd = stats_tests.noise_diagnostics(bt.rows)
    print(f"\n일별 스큐 변화 1차 자기상관 {nd['ac1_daily_change']:+.3f} | 스큐와 잔존일 상관 {nd['corr_skew_dte']:+.3f}")

    if not args.no_plot:
        from volarb5y import plots
        plots.show_all(results, bt.dates, args.save)


if __name__ == "__main__":
    main()
