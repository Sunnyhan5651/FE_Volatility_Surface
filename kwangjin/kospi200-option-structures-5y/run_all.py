#!/usr/bin/env python3
"""VRP 신호 기반 옵션 구조 전략 12개의 결과표를 출력하고, 전략별 누적수익률 그래프(1장씩)를 화면에 띄운다.
5년 판: 데이터 폴더의 기간별 원자료 파일(2021-08 ~ )을 모두 읽어 이어 붙인다.

사용 예
  python run_all.py                    # 결과표 + 그래프 12장
  python run_all.py --no-plot          # 결과표만
  python run_all.py --save figures     # 그래프를 figures/ 에 PNG 로도 저장
  python run_all.py --baseline         # 신호 없이 계속 매도/매수한 기준선 표 추가 (그래프 없음)
  python run_all.py --by-year          # 연도별 손익 표 추가
  python run_all.py --data-dir D:\\data # 데이터 폴더 직접 지정 (기본: 자동 탐색)

Spyder: 이 파일을 열고 F5. 그래프는 Plots 창에 전략별로 한 장씩 나온다.
"""

import argparse
import statistics as st
import sys
from pathlib import Path

PKG = "optstruct5y"
REPO = "kospi200-option-structures-5y"


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
        for sub in r.iterdir():
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

from optstruct5y import config as C  # noqa: E402
from optstruct5y import experiments as X  # noqa: E402
from optstruct5y import report  # noqa: E402
from optstruct5y.data import load_dataset  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data-dir", default=None, help="원자료 폴더 (생략하면 자동 탐색)")
    ap.add_argument("--no-plot", action="store_true", help="그래프를 띄우지 않음")
    ap.add_argument("--save", default=None, help="그래프를 PNG 로 저장할 폴더")
    ap.add_argument("--baseline", action="store_true", help="신호 없는 매도/매수 기준선 표도 출력")
    ap.add_argument("--by-year", action="store_true", help="연도별 손익 표도 출력")
    args, _ = ap.parse_known_args()          # Spyder 등이 넘기는 인자는 무시
    data_dir = Path(args.data_dir) if args.data_dir else find_data_dir(ROOT)

    ds = load_dataset(data_dir, cache_dir=ROOT / ".cache")
    bt = X.Backtester(ds)
    results = X.run_all(bt)

    sp = dict(ds.spot)
    d0, d1 = bt.dates[0], bt.dates[-1]
    iv = [r["atm_iv"] for r in bt.rows if r["atm_iv"] is not None]
    rv = [r["rv20"] for r in bt.rows if r["rv20"] is not None]
    print("\n" + "=" * 110)
    print(f"전략별 결과  |  {d0} ~ {d1} ({len(bt.dates)}일)  |  데이터: {data_dir}")
    print("=" * 110)
    print(f"시장: KOSPI200 {sp[d0]:.2f} → {sp[d1]:.2f} ({100 * (sp[d1] / sp[d0] - 1):+.1f}%), "
          f"근월 ATM IV 평균 {st.mean(iv):.1f}% / 20일 실현변동성 평균 {st.mean(rv):.1f}%")
    print("신호: z(근월 ATM IV − RV20) ≥ E 이면 변동성 매도, ≤ −E 이면 매수 | "
          "각 전략 = 윈도우 {20,40,60} × 진입|z| {1.0,1.5,2.0} 9개 셀 평균")
    print(f"청산: |z|<{C.Z_EXIT}, 보유 {C.MAX_HOLD}일, 잔존 {C.MIN_EXIT_DTE}일 미만 | "
          f"거래 만기: 잔존 {C.MIN_ENTRY_DTE}일 이상 최근월 | 비용 레그당 {C.COST_IV_PT} IV-pt (진입·청산), 헤지 선물 1단위당 {C.FUT_COST_PT}pt")
    print("크기: 구조 베가 = ATM 스트래들 1개 (콜 버터플라이만 몸통 ATM 콜 2개 기준) | 수익률 = 진입 선물가 대비 %, 가산 누적")
    print("당일/익일 = 신호가 나온 날 / 다음 날 종가에 체결 | 거래수 = 셀당 평균 유효 거래 | 매도 비중 = 변동성 매도 거래 비율")
    print("대체평가 = 보유일 중 행사가가 스마일 밖이라 외삽·직전 IV로 평가한 날 비율 | NW t: |t|≥2 가 대략 유의\n")
    report.show(report.table(results))

    if args.by_year:
        print("\n" + "=" * 110)
        print("연도별 손익 % (진입 선물가 기준 단순 합산, 당일 / 익일 체결)")
        print("=" * 110)
        for y in sorted({d[:4] for d in bt.dates}):
            dd = [r for r in bt.rows if r["date"][:4] == y]
            ivs = [r["atm_iv"] for r in dd if r["atm_iv"] is not None]
            rvs = [r["rv20"] for r in dd if r["rv20"] is not None]
            print(f"  {y}: KOSPI200 {100 * (sp[dd[-1]['date']] / sp[dd[0]['date']] - 1):+.1f}%, "
                  f"근월 ATM IV 평균 {st.mean(ivs):.1f}% / RV20 평균 {st.mean(rvs):.1f}%")
        print()
        report.show(report.yearly_table(results, bt.dates))

    if args.baseline:
        print("\n" + "=" * 110)
        print("기준선: 신호 없이 같은 방향으로 계속 진입, 보유 {5,10,20}일 3개 셀 평균 (변동성 위험 프리미엄 자체)")
        print("=" * 110)
        report.show(report.table(X.run_all(bt, baseline=True)))

    if not args.no_plot:
        from optstruct5y import plots
        plots.show_all(results, bt.dates, args.save)


if __name__ == "__main__":
    main()
