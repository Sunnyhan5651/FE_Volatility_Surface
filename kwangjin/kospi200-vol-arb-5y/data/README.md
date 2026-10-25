# data/

KRX에서 받은 일별 원자료 CSV를 이 폴더에 넣으세요. (저장소에는 포함하지 않습니다 — `.gitignore` 참고)
이름이 `kospi200` 으로 시작하고 아래 꼬리로 끝나는 파일을 **기간별로 전부** 읽어 날짜순으로 합칩니다. `.csv` 와 `.csv.gz` 둘 다 됩니다.

| 꼬리 | 내용 |
|---|---|
| `*_options_regular.csv(.gz)` | KOSPI200 옵션 일별 시세 (정규장). 행 = 날짜 × 종목 |
| `*_futures_regular.csv(.gz)` | KOSPI200·미니 선물 일별 시세 (정규장) |
| `*_spot.csv(.gz)` | KOSPI200 지수 종가 (`BAS_DD`, `KOSPI200_SPOT_CLOSE`) |

5년 판 구성 (15개):

```
kospi200_20210826_20220902_{options_regular,futures_regular,spot}.csv.gz
kospi200_20220905_20230908_{options_regular,futures_regular,spot}.csv.gz
kospi200_20230911_20240924_{options_regular,futures_regular,spot}.csv.gz
kospi200_20240925_20251013_{options_regular,futures_regular,spot}.csv.gz
kospi200_options_regular.csv.gz, kospi200_futures_regular.csv, kospi200_spot.csv   (2025-10-14 ~ 2026-10-23)
```

옵션 파일에 필요한 컬럼: `BAS_DD, PROD_NM, RGHT_TP_NM, EXPIRY_YM, STRIKE, NAME_TAG, LAST_TRADING_DATE, TRADED_CLOSE, TDD_CLSPRC, IMP_VOLT, ACC_TRDVOL, ACC_OPNINT_QTY`
선물 파일에 필요한 컬럼: `BAS_DD, PROD_NM, EXPIRY_YM, SESSION, TRADED_CLOSE, TDD_CLSPRC, ACC_TRDVOL`

같은 이름의 `.csv` 와 `.csv.gz` 가 둘 다 있으면 `.csv` 만 씁니다. 파일 이름·크기가 바뀌면 `.cache` 의 스마일 캐시를 새로 만듭니다.
