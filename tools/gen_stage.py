#!/usr/bin/env python3
"""モジュール(経路・区画・台本・モデル)のバイナリを作る(指示書 10.5 / 10.6)。

  gen_stage.py <出力ディレクトリ>   → modN.bin(16KB、N = 0〜7)と ids.h
stage_data.py がモジュールの中身を定義する。
"""
import math
import os
import struct
import sys
import content
from content import M
import stage_data
from stage_data import MODS

BASE = 0x8000
LIMIT = 0x4000
DATA_LIMIT = 0x2400   # 0xA400- は全モジュール共通のコード(game_ai.c)


def main(out):
    names = sorted(M)
    ids = {n: i + 1 for i, n in enumerate(names)}
    with open(os.path.join(out, 'ids.h'), 'w') as f:
        f.write('/* tools/gen_stage.py が生成 */\n')
        for n in names:
            f.write('#define M_%s %d\n' % (n, ids[n]))
        f.write('#define M_COUNT %d\n' % (len(names) + 1))
    for mod in MODS:
        build(mod, ids, len(names) + 1, out)


class Blob:
    def __init__(self):
        self.b = bytearray()
    def at(self):
        return BASE + len(self.b)
    def add(self, data):
        a = self.at()
        self.b += data
        return a


def mesh_bytes(blob, m, cache):
    vb, fb, sh, r, nv0 = m.encode()
    nr, rects = m.lod2()
    key = (bytes(vb), bytes(fb), sh)
    if key in cache:
        return cache[key]
    ra = blob.add(bytes(rects)) if nr else 0
    a = blob.add(bytes([len(m.v), len(m.f), sh, r, nr]) + struct.pack('<H', ra) + bytes([nv0]) + vb + fb)
    cache[key] = a
    return a


HDR = 2 * 6 + 2 + 2 + 2 + 2 + 2 + 2 + 2 + 4 + 4


def build(mod, ids, nids, out):
    b = Blob()
    b.add(bytes(HDR))
    cache = {}
    pal = b.add(mod.pal)
    pal2 = b.add(mod.pal2)
    # モデル
    tab = [0] * nids
    for n in mod.models:
        tab[ids[n]] = mesh_bytes(b, M[n], cache)
    meshes = b.add(struct.pack('<%dH' % nids, *tab))
    # 区画
    secs = bytearray()
    for s in mod.sections:
        ma = mesh_bytes(b, s['mesh'], cache) if s['mesh'] else 0
        secs += struct.pack('<HhhhBB', ma, s['x'], s['y'], s['z'], s['spd'], s['yaw'])
    sa = b.add(secs)
    # 経路
    pts = bytearray()
    for p in mod.path:
        pts += struct.pack('<hhhBb', p[0], p[1], p[2], p[3], p[4])
    pa = b.add(pts)
    # 字幕
    strs = []
    for s in mod.strs:
        strs.append(b.add(s.encode('ascii') + b'\0'))
    st = b.add(struct.pack('<%dH' % len(strs), *strs) if strs else b'\0\0')
    name = b.add(mod.name.encode('ascii') + b'\0')
    # ボス
    ba = 0
    if mod.boss:
        d = bytearray([mod.boss['mov'], mod.boss['dist'], len(mod.boss['parts'])])
        for p in mod.boss['parts']:
            d += bytes([ids[p[0]]] + [x & 255 for x in p[1:]])
        ba = b.add(d)
    # 台本
    ev = bytearray()
    for e in sorted(mod.events, key=lambda e: e[0]):
        at, cmd, a0, a1, a2, x, y, z = e
        if isinstance(a0, str):
            a0 = ids[a0]
        ev += struct.pack('<HBBBBhhh', at, cmd, a0 & 255, a1 & 255, a2 & 255, x, y, z)
    ea = b.add(ev)
    hdr = struct.pack('<HHHHHHHHHHHBBBBH', pa, len(mod.path), sa, len(mod.sections), ea, len(mod.events), pal, meshes, st, ba, name,
                      mod.bgm, mod.flags, mod.clock, 0, pal2)
    b.b[:len(hdr)] = hdr
    if len(b.b) > DATA_LIMIT:
        sys.exit('gen_stage: モジュール %s が %d バイトで %d を超えた' % (mod.name, len(b.b), DATA_LIMIT))
    with open(os.path.join(out, 'mod%d.bin' % mod.n), 'wb') as f:
        f.write(b.b + bytes(LIMIT - len(b.b)))
    print('gen_stage: mod%d %-24s %5d B  区画 %d 経路 %d 命令 %d メッシュ %d' % (mod.n, mod.name, len(b.b), len(mod.sections), len(mod.path), len(mod.events), len(cache)))


if __name__ == '__main__':
    main(sys.argv[1])
