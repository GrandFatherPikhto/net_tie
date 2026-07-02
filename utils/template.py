# -*- coding: utf-8 -*-
"""
template.py — загрузка текстового шаблона nettie_template.kicad_tpl
и сборка итогового .kicad_mod.

Все поля footprint-а живут в текстовом файле шаблона (str.format-плейсхолдеры,
литеральные фигурные скобки KiCad — удвоенные, например ${{REFERENCE}}).
Здесь — только подстановка значений и шаблоны падов.

Футпринт всегда рисуется на верхней стороне (F.Cu) — это конвенция KiCad.
Для установки на нижнюю сторону футпринт переворачивается на плате (клавиша
F в pcbnew): KiCad сам зеркалит все слои парами F.*→B.* и отражает геометрию.
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

_COURTYARD = (
    '\t(fp_rect\n'
    '\t\t(start {x1} {y1})\n'
    '\t\t(end {x2} {y2})\n'
    '\t\t(stroke\n'
    '\t\t\t(width 0.05)\n'
    '\t\t\t(type solid)\n'
    '\t\t)\n'
    '\t\t(fill no)\n'
    '\t\t(layer "F.CrtYd")\n'
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
                     courtyard: bool = True,
                     courtyard_margin: float = 0.25,
                     template_path: Path | None = None) -> str:
    """Подставляет все поля в шаблон и возвращает готовый .kicad_mod."""
    r1, r2 = d1 / 2.0, d2 / 2.0
    C = r1 + gap + r2
    x1 = -C

    # Courtyard: прямоугольник вокруг всей меди с запасом courtyard_margin.
    # Слева медь может выступать за пад на полуширину горла (шапка при neck>d1).
    # Опционален: нужен только для DRC-правил вида intersectsCourtyard();
    # с memberOfFootprint() не используется. Без него — allow_missing_courtyard.
    if courtyard:
        h = max(neck / 2.0, r1)
        m = courtyard_margin
        cy_block = _COURTYARD.format(
            x1=fmt(round(-(C + max(r1, h) + m), 2)),
            y1=fmt(-round(r2 + m, 2)),
            x2=fmt(round(r2 + m, 2)),
            y2=fmt(round(r2 + m, 2)),
            uid=uuid.uuid4(),
        )
        attr_cy = ""
    else:
        cy_block = ""
        attr_cy = " allow_missing_courtyard"

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
        attr_cy=attr_cy,
        courtyard=cy_block,
        pts=pts_str,
        poly_uid=uuid.uuid4(),
        fab_y=fmt(r2 + 2.5),
        text_uid=uuid.uuid4(),
        pads_str=pads_str,
    )
