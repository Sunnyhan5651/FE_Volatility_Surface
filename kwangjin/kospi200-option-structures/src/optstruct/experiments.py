"""전략 목록과 실행.

전략 12개 = 구조 × 날개(0.90/1.10, 25Δ) × 델타헤지 조합.
스트랩·스트립은 델타헤지 없이만 넣는다: 매일 델타헤지하면 같은 베가의 스트래들과 손익이 똑같아진다
(같은 행사가의 콜과 풋은 감마·베가가 같고, 델타 차이는 헤지가 지운다).
"""
from __future__ import annotations

from dataclasses import dataclass, field

from . import config as C
from .engine import run
from .indicators import indicator_rows, realized_vol, rolling_z
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
    cols: dict = field(default_factory=dict)   # {열 이름: 지표 dict}


class Backtester:
    def __init__(self, ds):
        self.ds = ds
        self.rows = indicator_rows(ds.smiles, realized_vol(ds.spot))
        self.dates = [r["date"] for r in self.rows]
        vrp = [r["vrp"] for r in self.rows]
        self.z = {W: rolling_z(vrp, W) for W in C.WINDOWS}

    def signal(self, structure, hedge):
        """VRP 신호: W × E 9개 셀 평균, 당일/익일 체결."""
        res = Result(label(structure, hedge))
        for lag, col in ((0, "당일"), (1, "익일")):
            cells = [run(self.dates, self.ds, self.z[W], structure, hedge, entry_lag=lag, z_entry=E)
                     for W in C.WINDOWS for E in C.ENTRIES]
            res.cols[col] = summarize(self.dates, cells)
        return res

    def baseline(self, structure, hedge):
        """기준선: 신호 없이 같은 방향으로 계속 진입·롤 (보유 H 3개 셀 평균)."""
        res = Result(label(structure, hedge))
        for sgn, col in ((1.0, "매도"), (-1.0, "매수")):
            sig = [10.0 * sgn] * len(self.dates)
            cells = [run(self.dates, self.ds, sig, structure, hedge, max_hold=H) for H in C.BASELINE_HOLDS]
            res.cols[col] = summarize(self.dates, cells)
        return res


def run_all(bt: Backtester, baseline=False):
    f = bt.baseline if baseline else bt.signal
    return [f(s, h) for s, h in STRATEGIES]
