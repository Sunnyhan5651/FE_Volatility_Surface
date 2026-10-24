"""콘솔 출력 + results/summary.txt 저장. 성과 수치는 여기(표/문장)로만 출력한다."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

pd.set_option("display.width", 200)
pd.set_option("display.max_columns", 50)


class Reporter:
    def __init__(self):
        self.lines: list[str] = []

    def say(self, text: str = ""):
        print(text)
        self.lines.append(text)

    def header(self, text: str):
        self.say("\n" + "=" * 100)
        self.say(text)
        self.say("=" * 100)

    def table(self, df: pd.DataFrame, formats: dict | None = None):
        self.say(df.to_string(index=False, float_format=lambda v: f"{v:,.2f}", formatters=formats or {}))

    def save(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(self.lines), encoding="utf-8")


METRIC_LEGEND = (
    "수익률은 거래별 진입 선물가 대비 %, 일별 가산(additive) 누적.  Sharpe = 연환산수익률/연환산변동성.\n"
    "MDD = 누적손익 곡선의 고점 대비 최대 낙폭(%p).  MDD일수 = 고점 갱신 없이 지난 최장 거래일.\n"
    "유효거래 = 손익이 0이 아닌 거래.  앙상블 = 윈도우 {20,40,60} × 진입 |z| {1.0,1.5,2.0} 9개 셀의 일별 손익 평균\n"
    "(사후에 좋은 셀을 고르지 않기 위한 사전 지정 평균).  NW t = 앙상블 일별손익 평균의 Newey-West t (lag 5)."
)

SINGLE_COLS = ["name", "hedge", "total_return_pct", "ann_vol_pct", "sharpe", "mdd_pct", "mdd_days", "calmar",
               "effective_trades", "win_rate_pct", "avg_trade_pct", "profit_factor", "worst_trade_pct", "avg_hold_days"]
ENS_COLS = ["mean_cell_return_pct", "pos", "mean_cell_sharpe", "mean_cell_mdd_pct", "mean_cell_eff_trades", "mdd_pct", "nw_t"]
ENS_RENAME = {"mean_cell_return_pct": "cell_ret%", "pos": "+cells", "mean_cell_sharpe": "cell_Sharpe", "mean_cell_mdd_pct": "cell_MDD%",
              "mean_cell_eff_trades": "eff_trades", "mdd_pct": "ens_MDD%", "nw_t": "NW_t"}
SINGLE_RENAME = {"name": "strategy", "total_return_pct": "ret%", "ann_vol_pct": "vol%", "mdd_pct": "MDD%", "mdd_days": "MDD_days",
                 "calmar": "Calmar", "sharpe": "Sharpe", "effective_trades": "trades", "win_rate_pct": "win%",
                 "avg_trade_pct": "avg_trade%", "profit_factor": "PF", "worst_trade_pct": "worst%", "avg_hold_days": "hold_d"}


def single_view(df: pd.DataFrame, cols=SINGLE_COLS) -> pd.DataFrame:
    return df[[c for c in cols if c in df.columns]].rename(columns=SINGLE_RENAME)


def ens_view(df: pd.DataFrame, lead: list[str]) -> pd.DataFrame:
    d = df.copy()
    d["pos"] = d.pos_cells.astype(int).astype(str) + "/" + d.n_cells.astype(int).astype(str)
    return d[lead + ENS_COLS].rename(columns=ENS_RENAME)


def f(v, n=2, sign=True):
    return f"{v:+.{n}f}" if sign else f"{v:.{n}f}"


def breakeven_cost(table: pd.DataFrame, name: str):
    """앙상블 수익률이 0을 지나는 비용(IV pt) 선형 보간. 전 구간 양/음이면 None."""
    t = table[table.name == name].sort_values("cost_iv_pt")
    xs, ys = t.cost_iv_pt.values, t.total_return_pct.values
    for i in range(len(xs) - 1):
        if ys[i] > 0 >= ys[i + 1]:
            return float(xs[i] + (ys[i] / (ys[i] - ys[i + 1])) * (xs[i + 1] - xs[i]))
    return None


def mdd_rows(group: str, df: pd.DataFrame, setting_fn) -> list[dict]:
    """각 전략·조합의 MDD 한 줄 요약. 앙상블이면 셀별 MDD도 함께 담는다 (단일 셀은 세 값이 같음)."""
    out = []
    for _, r in df.iterrows():
        single = "worst_cell_mdd_pct" not in r or pd.isna(r.get("worst_cell_mdd_pct"))
        out.append(dict(
            group=group, name=r["name"], setting=setting_fn(r),
            MDD_ens=r["mdd_pct"],
            MDD_worst=r["mdd_pct"] if single else r["worst_cell_mdd_pct"],
            MDD_avg=r["mdd_pct"] if single else r["mean_cell_mdd_pct"],
            MDD_days=r["mdd_days"],
            eff_trades=r["effective_trades"] if single else r["mean_cell_eff_trades"],
            cell_mdds="" if single else r["cell_mdd_list"]))
    return out
