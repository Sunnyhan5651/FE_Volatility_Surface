# 1. 변동성(Volatility)과 내재변동성(IV) — 정의와 도출

> FE_Volatility_Surface 팀 발표 | 담당: sunny  
> 참고: Hull, *Options, Futures, and Other Derivatives* 11e, Chapter 20

---

## 목차

1. 변동성이란 무엇인가
2. 역사적 변동성(Historical Volatility) 정의와 계산
3. BSM 모형과 변동성의 역할
4. 내재변동성(Implied Volatility) 정의와 역산 도출
5. Put-Call Parity와 IV 일치성 증명

---

## 1. 변동성이란 무엇인가

변동성 $\sigma$는 자산 로그수익률의 **표준편차** (연환산)다.

옵션 가격은 다섯 개의 파라미터로 결정된다:

$$c = f(S_0,\ K,\ r,\ T,\ \sigma)$$

| 파라미터 | 의미 | 관측 가능? |
|---------|------|-----------|
| $S_0$ | 현재 자산가격 | ✅ 직접 관측 |
| $K$ | 행사가 | ✅ 계약 조건 |
| $r$ | 무위험이자율 | ✅ 시장 금리 |
| $T$ | 잔존만기 | ✅ 계약 조건 |
| $\sigma$ | **변동성** | ❌ **추정 필요** |

나머지 넷은 직접 관찰되지만 $\sigma$만 미래이므로 추정해야 한다.

---

## 2. 역사적 변동성(Historical Volatility, HV)

### 계산 방법

**Step 1.** 일별 로그수익률:

$$r_t = \ln\left(\frac{S_t}{S_{t-1}}\right)$$

로그수익률을 쓰는 이유: 복리 구조를 반영하고 정규분포에 더 가깝기 때문.

**Step 2.** 표준편차 → 연환산:

$$\text{HV} = \text{std}(r_t) \times \sqrt{252}$$

(일별 → 연간, 거래일 252일 기준)

### 한계 — IV가 필요한 이유

- **후행(lagging) 지표** — 과거 기반이므로 미래 변동성을 보장하지 않음
- 실제 변동성은 시간에 따라 변함 (클러스터링, 점프) → BSM의 $\sigma = \text{상수}$ 가정 위반
- → 시장 옵션 가격에서 미래 $\sigma$를 역으로 읽어내는 방법이 필요

---

## 3. BSM 모형과 변동성의 역할

### BSM 공식

$$c = S_0\, N(d_1) - K e^{-rT} N(d_2)$$

$$d_1 = \frac{\ln(S_0/K) + \left(r + \dfrac{\sigma^2}{2}\right)T}{\sigma\sqrt{T}}, \qquad d_2 = d_1 - \sigma\sqrt{T}$$

- 분모의 $\sigma\sqrt{T}$ = 만기까지의 누적 불확실성 크기
- $\sigma$ 클수록 $d_1,\ d_2$ 변화 → $N(d_1),\ N(d_2)$ 변화 → 옵션 가격 변화

### IV 역산의 수학적 근거

$$\text{Vega} = \frac{\partial c}{\partial \sigma} > 0 \quad \text{(항상 성립)}$$

$c$는 $\sigma$의 **단조증가 함수** → 역함수 존재 보장

### BSM 가정 vs 현실

BSM은 $\sigma = \text{상수}$를 가정하지만 실제 시장에서는:

- 변동성이 시간에 따라 변함 (클러스터링, 레짐 변화)
- 가격이 연속적으로 움직이지 않음 (점프, 갭)
- 수익률 분포가 정규분포와 다름 (두꺼운 꼬리, 비대칭)

→ 트레이더들은 BSM을 쓰면서도 옵션마다 다른 $\sigma$를 넣는다. 그 $\sigma$가 IV다.

> 행사가·만기별로 IV가 달라지는 패턴 → Volatility Smile/Skew → **2번 발표자**

---

## 4. 내재변동성(Implied Volatility, IV)

### 정의

시장에서 관측된 옵션 가격을 BSM에 대입해 역으로 구한 $\sigma$:

$$c_{\text{market}} = \text{BSM}(\sigma_{\text{imp}}) \quad \Longrightarrow \quad \sigma_{\text{imp}} = \text{BSM}^{-1}(c_{\text{market}})$$

### 왜 수치 풀이가 필요한가?

$N(d_1),\ N(d_2)$는 정규분포 CDF → $\sigma$에 대한 **폐형식(closed-form) 역함수 없음**  
→ Newton-Raphson 반복법으로 수치 풀이

### Newton-Raphson 역산 (실무 표준)

$$\sigma^{(n+1)} = \sigma^{(n)} - \frac{c_{\text{BSM}}(\sigma^{(n)}) - c_{\text{market}}}{\text{Vega}(\sigma^{(n)})}$$

Vega $> 0$ → 단조증가 → 해가 반드시 존재, 보통 **5회 이내 수렴**

### IV의 의미

- **HV**: 실제로 얼마나 움직였는가 → 사후(ex-post)
- **IV**: 앞으로 얼마나 움직일 것인가 → 시장 기대(ex-ante)

일반적으로 $\text{IV} > \text{HV}$ (변동성 리스크 프리미엄, VRP)  
— 옵션 매도자가 감마 위험을 부담하는 대가로 프리미엄을 받기 때문

같은 자산이라도 행사가·만기별로 IV가 다르게 형성된다.  
→ 이 패턴을 시각화한 것이 Volatility Smile / Surface **(다음 발표자)**

---

## 5. Put-Call Parity와 IV 일치성 (Hull §20.1)

### Put-Call Parity

$$p + S_0 e^{-qT} = c + K e^{-rT}$$

Lognormal 가정 없이 **무차익거래 논리만으로** 성립.

### IV 일치 증명

BSM도 parity를 만족하므로 두 식을 빼면:

$$p_{\text{BSM}} - p_{\text{mkt}} = c_{\text{BSM}} - c_{\text{mkt}}$$

어떤 $\sigma$에서 $c_{\text{BSM}} = c_{\text{mkt}}$ 이면 → 자동으로 $p_{\text{BSM}} = p_{\text{mkt}}$

$$\boxed{\sigma_{\text{imp}}^{\text{call}} = \sigma_{\text{imp}}^{\text{put}} \qquad \text{(동일 } K,\ T \text{에서 항상 성립)}}$$

### 의미

- IV는 콜/풋 구분 없이 $(K,\ T)$ 쌍에 하나만 존재 → 단일 IV 곡면으로 표현 가능
- $\sigma_{\text{imp}}^{\text{call}} \neq \sigma_{\text{imp}}^{\text{put}}$ 이면 → 무차익거래 기회 존재

---

## 핵심 요약

| # | 내용 |
|---|------|
| 1 | $\sigma$ = 로그수익률 표준편차 (연환산) — BSM의 유일한 비관측 파라미터 |
| 2 | HV는 과거 기반, IV는 시장 기대 기반. 일반적으로 $\text{IV} > \text{HV}$ (VRP) |
| 3 | IV = 시장 가격을 BSM에 역대입한 $\sigma$ — Newton-Raphson으로 수치 풀이 |
| 4 | PCP → 동일 $K,\ T$에서 $\sigma_{\text{imp}}^{\text{call}} = \sigma_{\text{imp}}^{\text{put}}$ → 단일 IV 곡면 |

---

*참고문헌: Hull (2022), Ch.20 §20.1; Breeden & Litzenberger (1978)*
