"""핵심 로직 단위 테스트 (원자료 불필요, 합성 데이터 사용).  실행: pytest -q"""
import math
import random
import sys
from datetime import date, timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from optstruct5y import config as C  # noqa: E402
from optstruct5y.data import Dataset, Smile  # noqa: E402
from optstruct5y.engine import run  # noqa: E402
from optstruct5y.metrics import max_drawdown  # noqa: E402
from optstruct5y.indicators import rolling_z  # noqa: E402
from optstruct5y.pricing import bs76, strike_for_delta  # noqa: E402
from optstruct5y.structures import Structure, build  # noqa: E402

GRID = tuple(round(0.85 + 0.025 * i, 3) for i in range(13))     # K/F 0.85 ~ 1.15


def flat_smile(F, days, iv=40.0, expiry="209912"):
    return Smile(expiry, days, F, tuple((m, iv) for m in GRID))


def synthetic(n=40, F0=500.0, vol=0.30, seed=1, jump_day=None, jump=0.0, iv=40.0):
    """하나의 만기(잔존 60일에서 시작)에 플랫 스마일, 선물은 랜덤워크. jump_day 에 큰 점프."""
    rng = random.Random(seed)
    d0 = date(2030, 1, 1)
    dates, smiles, fwd = [], {}, {}
    F, k = F0, 0
    while len(dates) < n:
        d = d0 + timedelta(days=k)
        k += 1
        if d.weekday() >= 5:
            continue
        if dates:
            F *= math.exp(rng.gauss(0, vol / math.sqrt(252)))
        if jump_day is not None and len(dates) == jump_day:
            F *= 1 + jump
        ds = d.strftime("%Y%m%d")
        dates.append(ds)
        days = 60 - (d - d0).days
        smiles[ds] = {"209912": flat_smile(F, days, iv)}
        fwd[ds] = {"209912": F}
    return dates, Dataset(smiles=smiles, fwd=fwd, spot=[]), smiles


ALL = [Structure("straddle", None), Structure("strangle", "kf"), Structure("strangle", "d25"),
       Structure("strap", None), Structure("strip", None),
       Structure("butterfly", "kf"), Structure("butterfly", "d25")]


def test_put_call_parity():
    F, K, T, s = 500.0, 480.0, 0.1, 0.35
    c, dc, vc = bs76(F, K, T, s, "C")
    p, dp, vp = bs76(F, K, T, s, "P")
    disc = math.exp(-C.R * T)
    assert c - p == pytest.approx(disc * (F - K), abs=1e-9)
    assert dc - dp == pytest.approx(disc, abs=1e-12)
    assert vc == pytest.approx(vp)


def test_25_delta_strikes():
    sm = flat_smile(500.0, 30)
    for right in ("P", "C"):
        m = strike_for_delta(sm, right)
        d = bs76(500.0, m * 500.0, 30 / 365, 0.40, right)[1]
        assert abs(d) == pytest.approx(0.25, abs=1e-6)
    assert strike_for_delta(sm, "P") < 1 < strike_for_delta(sm, "C")


@pytest.mark.parametrize("wing", ["kf", "d25"])
def test_call_butterfly_tails_are_flat(wing):
    """콜 버터플라이(롱) 만기 손익: 양쪽 꼬리 0, 몸통에서 최대. 행사가 간격이 달라도 가중치로 맞춘다."""
    legs, F, _ = build(Structure("butterfly", wing), -1, {"x": flat_smile(500.0, 30)})
    payoff = lambda S: sum(l["qty"] * max(0.0, S - l["K"]) for l in legs)   # noqa: E731
    assert payoff(0.5 * F) == pytest.approx(0, abs=1e-9)
    assert payoff(2.0 * F) == pytest.approx(0, abs=1e-9)
    assert payoff(F) > 0
    assert sum(l["qty"] for l in legs if l["K"] == F) == pytest.approx(-2)


def test_vega_normalised_to_atm_straddle():
    sm = flat_smile(500.0, 30)
    T = 30 / 365
    target = 2 * bs76(500, 500, T, 0.40, "C")[2]
    for st in ALL[:5]:
        legs, _, _ = build(st, 1, {"x": sm})
        vega = sum(l["qty"] * bs76(500, l["K"], T, 0.40, l["right"])[2] for l in legs)
        assert vega == pytest.approx(target, rel=1e-9), st


@pytest.mark.parametrize("st", ALL)
@pytest.mark.parametrize("hedge", ["none", "daily"])
def test_long_short_mirror_without_cost(st, hedge):
    """비용이 0이면 매수와 매도 손익은 정확히 반대 (회계가 대칭)."""
    dates, ds, _ = synthetic()
    _, tl = run(dates, ds, [-10.0] * len(dates), st, hedge, max_hold=5, cost=0.0, fut_cost=0.0)
    _, ts = run(dates, ds, [10.0] * len(dates), st, hedge, max_hold=5, cost=0.0, fut_cost=0.0)
    assert len(tl) == len(ts) > 0
    for a, b in zip(tl, ts):
        assert a.pnl == pytest.approx(-b.pnl, abs=1e-12)


@pytest.mark.parametrize("st", ALL)
def test_cost_always_hurts(st):
    """비용은 매수·매도 어느 쪽이든 손익을 줄인다."""
    dates, ds, _ = synthetic()
    for s in (10.0, -10.0):
        _, t0 = run(dates, ds, [s] * len(dates), st, max_hold=5, cost=0.0, fut_cost=0.0)
        _, t1 = run(dates, ds, [s] * len(dates), st, max_hold=5, cost=0.5)
        for a, b in zip(t0, t1):
            assert b.pnl < a.pnl


def test_time_decay_long_straddle_loses_when_nothing_moves():
    dates, ds, _ = synthetic(vol=0.0)
    _, t = run(dates, ds, [-10.0] * len(dates), Structure("straddle", None), max_hold=5, cost=0.0, fut_cost=0.0)
    assert all(x.pnl < 0 for x in t)


def test_jump_day_is_not_skipped():
    """급등으로 행사가가 스마일 범위 밖으로 나가도 그날 손익을 반영한다 (전날 청산으로 피하지 않음)."""
    dates, ds, _ = synthetic(vol=0.0, jump_day=3, jump=0.30)
    daily, t = run(dates, ds, [10.0] * len(dates), Structure("straddle", None), max_hold=10, cost=0.0, fut_cost=0.0)
    first = t[0]
    assert first.exit >= dates[3]
    assert daily[dates[3]] < -0.10                # 숏 스트래들이 30% 점프에서 큰 손실
    assert first.fallback >= 1


def test_no_lookahead_in_signal():
    random.seed(0)
    vals = [random.gauss(0, 1) for _ in range(120)]
    z = rolling_z(vals, 40)
    changed = vals[:80] + [v + 100 for v in vals[80:]]
    z2 = rolling_z(changed, 40)
    assert z[:80] == z2[:80]


def test_next_day_execution_enters_one_day_later():
    dates, ds, _ = synthetic()
    sig = [None] * len(dates)
    sig[5] = 3.0
    _, t0 = run(dates, ds, sig, Structure("straddle", None), entry_lag=0)
    _, t1 = run(dates, ds, sig, Structure("straddle", None), entry_lag=1)
    assert t0[0].entry == dates[5] and t1[0].entry == dates[6]


def test_futures_hedge_cost_only_hits_hedged():
    """선물 헤지 비용은 델타헤지 전략에만 붙고, 단가에 비례해 손익을 줄인다."""
    dates, ds, _ = synthetic()
    st, sig = Structure("straddle", None), [-10.0] * 40
    u0 = run(dates, ds, sig, st, "none", max_hold=5, cost=0.0, fut_cost=0.0)[1]
    u1 = run(dates, ds, sig, st, "none", max_hold=5, cost=0.0, fut_cost=0.10)[1]
    assert [t.pnl for t in u0] == [t.pnl for t in u1]
    h0 = run(dates, ds, sig, st, "daily", max_hold=5, cost=0.0, fut_cost=0.0)[1]
    h1 = run(dates, ds, sig, st, "daily", max_hold=5, cost=0.0, fut_cost=0.05)[1]
    h2 = run(dates, ds, sig, st, "daily", max_hold=5, cost=0.0, fut_cost=0.10)[1]
    for a, b, c in zip(h0, h1, h2):
        assert c.pnl < b.pnl < a.pnl
        assert (a.pnl - c.pnl) == pytest.approx(2 * (a.pnl - b.pnl), rel=1e-9)


def test_max_drawdown_is_percent_of_equity():
    """자본 1에서 +44%까지 갔다가 −7.6%로 내려오면 잔고 1.44 → 0.924, MDD = −35.8%."""
    assert max_drawdown([0.10, 0.44, 0.20, -0.076, 0.0]) == pytest.approx(0.924 / 1.44 - 1)
    assert max_drawdown([0.0, -0.10, 0.05]) == pytest.approx(-0.10)
    assert max_drawdown([0.01, 0.02, 0.03]) == 0.0




def test_data_files_picks_all_periods(tmp_path):
    """기간별 파일을 모두 찾고, 같은 이름의 .csv 와 .csv.gz 는 하나로 친다."""
    from optstruct5y.data import data_files
    for n in ["kospi200_20210826_20220902_options_regular.csv.gz", "kospi200_options_regular.csv.gz",
              "kospi200_options_regular.csv", "kospi200_20210826_20220902_spot.csv.gz", "kospi200_spot.csv",
              "kospi200_futures_regular.csv", "kospi200_20210826_20220902_futures_regular.csv.gz", "notes.txt"]:
        (tmp_path / n).write_text("x")
    opt = [p.name for p in data_files(tmp_path, "options")]
    assert opt == ["kospi200_20210826_20220902_options_regular.csv.gz", "kospi200_options_regular.csv"]
    assert len(data_files(tmp_path, "spot")) == 2
    assert len(data_files(tmp_path, "futures")) == 2


def test_spot_merge_across_files(tmp_path):
    """여러 기간의 지수 파일을 날짜순으로 합친다."""
    from optstruct5y.data import load_spot
    hdr = "BAS_DD,KOSPI200_SPOT_CLOSE\n"
    (tmp_path / "kospi200_b_spot.csv").write_text(hdr + "20220105,300\n20220104,299\n", encoding="utf-8")
    (tmp_path / "kospi200_a_spot.csv").write_text(hdr + "20211230,290\n", encoding="utf-8")
    out = load_spot(sorted(tmp_path.iterdir()))
    assert [d for d, _ in out] == ["20211230", "20220104", "20220105"]
