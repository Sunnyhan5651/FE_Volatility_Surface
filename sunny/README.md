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

변동성(Volatility, σ)은 자산 수익률의 불확실성 크기를 나타내는 척도이다.

- 좁은 의미: 자산 로그수익률의 **표준편차** (연환산)
- 넓은 의미: 시장 참여자들이 미래의 가격 불확실성에 부여하는 **가격(price)**

옵션 가격결정에서 변동성이 핵심인 이유는 단순하다.  
BSM 공식에서 **직접 관측 불가능한 파라미터가 σ 하나뿐**이기 때문이다.

| 파라미터 | 관측 가능 여부 |
|---------|--------------|
| S₀ (현재 자산가격) | ✅ 직접 관측 |
| K (행사가) | ✅ 계약 조건 |
| r (무위험이자율) | ✅ 시장 금리 |
| T (잔존만기) | ✅ 계약 조건 |
| **σ (변동성)** | ❌ **관측 불가 — 추정해야 함** |

---

## 2. 역사적 변동성(Historical Volatility, HV)

### 정의

과거 가격 데이터로부터 수익률의 표준편차를 구하는 방법이다.

**Step 1.** 일별 로그수익률 계산:

$$r_t = \ln\left(\frac{S_t}{S_{t-1}}\right)$$

**Step 2.** N일 Rolling 분산 → 연환산 표준편차:

$$\text{HV}_t = \sqrt{\frac{252}{N-1} \sum_{i=1}^{N} (r_{t-i} - \bar{r})^2}$$

실무에서는 평균 수익률을 0으로 근사해 단순화하는 경우가 많다:

$$\text{RV}_t \approx \sqrt{\frac{252}{N} \sum_{i=1}^{N} r_{t-i}^2}$$

### 한계

- **후행(lagging) 지표** — 과거 기반이므로 미래 변동성과 다를 수 있음
- BSM의 상수 변동성 가정과 충돌: 실제 시장에서 변동성은 시간에 따라 변하고 클러스터링된다

---

## 3. BSM 모형과 변동성의 역할

### Black-Scholes-Merton 공식 (주식 옵션)

$$c = S_0 N(d_1) - Ke^{-rT} N(d_2)$$

$$d_1 = \frac{\ln(S_0/K) + (r + \sigma^2/2)T}{\sigma\sqrt{T}}, \quad d_2 = d_1 - \sigma\sqrt{T}$$

### Black-76 공식 (선물 옵션 — 본 팀 연구에서 사용)

$$c = e^{-rT}\left[F\,N(d_1) - K\,N(d_2)\right]$$

$$d_1 = \frac{\ln(F/K) + \frac{1}{2}\sigma^2 T}{\sigma\sqrt{T}}$$

### σ의 역할

- σ가 클수록 옵션 가격 상승 → **Vega(ν) = ∂c/∂σ > 0** 항상 성립
- 따라서 옵션 가격과 σ 사이에 **단조증가(monotone) 관계** 가 성립함
- 이 성질이 IV 역산의 근거가 된다

### BSM의 핵심 가정과 현실의 괴리

| BSM 가정 | 현실 |
|---------|------|
| σ = 상수 | 변동성 클러스터링, 레짐 변화 |
| 가격 변화가 연속적 | 갭·점프 빈번 |
| 수익률 ~ 정규분포 | 두꺼운 꼬리, 음의 비대칭 |

이 괴리 때문에 실무 트레이더는 **행사가·만기마다 다른 σ**를 사용한다. → 이것이 바로 IV다.

---

## 4. 내재변동성(Implied Volatility, IV) — 정의와 역산 도출

### 정의

> **IV란, 시장에서 관측된 옵션 가격(c_market)을 BSM 공식에 역대입했을 때 산출되는 σ값이다.**

$$c_{\text{market}} = \text{BSM}(\sigma_{\text{imp}}) \quad \Longrightarrow \quad \sigma_{\text{imp}} = \text{BSM}^{-1}(c_{\text{market}})$$

### 왜 해석적(closed-form) 역함수가 없는가

BSM 공식의 N(d₁), N(d₂)는 정규분포 CDF를 포함하고 있어, σ에 대한 **폐형식 역함수가 존재하지 않는다.**

### Newton-Raphson 수치 역산 (실무 표준)

단조증가 함수의 역함수를 수치적으로 구한다:

$$\sigma^{(n+1)} = \sigma^{(n)} - \frac{c_{\text{BSM}}(\sigma^{(n)}) - c_{\text{market}}}{\mathcal{V}(\sigma^{(n)})}$$

여기서 $\mathcal{V} = \partial c / \partial \sigma$ (Vega).

**수렴 조건**: Vega > 0 (단조증가)이므로 해가 반드시 존재하고 수렴이 빠르다. (보통 5회 이내)

### IV의 경제적 의미

| 관계 | 해석 |
|------|------|
| **IV > RV** | 시장이 미래를 더 불확실하게 봄 → 변동성 리스크 프리미엄(VRP) > 0 |
| **IV < RV** | 시장이 실제보다 낙관적 → VRP < 0 (이번 연구 샘플 기간이 이 케이스) |
| **IV 자체** | 특정 행사가·만기에 대한 시장의 불확실성 가격 |

---

## 5. Put-Call Parity와 IV 일치성 (Hull §20.1)

### Put-Call Parity (무배당 기준)

$$p + S_0 e^{-qT} = c + Ke^{-rT}$$

이 관계는 lognormal 가정 없이 **무차익거래 논리만으로** 성립한다.

### IV 일치 증명

BSM도 put-call parity를 만족하므로:

$$p_{\text{BSM}} + S_0 e^{-qT} = c_{\text{BSM}} + Ke^{-rT}$$

시장도 put-call parity를 만족하므로:

$$p_{\text{mkt}} + S_0 e^{-qT} = c_{\text{mkt}} + Ke^{-rT}$$

두 식을 빼면:

$$p_{\text{BSM}} - p_{\text{mkt}} = c_{\text{BSM}} - c_{\text{mkt}}$$

따라서 어떤 σ에서 `c_BSM = c_mkt` (즉, call의 IV) 이면 자동으로 `p_BSM = p_mkt` (즉, put의 IV가 같음):

$$\boxed{\sigma_{\text{imp}}^{\text{call}} = \sigma_{\text{imp}}^{\text{put}} \quad \text{(동일 K, T에서 항상 성립)}}$$

### 실용적 의미

- 콜과 풋을 구분하지 않고 **단일 IV 곡면**으로 시장을 묘사할 수 있다
- Volatility smile/surface는 콜·풋 중 어느 것으로 계산해도 동일한 결과를 줌
- 만약 실제 시장에서 `IV_call ≠ IV_put` 이라면 → **무차익거래 기회** 존재

---

*참고문헌: Hull (2022), Chapter 20 §20.1; Breeden & Litzenberger (1978)*
