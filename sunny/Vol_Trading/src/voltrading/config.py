"""상수와 백테스트 파라미터."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional

TRADING_DAYS = 252
RISK_FREE = 0.025          # 연 단리 (KRW 무위험금리 근사)

# ── 데이터 필터 ──────────────────────────────────────────
MIN_OPTION_VOLUME  = 10
MIN_OPEN_INTEREST  = 10
MIN_FUTURES_VOLUME = 100
IV_MIN, IV_MAX     = 3.0, 150.0
MIN_DTE, MAX_DTE   = 5, 180
MIN_MONEYNESS, MAX_MONEYNESS = 0.85, 1.15
MAX_STRIKE_GAP     = 0.06   # 보간 허용 최대 K/F 간격

# ── 실현변동성 ───────────────────────────────────────────
HV_WINDOW = 20              # 20일 실현변동성 (일별 → 연환산)

# ── 신호 격자 (앙상블용) ─────────────────────────────────
WINDOWS           = (20, 40, 60)
ENTRY_THRESHOLDS  = (1.0, 1.5, 2.0)

# ── 포지션 사이징 ────────────────────────────────────────
MIN_ENTRY_DTE     = 10      # 잔존일 10일 미만 진입 금지
DTE_TAPER_FULL    = 20      # 20일 이상이면 100% 사이즈
DTE_TAPER_FLOOR   = 0.2
REF_T, REF_SIGMA, REF_F = 25 / 365, 0.45, 800.0  # 기준 Vega 계산용


@dataclass(frozen=True)
class Params:
    """백테스트 1회를 규정하는 파라미터."""
    z_window:      int   = 40
    z_entry:       float = 1.5    # |z| >= 이 값에서 진입
    z_exit:        float = 0.3    # |z| < 이 값에서 청산
    max_hold:      int   = 15     # 최대 보유 거래일
    entry_lag:     int   = 0      # 0=당일 종가 체결, 1=익일 종가 체결
    rehedge:       bool  = True   # True=매일 델타 재헤지
    cost_iv_pt:    float = 0.5    # 레그당 체결 IV 비용 (포인트)
    stop_dz:       Optional[float] = 2.0   # z-score 손절: 진입 z 대비 이만큼 더 불리해지면 청산
    stop_loss_pct: Optional[float] = 5.0   # PnL 손절: 진입가 대비 -X% 초과 손실 시 청산
