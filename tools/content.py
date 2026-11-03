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

# 人物と場面(場面 1〜3)
@model('HINA')
def _():
    m = Mesh()
    m.box((0, .9, 0), (.35, .35, .35), ORANGE)
    m.box((0, .35, 0), (.45, .7, .3), RED)
    m.box((-.32, .4, 0), (.15, .5, .15), WHITE)
    m.box((.32, .4, 0), (.15, .5, .15), WHITE)
    m.box((-.12, -.3, 0), (.15, .6, .15), WHITE)
    m.box((.12, -.3, 0), (.15, .6, .15), WHITE)
    return m

@model('ZERO')
def _():      # 零戦(場面 3 とエンディング)
    m = Mesh()
    m.prism_z((0, 0, 0), .55, 4.6, 6, WHITE, cap=BLACK)
    m.plate([(-3.4, -.1, .1), (-.4, -.1, -.8), (.4, -.1, -.8), (3.4, -.1, .1)], WHITE)
    m.plate([(-1.1, .1, 2.2), (-.1, .1, 1.7), (.1, .1, 1.7), (1.1, .1, 2.2)], WHITE, detail=True)
    m.plate([(0, .1, 1.7), (0, 1.1, 2.3), (0, .1, 2.3)], WHITE, detail=True)
    m.box((0, .55, -.2), (.5, .4, 1.2), CYAN, detail=True)
    m.box((-.9, -.1, -.5), (.5, .5, .5), RED)     # 日の丸
    m.box((.9, -.1, -.5), (.5, .5, .5), RED)
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
