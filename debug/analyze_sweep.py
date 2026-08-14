"""Анализ данных режима --sweep: управляет ли смещение точки касания углом вылета.

Читает CSV сессии со свипом (колонка commanded_offset), находит отскоки от тележки и по
каждому меряет исходящий наклон vx/│vy│. Группирует по КОМАНДНОМУ смещению и считает связь.

    python debug/analyze_sweep.py debug/sweep.csv

Вывод: если наклон монотонно растёт со смещением (−40→влево … +40→вправо) и корреляция
заметная (|r|>0.4) — руление углом РАБОТАЕТ, можно калибровать и строить прицел. Если плоско
(|r|<0.2) — смещение тележки не управляет углом в этой игре.
"""

from __future__ import annotations

import csv
import statistics
import sys
from collections import defaultdict


def _f(v):
    return float(v) if v not in ("", None) else None


def main(path: str) -> int:
    rows = list(csv.DictReader(open(path, encoding="utf-8")))
    if "commanded_offset" not in (rows[0].keys() if rows else {}):
        print("В CSV нет колонки commanded_offset — это лог не из режима --sweep.")
        return 1

    # present-boot точки с командным смещением
    pts = []  # (frame, x, y, cart_x, commanded)
    for r in rows:
        x, y, cx = _f(r["boot_x"]), _f(r["boot_y"]), _f(r["cart_x"])
        if x is not None and y is not None and cx is not None:
            co = r.get("commanded_offset", "")
            co = int(co) if co not in ("", None) else None
            pts.append((int(r["frame"]), x, y, cx, co))

    def contig(i, a, b):
        return all(pts[k + 1][0] - pts[k][0] == 1 for k in range(i + a, i + b))

    W = 5
    events = []  # (commanded, actual_offset, out_slope)
    for i in range(W + 2, len(pts) - (W + 2)):
        f, x, y, cx, co = pts[i]
        if y < 842 or co is None:  # истинное касание тележки, известно смещение
            continue
        if not (y >= pts[i - 1][2] and y > pts[i + 1][2]):
            continue
        if not (contig(i, -W, -1) and contig(i, 1, W)):
            continue
        vy_in = (pts[i - 2][2] - pts[i - W][2]) / (W - 2)
        vx_in = (pts[i - 2][1] - pts[i - W][1]) / (W - 2)
        vy_out = (pts[i + W][2] - pts[i + 2][2]) / (W - 2)
        vx_out = (pts[i + W][1] - pts[i + 2][1]) / (W - 2)
        if vy_in <= 1 or vy_out >= -1:
            continue
        actual = (x + vx_in * (30 / vy_in)) - cx
        out_slope = vx_out / (-vy_out)
        if abs(out_slope) > 4:
            continue
        events.append((co, actual, out_slope))

    print(f"отскоков с известным смещением: {len(events)}\n")
    if len(events) < 20:
        print("Мало данных — поиграй в --sweep подольше.")
        return 0

    print("командное | n | медиана наклона вылета | среднее фактич. смещение")
    by_cmd = defaultdict(list)
    for co, act, sl in events:
        by_cmd[co].append((act, sl))
    for co in sorted(by_cmd):
        v = by_cmd[co]
        sl = [s for _, s in v]
        act = [a for a, _ in v]
        print(f"  {co:+4d}   | {len(v):3d} | {statistics.median(sl):+.2f}"
              f"                | {statistics.mean(act):+.0f} px")

    def corr(a, b):
        ma, mb = sum(a) / len(a), sum(b) / len(b)
        num = sum((x - ma) * (y - mb) for x, y in zip(a, b))
        da = (sum((x - ma) ** 2 for x in a)) ** 0.5
        db = (sum((y - mb) ** 2 for y in b)) ** 0.5
        return num / (da * db) if da and db else 0.0

    cmd = [e[0] for e in events]
    act = [e[1] for e in events]
    out = [e[2] for e in events]
    rc = corr(out, cmd)
    ra = corr(out, act)
    print(f"\ncorr(наклон, командное смещение) = {rc:+.2f}")
    print(f"corr(наклон, фактическое смещение) = {ra:+.2f}")
    verdict = ("РУЛЕНИЕ РАБОТАЕТ ✅ — можно калибровать и строить прицел"
               if abs(rc) > 0.4 or abs(ra) > 0.4
               else "смещение НЕ управляет углом ❌ — прицел через тележку не выйдет")
    print(f"ВЕРДИКТ: {verdict}")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Использование: python debug/analyze_sweep.py <sweep.csv>")
        raise SystemExit(2)
    raise SystemExit(main(sys.argv[1]))
