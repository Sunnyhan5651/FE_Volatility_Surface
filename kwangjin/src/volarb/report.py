"""콘솔 출력용 표."""
from __future__ import annotations

import pandas as pd

pd.set_option("display.width", 250)
pd.set_option("display.max_columns", 50)
pd.set_option("display.unicode.east_asian_width", True)


def show(df: pd.DataFrame, formats: dict | None = None):
    print(df.to_string(index=False, float_format=lambda v: f"{v:,.2f}", formatters=formats or {}))


def strategy_table(results) -> pd.DataFrame:
    rows = []
    for r in results:
        m = r["m"]
        rows.append({
            "전략": r["strategy"], "체결": r["fill"],
            "누적수익률%": m["total_return_pct"], "Sharpe": m["sharpe"],
            "MDD%p": m["mdd_pct"], "최악셀MDD%p": m["worst_cell_mdd_pct"],
            "거래당평균%": m["avg_trade_pct"], "승률%": m["win_rate_pct"],
            "거래수": m["mean_cell_eff_trades"], "NW_t": m["nw_t"]})
    return pd.DataFrame(rows)


def stats_tables(mr: pd.DataFrame, rb: pd.DataFrame):
    a = mr[mr.same_expiry].copy()
    a["사전지정"] = a.primary.map({True: "*", False: ""})
    a = a[["W", "h", "n_pairs", "b", "nw_t", "p_nw", "p_perm", "p_nonoverlap", "사전지정"]].rename(columns={
        "n_pairs": "쌍수", "nw_t": "NW_t", "p_nw": "p(NW)", "p_perm": "p(순열)", "p_nonoverlap": "p(비중첩)"})
    f3 = lambda v: "-" if v != v else ("<0.001" if v < 0.001 else f"{v:.3f}")
    b = rb[(rb.W == 40) & rb.spec.isin(["baseline", "skip 1 day", "skip 2 days", "control DTE"])].rename(
        columns={"spec": "사양", "nw_t": "NW_t", "p_one_sided": "p(단측)"})
    return a, {"p(NW)": f3, "p(순열)": f3, "p(비중첩)": f3}, b, {"p(단측)": f3}
