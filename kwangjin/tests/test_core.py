"""핵심 로직 단위 테스트 (합성 데이터, 원자료 불필요).  실행: pytest -q"""
import math

from volarb import config as C
from volarb.config import Params
from volarb.data import Smile
from volarb.engine import run_engine, to_equity
from volarb.indicators import delta_strike, rolling_z, skew25, sma_within_expiry
from volarb.metrics import compute_metrics, drawdown_series, max_drawdown_duration, newey_west_t
from volarb.pricing import bs76


def test_put_call_parity():
    F, K, T, s, r = 100.0, 95.0, 0.25, 0.3, C.RISK_FREE
    c, _, _ = bs76(F, K, T, s, r, "C")
    p, _, _ = bs76(F, K, T, s, r, "P")
    assert abs((c - p) - math.exp(-r * T) * (F - K)) < 1e-9


def test_drawdown_and_duration():
    eq = [0, 1, 3, 2, 1, 4, 3]
    assert min(drawdown_series(eq)) == -2
    assert max_drawdown_duration(eq) == 2           # 3(고점) 이후 2, 1 두 날
    m = compute_metrics(eq, [0.01, -0.02])
    assert m["mdd_pct"] == -200.0


def test_rolling_z_has_no_lookahead():
    rows = [{"x": float(i % 7)} for i in range(80)]
    z1 = rolling_z(rows, "x", 20)
    rows2 = [dict(r) for r in rows]
    rows2[60]["x"] = 1e6                              # 미래 값을 바꿔도 이전 z는 불변
    z2 = rolling_z(rows2, "x", 20)
    assert z1[:60] == z2[:60]


def test_sma_does_not_cross_expiry():
    rows = [{"near_expiry": "A", "k": 1.0}, {"near_expiry": "A", "k": 3.0}, {"near_expiry": "B", "k": 100.0},
            {"near_expiry": "B", "k": 102.0}]
    out = sma_within_expiry(rows, "k", n=3, min_valid=2)
    assert out[1] == 2.0 and out[2] is None and out[3] == 101.0


def _flat_smile(iv=30.0, days=30, F=100.0):
    pts = tuple((0.80 + 0.01 * k, iv) for k in range(41))
    return Smile("E1", days, F, pts)


def test_25_delta_strikes_on_flat_smile():
    sm = _flat_smile()
    s, kp, kc = skew25(sm)
    assert abs(s) < 1e-9 and kp < 1.0 < kc
    # 25델타 풋/콜은 ATM 기준 대칭에 가깝다 (로그 기준)
    assert abs(math.log(kp) + math.log(kc)) < 0.02
    assert delta_strike(sm, "P")[1] == 30.0


def test_engine_long_straddle_loses_theta_when_nothing_moves():
    days = ["2026%04d" % (101 + i) for i in range(12)]
    smiles = {d: {"E1": _flat_smile(days=30 - i)} for i, d in enumerate(days)}
    rows = {d: {"near_expiry": "E1", "far_expiry": "E1"} for d in days}
    z = [None, -2.0] + [None] * 10                    # 둘째 날 매수 신호
    z[5] = 0.0

    def builder(zi, row, sm):
        F = sm["E1"].forward
        return [dict(expiry="E1", right="C", K=F, qty=1.0), dict(expiry="E1", right="P", K=F, qty=1.0)], F, "BUY"

    res = run_engine(days, rows, z, smiles, builder, Params(z_entry=1.5, cost_iv_pt=0.0, max_hold=15))
    assert len(res.trades) == 1 and res.trades[0] < 0       # IV·선물 불변 -> 시간가치 감소만큼 손실
    assert abs(sum(res.daily.values()) - res.trades[0]) < 1e-12
    assert to_equity(days, res.daily)[-1] == sum(res.daily.values())


def test_engine_cost_hurts():
    days = ["2026%04d" % (101 + i) for i in range(8)]
    smiles = {d: {"E1": _flat_smile(days=30 - i)} for i, d in enumerate(days)}
    rows = {d: {"near_expiry": "E1", "far_expiry": "E1"} for d in days}
    z = [None, 2.0, None, 0.0, None, None, None, None]

    def builder(zi, row, sm):
        F = sm["E1"].forward
        return [dict(expiry="E1", right="C", K=F, qty=-1.0), dict(expiry="E1", right="P", K=F, qty=-1.0)], F, "SELL"

    free = run_engine(days, rows, z, smiles, builder, Params(cost_iv_pt=0.0))
    paid = run_engine(days, rows, z, smiles, builder, Params(cost_iv_pt=1.0))
    assert paid.trades[0] < free.trades[0]


def test_newey_west_t_of_constant_plus_noise():
    x = [0.1 + (0.01 if i % 2 else -0.01) for i in range(200)]
    m, t = newey_west_t(x, 3)
    assert abs(m - 0.1) < 1e-9 and t > 10
