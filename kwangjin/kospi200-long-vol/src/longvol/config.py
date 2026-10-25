"""백테스트 전반의 가정값. 바꾸면 결과표 전체가 바뀐다."""

# 가격·비용
R = 0.025                 # 무위험금리 (연, 고정)
COST_IV_PT = 0.5          # 체결 비용: 진입·청산 각각 레그당 IV 0.5pt (매수는 비싸게, 매도는 싸게)
FUT_COST_PT = 0.05        # 델타헤지 선물 비용: 선물 1단위 거래당 지수 0.05pt (KOSPI200 선물 1틱 슬리피지)

# 롤 규칙
MIN_ENTRY_DTE = 10        # 잔존 10일 이상인 가장 가까운 만기를 산다
MIN_EXIT_DTE = 5          # 잔존 5일 미만이 된 날 종가에 팔고, 다음 날 다음 월물을 산다

# 구조
WING_KF = (0.90, 1.10)    # K/F 날개 (풋, 콜)
WING_DELTA = 0.25         # 델타 날개

# 스마일 구성 필터 (kospi200-vol-arb 와 동일)
MIN_VOLUME, MIN_OI, MIN_FUT_VOL = 10, 10, 100
IV_MIN, IV_MAX = 3.0, 150.0
MIN_DTE, MAX_DTE = 5, 180
MIN_M, MAX_M = 0.85, 1.15
MAX_STRIKE_GAP = 0.06     # 인접 행사가 K/F 간격이 이보다 넓으면 보간하지 않음
