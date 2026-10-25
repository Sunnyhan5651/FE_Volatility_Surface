"""핵심 로직 단위 테스트 (원자료 불필요, 합성 데이터 사용).  실행: pytest -q"""
import math
import random
import sys
from datetime import date, timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from longvol5y import config as C  # noqa: E402
from longvol5y.data import Dataset, Smile  # noqa: E402
from longvol5y.engine import run  # noqa: E402
from longvol5y.metrics import max_drawdown  # noqa: E402
from longvol5y.pricing import bs76, strike_for_delta  # noqa: E402
from longvol5y.structures import Structure, build  # noqa: E402

GRID = tuple(round(0.85 + 0.025 * i, 3) for i in range(13))     # K/F 0.85 ~ 1.15


def flat_smile(F, days, iv=40.0, expiry="209912"):
    return Smile(expiry, days, F, tuple((m, iv) for m in GRID))


def synthetic(n=60, F0=500.0, vol=0.30, seed=1, jump_day=None, jump=0.0, iv=40.0):
    """만기 2개(잔존 40일·70일에서 시작)에 플랫 스마일, 선물은 랜덤워크. jump_day 에 큰 점프."""
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
        day = {}
        for e, start in (("209901", 40), ("209902", 70)):
            days = start - (d - d0).days
            if days >= C.MIN_DTE:
                day[e] = flat_smile(F, days, iv, e)
        smiles[ds] = day
        fwd[ds] = {"209901": F, "209902": F}
    return dates, Dataset(smiles=smiles, fwd=fwd, spot=[])


ALL = [Structure("straddle", None), Structure("strangle", "kf"), Structure("strangle", "d25"),
       Structure("strap", None), Structure("strip", None)]


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


def test_vega_normalised_to_atm_straddle():
    sm = flat_smile(500.0, 30)
    T = 30 / 365
    target = 2 * bs76(500, 500, T, 0.40, "C")[2]
    for st in ALL:
        legs, _, _ = build(st, {"x": sm})
        assert all(l["qty"] > 0 for l in legs)                  # 모두 매수
        vega = sum(l["qty"] * bs76(500, l["K"], T, 0.40, l["right"])[2] for l in legs)
        assert vega == pytest.approx(target, rel=1e-9), st


def test_always_invested_and_rolls_before_expiry():
    """판 다음 날 바로 다시 산다 (계속 보유), 그리고 잔존 5일 미만이 되면 판다."""
    dates, ds = synthetic()
    _, t = run(dates, ds, Structure("straddle", None))
    assert len(t) >= 2
    for a, b in zip(t, t[1:]):
        assert dates.index(b.entry) == dates.index(a.exit) + 1
    assert t[0].reason == "expiry"


def test_strap_plus_strip_equals_two_straddles():
    """베가를 맞추면 스트랩 + 스트립 = 스트래들 2개 (방향 노출이 정확히 상쇄)."""
    dates, ds = synthetic()
    get = lambda s: run(dates, ds, Structure(s, None), cost=0.0, fut_cost=0.0)[1]   # noqa: E731
    for a, b, c in zip(get("strap"), get("strip"), get("straddle")):
        assert a.pnl + b.pnl == pytest.approx(2 * c.pnl, abs=1e-12)


@pytest.mark.parametrize("st", ALL)
def test_cost_always_hurts(st):
    dates, ds = synthetic()
    _, t0 = run(dates, ds, st, cost=0.0, fut_cost=0.0)
    _, t1 = run(dates, ds, st, cost=0.5)
    assert len(t0) == len(t1)
    for a, b in zip(t0, t1):
        assert b.pnl < a.pnl


@pytest.mark.parametrize("hedge", ["none", "daily"])
def test_time_decay_when_nothing_moves(hedge):
    dates, ds = synthetic(vol=0.0)
    _, t = run(dates, ds, Structure("straddle", None), hedge, cost=0.0, fut_cost=0.0)
    assert all(x.pnl < 0 for x in t)


def test_jump_day_is_not_skipped():
    """급등으로 행사가가 스마일 범위 밖으로 나가도 그날 손익을 반영한다 (전날 청산으로 피하지 않음)."""
    dates, ds = synthetic(vol=0.0, jump_day=3, jump=0.30)
    daily, t = run(dates, ds, Structure("straddle", None), cost=0.0, fut_cost=0.0)
    assert daily[dates[3]] > 0.10                 # 스트래들 매수는 30% 점프에서 큰 이익
    assert t[0].fallback >= 1


def test_delta_hedge_removes_direction():
    """조용한 장에서 한 번 크게 뛰면, 무헤지는 방향만큼 벌지만 델타헤지는 그 점프의 감마 몫만 번다."""
    dates, ds = synthetic(vol=0.0, jump_day=3, jump=0.05)
    du, _ = run(dates, ds, Structure("strap", None), "none", cost=0.0, fut_cost=0.0)
    dh, _ = run(dates, ds, Structure("strap", None), "daily", cost=0.0, fut_cost=0.0)
    assert du[dates[3]] > dh[dates[3]] > 0


def test_futures_hedge_cost_only_hits_hedged():
    """선물 헤지 비용은 델타헤지 전략에만 붙고, 단가에 비례해 손익을 줄인다."""
    dates, ds = synthetic()
    st = Structure("straddle", None)
    u0 = run(dates, ds, st, "none", cost=0.0, fut_cost=0.0)[1]
    u1 = run(dates, ds, st, "none", cost=0.0, fut_cost=0.10)[1]
    assert [t.pnl for t in u0] == [t.pnl for t in u1]
    h0 = run(dates, ds, st, "daily", cost=0.0, fut_cost=0.0)[1]
    h1 = run(dates, ds, st, "daily", cost=0.0, fut_cost=0.05)[1]
    h2 = run(dates, ds, st, "daily", cost=0.0, fut_cost=0.10)[1]
    for a, b, c in zip(h0, h1, h2):
        assert c.pnl < b.pnl < a.pnl
        assert (a.pnl - c.pnl) == pytest.approx(2 * (a.pnl - b.pnl), rel=1e-9)


@pytest.mark.parametrize("wing", ["kf", "d25"])
def test_short_call_butterfly_payoff(wing):
    """콜 버터플라이 매도: 만기 손익이 양쪽 꼬리에서 0, 몸통에서 최소(음수) — 롱 버터플라이의 정반대."""
    legs, F, _ = build(Structure("butterfly", wing), {"x": flat_smile(500.0, 30)})
    payoff = lambda S: sum(l["qty"] * max(0.0, S - l["K"]) for l in legs)   # noqa: E731
    assert payoff(0.5 * F) == pytest.approx(0, abs=1e-9)
    assert payoff(2.0 * F) == pytest.approx(0, abs=1e-9)
    assert payoff(F) < 0
    assert sum(l["qty"] for l in legs if l["K"] == F) == pytest.approx(2)
    assert all(l["qty"] < 0 for l in legs if l["K"] != F)


def test_short_butterfly_is_long_vol():
    """나비 매도는 변동성 매수: 큰 점프에서 벌고, 아무 일 없으면 잃는다."""
    st = Structure("butterfly", "kf")
    dates, ds = synthetic(vol=0.0, jump_day=3, jump=0.08)
    daily, _ = run(dates, ds, st, cost=0.0, fut_cost=0.0)
    assert daily[dates[3]] > 0
    dates, ds = synthetic(vol=0.0)
    _, t = run(dates, ds, st, cost=0.0, fut_cost=0.0)
    assert all(x.pnl < 0 for x in t)


def test_max_drawdown_is_percent_of_equity():
    """자본 1에서 +44%까지 갔다가 −7.6%로 내려오면 잔고 1.44 → 0.924, MDD = −35.8%."""
    assert max_drawdown([0.10, 0.44, 0.20, -0.076, 0.0]) == pytest.approx(0.924 / 1.44 - 1)
    assert max_drawdown([0.0, -0.10, 0.05]) == pytest.approx(-0.10)
    assert max_drawdown([0.01, 0.02, 0.03]) == 0.0


def test_data_files_picks_all_periods(tmp_path):
    """기간별 파일을 모두 찾고, 같은 이름의 .csv 와 .csv.gz 는 하나로 친다."""
    from longvol5y.data import data_files
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
    from longvol5y.data import load_spot
    hdr = "BAS_DD,KOSPI200_SPOT_CLOSE\n"
    (tmp_path / "kospi200_b_spot.csv").write_text(hdr + "20220105,300\n20220104,299\n", encoding="utf-8")
    (tmp_path / "kospi200_a_spot.csv").write_text(hdr + "20211230,290\n", encoding="utf-8")
    out = load_spot(sorted(tmp_path.iterdir()))
    assert [d for d, _ in out] == ["20211230", "20220104", "20220105"]
