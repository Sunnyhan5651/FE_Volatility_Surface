"""결과표 출력."""
from __future__ import annotations

import pandas as pd

COLUMNS = {
    "누적수익률": ("누적수익률 %", "{:+.2f}"),
    "비용제외": ("비용 제외 %", "{:+.2f}"),
    "Sharpe": ("Sharpe", "{:.2f}"),
    "MDD": ("MDD %", "{:.2f}"),
    "롤당평균": ("롤당 평균 %", "{:+.3f}"),
    "승률": ("승률 %", "{:.0f}"),
    "롤횟수": ("롤 횟수", "{:d}"),
    "대체평가": ("대체평가 %", "{:.0f}"),
    "NW_t": ("NW t", "{:.2f}"),
}


def table(results) -> pd.DataFrame:
    recs = []
    for r in results:
        rec = {"전략": r.name}
        for k, (name, fmt) in COLUMNS.items():
            v = r.metrics[k]
            rec[name] = "nan" if v != v else fmt.format(v)
        recs.append(rec)
    return pd.DataFrame(recs)


def show(df: pd.DataFrame):
    with pd.option_context("display.unicode.east_asian_width", True, "display.max_columns", None,
                           "display.width", 250, "display.max_rows", None):
        print(df.to_string(index=False))
