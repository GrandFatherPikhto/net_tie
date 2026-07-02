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
from pathlib import Path

try:
    import geometry
    import ipc_calc
    import template
except ImportError as e:
    print(f"❌ Не найден модуль: {e.name}.py — он должен лежать рядом с CLI.",
          file=sys.stderr)
    sys.exit(1)

# Маленький эпсилон для сравнения
_EPS = 1e-9

def main() -> int:
    p = argparse.ArgumentParser(
        description="Генератор каплевидных NetTie-2 footprint-ов для KiCad 10",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    p.add_argument("-d", type=float,
                   help="Диаметр падов (если они равны), мм")
    p.add_argument("-d1", type=float,
                   help="диаметр большого пада, мм")
    p.add_argument("-d2", type=float,
                   help="диаметр малого пада, мм")

    p.add_argument("-v", "--voltage", type=float, required=True,
                   help="рабочее напряжение, В (→ зазор/длина перехода по IPC-2221B)")
    p.add_argument("-i", "--current", type=float, required=True,
                   help="максимальный ток (RMS для импульсных схем), А")
    p.add_argument("-t", "--type", choices=("smd", "tht"), default="smd",
                   help="тип монтажа")
    p.add_argument("--drill1", type=float, default=None,
                   help="сверло пада 1 для THT, мм (по умолчанию d1/2)")
    p.add_argument("--drill2", type=float, default=None,
                   help="сверло пада 2 для THT, мм (по умолчанию d2/2)")
    p.add_argument("--temp-rise", type=float, default=10.0,
                   help="допустимый перегрев меди, °C")
    p.add_argument("--copper", type=float, default=1.0,
                   help="толщина меди, oz")
    p.add_argument("--safety", type=float, default=1.5,
                   help="коэффициент запаса по зазору")
    p.add_argument("-k", "--neck-safety", type=float, default=2.0,
                   help="коэффициент запаса по ширине горла")
    p.add_argument("--min-gap", type=float, default=0.15,
                   help="минимальный зазор край-край, мм")
    p.add_argument("--gap", type=float, default=None,
                   help="зазор край-край вручную, мм (перекрывает расчёт по -v)")
    p.add_argument("--neck", type=float, default=None,
                   help="ширина горла вручную, мм (перекрывает расчёт по -i)")
    p.add_argument("--tented", action="store_true",
                   help="закрыть пады паяльной маской (без выреза)")
    p.add_argument("--no-courtyard", action="store_true",
                   help="не генерировать courtyard (вернёт allow_missing_courtyard)")
    p.add_argument("--courtyard-margin", type=float, default=0.25,
                   help="отступ courtyard от меди, мм")
    p.add_argument("--points", type=int, default=48,
                   help="число точек на половину контура капли")
    p.add_argument("-o", "--outdir", type=Path, default=Path("."),
                   help="каталог для сохранения")
    args = p.parse_args()

    # 1. Проверяем, что пользователь вообще хоть что-то ввел
    if args.d is None and args.d1 is None and args.d2 is None:
        p.error("Необходимо указать диаметры: либо '-d', либо оба '-d1' и '-d2'")

    # 2. Проверяем конфликт: нельзя вводить одиночный -d вместе с парами
    if args.d is not None and (args.d1 is not None or args.d2 is not None):
        p.error("Нельзя использовать аргумент -d одновременно с -d1 или -d2")

    # 3. Проверяем полноту пары: если ввели d1, то d2 обязан быть, и наоборот
    if (args.d1 is not None and args.d2 is None) or (args.d2 is not None and args.d1 is None):
        p.error("Аргументы -d1 и -d2 должны указываться ТОЛЬКО вместе")

    is_pads_equal = False
    
    if args.d is not None:
        d1 = args.d
        d2 = args.d
        print(f"d1 = {d1}, d2={d2}")
        is_pads_equal = True
    else:
        d1, d2 = args.d1, args.d2
        if d1 <= 0 or d2 <= 0:
            p.error("Диаметры должны быть положительными.")
        if d1 > d2:
            d1, d2 = d2, d1
            print("⚠️  d1 > d2 — поменял местами: пад 1 всегда малый.")
        if abs(d1 - d2) < _EPS:
            is_pads_equal = True
        else:
            is_pads_equal = False

    # ── Горло по току: IPC-минимум × запас ────────────────────────────
    neck_ipc = round(ipc_calc.ipc_neck_width_mm(
        args.current, args.temp_rise, args.copper), 3)
    neck = args.neck if args.neck is not None else round(
        neck_ipc * args.neck_safety, 3)

    # ── Зазор по напряжению ───────────────────────────────────────────
    if args.gap is not None:
        gap = args.gap
    else:
        gap = max(ipc_calc.ipc_clearance_mm(args.voltage) * args.safety,
                  args.min_gap)
    gap = round(gap, 3)

    warnings = []
    if is_pads_equal:
        if neck > d1 or neck > d2:
            warnings.append(
            f"горло {neck:.3f} мм шире пада d={d1:.2f} мм — "
            f"контур расширен шапкой; проверь ширину подходящей дорожки")
    else:
        if neck > d1:
            warnings.append(
                f"горло {neck:.3f} мм шире малого пада d1={d1:.2f} мм — "
                f"контур расширен шапкой; проверь ширину подходящей дорожки")
        if  neck >= d2:
            print(f"❌ Горло {neck:.3f} мм ≥ d2={d2:.2f} мм. Увеличьте d2, "
                f"уменьшите ток или запас -k.", file=sys.stderr)
            return 1

    L = d1 + d2 + gap
    mount = args.type
    drill1 = args.drill1 if args.drill1 is not None else d1 / 2.0
    drill2 = args.drill2 if args.drill2 is not None else d2 / 2.0

    name = f"NetTie-2_{mount.upper()}_D1-{d1:.2f}_D2-{d2:.2f}_L-{L:.2f}mm"
    if args.tented:
        name += "_Tented"
    fname = name + ".kicad_mod"

    # ── Геометрия и рендер ────────────────────────────────────────────
    r1, r2 = d1 / 2.0, d2 / 2.0
    C = r1 + gap + r2 # center_dist

    if is_pads_equal:
        # для равных радиусов используем симметричный мостик
        poly = geometry.equal_radii_contour(r1, C, neck, args.points)
    else:
        poly = geometry.teardrop_polygon(r1, r2, r1 + gap + r2, neck, args.points)

    content = template.render_footprint(
        name, d1, d2, gap, neck, mount, drill1, drill2, poly,
        tented=args.tented, courtyard=not args.no_courtyard,
        courtyard_margin=args.courtyard_margin)

    args.outdir.mkdir(parents=True, exist_ok=True)
    out = args.outdir / fname
    out.write_text(content, encoding="utf-8")

    # ── Сводка ────────────────────────────────────────────────────────
    i_cont = ipc_calc.ipc_current_a(neck, args.temp_rise, args.copper)
    fuse = lambda t: ipc_calc.onderdonk_fusing_a(neck, args.copper, t)
    print("🔥 Смузи-парабола готова для KiCad 10!")
    print("=" * 50)
    print(f"📦 Имя файла:    {fname}")
    print(f"🔧 Тип монтажа:  {mount.upper()}")
    print(f"📏 Физическая L: {L:.2f} мм")
    print(f"⚡ Узкое горло:  {neck:.3f} мм "
          f"(IPC-минимум {neck_ipc:.3f} × {args.neck_safety:g})")
    print(f"🌡  Непрерывно:   {i_cont:.1f} А при ΔT={args.temp_rise:g}°C")
    print(f"💥 Плавление:    {fuse(1.0):.0f} А/1с, {fuse(0.01):.0f} А/10мс, "
          f"{fuse(1e-4):.0f} А/100мкс")
    print(f"↔️  Зазор пад-пад: {gap:.3f} мм (IPC-2221B ×{args.safety})")
    print(f"🎭 Маска:        {'закрыта (tented)' if args.tented else 'открытые пады'}")
    if mount == "tht":
        print(f"🕳  Сверловка:    {drill1:.2f} / {drill2:.2f} мм")
    for w in warnings:
        print(f"⚠️  {w}")
    print("=" * 50)
    print(f"💾 {out.resolve()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
