"""상수와 백테스트 파라미터."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

TRADING_DAYS = 252
RISK_FREE = 0.025            # 연 단리 가정 (실제 KRW 금리곡선 미사용)

# --- 데이터 필터 (IV 곡면 구축) -------------------------------------------------
MIN_OPTION_VOLUME = 10
MIN_OPEN_INTEREST = 10
MIN_FUTURES_VOLUME = 100
IV_MIN, IV_MAX = 3.0, 150.0
MIN_DTE, MAX_DTE = 5, 180
MIN_MONEYNESS, MAX_MONEYNESS = 0.85, 1.15
MAX_STRIKE_GAP = 0.06        # 보간에 쓰는 인접 행사가 간 최대 K/F 간격 (외삽 없음)

# --- VRP 포지션 사이징 ----------------------------------------------------------
MIN_ENTRY_DTE = 10           # 잔존일 10일 미만 진입 금지
DTE_TAPER_FULL = 20          # 20일 이상이면 100% 사이즈
DTE_TAPER_FLOOR = 0.2        # 10일 직상단 사이즈 배수
REF_T, REF_SIGMA, REF_F = 25 / 365, 0.45, 800.0

# --- 신호 격자 ------------------------------------------------------------------
WINDOWS = (20, 40, 60)
ENTRY_THRESHOLDS = (1.0, 1.5, 2.0)


@dataclass(frozen=True)
class Params:
    """백테스트 한 번을 규정하는 파라미터.

    entry_lag : 신호 확인(종가) 후 며칠 뒤 종가에 체결하는가 (0 = 당일 종가)
    max_hold  : 최대 보유 거래일
    stop_dz   : 신호 z가 진입 z와 같은 방향으로 이만큼 더 벌어지면 청산 (None = 사용 안 함)
    rehedge   : True면 매일 델타 재헤지, False면 진입 시 1회만 헤지
    cost_iv_pt: 레그당 체결 시 IV 포인트 비용 (매수는 +, 매도는 −로 불리하게 적용)
    """
    z_window: int = 40
    z_entry: float = 1.5
    z_exit: float = 0.3
    max_hold: int = 15
    entry_lag: int = 0
    stop_dz: Optional[float] = None
    rehedge: bool = True
    cost_iv_pt: float = 0.5
