# -*- coding: utf-8 -*-
"""
geometry.py — построение контура капли NetTie.

Ключевая идея (устранение «зазубрин» у малого пада):
вершина параболы лежит на высоте h = max(neck/2, r1), т.е. НЕ НИЖЕ
верхушки малой окружности. При h = r1 парабола касается малой окружности
в её вершине (наклоны обеих кривых там нулевые → G1-гладкость), при
h > r1 контур замыкается полукруглой шапкой радиуса h. Кривая нигде не
пересекает окружность под углом, поэтому «уши» не возникают.

Вход в большую окружность — по аналитическому условию касания:
    f(xt) = √(r2² − xt²),   f'(xt) = −xt / √(r2² − xt²),
точка касания xt находится бисекцией, дальше контур идёт по дуге
самой окружности до её вершины.
"""

import math

_EPS = 1e-9


def teardrop_polygon(r1: float, r2: float, center_dist: float,
                     neck: float, n_points: int = 48):
    """
    Замкнутый контур капли (ось Y вниз, как в KiCad).

    Малый пад: центр (-center_dist, 0), радиус r1.
    Большой пад: центр (0, 0), радиус r2.
    neck — минимальная ширина меди по току.

    Возвращает список (x, y).
    """
    C = center_dist
    h = max(neck / 2.0, r1)          # вершина не ниже верхушки малого пада
    if h >= r2:
        raise ValueError(
            f"Полуширина горла {h:.3f} мм ≥ радиуса большого пада "
            f"{r2:.3f} мм — увеличьте d2 или уменьшите ток.")

    # ── Точка касания большой окружности (бисекция) ──────────────────
    def residual(xt: float) -> float:
        yt = math.sqrt(r2 * r2 - xt * xt)
        a = -xt / (2.0 * (xt + C) * yt)
        return h + a * (xt + C) ** 2 - yt

    lo, hi = -r2 * (1.0 - _EPS), -_EPS   # residual(lo) > 0, residual(hi) < 0
    for _ in range(100):
        mid = 0.5 * (lo + hi)
        if residual(mid) > 0:
            lo = mid
        else:
            hi = mid
    xt = 0.5 * (lo + hi)
    yt = math.sqrt(r2 * r2 - xt * xt)
    a = -xt / (2.0 * (xt + C) * yt)

    # ── Верхняя половина: парабола от вершины (-C, h) до касания ─────
    par = []
    for i in range(n_points + 1):
        x = -C + (xt + C) * i / n_points
        par.append((x, h + a * (x + C) ** 2))

    # ── Дуга большой окружности от точки касания до вершины (0, r2) ──
    n_arc = max(6, n_points // 4)
    ang_t = math.atan2(yt, xt)                    # II четверть
    arc = []
    for i in range(1, n_arc + 1):
        ang = ang_t + (math.pi / 2 - ang_t) * i / n_arc
        arc.append((r2 * math.cos(ang), r2 * math.sin(ang)))

    half = par + arc
    top = [(x, -y) for x, y in half]              # ось Y вниз
    bottom = [(x, y) for x, y in reversed(half)]

    # ── Шапка у малого конца, если горло шире пада ────────────────────
    cap = []
    if h > r1 + _EPS:
        n_cap = max(8, n_points // 3)
        for i in range(1, n_cap):
            ang = math.pi / 2 + math.pi * i / n_cap
            cap.append((-C + h * math.cos(ang), h * math.sin(ang)))

    return top + bottom + cap
