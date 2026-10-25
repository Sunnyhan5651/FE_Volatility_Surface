"""전략 목록과 실행.

전략 12개 = 구조 × 날개(0.90/1.10, 25Δ) × 델타헤지 조합. 모두 변동성 매수 방향.
스트랩·스트립은 델타헤지 없이만 넣는다: 매일 델타헤지하면 같은 베가의 스트래들과 손익이 똑같아진다
(같은 행사가의 콜과 풋은 감마·베가가 같고, 콜·풋 비율로 만든 방향 노출은 헤지가 지운다).
"""
from __future__ import annotations

from dataclasses import dataclass

from .engine import run
from .indicators import indicator_rows, realized_vol
from .metrics import summarize
from .structures import Structure

STRATEGIES = [
    # (구조, 헤지)
    (Structure("straddle", None), "none"),
    (Structure("straddle", None), "daily"),
    (Structure("strangle", "kf"), "none"),
    (Structure("strangle", "kf"), "daily"),
    (Structure("strangle", "d25"), "none"),
    (Structure("strangle", "d25"), "daily"),
    (Structure("strap", None), "none"),
    (Structure("strip", None), "none"),
    (Structure("butterfly", "kf"), "none"),
    (Structure("butterfly", "kf"), "daily"),
    (Structure("butterfly", "d25"), "none"),
    (Structure("butterfly", "d25"), "daily"),
]


def label(structure, hedge):
    return structure.name + (" + 델타헤지" if hedge == "daily" else "")


@dataclass
class Result:
    name: str
    metrics: dict


class Backtester:
    def __init__(self, ds):
        self.ds = ds
        self.rows = indicator_rows(ds.smiles, realized_vol(ds.spot))
        self.dates = [r["date"] for r in self.rows]

    def evaluate(self, structure, hedge):
        daily, trades = run(self.dates, self.ds, structure, hedge)
        m = summarize(self.dates, daily, trades)
        free_daily, free_trades = run(self.dates, self.ds, structure, hedge, cost=0.0, fut_cost=0.0)
        m["비용제외"] = summarize(self.dates, free_daily, free_trades)["누적수익률"]
        m["daily"] = daily
        return Result(label(structure, hedge), m)


def run_all(bt: Backtester):
    return [bt.evaluate(s, h) for s, h in STRATEGIES]
