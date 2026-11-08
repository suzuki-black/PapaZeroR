#!/usr/bin/env python3
"""PAPA ZERO の中身: モデル(敵・ボス・地形の部品)と 8 つのモジュールの定義(指示書 5〜7 章)。
gen_stage.py が読む。単位は 1 = 指示書の 1m(画面の大きさに合わせて縮めた世界)。"""
import math
from meshlib import *

# ---------------------------------------------------------------------------
# モデル
# ---------------------------------------------------------------------------
M = {}
def model(name):
    def deco(fn):
        M[name] = fn()
        return fn
    return deco

@model('BIKE')
def _():      # リベレーター: 箱 2 個 + 車輪
    m = Mesh()
    m.box((0, -.2, 0), (.5, .35, 1.8), ORANGE, top=IRON)
    m.box((0, .25, -.3), (.5, .6, .5), IRON, top=ORANGE)
    m.box((0, -.5, -.8), (.15, .5, .5), BLACK, detail=True)
    m.box((0, -.5, .8), (.15, .5, .5), BLACK, detail=True)
    m.box((.55, .1, .2), (.1, .1, 1.2), RED, detail=True)
    return m

def tank(muzzle):
    m = Mesh()
    m.box((0, -.25, 0), (2.4, .7, 3.8), IRON, top=BLACK)
    m.box((-1.25, -.4, 0), (.3, .5, 4), BLACK, detail=True)
    m.box((1.25, -.4, 0), (.3, .5, 4), BLACK, detail=True)
    m.box((0, .45, 0), (1.5, .7, 1.8), IRON, top=WHITE)
    m.box((0, .5, -1.8), (.25, .25, 2), muzzle)
    return m

@model('TANK')
def _(): return tank(RED)

@model('LTANK')
def _():
    m = tank(IRON)
    m.box((0, 1.05, 0), (.9, .5, .9), ORANGE, top=RED)
    return m

def mustang(c):
    m = Mesh()
    m.prism_z((0, 0, 0), .4, 3.6, 4, c, cap=WHITE)
    m.plate([(-2.6, -.05, .2), (-.3, 0, -.6), (.3, 0, -.6), (2.6, -.05, .2)], IRON)
    m.plate([(-.9, 0, 1.8), (-.1, 0, 1.4), (.1, 0, 1.4), (.9, 0, 1.8)], c, detail=True)
    m.plate([(0, 0, 1.4), (0, .9, 1.9), (0, 0, 1.9)], c, detail=True)
    return m

@model('MUSTANG')
def _(): return mustang(GREEN)

@model('RMUSTANG')
def _():
    m = mustang(GREEN)
    m.box((0, 0, 2.1), (.5, .5, .7), WHITE)
    return m

@model('SHIP')
def _():      # 小型ツェッペリン
    m = Mesh()
    m.prism_z((0, 1, 0), 2.2, 11, 6, CYAN, cap=IRON)
    m.box((0, -1.4, 0), (1.3, .9, 3), IRON, top=BLACK)
    m.box((0, -2, -1), (.6, .6, .6), RED, detail=True)
    m.plate([(0, 2.6, 4), (0, 4, 6), (0, 2.6, 6)], IRON, detail=True)
    return m

@model('MINE')
def _():
    m = Mesh()
    m.box((0, 0, 0), (1.2, 1.2, 1.2), IRON, top=PURPLE)
    m.box((0, 0, 0), (2.2, .2, .2), PURPLE, detail=True)
    m.box((0, 0, 0), (.2, 2.2, .2), PURPLE, detail=True)
    return m

@model('LSAT')
def _():      # レーザー衛星
    m = Mesh()
    m.prism_z((0, 0, 0), 1, 3.2, 6, IRON, cap=WHITE)
    m.plate([(-4.5, -.6, 0), (-4.5, .6, 0), (-1, .4, 0), (-1, -.4, 0)], CYAN)
    m.plate([(1, -.4, 0), (1, .4, 0), (4.5, .6, 0), (4.5, -.6, 0)], CYAN)
    return m

def balloon(band):
    m = Mesh()
    m.prism_y((0, 0, 0), 1.3, 1.8, 6, WHITE, top=WHITE)
    m.box((0, 0, -1.2), (1.5, .5, .1), band)
    return m

@model('SUPPLY')
def _(): return balloon(RED)

@model('MEDIC')
def _():
    m = balloon(RED)
    m.box((0, 0, -1.3), (.5, 1.2, .1), RED)
    return m

@model('FLAK')
def _():
    m = Mesh()
    m.box((0, 0, 0), (.5, .5, .5), ORANGE)
    return m

@model('ROCKET')
def _():
    m = Mesh()
    m.prism_z((0, 0, 0), .2, 1.3, 4, WHITE, cap=RED)
    return m

# 人物と場面(オープニング)。人物の原点は足もと(役者の y = 地面の高さ)
def person(m, h, body, legs, head, hair=None):
    """立っている人。h = 背の高さ"""
    k = h / 1.8
    m.box((-.13 * k, .45 * k, 0), (.18 * k, .9 * k, .2 * k), legs)
    m.box((.13 * k, .45 * k, 0), (.18 * k, .9 * k, .2 * k), legs)
    m.box((0, 1.17 * k, 0), (.5 * k, .55 * k, .28 * k), body)
    m.box((-.33 * k, 1.1 * k, 0), (.14 * k, .6 * k, .14 * k), body, detail=True)
    m.box((.33 * k, 1.1 * k, 0), (.14 * k, .6 * k, .14 * k), body, detail=True)
    m.box((0, 1.6 * k, 0), (.3 * k, .3 * k, .3 * k), head, top=hair)
    return m

@model('HINA')
def _():      # ヒナ(子供。赤い服)
    m = Mesh()
    person(m, 1.2, RED, WHITE, ORANGE, BLACK)
    m.max_rects = 2
    return m

@model('TERROR')
def _():      # テロリスト(黒ずくめ、目出し帽、小銃)
    m = Mesh()
    person(m, 1.85, BLACK, IRON, BLACK)
    m.box((.2, 1.15, -.35), (.08, .1, .8), IRON)      # 小銃(前へ構える)
    m.max_rects = 2
    return m

def loft(m, st, n, colors):
    """前後の筒。st = [(z, 中心 y, 半幅, 半高)…] を n 角の輪でつなぐ。colors(i, j) = 区間 i・辺 j の色。端の蓋は呼ぶ側で"""
    rings = []
    for z, cy, rx, ry in st:
        rings.append([(rx * math.cos(2 * math.pi * j / n), cy + ry * math.sin(2 * math.pi * j / n), z) for j in range(n)])
    for i in range(len(rings) - 1):
        a, b = rings[i], rings[i + 1]
        for j in range(n):
            k = (j + 1) % n
            mid = ((a[j][0] + a[k][0]) / 2, (a[j][1] + a[k][1]) / 2 - st[i][1], 0)
            m.face([a[j], a[k], b[k], b[j]], colors(i, j), False, mid)
    return rings

def zero(ground):
    """零式艦上戦闘機(A6M)。寸法は全幅 12m・全長 9.06m・主翼の上反角 6 度の公開値から、64×40 で見分けのつく形だけを残す。
    上面は初期型(A6M2)の明灰白色に近い TER1(濃緑だと草地に溶けた)、下面は灰(IRON。明灰だと朝の空の橙に溶けた)、カウリングは黒、日の丸。機首は -z。ground = 尾輪を着けて尻を下げた駐機の姿勢(原点は地面)"""
    m = Mesh()
    up, lo = TER1, IRON
    zc = 4.5                       # 機首からの距離 → モデルの z(機首が -z)
    Z = lambda d: d - zc
    # 胴体: 6 角の輪(左右に頂点、上下は平ら)。上の 3 辺は濃緑、下の 3 辺は明灰、カウリングは黒
    st = [(Z(.45), 0, .6, .6), (Z(1.6), 0, .64, .64), (Z(2.7), .02, .6, .62), (Z(4.7), .06, .5, .52), (Z(7.0), .14, .3, .3), (Z(8.9), .26, .08, .1)]
    rings = loft(m, st, 6, lambda i, j: BLACK if i == 0 else (up if j < 3 else lo))
    m.face4fan(rings[0], BLACK, (0, 0, -1))
    m.box((0, 0, Z(.25)), (.36, .36, .4), IRON, detail=True)                          # スピナー
    for a in (90, 210, 330):                                                            # 3 枚のプロペラ(止まっている。根もとは 1 点)
        r = math.radians(a)
        c, s = math.cos(r), math.sin(r)
        m.plate([(0, 0, Z(.1)), (-.12 * s + 1.45 * c, .12 * c + 1.45 * s, Z(.1)), (.12 * s + 1.45 * c, -.12 * c + 1.45 * s, Z(.1))], IRON, detail=True)
    # 風防: 長い温室形(2.9〜5.0)
    y0, y1 = .5, 1.0
    f0, f1, r0, r1 = Z(2.9), Z(3.3), Z(4.6), Z(5.1)
    w0, w1 = .36, .26
    m.face([(-w0, y0, f0), (-w1, y1, f1), (w1, y1, f1), (w0, y0, f0)], CYAN, False, (0, .6, -1))
    m.face([(-w1, y1, f1), (-w1, y1, r0), (w1, y1, r0), (w1, y1, f1)], CYAN, False, (0, 1, 0))
    m.face([(-w0, y0, f0), (-w0, y0, r1), (-w1, y1, r0), (-w1, y1, f1)], CYAN, False, (-1, 0, 0))
    m.face([(w0, y0, f0), (w1, y1, f1), (w1, y1, r0), (w0, y0, r1)], CYAN, False, (1, 0, 0))
    m.face([(-w1, y1, r0), (-w0, y0, r1), (w0, y0, r1), (w1, y1, r0)], up, False, (0, .5, 1))
    # 主翼: 低翼、上反角 6 度。翼端は丸く(4 点で切る)
    yr = -.38
    dy = lambda x: yr + (abs(x) - .55) * math.tan(math.radians(6))
    for sx in (-1, 1):
        P = lambda x, z: (sx * x, dy(x), Z(z))
        inner = [P(.55, 2.0), P(5.4, 2.85), P(5.4, 4.0), P(.55, 4.45)]
        tip = [P(5.4, 2.85), P(5.95, 3.25), P(5.95, 3.7), P(5.4, 4.0)]
        for poly in (inner, tip):
            m.face(poly, up, False, (0, 1, 0))
            m.face(poly, lo, False, (0, -1, 0))
        # 日の丸(上面、翼端寄り)と、内翼の前縁の黄色(敵味方の識別帯)
        e = .02
        m.face([(P(3.6, 2.85)[0], dy(3.6) + e, Z(2.85)), (P(4.6, 2.85)[0], dy(4.6) + e, Z(2.85)),
                (P(4.6, 3.75)[0], dy(4.6) + e, Z(3.75)), (P(3.6, 3.75)[0], dy(3.6) + e, Z(3.75))], RED, False, (0, 1, 0))
        m.face([(P(.6, 2.0)[0], dy(.6) + e, Z(2.0)), (P(2.6, 2.35)[0], dy(2.6) + e, Z(2.35)),
                (P(2.6, 2.6)[0], dy(2.6) + e, Z(2.6)), (P(.6, 2.25)[0], dy(.6) + e, Z(2.25))], ORANGE, True, (0, 1, 0))
        # 胴体の日の丸(操縦席の後ろ)
        x = sx * .43
        m.face([(x, -.2, Z(5.9)), (x, .4, Z(5.9)), (x, .4, Z(6.6)), (x, -.2, Z(6.6))], RED, False, (sx, 0, 0))
    # 水平尾翼・垂直尾翼
    for sx in (-1, 1):
        poly = [(sx * .15, .2, Z(7.35)), (sx * 2.35, .2, Z(7.85)), (sx * 2.35, .2, Z(8.45)), (sx * .15, .2, Z(8.8))]
        m.face(poly, up, False, (0, 1, 0))
        m.face(poly, lo, True, (0, -1, 0))
    m.plate([(0, .35, Z(7.1)), (0, 1.55, Z(8.1)), (0, 1.45, Z(8.75)), (0, .3, Z(8.95))], up)
    if ground:
        # 主脚(翼の下、間隔 3.6m。脚と車輪を 1 枚の板に)と尾輪
        for sx in (-1, 1):
            x = sx * 1.8
            m.plate([(x, dy(1.8), Z(2.55)), (x, dy(1.8), Z(2.75)), (x, -1.35, Z(2.95)), (x, -1.35, Z(2.35))], BLACK)
        m.plate([(0, .1, Z(8.45)), (0, -.35, Z(8.6)), (0, -.35, Z(8.3))], BLACK, detail=True)
        # 3 点の姿勢: 機首を 11 度上げ、車輪の下を y = 0 に
        a = math.radians(11)
        rot = lambda p: (p[0], p[1] * math.cos(a) - p[2] * math.sin(a), p[2] * math.cos(a) + p[1] * math.sin(a))
        m.v = [rot(p) for p in m.v]
        ymin = min(p[1] for p in m.v)
        m.v = [(p[0], round((p[1] - ymin) * 16) / 16, round(p[2] * 16) / 16) for p in m.v]
    m.max_rects = 3
    return m

@model('ZERO')
def _(): return zero(True)          # 格納庫の中の零戦

@model('ZEROF')
def _(): return zero(False)         # 飛んでいる零戦(脚を上げる)

def raider():  # テロ集団の魔改造の戦闘機: 黒い胴、紫の後退翼、双尾翼、ジェット。胴の下にヒナを入れるカプセルを吊る(6 面のボス・エンディングのカプセル)
    m = Mesh()
    rings = loft(m, [(-5, 2.6, .2, .2), (-3.4, 2.6, .8, .7), (1.5, 2.7, .9, .8), (4.6, 2.8, .7, .6)], 4, lambda i, j: BLACK if j < 2 else IRON)
    m.face4fan(rings[0], RED, (0, 0, -1))
    m.face4fan(rings[-1], ORANGE, (0, 0, 1))                                   # 噴射口
    m.face([(-.5, 3.3, -3.2), (-.35, 3.75, -2.2), (.35, 3.75, -2.2), (.5, 3.3, -3.2)], RED, False, (0, .6, -1))   # 赤い風防
    m.face([(-.35, 3.75, -2.2), (-.35, 3.75, -.8), (.35, 3.75, -.8), (.35, 3.75, -2.2)], RED, False, (0, 1, 0))
    for sx in (-1, 1):
        poly = [(sx * .8, 2.5, -1.2), (sx * 5.2, 2.7, 2.4), (sx * 5.2, 2.7, 3.4), (sx * .8, 2.5, 3.0)]
        m.face(poly, PURPLE, False, (0, 1, 0))
        m.face(poly, BLACK, False, (0, -1, 0))
        m.plate([(sx * .7, 3.2, 2.6), (sx * 1.2, 5.0, 4.0), (sx * 1.2, 5.0, 4.8), (sx * .7, 3.2, 4.6)], PURPLE)    # 双尾翼
        m.plate([(sx * 1.3, 2.4, -1.2), (sx * 1.3, 2.4, -.9), (sx * 1.3, 0.1, -.9), (sx * 1.3, 0.1, -1.2)], IRON, detail=True)   # 脚
        m.plate([(sx * .3, 2.3, 1.2), (sx * .3, 2.3, 1.5), (sx * .3, 1.5, 1.5), (sx * .3, 1.5, 1.2)], IRON, detail=True)        # カプセルの吊り具
    m.prism_z((0, .95, .6), .65, 2.8, 6, WHITE, cap=WHITE)                    # カプセル(白、水色の帯)
    m.box((0, .95, .6), (1.4, 1.4, .3), CYAN, detail=True)
    m.max_rects = 3
    return m

@model('RAIDER')
def _(): return raider()            # オープニングでは op.c がスプライトで描く(モデルは入れない)

@model('RAIDERM')
def _(): return raider()            # 家の上をかすめて降りる場面だけは 3D で描く(横から見る絵のスプライトは無い)

@model('ZEROHANGAR')
def _():      # 父の格納庫(赤い納屋)。開いた正面は +z(役者のヨーで向ける)。中は明るい木の壁と灰色の床(黒にすると零戦の黒いカウリングが溶けた)
    m = Mesh()
    w, h, d = 7.5, 5.5, 7.0
    m.face([(-w, 0, -d), (-w, h, -d), (w, h, -d), (w, 0, -d)], RED, False, (0, 0, -1))         # 外の後ろ
    m.face([(-w, 0, -d), (-w, h, -d), (w, h, -d), (w, 0, -d)], TER1, False, (0, 0, 1))         # 中の後ろ
    for sx in (-1, 1):
        side = [(sx * w, 0, -d), (sx * w, h, -d), (sx * w, h, d), (sx * w, 0, d)]
        m.face(side, RED, False, (sx, 0, 0))
        m.face(side, TER1, False, (-sx, 0, 0))
        roof = [(sx * w, h, -d), (0, h + 2.5, -d), (0, h + 2.5, d), (sx * w, h, d)]
        m.face(roof, TER2, False, (sx * .5, 1, 0))
        m.face(roof, TER2, False, (-sx * .5, -1, 0))
        gable = [(sx * w, h, d), (0, h + 2.5, d), (0, h, d)]
        m.face(gable, RED, False, (0, 0, 1))
        m.face(gable, RED, False, (0, 0, -1))
        m.face([(sx * w, h, -d), (0, h + 2.5, -d), (0, h, -d)], RED, False, (0, 0, -1))
        m.face([(sx * w, h, -d), (0, h + 2.5, -d), (0, h, -d)], TER1, False, (0, 0, 1))    # 奥の切妻の内側(無いと空が透けた)
        door = [(sx * w, 0, d), (sx * w, h, d), (sx * (w + .2), h, d - 4.2), (sx * (w + .2), 0, d - 4.2)]   # 開いた扉(外へ)
        m.plate(door, WHITE, detail=True)
    m.face([(-w, .02, -d), (-w, .02, d), (w, .02, d), (w, .02, -d)], IRON, False, (0, 1, 0))  # 床
    return m

@model('FARMHOUSE')
def _():      # 父の家
    m = Mesh()
    m.box((0, 2, 0), (8, 4, 6), WHITE, top=WHITE, skip='b')
    for sx in (-1, 1):
        roof = [(sx * 4.4, 4, -3.4), (0, 6.2, -3.4), (0, 6.2, 3.4), (sx * 4.4, 4, 3.4)]
        m.face(roof, RED, False, (sx * .6, 1, 0))
        m.face([(sx * 4, 4, -3), (0, 6, -3), (0, 4, -3)], WHITE, False, (0, 0, -1))
        m.face([(sx * 4, 4, 3), (0, 6, 3), (0, 4, 3)], WHITE, False, (0, 0, 1))
        m.face([(sx * 2.6, 1.6, -3.02), (sx * 2.6, 3, -3.02), (sx * 1.4, 3, -3.02), (sx * 1.4, 1.6, -3.02)], CYAN, True, (0, 0, -1))
    m.face([(-.6, 0, -3.02), (-.6, 2.6, -3.02), (.6, 2.6, -3.02), (.6, 0, -3.02)], TER2, False, (0, 0, -1))   # 玄関(-z)
    m.max_rects = 3
    return m

@model('TREE')
def _():
    m = Mesh()
    m.box((0, 1.5, 0), (.5, 3, .5), TER2, detail=True)
    m.prism_y((0, 4.5, 0), 2.2, 3.5, 6, GREEN, top=GREEN)
    m.max_rects = 2
    return m

@model('SMOKE')
def _():      # 町から上がる黒煙(上ほど太く、風で流れる)。根もとに炎
    m = Mesh()
    m.prism_y((0, 5, 0), 1.6, 10, 4, BLACK, top=BLACK)
    m.prism_y((1.2, 13, 0), 2.6, 7, 4, BLACK, top=BLACK)
    m.prism_y((3, 19, 0), 3.4, 5, 4, BLACK, top=BLACK, detail=True)
    m.box((0, .8, 0), (3, 1.6, 3), ORANGE, top=RED, detail=True)
    return m

@model('CAPSULE')
def _():
    m = Mesh()
    m.prism_z((0, 0, 0), 1.6, 3.2, 8, WHITE, cap=WHITE)
    m.box((0, 0, -1.65), (.5, 1.8, .1), CYAN)
    m.box((0, 0, -1.7), (1.8, .5, .1), CYAN)
    return m

# ---------------------------------------------------------------------------
# ボスの部品
# ---------------------------------------------------------------------------
@model('B_BALLOON')
def _():
    m = Mesh()
    m.prism_y((0, 3, 0), 3, 4, 4, RED, top=WHITE)     # 4 角柱(6 角柱だと 5 個で 1 フレーム約 19ms。64×40 の画面では見分けがつかない)
    m.plate([(-.1, 1, 0), (.1, 1, 0), (.1, -2.4, 0), (-.1, -2.4, 0)], BLACK, detail=True)
    m.box((0, -2.8, 0), (.8, .8, 2), ORANGE, top=IRON, detail=True)
    return m

@model('B_CRAB')
def _():     # ケーニヒス・クラブの車体と脚
    m = Mesh()
    m.box((0, 2, 0), (10, 3, 12), IRON, top=BLACK)
    m.box((0, 4.5, 0), (5.5, 2, 5), IRON, top=WHITE)
    m.box((0, 4.6, -4.5), (.8, .8, 5), RED)
    for sx in (-1, 1):
        for sz in (-1, 1):
            m.plate([(sx * 5, 2, sz * 5), (sx * 9, 3, sz * 6), (sx * 9, 2.2, sz * 6)], IRON, detail=True)
            m.plate([(sx * 9, 3, sz * 6), (sx * 11, -3, sz * 6.5), (sx * 10, -3, sz * 6.5)], BLACK, detail=True)
    return m

@model('B_MOUTH')
def _():
    m = Mesh()
    m.box((0, 0, 0), (2, 1.4, 2), ORANGE, top=RED)
    return m

@model('B_CORE')
def _():
    m = Mesh()
    m.box((0, 0, 0), (2.4, 2, 2.4), RED, top=ORANGE)
    return m

@model('B_HYDRA')
def _():     # P-51 × 3 の 1 機
    m = Mesh()
    m.prism_z((0, 0, 0), .9, 8, 4, GREEN, cap=WHITE)      # 胴は 4 角柱(6 角柱だと 3 機で 1 フレーム 24ms かかった)
    m.plate([(-6, 0, .4), (-.8, 0, -1.6), (.8, 0, -1.6), (6, 0, .4)], IRON)
    m.plate([(0, 0, 3), (0, 2.2, 4), (0, 0, 4)], GREEN, detail=True)
    return m

@model('B_HULL')
def _():     # グラーフ改の船体
    m = Mesh()
    m.prism_z((0, 3, 0), 7, 56, 6, CYAN, cap=IRON)
    m.prism_z((0, 3, -32), 4, 8, 6, CYAN, cap=WHITE, detail=True)
    m.plate([(0, 9, 24), (0, 16, 30), (0, 9, 30)], IRON, detail=True)
    m.plate([(-13, 3, 26), (-7, 3, 23), (-7, 3, 29)], IRON, detail=True)
    m.plate([(7, 3, 23), (13, 3, 26), (7, 3, 29)], IRON, detail=True)
    return m

@model('B_GONDOLA')
def _():
    m = Mesh()
    m.box((0, 0, 0), (3, 2, 5), IRON, top=BLACK, skip='t')     # 上は船体に隠れる
    m.box((0, -.3, -3.2), (.5, .5, 2), CYAN, detail=True)       # 砲身は細部(ボスの部位は細部を省くので、遠くの矩形の絵にだけ出る)
    return m

@model('B_DOPPEL')
def _():     # ドッペルゲンガー改
    m = Mesh()
    m.prism_z((0, 0, 0), 1.4, 14, 4, WHITE, cap=IRON)      # 胴は 4 角柱(P-51 と同じ。6 角柱より 1.5ms 軽い)
    m.box((-1.2, -.3, 4), (1.2, 1.2, 7), IRON)
    m.box((1.2, -.3, 4), (1.2, 1.2, 7), IRON)
    m.plate([(-9, 0, 3), (-1.4, 0, -2), (-1.4, 0, 2)], IRON)
    m.plate([(1.4, 0, -2), (9, 0, 3), (1.4, 0, 2)], IRON)
    m.plate([(0, 1, 4), (-.2, 4, 7), (.2, 1, 7)], IRON, detail=True)
    return m

@model('B_NOZZLE')
def _():
    m = Mesh()
    m.box((0, 0, 0), (1.4, 1.4, 1), ORANGE, top=RED)
    return m

@model('B_LENS')
def _():
    m = Mesh()
    m.prism_z((0, 0, 0), 1.6, .6, 6, WHITE, cap=CYAN)
    return m

@model('B_KEYHOLE')
def _():
    m = Mesh()
    m.prism_z((0, 0, 0), 5, 20, 6, IRON, cap=WHITE)      # 6 角柱(8 角柱より 1.6ms 軽い)
    m.plate([(-22, -3, 0), (-22, 3, 0), (-5, 2, 0), (-5, -2, 0)], CYAN)
    m.plate([(5, -2, 0), (5, 2, 0), (22, 3, 0), (22, -3, 0)], CYAN)
    return m

# ---------------------------------------------------------------------------
# 地形の部品(1 区画 = 8 単位。区画の原点は経路の真下の地面、z が進む向き)
# ---------------------------------------------------------------------------
def house(m, x, z, w=5, h=3, d=5, wall=TER1, roof=RED):
    m.tbox((x, h / 2, z), (w, h, d), wall, side=TER2, skip='bkt')
    y = h
    m.face([(x - w / 2, y, z - d / 2), (x - w / 2, y + 2, z), (x + w / 2, y + 2, z), (x + w / 2, y, z - d / 2)], roof, True, (0, 1, -1))
    return m

def strip(m, x0, x1, c, z0=-4, z1=4, y=0, detail=False):
    m.face([(x0, y, z0), (x0, y, z1), (x1, y, z1), (x1, y, z0)], c, detail, (0, 1, 0))
    return m

def pal(*rgb):
    b = bytearray()
    for r, g, bl in rgb:
        b += bytes([(r << 4) | bl, g])
    return b

MORNING = pal((7, 5, 5), (7, 4, 2), (4, 6, 1), (2, 4, 1), (5, 4, 3), (3, 2, 1), (7, 7, 7))
NOON = pal((4, 6, 7), (2, 3, 7), (3, 5, 3), (1, 3, 1), (4, 4, 4), (2, 2, 2), (7, 7, 7))
DUSK = pal((7, 4, 1), (4, 1, 4), (4, 3, 1), (2, 1, 0), (5, 2, 1), (2, 1, 0), (7, 4, 5))
NIGHT = pal((1, 1, 4), (0, 0, 1), (1, 1, 3), (0, 0, 1), (2, 2, 3), (0, 0, 0), (3, 3, 4))
TWILIGHT = pal((4, 2, 6), (1, 1, 3), (2, 3, 6), (1, 1, 3), (3, 3, 4), (1, 1, 2), (7, 7, 7))
SPACE = pal((0, 0, 0), (0, 0, 0), (1, 3, 7), (6, 6, 7), (3, 3, 3), (0, 0, 0), (7, 7, 7))
