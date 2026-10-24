# 코스피200 월물 옵션 변동성 표면

코스피200 정규 월물 옵션의 일별 내재변동성(IV)을 **머니니스 × 잔존만기** 격자에 놓고, 유동성 있는 관측값 사이를 2차원 선형 보간하여 3D 표면으로 그리는 연구입니다. X축은 동일 결제월 선물 종가를 기준으로 한 `K/F`, Y축은 옵션 최종거래일까지의 달력일수, Z축은 KRX의 `IMP_VOLT`(%)입니다.

## 파일 구성

```text
Option_data/
├── README.md
├── download_krx_kospi200_252d.py       # KRX API에서 공통 252거래일 수집
├── build_kospi200_bilinear_surface.py  # 날짜별 IV 격자 및 3D 그림 생성
└── kospi200_252d_20251014_20261023/
    ├── manifest.json                    # 거래일·건수·API 범위
    ├── kospi200_spot.csv                # 코스피200 현물 지수
    ├── kospi200_options_regular.csv     # 정규 월물 콜·풋
    ├── kospi200_options_regular.csv.gz  # 원본 옵션 CSV의 gzip 사본
    ├── kospi200_futures_regular.csv     # 정규 코스피200·미니 선물
    └── bilinear_iv_surface_results/
        ├── iv_grid_20261023.csv
        └── iv_surface_3d_20261023.png
```

현재 데이터는 **2025-10-14~2026-10-23, 실제 거래일 252개**입니다. `manifest.json`에 현물 252행, 정규 월물 옵션 930,576행, 정규 선물 3,276행과 거래일 목록이 기록되어 있습니다. 거래가 없는 옵션 행도 원본 CSV에 남아 있으며, 표면 생성 단계에서 제외합니다. `.csv.gz`는 원본 CSV를 대체하는 분석 입력이 아니라 전송·보관용 압축 사본입니다.

## 실행

프로젝트 폴더에서 실행합니다. 현재 `.venv`에는 그림 생성에 필요한 Matplotlib이 설치되어 있습니다. 다른 Python 환경에서는 `python3 -m pip install matplotlib`가 필요합니다.

```bash
cd /Users/Kang/projects/Option_data
.venv/bin/python build_kospi200_bilinear_surface.py
```

기본 날짜는 옵션 CSV의 마지막 거래일입니다. 특정 날짜를 보려면 다음과 같이 실행합니다.

```bash
.venv/bin/python build_kospi200_bilinear_surface.py --date 20251107
```

결과는 해당 데이터 폴더의 `bilinear_iv_surface_results/`에 저장됩니다. 날짜별 `iv_grid_YYYYMMDD.csv`는 격자점의 `K/F`, 잔존일수, IV, 생성 방식(`observed`, `strike_linear`, `tenor_linear`, `bilinear`, `unsupported`)을 담고, `iv_surface_3d_YYYYMMDD.png`는 Matplotlib 3D 그림입니다. 같은 날짜로 다시 실행하면 해당 날짜의 결과 두 파일을 갱신합니다.

다른 252거래일 묶음을 분석할 때는 옵션·선물 CSV를 함께 지정합니다.

```bash
.venv/bin/python build_kospi200_bilinear_surface.py \
  --options /path/to/kospi200_options_regular.csv \
  --futures /path/to/kospi200_futures_regular.csv
```

### 데이터 수집

수집기에는 KRX Open API의 **KOSPI 시리즈 일별시세정보**, **옵션 일별매매정보(주식옵션外)**, **선물 일별매매정보(주식선물外)** 승인이 필요합니다. 실행 중 인증키를 화면에 표시하지 않고 입력할 수 있으며 `KRX_AUTH_KEY` 환경변수도 지원합니다.

```bash
.venv/bin/python download_krx_kospi200_252d.py --end 20261023
```

코스피200 현물 지수가 게시된 날을 거꾸로 확인해 252거래일을 고른 뒤, 세 CSV와 `manifest.json`을 **별도 데이터 폴더**에 저장합니다. 같은 이름의 결과 폴더가 이미 있으면 덮어쓰지 않고 중단합니다. 날짜가 다른 데이터 폴더를 분석하려면 위 `--options`와 `--futures`를 지정하세요.

## 표면 구성

1. 같은 날짜의 정규 월물 옵션과 **동일 결제월** 코스피200 또는 미니 코스피200 선물을 연결합니다. 둘 다 있으면 거래량이 더 큰 선물을 사용합니다. 대응하는 유동성 있는 선물이 없으면 그 옵션 만기는 표면에 넣지 않습니다.
2. 거래 종가가 있는 OTM 풋·콜 중 옵션 거래량 **10계약 이상**, 미결제약정 **10계약 이상**, 선물 거래량 **100계약 이상**, IV **3~150%**, 잔존만기 **5~180일**, `K/F` **0.85~1.15**만 사용합니다. 같은 행사가의 콜·풋이 함께 남으면 거래량 가중 IV를 사용합니다.
3. 각 관측 만기에서 인접한 행사가의 IV를 `K/F` 방향으로 선형 보간한 뒤, 인접 만기 사이를 잔존일수 방향으로 선형 보간합니다. 격자 간격은 `K/F` **0.005**, 만기 **2일**이며 실제 관측 `K/F`와 만기일도 격자에 포함합니다.
4. 행사가 간격이 `K/F` **0.06**을 넘거나 만기 간격이 **65일**을 넘는 구간은 보간하지 않습니다. 관측 범위 밖 외삽도 하지 않으며 CSV에서 `unsupported`로 표시합니다.

주요 기준은 `--min-volume`, `--min-open-interest`, `--min-futures-volume`, `--max-strike-gap`, `--max-tenor-gap`으로 바꿀 수 있습니다. 전체 옵션은 `--include-itm`으로 포함할 수 있습니다. 모든 설정은 `--help`에서 확인할 수 있습니다.

## 해석 범위

- Bilinear 표면은 **연속인 구간별 선형 면**입니다. 스플라인처럼 모든 지점에서 기울기가 매끄럽지는 않습니다.
- IV는 KRX가 제공한 일별 값이며, 호가 중간값이나 장중 동시각 가격에서 다시 계산한 IV가 아닙니다. 거래량과 미결제약정 필터만으로 종가 잡음이 완전히 사라지지는 않습니다.
- 날짜에 따라 유효 만기와 행사가 수가 달라집니다. 예를 들어 2026-10-23에는 2026년 11월물 69개, 12월물 4개의 관측 행사가가 사용되므로, 먼 만기나 범위 밖으로 면을 확장해 해석하면 안 됩니다.
- 이 그림은 날짜별 IV 단면입니다. 날짜 간 IV 변화나 헤지 성과를 계산한 결과는 아닙니다.

