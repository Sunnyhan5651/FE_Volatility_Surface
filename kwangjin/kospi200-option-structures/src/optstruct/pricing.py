"""Black-76 가격·그릭스와 스마일 보간."""
from __future__ import annotations

import bisect
import math

from . import config as C


def _ncdf(x):
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def _npdf(x):
    return math.exp(-0.5 * x * x) / math.sqrt(2 * math.pi)


def bs76(F, K, T, sigma, right, r=C.R):
    """Black-76. 반환: (가격, 델타(F 기준), 베가(IV 1pt 당)). sigma 는 소수(0.30 = 30%)."""
    if T <= 0 or sigma <= 0:
        return max(0.0, (F - K) if right == "C" else (K - F)), 0.0, 0.0
    sq = math.sqrt(T)
    d1 = (math.log(F / K) + 0.5 * sigma * sigma * T) / (sigma * sq)
    d2 = d1 - sigma * sq
    disc = math.exp(-r * T)
    vega = F * disc * _npdf(d1) * sq / 100.0
    if right == "C":
        return disc * (F * _ncdf(d1) - K * _ncdf(d2)), disc * _ncdf(d1), vega
    return disc * (K * _ncdf(-d2) - F * _ncdf(-d1)), disc * (_ncdf(d1) - 1), vega


def interp(points, x, max_gap=C.MAX_STRIKE_GAP):
    """(K/F, IV) 점들 사이 선형보간. 범위 밖이거나 간격이 넓으면 None (외삽하지 않음)."""
    xs = [p[0] for p in points]
    i = bisect.bisect_left(xs, x)
    if i < len(points) and abs(xs[i] - x) < 1e-9:
        return points[i][1]
    if i > 0 and abs(xs[i - 1] - x) < 1e-9:
        return points[i - 1][1]
    if i == 0 or i == len(points):
        return None
    (x0, z0), (x1, z1) = points[i - 1], points[i]
    if x1 - x0 > max_gap:
        return None
    return z0 + (x - x0) / (x1 - x0) * (z1 - z0)


def interp_flat(points, x):
    """보유 중 평가용: 범위 밖이면 끝점 IV 그대로(플랫), 안쪽은 간격과 무관하게 선형보간."""
    if x <= points[0][0]:
        return points[0][1]
    if x >= points[-1][0]:
        return points[-1][1]
    return interp(points, x, max_gap=1e9)


def strike_for_delta(smile, right, target=C.WING_DELTA):
    """스마일 IV로 계산한 |델타| = target 인 행사가 K/F (이분법). 스마일 범위 밖이면 None."""
    F, T = smile.forward, smile.days / 365
    lo, hi = (smile.points[0][0], 1.0) if right == "P" else (1.0, smile.points[-1][0])

    def f(m):
        iv = interp(smile.points, m)
        if iv is None:
            return None
        return abs(bs76(F, m * F, T, iv / 100, right)[1]) - target

    flo, fhi = f(lo), f(hi)
    if flo is None or fhi is None or flo * fhi > 0:
        return None
    for _ in range(50):
        mid = 0.5 * (lo + hi)
        fm = f(mid)
        if fm is None:
            return None
        if (fm > 0) == (flo > 0):
            lo, flo = mid, fm
        else:
            hi = mid
    return 0.5 * (lo + hi)
