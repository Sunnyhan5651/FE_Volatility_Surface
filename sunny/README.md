# 변동성(Volatility)과 내재변동성(IV) — 정의와 도출

> FE_Volatility_Surface 팀 발표 | 담당: sunny  
> 참고: Hull, *Options, Futures, and Other Derivatives* 11e, Chapter 20

---

## 발표 구성 개요

| 순서 | 소제목 | 핵심 메시지 |
|------|--------|-------------|
| 1 | 왜 변동성이 중요한가 | BSM의 단 하나의 비관측 파라미터 |
| 2 | 역사적 변동성(HV) 정의와 계산 | 과거 수익률 표준편차 |
| 3 | BSM 모형과 변동성의 역할 | 모든 옵션 가격은 σ의 함수 |
| 4 | 내재변동성(IV) 정의와 역산 도출 | 시장가격 → BSM 역함수 → IV |
| 5 | Put-Call Parity와 IV 일치성 | 동일 행사가/만기: IV_call = IV_put |
| 6 | 변동성 스마일과 변동성 표면 | IV가 행사가·만기에 따라 달라지는 현실 |
| 7 | 팀 연구로의 연결 | KOSPI200 skew / calendar / VRP 전략의 이론적 토대 |

---

## 1. 왜 변동성이 중요한가

- BSM 공식 `c = S₀N(d₁) - Ke^{-rT}N(d₂)` 에서 **유일한 비관측(non-observable) 파라미터**가 σ
- S₀, K, r, T는 직접 관찰되지만, 미래 변동성은 알 수 없음
- 따라서 옵션 시장의 핵심 질문: **"시장은 σ를 어떻게 가격에 반영하는가?"**

---

## 2. 역사적 변동성(Realized Volatility, RV) 정의

### 수식 정의

일별 로그수익률:

$$r_t = \ln\left(\frac{S_t}{S_{t-1}}\right)$$

N일 Rolling RV (연환산):

$$\text{RV}_t = \sqrt{\frac{252}{N} \sum_{i=1}^{N} r_{t-i}^2}$$

> **코드 연결**: `data.py`의 `load_spot()` 함수가 20일 Rolling RV를 정확히 이 방식으로 계산

### 한계
- **과거** 데이터 기반 → 미래 변동성 ≠ 과거 변동성
- 변동성이 일정하다는 BSM 가정과 충돌 (실제로는 변동성 클러스터링, 점프 존재)

---

## 3. BSM 모형에서 변동성의 역할

### Black-76 (선물 옵션 버전, 본 연구에서 사용)

$$c = e^{-rT}\left[F\,N(d_1) - K\,N(d_2)\right]$$

$$d_1 = \frac{\ln(F/K) + \frac{1}{2}\sigma^2 T}{\sigma\sqrt{T}}, \quad d_2 = d_1 - \sigma\sqrt{T}$$

- **σ가 클수록** 옵션 가격 상승 (vega > 0)
- 모형은 σ = 상수를 가정 → 모든 행사가·만기에 **동일한 σ**를 사용

### BSM의 핵심 가정 (현실과의 괴리)

| BSM 가정 | 현실 |
|---------|------|
| σ = 상수 | 변동성 클러스터링, regime 변화 |
| 가격이 연속적으로 움직임 | 갭, 점프 빈번 |
| 자산 수익률 ~ Lognormal | 두꺼운 꼬리(fat tail), 음의 skewness |

---

## 4. 내재변동성(Implied Volatility, IV) — 정의와 역산 도출

### 정의

> **IV란, 시장에서 관측된 옵션 가격을 BSM 공식에 대입했을 때 역으로 산출되는 σ값이다.**

$$c_{\text{market}} = \text{BSM}(\sigma_{\text{imp}}) \quad \Longrightarrow \quad \sigma_{\text{imp}} = \text{BSM}^{-1}(c_{\text{market}})$$

### 왜 해석적 역함수가 없는가?

BSM은 σ에 대해 **단조증가(monotone increasing)** 이지만 폐형식(closed-form) 역함수가 존재하지 않음.  
→ Newton-Raphson 수치 반복법으로 풀어야 함:

$$\sigma^{(n+1)} = \sigma^{(n)} - \frac{c_{\text{BSM}}(\sigma^{(n)}) - c_{\text{market}}}{\mathcal{V}(\sigma^{(n)})}$$

여기서 $\mathcal{V} = \partial c / \partial \sigma$ (vega).

### IV의 경제적 의미

- IV는 **시장이 현재 시점에서 기대하는 미래 변동성의 가격**
- IV > RV → 시장이 미래를 더 불확실하게 봄 (변동성 리스크 프리미엄, VRP > 0)
- IV < RV → 시장이 과거보다 미래를 낙관적으로 봄 (이번 연구 샘플 기간이 이 케이스)

---

## 5. Put-Call Parity와 IV 일치성 (Hull §20.1)

### Put-Call Parity

$$p + S_0 e^{-qT} = c + Ke^{-rT}$$

### IV 일치 증명

BSM이 put-call parity를 만족하면:

$$p_{\text{BSM}} - p_{\text{mkt}} = c_{\text{BSM}} - c_{\text{mkt}}$$

따라서 특정 σ에서 `c_BSM = c_mkt`이면 동시에 `p_BSM = p_mkt`  

$$\boxed{\sigma_{\text{imp}}^{\text{call}} = \sigma_{\text{imp}}^{\text{put}} \quad \text{(동일 K, T)}}$$

**실용적 의미**: Volatility smile/surface를 논할 때 콜/풋 구분 없이 단일 IV 곡면으로 표현 가능

---

## 6. 변동성 스마일과 변동성 표면

### 현실에서 IV가 일정하지 않은 이유

BSM의 lognormal 가정이 틀렸기 때문:

| 시장 | 실제 분포의 특징 | 결과적 IV 패턴 |
|------|----------------|----------------|
| **주식/지수** (KOSPI200 포함) | 좌측 꼬리가 두꺼움 (음의 skewness) | IV가 낮은 행사가(OTM put)일수록 높음 → **하향 skew** |
| **FX** | 양쪽 꼬리 모두 두꺼움 (높은 kurtosis) | 양끝 행사가에서 IV 높음 → **U자형 smile** |

### 주식/지수 음의 skew 원인 (Hull §20.3)

1. **레버리지 효과**: 주가 하락 → 부채비율 증가 → 변동성 증가
2. **Volatility Feedback**: 변동성 증가 → 요구수익률 증가 → 주가 추가 하락
3. **Crashophobia**: 1987년 블랙먼데이 이후 투자자들이 OTM put에 과도한 프리미엄 부여

### 변동성 표면 (Volatility Surface)

$$\sigma_{\text{imp}} = \sigma(K/S_0, \, T)$$

| K/S₀ | 1M | 3M | 6M | 1Y | 2Y |
|-------|----|----|----|----|-----|
| 0.90 | 높음 | ↓ | ↓ | ↓ | ↓ |
| 1.00 | 낮음 | — | — | — | — |
| 1.10 | 낮음 | ↑ | ↑ | ↑ | ↑ |

- 만기가 길수록 smile의 기울기(skew)는 완만해짐 → 점프·변동성 변화의 시간평균 효과
- 실무: 이 표에서 보간(interpolation)하여 임의 옵션에 적용

---

## 7. 팀 연구와의 연결

| Hull 이론 개념 | kwangjin 코드 구현 |
|--------------|-------------------|
| IV 역산 (Newton-Raphson) | `pricing.py` bs76() → IV smile 구축 |
| Volatility smile (행사가별 IV) | `data.py` smile 보간, `indicators.py` IV(90%)/IV(110%) 비율 |
| IV skew = 음의 skew 존재 | `strategies.py` Skew Builder: skew z-score로 시그널 |
| VRP = IV - RV 차이 | `indicators.py` VRP 계산, `strategies.py` VRP Builder |
| Volatility term structure | `strategies.py` Calendar Builder: 근/원월 ATM IV 차이 |
| Volatility surface (K, T) | 전체 연구의 관심 대상 — KOSPI200 월물 변동성 표면 |

> 요약: 이론적으로 IV가 행사가·만기에 따라 달라지는 이유(분포의 비대칭·두꺼운 꼬리)를  
> 통계적으로 포착해 **skew mean-reversion**에 베팅하는 것이 팀 전략의 핵심이다.

---

## 발표 시 강조 포인트

1. **IV는 "미래 변동성의 시장 가격"** — 단순한 수치가 아니라 시장의 기대와 두려움이 담긴 정보
2. **BSM은 보간 도구** — Hull §20.7: 트레이더들은 BSM을 이미 잘못됐다는 걸 알면서도 일관성 있는 인터폴레이션 도구로 사용
3. **IV smile의 형태 → 내재 확률분포** — Breeden-Litzenberger: $g(K) = e^{rT} \frac{\partial^2 c}{\partial K^2}$ 로 시장이 가정하는 리스크중립분포 추출 가능

---

*참고문헌: Hull (2022), Chapter 20; Breeden & Litzenberger (1978)*
