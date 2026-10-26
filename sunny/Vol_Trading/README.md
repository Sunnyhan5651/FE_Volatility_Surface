# Vol_Trading — IV 기반 변동성 트레이딩 백테스트

> FE_Volatility_Surface 팀 발표 | 담당: sunny  
> 발표 파트: 변동성·IV 정의와 도출 → **IV를 활용한 거래 전략**

---

## 개요

이 모듈은 발표 슬라이드 10–11에서 소개한 두 가지 전략을 KOSPI200 옵션 실데이터로 백테스트합니다.

| 전략 | 원리 | 신호 |
|------|------|------|
| **VRP (Short Volatility)** | 일반적으로 IV > HV → 옵션 매도로 프리미엄 수취 | VRP z-score > +threshold |
| **Long Volatility** | IV가 RV 대비 저렴 → ATM 스트래들 매수, 위기 헤지 | VRP z-score < −threshold |
| **양방향 VRP** | z 부호에 따라 롱/숏 자동 전환 | \|VRP z-score\| > threshold |

---

## 디렉터리 구조

```
Vol_Trading/
├── run_all.py               # 메인 실행 스크립트
├── requirements.txt
├── src/
│   └── voltrading/
│       ├── config.py        # 상수·파라미터
│       ├── data.py          # KRX 데이터 로딩, 스마일 구축
│       ├── pricing.py       # Black-76, Newton-Raphson IV 역산
│       ├── signals.py       # VRP 지표 계산, z-score 신호
│       ├── strategies.py    # 포지션 빌더 (VRP / Long Vol / Short Vol)
│       ├── engine.py        # 백테스트 엔진 (일별 마크, 델타 헤지)
│       ├── metrics.py       # 성과 지표 (Sharpe, MDD, Newey-West t)
│       └── plots.py         # 시각화
└── results/                 # 자동 생성 (실행 후)
    ├── 01_IV_vs_HV.png
    ├── 02_VRP_distribution.png
    ├── 03_term_structure.png
    ├── 04_VRP_양방향.png
    ├── 05_Short_Vol.png
    ├── 06_Long_Vol.png
    └── 07_strategy_comparison.png
```

---

## 실행 방법

```bash
# 의존 패키지 설치
pip install -r requirements.txt

# 기본 실행 (minjae 폴더 데이터 자동 탐색)
python run_all.py

# 데이터 경로 직접 지정
python run_all.py --data-dir ../../../minjae

# 캐시 무시하고 재계산
python run_all.py --no-cache
```

필요 데이터 파일 (`data_dir` 아래):

| 파일 | 내용 |
|------|------|
| `kospi200_options_regular.csv[.gz]` | KRX KOSPI200 옵션 일별 시세 |
| `kospi200_futures_regular.csv[.gz]` | KOSPI200 선물 일별 시세 |
| `kospi200_spot.csv` | KOSPI200 지수 종가 |

---

## 전략 상세

### 1. VRP (Volatility Risk Premium) 전략

**원리**: 일반적으로 $\text{IV} > \text{HV}$ (변동성 리스크 프리미엄 존재)

$$\text{VRP}_t = \text{ATM IV}_t - \text{HV}_{20,t}$$

- VRP z-score > 0 → IV 고평가 → **ATM 스트래들 매도** (Short Volatility)
- VRP z-score < 0 → IV 저평가 → **ATM 스트래들 매수** (Long Volatility)

**포지션 구성**:

$$\text{Short Straddle} = \text{ATM Call 매도} + \text{ATM Put 매도}$$

**수익 원천**: $\text{수익} \approx \text{수취 IV} - \text{실현 변동성}$

---

### 2. Long Volatility 전략

**원리**: IV가 상대적으로 저렴한 시점에 ATM 스트래들 매수 + 델타 헤지  
→ 순수 Vega(변동성) 익스포저만 남김

$$\text{Long Straddle} = \text{ATM Call 매수} + \text{ATM Put 매수}$$

**수익 구조**:
- Vega 수익: IV 자체가 상승 → 보유 옵션 가치 상승
- Gamma 수익: 실현변동성 > 지불한 IV → 델타 재헤지 과정에서 수익

---

### 3. 신호 생성

$$z_t = \frac{\text{VRP}_t - \mu_{t-W,t}}{\sigma_{t-W,t}}$$

- 롤링 윈도우 $W \in \{20, 40, 60\}$, 진입 임계값 $|z| \in \{1.0, 1.5, 2.0\}$
- **앙상블 평균**: 9개 셀의 일별 손익 평균 → 파라미터 과적합 방지

---

### 4. 백테스트 설계

| 설정 | 값 |
|------|-----|
| 체결 가정 | 당일 종가 / 익일 종가 (양쪽 보고) |
| 최대 보유 | 15 거래일 |
| 청산 조건 | \|z\| < 0.3 또는 만기 초과 |
| 델타 헤지 | 매일 재헤지 (선물 이용) |
| 거래비용 | 레그당 0.5 IV-pt (체결 불리 방향 적용) |
| 포지션 사이징 | Vega 정규화 (잔존일 10일 미만 진입 금지) |

---

## 주요 결과 (그림 설명)

| 파일 | 설명 |
|------|------|
| `01_IV_vs_HV.png` | ATM IV와 20일 HV 시계열 + VRP 추이 |
| `02_VRP_distribution.png` | VRP 분포 — IV > HV 구조적 프리미엄 확인 |
| `03_term_structure.png` | 변동성 기간구조 — 역전 구간 = 위기 국면 |
| `04_VRP_양방향.png` | 양방향 VRP 전략 누적 손익 (당일/익일 체결) |
| `05_Short_Vol.png` | Short Volatility 전략 누적 손익 |
| `06_Long_Vol.png` | Long Volatility 전략 누적 손익 |
| `07_strategy_comparison.png` | 3개 전략 비교 |

---

## 한계 및 주의사항

- **샘플 기간**: 분석 기간에 따라 결과가 크게 달라질 수 있음 (특히 KOSPI200 급등락 구간 포함 여부)
- **거래비용**: 실제 시장의 bid-ask spread, 슬리피지는 반영되지 않음
- **롤오버**: 만기 교체 시점의 롤비용 미반영
- **레버리지**: Vega 정규화 수량은 개념적 단위이며 실제 계좌 기준 레버리지와 다름
- **사후 선택 편향**: 앙상블 설계임에도 파라미터 범위 자체에 편향 가능성 존재

---

*참고: kwangjin의 volarb 모듈 구조를 참조하여 설계됨*  
*데이터: KRX KOSPI200 옵션·선물·현물 (minjae 폴더)*
