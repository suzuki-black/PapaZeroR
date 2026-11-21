#!/usr/bin/env python3
"""映像の場面で「見せたいもの」をスプライトで描くための絵と表(src/engine/op.c が読む)。

64×40 のブロックの 3D では、遠い機体は数ブロックの点に、近い機体は輪郭の分からない塊になった。そこで場面ごとに、
見せたいもの(主役)だけを 2 色の拡大スプライトで描く。台本(Film)はカメラも役者も時刻だけで決まるので、
どの時刻にどの向き・どの大きさで映るかは前もって全部分かる。ここでその絵(3D モデルを向きごとに描いたもの)と、
時刻 → 絵の表を作り、op.c は表を引いて置くだけにする(実行時に向きの計算をしない)。

  大きさ: 'B' = 2×2 枚(32×32 → 画面で 64×64 ドット = 16 ブロック)、'N' = 1 枚(16 ブロックの半分)、'M'・'S' = 1 枚の中に縮めた絵
  色: 1 枚目 c1(輪郭と暗い所)、2 枚目 c2(明るい所)。同じ画素に 2 枚が重ならないように分ける
  絵の置き場: スプライトのパターン 17〜62(46 枚。0〜16 はゲームの照準・札で使う)。場面の始めに op.c が送り込む
"""
import math
from PIL import Image, ImageDraw

SLOT0, SLOTS = 17, 46
SIZES = {'B': (32, 1.0), 'N': (16, 1.0), 'M': (16, .68), 'S': (16, .45)}
BLOCKS = {'B': 16, 'N': 8, 'M': 8 * .68, 'S': 8 * .45}     # 画面での大きさ(ブロック)


def rot_y(a):
    c, s = math.cos(a), math.sin(a)
    return [[c, 0, s], [0, 1, 0], [-s, 0, c]]      # 列 0 = (c, 0, -s)、列 2 = (s, 0, c)


def rot_x(a):
    c, s = math.cos(a), math.sin(a)
    return [[1, 0, 0], [0, c, -s], [0, s, c]]


def rot_z(a):
    c, s = math.cos(a), math.sin(a)
    return [[c, -s, 0], [s, c, 0], [0, 0, 1]]


def mul(a, b):
    return [[sum(a[i][k] * b[k][j] for k in range(3)) for j in range(3)] for i in range(3)]


def mv(m, v):
    return [sum(m[i][k] * v[k] for k in range(3)) for i in range(3)]


def tr(m):
    return [[m[j][i] for j in range(3)] for i in range(3)]


def ang(a):
    return a * 2 * math.pi / 256


def cam_matrix(yaw, pitch, roll):
    """view.c の cam_update と同じ(行 = 右・上・前)"""
    sy, cy = math.sin(ang(yaw)), math.cos(ang(yaw))
    sp, cp = math.sin(ang(pitch)), math.cos(ang(pitch))
    sr, cr = math.sin(ang(roll)), math.cos(ang(roll))
    r, u, f = [cy, 0, -sy], [0, 1, 0], [sy, 0, cy]
    u, f = [u[i] * cp - f[i] * sp for i in range(3)], [u[i] * sp + f[i] * cp for i in range(3)]
    r, u = [r[i] * cr - u[i] * sr for i in range(3)], [u[i] * cr + r[i] * sr for i in range(3)]
    return [r, u, f]


def actor_matrix(yaw, roll):
    """物体のローカル → 世界(view.c の mat_yaw: ヨーのあと、ローカルの x を y の側へロール)"""
    m = rot_y(ang(yaw))
    sr, cr = math.sin(ang(roll)), math.cos(ang(roll))
    c0 = [m[i][0] for i in range(3)]
    c1 = [m[i][1] for i in range(3)]
    n0 = [c0[i] * cr + c1[i] * sr for i in range(3)]
    n1 = [c1[i] * cr - c0[i] * sr for i in range(3)]
    return [[n0[i], n1[i], m[i][2]] for i in range(3)]


def key_at(keys, t, angles):
    """op.c の key_at と同じ補間(角度は u8 の差を i8 で)。keys = (t, p, a, b, c, fl)。angles = 補間する角度の数"""
    i = 0
    while i + 1 < len(keys) and keys[i + 1][0] <= t:
        i += 1
    k = keys[i]
    if i + 1 >= len(keys) or t <= k[0] or k[5] & 16:
        return k
    n = keys[i + 1]
    f = (t - k[0]) / (n[0] - k[0])
    if k[5] & 1:
        f = f * f * (3 - 2 * f)
    p = tuple(k[1][j] + (n[1][j] - k[1][j]) * f for j in range(3))
    a = list(k[2:5])
    for j in range(angles):
        d = (n[2 + j] - k[2 + j]) & 255
        d = d - 256 if d >= 128 else d
        a[j] = (k[2 + j] + d * f) % 256
    return (t, p, a[0], a[1], a[2], k[5])


def render(mesh, m, n, k, light):
    """mesh を行列 m(ローカル → 見る向き: x 右、y 上、z 奥)で n×n に描く。半径が絵の半分 × k に収まる縮尺。
    戻り値は画素ごとの 0(空)/ 1(c1)/ 2(c2)"""
    R = max(math.sqrt(x * x + y * y + z * z) for x, y, z in mesh.v)
    over = 8
    N = n * over
    sc = N / 2 * k / R
    pts = [mv(m, v) for v in mesh.v]
    img = Image.new('L', (N, N), 0)
    dr = ImageDraw.Draw(img)
    order = sorted(mesh.f, key=lambda f: -sum(pts[i][2] for i in f[0]) / len(f[0]))
    for idx, col, det in order:
        pp = [(N / 2 + pts[i][0] * sc, N / 2 - pts[i][1] * sc) for i in idx]
        area = sum(pp[i][0] * pp[(i + 1) % len(pp)][1] - pp[(i + 1) % len(pp)][0] * pp[i][1] for i in range(len(pp)))
        if area <= 0:            # 裏向き(meshlib.py の lod2 と同じ判定)
            continue
        dr.polygon(pp, fill=col)
    px = img.load()
    out = [[0] * n for _ in range(n)]
    for y in range(n):
        for x in range(n):
            cells = [px[x * over + i, y * over + j] for j in range(over) for i in range(over)]
            filled = [c for c in cells if c]
            if len(filled) * 3 >= len(cells):         # 細い翼が消えないよう、3 分の 1 埋まっていれば塗る
                best = max(set(filled), key=filled.count)
                out[y][x] = 2 if best in light else 1
    if n >= 16 and k >= .9:
        # 輪郭: 外に接する画素は c1(暗い色)にして、空に溶けないようにする
        o2 = [row[:] for row in out]
        for y in range(n):
            for x in range(n):
                if out[y][x] == 2:
                    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                        xx, yy = x + dx, y + dy
                        if not (0 <= xx < n and 0 <= yy < n) or out[yy][xx] == 0:
                            o2[y][x] = 1
                            break
        out = o2
    return out


def pattern_bytes(rows, ch):
    """16×16 の 1 枚(左上・左下・右上・右下の 8×8 の順。tools/gen_data.py の sprite_bytes と同じ)"""
    b = []
    for x0 in (0, 8):
        for y in range(16):
            v = 0
            for x in range(8):
                if rows[y][x0 + x] == ch:
                    v |= 0x80 >> x
            b.append(v)
    return b


def decompose(m):
    """見る向きの行列 → (ヨー, ピッチ, ロール)(m = Ry Rx Rz)"""
    fx, fy, fz = m[0][2], m[1][2], m[2][2]
    yaw = math.atan2(fx, fz)
    pitch = math.atan2(-fy, math.hypot(fx, fz))
    r0 = mul(rot_y(yaw), rot_x(pitch))
    rz = mul(tr(r0), m)
    roll = math.atan2(rz[1][0], rz[0][0])
    return yaw, pitch, roll


def fix_tilt(m, least=math.radians(25)):
    """平らな翼は同じ高さから見ると線になって消える(後ろから見た戦闘機が縦の棒になった)。
    物体の上の面か下の面が、少なくとも least だけカメラに向くよう、見る向きを上下に傾ける(画面の x 軸まわり)"""
    u = [m[0][1], m[1][1], m[2][1]]            # 物体の上(見る向きの座標)。カメラは +z を見るので、-u.z > 0 なら上の面が見える
    t = -u[2]
    want = math.sin(least)
    if abs(t) >= want:
        return m
    s = 1 if t >= 0 else -1
    best = None
    for d in range(-80, 81):
        ph = math.radians(d)
        if -(u[1] * math.sin(ph) + u[2] * math.cos(ph)) * s >= want and (best is None or abs(d) < abs(best)):
            best = d
    return mul(rot_x(math.radians(best)), m) if best is not None else m


class Subject:
    """見せたいもの: 役者 a、メッシュ mesh、2 色(c1 = 暗い所と輪郭、c2 = light に入るメッシュの色の所)"""
    def __init__(self, a, mesh, c1, c2, light, big=True):
        self.a, self.mesh, self.c1, self.c2, self.light, self.big = a, mesh, c1, c2, set(light), big


def plan(film, subjects, meshes, end):
    """主役ごとに、時刻 → (大きさ, その時刻の向きで描いた絵) の並び(2 ティックごと)"""
    cam = film.cam
    out = []
    for s in subjects:
        keys = film.acts[s.a]
        mesh = meshes[s.mesh]
        R = max(math.sqrt(x * x + y * y + z * z) for x, y, z in mesh.v)
        seq = []
        for t in range(0, end, 2):
            k = key_at(keys, t, 2)
            if k[4] != s.mesh:
                seq.append((t, None))
                continue
            c = key_at(cam, t, 3)
            cm = cam_matrix(c[2], c[3], c[4])
            d = [k[1][j] - c[1][j] for j in range(3)]
            P = mv(cm, d)
            if P[2] < 1:
                seq.append((t, None))
                continue
            sx, sy = 32 + 32 * P[0] / P[2], 20 - 32 * P[1] / P[2]
            if not (-12 < sx < 76 and -12 < sy < 52):
                seq.append((t, None))
                continue
            # 視線の向きにそろえた枠(z = 物体への向き)で見た物体の向き
            L = math.sqrt(sum(v * v for v in P))
            z = [v / L for v in P]
            x = [z[2], 0, -z[0]]
            lx = math.hypot(x[0], x[2])
            x = [x[0] / lx, 0, x[2] / lx]
            y = [z[1] * x[2] - z[2] * x[1], z[2] * x[0] - z[0] * x[2], z[0] * x[1] - z[1] * x[0]]
            m = fix_tilt(mul([x, y, z], mul(cm, actor_matrix(k[2], k[3]))))
            D = 64 * R / P[2]                      # 画面での直径(ブロック)
            size = min((sz for sz in BLOCKS if s.big or sz != 'B'), key=lambda sz: abs(math.log(BLOCKS[sz] / D)))
            n, kk = SIZES[size]
            seq.append((t, (size, render(mesh, m, n, kk, s.light), m)))
        out.append(seq)
    return out


def differ(a, b):
    """2 枚の絵の違い(違う画素 / どちらかが塗られた画素)"""
    d = u = 0
    for ra, rb in zip(a, b):
        for x, y in zip(ra, rb):
            if x or y:
                u += 1
                d += x != y
    return d / max(1, u)


def build(film, subjects, meshes, end):
    """絵(パターンのバイト列)と表を作る。主役ごとに、同じ大きさで続く時間を区間に分け、隣り合う区間のうち絵がいちばん
    似ている 2 つを 1 つにまとめていき、46 枚に収まったら止める(区間の絵は、区間の真ん中の時刻の絵)"""
    seqs = plan(film, subjects, meshes, end)
    segs = []                                      # [主役, 大きさ, [(t, 絵)...]]。見えない所は None で区切る
    for si, seq in enumerate(seqs):
        for t, v in seq:
            if v is None:
                if segs and segs[-1] is not None:
                    segs.append(None)
                continue
            size, pix, m = v
            last = segs[-1] if segs else None
            if last is not None and last[0] == si and last[1] == size and last[2][-1][1] == pix:
                last[2].append((t, pix, m))
            else:
                segs.append([si, size, [(t, pix, m)]])
        segs.append(None)
    rep = lambda g: g[2][len(g[2]) // 2][1]
    cost = lambda g: 8 if g[1] == 'B' else 2
    while sum(cost(g) for g in segs if g) > SLOTS:
        best = None
        for k in range(len(segs) - 1):
            a, b = segs[k], segs[k + 1]
            if a and b and a[0] == b[0] and a[1] == b[1]:
                d = differ(rep(a), rep(b)) * (len(a[2]) + len(b[2])) ** .5
                if best is None or d < best[0]:
                    best = (d, k)
        if best is None:
            # 大きさの違う区間しか残っていない: 大きい絵(B)を 1 つ下の大きさ(N)に落として数を減らす
            big = [g for g in segs if g and g[1] == 'B']
            if not big:
                raise SystemExit('film_spr: スプライトの絵が %d 枚に収まらない' % SLOTS)
            g = min(big, key=lambda g: len(g[2]))
            s0 = subjects[g[0]]
            n, kk = SIZES['N']
            px = render(meshes[s0.mesh], g[2][len(g[2]) // 2][2], n, kk, s0.light)
            g[1] = 'N'
            g[2] = [(t, px, m) for t, _, m in g[2]]
            continue
        k = best[1]
        segs[k][2] += segs[k + 1][2]
        del segs[k + 1]
    arts, pick = [], [[] for _ in subjects]
    for g in segs:
        if g is None:
            continue
        arts.append((g[0], g[1], rep(g)))
        for t, px, m in g[2]:
            pick[g[0]].append((t, len(arts) - 1))
    for si, seq in enumerate(seqs):               # 見えない時刻を入れて、時刻の順に並べる
        shown = dict(pick[si])
        pick[si] = [(t, shown.get(t)) for t, v in seq]
    tol = len(arts)
    pats, slot, place, pics = [], SLOT0, [], {}
    for ai, (si, size, pix) in enumerate(arts):
        pics[(si, size, ai)] = pix
        rows = [''.join('#' if v == 1 else 'o' if v == 2 else '.' for v in r) for r in pix]
        if size == 'B':
            quads = [[r[x0:x0 + 16] for r in rows[y0:y0 + 16]] for y0, x0 in ((0, 0), (0, 16), (16, 0), (16, 16))]
            for ch in '#o':
                for qd in quads:
                    pats += pattern_bytes(qd, ch)
            place.append((slot, 2))
            slot += 8
        else:
            pats += pattern_bytes(rows, '#') + pattern_bytes(rows, 'o')
            place.append((slot, 1))
            slot += 2
    # 表: 主役ごとに (時刻, 絵の番号, 種類 0 = 出さない / 1 = 1 枚 / 2 = 2×2)。変わる所だけ
    ents, heads = [], []
    for row in pick:
        first = len(ents)
        last = None
        for t, ai in row:
            e = place[ai] if ai is not None else (0, 0)
            if e != last:
                ents.append((t, e[0], e[1]))
                last = e
        heads.append((first, len(ents) - first))
    return pats, ents, heads, pics, tol


def header(film, subjects, meshes, end):
    pats, ents, heads, pics, q = build(film, subjects, meshes, end)
    out = ['#define N_SPRPAT %d' % (len(pats) // 32)]
    out.append('static const u8 spr_pat[] = {' + ','.join(map(str, pats)) + '};')
    out.append('#define N_SUBJ %d' % len(subjects))
    out.append('static const SprSub spr_sub[] = {' + ','.join('{%d,%d,%d,%d,%d}' % (s.a, s.c1, s.c2, h[0], h[1]) for s, h in zip(subjects, heads)) + '};')
    out.append('static const SprEnt spr_ent[] = {' + ','.join('{%d,%d,%d}' % e for e in ents) + '};')
    sub_of = [0xFF] * len(film.acts)
    for i, s in enumerate(subjects):
        sub_of[s.a] = i
    out.append('static const u8 spr_sub_of[] = {' + ','.join(map(str, sub_of)) + '};')
    return '\n'.join(out) + '\n', pics, q


def preview(pics, path, scale=4):
    """絵を並べて PNG にする(確かめる用)。c1 = 黒、c2 = 白、空 = 水色"""
    items = list(pics.items())
    W = 32 * scale + 8
    img = Image.new('RGB', (W * min(8, len(items)), W * ((len(items) + 7) // 8)), (40, 40, 40))
    for i, (key, pix) in enumerate(items):
        n = len(pix)
        for y in range(n):
            for x in range(n):
                c = {0: (120, 180, 255), 1: (0, 0, 0), 2: (240, 240, 240)}[pix[y][x]]
                x0 = (i % 8) * W + x * scale * (32 // n)
                y0 = (i // 8) * W + y * scale * (32 // n)
                for yy in range(scale * (32 // n)):
                    for xx in range(scale * (32 // n)):
                        img.putpixel((x0 + xx, y0 + yy), c)
    img.save(path)
