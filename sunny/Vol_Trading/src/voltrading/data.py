"""KRX 일별 원자료 로딩 및 일별 IV 스마일 구축.

필요 파일 (data_dir 아래):
  kospi200_options_regular.csv  (또는 .csv.gz)
  kospi200_futures_regular.csv  (또는 .csv.gz)
  kospi200_spot.csv
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


# ── 유틸 ─────────────────────────────────────────────────
def _num(v):
    try:
        x = float((v or "").replace(",", "").strip())
    except ValueError:
        return None
    return x if math.isfinite(x) else None


def _find(data_dir: Path, stem: str) -> Path:
    for ext in (".csv", ".csv.gz"):
        p = data_dir / f"{stem}{ext}"
        if p.exists():
            return p
    raise FileNotFoundError(f"{data_dir}/{stem}.csv[.gz] 없음")


def _open(path: Path):
    if path.suffix == ".gz":
        return gzip.open(path, "rt", encoding="utf-8-sig", newline="")
    return path.open(encoding="utf-8-sig", newline="")


# ── 선물·현물 ─────────────────────────────────────────────
def load_futures(path: Path) -> Dict[str, Dict[str, float]]:
    """day -> {expiry: 종가}. 거래량 최대 종목 선택."""
    best = defaultdict(dict)
    with _open(path) as f:
        for row in csv.DictReader(f):
            if row["SESSION"] != "정규":
                continue
            if row["PROD_NM"] not in {"코스피200 선물", "미니코스피200 선물"}:
                continue
            price = _num(row["TDD_CLSPRC"])
            vol   = _num(row["ACC_TRDVOL"])
            if row["TRADED_CLOSE"] != "1" or not price or not vol or vol < C.MIN_FUTURES_VOLUME:
                continue
            day, exp = row["BAS_DD"], row["EXPIRY_YM"]
            cur = best[day].get(exp)
            if cur is None or vol > cur[0]:
                best[day][exp] = (vol, price)
    return {d: {e: p for e, (_, p) in v.items()} for d, v in best.items()}


def load_spot(path: Path):
    """[(날짜, 종가), ...] 오름차순."""
    rows = []
    with _open(path) as f:
        for row in csv.DictReader(f):
            rows.append((row["BAS_DD"], float(row["KOSPI200_SPOT_CLOSE"])))
    return sorted(rows)


def rv_by_day(spot, window: int = C.HV_WINDOW) -> Dict[str, float]:
    """20일 종가-종가 실현변동성 (연율 %)."""
    rets = [(spot[i][0], math.log(spot[i][1] / spot[i-1][1])) for i in range(1, len(spot))]
    out  = {}
    for i in range(window - 1, len(rets)):
        w  = [r for _, r in rets[i - window + 1: i + 1]]
        sd = st.pstdev(w) if len(set(w)) > 1 else 0.0
        out[rets[i][0]] = sd * math.sqrt(C.TRADING_DAYS) * 100
    return out


# ── 스마일 ────────────────────────────────────────────────
@dataclass(frozen=True)
class Smile:
    expiry:  str
    days:    int     # 잔존 달력일
    forward: float   # 동일 만기 선물 종가
    points:  tuple   # ((K/F, IV%), ...) OTM만, 거래량 가중


def interpolate(points, x, max_gap=C.MAX_STRIKE_GAP) -> Optional[float]:
    """K/F = x 에서 선형 보간 (외삽·간격 초과 시 None)."""
    xs = [p[0] for p in points]
    i  = bisect.bisect_left(xs, x)
    if i < len(points) and math.isclose(xs[i], x, abs_tol=1e-9):
        return points[i][1]
    if i > 0 and math.isclose(xs[i-1], x, abs_tol=1e-9):
        return points[i-1][1]
    if i == 0 or i == len(points):
        return None
    x0, z0 = points[i-1]
    x1, z1 = points[i]
    if x1 - x0 > max_gap:
        return None
    return z0 + (x - x0) / (x1 - x0) * (z1 - z0)


def build_smiles(options_path: Path, fwd_by_day) -> Dict[str, Dict[str, Smile]]:
    """옵션 CSV 1회 순회 → day -> {expiry: Smile}."""
    out: Dict[str, Dict[str, Smile]] = {}
    with _open(options_path) as f:
        reader = csv.DictReader(f)
        cur_day, buf = None, []

        def flush():
            if not cur_day or not buf:
                return
            fwds = fwd_by_day.get(cur_day, {})
            if not fwds:
                return
            date = datetime.strptime(cur_day, "%Y%m%d").date()
            weighted = defaultdict(lambda: [0.0, 0.0])
            exp_dte: Dict[str, int] = {}
            for r in buf:
                if r["PROD_NM"] != "코스피200 옵션" or r["NAME_TAG"] != "정규":
                    continue
                exp = r["EXPIRY_YM"]
                if exp not in fwds:
                    continue
                strike = _num(r["STRIKE"])
                price  = _num(r["TDD_CLSPRC"])
                iv     = _num(r["IMP_VOLT"])
                vol    = _num(r["ACC_TRDVOL"])
                oi     = _num(r["ACC_OPNINT_QTY"])
                if r["TRADED_CLOSE"] != "1" or not price or price <= 0:
                    continue
                if not strike or iv is None or not (C.IV_MIN <= iv <= C.IV_MAX):
                    continue
                if vol is None or vol < C.MIN_OPTION_VOLUME:
                    continue
                if oi is None or oi < C.MIN_OPEN_INTEREST:
                    continue
                try:
                    dte = (datetime.strptime(r["LAST_TRADING_DATE"], "%Y%m%d").date() - date).days
                except ValueError:
                    continue
                if not (C.MIN_DTE <= dte <= C.MAX_DTE):
                    continue
                m = strike / fwds[exp]
                if not (C.MIN_MONEYNESS <= m <= C.MAX_MONEYNESS):
                    continue
                right = r["RGHT_TP_NM"].upper()
                if right not in {"CALL", "PUT"}:
                    continue
                if (right == "CALL" and m < 1) or (right == "PUT" and m > 1):
                    continue   # OTM만 사용
                if exp in exp_dte and exp_dte[exp] != dte:
                    continue
                exp_dte[exp] = dte
                s, w = weighted[(exp, strike)]
                weighted[(exp, strike)] = [s + iv * vol, w + vol]
            grouped = defaultdict(list)
            for (exp, strike), (s, w) in weighted.items():
                grouped[exp].append((strike / fwds[exp], s / w))
            day_smiles = {}
            for exp, pts in grouped.items():
                if len(pts) < 2:
                    continue
                day_smiles[exp] = Smile(exp, exp_dte[exp], fwds[exp], tuple(sorted(pts)))
            if day_smiles:
                out[cur_day] = day_smiles

        for row in reader:
            d = row["BAS_DD"]
            if d != cur_day:
                flush()
                cur_day, buf = d, []
            buf.append(row)
        flush()
    return out


# ── 묶음 로더 ─────────────────────────────────────────────
@dataclass
class Dataset:
    smiles_by_day: Dict[str, Dict[str, Smile]]
    spot:          list
    rv:            Dict[str, float]   # 20일 실현변동성 (%)


def load_dataset(data_dir: str, cache_dir: str = ".cache", verbose: bool = True) -> Dataset:
    dp = Path(data_dir)
    opt = _find(dp, "kospi200_options_regular")
    fut = _find(dp, "kospi200_futures_regular")
    spt = _find(dp, "kospi200_spot")

    if cache_dir:
        Path(cache_dir).mkdir(parents=True, exist_ok=True)
        stamp = "_".join(str(int(p.stat().st_mtime)) for p in (opt, fut, spt))
        cache = Path(cache_dir) / f"smiles_{stamp}.pkl"
        if cache.exists():
            if verbose:
                print(f"[data] 캐시 로드: {cache.name}")
            with cache.open("rb") as f:
                return pickle.load(f)
    else:
        cache = None

    if verbose:
        print("[data] 선물·현물 로딩...")
    fwds = load_futures(fut)
    spot = load_spot(spt)
    if verbose:
        print("[data] 옵션 스마일 구축 중 (수 분 소요)...")
    smiles = build_smiles(opt, fwds)
    ds = Dataset(smiles, spot, rv_by_day(spot))

    if cache:
        with cache.open("wb") as f:
            pickle.dump(ds, f)
        if verbose:
            print(f"[data] 캐시 저장: {cache.name}")
    return ds
