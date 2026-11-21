#!/usr/bin/env python3
"""メッシュの部品と、ROM に入れるバイト列(指示書 8.3 / 10.5)。

座標は x = 右、y = 上、z = 奥(前)。単位は 1 = 1 ゲーム単位(指示書の 1m)。
面の頂点は、外から見て時計回り(view.c の裏面の判定)。

バイト列: nv nf sh r nrect, dw rects, nv0, 頂点(i8 × 3 × nv), 面(hdr, color, v0, v1, v2, v3)
  sh   = 頂点の単位の右シフト(0 = 1/2、1 = 1/4、2 = 1/8、3 = 1/16)
  r    = 半径(切り上げ)
  rects = LOD 2 の矩形(x0, y0, x1, y1: 1/16、color, part)× nrect × 8 方向
"""
import math
from PIL import Image, ImageDraw

BLACK, WHITE, RED, ORANGE, GREEN, CYAN, PURPLE, IRON = 1, 2, 3, 4, 5, 6, 7, 8
SKY1, SKY2, GND1, GND2, TER1, TER2, CLOUD = 9, 10, 11, 12, 13, 14, 15


class Mesh:
    def __init__(self):
        self.v = []
        self.f = []      # (頂点番号の並び, 色, 細部か)

    def vert(self, p):
        p = tuple(round(c * 16) / 16 for c in p)
        if p in self.v:
            return self.v.index(p)
        self.v.append(p)
        return len(self.v) - 1

    def face(self, pts, color, detail=False, normal=None):
        """pts は外から見て時計回り。normal を渡すとその向きに合わせて並びを直す"""
        if normal is not None:
            a, b, c = pts[0], pts[1], pts[2]
            n = cross(sub(b, a), sub(c, a))
            if dot(n, normal) < 0:
                pts = pts[::-1]
        self.f.append(([self.vert(p) for p in pts], color, detail))
        return self

    def box(self, c, s, color, top=None, side=None, detail=False, skip=''):
        """c = 中心、s = (幅, 高さ, 奥行き)。top・side で面の色を変える。skip は省く面(b = 底、t = 上、f = 前、k = 後ろ)"""
        x, y, z = c
        w, h, d = s[0] / 2, s[1] / 2, s[2] / 2
        top = top or color
        side = side or color
        p = lambda sx, sy, sz: (x + sx * w, y + sy * h, z + sz * d)
        if 'b' not in skip:
            self.face([p(-1, -1, -1), p(1, -1, -1), p(1, -1, 1), p(-1, -1, 1)], side, detail, (0, -1, 0))
        if 'k' not in skip:
            self.face([p(-1, -1, 1), p(1, -1, 1), p(1, 1, 1), p(-1, 1, 1)], color, detail, (0, 0, 1))
        if 'f' not in skip:
            self.face([p(-1, -1, -1), p(-1, 1, -1), p(1, 1, -1), p(1, -1, -1)], color, detail, (0, 0, -1))
        self.face([p(-1, -1, -1), p(-1, -1, 1), p(-1, 1, 1), p(-1, 1, -1)], side, detail, (-1, 0, 0))
        self.face([p(1, -1, -1), p(1, 1, -1), p(1, 1, 1), p(1, -1, 1)], side, detail, (1, 0, 0))
        if 't' not in skip:
            self.face([p(-1, 1, -1), p(-1, 1, 1), p(1, 1, 1), p(1, 1, -1)], top, detail, (0, 1, 0))
        return self

    def tbox(self, c, s, color, top=None, side=None, detail=False, skip=''):
        """地形の箱: 前の面だけを残し、ほかは細部にする(遠い区画は前の面だけ描く)"""
        n0 = len(self.f)
        self.box(c, s, color, top, side, detail, skip)
        for i in range(n0, len(self.f)):
            idx, col, det = self.f[i]
            front = all(self.v[k][2] == c[2] - s[2] / 2 for k in idx)
            self.f[i] = (idx, col, det or not front)
        return self

    def prism_y(self, c, r, h, n, color, top=None, detail=False):
        """縦の n 角柱(中心 c、半径 r、高さ h)"""
        x, y, z = c
        ring = [(x + r * math.sin(2 * math.pi * i / n), z + r * math.cos(2 * math.pi * i / n)) for i in range(n)]
        for i in range(n):
            a, b = ring[i], ring[(i + 1) % n]
            mid = ((a[0] + b[0]) / 2 - x, 0, (a[1] + b[1]) / 2 - z)
            self.face([(a[0], y - h / 2, a[1]), (a[0], y + h / 2, a[1]), (b[0], y + h / 2, b[1]), (b[0], y - h / 2, b[1])], color, detail, mid)
        pts = [(p[0], y + h / 2, p[1]) for p in ring]
        self.face4fan(pts, top or color, (0, 1, 0), detail)
        return self

    def prism_z(self, c, r, l, n, color, cap=None, detail=False, sy=1.0):
        """前後の n 角柱(筒。中心 c、半径 r、長さ l)"""
        x, y, z = c
        ring = [(x + r * math.cos(2 * math.pi * i / n), y + sy * r * math.sin(2 * math.pi * i / n)) for i in range(n)]
        for i in range(n):
            a, b = ring[i], ring[(i + 1) % n]
            mid = ((a[0] + b[0]) / 2 - x, (a[1] + b[1]) / 2 - y, 0)
            self.face([(a[0], a[1], z - l / 2), (b[0], b[1], z - l / 2), (b[0], b[1], z + l / 2), (a[0], a[1], z + l / 2)], color, detail, mid)
        self.face4fan([(p[0], p[1], z - l / 2) for p in ring], cap or color, (0, 0, -1), detail)
        self.face4fan([(p[0], p[1], z + l / 2) for p in ring], cap or color, (0, 0, 1), detail)
        return self

    def face4fan(self, pts, color, normal, detail=False):
        """凸多角形を四角形の扇に切る"""
        n = len(pts)
        i = 0
        while i + 2 < n:
            if i + 3 < n:
                self.face([pts[0], pts[i + 1], pts[i + 2], pts[i + 3]], color, detail, normal)
                i += 2
            else:
                self.face([pts[0], pts[i + 1], pts[i + 2]], color, detail, normal)
                i += 1
        return self

    def tri(self, a, b, c, color, normal=None, detail=False):
        return self.face([a, b, c], color, detail, normal)

    def plate(self, pts, color, detail=False):
        """両面の板(翼・ロープなど)"""
        self.f.append(([self.vert(p) for p in pts], color, detail))
        self.f.append(([self.vert(p) for p in pts[::-1]], color, detail))
        return self

    def radius(self):
        return max(math.sqrt(x * x + y * y + z * z) for x, y, z in self.v)

    def lod2(self):
        """8 方向から描いて、矩形の集まりにする。半径が 7 単位を超えるものは作らない"""
        ext = max(max(abs(c) for c in p) for p in self.v)
        if ext > 7.5 or getattr(self, 'no_lod2', False):
            return 0, []
        N = 16
        scale = N / (2 * max(ext * 1.5, 0.25))
        out = []
        count = 0
        lists = []
        for d in range(8):
            a = 2 * math.pi * d / 8
            s, c = math.sin(a), math.cos(a)
            img = Image.new('L', (N, N), 0)
            dr = ImageDraw.Draw(img)
            def pv(p):
                u = p[0] * c - p[2] * s
                z = p[0] * s + p[2] * c
                return u, p[1], z
            order = sorted(self.f, key=lambda f: -sum(pv(self.v[i])[2] for i in f[0]) / len(f[0]))
            for idx, col, det in order:
                pts = [pv(self.v[i]) for i in idx]
                # 裏向きの面は描かない
                pp = [((u * scale + N / 2), (N / 2 - v * scale)) for u, v, _ in pts]
                area = sum(pp[i][0] * pp[(i + 1) % len(pp)][1] - pp[(i + 1) % len(pp)][0] * pp[i][1] for i in range(len(pp)))
                if area <= 0:
                    continue
                dr.polygon(pp, fill=col)
            lists.append(rects_of(img, scale))
        count = max(1, min(getattr(self, 'max_rects', 5), max(len(r) for r in lists)))   # 遠くで描く矩形の数(細いものは少なくてよい)
        for r in lists:
            r = r[:count]
            while len(r) < count:
                r.append((0, 0, 0, 0, BLACK, 3))
            for t in r:
                out += [t[0] & 255, t[1] & 255, t[2] & 255, t[3] & 255, t[4], t[5]]
        return count, out

    def encode(self):
        ext = max(max(abs(c) for c in p) for p in self.v)
        sh = 3
        lsb = 1 / 16
        while ext / lsb > 126 and sh > 0:
            sh -= 1
            lsb *= 2
        if ext / lsb > 127:
            raise SystemExit('meshlib: メッシュが大きすぎる (%.1f)' % ext)
        if len(self.v) > 120 or len(self.f) > 80:
            raise SystemExit('meshlib: 頂点 %d / 面 %d が多すぎる' % (len(self.v), len(self.f)))
        # 細部でない面が使う頂点を先に並べる(LOD 1 はそこまでしか変換しない)
        core = []
        for idx, col, det in self.f:
            if not det:
                for i in idx:
                    if i not in core:
                        core.append(i)
        rest = [i for i in range(len(self.v)) if i not in core]
        order = core + rest
        remap = {o: n for n, o in enumerate(order)}
        vb = bytearray()
        for o in order:
            p = self.v[o]
            for c in p:
                vb.append(int(round(c / lsb)) & 255)
        fb = bytearray()
        for idx, col, det in self.f:
            n = len(idx)
            vv = ([remap[i] for i in idx] + [0, 0, 0, 0])[:4]
            fb += bytes([n | (0x80 if det else 0), col] + vv)
        return vb, fb, sh, min(255, int(math.ceil(self.radius()))), len(core)


def rects_of(img, scale):
    """色ごとの塊を、面積の大きい順の矩形にする(画素を貪欲につなぐ)"""
    N = img.size[0]
    px = [[img.getpixel((x, y)) for x in range(N)] for y in range(N)]
    rects = []
    for _ in range(12):
        best = None
        for y in range(N):
            for x in range(N):
                c = px[y][x]
                if c == 0:
                    continue
                w = 1
                while x + w < N and px[y][x + w] == c:
                    w += 1
                for mw in range(1, w + 1):
                    h = 1
                    while y + h < N and all(px[y + h][x + i] == c for i in range(mw)):
                        h += 1
                    a = mw * h
                    if best is None or a > best[0]:
                        best = (a, x, y, mw, h, c)
        if best is None:
            break
        a, x, y, w, h, c = best
        for j in range(h):
            for i in range(w):
                px[y + j][x + i] = 0
        k = 16 / scale
        x0 = int(round((x - N / 2) * k))
        x1 = int(round((x + w - N / 2) * k))
        y1 = int(round((N / 2 - y) * k))
        y0 = int(round((N / 2 - y - h) * k))
        rects.append((a, (max(-127, x0), max(-127, y0), min(127, x1), min(127, y1), c, 0)))
    rects.sort(key=lambda r: -r[0])
    return [r[1] for r in rects]


def sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]
