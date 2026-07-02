# -*- coding: utf-8 -*-
"""
template.py — загрузка текстового шаблона nettie_template.kicad_tpl
и сборка итогового .kicad_mod.

Все поля footprint-а живут в текстовом файле шаблона (str.format-плейсхолдеры,
литеральные фигурные скобки KiCad — удвоенные, например ${{REFERENCE}}).
Здесь — только подстановка значений и шаблоны падов.
"""

import uuid
from pathlib import Path

TEMPLATE_FILE = "nettie_template.kicad_tpl"

_PAD_SMD = (
    '\t(pad "{num}" smd circle\n'
    '\t\t(at {x} 0)\n'
    '\t\t(size {d} {d})\n'
    '\t\t(layers {layers})\n'
    '\t\t(thermal_bridge_angle 90)\n'
    '\t\t(uuid "{uid}")\n'
    '\t)\n'
)

_PAD_THT = (
    '\t(pad "{num}" thru_hole circle\n'
    '\t\t(at {x} 0)\n'
    '\t\t(size {d} {d})\n'
    '\t\t(drill {dr})\n'
    '\t\t(layers {layers})\n'
    '\t\t(remove_unused_layers no)\n'
    '\t\t(thermal_bridge_angle 90)\n'
    '\t\t(uuid "{uid}")\n'
    '\t)\n'
)


def fmt(v: float) -> str:
    """Число без хвостовых нулей, максимум 6 знаков после запятой."""
    s = f"{v:.6f}".rstrip("0").rstrip(".")
    return s if s not in ("-0", "") else "0"


def load_template(path: Path | None = None) -> str:
    """Читает текст шаблона (по умолчанию — рядом с этим модулем)."""
    tpl = path or Path(__file__).parent / TEMPLATE_FILE
    if not tpl.exists():
        raise FileNotFoundError(f"Не найден файл шаблона: {tpl}")
    return tpl.read_text(encoding="utf-8")


def render_pads(mount: str, x1: float, d1: float, d2: float,
                drill1: float, drill2: float, tented: bool = False) -> str:
    """
    Собирает S-expr обоих падов (малый — «1» в x1, большой — «2» в нуле).

    tented=True — пад без выреза в маске (медь закрыта). Маска — негативный
    слой: наличие F.Mask/*.Mask в слоях пада означает окно в маске.
    Для THT маска закроет только кольцо; ствол отверстия остаётся открытым.
    """
    if mount == "smd":
        layers = '"F.Cu"' if tented else '"F.Cu" "F.Mask"'
        pad1 = _PAD_SMD.format(num=1, x=fmt(x1), d=fmt(d1), layers=layers,
                               uid=uuid.uuid4())
        pad2 = _PAD_SMD.format(num=2, x=0, d=fmt(d2), layers=layers,
                               uid=uuid.uuid4())
    else:
        layers = '"*.Cu"' if tented else '"*.Cu" "*.Mask"'
        pad1 = _PAD_THT.format(num=1, x=fmt(x1), d=fmt(d1), dr=fmt(drill1),
                               layers=layers, uid=uuid.uuid4())
        pad2 = _PAD_THT.format(num=2, x=0, d=fmt(d2), dr=fmt(drill2),
                               layers=layers, uid=uuid.uuid4())
    return pad1 + pad2


def render_footprint(name: str, d1: float, d2: float, gap: float, neck: float,
                     mount: str, drill1: float, drill2: float,
                     poly_points, tented: bool = False,
                     template_path: Path | None = None) -> str:
    """Подставляет все поля в шаблон и возвращает готовый .kicad_mod."""
    r2 = d2 / 2.0
    x1 = -(d1 / 2.0 + gap + r2)

    pts_str = " ".join(f"(xy {fmt(x)} {fmt(y)})" for x, y in poly_points)
    pads_str = render_pads(mount, x1, d1, d2, drill1, drill2, tented)

    return load_template(template_path).format(
        name=name,
        ref_y=fmt(-(r2 + 1.2)),
        ref_uid=uuid.uuid4(),
        val_y=fmt(r2 + 1.2),
        val_uid=uuid.uuid4(),
        ds_uid=uuid.uuid4(),
        mount_upper=mount.upper(),
        d1=fmt(d1),
        d2=fmt(d2),
        neck=fmt(neck),
        gap=fmt(gap),
        desc_uid=uuid.uuid4(),
        pts=pts_str,
        poly_uid=uuid.uuid4(),
        fab_y=fmt(r2 + 2.5),
        text_uid=uuid.uuid4(),
        pads_str=pads_str,
    )
