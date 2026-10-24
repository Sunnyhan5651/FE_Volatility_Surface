#!/usr/bin/env python3
"""Plot a KOSPI 200 monthly-option IV surface with bilinear interpolation.

Inputs are the regular-session KRX daily option and futures CSVs produced by
download_krx_kospi200_252d.py. X is K/F for a future with the *same* expiry
month as the option, Y is calendar days to the option's last trading day, and
Z is the KRX-reported IV in percent. No extrapolation is performed.

For each traded expiry, linearly interpolate IV between liquid observed
moneyness nodes. Between two traded expiries, linearly interpolate those
strike-interpolated values in calendar time. This is bilinear interpolation
where the four surrounding market observations exist. Unsupported cells stay
empty; it does not infer a smile from a single quote or fill distant gaps.
"""

from __future__ import annotations

import argparse
import bisect
import csv
import math
import os
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


DEFAULT_DATA = Path(__file__).resolve().parent / "kospi200_252d_20251014_20261023"
OPTION_COLUMNS = {
    "BAS_DD", "PROD_NM", "RGHT_TP_NM", "EXPIRY_YM", "STRIKE",
    "NAME_TAG", "LAST_TRADING_DATE", "TRADED_CLOSE", "TDD_CLSPRC",
    "IMP_VOLT", "ACC_TRDVOL", "ACC_OPNINT_QTY",
}
FUTURE_COLUMNS = {
    "BAS_DD", "PROD_NM", "EXPIRY_YM", "SESSION", "TRADED_CLOSE",
    "TDD_CLSPRC", "ACC_TRDVOL",
}


def number(value: str | None) -> float | None:
    try:
        result = float((value or "").replace(",", "").strip())
    except ValueError:
        return None
    return result if math.isfinite(result) else None


def checked_reader(file, required: set[str]):
    reader = csv.DictReader(file)
    missing = required - set(reader.fieldnames or [])
    if missing:
        raise ValueError(f"CSV 필수 칼럼 누락: {', '.join(sorted(missing))}")
    return reader


def normalize_date(value: str) -> str:
    value = value.replace("-", "")
    datetime.strptime(value, "%Y%m%d")
    return value


def latest_date(path: Path) -> str:
    latest = ""
    with path.open(encoding="utf-8-sig", newline="") as file:
        for row in checked_reader(file, OPTION_COLUMNS):
            if row["BAS_DD"] > latest:
                latest = row["BAS_DD"]
    if not latest:
        raise ValueError("옵션 CSV가 비어 있습니다.")
    return normalize_date(latest)


def futures_by_expiry(path: Path, day: str, min_volume: int) -> dict[str, tuple[float, str]]:
    best: dict[str, tuple[float, float, str]] = {}
    with path.open(encoding="utf-8-sig", newline="") as file:
        for row in checked_reader(file, FUTURE_COLUMNS):
            if row["BAS_DD"] != day or row["SESSION"] != "정규":
                continue
            if row["PROD_NM"] not in {"코스피200 선물", "미니코스피200 선물"}:
                continue
            price = number(row["TDD_CLSPRC"])
            volume = number(row["ACC_TRDVOL"])
            if row["TRADED_CLOSE"] != "1" or price is None or price <= 0:
                continue
            if volume is None or volume < min_volume:
                continue
            expiry = row["EXPIRY_YM"]
            candidate = (volume, price, row["PROD_NM"])
            if expiry not in best or candidate[0] > best[expiry][0]:
                best[expiry] = candidate
    return {expiry: (price, product) for expiry, (_, price, product) in best.items()}


@dataclass(frozen=True)
class Smile:
    expiry: str
    days: int
    forward: float
    future_product: str
    points: tuple[tuple[float, float], ...]  # (K/F, IV percentage)


def liquid_smiles(path: Path, day: str, forwards: dict[str, tuple[float, str]], args):
    weighted = defaultdict(lambda: [0.0, 0.0])
    expiry_days: dict[str, int] = {}
    counts = Counter()
    date = datetime.strptime(day, "%Y%m%d").date()
    with path.open(encoding="utf-8-sig", newline="") as file:
        for row in checked_reader(file, OPTION_COLUMNS):
            if row["BAS_DD"] != day:
                continue
            counts["day_rows"] += 1
            if row["PROD_NM"] != "코스피200 옵션" or row["NAME_TAG"] != "정규":
                continue
            expiry = row["EXPIRY_YM"]
            if expiry not in forwards:
                counts["no_matching_liquid_future"] += 1
                continue
            strike = number(row["STRIKE"])
            price = number(row["TDD_CLSPRC"])
            iv = number(row["IMP_VOLT"])
            volume = number(row["ACC_TRDVOL"])
            oi = number(row["ACC_OPNINT_QTY"])
            if row["TRADED_CLOSE"] != "1" or not price or price <= 0:
                counts["no_traded_close"] += 1
                continue
            if not strike or strike <= 0 or iv is None or not args.iv_min <= iv <= args.iv_max:
                counts["invalid_strike_or_iv"] += 1
                continue
            if volume is None or volume < args.min_volume or oi is None or oi < args.min_open_interest:
                counts["below_liquidity_cutoff"] += 1
                continue
            try:
                dte = (datetime.strptime(row["LAST_TRADING_DATE"], "%Y%m%d").date() - date).days
            except ValueError:
                counts["invalid_expiry_date"] += 1
                continue
            if not args.min_dte <= dte <= args.max_dte:
                counts["outside_tenor_range"] += 1
                continue
            forward = forwards[expiry][0]
            m = strike / forward
            if not args.min_moneyness <= m <= args.max_moneyness:
                counts["outside_moneyness_range"] += 1
                continue
            right = row["RGHT_TP_NM"].upper()
            if right not in {"CALL", "PUT"}:
                counts["unknown_right"] += 1
                continue
            if args.otm_only and ((right == "CALL" and m < 1) or (right == "PUT" and m > 1)):
                counts["itm_quote"] += 1
                continue
            if expiry in expiry_days and expiry_days[expiry] != dte:
                raise ValueError(f"{day} {expiry}: 옵션 최종거래일이 행마다 다릅니다.")
            expiry_days[expiry] = dte
            iv_sum, weight_sum = weighted[(expiry, strike)]
            weighted[(expiry, strike)] = [iv_sum + iv * volume, weight_sum + volume]
            counts["selected_rows"] += 1

    grouped = defaultdict(list)
    for (expiry, strike), (iv_sum, weight_sum) in weighted.items():
        grouped[expiry].append((strike / forwards[expiry][0], iv_sum / weight_sum))
    smiles = []
    for expiry, points in grouped.items():
        if len(points) < 2:
            counts["single_quote_expiries"] += 1
            continue
        forward, product = forwards[expiry]
        smiles.append(Smile(expiry, expiry_days[expiry], forward, product, tuple(sorted(points))))
    smiles.sort(key=lambda smile: smile.days)
    if len(smiles) < 2:
        raise ValueError(
            f"{day}: 보간에 필요한 유동성 있는 만기가 2개 미만입니다. "
            "--min-volume 또는 --min-futures-volume을 낮추거나 다른 날짜를 선택하세요."
        )
    return smiles, counts


def interpolate_strike(points: tuple[tuple[float, float], ...], x: float, max_gap: float):
    """Return (IV, exact-observation flag), without strike extrapolation."""
    xs = [point[0] for point in points]
    i = bisect.bisect_left(xs, x)
    if i < len(points) and math.isclose(xs[i], x, abs_tol=1e-9, rel_tol=0):
        return points[i][1], True
    if i > 0 and math.isclose(xs[i - 1], x, abs_tol=1e-9, rel_tol=0):
        return points[i - 1][1], True
    if i == 0 or i == len(points):
        return None, False
    x0, z0 = points[i - 1]
    x1, z1 = points[i]
    if x1 - x0 > max_gap:
        return None, False
    weight = (x - x0) / (x1 - x0)
    return z0 + weight * (z1 - z0), False


def axis(start: float, stop: float, step: float, extra=()) -> list[float]:
    count = math.floor((stop - start) / step)
    regular = [start + i * step for i in range(count + 1)]
    regular.append(stop)
    return sorted({round(v, 10) for v in (*regular, *extra) if start - 1e-10 <= v <= stop + 1e-10})


def build_grid(smiles: list[Smile], args):
    # Include market strikes and actual expiry days as grid nodes. All other
    # nodes are evaluated by strike-then-tenor linear interpolation.
    xs = axis(args.min_moneyness, args.max_moneyness, args.m_step,
              (x for smile in smiles for x, _ in smile.points))
    ys = axis(smiles[0].days, smiles[-1].days, args.tenor_step,
              (smile.days for smile in smiles))
    day_to_smile = {smile.days: smile for smile in smiles}
    observed_days = sorted(day_to_smile)
    rows = []
    for days in ys:
        direct = day_to_smile.get(days)
        if direct:
            lower = upper = direct
            weight = 0.0
        else:
            i = bisect.bisect_left(observed_days, days)
            if i == 0 or i == len(observed_days):
                raise AssertionError("tenor grid outside observed expiry range")
            lower = day_to_smile[observed_days[i - 1]]
            upper = day_to_smile[observed_days[i]]
            weight = (days - lower.days) / (upper.days - lower.days)
        row = []
        for x in xs:
            method = ""
            z0, exact0 = interpolate_strike(lower.points, x, args.max_strike_gap)
            z1, exact1 = (z0, exact0) if direct else interpolate_strike(
                upper.points, x, args.max_strike_gap
            )
            if upper.days - lower.days <= args.max_tenor_gap and z0 is not None and z1 is not None:
                iv = z0 + weight * (z1 - z0)
                method = ("observed" if exact0 else "strike_linear") if direct else (
                    "tenor_linear" if exact0 and exact1 else "bilinear"
                )
            else:
                iv = None
            row.append((iv, method, lower.expiry, upper.expiry))
        rows.append(row)
    return xs, ys, rows


def write_grid(path: Path, day: str, xs, ys, rows):
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(["date", "moneyness_k_over_f", "days_to_expiry", "iv_pct",
                         "method", "lower_expiry", "upper_expiry"])
        for days, row in zip(ys, rows):
            for x, (iv, method, lower, upper) in zip(xs, row):
                writer.writerow([day, f"{x:.10f}", int(days),
                                 "" if iv is None else f"{iv:.8f}",
                                 method or "unsupported", lower, upper])


def render_png(path: Path, day: str, smiles, xs, ys, rows):
    os.environ.setdefault("MPLCONFIGDIR", str(path.parent / ".matplotlib_cache"))
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib import cm, colors
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection

    z = [[cell[0] for cell in row] for row in rows]
    values = [value for row in z for value in row if value is not None]
    if not values:
        raise ValueError("유효한 보간 격자가 없습니다. 필터나 간격 제한을 확인하세요.")
    norm = colors.Normalize(vmin=min(values), vmax=max(values) + 1e-9)
    cmap = matplotlib.colormaps["viridis"]
    quads, face_values = [], []
    for j in range(len(ys) - 1):
        for i in range(len(xs) - 1):
            corners = (z[j][i], z[j][i + 1], z[j + 1][i + 1], z[j + 1][i])
            if any(value is None for value in corners):
                continue
            quads.append(((xs[i], ys[j], corners[0]),
                          (xs[i + 1], ys[j], corners[1]),
                          (xs[i + 1], ys[j + 1], corners[2]),
                          (xs[i], ys[j + 1], corners[3])))
            face_values.append(sum(corners) / 4)
    if not quads:
        raise ValueError(
            "서로 맞닿은 유효 격자 셀이 없습니다. 다른 날짜를 선택하거나 "
            "--max-strike-gap/유동성 기준을 조정하세요."
        )

    fig = plt.figure(figsize=(12, 8), dpi=170, facecolor="#f8fbfe")
    ax = fig.add_subplot(111, projection="3d")
    ax.set_facecolor("#f8fbfe")
    if quads:
        surface = Poly3DCollection(quads, facecolors=cmap(norm(face_values)),
                                   edgecolors="none", alpha=0.93)
        ax.add_collection3d(surface)
    observed = [(x, smile.days, iv) for smile in smiles for x, iv in smile.points]
    ax.scatter(*zip(*observed), s=13, color="#19344c", edgecolor="white",
               linewidth=0.25, depthshade=False, label="Traded liquid IV")
    ax.set_xlim(xs[0], xs[-1])
    ax.set_ylim(ys[0], ys[-1])
    ax.set_zlim(max(0, min(values) - 3), max(values) + 3)
    ax.set_xticks([x for x in (0.85, 0.9, 0.95, 1.0, 1.05, 1.1, 1.15)
                   if xs[0] <= x <= xs[-1]])
    ax.set_yticks([smile.days for smile in smiles])
    ax.set_xlabel("Moneyness K / F (same expiry)", labelpad=14)
    ax.set_ylabel("Days to expiry", labelpad=12)
    ax.set_zlabel("Implied volatility (%)", labelpad=12)
    ax.set_box_aspect((1.7, 1.0, 0.85))
    ax.view_init(elev=26, azim=-58)
    ax.legend(loc="upper right", fontsize=8)
    fig.suptitle(f"KOSPI 200 monthly options | bilinear IV surface | {day}",
                 fontsize=16, fontweight="bold", y=0.96)
    fig.text(0.5, 0.07,
             f"{len(smiles)} observed expiries; {len(observed)} traded strike nodes; "
             f"{len(quads)} supported cells. Empty regions are not extrapolated.",
             ha="center", fontsize=10, color="#45596c")
    fig.colorbar(cm.ScalarMappable(norm=norm, cmap=cmap), ax=ax,
                 shrink=0.67, pad=0.12, aspect=23, label="IV (%)")
    fig.savefig(path, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    return len(quads)


def main():
    parser = argparse.ArgumentParser(description="KRX 정규 월물 옵션의 K/F × 잔존만기 bilinear IV 3D 표면")
    parser.add_argument("--options", type=Path, default=DEFAULT_DATA / "kospi200_options_regular.csv")
    parser.add_argument("--futures", type=Path, default=DEFAULT_DATA / "kospi200_futures_regular.csv")
    parser.add_argument("--date", help="YYYYMMDD 또는 YYYY-MM-DD (기본값: 옵션 CSV 마지막 거래일)")
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--min-volume", type=int, default=10, help="옵션 최소 일별 거래량")
    parser.add_argument("--min-open-interest", type=int, default=10, help="옵션 최소 미결제약정")
    parser.add_argument("--min-futures-volume", type=int, default=100, help="동일 만기 선물 최소 일별 거래량")
    parser.add_argument("--iv-min", type=float, default=3.0)
    parser.add_argument("--iv-max", type=float, default=150.0)
    parser.add_argument("--min-dte", type=int, default=5)
    parser.add_argument("--max-dte", type=int, default=180)
    parser.add_argument("--min-moneyness", type=float, default=0.85)
    parser.add_argument("--max-moneyness", type=float, default=1.15)
    parser.add_argument("--m-step", type=float, default=0.005, help="규칙 머니니스 격자 간격")
    parser.add_argument("--tenor-step", type=int, default=2, help="규칙 만기 격자 간격(일)")
    parser.add_argument("--max-strike-gap", type=float, default=0.06,
                        help="행사가 보간에 허용하는 최대 K/F 간격")
    parser.add_argument("--max-tenor-gap", type=int, default=65,
                        help="만기 보간에 허용하는 최대 일수")
    parser.add_argument("--include-itm", dest="otm_only", action="store_false",
                        help="기본 OTM 풋·콜 필터를 해제")
    args = parser.parse_args()
    if not args.options.is_file() or not args.futures.is_file():
        parser.error("옵션 및 선물 CSV 경로를 확인하세요.")
    if (args.min_volume < 1 or args.min_open_interest < 0 or args.min_futures_volume < 1
            or args.min_dte < 1 or args.max_dte < args.min_dte or args.iv_min <= 0
            or args.iv_max <= args.iv_min or args.min_moneyness <= 0
            or args.max_moneyness <= args.min_moneyness or args.m_step <= 0
            or args.tenor_step < 1 or args.max_strike_gap <= 0 or args.max_tenor_gap < 1):
        parser.error("필터와 격자 간격은 양수이며, 최대값은 최소값보다 커야 합니다.")
    try:
        day = normalize_date(args.date) if args.date else latest_date(args.options)
        forwards = futures_by_expiry(args.futures, day, args.min_futures_volume)
        smiles, counts = liquid_smiles(args.options, day, forwards, args)
        xs, ys, grid = build_grid(smiles, args)
        output_dir = args.output_dir or args.options.parent / "bilinear_iv_surface_results"
        output_dir.mkdir(parents=True, exist_ok=True)
        csv_path = output_dir / f"iv_grid_{day}.csv"
        png_path = output_dir / f"iv_surface_3d_{day}.png"
        cells = render_png(png_path, day, smiles, xs, ys, grid)
        write_grid(csv_path, day, xs, ys, grid)
    except (OSError, ValueError, ImportError) as exc:
        parser.exit(1, f"오류: {exc}\n")
    print(f"날짜 {day} | 옵션 유효 행 {counts['selected_rows']}개 | 관측 만기 {len(smiles)}개")
    for smile in smiles:
        print(f"  {smile.expiry}: DTE {smile.days}, 선물 {smile.future_product} "
              f"{smile.forward:.2f}, IV 관측 행사가 {len(smile.points)}개")
    print(f"보간 격자 {len(xs)}×{len(ys)}개 | 유효 3D 셀 {cells}개")
    print(f"CSV: {csv_path.resolve()}\nPNG: {png_path.resolve()}")


if __name__ == "__main__":
    main()
