# 2번 파트: Volatility Smile·Skew & Term Structure — 코스피200 시장 사례

Hull 『Options, Futures, and Other Derivatives』 Ch.20의 **volatility skew(20.3절)** 와 **변동성 기간구조(20.5절)** 가
실제 코스피200 옵션 시장에서도 나타나는지, **평온한 날과 급락한 날을 비교**해서 확인한 자료입니다.

## 한 줄 요약
교과서 그림이 한국 시장에서도 그대로 나타나고, 위기 때는 **IV 수준이 약 3배로 뛰고 기간구조가 역전**된다.

## 비교한 두 날짜
| 구분 | 날짜 | 특징 |
|---|---|---|
| 평온 | 2025-12-24 | 1년 중 IV가 가장 낮은 구간 (근월물 ATM IV 약 21%) |
| 급락 | 2026-03-04 | 코스피200 하루 −11.9%, 근월물 ATM IV 1년 중 최고 |

## 결과

### fig3_timeseries.png — 1년 흐름 (도입)
- 위: 코스피200 지수 / 아래: 근월물 vs 3번째 월물 ATM IV
- 지수가 급락할 때마다 **단기(근월물) IV가 장기 IV를 추월**하는 역전이 반복됨 (색칠된 구간)

### fig1_skew.png — 행사가별 IV (Skew)
| K/F | 0.8 | 0.9 | 1.0 (ATM) | 1.1 |
|---|---|---|---|---|
| 평온 (2026.02물, 50일) | 35% | 28% | 24% | 25% |
| 급락 (2026.04물, 36일) | 87% | 77% | 73% | 66% |

- 평온한 날: 낮은 행사가(폭락 대비 풋)일수록 IV가 높은 **전형적인 equity skew** → 시장이 폭락 가능성을 로그정규분포보다 높게 봄 (왼쪽 꼬리가 두꺼움, crashophobia)
- 급락한 날: 곡선 전체가 약 **3배 위로 이동**, 0.9→1.1 구간 IV 차이 3%p → 10.5%p로 **절대 기준 skew가 가팔라짐** (Hull: 지수 하락 시 skew 가팔라짐과 일치)
- 오른쪽 그래프(ATM=1로 정규화)로 모양만 보면 오히려 급락한 날이 완만함 → ATM IV 자체가 폭등해 상대적 기울기는 줄어듦

### fig2_term.png — 만기별 ATM IV (기간구조)
- 평온: 21% (15일) → 26% (351일) **우상향** — 지금 변동성이 낮으니 앞으로 오를 것으로 예상
- 급락: 108% (8일) → 48% (281일) **역전(우하향)** — 지금 변동성이 극단적이니 진정될 것으로 예상
- Hull 20.5절 "단기 변동성이 낮으면 우상향, 높으면 우하향"과 일치

## 방법
1. **데이터**: 민재 폴더의 KRX 코스피200 옵션(정규)·선물·현물 일별 데이터 (2025.10.14 ~ 2026.10.23, 252거래일)
2. **IV**: KRX 공표 내재변동성(`IMP_VOLT`) 사용
3. **선물가격 F**: 같은 만기 선물 정산가(없으면 현물 지수) → 가로축을 **K/F**로 표준화 (Hull 20.4절)
4. **OTM 옵션만 사용**: K<F는 풋, K≥F는 콜 (같은 행사가·만기의 콜·풋 IV는 동일 — Hull 20.1절)
5. **필터**: 미결제약정 0 종목, IV 5% 미만·150% 초과 값 제외
6. **곡선 다듬기**: K/F 0.02 구간별 IV 중앙값
7. **월물 선택**: skew 비교는 만기 30일 이상 중 가장 가까운 월물 / ATM IV는 K/F=1 지점을 보간

## 실행 방법
`opt.pkl`, `fut.pkl`을 먼저 만든 뒤 스크립트를 실행합니다.

```python
import pandas as pd
o = pd.read_csv('kospi200_options_regular.csv', dtype={'BAS_DD':str,'EXPIRY_YM':str,'LAST_TRADING_DATE':str},
                usecols=['BAS_DD','RGHT_TP_NM','EXPIRY_YM','STRIKE','LAST_TRADING_DATE','TDD_CLSPRC',
                         'NXTDD_BAS_PRC','IMP_VOLT','ACC_TRDVOL','ACC_OPNINT_QTY','KOSPI200_SPOT_CLOSE'])
o.to_pickle('opt.pkl')
pd.read_csv('kospi200_futures_regular.csv', dtype={'BAS_DD':str,'EXPIRY_YM':str}).to_pickle('fut.pkl')
```

```bash
python part2_smile_term_structure.py
```
- 필요 라이브러리: pandas, numpy, matplotlib, scipy
- 스크립트 안의 CSV 경로(`kospi200_spot.csv`)와 한글 폰트 경로는 본인 환경에 맞게 수정

## 파일
| 파일 | 내용 |
|---|---|
| `part2_smile_term_structure.py` | 데이터 처리 + 그래프 생성 코드 |
| `fig1_skew.png` | 행사가별 IV 비교 (skew) |
| `fig2_term.png` | 만기별 ATM IV 비교 (기간구조) |
| `fig3_timeseries.png` | 1년간 지수와 ATM IV 흐름 |

## 한계
- 장중이 아닌 **일별 종가** 데이터라 노이즈가 있음 (종가로 직접 역산한 IV와 KRX 공표 IV의 중간값 차이 약 2.9%p)
- 두 날짜의 비교 월물 만기가 다름 (50일 vs 36일)
- 대표 사례 두 날짜 비교이므로 일반화에는 주의
