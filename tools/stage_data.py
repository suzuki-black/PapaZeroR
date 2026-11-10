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
        self.film = None                # 映像の場面(Film。オープニングと継ぎ目)
        self.ahead = 8                  # 道中に描く区画の数(1 区画 8 単位)。多いほど遠くまで見えるが重い
        self.op_base = 0                # 演出のコードの置き場所(Makefile の OPn_BASE と同じ値)
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
    sp = 14     # 低く飛ぶ面なので、ほかの面(20〜26)より遅く。20 だとロックした戦車へ誘導弾が届く前に通り過ぎ、倒したか見えなかった
    s.segs((96, 0, 0, sp), (32, 30, 0, sp), (32, -30, 0, sp), *lap_segs(sp), (64, 0, 0, sp), (32, -35, 0, sp), (32, 35, 0, sp), *lap_segs(sp), (32, 0, 0, sp), *lap_segs(13))
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
    # 追っ手との空中戦が主なので、前半は高く(24)飛ぶ。後半に港の基地(レーザー戦車)へ降りて叩き、そのままボスへ
    s.y0 = 24
    sp = 22
    s.segs((104, 0, 0, sp), (24, 0, 0, sp), (40, 25, 0, sp), *lap_segs(sp), (48, -25, -8, sp), (32, 0, -6, sp), *lap_segs(sp), (32, 0, 0, sp), *lap_segs(16))
    q = strip(Mesh(), -40, -5, IRON)
    strip(q, 5, 60, CLOUD, y=0, detail=True)
    a = Mesh(); strip(a, -40, -5, IRON); a.tbox((-14, 2.5, 0), (9, 5, 7), TER1, side=TER2, top=IRON, skip='bk')
    b = Mesh(); strip(b, -40, -5, IRON); b.tbox((-8, 7, 0), (.8, 14, .8), ORANGE); b.tbox((0, 13.5, 0), (18, .8, .8), ORANGE, detail=True)
    c = Mesh(); strip(c, -40, -5, IRON); c.tbox((-12, 1.2, 0), (3, 2.4, 6), RED, skip='b'); c.tbox((-8.5, 1.2, 0), (3, 2.4, 6), GREEN, skip='b'); c.tbox((-12, 3.6, 0), (3, 2.4, 6), CYAN, detail=True, skip='b')
    d = Mesh(); strip(d, -40, -5, IRON); d.tbox((22, 2, 0), (10, 4, 8), IRON, top=TER2, skip='bk'); d.tbox((22, 6, 2), (4, 4, 3), WHITE, detail=True, skip='b')
    pats = [q, a, c, q, b, a, d, c]
    s.finish(lambda k: pats[(k * 3 + k // 5) % len(pats)])
    s.lap(0); s.lap(1); s.lap(2)
    s.text(40, 'BANDITS!')
    for at in (16, 48, 80, 112):
        s.spawn(at, E04, at + 70, -6, 25, P_PASS, 128); s.spawn(at, E04, at + 76, 5, 22, P_PASS, 128)
    for at in (130, 170, 200, 226):
        s.spawn(at, E04, at + 80, 2, 24, P_PASS, 128); s.spawn(at, E04, at + 84, -6, 27, P_PASS, 128)
    s.text(286, 'LASER TANK!')
    s.prompt(88, PR_ROLL, 60)
    s.item(150, SUPPLY, 190, 2, 24); s.item(250, MEDIC, 300, -3, 22)
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
    s.ahead = 11                        # 谷の壁を遠くまで見せる(8 区画だと、高く飛ぶ前半に遠くの壁が消えて平地に見えた)
    # 前半は谷の上(28。壁は 24 まで)で追っ手と空中戦。後半に谷へ降り、谷底の基地(戦車)を叩いてボスへ
    s.y0 = 28
    sp = 24
    s.segs((80, 0, 0, sp), (40, 35, 0, sp), (40, -70, 0, sp), (40, 35, 0, sp), *lap_segs(sp), (56, 30, -10, sp), (56, -30, -11, sp), *lap_segs(sp), (24, 0, 0, sp), *lap_segs(18))
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
        s.spawn(at, E04, at + 70, -6, 30, P_PASS, 128); s.spawn(at, E04, at + 80, 3, 27, P_PASS, 128)
    s.roll(120, 30, 3); s.roll(170, 30, -3)      # S 字で傾く
    s.roll(205, 20, 0)
    for at in (140, 176, 212, 240, 270):
        s.spawn(at, E04, at + 80, -3, 28, P_TAIL, 128)
    s.prompt(180, PR_ROLL, 60)
    s.item(216, SUPPLY, 250, 0, 28)
    for at in (310, 340, 370, 400):
        s.spawn(at, E04, at + 80, 2, None, P_PASS, 128); s.spawn(at, E03, at + 60, -6, .8, P_HOLD)    # 降りながら。高さは経路に合わせる
    s.item(420, MEDIC, 460, 0, 8)
    for at in (440, 470, 496):
        s.spawn(at, E04, at + 80, -2, 9, P_TAIL, 128)
    s.setboss(528, 0, 30, [
        ('B_HYDRA', -12, 0, 0, 20, 0, 16, 0x11), ('B_HYDRA', 6, 10, 0, 20, 0, 16, 0x11), ('B_HYDRA', 6, -10, 0, 20, 0, 16, 0x11)], s.at(560, 0, 7))
    s.end()
    return s

def s4():
    s = Mod(4, 'STAGE 4 / THE CLOUD SEA', NIGHT, 'STAGE4', clock=0x20, radio='THEY ARE ON YOUR TAIL!', line='TOO MUCH GAS.')
    # 雲の峰(18 まで)の上を飛ぶ(前は 12 で、雲の海の中に沈んで見えた)
    s.y0 = 20
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
        s.spawn(at, E05, at + 60, -24, 28, P_CROSS); s.spawn(at, E05, at + 76, -30, 24, P_CROSS)
    s.prompt(96, PR_ROLL, 60)
    s.roll(150, 42, 3)                  # 艦隊の下をくぐる 180°
    s.roll(240, 42, 3)
    for at in (170, 200, 226):
        s.spawn(at, E04, at + 80, 4, 20, P_TAIL, 128)
    s.item(190, SUPPLY, 240, 0, 21)
    for at in (262, 292, 322, 352):
        s.spawn(at, E05, at + 60, -24, 26, P_CROSS); s.spawn(at, E04, at + 80, -3, 21, P_PASS, 128)
    s.prompt(300, PR_ROLL, 60)
    s.item(360, MEDIC, 400, 2, 22)
    for at in (384, 412, 440):
        s.spawn(at, E04, at + 80, 3, 22, P_TAIL, 128)
    parts = [('B_HULL', 0, 8, 10, 1, 9, 8, 0)]
    for k, (x, z) in enumerate(((-9, -12), (0, -8), (9, -12))):
        parts.append(('B_GONDOLA', x, -2, z, 15, 0, 0, CLR_FIBER))
    for x in (-6, -2, 2, 6):
        parts.append(('B_CORE', x, 2, -22, 10, 1, 2, 0))
    s.setboss(480, 0, 58, parts, s.at(520, 0, 26))
    s.end()
    return s

def s5():
    s = Mod(5, 'STAGE 5 / THE STRATOSPHERE', TWILIGHT, 'STAGE5', clock=0x10, radio='PAPA, HURRY!', line='NICE WINGS.')
    s.y0 = 22
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
        s.spawn(at, E06, at + 70, 3, 30, P_BOUNCE, 128); s.spawn(at, E04, at + 84, -4, 32, P_PASS, 128)
    s.prompt(64, PR_LOOP, 60); s.prompt(120, PR_ROLL, 60)
    for at in (160, 190, 220):
        s.spawn(at, E06, at + 70, -3, 42, P_PASS, 128); s.spawn(at, E04, at + 80, 3, 42, P_TAIL, 128)
    s.item(180, SUPPLY, 220, 0, 44)
    for at in (250, 280, 310, 340, 370):
        s.spawn(at, E06, at + 70, 4, 52, P_BOUNCE, 128); s.spawn(at, E06, at + 76, -4, 54, P_PASS, 128)
    s.prompt(300, PR_ROLL, 60)
    s.item(350, MEDIC, 400, 0, 60)
    for at in (392, 420, 448):
        s.spawn(at, E04, at + 80, 3, 64, P_TAIL, 128)
    s.setboss(480, 0, 34, [
        ('B_DOPPEL', 0, 0, 0, 60, 1, 0, 0x13),
        ('B_NOZZLE', -3, 0, -8, 15, 0, 0, 2), ('B_NOZZLE', 3, 0, -8, 15, 0, 0, 2)], s.at(520, 0, 58))     # カメラ(高さ 54)の少し上。カメラより 14 上だと画面の上の端に張り付いた
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

class Film:
    """オープニングの映画(src/engine/op.c が時刻 t[ティック] で再生する)。曲 OPENING と同じ時計。
    座標は単位(8.8 にして 16bit で回り込む。カメラから 128 単位より遠いものは描かない)。
    向き: 方位 h は度(0 = 北 = +z、90 = 東 = +x)。カメラのヨー = h、役者のヨー = h + 180(モデルの正面は -z)"""
    FL_EASE, FL_BOB, FL_C, FL_SHAKE, FL_STEP = 1, 2, 4, 8, 16
    FE_SUB, FE_CAP, FE_VOICE, FE_SE, FE_COCKPIT, FE_END, FE_SHAKE = range(1, 8)

    def __init__(self):
        self.cam, self.acts, self.evs = [], [], []

    @staticmethod
    def ang(d):
        return int(round(d * 256 / 360)) & 255

    def cam_key(self, t, p, h, pitch=0, roll=0, fl=0, sect=0):
        self.cam.append((t, p, self.ang(h), self.ang(pitch), self.ang(roll), fl | self.FL_C | (sect << 5)))

    def actor(self):
        self.acts.append([])
        return len(self.acts) - 1

    def key(self, a, t, mesh, p=None, h=None, roll=0, fl=0, cut=False):
        """役者 a のキー。p・h を省くと前のキーのまま。cut = その時刻で切り替える(前のキーに FL_STEP を付けて動かさない)。
        mesh = 0(隠す)のときは必ず切り替え、場所は前のまま"""
        keys = self.acts[a]
        prev = keys[-1] if keys else None
        if prev is not None:
            if p is None or mesh == 0:
                p = p if mesh else prev[1]
            if h is None:
                h = (prev[2] * 360 / 256) - 180
            if cut or mesh == 0:
                keys[-1] = prev[:5] + (self.FL_STEP,)
        if h is None:
            h = 180
        keys.append((t, p, self.ang(h + 180), self.ang(roll), mesh, fl))

    def ev(self, t, kind, arg=0, s=None):
        self.evs.append((t, kind, arg, s))

    def header(self, ids):
        def fx(v):
            v = int(round(v * 256)) & 0xFFFF
            return v - 0x10000 if v >= 0x8000 else v
        def key(k, mesh_is_c):
            t, p, a, b, c, fl = k
            if mesh_is_c:
                c = ids[c] if c else 0
            return '{%d,%d,%d,%d,%d,%d,%d,%d}' % (t, fx(p[0]), fx(p[1]), fx(p[2]), a, b, c, fl)
        def check(keys, what, actor=False):
            for i in range(len(keys) - 1):
                if keys[i + 1][0] < keys[i][0]:
                    raise SystemExit('Film: %s のキーの時刻が戻っている (%d → %d)' % (what, keys[i][0], keys[i + 1][0]))
                if 0 < keys[i + 1][0] - keys[i][0] < 2 and not keys[i][5] & self.FL_STEP:
                    raise SystemExit('Film: %s のキーの間が短すぎる (%d)' % (what, keys[i][0]))
                # 補間は 16 ビットの差で行うので、1 区間で 128 単位以上動くと回り込んで逆へ動く(継ぎ目でカメラが後ろへ下がった)
                hidden = actor and (keys[i][4] == 0 or keys[i + 1][4] == 0)   # 隠れている間の移動は見えない
                if keys[i + 1][0] > keys[i][0] and not keys[i][5] & self.FL_STEP and not hidden and \
                        max(abs(keys[i + 1][1][j] - keys[i][1][j]) for j in range(3)) >= 120:
                    raise SystemExit('Film: %s のキー %d → %d で 120 単位以上動く。間にキーを足す' % (what, keys[i][0], keys[i + 1][0]))
        check(self.cam, 'カメラ')
        out = ['/* tools/stage_data.py の opening() が生成。src/engine/op.c が読む */']
        out.append('#define N_CAMK %d' % len(self.cam))
        out.append('static const Key cam_k[] = {' + ','.join(key(k, False) for k in self.cam) + '};')
        flat, idx = [], [0]
        for i, keys in enumerate(self.acts):
            check(keys, '役者 %d' % i, True)
            flat += keys
            idx.append(len(flat))
        if len(flat) > 255 or len(self.acts) > 30:
            raise SystemExit('Film: 役者のキーが多すぎる')
        out.append('#define N_ACT %d' % len(self.acts))
        out.append('static const Key act_k[] = {' + ','.join(key(k, True) for k in flat) + '};')
        out.append('static const u8 act_i[] = {' + ','.join(map(str, idx)) + '};')
        evs = sorted(self.evs, key=lambda e: e[0])
        out.append('#define N_FEV %d' % len(evs))
        out.append('static const FilmEv film_ev[] = {' + ','.join('{%d,%d,%d,%s}' % (t, k, a, '"%s"' % s if s is not None else '0') for t, k, a, s in evs) + '};')
        return '\n'.join(out) + '\n'


def opening():
    """オープニング: 制圧された町 → 朝の農場 → 父が目を離した隙にヒナがさらわれる → 魔改造の戦闘機が飛び立つ →
    父は格納庫の零戦へ走り、乗り込み、追って飛び立つ。字幕に頼らず絵でわかるように作る。
    時刻は曲 OPENING の小節に合わせる(t90 の 1 小節 = 160 ティック、t180 の 1 小節 = 80 ティック。11 小節目 = 1600 から速くなる)"""
    s = Mod(0, 'OPENING', MORNING, 'OPENING', flags=SF_SCENE)
    # 人物(HINA・TERROR)・誘拐の戦闘機(RAIDER)・戦車(TANK)はモデルを入れず、op.c がスプライトで描く(役者のメッシュの番号で見分ける)
    s.models = ['ZERO', 'ZEROF', 'ZEROHANGAR', 'FARMHOUSE', 'TREE', 'SMOKE', 'SHIP', 'RAIDERM']
    # 地形: 北(+z)へまっすぐの道。0〜11 区画は農場の道、12 区画からは制圧された町(1 面と同じ町並み)。速さは 0(カメラは op.c が動かす)
    s.y0 = 0
    s.segs((224, 0, 0, 0))
    farm = strip(Mesh(), -2.5, 2.5, TER2)
    pats, over = towns()
    s.finish(lambda k: farm if k < 12 else pats[(k * 5) % len(pats)])
    del s.path[3:]                            # 経路は進まないので、初めの点だけ(区画の置き場所は finish で決まっている)
    f = Film()
    F = Film
    TOWN = 3                                  # 町の区画(3 × 4 = 12 から)
    BAR, T2 = 160, 1600                       # 前半の 1 小節、速くなる時刻
    HIDE = 0

    # ---- 役者 ----
    hina, t1, t2, raider, zero = f.actor(), f.actor(), f.actor(), f.actor(), f.actor()
    hangar, house, tree1, tree2 = f.actor(), f.actor(), f.actor(), f.actor()
    smoke1, smoke2, ship, tank1, tank2, tank3 = f.actor(), f.actor(), f.actor(), f.actor(), f.actor(), f.actor()

    # 1〜2 小節: 制圧された町(戦車が通りを進み、飛行船が浮かび、黒煙が上がる)。高いところからゆっくり降りる
    f.cam_key(0, (0, 11, 84), 0, -14, sect=TOWN)
    f.cam_key(2 * BAR, (0, 7, 100), 0, -8, sect=TOWN)
    f.key(smoke1, 0, 'SMOKE', (-12, 0, 132)); f.key(smoke2, 0, 'SMOKE', (13, 0, 146))
    f.key(ship, 0, 'SHIP', (12, 17, 130), 270); f.key(ship, 2 * BAR - 2, 'SHIP', (5, 17, 130), 270)
    f.key(tank1, 0, 'TANK', (-1.5, 0, 116), 180); f.key(tank1, 2 * BAR - 2, 'TANK', (-1.5, 0, 108), 180)
    f.key(tank2, 0, 'TANK', (2, 0, 128), 180); f.key(tank2, 2 * BAR - 2, 'TANK', (2, 0, 120), 180)
    f.key(tank3, 0, 'TANK', (-2, 0, 142), 180); f.key(tank3, 2 * BAR - 2, 'TANK', (-2, 0, 134), 180)
    for a in (tank1, tank2, tank3):
        f.key(a, 2 * BAR, HIDE, (0, 0, 0))
    # 町は農場から北へ約 110 単位(遠景の黒煙と飛行船だけを置き直す)
    f.key(smoke1, 2 * BAR, 'SMOKE', (26, 0, 108), cut=True); f.key(smoke2, 2 * BAR, 'SMOKE', (40, 0, 98), cut=True)
    f.key(ship, 2 * BAR, 'SHIP', (34, 24, 104), 270, cut=True)
    f.ev(20, F.FE_SUB, 0, 'THE TOWN FELL AT DAWN.')
    f.ev(2 * BAR, F.FE_SUB, 0, '')

    # 農場の配置: 父は庭(2, -2)。家は東、格納庫(赤い納屋)は南西で北へ開き、中に零戦が北を向いて止まる
    for a in (hina, t1, t2, raider, zero, hangar, house, tree1, tree2):
        f.key(a, 0, HIDE, (0, 0, 0))
    f.key(house, 2 * BAR, 'FARMHOUSE', (17, 0, 1), 270)
    # 零戦は納屋の前の外に止める(格納庫の中だと、目の高さの真正面からしか見えず、主翼が線にしか見えなかった)
    f.key(hangar, 2 * BAR, 'ZEROHANGAR', (7, 0, -27), 180)        # 零戦の向こうに重ならないよう、南東に
    f.key(zero, 2 * BAR, 'ZERO', (-8, 0, -14), 0)
    f.key(tree1, 2 * BAR, 'TREE', (-21, 0, 8)); f.key(tree2, 2 * BAR, 'TREE', (11, 0, 22))

    # 3〜4 小節: 朝の農場。ヒナが庭で跳ねて遊ぶ。父は家のほうへ目をやる(のどかな旋律)
    eye = 1.6
    p0 = (2, eye, -2)
    f.cam_key(2 * BAR, p0, 0, -12)
    f.cam_key(3 * BAR, p0, 0, -12, fl=F.FL_EASE)
    f.cam_key(3 * BAR + 50, p0, 70, 0)                              # 家を見る(目を離す)
    f.key(hina, 2 * BAR, 'HINA', (2.3, 0, 1.8), 180, fl=F.FL_BOB)
    f.key(hina, 3 * BAR + 70, 'HINA', (2.3, 0, 1.8), 180)
    # 父が目を離している間に、戦闘機が道に降り、テロリストがヒナをつかむ
    CAR = 3 * BAR + 80
    f.ev(CAR - 20, F.FE_SE, 10)                                          # 轟音(SE_BOSS)
    # 父が家を見ている間に、轟音とともに戦闘機が家の上をかすめ、北の道へ降りていく(横から見えるので 3D で描く)
    f.key(raider, CAR - 30, 'RAIDERM', (34, 14, -22), -32, roll=-25)
    f.key(raider, CAR + 30, 'RAIDERM', (14, 4.5, 10), -32, roll=-15)
    f.key(raider, CAR + 60, 'RAIDERM', (5, 2, 21), -20)
    f.key(raider, CAR + 80, 'RAIDER', (0, 0, 24), 0, cut=True)
    # 5〜6 小節(暗い主題): 振り返ると、黒ずくめの男がヒナを肩に担いで戦闘機へ走っている。もう一人が銃を構えて父を止める
    BACK = 4 * BAR - 20
    f.cam_key(BACK, p0, 70, 0, fl=F.FL_EASE)
    f.cam_key(BACK + 30, p0, 0, 0)
    run0, run1 = (2.6, 0, 4.5), (1.2, 0, 21.4)
    f.key(t1, CAR, 'TERROR', run0, 0, fl=F.FL_BOB)
    f.key(t1, 4 * BAR + 220, 'TERROR', run1, 0)
    carry = lambda p: p                     # 担がれたヒナのスプライトは誘拐犯と同じ足もとに置く(絵が肩の上にある)
    f.key(hina, CAR, 'HINA', carry(run0), 0, roll=90, fl=F.FL_BOB, cut=True)
    f.key(hina, 4 * BAR + 220, 'HINA', carry(run1), 0, roll=90)
    f.key(hina, 4 * BAR + 240, 'HINA', (0, .5, 22.6), 0, roll=90)  # カプセルへ入れられる
    f.key(hina, 4 * BAR + 250, HIDE, (0, 0, 0))
    f.ev(4 * BAR + 40, F.FE_VOICE, 9)                               # 「Papa!」(VOICE_PAPA)
    f.key(t1, 4 * BAR + 250, 'TERROR', run1, 0)
    f.key(t1, 4 * BAR + 290, 'TERROR', (-1.6, 0, 25), 0, fl=F.FL_BOB)
    f.key(t1, 4 * BAR + 300, HIDE, (0, 0, 0))                        # 乗り込む
    f.key(t2, CAR, 'TERROR', (-.6, 0, 4.5), 180)                    # 2 人目は父の前に立ちはだかり、銃を向ける
    f.key(t2, 4 * BAR + 262, 'TERROR', (-.6, 0, 4.5), 180)
    f.key(t2, 4 * BAR + 270, 'TERROR', (-.6, 0, 4.5), 0, fl=F.FL_BOB)
    f.key(t2, 4 * BAR + 310, 'TERROR', (-1.8, 0, 23), 0)
    f.key(t2, 4 * BAR + 320, HIDE, (0, 0, 0))
    # 父は追おうとするが、2 人目に銃を向けられて数歩で止まる(5 小節目〜6 小節目)
    p1 = (1.8, eye, 1.2)
    f.cam_key(4 * BAR + 20, p0, 0, 0, fl=F.FL_BOB)
    f.cam_key(4 * BAR + 300, p1, 0, 0)
    # 7〜8 小節: 戦闘機は道を滑って飛び立ち、右へ傾いて町のほうへ消える。父は見上げる
    TO = 6 * BAR
    f.key(raider, TO, 'RAIDER', (0, 0, 24), 0)
    f.key(raider, TO + 50, 'RAIDER', (0, 0, 30), 0)
    f.key(raider, TO + 100, 'RAIDER', (0, 0, 48), 0)
    f.key(raider, TO + 140, 'RAIDER', (0, 2.5, 68), 0)
    f.key(raider, TO + 190, 'RAIDER', (3, 9, 90), 8, roll=-20)
    f.key(raider, TO + 260, 'RAIDER', (14, 20, 110), 20, roll=-30)
    f.key(raider, TO + 300, 'RAIDER', (22, 26, 120), 25, roll=-30)
    f.key(raider, TO + 302, HIDE, (0, 0, 0))
    f.ev(TO, F.FE_SE, 10)
    f.cam_key(TO + 100, p1, 0, 0, fl=F.FL_EASE)
    f.cam_key(TO + 220, p1, 6, 12, fl=F.FL_EASE)
    f.cam_key(TO + 300, p1, 10, 10)
    # 9 小節: 振り返り、格納庫へ走る
    TURN = 8 * BAR
    f.cam_key(TURN, p1, 10, 10, fl=F.FL_EASE)
    f.cam_key(TURN + 40, p1, -157, 0, fl=F.FL_BOB)
    p2 = (-2.5, 2.5, -8.5)                                           # 零戦の右斜め前。横顔(長い風防・丸い尾翼・黒いカウリング)と主翼の上面が見えるよう、目線を少し上げる
    f.cam_key(9 * BAR - 20, p2, -135, -12, fl=F.FL_EASE)
    f.cam_key(9 * BAR + 20, p2, -132, -12, fl=F.FL_EASE)
    # 10 小節(スネアのロール): 零戦の左へ回り、翼から乗り込み、前を向いて座る
    f.cam_key(9 * BAR + 60, (-5.8, eye, -11), -120, 0, fl=F.FL_EASE)
    f.cam_key(9 * BAR + 110, (-6.8, 2.5, -13), -60, 8, fl=F.FL_EASE)
    cock = (-8, 2.9, -13.4)
    f.cam_key(10 * BAR - 12, cock, 0, 9)
    # 11〜12 小節(速くなる): 計器盤が見え、エンジンがかかる。13〜16 小節: 格納庫から出て滑走し、離陸
    f.ev(T2, F.FE_COCKPIT, 0)
    f.ev(T2, F.FE_SHAKE, 24)
    f.key(zero, T2, HIDE, (0, 0, 0))
    f.cam_key(T2, cock, 0, 9, fl=F.FL_SHAKE)
    f.cam_key(T2 + 80, cock, 0, 9, fl=F.FL_SHAKE)
    f.cam_key(T2 + 140, (-8, 2.85, 0), 0, 9, fl=F.FL_SHAKE)
    f.cam_key(T2 + 190, (-8, 2.5, 20), 0, 2, fl=F.FL_SHAKE)
    f.cam_key(T2 + 225, (-8, 4, 44), 0, 8)
    f.cam_key(T2 + 260, (-8, 10, 66), 0, 12)
    # 17〜18 小節: 外から。零戦が頭上を越え、黒煙の上がる町へ向かって小さくなる(最後の和音)
    OUT = T2 + 260
    f.ev(OUT, F.FE_COCKPIT, 1)
    f.ev(OUT + 2, F.FE_SUB, 0, "LET'S GO.")
    f.ev(OUT + 150, F.FE_SUB, 0, 'THEY LAUNCH HER IN 6 HOURS.')
    f.ev(OUT, F.FE_SE, 10)
    f.key(zero, OUT, 'ZEROF', (-8, 9, 62), 0, roll=0)
    f.key(zero, OUT + 70, 'ZEROF', (-6, 17, 90), 10, roll=-15)
    f.key(zero, OUT + 140, 'ZEROF', (-1, 25, 115), 8, roll=-5)
    f.key(zero, 2250, 'ZEROF', (6, 38, 170), 5)
    camx = (6, 1.4, 76)
    f.cam_key(OUT, camx, -126, 10)
    f.cam_key(OUT + 70, camx, -40, 38)
    f.cam_key(OUT + 140, camx, -14, 30, fl=F.FL_EASE)
    f.cam_key(2250, camx, -1, 20)
    f.key(smoke1, OUT, 'SMOKE', (-6, 0, 180), cut=True); f.key(smoke2, OUT, 'SMOKE', (14, 0, 188), cut=True)
    f.key(ship, OUT, 'SHIP', (6, 34, 184), 270, cut=True)
    f.ev(2260, F.FE_END)
    s.film = f
    s.op_base = 0x9400
    return s

def seam1():
    """1 面の後の継ぎ目(モジュール 15)。曲 BRIDGE(t128、8 小節 = 900 ティック。1 小節 112.5)に合わせる。
    海の上を外から見た零戦が北へ飛ぶ → 操縦席から、遠くに誘拐犯の戦闘機(ヒナのカプセル)と、無線のヒナの声 →
    水平線に港が現れ、港から空へレーザーが伸びる(2 面の港の基地のレーザー戦車の前振り)"""
    s = Mod(15, 'SEAM 1', SEA, 'BRIDGE', flags=SF_SCENE)
    s.models = ['ZEROF', 'CRANE', 'DEPOT', 'BEAM', 'CLOUDP']
    s.y0 = 0
    s.segs((16, 0, 0, 0))
    s.finish(lambda k: None)
    del s.path[3:]
    f = Film()
    F = Film
    B = 112.5
    HIDE = 0
    zero, jet = f.actor(), f.actor()
    clouds = [f.actor() for _ in range(3)]
    crane1, crane2, depot, beam = f.actor(), f.actor(), f.actor(), f.actor()
    for a in [zero, jet, crane1, crane2, depot, beam] + clouds:
        f.key(a, 0, HIDE, (0, 0, 0))
    # 1〜2 小節: 海の上。外から見た零戦が左をかすめて北へ(カメラは振り返って追う)
    cam = (5, 4, 10)
    f.cam_key(0, cam, -160, 6)
    f.cam_key(110, cam, -95, 10, fl=F.FL_EASE)
    f.cam_key(225, cam, 0, 6)
    f.key(zero, 0, 'ZEROF', (-6, 5, -30), 0, roll=10)
    f.key(zero, 110, 'ZEROF', (-1, 7, 12), 0, roll=-10)
    f.key(zero, 224, 'ZEROF', (3, 10, 60), 0)
    f.key(zero, 226, HIDE)
    f.key(clouds[0], 0, 'CLOUDP', (-14, 12, 30))
    f.key(clouds[1], 0, 'CLOUDP', (16, 16, 70))
    # 3〜5 小節: 操縦席。遠くに誘拐犯の戦闘機。無線でヒナの声
    T = int(2 * B)
    f.ev(T, F.FE_COCKPIT, 0)
    v = .3                                     # 1 ティックに進む単位
    end = 900
    for t in range(T, end, 150):               # 1 区間で 120 単位を超えないよう、150 ティックごとにキーを置く
        f.cam_key(t, (3, 10, 60 + v * (t - T)), 0, 2)
    f.cam_key(end, (3, 10, 60 + v * (end - T)), 0, 2)
    f.key(jet, T, 'RAIDER', (8, 17, 112), 0)                       # 正面のやや上(高すぎると画面の上へ外れた)
    f.key(jet, int(5 * B), 'RAIDER', (6, 17, 212), 0)
    f.key(jet, end, 'RAIDER', (2, 19, 325), 0)
    # そばを流れる雲(速さを見せる)
    zc = lambda t: 60 + v * (t - T)
    f.key(clouds[0], T, 'CLOUDP', (-10, 13, zc(T) + 60), cut=True); f.key(clouds[0], T + 200, 'CLOUDP', (-10, 13, zc(T) + 60))
    f.key(clouds[1], T, 'CLOUDP', (14, 6, zc(T) + 110), cut=True); f.key(clouds[1], T + 360, 'CLOUDP', (14, 6, zc(T) + 110))
    f.key(clouds[2], T + 150, 'CLOUDP', (-6, 8, zc(T + 150) + 100)); f.key(clouds[2], T + 450, 'CLOUDP', (-6, 8, zc(T + 150) + 100))
    f.ev(int(3 * B) + 20, F.FE_VOICE, 6)                            # 「Papa, hurry!」(VOICE_HURRY)
    f.ev(int(3 * B) + 20, F.FE_CAP, 2, 'PAPA, HURRY!')
    # 6〜8 小節: 水平線に港。港から空へレーザーが伸びて光る(戦闘機はその上を越えていく)
    H = 300                                    # 港の z(カメラは最後に 60 + 0.3 × 675 ≒ 262。座標は 256 で回り込むので、カメラから 120 以内に置く)
    f.key(crane1, int(5 * B), 'CRANE', (-14, 0, H), 90)
    f.key(crane2, int(5 * B), 'CRANE', (10, 0, H + 8), 270)
    f.key(depot, int(5 * B), 'DEPOT', (-2, 0, H - 4), 180)
    for i, t0 in enumerate((int(6 * B), int(6.6 * B), int(7.2 * B))):
        f.key(beam, t0, 'BEAM', ((-5, -1, -3)[i], 12, H + 2))
        f.key(beam, t0 + 40, HIDE)
        f.ev(t0, F.FE_SE, 11)                                          # SE_LASER
    f.ev(int(6 * B) + 20, F.FE_CAP, 3, 'THEY HAVE LASERS')           # 赤(水色は青空に溶けた)
    f.ev(end, F.FE_END)
    s.film = f
    s.op_base = 0x9000
    return s

def seam_mod(n, name, pal, flags=0):
    """継ぎ目の映像の場面のモジュール(地形なし。曲は BRIDGE: t128、8 小節 = 900 ティック、1 小節 112.5)"""
    s = Mod(n, name, pal, 'BRIDGE', flags=SF_SCENE | flags)
    s.op_base = 0x9000                         # 演出のコード(Makefile の OPn_BASE と同じ値)
    s.y0 = 0
    s.segs((16, 0, 0, 0))
    s.finish(lambda k: None)
    del s.path[3:]
    return s


def cruise(f, t0, t1, p0, v, pitch=2, climb=0.0, yaw=0):
    """操縦席のカメラ: t0 から t1 まで、p0 から北へ 1 ティック v 単位、climb ずつ昇る(120 単位を超えないよう 150 ティックごとにキー)"""
    ts = list(range(t0, t1, 150)) + [t1]
    for t in ts:
        f.cam_key(t, (p0[0], p0[1] + climb * (t - t0), p0[2] + v * (t - t0)), yaw, pitch)
    return lambda t: (p0[0], p0[1] + climb * (t - t0), p0[2] + v * (t - t0))


def seam2():
    """2 面の後(港 → 谷、夕方)。夕日の荒れ地の先に台地。誘拐犯の戦闘機は谷へ降り、P-51 が迎え撃ちに上がってくる"""
    s = seam_mod(16, 'SEAM 2', DUSK)
    s.models = ['MESA', 'MUSTANG', 'CLOUDP']
    f = Film(); F = Film; B = 112.5; end = 900
    jet, m1, m2, m3, p1, p2, cl = [f.actor() for _ in range(7)]
    for a in (jet, m1, m2, m3, p1, p2, cl):
        f.key(a, 0, 0, (0, 0, 0))
    f.ev(0, F.FE_COCKPIT, 0)
    cam = cruise(f, 0, end, (0, 14, 0), .3)
    f.key(cl, 0, 'CLOUDP', (-12, 18, 70)); f.key(cl, 300, 'CLOUDP', (-12, 18, 70))
    f.key(jet, 0, 'RAIDER', (4, 18, 60), 0)
    f.key(jet, int(3 * B), 'RAIDER', (3, 16, 150), 0)
    f.key(jet, int(6 * B), 'RAIDER', (0, 6, 250), 0)                 # 谷へ降りていく
    f.key(jet, end, 'RAIDER', (0, 2, 330), 0)
    f.ev(int(2 * B), F.FE_VOICE, 6)                                  # 「Papa, hurry!」
    f.ev(int(2 * B), F.FE_CAP, 2, 'PAPA, HURRY!')
    for a, (x, z) in zip((m1, m2, m3), ((-14, 250), (12, 262), (-4, 290))):
        f.key(a, int(3.5 * B), 'MESA', (x, 0, z), 180)
    # 6〜8 小節: 台地の間から P-51 が 2 機、こちらへ上がってくる
    t = int(4.5 * B)
    for a, x in ((p1, -5), (p2, 6)):
        z0 = cam(t)[2] + 90
        f.key(a, t, 'MUSTANG', (x, 4, z0), 180)
        f.key(a, t + 180, 'MUSTANG', (x * .6, 13, z0 - 25), 180)
        f.key(a, end, 'MUSTANG', (x * .4, 15, cam(end)[2] + 10), 180, roll=30)
    f.ev(t + 20, F.FE_SE, 4)                                         # SE_ALARM
    f.ev(t + 30, F.FE_CAP, 3, 'BANDITS!')
    f.ev(end, F.FE_END)
    s.film = f
    return s


def seam3():
    """3 面の後(谷 → 雲海、夜)。雲を抜けて上へ。振り返ると、ロケットを積んだ P-51 が後ろに食いついている"""
    s = seam_mod(17, 'SEAM 3', NIGHT)
    s.models = ['RMUSTANG', 'CLOUDP']
    f = Film(); F = Film; B = 112.5; end = 900
    c1, c2, c3, p1, p2 = [f.actor() for _ in range(5)]
    for a in (c1, c2, c3, p1, p2):
        f.key(a, 0, 0, (0, 0, 0))
    f.ev(0, F.FE_COCKPIT, 0)
    # 1〜4 小節: 機首を上げて雲を抜ける
    cam = cruise(f, 0, int(4 * B), (0, 6, 0), .28, pitch=12, climb=.06)
    for a, (x, y, z, t0) in zip((c1, c2, c3), ((-6, 14, 40, 0), (8, 22, 90, 120), (-3, 30, 150, 260))):
        f.key(a, t0, 'CLOUDP', (x, y, z)); f.key(a, t0 + 200, 'CLOUDP', (x, y, z))
    # 5〜8 小節: 雲の上で水平に。警報、振り返ると後ろに 2 機
    t = int(4 * B)
    p = cam(t)
    tl = int(4.6 * B)
    cruise(f, t, tl, p, .28, pitch=0)
    f.ev(tl, F.FE_SE, 4)
    f.ev(tl, F.FE_VOICE, 5)                                          # 「Warning!」
    f.ev(tl + 20, F.FE_CAP, 3, 'ON YOUR TAIL!')
    zc = lambda tt: p[2] + .28 * (tt - t)
    turn0, turn1 = tl + 30, tl + 90
    f.cam_key(turn0, (p[0], p[1], zc(turn0)), 0, 0, fl=F.FL_EASE)
    f.cam_key(turn1, (p[0], p[1], zc(turn1)), 175, 4)
    f.cam_key(int(7.2 * B), (p[0], p[1], zc(int(7.2 * B))), 178, 4, fl=F.FL_EASE)
    f.cam_key(end, (p[0], p[1], zc(end)), 0, 0)
    for a, x in ((p1, -4), (p2, 5)):
        f.key(a, tl, 'RMUSTANG', (x, p[1] + 2, zc(tl) - 40), 0)
        f.key(a, int(6.5 * B), 'RMUSTANG', (x * .6, p[1] + .5, zc(int(6.5 * B)) - 9), 0, roll=15 if x < 0 else -15)
        f.key(a, end, 'RMUSTANG', (x * .6, p[1] + .5, zc(end) - 8), 0)
    f.ev(end, F.FE_END)
    s.film = f
    return s


def seam4():
    """4 面の後(雲海 → 成層圏、明け方)。遠くでロケットが打ち上がり、白い煙を引いて空へ。ヒナを乗せている"""
    s = seam_mod(18, 'SEAM 4', TWILIGHT)
    s.models = ['ROCKETL', 'PUFF', 'CLOUDP']
    f = Film(); F = Film; B = 112.5; end = 900
    rk, c1 = f.actor(), f.actor()
    puffs = [f.actor() for _ in range(5)]
    for a in [rk, c1] + puffs:
        f.key(a, 0, 0, (0, 0, 0))
    f.ev(0, F.FE_COCKPIT, 0)
    cam = cruise(f, 0, end, (0, 20, 0), .22, pitch=8, climb=.02)
    f.key(c1, 0, 'CLOUDP', (10, 16, 60)); f.key(c1, 300, 'CLOUDP', (10, 16, 60))
    # 2 小節目から、正面の遠く(100 単位先)でロケットが上がる。昇りながら白い煙を残す
    t0 = int(1.5 * B)
    zr = cam(t0)[2] + 45
    path = lambda t: (4, 4 + .05 * (t - t0), zr + .22 * (t - t0))    # カメラと同じ速さで遠ざかり、大きさを保つ(遅いと追い越して消えた)
    for t in list(range(t0, end, 300)) + [end]:  # 1 区間で 120 単位を超えないよう刻む
        f.key(rk, t, 'ROCKETL', path(t))
    for i, a in enumerate(puffs):
        tp = t0 + 40 + i * 110
        f.key(a, tp, 'PUFF', path(tp - 30))
        f.key(a, end, 'PUFF', path(tp - 30))
    f.ev(t0, F.FE_SE, 10)                                            # 轟音
    f.ev(int(3 * B), F.FE_CAP, 2, 'THE ROCKET!')
    f.ev(int(5 * B), F.FE_VOICE, 6)                                  # 「Papa, hurry!」
    f.ev(int(5 * B), F.FE_CAP, 2, 'PAPA, HURRY!')
    f.ev(end, F.FE_END)
    s.film = f
    return s


def seam5():
    """5 面の後(成層圏 → 軌道)。星空へ抜けると、遠くに鍵穴の形の基地。先に上がったロケットがそこへ向かう"""
    s = seam_mod(19, 'SEAM 5', SPACE, SF_SPACE)
    s.models = ['B_KEYHOLE', 'ROCKETL']
    f = Film(); F = Film; B = 112.5; end = 900
    kh, rk = f.actor(), f.actor()
    for a in (kh, rk):
        f.key(a, 0, 0, (0, 0, 0))
    f.ev(0, F.FE_COCKPIT, 0)
    cam = cruise(f, 0, end, (0, 40, 0), .05, pitch=4)
    # 鍵穴の基地は半径が 22 あり、90 単位より遠いと描かれない(mesh_draw の視野の判定)。80 単位先から近づく
    t0 = int(2 * B)
    zk = cam(t0)[2] + 85                                             # 最後に 50 単位ほど先(近すぎると画面を覆った)
    f.key(kh, t0, 'B_KEYHOLE', (0, 52, zk), 180)
    f.key(kh, end, 'B_KEYHOLE', (0, 52, zk), 180)
    f.key(rk, t0, 'ROCKETL', (6, 44, zk - 50))
    f.key(rk, end, 'ROCKETL', (1, 50, zk - 8))
    f.ev(int(4 * B), F.FE_VOICE, 7)                                  # 「I can see you!」(VOICE_SEE)
    f.ev(int(4 * B), F.FE_CAP, 2, 'I CAN SEE YOU!')
    f.ev(end, F.FE_END)
    s.film = f
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

MODS = [opening(), s1(), s2(), s3(), s4(), s5(), s6(), ending(), seam1(), seam2(), seam3(), seam4(), seam5()]
