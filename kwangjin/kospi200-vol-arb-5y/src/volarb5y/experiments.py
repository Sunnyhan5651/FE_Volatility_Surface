"""비교할 전략 목록과 실행.

전략 15개 = 기본 3개(스큐·캘린더·VRP) + 스큐 변형 12개
  변형 이름: S=손절(진입 z보다 1.0 더 벌어지면 청산), D=잔존 10일 미만 진입 금지, M=중앙값/MAD z,
            SMA3=신호 3일 평활, D25=25델타 신호, L=거래 행사가도 25델타
각 전략을 '당일 종가 체결'과 '익일 종가 체결' 두 가정으로 돌린다.
공통 설정: 보유 ≤5일, 청산 |z|<0.3, 비용 0.5 IV-pt, 일별 델타 재헤지,
          결과는 윈도우 {20,40,60} × 진입 |z| {1.0,1.5,2.0} 9개 셀의 일별 손익 평균(앙상블).
"""
from __future__ import annotations

from dataclasses import replace

from .backtest import Backtester, Spec
from .config import Params

BASE = Params(z_window=40, z_entry=1.5, z_exit=0.3, max_hold=5, rehedge=True, cost_iv_pt=0.5)
STOP_DZ = 1.0
MIN_DTE = 10

STRATEGIES = [
    # (이름, Spec, 손절 z폭)
    ("스큐 (기본)", Spec("skew"), None),
    ("캘린더", Spec("calendar"), None),
    ("VRP", Spec("vrp"), None),
    ("스큐 + S", Spec("skew"), STOP_DZ),
    ("스큐 + D", Spec("skew", min_dte=MIN_DTE), None),
    ("스큐 + M", Spec("skew", robust=True), None),
    ("스큐 + S + D", Spec("skew", min_dte=MIN_DTE), STOP_DZ),
    ("스큐 + S + M", Spec("skew", robust=True), STOP_DZ),
    ("스큐 + D + M", Spec("skew", min_dte=MIN_DTE, robust=True), None),
    ("스큐 + S + D + M", Spec("skew", min_dte=MIN_DTE, robust=True), STOP_DZ),
    ("스큐 SMA3", Spec("skew", signal="skew_sma3"), None),
    ("스큐 D25", Spec("skew", signal="skew25"), None),
    ("스큐 D25L", Spec("skew", signal="skew25", legs="delta25"), None),
    ("스큐 D25S", Spec("skew", signal="skew25_sma3"), None),
    ("스큐 D25SL", Spec("skew", signal="skew25_sma3", legs="delta25"), None),
]
FILLS = (("당일 체결", 0), ("익일 체결", 1))


def run_all(bt: Backtester) -> list[dict]:
    out = []
    for name, spec, stop in STRATEGIES:
        for fill, lag in FILLS:
            ens = bt.ensemble(spec, replace(BASE, entry_lag=lag, stop_dz=stop))
            out.append(dict(strategy=name, fill=fill, equity=ens["equity"], m=ens["metrics"]))
    return out
