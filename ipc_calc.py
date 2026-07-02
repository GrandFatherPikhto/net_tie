# -*- coding: utf-8 -*-
"""
ipc_calc.py — расчёты по IPC-2221: ширина проводника, зазоры,
токи плавления (Ондердонк).
"""

import math

OZ_TO_MIL = 1.378          # толщина 1 oz меди в милах (35 мкм)
MIL_TO_MM = 0.0254
CMIL_MM2 = 5.067e-4        # площадь одного circular mil, мм²

# IPC-2221B, таблица зазоров, колонка B2 (внешний слой, без покрытия, < 3050 м)
IPC_CLEARANCE_B2 = [
    (15,   0.10),
    (30,   0.10),
    (50,   0.60),
    (100,  0.60),
    (150,  0.60),
    (170,  1.25),
    (250,  1.25),
    (300,  1.25),
    (500,  2.50),
]


def ipc_neck_width_mm(current_a: float, temp_rise_c: float = 10.0,
                      copper_oz: float = 1.0, internal: bool = False) -> float:
    """Минимальная ширина медного мостика по току (IPC-2221)."""
    k = 0.024 if internal else 0.048
    area_mil2 = (current_a / (k * temp_rise_c ** 0.44)) ** (1.0 / 0.725)
    width_mil = area_mil2 / (copper_oz * OZ_TO_MIL)
    return width_mil * MIL_TO_MM


def ipc_current_a(width_mm: float, temp_rise_c: float = 10.0,
                  copper_oz: float = 1.0, internal: bool = False) -> float:
    """Обратная задача: непрерывный ток для заданной ширины."""
    k = 0.024 if internal else 0.048
    area_mil2 = width_mm / MIL_TO_MM * copper_oz * OZ_TO_MIL
    return k * temp_rise_c ** 0.44 * area_mil2 ** 0.725


def ipc_clearance_mm(voltage_v: float) -> float:
    """Минимальный изоляционный зазор по напряжению (IPC-2221B, B2)."""
    for vmax, clearance in IPC_CLEARANCE_B2:
        if voltage_v <= vmax:
            return clearance
    return 0.005 * voltage_v  # > 500 В: 0.005 мм/В


def onderdonk_fusing_a(width_mm: float, copper_oz: float, t_s: float,
                       t_ambient: float = 25.0) -> float:
    """Ток плавления медного сечения за время t_s (формула Ондердонка)."""
    area_cmil = (width_mm * copper_oz * OZ_TO_MIL * MIL_TO_MM) / CMIL_MM2
    return area_cmil * math.sqrt(
        math.log10((1083.0 - t_ambient) / (234.0 + t_ambient) + 1.0)
        / (33.5 * t_s))
