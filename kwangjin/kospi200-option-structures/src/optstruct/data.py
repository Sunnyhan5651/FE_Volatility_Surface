"""KRX 원자료(옵션·선물·지수) 로드와 일별 IV 스마일 구성."""
from __future__ import annotations

import csv
import gzip
import math
import pickle
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from . import config as C

OPTIONS = "kospi200_options_regular.csv"
FUTURES = "kospi200_futures_regular.csv"
SPOT = "kospi200_spot.csv"


@dataclass(frozen=True)
class Smile:
    expiry: str     # 만기월 YYYYMM
    days: int       # 잔존 달력일
    forward: float  # 같은 만기 선물 종가
    points: tuple   # ((K/F, IV%), ...) K/F 오름차순


@dataclass
class Dataset:
    smiles: dict    # {날짜: {만기: Smile}}
    fwd: dict       # {날짜: {만기: 선물가}}  (스마일이 없는 날의 평가에도 사용)
    spot: list      # [(날짜, KOSPI200 종가), ...]


def _num(v):
    try:
        x = float((v or "").replace(",", "").strip())
    except ValueError:
        return None
    return x if math.isfinite(x) else None


def open_csv(path: Path):
    """.csv 가 없으면 같은 이름의 .csv.gz 를 연다."""
    if path.exists():
        return path.open(encoding="utf-8-sig", newline="")
    return gzip.open(path.with_name(path.name + ".gz"), "rt", encoding="utf-8-sig", newline="")


def load_futures(path: Path) -> dict:
    """날짜·만기별로 거래량이 가장 많은 정규세션 선물(코스피200·미니) 종가."""
    best = defaultdict(dict)
    with open_csv(path) as f:
        for row in csv.DictReader(f):
            if row["SESSION"] != "정규" or row["PROD_NM"] not in {"코스피200 선물", "미니코스피200 선물"}:
                continue
            p, v = _num(row["TDD_CLSPRC"]), _num(row["ACC_TRDVOL"])
            if row["TRADED_CLOSE"] != "1" or not p or p <= 0 or not v or v < C.MIN_FUT_VOL:
                continue
            cur = best[row["BAS_DD"]].get(row["EXPIRY_YM"])
            if cur is None or v > cur[0]:
                best[row["BAS_DD"]][row["EXPIRY_YM"]] = (v, p)
    return {d: {e: p for e, (_, p) in ex.items()} for d, ex in best.items()}


def _day_smiles(day, rows, fw):
    date = datetime.strptime(day, "%Y%m%d").date()
    wsum, edays = defaultdict(lambda: [0.0, 0.0]), {}
    for row in rows:
        if row["PROD_NM"] != "코스피200 옵션" or row["NAME_TAG"] != "정규":
            continue
        e = row["EXPIRY_YM"]
        if e not in fw:
            continue
        K, p, iv = _num(row["STRIKE"]), _num(row["TDD_CLSPRC"]), _num(row["IMP_VOLT"])
        vol, oi = _num(row["ACC_TRDVOL"]), _num(row["ACC_OPNINT_QTY"])
        if row["TRADED_CLOSE"] != "1" or not p or p <= 0:
            continue
        if not K or K <= 0 or iv is None or not C.IV_MIN <= iv <= C.IV_MAX:
            continue
        if vol is None or vol < C.MIN_VOLUME or oi is None or oi < C.MIN_OI:
            continue
        try:
            dte = (datetime.strptime(row["LAST_TRADING_DATE"], "%Y%m%d").date() - date).days
        except ValueError:
            continue
        if not C.MIN_DTE <= dte <= C.MAX_DTE:
            continue
        m = K / fw[e]
        if not C.MIN_M <= m <= C.MAX_M:
            continue
        right = row["RGHT_TP_NM"].upper()
        if right not in {"CALL", "PUT"} or (right == "CALL" and m < 1) or (right == "PUT" and m > 1):
            continue                                  # OTM 만 사용
        if e in edays and edays[e] != dte:
            continue
        edays[e] = dte
        s, w = wsum[(e, K)]
        wsum[(e, K)] = [s + iv * vol, w + vol]        # 거래량 가중 IV
    grp = defaultdict(list)
    for (e, K), (s, w) in wsum.items():
        grp[e].append((K / fw[e], s / w))
    return {e: Smile(e, edays[e], fw[e], tuple(sorted(pts))) for e, pts in grp.items() if len(pts) >= 2}


def build_smiles(path: Path, fwd: dict) -> dict:
    out = {}
    with open_csv(path) as f:
        day, buf = None, []
        for row in csv.DictReader(f):
            if row["BAS_DD"] != day:
                if day is not None and fwd.get(day):
                    sm = _day_smiles(day, buf, fwd[day])
                    if sm:
                        out[day] = sm
                day, buf = row["BAS_DD"], []
            buf.append(row)
        if day is not None and fwd.get(day):
            sm = _day_smiles(day, buf, fwd[day])
            if sm:
                out[day] = sm
    return out


def load_spot(path: Path) -> list:
    with open_csv(path) as f:
        return sorted((r["BAS_DD"], float(r["KOSPI200_SPOT_CLOSE"])) for r in csv.DictReader(f))


def load_dataset(data_dir: Path, cache_dir: Path | None = None) -> Dataset:
    """원자료를 읽어 Dataset 을 만든다. 스마일은 cache_dir 에 저장해 두 번째부터 빠르게 읽는다."""
    data_dir = Path(data_dir)
    fwd = load_futures(data_dir / FUTURES)
    cache = Path(cache_dir) / "smiles.pkl" if cache_dir else None
    smiles = None
    if cache and cache.exists():
        try:
            with cache.open("rb") as f:
                raw = pickle.load(f)
            smiles = {d: {e: Smile(e, *v) for e, v in ex.items()} for d, ex in raw.items()}
        except Exception:
            smiles = None
    if smiles is None:
        print("일별 스마일 구성 중 (최초 1회, 1~2분)...")
        smiles = build_smiles(data_dir / OPTIONS, fwd)
        if cache:
            try:
                cache.parent.mkdir(parents=True, exist_ok=True)
                with cache.open("wb") as f:              # 클래스 대신 튜플로 저장 (실행 방식과 무관하게 읽히도록)
                    pickle.dump({d: {e: (s.days, s.forward, s.points) for e, s in ex.items()}
                                 for d, ex in smiles.items()}, f)
            except OSError:
                pass
    return Dataset(smiles=smiles, fwd=fwd, spot=load_spot(data_dir / SPOT))
