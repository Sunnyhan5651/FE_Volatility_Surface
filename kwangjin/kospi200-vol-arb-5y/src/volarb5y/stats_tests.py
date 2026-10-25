"""스큐 평균회귀 통계검증.

가설  H0: b = 0   vs   H1: b < 0 (평균회귀)
모형  Δskew(t→t+h) = a + b · z_t + e        (같은 근월물 안에서 이어진 쌍만 사용)
사전 지정(primary) 사양: W=40, h=10, 동일 만기 쌍. 나머지는 견고성 확인용.

추론: Newey-West HAC 표준오차(lag=h), 원형 이동(circular-shift) 순열검정, 비중첩 부분표본.
"""
from __future__ import annotations

from typing import List

import numpy as np
import pandas as pd
from scipy import stats

from .indicators import rolling_z

PRIMARY = dict(W=40, h=10, same_expiry=True)


def _arrays(rows):
    skew = np.array([np.nan if r["skew"] is None else r["skew"] for r in rows])
    expiry = np.array([r["near_expiry"] for r in rows])
    dte = np.array([r["near_dte"] for r in rows], float)
    return skew, expiry, dte


def _z_array(rows, W):
    return np.array([np.nan if v is None else v for v in rolling_z(rows, "skew", W)])


def ols_nw(X, y, lag):
    """OLS + Newey-West 공분산. (계수, 표준오차, R²)"""
    m = len(y)
    beta = np.linalg.lstsq(X, y, rcond=None)[0]
    e = y - X @ beta
    xtxi = np.linalg.inv(X.T @ X)
    S = (X * e[:, None]).T @ (X * e[:, None])
    for l in range(1, lag + 1):
        w = 1 - l / (lag + 1)
        G = (X[l:] * e[l:, None]).T @ (X[:-l] * e[:-l, None])
        S += w * (G + G.T)
    V = xtxi @ S @ xtxi * m / (m - X.shape[1])
    r2 = 1 - (e @ e) / (((y - y.mean()) ** 2).sum())
    return beta, np.sqrt(np.diag(V)), r2


def mean_reversion_table(rows, windows=(20, 40, 60), horizons=(5, 10, 15), n_perm=2000, seed=0) -> pd.DataFrame:
    skew, expiry, _ = _arrays(rows)
    n = len(rows)
    rng = np.random.default_rng(seed)

    def pairs(z, h, same):
        idx = [i for i in range(n - h) if not np.isnan(z[i]) and not np.isnan(skew[i]) and not np.isnan(skew[i + h])
               and (not same or expiry[i] == expiry[i + h])]
        return np.array(idx)

    def b_of(z, h, same):
        idx = pairs(z, h, same)
        if len(idx) < 12:
            return None
        return np.polyfit(z[idx], skew[idx + h] - skew[idx], 1)[0]

    out = []
    for W in windows:
        z = _z_array(rows, W)
        for h in horizons:
            for same in (True, False):
                idx = pairs(z, h, same)
                if len(idx) < 12:
                    continue
                x, y = z[idx], skew[idx + h] - skew[idx]
                beta, se, r2 = ols_nw(np.column_stack([np.ones_like(x), x]), y, h)
                t = beta[1] / se[1]
                p_nw = stats.t.cdf(t, df=len(idx) - 2)
                obs, cnt, K = b_of(z, h, same), 0, 0
                for k in rng.integers(h + 5, n - h - 5, size=n_perm):
                    bb = b_of(np.roll(z, int(k)), h, same)
                    if bb is None:
                        continue
                    K += 1
                    cnt += bb <= obs
                sub = idx[::h]
                if len(sub) >= 8:
                    bs, _, _, ps, _ = stats.linregress(z[sub], skew[sub + h] - skew[sub])
                    p_sub = ps / 2 if bs < 0 else 1 - ps / 2
                else:
                    bs, p_sub = np.nan, np.nan
                dm = lambda ii: float(np.mean(skew[ii + h] - skew[ii])) if len(ii) else float("nan")
                hi, lo = idx[z[idx] > 1.0], idx[z[idx] < -1.0]
                out.append(dict(W=W, h=h, same_expiry=same, n_pairs=len(idx), n_nonoverlap=len(sub),
                                b=beta[1], nw_t=t, p_nw=p_nw, p_perm=(cnt + 1) / (K + 1),
                                b_nonoverlap=bs, p_nonoverlap=p_sub, r2=r2,
                                dskew_z_gt1=dm(hi), n_hi=len(hi), dskew_z_lt_m1=dm(lo), n_lo=len(lo),
                                dskew_mid=dm(idx[np.abs(z[idx]) <= 1.0]),
                                primary=(W == PRIMARY["W"] and h == PRIMARY["h"] and same == PRIMARY["same_expiry"])))
    return pd.DataFrame(out)


def robustness_table(rows) -> pd.DataFrame:
    """체결 지연(진입을 1~2일 미룸)과 잔존일 통제를 넣어도 평균회귀가 남는가."""
    skew, expiry, dte = _arrays(rows)
    n = len(rows)
    out = []
    for label, skip, ctrl in [("baseline", 0, False), ("skip 1 day", 1, False), ("skip 2 days", 2, False),
                              ("control DTE", 0, True), ("skip 1 + control DTE", 1, True)]:
        for W in (20, 40, 60):
            z = _z_array(rows, W)
            for h in (5, 10):
                idx = np.array([i for i in range(skip, n - h) if not np.isnan(z[i - skip]) and not np.isnan(skew[i])
                                and not np.isnan(skew[i + h]) and expiry[i] == expiry[i + h]])
                y, x = skew[idx + h] - skew[idx], z[idx - skip]
                cols = [np.ones(len(idx)), x] + ([dte[idx]] if ctrl else [])
                X = np.column_stack(cols)
                beta, se, _ = ols_nw(X, y, h)
                t = beta[1] / se[1]
                out.append(dict(spec=label, W=W, h=h, n=len(idx), b=beta[1], nw_t=t,
                                p_one_sided=stats.t.cdf(t, df=len(idx) - X.shape[1])))
    return pd.DataFrame(out)


def noise_diagnostics(rows) -> dict:
    """스큐의 만기 편향·일별 변화 자기상관(음수면 하루짜리 반등 = 노이즈 성분)."""
    skew, expiry, dte = _arrays(rows)
    v = ~np.isnan(skew)
    d = np.diff(skew)
    ok = (~np.isnan(d[:-1]) & ~np.isnan(d[1:]) & (expiry[1:-1] == expiry[2:]) & (expiry[:-2] == expiry[1:-1]))
    tenor = []
    for lo, hi in [(5, 10), (10, 15), (15, 20), (20, 30), (30, 60)]:
        m = v & (dte >= lo) & (dte < hi)
        if m.sum():
            tenor.append(dict(dte_bucket=f"{lo}-{hi}", mean_skew=float(skew[m].mean()), n=int(m.sum())))
    return dict(corr_skew_dte=float(np.corrcoef(skew[v], dte[v])[0, 1]),
                ac1_daily_change=float(np.corrcoef(d[:-1][ok], d[1:][ok])[0, 1]), ac1_n=int(ok.sum()),
                tenor_table=pd.DataFrame(tenor))


def scatter_data(rows, W=40, h=10):
    """산점도용: 같은 만기 쌍의 (z_t, Δskew) 와 OLS 직선."""
    skew, expiry, _ = _arrays(rows)
    z = _z_array(rows, W)
    n = len(rows)
    idx = np.array([i for i in range(n - h) if not np.isnan(z[i]) and not np.isnan(skew[i])
                    and not np.isnan(skew[i + h]) and expiry[i] == expiry[i + h]])
    x, y = z[idx], skew[idx + h] - skew[idx]
    b, a = np.polyfit(x, y, 1)
    return x, y, a, b
