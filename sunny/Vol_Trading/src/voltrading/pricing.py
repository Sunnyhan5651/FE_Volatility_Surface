"""Black-76 가격·델타·베가 (선물 기초자산 옵션)."""
from __future__ import annotations
import math
from .config import REF_F, REF_SIGMA, REF_T, RISK_FREE


def norm_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def norm_pdf(x: float) -> float:
    return math.exp(-0.5 * x * x) / math.sqrt(2.0 * math.pi)


def bs76(F: float, K: float, T: float, sigma: float, r: float, right: str):
    """(가격, 델타, 베가) 반환.
    sigma: 소수 형태 (0.30 = 30%)
    베가:  IV 1포인트(%) 변화당 가격 변화
    """
    if T <= 0 or sigma <= 0:
        intrinsic = max(0.0, (F - K) if right == "C" else (K - F))
        delta = (1.0 if F > K else 0.0) if right == "C" else (-1.0 if F < K else 0.0)
        return intrinsic, delta, 0.0
    sqT = math.sqrt(T)
    d1  = (math.log(F / K) + 0.5 * sigma * sigma * T) / (sigma * sqT)
    d2  = d1 - sigma * sqT
    disc = math.exp(-r * T)
    vega = F * disc * norm_pdf(d1) * sqT / 100.0   # IV 1%p당
    if right == "C":
        price = disc * (F * norm_cdf(d1) - K * norm_cdf(d2))
        delta = disc * norm_cdf(d1)
    else:
        price = disc * (K * norm_cdf(-d2) - F * norm_cdf(-d1))
        delta = disc * (norm_cdf(d1) - 1.0)
    return price, delta, vega


# ATM 스트래들(콜+풋) 기준 정규화 단위 Vega
TARGET_VEGA_UNIT = 2.0 * bs76(REF_F, REF_F, REF_T, REF_SIGMA, RISK_FREE, "C")[2]


def implied_vol_newton(market_price: float, F: float, K: float, T: float,
                       r: float, right: str, tol: float = 1e-7, max_iter: int = 50):
    """Newton-Raphson으로 IV 역산. 수렴 실패 시 None."""
    if T <= 0 or market_price <= 0:
        return None
    sigma = 0.3  # 초기 추정치
    for _ in range(max_iter):
        price, _, vega = bs76(F, K, T, sigma, r, right)
        if vega <= 0:
            return None
        diff = price - market_price
        sigma -= diff / (vega * 100)   # vega는 1%당이므로 100 곱
        if sigma <= 0:
            sigma = 1e-6
        if abs(diff) < tol:
            return sigma * 100.0  # %로 반환
    return None
