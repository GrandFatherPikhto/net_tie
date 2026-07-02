# -*- coding: utf-8 -*-

import sys
from pathlib import Path
from types import SimpleNamespace

try:
    import utils.ipc_calc as ipc_calc
except ImportError as e:
    print(f"❌ Не найден модуль: {e.name}.py — он должен лежать рядом с CLI.",
          file=sys.stderr)
    sys.exit(1)

def fill_args(p):
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

def prepare_nettie_args(args):
    """
    Разбирает аргументы командной строки, вычисляет все необходимые параметры
    и возвращает SimpleNamespace с ними.
    """
    # Маленький эпсилон для сравнения
    _EPS = 1e-9


    # Проверка наличия диаметров
    if args.d is None and args.d1 is None and args.d2 is None:
        raise ValueError("Необходимо указать диаметры: либо '-d', либо оба '-d1' и '-d2'")
    if args.d is not None and (args.d1 is not None or args.d2 is not None):
        raise ValueError("Нельзя использовать -d одновременно с -d1 или -d2")
    if (args.d1 is not None and args.d2 is None) or (args.d2 is not None and args.d1 is None):
        raise ValueError("-d1 и -d2 должны указываться ТОЛЬКО вместе")

    # Определяем d1, d2 и флаг равенства
    if args.d is not None:
        d1 = args.d
        d2 = args.d
        is_pads_equal = True
    else:
        d1, d2 = args.d1, args.d2
        if d1 <= 0 or d2 <= 0:
            raise ValueError("Диаметры должны быть положительными.")
        if d1 > d2:
            d1, d2 = d2, d1
            print("⚠️  d1 > d2 — поменял местами: пад 1 всегда малый.")
        is_pads_equal = abs(d1 - d2) < _EPS

    # Горло по току
    neck_ipc = round(ipc_calc.ipc_neck_width_mm(
        args.current, args.temp_rise, args.copper), 3)
    # Если диаметры равны и neck не задан вручную, приравниваем neck к диаметру
    if is_pads_equal and args.neck is None:
        neck = d1
    else:        
        neck = args.neck if args.neck is not None else round(
            neck_ipc * args.neck_safety, 3)

    # Зазор
    if args.gap is not None:
        gap = args.gap
    else:
        gap = max(ipc_calc.ipc_clearance_mm(args.voltage) * args.safety,
                  args.min_gap)
    gap = round(gap, 3)

    # Предупреждения
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
        if neck >= d2:
            raise ValueError(
                f"Горло {neck:.3f} мм ≥ d2={d2:.2f} мм. Увеличьте d2, "
                f"уменьшите ток или запас -k.")

    L = d1 + d2 + gap
    mount = args.type
    drill1 = args.drill1 if args.drill1 is not None else d1 / 2.0
    drill2 = args.drill2 if args.drill2 is not None else d2 / 2.0

    name = f"NetTie-2_{mount.upper()}_D1-{d1:.2f}_D2-{d2:.2f}_L-{L:.2f}mm"
    if args.tented:
        name += "_Tented"
    fname = name + ".kicad_mod"

    r1, r2 = d1 / 2.0, d2 / 2.0
    C = r1 + gap + r2

    return SimpleNamespace(
        d1=d1, d2=d2,
        is_pads_equal=is_pads_equal,
        gap=gap,
        neck=neck,
        neck_ipc=neck_ipc,
        warnings=warnings,
        L=L,
        mount=mount,
        drill1=drill1,
        drill2=drill2,
        name=name,
        fname=fname,
        r1=r1, r2=r2,
        C=C,
    )