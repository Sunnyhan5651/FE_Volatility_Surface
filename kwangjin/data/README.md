# data/

KRX에서 받은 일별 원자료 CSV를 이 폴더에 넣으세요. (저장소에는 포함하지 않습니다 — `.gitignore` 참고)

| 파일 | 내용 |
|---|---|
| `kospi200_options_regular.csv` (또는 `.csv.gz`) | KOSPI200 옵션 일별 시세 (정규장). 행 = 날짜 × 종목 |
| `kospi200_futures_regular.csv` (또는 `.csv.gz`) | KOSPI200·미니 선물 일별 시세 (정규장) |
| `kospi200_spot.csv` | KOSPI200 지수 종가 (`BAS_DD`, `KOSPI200_SPOT_CLOSE`) |

옵션 파일에 필요한 컬럼: `BAS_DD, PROD_NM, RGHT_TP_NM, EXPIRY_YM, STRIKE, NAME_TAG, LAST_TRADING_DATE, TRADED_CLOSE, TDD_CLSPRC, IMP_VOLT, ACC_TRDVOL, ACC_OPNINT_QTY`
선물 파일에 필요한 컬럼: `BAS_DD, PROD_NM, EXPIRY_YM, SESSION, TRADED_CLOSE, TDD_CLSPRC, ACC_TRDVOL`
