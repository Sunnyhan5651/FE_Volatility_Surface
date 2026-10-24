"""KRX 일별 원자료 로딩과 월물별 IV 스마일 구축.

입력 CSV (data/ 폴더, .csv 또는 .csv.gz):
  kospi200_options_regular.csv  / kospi200_futures_regular.csv / kospi200_spot.csv
"""
from __future__ import annotations

import bisect
import csv
import gzip
import math
import pickle
import statistics as st
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

from . import config as C


# --------------------------------------------------------------------- 유틸
def number(v):
    try:
        x = float((v or "").replace(",", "").strip())
    except ValueError:
        return None
    return x if math.isfinite(x) else None


def find_file(data_dir: Path, stem: str) -> Path:
    for ext in (".csv", ".csv.gz"):
        p = data_dir / f"{stem}{ext}"
        if p.exists():
            return p
    raise FileNotFoundError(f"{data_dir}/{stem}.csv")


def open_text(path: Path):
    if path.suffix == ".gz":
        return gzip.open(path, "rt", encoding="utf-8-sig", newline="")
    return path.open(encoding="utf-8-sig", newline="")


# --------------------------------------------------------------------- 선물/현물
def load_futures_by_day(path: Path) -> Dict[str, Dict[str, float]]:
    """day -> {expiry: 종가}. 정규장·거래량 필터 통과 중 거래량 최대 종목."""
    best = defaultdict(dict)
    with open_text(path) as f:
        for row in csv.DictReader(f):
            if row["SESSION"] != "정규" or row["PROD_NM"] not in {"코스피200 선물", "미니코스피200 선물"}:
                continue
            price, vol = number(row["TDD_CLSPRC"]), number(row["ACC_TRDVOL"])
            if row["TRADED_CLOSE"] != "1" or not price or price <= 0 or not vol or vol < C.MIN_FUTURES_VOLUME:
                continue
            day, expiry = row["BAS_DD"], row["EXPIRY_YM"]
            cur = best[day].get(expiry)
            if cur is None or vol > cur[0]:
                best[day][expiry] = (vol, price)
    return {d: {e: p for e, (_, p) in exps.items()} for d, exps in best.items()}


def load_spot(path: Path):
    spot = []
    with open_text(path) as f:
        for row in csv.DictReader(f):
            spot.append((row["BAS_DD"], float(row["KOSPI200_SPOT_CLOSE"])))
    spot.sort()
    return spot


def rv20_by_day(spot, window: int = 20) -> Dict[str, float]:
    """20일 종가-종가 실현변동성 (연율, %)."""
    rets = [(spot[i][0], math.log(spot[i][1] / spot[i - 1][1])) for i in range(1, len(spot))]
    out = {}
    for i in range(window - 1, len(rets)):
        w = [r for _, r in rets[i - window + 1:i + 1]]
        sd = st.pstdev(w) if len(set(w)) > 1 else 0.0
        out[rets[i][0]] = sd * math.sqrt(C.TRADING_DAYS) * 100
    return out


# --------------------------------------------------------------------- 스마일
@dataclass(frozen=True)
class Smile:
    expiry: str
    days: int          # 잔존 달력일
    forward: float     # 동일 만기 선물 종가
    points: tuple      # ((K/F, IV%), ...) 오름차순, OTM만, 거래량 가중


def interpolate_strike(points, x, max_gap=C.MAX_STRIKE_GAP) -> Optional[float]:
    """K/F = x 에서의 IV를 행사가 방향 선형 보간 (외삽 없음, 간격 초과 시 None)."""
    xs = [p[0] for p in points]
    i = bisect.bisect_left(xs, x)
    if i < len(points) and math.isclose(xs[i], x, abs_tol=1e-9, rel_tol=0):
        return points[i][1]
    if i > 0 and math.isclose(xs[i - 1], x, abs_tol=1e-9, rel_tol=0):
        return points[i - 1][1]
    if i == 0 or i == len(points):
        return None
    x0, z0 = points[i - 1]
    x1, z1 = points[i]
    if x1 - x0 > max_gap:
        return None
    return z0 + (x - x0) / (x1 - x0) * (z1 - z0)


def build_smiles_by_day(options_path: Path, forwards_by_day) -> Dict[str, Dict[str, Smile]]:
    """옵션 CSV 1회 순회로 day -> {expiry: Smile} 구축."""
    smiles_by_day: Dict[str, Dict[str, Smile]] = {}
    with open_text(options_path) as f:
        reader = csv.DictReader(f)
        current_day, buf = None, []

        def flush():
            if current_day is None or not buf:
                return
            forwards = forwards_by_day.get(current_day, {})
            if not forwards:
                return
            date = datetime.strptime(current_day, "%Y%m%d").date()
            weighted = defaultdict(lambda: [0.0, 0.0])
            expiry_days = {}
            for row in buf:
                if row["PROD_NM"] != "코스피200 옵션" or row["NAME_TAG"] != "정규":
                    continue
                expiry = row["EXPIRY_YM"]
                if expiry not in forwards:
                    continue
                strike, price, iv = number(row["STRIKE"]), number(row["TDD_CLSPRC"]), number(row["IMP_VOLT"])
                vol, oi = number(row["ACC_TRDVOL"]), number(row["ACC_OPNINT_QTY"])
                if row["TRADED_CLOSE"] != "1" or not price or price <= 0:
                    continue
                if not strike or strike <= 0 or iv is None or not C.IV_MIN <= iv <= C.IV_MAX:
                    continue
                if vol is None or vol < C.MIN_OPTION_VOLUME or oi is None or oi < C.MIN_OPEN_INTEREST:
                    continue
                try:
                    dte = (datetime.strptime(row["LAST_TRADING_DATE"], "%Y%m%d").date() - date).days
                except ValueError:
                    continue
                if not C.MIN_DTE <= dte <= C.MAX_DTE:
                    continue
                m = strike / forwards[expiry]
                if not C.MIN_MONEYNESS <= m <= C.MAX_MONEYNESS:
                    continue
                right = row["RGHT_TP_NM"].upper()
                if right not in {"CALL", "PUT"}:
                    continue
                if (right == "CALL" and m < 1) or (right == "PUT" and m > 1):
                    continue                      # OTM만 사용
                if expiry in expiry_days and expiry_days[expiry] != dte:
                    continue
                expiry_days[expiry] = dte
                s, w = weighted[(expiry, strike)]
                weighted[(expiry, strike)] = [s + iv * vol, w + vol]
            grouped = defaultdict(list)
            for (expiry, strike), (s, w) in weighted.items():
                grouped[expiry].append((strike / forwards[expiry], s / w))
            day_smiles = {}
            for expiry, points in grouped.items():
                if len(points) < 2:
                    continue
                day_smiles[expiry] = Smile(expiry, expiry_days[expiry], forwards[expiry], tuple(sorted(points)))
            if day_smiles:
                smiles_by_day[current_day] = day_smiles

        for row in reader:
            day = row["BAS_DD"]
            if day != current_day:
                flush()
                current_day, buf = day, []
            buf.append(row)
        flush()
    return smiles_by_day


# --------------------------------------------------------------------- 묶음 로더
@dataclass
class Dataset:
    smiles_by_day: Dict[str, Dict[str, Smile]]
    spot: list
    rv20: Dict[str, float]


def load_dataset(data_dir: str | Path, cache_dir: str | Path | None = None, verbose: bool = True) -> Dataset:
    data_dir = Path(data_dir)
    opt = find_file(data_dir, "kospi200_options_regular")
    fut = find_file(data_dir, "kospi200_futures_regular")
    spt = find_file(data_dir, "kospi200_spot")
    cache = None
    if cache_dir:
        Path(cache_dir).mkdir(parents=True, exist_ok=True)
        stamp = "_".join(str(int(p.stat().st_mtime)) for p in (opt, fut, spt))
        cache = Path(cache_dir) / f"smiles_{stamp}.pkl"
        if cache.exists():
            if verbose:
                print(f"[data] 캐시 사용: {cache.name}")
            with cache.open("rb") as f:
                return pickle.load(f)
    if verbose:
        print("[data] 선물·현물 로딩...")
    forwards = load_futures_by_day(fut)
    spot = load_spot(spt)
    if verbose:
        print("[data] 옵션 CSV 순회하며 일별 스마일 구축 (수 분 걸릴 수 있음)...")
    smiles = build_smiles_by_day(opt, forwards)
    ds = Dataset(smiles, spot, rv20_by_day(spot))
    if cache:
        with cache.open("wb") as f:
            pickle.dump(ds, f)
    return ds
