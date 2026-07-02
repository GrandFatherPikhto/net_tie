#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
kicad_nettie_cli.py — CLI-генератор каплевидных NetTie-2 footprint-ов
для KiCad 10.

Архитектура:
    ipc_calc.py             — физика: IPC-2221, зазоры, Ондердонк
    geometry.py             — контур капли (касательная парабола)
    template.py             — загрузка и рендер текстового шаблона
    nettie_template.kicad_tpl — все поля footprint-а (текстовый файл)

Примеры:
    python kicad_nettie_cli.py -v 12 -i 1.0 -d1 0.65 -d2 3.0 -t smd
    python kicad_nettie_cli.py -v 400 -i 5 -d1 1.2 -d2 4.0 -t tht --drill2 2.0
"""

import argparse
import sys

try:
    import utils.geometry as geometry
    import utils.ipc_calc as ipc_calc
    import utils.template as template
    import utils.args_util as args_util
except ImportError as e:
    print(f"❌ Не найден модуль: {e.name}.py — он должен лежать рядом с CLI.",
          file=sys.stderr)
    sys.exit(1)

def main() -> int:
    p = argparse.ArgumentParser(
        description="Генератор каплевидных NetTie-2 footprint-ов для KiCad 10",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    args_util.fill_args(p)
    args = p.parse_args()

    try:
        params = args_util.prepare_nettie_args(args)
    except ValueError as e:
        print(f"❌ {e}", file=sys.stderr)
        return 1

    # Геометрия
    if params.is_pads_equal:
        poly = geometry.equal_radii_contour(params.r1, params.C, params.neck, args.points)
    else:
        poly = geometry.teardrop_polygon(params.r1, params.r2, params.C, params.neck, args.points)

    # Рендер
    content = template.render_footprint(
        params.name, params.d1, params.d2, params.gap,
        params.neck, params.mount, params.drill1, params.drill2,
        poly, tented=args.tented, courtyard=not args.no_courtyard,
        courtyard_margin=args.courtyard_margin)

    args.outdir.mkdir(parents=True, exist_ok=True)
    out = args.outdir / params.fname
    out.write_text(content, encoding="utf-8")

    # Сводка
    i_cont = ipc_calc.ipc_current_a(params.neck, args.temp_rise, args.copper)
    fuse = lambda t: ipc_calc.onderdonk_fusing_a(params.neck, args.copper, t)
    print("🔥 Смузи-парабола готова для KiCad 10!")
    print("=" * 50)
    print(f"📦 Имя файла:    {params.fname}")
    print(f"🔧 Тип монтажа:  {params.mount.upper()}")
    print(f"📏 Физическая L: {params.L:.2f} мм")
    print(f"⚡ Узкое горло:  {params.neck:.3f} мм "
          f"(IPC-минимум {params.neck_ipc:.3f} × {args.neck_safety:g})")
    print(f"🌡  Непрерывно:   {i_cont:.1f} А при ΔT={args.temp_rise:g}°C")
    print(f"💥 Плавление:    {fuse(1.0):.0f} А/1с, {fuse(0.01):.0f} А/10мс, "
          f"{fuse(1e-4):.0f} А/100мкс")
    print(f"↔️  Зазор пад-пад: {params.gap:.3f} мм (IPC-2221B ×{args.safety})")
    print(f"🎭 Маска:        {'закрыта (tented)' if args.tented else 'открытые пады'}")
    if params.mount == "tht":
        print(f"🕳  Сверловка:    {params.drill1:.2f} / {params.drill2:.2f} мм")
    for w in params.warnings:
        print(f"⚠️  {w}")
    print("=" * 50)
    print(f"💾 {out.resolve()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
