"""전략당 그래프 1개 (선 2개: 당일 체결 / 익일 체결). 화면에만 표시하고 파일로 저장하지 않는다."""
from __future__ import annotations

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from matplotlib import font_manager

_have = {f.name for f in font_manager.fontManager.ttflist}
for _name in ("Malgun Gothic", "AppleGothic", "NanumGothic", "Noto Sans CJK KR"):     # 설치된 한글 폰트를 하나 고른다
    if _name in _have:
        plt.rcParams["font.family"] = _name
        break
plt.rcParams["axes.unicode_minus"] = False
plt.rcParams.update({"axes.spines.top": False, "axes.spines.right": False, "axes.grid": True, "grid.alpha": 0.25})


def strategy_figure(name: str, dates, eq_same_day, eq_next_day):
    x = pd.to_datetime(pd.Series(dates), format="%Y%m%d")
    fig, ax = plt.subplots(figsize=(9, 4))
    ax.plot(x, 100 * np.array(eq_same_day[1:]), label="당일 체결", color="#D55E00", lw=1.5)
    ax.plot(x, 100 * np.array(eq_next_day[1:]), label="익일 체결", color="#0072B2", lw=1.5)
    ax.axhline(0, color="k", lw=0.6)
    ax.set_title(name)
    ax.set_ylabel("누적 수익률 (%)")
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%y-%m"))
    ax.xaxis.set_major_locator(mdates.MonthLocator(interval=2))
    ax.legend(frameon=False)
    fig.tight_layout()
    return fig


def show_all(results, dates):
    """전략별 그림을 모두 만든 뒤 한 번에 표시한다."""
    by = {}
    for r in results:
        by.setdefault(r["strategy"], {})[r["fill"]] = r["equity"]
    for name, eqs in by.items():
        strategy_figure(name, dates, eqs["당일 체결"], eqs["익일 체결"])
    plt.show()
