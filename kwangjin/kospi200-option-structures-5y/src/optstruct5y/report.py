"""결과표 출력."""
from __future__ import annotations

import pandas as pd

COLUMNS = {
    "누적수익률": ("누적수익률 %", "{:+.2f}"),
    "Sharpe": ("Sharpe", "{:.2f}"),
    "MDD": ("MDD %", "{:.2f}"),
    "최악셀MDD": ("최악셀 MDD %", "{:.2f}"),
    "거래당평균": ("거래당 평균 %", "{:+.3f}"),
    "승률": ("승률 %", "{:.0f}"),
    "거래수": ("거래수", "{:.1f}"),
    "매도비중": ("매도 비중 %", "{:.0f}"),
    "대체평가": ("대체평가 %", "{:.0f}"),
    "NW_t": ("NW t", "{:.2f}"),
}


def table(results) -> pd.DataFrame:
    recs = []
    for r in results:
        for col, m in r.cols.items():
            rec = {"전략": r.name, "체결" if col in ("당일", "익일") else "방향": col}
            for k, (name, fmt) in COLUMNS.items():
                v = m[k]
                rec[name] = "nan" if v != v else fmt.format(v)
            recs.append(rec)
    return pd.DataFrame(recs)


def yearly_table(results, dates) -> pd.DataFrame:
    """전략·체결별 연도별 손익 (%, 진입 선물가 기준 단순 합산). 누적곡선(curve)의 연도별 증분."""
    years = sorted({d[:4] for d in dates})
    recs = []
    for r in results:
        for col, m in r.cols.items():
            c = m["curve"]
            rec = {"전략": r.name, "체결": col}
            prev = 0.0
            for y in years:
                last = max(i for i, d in enumerate(dates) if d[:4] == y)
                rec[y] = "{:+.2f}".format(c[last] - prev)
                prev = c[last]
            rec["합계"] = "{:+.2f}".format(c[-1])
            recs.append(rec)
    return pd.DataFrame(recs)


def show(df: pd.DataFrame):
    with pd.option_context("display.unicode.east_asian_width", True, "display.max_columns", None,
                           "display.width", 250, "display.max_rows", None):
        print(df.to_string(index=False))
