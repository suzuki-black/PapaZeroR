#!/usr/bin/env python3
"""8 つのモジュールの定義: 0 = オープニング、1〜6 = 面、7 = エンディング(指示書 7 章)"""
import math
import re
from content import *

EV_SPAWN, EV_BOSS, EV_ROLL, EV_PROMPT, EV_TEXT, EV_SUB, EV_VOICE, EV_BGM, EV_PAL, EV_LOOP, EV_END, EV_CAM, EV_ITEM, EV_PROP, EV_FADE = range(15)
PR_ROLL, PR_LOOP, PR_DIVE = 1, 2, 3
E01, E02, E03, E04, E05, E06, E07, E08, SUPPLY, MEDIC = range(1, 11)
P_PARALLEL, P_HOLD, P_PASS, P_TAIL, P_CROSS, P_DRIFT, P_BOUNCE, P_FALL, P_LIFT = range(1, 10)
V_ROLL, V_LOOP, V_DIVE, V_FIRE, V_WARNING, V_HURRY, V_SEE, V_NOPAPA, V_PAPA, V_GIVE = range(1, 11)
SF_SPACE, SF_SCENE = 1, 2
ENEMY_MODELS = {E01: 'BIKE', E02: 'TANK', E03: 'LTANK', E04: 'MUSTANG', E05: 'SHIP', E06: 'RMUSTANG', E07: 'MINE', E08: 'LSAT'}
SONG = {}
with open('src/sound/songs.mml', encoding='utf8') as f:
    for line in f:
        m = re.match(r'@song (\w+)', line)
        if m:
            SONG[m.group(1)] = len(SONG) + 1


class Mod:
    def __init__(self, n, name, pal, bgm='', flags=0, clock=0, radio='', line=''):
        self.n, self.name, self.pal, self.flags, self.clock = n, name, pal, flags, clock
        self.pal2 = pal
        self.bgm = SONG.get(bgm, 0)
        self.path, self.sections, self.events = [], [], []
        self.strs = [radio, line]       # 0 = 継ぎ目の無線、1 = ボスを倒したときの父の一言
        self.models = ['FLAK', 'ROCKET', 'SUPPLY', 'MEDIC']
        self.boss = None
        self._p = []          # 点ごとの (x, y, z, yaw_rad, spd)

    def segs(self, *segs):
        """(長さ, ヨー変化[度], 高さの変化, 速度) の列。長さは 2 の倍数。stage は 4 単位ずつの量を積む"""
        x, y, z, yaw = 0.0, self.y0, 0.0, 0.0
        self.circles = []
        m = 0
        for j, (ln, dyaw, dy, spd) in enumerate(segs):
            if dyaw == 90 and (j == 0 or segs[j - 1][1] != 90):
                self.circles.append(m)
            m += ln
        for ln, dyaw, dy, spd in segs:
            n = ln // 2
            for i in range(n):
                self._p.append((x, y, z, yaw, spd))
                yaw += math.radians(dyaw) / n
                x += 2 * math.sin(yaw)
                z += 2 * math.cos(yaw)
                y += dy / n
        for i in range(3):
            self._p.append((x, y, z, yaw, segs[-1][3]))
            x += 2 * math.sin(yaw)
            z += 2 * math.cos(yaw)

    y0 = 8.0
    sec_y = 0

    def wrap(self, v):
        v = int(round(v * 256)) & 0xFFFF
        return v - 0x10000 if v >= 0x8000 else v

    def finish(self, pat):
        """経路の点を固定小数点にし、区画を作る。pat(k) = 区画 k のメッシュ"""
        ps = self._p
        for i, (x, y, z, yaw, spd) in enumerate(ps):
            nx = ps[min(i + 1, len(ps) - 1)]
            pitch = math.atan2(nx[1] - y, 2.0)
            self.path.append((self.wrap(x), self.wrap(y), self.wrap(z), int(round(yaw * 128 / math.pi)) & 255, int(round(pitch * 128 / math.pi))))
        for k in range(len(ps) // 4):
            x, y, z, yaw, spd = ps[k * 4]
            self.sections.append({'mesh': pat(k), 'x': self.wrap(x), 'y': self.wrap(self.sec_y), 'z': self.wrap(z), 'spd': spd, 'yaw': int(round(yaw * 128 / math.pi)) & 255})

    def at(self, m, lat=0, alt=None):
        p = self._p[min(int(m) // 2, len(self._p) - 1)]
        x = p[0] + lat * math.cos(p[3])
        z = p[2] - lat * math.sin(p[3])
        return x, (p[1] if alt is None else alt), z

    def ev(self, at, cmd, a=0, b=0, c=0, x=0, y=0, z=0):
        self.events.append((at, cmd, a, b, c, x, y, z))

    def spawn(self, at, t, m, lat, alt, ptn, yaw=0):
        if t in ENEMY_MODELS and ENEMY_MODELS[t] not in self.models:
            self.models.append(ENEMY_MODELS[t])
        x, y, z = self.at(m, lat, alt)
        self.ev(at, EV_SPAWN, t, ptn, yaw, self.wrap(x), self.wrap(y), self.wrap(z))

    def item(self, at, t, m, lat, alt):
        x, y, z = self.at(m, lat, alt)
        self.ev(at, EV_ITEM, t, 0, 0, self.wrap(x), self.wrap(y), self.wrap(z))

    def text(self, at, s, color=0):
        self.strs.append(s)
        self.ev(at, EV_TEXT, len(self.strs) - 1, color)

    def sub(self, at, s):
        self.strs.append(s)
        self.ev(at, EV_SUB, len(self.strs) - 1)

    def prompt(self, at, kind, frames):
        self.ev(at, EV_PROMPT, kind, frames)

    def roll(self, at, frames, step):
        self.ev(at, EV_ROLL, frames, step)

    def lap(self, n):
        """n 番目の周回区間(経路の 1 周の部分)に、敵が残っていれば回る命令を置く"""
        a = self.circles[n]
        self.ev(a + 72, EV_LOOP, x=a)

    def setboss(self, at, mov, dist, parts, pos=(0, 0, 0)):
        for p in parts:
            if p[0] not in self.models:
                self.models.append(p[0])
        # 指示書の耐久のままだとバルカン 10 発/秒で数秒で終わるので、ボスの部位は 3 倍にする(飾りと耐久 1 の部位はそのまま)
        parts = [p[:4] + (min(255, p[4] * 3) if p[4] > 1 else p[4],) + p[5:] for p in parts]
        self.boss = {'mov': mov, 'dist': dist, 'parts': parts}
        at = self.circles[2] - 16
        x, y, z = pos
        self.ev(at, EV_BOSS, x=self.wrap(x), y=self.wrap(y), z=self.wrap(z))

    def end(self):
        self.ev(len(self._p) * 2 - 8, EV_END)


def lap_segs(spd):
    """周回区間(120 単位): 直線 24、右へ 1 周 72、直線 24"""
    return [(24, 0, 0, spd), (18, 90, 0, spd), (18, 90, 0, spd), (18, 90, 0, spd), (18, 90, 0, spd), (24, 0, 0, spd)]


MODS = []

CLR_LASER, CLR_FIBER = 0x10, 0x12

def towns():
    road = lambda: strip(Mesh(), -4, 4, TER2, detail=True)
    a = road()
    strip(a, -.3, .3, WHITE, -2, 2, detail=True)
    b = road()
    house(b, -11, 0)
    house(b, 12, 1, wall=CLOUD, roof=TER2)
    c = road()
    house(c, -13, 1, 6, 4, 6, wall=CLOUD, roof=ORANGE)
    m = Mesh(); strip(m, -4, 4, TER2); m.tbox((6, 3, 0), (.3, 6, .3), TER2, detail=True)
    m.tbox((-16, 7, 0), (.4, 14, .4), IRON); m.prism_y((-16, 14, 0), 3, 3, 6, CYAN, top=WHITE, detail=True)
    over = Mesh(); strip(over, -4, 4, TER2)
    over.tbox((0, 12, 0), (60, 1.5, 4), IRON, top=TER2, skip='b'); over.tbox((-14, 6, 0), (2, 12, 2), IRON, detail=True); over.tbox((14, 6, 0), (2, 12, 2), IRON, detail=True)
    return [a, b, a, c, a, b, m, c], over

def s1():
    s = Mod(1, 'STAGE 1 / THE TOWN', MORNING, 'STAGE1', clock=0x50, radio='HOLD ON, HINA.', line='HOT AIR.')
    s.y0 = 6
    sp = 20
    s.segs((96, 0, 0, sp), (32, 30, 0, sp), (32, -30, 0, sp), *lap_segs(sp), (64, 0, 0, sp), (32, -35, 0, sp), (32, 35, 0, sp), *lap_segs(sp), (32, 0, 0, sp), *lap_segs(16))
    pats, over = towns()
    s.finish(lambda k: over if k == 42 else pats[(k * 5 + k // 7) % len(pats)])
    # 周回区間 1: 136-208、2: 368-440、ボス: 496-568
    s.lap(0); s.lap(1); s.lap(2)
    s.text(32, 'ROOFTOPS!')
    for at in (16, 44, 72, 112, 140):
        s.spawn(at, E01, at + 30, -3 if at % 8 else 3, .6, P_PARALLEL)
        s.spawn(at, E01, at + 34, 5 if at % 8 else -5, .6, P_PARALLEL)
    for at in (60, 100, 124):
        s.spawn(at, E02, at + 50, 7, .8, P_HOLD); s.spawn(at, E02, at + 58, -8, .8, P_HOLD)
    s.item(90, SUPPLY, 140, 3, 8); s.item(150, MEDIC, 190, -3, 7)
    for at in (166, 186, 206):
        s.spawn(at, E02, at + 40, -5, .8, P_HOLD); s.spawn(at, E01, at + 30, 4, .6, P_PARALLEL)
    for at in (240, 262, 284, 306, 328):
        s.spawn(at, E01, at + 30, 3, .6, P_PARALLEL); s.spawn(at, E02, at + 50, -7, .8, P_HOLD)
    s.prompt(332, PR_DIVE, 60)
    s.text(328, 'OVERPASS!')
    for at in (350, 372, 394, 416):
        s.spawn(at, E02, at + 45, 6 if at < 390 else -10, .8, P_HOLD); s.spawn(at, E02, at + 52, -6, .8, P_HOLD)
    for at in (432, 450, 468):
        s.spawn(at, E01, at + 30, -3, .6, P_PARALLEL); s.spawn(at, E01, at + 30, 4, .6, P_PARALLEL)
    s.item(470, MEDIC, 520, 2, 7)
    s.setboss(530, 0, 34, [
        ('B_BALLOON', -14, 2, 0, 6, 0, 0, 1), ('B_BALLOON', -7, 5, 6, 6, 0, 0, 1), ('B_BALLOON', 0, 2, 0, 6, 0, 0, 1),
        ('B_BALLOON', 7, 5, 6, 6, 0, 0, 1), ('B_BALLOON', 14, 2, 0, 6, 0, 0, 1)], s.at(560, 0, 16))
    s.end()
    return s

def s2():
    s = Mod(2, 'STAGE 2 / THE HARBOR', NOON, 'STAGE2', clock=0x40, radio='THEY HAVE LASERS, PAPA.', line='CRABS GO IN THE POT.')
    s.y0 = 9
    sp = 22
    s.segs((104, 0, 0, sp), (24, 0, 6, sp), (40, 25, 0, sp), *lap_segs(sp), (48, -25, 0, sp), (32, 0, -5, sp), *lap_segs(sp), (32, 0, 0, sp), *lap_segs(16))
    q = strip(Mesh(), -40, -5, IRON)
    strip(q, 5, 60, CLOUD, y=0, detail=True)
    a = Mesh(); strip(a, -40, -5, IRON); a.tbox((-14, 2.5, 0), (9, 5, 7), TER1, side=TER2, top=IRON, skip='bk')
    b = Mesh(); strip(b, -40, -5, IRON); b.tbox((-8, 7, 0), (.8, 14, .8), ORANGE); b.tbox((0, 13.5, 0), (18, .8, .8), ORANGE, detail=True)
    c = Mesh(); strip(c, -40, -5, IRON); c.tbox((-12, 1.2, 0), (3, 2.4, 6), RED, skip='b'); c.tbox((-8.5, 1.2, 0), (3, 2.4, 6), GREEN, skip='b'); c.tbox((-12, 3.6, 0), (3, 2.4, 6), CYAN, detail=True, skip='b')
    d = Mesh(); strip(d, -40, -5, IRON); d.tbox((22, 2, 0), (10, 4, 8), IRON, top=TER2, skip='bk'); d.tbox((22, 6, 2), (4, 4, 3), WHITE, detail=True, skip='b')
    pats = [q, a, c, q, b, a, d, c]
    s.finish(lambda k: pats[(k * 3 + k // 5) % len(pats)])
    s.lap(0); s.lap(1); s.lap(2)
    s.text(40, 'LASER TANK!')
    for at in (16, 48, 80, 112, 148):
        s.spawn(at, E02, at + 50, -9, .8, P_HOLD); s.spawn(at, E03, at + 60, -12, .8, P_HOLD)
    for at in (130, 170, 200, 226):
        s.spawn(at, E04, at + 80, 2, 12, P_PASS, 128); s.spawn(at, E04, at + 84, -6, 14, P_PASS, 128)
    s.prompt(88, PR_ROLL, 60)
    s.item(150, SUPPLY, 190, 2, 11); s.item(250, MEDIC, 300, -3, 12)
    for at in (272, 298, 324, 350, 376):
        s.spawn(at, E03, at + 56, -10, .8, P_HOLD); s.spawn(at, E04, at + 80, 3, 12, P_PASS, 128)
    s.prompt(300, PR_ROLL, 60)
    for at in (404, 430, 456):
        s.spawn(at, E02, at + 36, -8, .8, P_HOLD); s.spawn(at, E04, at + 80, 0, 13, P_PASS, 128)
    s.item(470, MEDIC, 510, 2, 9)
    s.setboss(500, 0, 34, [
        ('B_CRAB', 0, -3, 0, 40, 9, 8, 0),
        ('B_MOUTH', -2, 4, -1, 10, 0, 0, CLR_LASER), ('B_MOUTH', 2, 4, -1, 10, 0, 0, CLR_LASER),
        ('B_CORE', 0, 1, -6, 40, 1, 2, 1)], s.at(520, 0, 6))
    s.end()
    return s

def s3():
    s = Mod(3, 'STAGE 3 / THE CANYON', DUSK, 'STAGE3', clock=0x30, radio='PAPA, HURRY!', line='THREE FOR ONE.')
    s.y0 = 7
    sp = 24
    s.segs((80, 0, 0, sp), (40, 35, 0, sp), (40, -70, 0, sp), (40, 35, 0, sp), *lap_segs(sp), (56, 30, 0, sp), (56, -30, 0, sp), *lap_segs(sp), (24, 0, 0, sp), *lap_segs(18))
    def wall(rock):
        # 壁は 16 単位ずつ。偶数の区画だけ描き、2 区画に 1 枚で済ませる(谷の壁は大きいので、枚数を減らさないと 12fps を割る)
        m = Mesh()
        strip(m, -6, 6, CLOUD, -4, 12, detail=True)
        for sx in (-1, 1):
            m.face([(sx * 12, 0, -4), (sx * 16, 11, -4), (sx * 16, 11, 12), (sx * 12, 0, 12)], TER1 if sx < 0 else TER2, False, (-sx, .3, 0))
            m.face([(sx * 16, 11, -4), (sx * 22, 24, -4), (sx * 22, 24, 12), (sx * 16, 11, 12)], TER2 if sx < 0 else TER1, True, (-sx, .3, 0))
        if rock:
            m.tbox((rock, 5, 0), (3, 10, 3), TER2, top=TER1, detail=True, skip='b')
        return m
    a, b, c = wall(0), wall(7), wall(-7)
    br = wall(0)
    br.tbox((0, 13, 0), (40, .6, 2), IRON, top=TER1, skip='b')
    aa = Mesh(); aa.__dict__.update(wall(0).__dict__); aa.tbox((-9, 1, 0), (5, 2, 5), IRON, top=BLACK, skip='b')
    pats = [a, a, b, a, c, a, aa, a]
    s.finish(lambda k: None if k % 2 else br if k in (24, 60) else pats[(k // 2 * 3) % len(pats)])
    s.lap(0); s.lap(1); s.lap(2)
    s.text(36, 'BEHIND YOU!')
    for at in (16, 44, 76, 108):
        s.spawn(at, E03, at + 56, -6, .8, P_HOLD); s.spawn(at, E04, at + 80, 3, 9, P_PASS, 128)
    s.roll(120, 30, 3); s.roll(170, 30, -3)      # S 字で傾く
    s.roll(205, 20, 0)
    for at in (140, 176, 212, 240, 270):
        s.spawn(at, E04, at + 80, -3, 9, P_TAIL, 128)
    s.prompt(180, PR_ROLL, 60)
    s.item(216, SUPPLY, 250, 0, 8)
    for at in (310, 340, 370, 400):
        s.spawn(at, E04, at + 80, 2, 8, P_PASS, 128); s.spawn(at, E03, at + 60, -6, .8, P_HOLD)
    s.item(420, MEDIC, 460, 0, 8)
    for at in (440, 470, 496):
        s.spawn(at, E04, at + 80, -2, 9, P_TAIL, 128)
    s.setboss(528, 0, 30, [
        ('B_HYDRA', -12, 0, 0, 20, 0, 16, 0x11), ('B_HYDRA', 6, 10, 0, 20, 0, 16, 0x11), ('B_HYDRA', 6, -10, 0, 20, 0, 16, 0x11)], s.at(560, 0, 7))
    s.end()
    return s

def s4():
    s = Mod(4, 'STAGE 4 / THE CLOUD SEA', NIGHT, 'STAGE4', clock=0x20, radio='THEY ARE ON YOUR TAIL!', line='TOO MUCH GAS.')
    s.y0 = 12
    sp = 20
    s.segs((104, 0, 0, sp), (32, 20, 0, sp), *lap_segs(sp), (32, -20, 2, sp), (80, 0, 0, sp), *lap_segs(sp), (24, 0, 0, sp), *lap_segs(16))
    a = strip(Mesh(), -60, 60, CLOUD, detail=True)
    b = Mesh(); strip(b, -60, 60, CLOUD, detail=True); b.tbox((-16, 9, 0), (10, 18, 8), CLOUD, top=WHITE, side=TER1, skip='b')
    c = Mesh(); c.tbox((18, 7, 0), (12, 14, 10), CLOUD, top=WHITE, side=TER1, skip='b')
    d = Mesh(); d.prism_y((30, 40, 40), 5, .5, 8, WHITE, detail=False)
    pats = [a, Mesh().face([(-1, 0, 0), (0, 0, 1), (1, 0, 0)], CLOUD), b, a, c, a]
    s.finish(lambda k: d if k % 16 == 3 else pats[(k * 5) % len(pats)])
    s.lap(0); s.lap(1); s.lap(2)
    s.text(36, 'AIRSHIPS!')
    for at in (16, 48, 84, 120):
        s.spawn(at, E05, at + 60, -24, 20, P_CROSS); s.spawn(at, E05, at + 76, -30, 16, P_CROSS)
    s.prompt(96, PR_ROLL, 60)
    s.roll(150, 42, 3)                  # 艦隊の下をくぐる 180°
    s.roll(240, 42, 3)
    for at in (170, 200, 226):
        s.spawn(at, E04, at + 80, 4, 12, P_TAIL, 128)
    s.item(190, SUPPLY, 240, 0, 13)
    for at in (262, 292, 322, 352):
        s.spawn(at, E05, at + 60, -24, 18, P_CROSS); s.spawn(at, E04, at + 80, -3, 13, P_PASS, 128)
    s.prompt(300, PR_ROLL, 60)
    s.item(360, MEDIC, 400, 2, 14)
    for at in (384, 412, 440):
        s.spawn(at, E04, at + 80, 3, 14, P_TAIL, 128)
    parts = [('B_HULL', 0, 8, 10, 1, 9, 8, 0)]
    for k, (x, z) in enumerate(((-9, -12), (0, -8), (9, -12))):
        parts.append(('B_GONDOLA', x, -2, z, 15, 0, 0, CLR_FIBER))
    for x in (-6, -2, 2, 6):
        parts.append(('B_CORE', x, 2, -22, 10, 1, 2, 0))
    s.setboss(480, 0, 58, parts, s.at(520, 0, 18))
    s.end()
    return s

def s5():
    s = Mod(5, 'STAGE 5 / THE STRATOSPHERE', TWILIGHT, 'STAGE5', clock=0x10, radio='PAPA, HURRY!', line='NICE WINGS.')
    s.y0 = 14
    sp = 26
    s.segs((80, 0, 8, sp), (48, 15, 8, sp), *lap_segs(sp), (48, -15, 8, sp), (64, 0, 6, sp), *lap_segs(sp), (24, 0, 2, sp), *lap_segs(18))
    a = strip(Mesh(), -60, 60, CLOUD, detail=True)
    b = Mesh().prism_y((-14, 40, 0), 3, 3, 8, IRON, top=WHITE)
    c = Mesh(); c.tbox((14, 34, 0), (1, 40, 1), RED); c.tbox((14, 54, 0), (5, 1, 5), IRON, detail=True)
    pats = [a, Mesh().face([(-1, 0, 0), (0, 0, 1), (1, 0, 0)], CLOUD), b, a]
    s.finish(lambda k: c if k == 66 else pats[(k * 3) % len(pats)])
    s.lap(0); s.lap(1); s.lap(2)
    s.text(36, 'MISSILES!')
    for at in (16, 44, 76, 108, 136):
        s.spawn(at, E06, at + 70, 3, 22, P_BOUNCE, 128); s.spawn(at, E04, at + 84, -4, 24, P_PASS, 128)
    s.prompt(64, PR_LOOP, 60); s.prompt(120, PR_ROLL, 60)
    for at in (160, 190, 220):
        s.spawn(at, E06, at + 70, -3, 34, P_PASS, 128); s.spawn(at, E04, at + 80, 3, 34, P_TAIL, 128)
    s.item(180, SUPPLY, 220, 0, 36)
    for at in (250, 280, 310, 340, 370):
        s.spawn(at, E06, at + 70, 4, 44, P_BOUNCE, 128); s.spawn(at, E06, at + 76, -4, 46, P_PASS, 128)
    s.prompt(300, PR_ROLL, 60)
    s.item(350, MEDIC, 400, 0, 52)
    for at in (392, 420, 448):
        s.spawn(at, E04, at + 80, 3, 56, P_TAIL, 128)
    s.setboss(480, 0, 34, [
        ('B_DOPPEL', 0, 0, 0, 60, 1, 0, 0x13),
        ('B_NOZZLE', -3, 0, -8, 15, 0, 0, 2), ('B_NOZZLE', 3, 0, -8, 15, 0, 0, 2)], s.at(520, 0, 50))     # カメラ(高さ 46)の少し上。60 だと画面の上の端に張り付いた
    s.end()
    return s

def s6():
    s = Mod(6, 'STAGE 6 / THE ORBIT', SPACE, 'STAGE6', flags=SF_SPACE, clock=0x01, radio='I CAN SEE YOU!', line='GIVE HER BACK.')
    s.y0 = 60
    sp = 20
    s.segs((104, 0, 0, sp), (32, 15, 0, sp), *lap_segs(sp), (32, -15, 0, sp), (88, 0, 0, sp), *lap_segs(sp), (24, 0, 0, sp), *lap_segs(16))
    a = Mesh(); a.tbox((-14, 2, 0), (3, 3, 3), TER2, top=TER1)
    b = Mesh(); b.plate([(12, -4, -3), (12, 4, -3), (18, 4, 3), (18, -4, 3)], CYAN)
    c = Mesh(); c.tbox((-22, 0, 0), (1, 1, 8), TER1, skip='fk'); c.tbox((-22, 6, 0), (1, 12, 1), TER1, detail=True); c.tbox((22, 0, 0), (1, 1, 8), TER1, skip='fk')
    s.sec_y = 60
    pats = [None, a, None, b, None, c]
    s.finish(lambda k: pats[(k * 5) % len(pats)])
    s.lap(0); s.lap(1); s.lap(2)
    s.text(36, 'THERE SHE IS!')
    s.ev(8, EV_PAL, 1)                  # 常にゆっくり回る
    for at in (16, 40, 64, 92, 120, 148):
        s.spawn(at, E07, at + 60, -6, 62, P_DRIFT); s.spawn(at, E07, at + 66, 6, 58, P_DRIFT); s.spawn(at, E08, at + 80, -3, 63, P_HOLD)
    for at in (170, 200, 226):
        s.spawn(at, E08, at + 40, -5, 60, P_HOLD); s.spawn(at, E07, at + 56, 0, 60, P_DRIFT)
    s.item(180, SUPPLY, 230, 0, 61)
    for at in (260, 288, 316, 344, 372):
        s.spawn(at, E08, at + 70, -2, 60, P_HOLD); s.spawn(at, E07, at + 56, 4, 60, P_DRIFT)
    for at in (130, 300, 360, 440):
        s.prompt(at, PR_ROLL, 60)
    s.item(400, MEDIC, 440, 0, 60)
    s.ev(470, EV_VOICE, V_GIVE)
    s.text(470, 'GIVE HER BACK.')
    s.setboss(486, 0, 38, [
        ('B_KEYHOLE', 0, 0, 6, 1, 9, 8, 0),
        ('B_LENS', -6, 0, -6, 12, 0, 0, 0x10), ('B_LENS', -2, 5, -6, 12, 0, 0, 0x11),
        ('B_LENS', 4, 3, -6, 12, 0, 0, 0x12), ('B_LENS', 4, -3, -6, 12, 0, 0, 0x13),
        ('B_LENS', -2, -5, -6, 12, 9, 8, 0x14),
        ('B_CORE', 0, 0, -5, 60, 1, 2, 0),
        ('CAPSULE', 0, 8, 0, 1, 9, 1, 0)], s.at(520, 0, 60))
    s.end()
    return s

def opening():
    s = Mod(0, 'OPENING', MORNING, 'OPENING', flags=SF_SCENE)
    s.y0 = 3
    s.models += ['HINA', 'BIKE', 'SHIP', 'ZERO']
    s.segs((48, 0, 0, 9), (40, 40, 2, 8), (40, -40, 0, 11), (16, 0, 0, 11))
    h = Mesh(); house(h, -9, 2, 7, 4, 7, wall=TER1, roof=TER2); h.tbox((11, 3, 2), (9, 6, 10), TER2, top=RED, skip='b')
    g = strip(Mesh(), -2, 2, TER1)
    s.finish(lambda k: h if k in (3, 7, 11) else g)
    s.sub(4, 'MORNING.')
    s.ev(4, EV_PROP, 'HINA', P_LIFT, 0, *[s.wrap(v) for v in s.at(26, 1, .9)])
    s.ev(8, EV_VOICE, V_PAPA)
    s.sub(16, 'PAPA, BREAKFAST!')
    s.ev(22, EV_PROP, 'SHIP', 0, 0, *[s.wrap(v) for v in s.at(30, 1, 11)])
    s.spawn(20, E01, 42, 3, .6, P_PARALLEL); s.spawn(20, E01, 44, -2, .6, P_PARALLEL); s.spawn(20, E01, 48, 1, .6, P_PARALLEL)
    s.ev(30, EV_VOICE, V_PAPA)
    s.sub(30, 'PAPA!')
    s.sub(40, 'SIX HOURS.')
    s.sub(52, 'THEN SHE RIDES THE ROCKET.')
    s.sub(62, '06:00')
    s.sub(76, 'HE DID NOT CALL THE POLICE.')
    s.ev(74, EV_PROP, 'ZERO', 0, 0, *[s.wrap(v) for v in s.at(146, 0, 3.5)])   # 道の終わりのすぐ先、目の高さの少し下。走り寄って乗り込むところで場面が終わる
    s.sub(130, "LET'S GO.")
    s.end()
    return s

def ending():
    s = Mod(7, 'ENDING', SPACE, 'ENDING', flags=SF_SCENE | SF_SPACE)
    s.pal2 = MORNING
    s.y0 = 40
    s.models += ['CAPSULE']
    s.segs((40, 0, 0, 10), (48, 0, -20, 16), (48, 0, -12, 16), (48, 0, -4, 12), (32, 0, -1, 6), (16, 0, 0, 3))
    pats, over = towns()
    s.finish(lambda k: None if k < 11 else pats[(k * 5) % len(pats)])
    s.ev(2, EV_VOICE, V_PAPA)
    s.sub(2, 'PAPA!')
    s.ev(2, EV_PROP, 'CAPSULE', 0, 0, *[s.wrap(v) for v in s.at(22, 0, 40)])
    s.ev(44, EV_FADE)
    s.sub(90, 'HOME.')
    s.sub(150, 'BREAKFAST?')
    s.sub(176, 'YEAH.')
    s.end()
    return s

MODS = [opening(), s1(), s2(), s3(), s4(), s5(), s6(), ending()]
