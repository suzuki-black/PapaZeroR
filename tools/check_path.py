#!/usr/bin/env python3
"""経路が地形(区画のメッシュ)を突き抜ける所を探す。

  check_path.py [モジュール番号 ...]

経路は決まっていて避けられないので、建物や壁を突き抜けると「ぶつかると思ったのにすり抜けた」に見える。
2 単位ごとの経路の線分が、近くの区画の面(地面を除く)を横切る所を、経路の位置(単位)で出す。
"""
import math
import sys
sys.path.insert(0, __file__.rsplit('/', 1)[0])
from stage_data import MODS, LAP


def sub(a, b): return (a[0] - b[0], a[1] - b[1], a[2] - b[2])
def dot(a, b): return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]
def cross(a, b): return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def world_faces(mod, k, mesh):
    p = mod._p[k * 4]
    ox, oz, yaw = p[0], p[2], p[3]
    c, s = math.cos(yaw), math.sin(yaw)
    out = []
    for idx, color, detail in mesh.f:
        pts = []
        for i in idx:
            lx, ly, lz = mesh.v[i]
            pts.append((ox + lx * c + lz * s, mod.sec_y + ly, oz - lx * s + lz * c))
        if all(abs(q[1] - mod.sec_y) < 1e-6 for q in pts):
            continue                                  # 地面
        out.append(pts)
    return out


def crosses(a, b, poly):
    n = cross(sub(poly[1], poly[0]), sub(poly[2], poly[0]))
    da, db = dot(n, sub(a, poly[0])), dot(n, sub(b, poly[0]))
    if da * db > 0 or da == db:
        return False
    t = da / (da - db)
    q = (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t)
    sign = 0
    for i in range(len(poly)):
        e = sub(poly[(i + 1) % len(poly)], poly[i])
        s = dot(cross(e, sub(q, poly[i])), n)
        if s != 0:
            if sign and (s > 0) != (sign > 0):
                return False
            sign = s
    return True


def check(mod):
    hits = []
    secs = mod.sections
    cache = {}
    for i in range(len(mod._p) - 1):
        a, b = mod._p[i][:3], mod._p[i + 1][:3]
        ki = i // 4
        for k in range(max(0, ki - 3), min(len(secs), ki + 4)):
            m = secs[k]['mesh']
            if not m:
                continue
            if k not in cache:
                cache[k] = world_faces(mod, k, m)
            if any(crosses(a, b, f) for f in cache[k]):
                hits.append(i * 2)
                break
    # 続いている所をまとめる
    spans = []
    for h in hits:
        if spans and h - spans[-1][1] <= 2:
            spans[-1][1] = h
        else:
            spans.append([h, h])
    return spans


def main(args):
    want = set(int(a) for a in args)
    for mod in MODS:
        if (want and mod.n not in want) or not mod.sections or mod.film:
            continue
        spans = check(mod)
        print('mod%d %-28s %s' % (mod.n, mod.name, ' '.join('%d-%d' % (a, b) for a, b in spans) or 'なし'))


if __name__ == '__main__':
    main(sys.argv[1:])
