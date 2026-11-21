#!/usr/bin/env python3
"""8 つのモジュールの定義: 0 = オープニング、1〜6 = 面、7 = エンディング(指示書 7 章)"""
import math
import re
from content import *
from film_spr import Subject
import gen_font

EV_SPAWN, EV_BOSS, EV_ROLL, EV_PROMPT, EV_TEXT, EV_SUB, EV_VOICE, EV_BGM, EV_PAL, EV_LOOP, EV_END, EV_CAM, EV_ITEM, EV_PROP, EV_FADE = range(15)
PR_ROLL, PR_LOOP, PR_DIVE = 1, 2, 3
E01, E02, E03, E04, E05, E06, E07, E08, E09, E10, SUPPLY, MEDIC = range(1, 13)
P_PARALLEL, P_HOLD, P_PASS, P_TAIL, P_CROSS, P_DRIFT, P_BOUNCE, P_FALL, P_LIFT, P_WEAVE, P_ORBIT, P_SWOOP = range(1, 13)
V_ROLL, V_LOOP, V_DIVE, V_FIRE, V_WARNING, V_HURRY, V_SEE, V_NOPAPA, V_PAPA, V_GIVE = range(1, 11)
SF_SPACE, SF_SCENE, SF_DEEP = 1, 2, 4
ENEMY_MODELS = {E01: 'BIKE', E02: 'TANK', E03: 'LTANK', E04: 'MUSTANG', E05: 'SHIP', E06: 'RMUSTANG', E07: 'MINE', E08: 'LSAT', E09: 'BATTLESHIP', E10: 'PTBOAT'}
SONG = {}
with open('src/sound/songs.mml', encoding='utf8') as f:
    for line in f:
        m = re.match(r'@song (\w+)', line)
        if m:
            SONG[m.group(1)] = len(SONG) + 1


class Mod:
    def __init__(self, n, name, pal, bgm='', flags=0, clock=0, radio='', line=''):
        self.n, self.name, self.pal, self.flags, self.clock = n, name, pal, flags, clock
        self.weapon = 0                 # ボスの秘密兵器(src/engine/stg.c の W_。7 = 全部を順に)。面には stg.c を付ける
        self.pal2 = pal
        self.bgm = SONG.get(bgm, 0)
        self.sections, self.events = [], []
        self.strs = [radio, line]       # 0 = 継ぎ目の無線、1 = ボスを倒したときの父の一言
        self.film = None                # 映像の場面(Film。オープニングと継ぎ目)
        self.ahead = 8                  # 道中に描く区画の数(1 区画 8 単位)。多いほど遠くまで見えるが重い
        self.op_base = 0                # 演出のコードの置き場所(Makefile の OPn_BASE / STGn_BASE と同じ値)
        self.stg = 1 <= n <= 6 or n == 21   # 面: 面のコード(stg.c)を呼ぶ(tools/mkrom.py が見出しに番地を書く)
        self.models = ['FLAK', 'ROCKET', 'SUPPLY', 'MEDIC']
        self.boss = None
        self._p = []          # 点ごとの (x, y, z, yaw_rad, spd)

    def segs(self, *segs):
        """(長さ, ヨー変化[度], 高さの変化, 速度) の列。長さは 2 の倍数(周回区間の初めは 8 の倍数)。
        lap_segs の区間(ヨー変化が LAP)は、敵が残っている間に繰り返すまっすぐな区間"""
        x, y, z, yaw = 0.0, self.y0, 0.0, 0.0
        self.circles = []
        m = 0
        out = []
        for ln, dyaw, dy, spd in segs:
            if dyaw == LAP:
                assert m % 8 == 0 and ln % 8 == 0, (self.name, m)
                self.circles.append(m)
                dyaw = 0
            out.append((ln, dyaw, dy, spd))
            m += ln
        for ln, dyaw, dy, spd in out:
            n = ln // 2
            for i in range(n):
                self._p.append((x, y, z, yaw, spd))
                yaw += math.radians(dyaw) / n
                x += 2 * math.sin(yaw)
                z += 2 * math.cos(yaw)
                y += dy / n
        for i in range(3 if self.flags & SF_SCENE else 8):     # 終わりの先の余り(場面は経路を進まないので少しでよい)
            self._p.append((x, y, z, yaw, segs[-1][3]))
            x += 2 * math.sin(yaw)
            z += 2 * math.cos(yaw)

    y0 = 8.0
    sec_y = 0

    def wrap(self, v):
        v = int(round(v * 256)) & 0xFFFF
        return v - 0x10000 if v >= 0x8000 else v

    def finish(self, pat):
        """区画(8 単位ごと。経路の点を兼ねる)を作る。pat(k) = 区画 k のメッシュ"""
        ps = self._p
        n = len(ps) // 4
        if n < 3:
            raise SystemExit('stage_data: %s の区画が %d しかない(3 つ以上ないと場面がすぐ終わる)' % (self.name, n))
        if n > 250:
            raise SystemExit('stage_data: %s の経路が長すぎる(%d 区画。250 まで)' % (self.name, n))
        for k in range(n):
            x, y, z, yaw, spd = ps[k * 4]
            nx = ps[min(k * 4 + 4, len(ps) - 1)]
            pitch = math.atan2(nx[1] - y, 8.0)
            self.sections.append({'mesh': pat(k), 'x': self.wrap(x), 'y': self.wrap(self.sec_y), 'z': self.wrap(z), 'spd': spd,
                                  'yaw': int(round(yaw * 128 / math.pi)) & 255, 'py': self.wrap(y), 'pitch': int(round(pitch * 128 / math.pi))})

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
        """n 番目の周回区間(まっすぐ LAP_LEN 単位)に、敵が残っていれば初めへ戻る命令を置く"""
        a = self.circles[n]
        self.ev(a + LAP_LEN - 2, EV_LOOP, x=a)

    def setboss(self, at, mov, dist, parts, pos=(0, 0, 0)):
        for p in parts:
            if p[0] not in self.models:
                self.models.append(p[0])
        # 指示書の耐久のままだとバルカン 10 発/秒で数秒で終わるので、ボスの部位は 3 倍にする(飾りと耐久 1 の部位はそのまま)
        parts = [p[:4] + (min(255, p[4] * 3) if p[4] > 1 else p[4],) + p[5:] for p in parts]
        self.boss = {'mov': mov, 'dist': dist, 'parts': parts}
        at = self.circles[-1] - 16      # 最後の周回区間の手前で現れ、その区間を回りながら戦う
        x, y, z = pos
        self.ev(at, EV_BOSS, x=self.wrap(x), y=self.wrap(y), z=self.wrap(z))

    def end(self):
        # 最後のまっすぐな区間(ボスを倒した後の余韻。面の速さで約 6 秒)を飛び切ったら終える
        self.ev(len(self._p) * 2 - 24, EV_END)


LAP = 'LAP'
LAP_LEN = 128


def lap_segs(spd):
    """周回区間: まっすぐ LAP_LEN 単位(敵が残っている間は初めへ戻って繰り返す。前は右へ 1 周する円で、同じ所を旋回して見えた)。
    区画の絵は 16 区画ごとに繰り返されるので、区間の中に一度きりの目印を置かない"""
    return [(LAP_LEN, LAP, 0, spd)]


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

def ahead_alt(s, m, d=0.0):
    """経路の位置 m の高さ + d(高さが変わる面で、敵を経路に合わせて置く)"""
    return s.at(m)[1] + d


def s1():
    s = Mod(1, 'STAGE 1 / THE TOWN', MORNING, 'STAGE1', radio='HOLD ON, HINA.', line='HOT AIR.')
    s.y0 = 6
    s.weapon = 1                        # 秘密兵器: 気球の爆弾
    sp = 14     # 低く飛ぶ面なので、ほかの面(20〜26)より遅く。20 だとロックした戦車へ誘導弾が届く前に通り過ぎ、倒したか見えなかった
    s.segs((96, 0, 0, sp), (32, 30, 0, sp), (32, -30, 0, sp), *lap_segs(sp), (64, 0, 0, sp), (32, -35, 0, sp), (32, 35, 0, sp), *lap_segs(sp),
           (64, 0, 0, sp), (48, 25, 0, sp), (48, -25, 0, sp), (64, 0, 0, sp), (32, 20, 0, sp), (32, -20, 0, sp), *lap_segs(sp),
           (32, 0, 0, sp), *lap_segs(13), (40, 0, 0, 13))
    pats, over = towns()
    s.finish(lambda k: over if k in (42, 78) else pats[(k * 5 + k // 7) % len(pats)])
    # 周回区間 0: 160-288、1: 416-544、2: 832-960、ボス: 992-1120
    s.lap(0); s.lap(1); s.lap(2); s.lap(3)
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
    for at in (350, 372, 394):
        s.spawn(at, E02, at + 45, 6 if at < 390 else -10, .8, P_HOLD); s.spawn(at, E02, at + 52, -6, .8, P_HOLD)
    for at in (430, 452, 474, 496):
        s.spawn(at, E01, at + 30, -3, .6, P_PARALLEL); s.spawn(at, E01, at + 30, 4, .6, P_PARALLEL)
    # 後半: 町の上に P-51 が降りてくる(蛇行・後ろから追い越す)。2 つ目の高架の下をくぐる
    s.text(548, 'P-51S!')
    for at in (552, 586, 620):
        s.spawn(at, E04, at + 70, -4, 9, P_WEAVE, 128); s.spawn(at, E04, at + 74, 5, 10, P_WEAVE, 128)
    for at in (570, 604, 638):
        s.spawn(at, E02, at + 50, -7, .8, P_HOLD); s.spawn(at, E01, at + 30, 3, .6, P_PARALLEL)
    s.item(600, SUPPLY, 650, 0, 8)
    s.prompt(616, PR_DIVE, 60)
    s.text(612, 'OVERPASS!')
    for at in (660, 700, 740):
        s.spawn(at, E04, at - 8, 0, 12, P_SWOOP, 128)
        s.spawn(at, E02, at + 46, 7, .8, P_HOLD); s.spawn(at, E02, at + 54, -7, .8, P_HOLD)
    s.item(720, MEDIC, 770, -2, 7)
    for at in (770, 796, 822, 848):
        s.spawn(at, E01, at + 30, -4, .6, P_PARALLEL); s.spawn(at, E04, at + 60, 0, 10, P_ORBIT, 128)
    s.item(930, MEDIC, 980, 2, 7)
    s.setboss(0, 0, 24, [
        ('B_BALLOON', -14, 2, 0, 6, 0, 0, 1), ('B_BALLOON', -7, 5, 6, 6, 0, 0, 1), ('B_BALLOON', 0, 2, 0, 6, 0, 0, 1),
        ('B_BALLOON', 7, 5, 6, 6, 0, 0, 1), ('B_BALLOON', 14, 2, 0, 6, 0, 0, 1)], s.at(1020, 0, 8))      # カメラ(6)の少し上。16 だと近づけた後は画面の上の端に寄った
    s.end()
    return s

def s2():
    s = Mod(2, 'STAGE 2 / THE HARBOR', NOON, 'STAGE2', radio='THEY HAVE LASERS, PAPA.', line='CRABS GO IN THE POT.')
    # 追っ手との空中戦が主なので、前半は高く(24)飛ぶ。中ほどで港の基地(レーザー戦車)へ降りて叩き、沖の艦隊を抜けてボスへ
    s.y0 = 24
    s.weapon = 2                        # 秘密兵器: 左右からの誘導弾
    sp = 22
    s.segs((104, 0, 0, sp), (24, 0, 0, sp), (40, 25, 0, sp), *lap_segs(sp), (48, -25, -8, sp), (32, 0, -6, sp), *lap_segs(sp),
           (64, 0, 0, sp), (48, -20, 0, sp), (48, 20, 0, sp), (96, 0, 0, sp), (64, 15, 0, sp), (64, -15, 0, sp), (96, 0, 0, sp), *lap_segs(sp),
           (32, 0, 0, sp), *lap_segs(16), (48, 0, 0, 16))
    q = strip(Mesh(), -40, -5, IRON)
    strip(q, 5, 60, CLOUD, y=0, detail=True)
    a = Mesh(); strip(a, -40, -5, IRON); a.tbox((-14, 2.5, 0), (9, 5, 7), TER1, side=TER2, top=IRON, skip='bk')
    b = Mesh(); strip(b, -40, -5, IRON); b.tbox((-8, 7, 0), (.8, 14, .8), ORANGE); b.tbox((-12, 13.5, 0), (10, .8, .8), ORANGE, detail=True)
    c = Mesh(); strip(c, -40, -5, IRON); c.tbox((-12, 1.2, 0), (3, 2.4, 6), RED, skip='b'); c.tbox((-8.5, 1.2, 0), (3, 2.4, 6), GREEN, skip='b'); c.tbox((-12, 3.6, 0), (3, 2.4, 6), CYAN, detail=True, skip='b')
    d = Mesh(); strip(d, -40, -5, IRON); d.tbox((22, 2, 0), (10, 4, 8), IRON, top=TER2, skip='bk'); d.tbox((22, 6, 2), (4, 4, 3), WHITE, detail=True, skip='b')
    pats = [q, a, c, q, b, a, d, c]
    s.finish(lambda k: pats[(k * 3 + k // 5) % len(pats)])
    # 周回区間 0: 168-296、1: 376-504、2: 984-1112、ボス: 1144-1272
    s.lap(0); s.lap(1); s.lap(2); s.lap(3)
    s.text(40, 'Bandits!')
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
    for at in (404, 430, 456, 482):
        s.spawn(at, E02, at + 36, -8, .8, P_HOLD); s.spawn(at, E04, at + 80, 0, 13, P_WEAVE, 128)
    # 後半: 沖の艦隊。右の海に戦艦が並び、魚雷艇が並走して撃ってくる
    s.text(520, 'BATTLESHIPS!')
    for at in (520, 590, 660, 730, 800, 870):
        s.spawn(at, E09, at + 70, 22 if at % 140 else 30, 0, P_HOLD)
    for at in (540, 600, 660, 720, 780, 840, 900):
        s.spawn(at, E10, at + 30, 9, .3, P_PARALLEL); s.spawn(at, E10, at + 36, 14, .3, P_PARALLEL)
    for at in (560, 640, 720, 800, 880):
        s.spawn(at, E04, at + 80, -4, 14, P_WEAVE, 128)
    s.prompt(690, PR_ROLL, 60)
    s.item(620, SUPPLY, 670, 0, 11); s.item(780, MEDIC, 830, 2, 11)
    for at in (920, 950, 980):
        s.spawn(at, E03, at + 56, -12, .8, P_HOLD); s.spawn(at, E04, at - 8, 0, 16, P_SWOOP, 128)
    s.item(1100, MEDIC, 1150, 2, 9)
    s.setboss(0, 0, 24, [
        ('B_CRAB', 0, -3, 0, 40, 9, 8, 0),
        ('B_MOUTH', -2, 4, -1, 10, 0, 0, CLR_LASER), ('B_MOUTH', 2, 4, -1, 10, 0, 0, CLR_LASER),
        ('B_CORE', 0, 1, -6, 40, 1, 2, 1)], s.at(1180, 0, 9))      # カメラ(10)とほぼ同じ高さ
    s.end()
    return s

def s3():
    s = Mod(3, 'STAGE 3 / THE CANYON', DUSK, 'STAGE3', radio='Papa, hurry!', line='THREE FOR ONE.')
    s.ahead = 11                        # 谷の壁を遠くまで見せる(8 区画だと、高く飛ぶ前半に遠くの壁が消えて平地に見えた)
    s.weapon = 3                        # 秘密兵器: P-51 の群れ
    # 前半は谷の上(28。壁は 24 まで)で追っ手と空中戦。中ほどで谷へ降り、谷底の基地(戦車)を叩きながら谷を抜けてボスへ
    s.y0 = 28
    sp = 24
    s.segs((80, 0, 0, sp), (40, 35, 0, sp), (40, -70, 0, sp), (40, 35, 0, sp), *lap_segs(sp), (56, 30, -10, sp), (56, -30, -11, sp), *lap_segs(sp),
           (64, 0, 0, sp), (48, 40, 0, sp), (48, -40, 0, sp), (64, 0, 0, sp), (48, -30, 0, sp), (48, 30, 0, sp), (96, 0, 0, sp), *lap_segs(sp),
           (24, 0, 0, sp), *lap_segs(18), (56, 0, 0, 18))
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
    s.finish(lambda k: None if k % 2 else br if k in (24, 78, 112) else pats[(k // 2 * 3) % len(pats)])
    # 周回区間 0: 200-328、1: 440-568、2: 984-1112、ボス: 1136-1264
    s.lap(0); s.lap(1); s.lap(2); s.lap(3)
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
    for at in (440, 470, 500):
        s.spawn(at, E04, at + 80, -2, 9, P_TAIL, 128)
    # 後半: 谷底を低く。前で輪を描く P-51 と、谷底の戦車
    s.text(576, 'IN THE CANYON!')
    s.roll(600, 24, 2); s.roll(650, 24, -2); s.roll(700, 24, 0)
    for at in (576, 612, 648, 684):
        s.spawn(at, E04, at + 60, 0, 9, P_ORBIT, 128); s.spawn(at, E02, at + 50, 5 if at % 72 else -5, .8, P_HOLD)
    s.item(660, SUPPLY, 700, 0, 7)
    for at in (720, 756, 792, 828):
        s.spawn(at, E04, at + 80, -2, 8, P_WEAVE, 128); s.spawn(at, E03, at + 56, 6, .8, P_HOLD)
    s.prompt(800, PR_ROLL, 60)
    for at in (860, 900, 940):
        s.spawn(at, E04, at - 8, 0, 12, P_SWOOP, 128); s.spawn(at, E04, at + 80, 3, 8, P_TAIL, 128)
    s.item(960, MEDIC, 1000, 0, 7)
    s.setboss(0, 0, 22, [
        ('B_HYDRA', -12, 0, 0, 20, 0, 16, 0x11), ('B_HYDRA', 6, 10, 0, 20, 0, 16, 0x11), ('B_HYDRA', 6, -10, 0, 20, 0, 16, 0x11)], s.at(1180, 0, 7))
    s.end()
    return s

def s4():
    s = Mod(4, 'STAGE 4 / THE CLOUD SEA', NIGHT, 'STAGE4', radio='THEY ARE ON YOUR TAIL!', line='TOO MUCH GAS.')
    # 雲の峰(18 まで)の上を飛ぶ(前は 12 で、雲の海の中に沈んで見えた)
    s.y0 = 20
    s.weapon = 4                        # 秘密兵器: 横一列の弾幕
    sp = 20
    s.segs((104, 0, 0, sp), (32, 20, 0, sp), *lap_segs(sp), (32, -20, 2, sp), (80, 0, 0, sp), *lap_segs(sp),
           (64, 0, 0, sp), (48, 25, 0, sp), (48, -25, 0, sp), (96, 0, 0, sp), (48, -15, 0, sp), (48, 15, 0, sp), (64, 0, 0, sp), *lap_segs(sp),
           (24, 0, 0, sp), *lap_segs(16), (48, 0, 0, 16))
    a = strip(Mesh(), -60, 60, CLOUD, detail=True)
    b = Mesh(); strip(b, -60, 60, CLOUD, detail=True); b.tbox((-16, 9, 0), (10, 18, 8), CLOUD, top=WHITE, side=TER1, skip='b')
    c = Mesh(); c.tbox((18, 7, 0), (12, 14, 10), CLOUD, top=WHITE, side=TER1, skip='b')
    d = Mesh(); d.prism_y((30, 40, 40), 5, .5, 8, WHITE, detail=False)
    pats = [a, Mesh().face([(-1, 0, 0), (0, 0, 1), (1, 0, 0)], CLOUD), b, a, c, a]
    s.finish(lambda k: d if k % 16 == 3 else pats[(k * 5) % len(pats)])
    # 周回区間 0: 136-264、1: 376-504、2: 920-1048、ボス: 1072-1200
    s.lap(0); s.lap(1); s.lap(2); s.lap(3)
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
    for at in (384, 412, 440, 468):
        s.spawn(at, E04, at + 80, 3, 22, P_TAIL, 128)
    # 後半: 雲の峰の間を、飛行船の艦隊と夜間戦闘機
    s.text(512, 'FLEET AHEAD!')
    for at in (512, 560, 608, 656, 704):
        s.spawn(at, E05, at + 64, -26, 27, P_CROSS); s.spawn(at, E04, at + 70, 4, 22, P_ORBIT, 128)
    s.roll(600, 42, 3); s.roll(690, 42, 3)
    s.item(640, SUPPLY, 690, 0, 23)
    for at in (740, 776, 812, 848, 884):
        s.spawn(at, E04, at + 80, -3, 22, P_WEAVE, 128); s.spawn(at, E04, at - 8, 2, 26, P_SWOOP, 128)
    s.prompt(800, PR_ROLL, 60)
    s.item(900, MEDIC, 940, 2, 22)
    parts = [('B_HULL', 0, 8, 10, 1, 9, 8, 0)]
    for k, (x, z) in enumerate(((-9, -12), (0, -8), (9, -12))):
        parts.append(('B_GONDOLA', x, -2, z, 15, 0, 0, CLR_FIBER))
    for x in (-6, -2, 2, 6):
        parts.append(('B_CORE', x, 2, -22, 10, 1, 2, 0))
    s.setboss(0, 0, 40, parts, s.at(1110, 0, 26))
    s.end()
    return s

def s5():
    s = Mod(5, 'STAGE 5 / THE STRATOSPHERE', TWILIGHT, 'STAGE5', radio='Papa, hurry!', line='NICE WINGS.')
    s.y0 = 22
    s.weapon = 5                        # 秘密兵器: 大きな誘導弾
    s.models.append('ROCKETL')
    sp = 26
    s.segs((80, 0, 8, sp), (48, 15, 8, sp), *lap_segs(sp), (48, -15, 8, sp), (64, 0, 6, sp), *lap_segs(sp),
           (64, 0, 4, sp), (48, 20, 4, sp), (48, -20, 4, sp), (96, 0, 4, sp), (48, 15, 2, sp), (48, -15, 2, sp), (64, 0, 2, sp), *lap_segs(sp),
           (24, 0, 0, sp), *lap_segs(18), (56, 0, 0, 18))
    a = strip(Mesh(), -60, 60, CLOUD, detail=True)
    b = Mesh().prism_y((-14, 40, 0), 3, 3, 8, IRON, top=WHITE)
    c = Mesh(); c.tbox((14, 34, 0), (1, 40, 1), RED); c.tbox((14, 54, 0), (5, 1, 5), IRON, detail=True)
    pats = [a, Mesh().face([(-1, 0, 0), (0, 0, 1), (1, 0, 0)], CLOUD), b, a]
    s.finish(lambda k: c if k == 66 else pats[(k * 3) % len(pats)])
    # 周回区間 0: 128-256、1: 368-496、2: 912-1040、ボス: 1064-1192
    s.lap(0); s.lap(1); s.lap(2); s.lap(3)
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
    for at in (392, 420, 448, 476):
        s.spawn(at, E04, at + 80, 3, 64, P_TAIL, 128)
    # 後半: さらに昇る。ロケットを積んだ P-51 の編隊
    s.text(504, 'ROCKET SQUADRON!')
    for at in (504, 540, 576, 612, 648):
        s.spawn(at, E06, at + 70, -3, ahead_alt(s, at + 70, 1), P_WEAVE, 128); s.spawn(at, E06, at + 76, 4, ahead_alt(s, at + 76, 2), P_BOUNCE, 128)
    s.prompt(560, PR_LOOP, 60)
    s.item(600, SUPPLY, 650, 0, ahead_alt(s, 650))
    for at in (690, 726, 762, 798, 834, 870):
        s.spawn(at, E04, at + 60, 0, ahead_alt(s, at + 60, 2), P_ORBIT, 128); s.spawn(at, E06, at - 8, 0, ahead_alt(s, at, 6), P_SWOOP, 128)
    s.prompt(760, PR_ROLL, 60)
    s.item(880, MEDIC, 930, 0, ahead_alt(s, 930))
    s.setboss(0, 0, 24, [
        ('B_DOPPEL', 0, 0, 0, 60, 1, 0, 0x13),
        ('B_NOZZLE', -3, 0, -8, 15, 0, 0, 2), ('B_NOZZLE', 3, 0, -8, 15, 0, 0, 2)], s.at(1120, 0, ahead_alt(s, 1120, 4)))     # カメラの少し上。カメラより 14 上だと画面の上の端に張り付いた
    s.end()
    return s

def s6():
    s = Mod(6, 'STAGE 6 / THE ORBIT', SPACE, 'STAGE6', flags=SF_SPACE, radio='She is on that rocket!', line='NOT SO FAST!')
    s.y0 = 60
    s.weapon = 6                        # 秘密兵器: 機雷
    sp = 20
    s.segs((104, 0, 0, sp), (32, 15, 0, sp), *lap_segs(sp), (32, -15, 0, sp), (88, 0, 0, sp), *lap_segs(sp),
           (64, 0, 0, sp), (48, 20, 0, sp), (48, -20, 0, sp), (96, 0, 0, sp), (48, -15, 0, sp), (48, 15, 0, sp), (64, 0, 0, sp), *lap_segs(sp),
           (24, 0, 0, sp), *lap_segs(16), (48, 0, 0, 16))
    a = Mesh(); a.tbox((-14, 2, 0), (3, 3, 3), TER2, top=TER1)
    b = Mesh(); b.plate([(12, -4, -3), (12, 4, -3), (18, 4, 3), (18, -4, 3)], CYAN)
    c = Mesh(); c.tbox((-22, 0, 0), (1, 1, 8), TER1, skip='fk'); c.tbox((-22, 6, 0), (1, 12, 1), TER1, detail=True); c.tbox((22, 0, 0), (1, 1, 8), TER1, skip='fk')
    s.sec_y = 60
    pats = [None, a, None, b, None, c]
    s.finish(lambda k: pats[(k * 5) % len(pats)])
    # 周回区間 0: 136-264、1: 384-512、2: 928-1056、ボス: 1080-1208
    s.lap(0); s.lap(1); s.lap(2); s.lap(3)
    s.text(36, 'THE ORBIT BASE!')
    s.ev(8, EV_PAL, 1)                  # 常にゆっくり回る
    for at in (16, 40, 64, 92, 120, 148):
        s.spawn(at, E07, at + 60, -6, 62, P_DRIFT); s.spawn(at, E07, at + 66, 6, 58, P_DRIFT); s.spawn(at, E08, at + 80, -3, 63, P_HOLD)
    for at in (170, 200, 226):
        s.spawn(at, E08, at + 40, -5, 60, P_HOLD); s.spawn(at, E07, at + 56, 0, 60, P_DRIFT)
    s.item(180, SUPPLY, 230, 0, 61)
    for at in (260, 288, 316, 344, 372):
        s.spawn(at, E08, at + 70, -2, 60, P_HOLD); s.spawn(at, E07, at + 56, 4, 60, P_DRIFT)
    for at in (130, 300, 360):
        s.prompt(at, PR_ROLL, 60)
    s.item(400, MEDIC, 440, 0, 60)
    # 後半: 基地の守りの宇宙戦闘機(P-51 の改造)と衛星
    s.text(520, 'SPACE FIGHTERS!')
    for at in (520, 556, 592, 628, 664):
        s.spawn(at, E06, at + 70, -3, 61, P_WEAVE, 128); s.spawn(at, E08, at + 60, 6, 62, P_HOLD)
    s.item(640, SUPPLY, 690, 0, 60)
    for at in (700, 736, 772, 808, 844, 880):
        s.spawn(at, E04, at + 60, 0, 60, P_ORBIT, 128); s.spawn(at, E07, at + 50, -4 if at % 72 else 4, 60, P_DRIFT)
    for at in (600, 760, 860):
        s.prompt(at, PR_ROLL, 60)
    s.item(900, MEDIC, 950, 0, 60)
    s.setboss(0, 0, 28, [
        ('B_KEYHOLE', 0, 0, 6, 1, 9, 8, 0),
        ('B_LENS', -6, 0, -6, 12, 0, 0, 0x10), ('B_LENS', -2, 5, -6, 12, 0, 0, 0x11),
        ('B_LENS', 4, 3, -6, 12, 0, 0, 0x12), ('B_LENS', 4, -3, -6, 12, 0, 0, 0x13),
        ('B_LENS', -2, -5, -6, 12, 9, 8, 0x14),
        ('B_CORE', 0, 0, -5, 60, 1, 2, 0)], s.at(1120, 0, 60))
    s.end()
    return s

def s7():
    """7 面: 深宇宙。地球の見えない星空。ヒナを乗せたロケット(方舟)を追い、小惑星の間を抜けて取り戻す"""
    s = Mod(21, 'STAGE 7 / DEEP SPACE', SPACE, 'STAGE6', flags=SF_SPACE | SF_DEEP, radio='I can see you!', line='GIVE HER BACK.')
    s.y0 = 60
    s.weapon = 7                        # 秘密兵器: 全部を順に
    s.models += ['MUSTANG', 'MINE', 'ROCKETL']
    sp = 20
    s.segs((104, 0, 0, sp), (32, 15, 0, sp), *lap_segs(sp), (64, -15, 0, sp), (96, 0, 0, sp), *lap_segs(sp),
           (64, 20, 0, sp), (64, -20, 0, sp), (96, 0, 0, sp), (64, 0, 0, sp), *lap_segs(sp),
           (24, 0, 0, sp), *lap_segs(16), (48, 0, 0, 16))
    s.sec_y = 60
    def rocks(seed):
        m = Mesh()
        for i in range(2):
            x = ((seed * 7 + i * 13) % 30 + 10) * (1 if (seed + i) % 2 else -1)
            y = ((seed * 5 + i * 3) % 14) - 7
            m.box((x, y, (i * 4) % 8 - 2), (3 + (seed + i) % 3, 2.5, 3), TER1 if i else TER2, top=IRON, skip='b')
        return m
    pats = [rocks(k) for k in range(3)] + [None, None, None]
    # ボスの周回では小惑星を置かない(近くの岩は 1 区画 5ms ほどかかり、ボス戦の 1 フレームの 1/4 を使っていた)
    nb = (s.circles[-1] - 24) // 8
    s.finish(lambda k: pats[(k * 3) % len(pats)] if k < nb else None)
    # 周回区間 0: 136-264、1: 424-552、2: 840-968、ボス: 992-1120
    s.lap(0); s.lap(1); s.lap(2); s.lap(3)
    s.text(36, 'DEEP SPACE!')
    for at in (16, 44, 72, 100, 128):
        s.spawn(at, E07, at + 56, -5, 62, P_DRIFT); s.spawn(at, E06, at + 70, 4, 60, P_WEAVE, 128)
    for at in (160, 196, 232):
        s.spawn(at, E08, at + 50, -4, 61, P_HOLD); s.spawn(at, E04, at + 60, 0, 60, P_ORBIT, 128)
    s.item(200, SUPPLY, 250, 0, 60)
    for at in (280, 316, 352, 388, 424):
        s.spawn(at, E06, at - 8, 0, 64, P_SWOOP, 128); s.spawn(at, E07, at + 50, 5, 59, P_DRIFT)
    for at in (150, 330, 470):
        s.prompt(at, PR_ROLL, 60)
    s.item(440, MEDIC, 490, 0, 60)
    s.text(560, 'ASTEROIDS!')
    for at in (560, 596, 632, 668, 704, 740, 776):
        s.spawn(at, E07, at + 44, -3 if at % 72 else 3, 60, P_DRIFT); s.spawn(at, E06, at + 70, 0, 61, P_WEAVE, 128)
    s.prompt(650, PR_LOOP, 60)
    s.item(700, SUPPLY, 750, 0, 60)
    for at in (800, 830, 860):
        s.spawn(at, E08, at + 60, -5, 62, P_HOLD); s.spawn(at, E04, at + 60, 4, 60, P_ORBIT, 128)
    s.item(900, MEDIC, 950, 0, 60)
    s.ev(980, EV_VOICE, V_GIVE)
    s.text(980, 'GIVE HER BACK.')
    s.setboss(0, 0, 30, [
        ('B_ARK', 0, 0, 8, 1, 9, 8, 0),
        ('B_NOZZLE', -5, -3, 2, 15, 0, 0, 2), ('B_NOZZLE', 5, -3, 2, 15, 0, 0, 2), ('B_NOZZLE', -5, 3, 2, 15, 0, 0, 1), ('B_NOZZLE', 5, 3, 2, 15, 0, 0, 1),
        ('B_LENS', -3, 0, -6, 14, 1, 0, 0x13), ('B_LENS', 3, 0, -6, 14, 1, 0, 0x14),
        ('B_CORE', 0, 0, -6, 60, 2, 2, 0),
        ('CAPSULE', 0, 7, 0, 1, 9, 1, 0)], s.at(1040, 0, 60))
    s.end()
    return s

# 字幕の話し手(src/engine/op.c の who と同じ並び): ナレーション(第三者)・父・ヒナ(無線)・ヒナ(その場)・機の警報・敵
WHO_NARR, WHO_PAPA, WHO_HINA_RADIO, WHO_HINA, WHO_ALERT, WHO_ENEMY = range(6)

class Film:
    """オープニングの映画(src/engine/op.c が時刻 t[ティック] で再生する)。曲 OPENING と同じ時計。
    座標は単位(8.8 にして 16bit で回り込む。カメラから 128 単位より遠いものは描かない)。
    向き: 方位 h は度(0 = 北 = +z、90 = 東 = +x)。カメラのヨー = h、役者のヨー = h + 180(モデルの正面は -z)"""
    FL_EASE, FL_BOB, FL_C, FL_SHAKE, FL_STEP = 1, 2, 4, 8, 16
    FE_SUB, FE_CAP, FE_VOICE, FE_SE, FE_COCKPIT, FE_END, FE_SHAKE, FE_FADE, FE_SPR = range(1, 10)

    def __init__(self):
        self.cam, self.acts, self.evs = [], [], []
        self.sprites = []          # 見せたいもの(tools/film_spr.py の Subject)。スプライトで描く
        self.clears = []           # say の dur で消す字幕(出した時刻, 消す時刻)

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

    def say(self, t, who, s, mood=0, dur=None):
        """字幕(下の黒帯)。who = WHO_ の話し手(色・名前の札・斜体が決まる。src/engine/op.c の who)、mood = 時間による出し分け。
        dur を渡すとそのティック後に消す(その間に次の字幕が来るときは消さない)"""
        self.evs.append((t, self.FE_SUB, mood | who << 2, s))
        if dur:
            self.clears.append((t, t + dur))

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
        spr = ''
        if self.sprites:
            import film_spr
            end = max(e[0] for e in self.evs)
            spr, _, _ = film_spr.header(self, self.sprites, M, end)
            self.evs.append((0, self.FE_SPR, 0, None))
        for t0, t1 in self.clears:
            if not any(e[1] == self.FE_SUB and t0 < e[0] <= t1 for e in self.evs):
                self.evs.append((t1, self.FE_SUB, 0, ''))
        self.clears = []
        evs = sorted(self.evs, key=lambda e: e[0])
        out.append('#define N_FEV %d' % len(evs))
        def c_s(k, a, s):
            if s is None:
                return '0'
            if k == self.FE_SUB:   # 字幕は字体に合わせて並べた形で(tools/gen_font.py)
                return gen_font.c_str(gen_font.layout(s, a >> 2))
            return '"%s"' % s
        out.append('static const FilmEv film_ev[] = {' + ','.join('{%d,%d,%d,%s}' % (t, k, a, c_s(k, a, s)) for t, k, a, s in evs) + '};')
        return '\n'.join(out) + '\n' + spr


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
    f.say(20, WHO_NARR, 'The town fell at dawn.')
    f.say(2 * BAR, WHO_NARR, '')

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
    # 父が家を見ている間に、轟音とともに戦闘機が東から家の上をかすめ、庭の先(約 13 単位)へ西向きに降りる。
    # 戦闘機は最後まで 3D で描く(前は道に降りると後ろから見たスプライトになり、黒い蜘蛛のような塊に見えた)。横向きに止めて右の横腹を見せる
    G = (-1, 0, 11)
    f.key(raider, CAR - 30, 'RAIDERM', (40, 12, 14), -90, roll=-20)
    f.key(raider, CAR + 30, 'RAIDERM', (15, 3, 12), -90, roll=-8)
    f.key(raider, CAR + 60, 'RAIDERM', (4, .8, 11), -90)
    f.key(raider, CAR + 80, 'RAIDERM', G, -90)
    # 5〜6 小節(暗い主題): 振り返ると、黒ずくめの男がヒナを肩に担いで戦闘機へ走っている。もう一人が銃を構えて父を止める
    BACK = 4 * BAR - 20
    f.cam_key(BACK, p0, 70, 0, fl=F.FL_EASE)
    f.cam_key(BACK + 30, p0, 0, 0)
    run0, run1 = (2.6, 0, 4.5), (.5, 0, 9.6)                       # 戦闘機の右の横腹(胴の下にカプセル)へ
    f.key(t1, CAR, 'TERROR', run0, 0, fl=F.FL_BOB)
    f.key(t1, 4 * BAR + 220, 'TERROR', run1, 0)
    carry = lambda p: p                     # 担がれたヒナのスプライトは誘拐犯と同じ足もとに置く(絵が肩の上にある)
    f.key(hina, CAR, 'HINA', carry(run0), 0, roll=90, fl=F.FL_BOB, cut=True)
    f.key(hina, 4 * BAR + 220, 'HINA', carry(run1), 0, roll=90)
    f.key(hina, 4 * BAR + 240, 'HINA', (-.5, .5, 10.6), 0, roll=90)  # カプセルへ入れられる
    f.key(hina, 4 * BAR + 250, HIDE, (0, 0, 0))
    f.ev(4 * BAR + 40, F.FE_VOICE, 9)                               # 「Papa!」(VOICE_PAPA)
    f.key(t1, 4 * BAR + 250, 'TERROR', run1, 0)
    f.key(t1, 4 * BAR + 290, 'TERROR', (-2.5, 0, 9.8), 270, fl=F.FL_BOB)
    f.key(t1, 4 * BAR + 300, HIDE, (0, 0, 0))                        # 乗り込む
    f.key(t2, CAR, 'TERROR', (-.6, 0, 4.5), 180)                    # 2 人目は父の前に立ちはだかり、銃を向ける
    f.key(t2, 4 * BAR + 262, 'TERROR', (-.6, 0, 4.5), 180)
    f.key(t2, 4 * BAR + 270, 'TERROR', (-.6, 0, 4.5), 0, fl=F.FL_BOB)
    f.key(t2, 4 * BAR + 310, 'TERROR', (-2.8, 0, 9.6), 0)
    f.key(t2, 4 * BAR + 320, HIDE, (0, 0, 0))
    # 父は追おうとするが、2 人目に銃を向けられて数歩で止まる(5 小節目〜6 小節目)
    p1 = (1.8, eye, 1.2)
    f.cam_key(4 * BAR + 20, p0, 0, 0, fl=F.FL_BOB)
    f.cam_key(4 * BAR + 300, p1, 0, 0)
    # 7〜8 小節: 戦闘機は父の目の前を西へ滑走して飛び立ち、右へ回って父の頭の上をかすめ、町のほうへ消える。父は目で追い、見上げる
    # (前は北へまっすぐ遠ざかり、すぐに点になった)
    TO = 6 * BAR
    f.key(raider, TO, 'RAIDERM', G, -90)
    f.key(raider, TO + 50, 'RAIDERM', (-5, 0, 11), -90)
    f.key(raider, TO + 100, 'RAIDERM', (-16, 0, 11), -90)
    f.key(raider, TO + 140, 'RAIDERM', (-28, 2, 11), -88)
    # 小さく右へ回り、父のすぐ上(約 22 単位)を低くかすめて、東の町のほうへ(前は 45 単位より遠くを回り、点になった)
    f.key(raider, TO + 175, 'RAIDERM', (-30, 6, 20), 0, roll=-35)
    f.key(raider, TO + 210, 'RAIDERM', (-20, 9, 24), 60, roll=-35)
    f.key(raider, TO + 245, 'RAIDERM', (-4, 11, 22), 100, roll=-20)
    f.key(raider, TO + 280, 'RAIDERM', (16, 14, 26), 60, roll=-25)
    f.key(raider, TO + 310, 'RAIDERM', (30, 18, 44), 30, roll=-15)
    f.key(raider, TO + 312, HIDE, (0, 0, 0))
    f.ev(TO, F.FE_SE, 10)
    f.cam_key(TO + 20, p1, -10, 0, fl=F.FL_EASE)
    f.cam_key(TO + 100, p1, -50, 0)
    f.cam_key(TO + 140, p1, -66, 2)
    f.cam_key(TO + 175, p1, -59, 7)
    f.cam_key(TO + 210, p1, -44, 13)
    f.cam_key(TO + 245, p1, -14, 22)
    f.cam_key(TO + 280, p1, 28, 22)
    f.cam_key(TO + 310, p1, 33, 18)
    # 9 小節: 振り返り、格納庫へ走る
    TURN = 8 * BAR
    f.cam_key(TURN, p1, 33, 18, fl=F.FL_EASE)
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
    f.say(OUT + 2, WHO_PAPA, "Let's go.")
    f.say(OUT + 150, WHO_NARR, 'You have 6 hours to save her.')
    f.ev(OUT, F.FE_SE, 10)
    # 零戦は 6 秒のあいだ約 20〜30 単位に保ち、カメラも昇りながら後ろから追う(前はカメラが地上に止まっていて、
    # 2〜3 秒で 40 単位より遠くなり、最後は 95 単位先の点になった)
    zk = [(OUT, (-8, 9, 62), 0, 0), (OUT + 70, (-5, 15, 86), 10, -15), (OUT + 140, (-1, 20, 102), 8, -5), (2250, (4, 25, 124), 5, 0)]
    ck = [(OUT, (6, 1.4, 76)), (OUT + 70, (6, 4, 80)), (OUT + 140, (5, 8, 86)), (2250, (4, 13, 102))]
    def lerp(ks, t):
        for (t0, a, *_), (t1, b, *_) in zip(ks, ks[1:]):
            if t0 <= t <= t1:
                k = (t - t0) / (t1 - t0)
                return tuple(a[i] + (b[i] - a[i]) * k for i in range(3))
    for t, p, h, r in zk:
        f.key(zero, t, 'ZEROF', p, h, roll=r)
    for t in (OUT, OUT + 35, OUT + 70, OUT + 105, OUT + 140, OUT + 220, OUT + 300, 2250):
        c, z = lerp(ck, t), lerp(zk, t)
        dx, dy, dz = z[0] - c[0], z[1] - c[1], z[2] - c[2]
        f.cam_key(t, c, math.degrees(math.atan2(dx, dz)), math.degrees(math.atan2(dy, math.hypot(dx, dz))), fl=F.FL_EASE if t == OUT + 140 else 0)
    f.key(smoke1, OUT, 'SMOKE', (-6, 0, 180), cut=True); f.key(smoke2, OUT, 'SMOKE', (14, 0, 188), cut=True)
    f.key(ship, OUT, 'SHIP', (6, 34, 184), 270, cut=True)
    f.ev(2260, F.FE_END)
    s.film = f
    s.op_base = 0x9420
    return s

def seam1():
    """1 面の後の継ぎ目(モジュール 15)。曲 BRIDGE(t128、8 小節 = 900 ティック。1 小節 112.5)に合わせる。
    海の上を外から見た零戦が北へ飛ぶ → 操縦席から、遠くに誘拐犯の戦闘機(ヒナのカプセル)と、無線のヒナの声 →
    水平線に港が現れ、港から空へレーザーが伸びる(2 面の港の基地のレーザー戦車の前振り)"""
    s = Mod(15, 'SEAM 1', SEA, 'BRIDGE', flags=SF_SCENE)
    s.models = ['ZEROF', 'RAIDER', 'CRANE', 'DEPOT', 'BEAM', 'CLOUDP']
    s.y0 = 0
    s.segs((32, 0, 0, 0))
    s.finish(lambda k: None)
    f = Film()
    F = Film
    B = 112.5
    HIDE = 0
    zero, jet = f.actor(), f.actor()
    clouds = [f.actor() for _ in range(3)]
    crane1, crane2, depot, beam = f.actor(), f.actor(), f.actor(), f.actor()
    for a in [zero, jet, crane1, crane2, depot, beam] + clouds:
        f.key(a, 0, HIDE, (0, 0, 0))
    # 1〜2 小節: 海の上。父の零戦がカメラの近くを左から右へゆっくり横切る。少し上から見下ろして、暗い海を背に翼の上面(日の丸)を見せ、カメラは首を振って追う
    # (前は後ろからカメラの横をかすめて北へ抜けたので、点 → 画面からはみ出す塊 → 点と変わり、零戦に見える時間がほとんど無かった)
    cam = (0, 10.5, 0)
    f.cam_key(0, cam, -40, -24)
    f.cam_key(225, cam, 35, -24)
    f.key(zero, 0, 'ZEROF', (-10, 5.5, 9), 80, roll=-5)
    f.key(zero, 110, 'ZEROF', (-1, 5.7, 9.5), 82, roll=-5)
    f.key(zero, 224, 'ZEROF', (8, 6, 10.5), 84)
    f.key(zero, 226, HIDE)
    f.key(clouds[0], 0, 'CLOUDP', (-14, 12, 30))
    f.key(clouds[1], 0, 'CLOUDP', (16, 16, 70))
    # 3〜5 小節: 操縦席。遠くに誘拐犯の戦闘機。無線でヒナの声
    T = int(2 * B)
    v = .3                                     # 1 ティックに進む単位
    end = 900
    for t in range(T, end, 150):               # 1 区間で 120 単位を超えないよう、150 ティックごとにキーを置く
        f.cam_key(t, (3, 10, 60 + v * (t - T)), 0, 2)
    f.cam_key(end, (3, 10, 60 + v * (end - T)), 0, 2)
    # 正面のやや上、約 20 単位先(前は 50〜60 単位先で、小さくて何か分からなかった)
    f.key(jet, T, 'RAIDER', (5, 13.5, 80), 0)
    f.key(jet, int(5 * B), 'RAIDER', (4, 13.5, 181), 0)
    f.key(jet, end, 'RAIDER', (2, 14, 283), 0)
    # そばを流れる雲(速さを見せる)
    zc = lambda t: 60 + v * (t - T)
    f.key(clouds[0], T, 'CLOUDP', (-10, 13, zc(T) + 60), cut=True); f.key(clouds[0], T + 200, 'CLOUDP', (-10, 13, zc(T) + 60))
    f.key(clouds[1], T, 'CLOUDP', (14, 6, zc(T) + 110), cut=True); f.key(clouds[1], T + 360, 'CLOUDP', (14, 6, zc(T) + 110))
    f.key(clouds[2], T + 150, 'CLOUDP', (-6, 8, zc(T + 150) + 100)); f.key(clouds[2], T + 450, 'CLOUDP', (-6, 8, zc(T + 150) + 100))
    f.ev(int(3 * B) + 20, F.FE_VOICE, 6)                            # 「Papa, hurry!」(VOICE_HURRY)
    f.say(int(3 * B) + 20, WHO_HINA_RADIO, 'Papa, hurry!', dur=150)
    # 6〜8 小節: 水平線に港。港から空へレーザーが伸びて光る(戦闘機はその上を越えていく)
    H = 300                                    # 港の z(カメラは最後に 60 + 0.3 × 675 ≒ 262。座標は 256 で回り込むので、カメラから 120 以内に置く)
    f.key(crane1, int(5 * B), 'CRANE', (-14, 0, H), 90)
    f.key(crane2, int(5 * B), 'CRANE', (10, 0, H + 8), 270)
    f.key(depot, int(5 * B), 'DEPOT', (-2, 0, H - 4), 180)
    for i, t0 in enumerate((int(6 * B), int(6.6 * B), int(7.2 * B))):
        f.key(beam, t0, 'BEAM', ((-5, -1, -3)[i], 12, H + 2))
        f.key(beam, t0 + 40, HIDE)
        f.ev(t0, F.FE_SE, 11)                                          # SE_LASER
    f.say(int(6 * B) + 20, WHO_PAPA, 'They have lasers!', dur=150)
    f.ev(end, F.FE_END)
    s.film = f
    s.op_base = 0x9000
    return s

def seam_mod(n, name, pal, flags=0):
    """継ぎ目の映像の場面のモジュール(地形なし。曲は BRIDGE: t128、8 小節 = 900 ティック、1 小節 112.5)"""
    s = Mod(n, name, pal, 'BRIDGE', flags=SF_SCENE | flags)
    s.op_base = 0x8800                         # 演出のコード(Makefile の OPn_BASE と同じ値。主役のスプライトの絵も入るので、データの後ろから)
    s.y0 = 0
    s.segs((32, 0, 0, 0))                      # 区画が 3 つ以上ないと経路の終わり(path_max)が 0 になり、場面がすぐ終わる
    s.finish(lambda k: None)
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
    s.models = ['MESA', 'MUSTANGF', 'RAIDER', 'CLOUDP']
    f = Film(); F = Film; B = 112.5; end = 900
    jet, m1, m2, m3, p1, p2, cl = [f.actor() for _ in range(7)]
    for a in (jet, m1, m2, m3, p1, p2, cl):
        f.key(a, 0, 0, (0, 0, 0))
    cam = cruise(f, 0, end, (0, 14, 0), .3)
    f.key(cl, 0, 'CLOUDP', (-12, 18, 70)); f.key(cl, 300, 'CLOUDP', (-12, 18, 70))
    # 誘拐犯の戦闘機は 3D で、約 20 単位先の少し上(前は 60〜90 単位先のスプライトで、虫のように見えた。同じ高さだと翼が線になる)
    f.key(jet, 0, 'RAIDER', (3, 19, 20), 0)
    f.key(jet, int(3 * B), 'RAIDER', (2, 19, 121), 0)
    f.key(jet, 600, 'RAIDER', (1, 18.5, 201), 0)
    f.key(jet, 680, 'RAIDER', (0, 7, 227), 0)                       # 谷へ急降下(同じ高さを通る間は翼が線になるので、短く)
    f.key(jet, end, 'RAIDER', (0, 4, 296), 0)                       # 上から紫の翼が見える
    f.ev(int(2 * B), F.FE_VOICE, 6)                                  # 「Papa, hurry!」
    f.say(int(2 * B), WHO_HINA_RADIO, 'Papa, hurry!', dur=150)
    for a, (x, z) in zip((m1, m2, m3), ((-14, 250), (12, 262), (-4, 290))):
        f.key(a, int(3.5 * B), 'MESA', (x, 0, z), 180)
    # 6〜8 小節: 台地の間から P-51 が 2 機、こちらへ上がってきて、操縦席のすぐ横を正面からすれ違う
    # (前は 65〜90 単位先から近づくだけで、地平線の緑の点にしか見えなかった)
    t = int(4.5 * B)
    for a, x in ((p1, -5), (p2, 6)):
        z0 = cam(t)[2] + 35
        f.key(a, t, 'MUSTANGF', (x, 8, z0), 180)
        f.key(a, 700, 'MUSTANGF', (x * .9, 12, cam(700)[2] + 18), 180, roll=40 if x < 0 else -40)
        f.key(a, end, 'MUSTANGF', (x * 1.3, 13.5, cam(end)[2] + 9), 180, roll=60 if x < 0 else -60)   # 翼を立てて両横をすれ違う(正面からだと薄い)
    f.ev(t + 20, F.FE_SE, 4)                                         # SE_ALARM
    f.say(t + 30, WHO_ALERT, 'Bandits!', dur=150)
    f.ev(end, F.FE_END)
    s.film = f
    return s


def seam3():
    """3 面の後(谷 → 雲海、夜)。雲を抜けて上へ。振り返ると、ロケットを積んだ P-51 が後ろに食いついている"""
    s = seam_mod(17, 'SEAM 3', NIGHT)
    s.models = ['RMUSTANGF', 'RAIDERN', 'CLOUDP']
    f = Film(); F = Film; B = 112.5; end = 900
    c1, c2, c3, p1, p2, jet = [f.actor() for _ in range(6)]
    for a in (c1, c2, c3, p1, p2, jet):
        f.key(a, 0, 0, (0, 0, 0))
    # 1〜4 小節: 機首を上げて雲を抜ける。前を、ヒナを乗せた誘拐犯の戦闘機が昇っていく。約 18 単位先の少し上に置き、
    # 月明かりの灰の腹と白いカプセルを夜空を背に見上げる(前は 50 単位先の黒いスプライトで、夜空に溶けて見えなかった)
    cam = cruise(f, 0, int(4 * B), (0, 6, 0), .28, pitch=12, climb=.06)
    for t in (0, 150, 300, int(4 * B)):
        x, y, z = cam(t)
        f.key(jet, t, 'RAIDERN', (2, y + 3, z + 18), 0)
    f.key(jet, int(4 * B) + 2, 0)
    f.say(60, WHO_PAPA, 'After that jet!', dur=150)
    for a, (x, y, z, t0) in zip((c1, c2, c3), ((-6, 14, 40, 0), (8, 22, 90, 120), (-3, 30, 150, 260))):
        f.key(a, t0, 'CLOUDP', (x, y, z)); f.key(a, t0 + 200, 'CLOUDP', (x, y, z))
    # 5〜8 小節: 雲の上で水平に。警報、振り返ると後ろに 2 機
    t = int(4 * B)
    p = cam(t)
    tl = int(4.6 * B)
    cruise(f, t, tl, p, .28, pitch=0)
    f.ev(tl, F.FE_SE, 4)
    f.ev(tl, F.FE_VOICE, 5)                                          # 「Warning!」
    f.say(tl + 20, WHO_ALERT, 'On your tail!', dur=150)
    zc = lambda tt: p[2] + .28 * (tt - t)
    turn0, turn1 = tl + 30, tl + 90
    f.cam_key(turn0, (p[0], p[1], zc(turn0)), 0, 0, fl=F.FL_EASE)
    f.cam_key(turn1, (p[0], p[1], zc(turn1)), 175, 4)
    f.cam_key(int(7.2 * B), (p[0], p[1], zc(int(7.2 * B))), 178, 4, fl=F.FL_EASE)
    f.cam_key(end, (p[0], p[1], zc(end)), 0, 0)
    for a, x in ((p1, -4), (p2, 5)):                                # 映像用の大きい P-51(前は小さな緑の点だった)を、左右に並べて 10 単位後ろへ
        f.key(a, tl, 'RMUSTANGF', (x * 1.1, p[1] + 2, zc(tl) - 40), 0)
        f.key(a, int(6.5 * B), 'RMUSTANGF', (x * .8, p[1] - 1.5, zc(int(6.5 * B)) - 10), 0, roll=15 if x < 0 else -15)
        f.key(a, end, 'RMUSTANGF', (x * .8, p[1] - 1.5, zc(end) - 9), 0)
    f.ev(end, F.FE_END)
    s.film = f
    return s


def seam4():
    """4 面の後(雲海 → 成層圏、明け方)。前半は雲の上の発射台に寄った絵: 着いた戦闘機から誘拐犯がヒナを担いでロケットへ運び、
    ヒナが叫ぶ(人物はスプライト)。後半はそのロケットが白い煙を引いて打ち上がるのを、発射台の横から見上げ、並んで昇りながら追う"""
    s = seam_mod(18, 'SEAM 4', TWILIGHT)
    s.models = ['ROCKETL', 'PUFF', 'PAD']
    f = Film(); F = Film; B = 112.5; end = 900
    rk, pad, jet, t1, t2, hina = [f.actor() for _ in range(6)]
    puffs = [f.actor() for _ in range(4)]
    for a in [rk, pad, jet, t1, t2, hina] + puffs:
        f.key(a, 0, 0, (0, 0, 0))
    P = 20                                     # 発射台の高さ(雲の上)
    R = (5, P + 6, 12)                         # ロケットの中心(発射台の上に立つ)
    # 0〜340: 発射台(外の絵、黒帯)
    f.ev(0, F.FE_COCKPIT, 1)
    f.cam_key(0, (-2, P + 1.8, 1), 20, -2)               # 人物が中くらいの絵になる近さ(10 単位より近く)
    f.cam_key(339, (-1, P + 1.8, 2), 32, -4, fl=F.FL_STEP)
    f.key(pad, 0, 'PAD', (0, P, 9), cut=True)
    f.key(rk, 0, 'ROCKETL', R, cut=True)
    f.key(jet, 0, 'RAIDER', (-6, P, 12), 180, cut=True)
    f.key(t1, 40, 'TERROR', (-4.5, P, 9), 270, fl=F.FL_BOB, cut=True)
    f.key(hina, 40, 'HINA', (-4.5, P, 9), 270, roll=90, fl=F.FL_BOB, cut=True)
    f.key(t1, 280, 'TERROR', (3, P, 11), 270)
    f.key(hina, 280, 'HINA', (3, P, 11), 270, roll=90)
    f.key(t1, 300, 0); f.key(hina, 300, 0)           # ロケットに乗り込む
    f.key(t2, 40, 'TERROR', (-3, P, 6.5), 180, cut=True)    # もう一人は見張る
    f.key(t2, 300, 'TERROR', (-3, P, 6.5), 270)
    f.ev(130, F.FE_VOICE, 9)                                  # 「Papa!」
    f.say(130, WHO_HINA, 'Papa!')
    f.say(220, WHO_NARR, 'They put her in a rocket.')
    # 340〜: 打ち上げ。前は操縦席から 80 単位先の発射台を見ていて、ロケットが点にしか見えなかった。
    # ロケットに寄った 2 つのカットにする: 発射台の横から見上げるカットと、並んで昇りながら追うカット
    f.say(340, WHO_NARR, '')
    f.key(t2, 340, 0); f.key(jet, 340, 0)
    t0, tc = 420, 600                                    # 点火、追うカットへの切り替え
    ry = lambda t: R[1] + .00035 * max(0, t - t0) ** 2   # 加速しながら真上へ
    rp = lambda t: (R[0], ry(t), R[2])
    def look(c, t, fl=0):                                # カメラ c からロケットの胴の真ん中を向く
        dx, dy, dz = R[0] - c[0], ry(t) - c[1], R[2] - c[2]
        f.cam_key(t, c, math.degrees(math.atan2(dx, dz)), math.degrees(math.atan2(dy, math.hypot(dx, dz))), fl=fl)
    # 1 つ目(340〜600): 発射台の横、約 16 単位から。ロケットの全身が画面の 7 割ほどに映り、昇るのを見上げて追う。
    # 南東から見る(南西からだと発射台の赤い塔がロケットの手前に重なって描かれ、胴が半分赤く見えた)
    C = (16, P + 3, 0)
    for t in [340] + list(range(t0, tc, 30)) + [tc - 1]:
        look(C, t, F.FL_STEP if t == tc - 1 else 0)
    f.key(rk, 340, 'ROCKETL', R, cut=True)
    for t in range(t0, 901, 30):
        f.key(rk, t, 'ROCKETL', rp(t))
    # 2 つ目(600〜900): 並んで昇りながら追う。初めは斜め後ろのすぐ横、だんだん引き離されて見上げる形に
    for t in range(tc, 901, 30):
        k = (t - tc) / 300
        o = (-9 - 2 * k, -2 - 8 * k, -6 - 2 * k)       # 約 11 → 14 単位。離れすぎると点になる
        look((R[0] + o[0], ry(t) + o[1], R[2] + o[2]), t)
    # 白い煙: ロケットの根もとに、通った跡として残す(追うカットでは同じ役者を新しい跡へ移す)
    for i, a in enumerate(puffs):
        for tp in (t0 + 20 + i * 45, tc + 40 + i * 70):
            q = rp(tp)
            f.key(a, tp, 'PUFF', (q[0] + (i % 2 - .5) * 1.5, q[1] - 7, q[2]), cut=True)
    f.ev(t0, F.FE_SE, 10)                                            # 轟音
    f.say(t0 + 40, WHO_PAPA, 'The rocket!', dur=150)
    f.ev(int(6.5 * B), F.FE_VOICE, 6)                                # 「Papa, hurry!」
    f.say(int(6.5 * B), WHO_HINA_RADIO, 'Papa, hurry!', dur=150)
    f.ev(end, F.FE_END)
    s.film = f
    return s


def seam5():
    """5 面の後(成層圏 → 軌道)。星空へ抜けると、遠くに鍵穴の形の基地。先に上がったロケットがそこへ向かう"""
    s = seam_mod(19, 'SEAM 5', SPACE, SF_SPACE)
    s.models = ['B_KEYHOLE', 'ROCKETL']
    f = Film(); F = Film; B = 112.5; end = 900
    kh, rk = f.actor(), f.actor()
    f.key(kh, 0, 0, (0, 0, 0))
    def look(t, c, p, fl=0):                             # カメラ c から点 p を向く
        dx, dy, dz = p[0] - c[0], p[1] - c[1], p[2] - c[2]
        f.cam_key(t, c, math.degrees(math.atan2(dx, dz)), math.degrees(math.atan2(dy, math.hypot(dx, dz))), fl=fl)
    # 前は操縦席から 50〜85 単位先の基地を正面から見ていて、横棒と白い塊にしか見えず、ロケットも小さかった。
    # 1 つ目(0〜300): 4 面の後の終わりと同じく、昇るロケットのすぐ横を並んで飛ぶ。カメラは少しずつ遅れ、
    # ロケットが画面を下から上へ抜けていく(同じ速さだと止まって見えた)。下に地球
    tc = 300
    # カメラの向きは変えない(ロケットを向き続けると真ん中に止まって見え、地球も画面から外れた)
    rk1 = lambda t: (0, 30 + .1 * t, 20)
    cm1 = lambda t: (-9, 36 + .05 * t, 14)
    for t in list(range(0, tc, 60)) + [tc - 1]:
        f.cam_key(t, cm1(t), math.degrees(math.atan2(9, 6)), 8, fl=F.FL_STEP if t == tc - 1 else 0)
        f.key(rk, t, 'ROCKETL', rk1(t), cut=t == 0)
    # 2 つ目(300〜900): 鍵穴の基地を斜め横から(胴の長さと太陽の板が見える)。ロケットは左下から昇ってきて、
    # 基地の左の口へ向かって小さくなっていく(基地に重ならないように)。基地は半径が 22 あり、90 単位より遠いと描かれない
    K = (8, 56, 62)
    f.key(kh, tc, 'B_KEYHOLE', K, 250, cut=True)
    for t, c in ((tc, (-2, 48, 20)), (600, (-1, 48.5, 25)), (end, (0, 49, 30))):
        look(t, c, (K[0] - 3, K[1] - 1, K[2]))
    f.key(rk, tc, 'ROCKETL', (-7, 41, 32), cut=True)
    f.key(rk, 600, 'ROCKETL', (-6, 48, 44))
    f.key(rk, end, 'ROCKETL', (-5, 54, 54))
    f.ev(int(4 * B), F.FE_VOICE, 7)                                  # 「I can see you!」(VOICE_SEE)
    f.say(int(4 * B), WHO_HINA_RADIO, 'I can see you!', dur=150)
    f.ev(end, F.FE_END)
    s.film = f
    return s

def seam6():
    """6 面の後(軌道 → 深宇宙)。壊れた鍵穴の基地の陰から方舟(ヒナのロケット)が離れ、深宇宙へ。零戦はそれを追う"""
    s = seam_mod(20, 'SEAM 6', SPACE, SF_SPACE | SF_DEEP)
    s.models = ['B_KEYHOLE', 'B_ARK']
    f = Film(); F = Film; B = 112.5; end = 900
    kh, ark = f.actor(), f.actor()
    f.key(kh, 0, 0, (0, 0, 0))
    def look(t, c, p, fl=0):                             # カメラ c から点 p を向く
        dx, dy, dz = p[0] - c[0], p[1] - c[1], p[2] - c[2]
        f.cam_key(t, c, math.degrees(math.atan2(dx, dz)), math.degrees(math.atan2(dy, math.hypot(dx, dz))), fl=fl)
    # 前は操縦席から 60〜75 単位先の方舟を真後ろから見ていて、赤い尾の点にしか見えなかった(胴は 18 単位ある)。
    # 1 つ目(0〜420): 壊れた基地を斜めに映し、その陰から方舟が出てきて、カメラの約 22 単位前を右から左へ横切る(横向きの全身)
    tc = 420
    f.cam_key(0, (0, 60, 0), 0, 2)
    f.cam_key(tc - 1, (0, 60, 6), -6, 2, fl=F.FL_STEP)
    f.key(kh, 0, 'B_KEYHOLE', (-13, 67, 58), 230, cut=True)
    f.key(kh, tc - 1, 'B_KEYHOLE', (-13, 67, 58), 240)
    f.key(ark, 0, 'B_ARK', (18, 59, 50), 300, cut=True)          # 基地の右下の奥から(基地に重ならないように)
    f.key(ark, 150, 'B_ARK', (12, 61, 34), 280)
    f.key(ark, tc - 1, 'B_ARK', (-16, 60, 26), 270)
    # 2 つ目(420〜900): 方舟を斜め後ろから追う。白い胴と赤い 4 枚の翼が見える。少しずつ引き離される
    f.key(kh, tc, 0)
    A = lambda t: (-4, 61, 30 + .12 * (t - tc))
    for t in range(tc, end + 1, 60):
        k = (t - tc) / (end - tc)
        f.key(ark, t, 'B_ARK', A(t), 0, roll=10 * k, cut=t == tc)
        c = A(t)
        look(t, (c[0] - 9 - 2 * k, c[1] + 3 + k, c[2] - 17 - 8 * k), c)
    f.ev(60, F.FE_SE, 10)
    f.say(int(2 * B), WHO_PAPA, 'She is on that rocket!', dur=150)
    f.ev(int(5 * B), F.FE_VOICE, 6)                                  # 「Papa, hurry!」
    f.say(int(5 * B), WHO_HINA_RADIO, 'Papa, hurry!', dur=150)
    f.ev(end, F.FE_END)
    s.film = f
    return s

def ending():
    """エンディング(モジュール 7): 宇宙でカプセルに追いつく → ヒナが零戦へ移る → 夕焼けの空へ → 零戦が夕日へ小さくなる間の親子の会話。
    会話は残り時間で変わる(1 時間以上残っていれば素直に喜び、遅れるとすねる)。続くエンドロールの文面も、ここの字幕に置く"""
    s = Mod(7, 'ENDING', SPACE, '',   # 曲は無し(最後のボスを倒したときに鳴らした FINALE が、映像の終わりまで続く)
            flags=SF_SCENE | SF_SPACE | SF_DEEP)
    s.pal2 = SUNSET
    s.models = ['CAPSULE', 'ZEROF', 'ZEROS', 'SUN', 'CLOUDS']
    s.y0 = 0
    s.segs((32, 0, 0, 0))
    s.finish(lambda k: None)
    f = Film(); F = Film
    cap, zero, hina, sun, c1, c2 = [f.actor() for _ in range(6)]
    for a in (cap, zero, hina, sun, c1, c2):
        f.key(a, 0, 0, (0, 0, 0))
    # 0〜300: 操縦席。前にヒナのカプセルが浮かんでいて、追いつく
    f.cam_key(0, (0, 40, 0), 0, 2)
    f.cam_key(280, (0, 40, 60), 0, 4, fl=F.FL_EASE)
    f.key(cap, 0, 'CAPSULE', (1, 41, 90))
    f.key(cap, 300, 'CAPSULE', (1, 41, 78))
    f.say(60, WHO_PAPA, 'Hina!', dur=150)
    # 300〜640: 外から。零戦の横にカプセル。ヒナが出てきて、零戦の操縦席へ泳いでいく
    f.ev(300, F.FE_COCKPIT, 1)
    f.cam_key(299, (0, 40, 60), 0, 4, fl=F.FL_STEP)       # 切り替え
    f.cam_key(300, (8, 42, 70), -60, 6)
    f.cam_key(640, (6, 42, 68), -50, 4)
    f.cam_key(739, (6, 42, 68), -50, 4, fl=F.FL_STEP)
    f.key(zero, 300, 'ZEROF', (-2, 40, 76), 90)
    f.key(zero, 640, 'ZEROF', (-2, 40.5, 76), 90)
    # 宇宙から夕方への色の移り(640〜)が終わってから夕焼けの絵に切り替える(700 だと、星空の上に夕日が数コマ出た)
    f.key(cap, 300, 'CAPSULE', (2, 41, 76), cut=True)
    f.key(cap, 640, 'CAPSULE', (2.5, 41.5, 76))
    f.key(hina, 380, 'HINA', (2, 40.4, 76), 270, cut=True)
    f.key(hina, 520, 'HINA', (-1, 40.6, 76), 270)
    f.key(hina, 560, 0)                                   # 操縦席に入る
    f.ev(400, F.FE_VOICE, 9)                              # 「Papa!」
    f.say(400, WHO_HINA, 'Papa!')
    f.say(470, WHO_HINA, 'I knew you would come!', 1)
    f.say(470, WHO_HINA, "You're late, Papa.", 2)
    f.say(570, WHO_PAPA, 'Always, Hina.', 1)
    f.say(570, WHO_PAPA, 'Sorry. Traffic.', 2)
    # 640〜: 地球へ戻り、夕焼けの空へ(宇宙の色から夕方の色へ移る)。カメラは残り、零戦は夕日へ飛んで小さくなる
    f.ev(640, F.FE_FADE)
    f.say(640, WHO_HINA, 'In space?', 2)
    f.cam_key(740, (0, 5, 0), 0, 0)
    f.cam_key(1500, (0, 5, 0), 0, 0, fl=F.FL_EASE)
    f.key(cap, 740, 0)
    # 大きな夕日を零戦の真後ろ、地平線のすぐ上に置き、零戦はその前を逆光の影になって飛ぶ。雲は夕日にかかる暗い筋
    f.key(sun, 740, 'SUN', (-3, 18.5, 40), 0, cut=True)
    f.key(sun, 1500, 'SUN', (-2, 17, 40), 0)
    f.key(c1, 740, 'CLOUDS', (-9, 21, 41), cut=True); f.key(c1, 1500, 'CLOUDS', (-5, 21, 41))
    f.key(c2, 740, 'CLOUDS', (12, 12.5, 41), cut=True); f.key(c2, 1500, 'CLOUDS', (8, 12.5, 41))
    # 零戦は黒い影になって夕日へ向かう。2 人の乗った機だと分かるように、映像の終わりまで大きく映る距離にとどめ、
    # 斜め下から見上げて、空を背に翼の形を見せる(真後ろの水平からだと翼が線になって点のように見え、上から見ると暗い地面に溶けた)
    f.key(zero, 740, 'ZEROS', (-2.5, 6.4, 7.5), 25, cut=True)
    f.key(zero, 900, 'ZEROS', (-1.5, 6.7, 8), 20, roll=-15)
    f.key(zero, 1150, 'ZEROS', (-.5, 7, 9.5), 15, roll=10)
    f.key(zero, 1500, 'ZEROS', (.5, 7.2, 11), 10)
    H, P = WHO_HINA, WHO_PAPA
    for t, who, mood, line in ((760, H, 0, 'Can I fly it next time?'), (870, P, 0, "When you're taller."),
                               (980, H, 1, 'I was brave, Papa.'), (980, H, 2, 'I was scared, Papa.'),
                               (1090, P, 1, 'I know. Me too.'), (1090, P, 2, "I know. I'm here now."),
                               (1200, H, 0, 'Pancakes for dinner?'), (1310, P, 0, 'Pancakes.')):
        f.say(t, who, line, mood)
    f.say(1420, WHO_NARR, '')
    f.ev(1500, F.FE_END)
    s.film = f
    s.op_base = 0x8E00
    # エンドロール(src/engine/scene.c の ending_run)。映像の場面の字幕と同じ字体で、見出し(役)は水色、名前は白。
    # 1 行 = [色 + 10h][左端の x] 字…(tools/gen_font.py で真ん中にそろえる)。"\x01" = 得点の行、"\x02" = 終わり。出演者の名前は作り話
    W, C, O = 2, 6, 4                                    # 白・水色・橙(src/engine/engine.h の C_)
    def ln(t, c=W):
        if not t:
            return ''
        x = max(2, (256 - gen_font.advance(t)) // 2)
        return chr(c | 0x10) + chr(x) + t                  # 色に 10h を足す(1 = 得点の行・2 = 終わりの印と分ける)
    def cast(name, role):
        return [ln(name), ln(role, C), '']
    def staff(role, name):
        return [ln(role, C), ln(name), '']
    s.strs += ([ln('He brought his daughter home.', C), '', '', '', '',
                ln('PAPA ZERO', O), '', '', ln('- STARRING -', C), '']
               + cast("BRICK O'HARA", 'as Papa') + cast('MOMO SUZUNARI', 'as Hina') + cast('VIKTOR GRAUSS', 'as the Boss')
               + cast('SILENT STEVE', 'as Kidnapper #1') + cast('OTHER STEVE', 'as Kidnapper #2')
               + cast('KONIGS KRABBE', 'as the Crab') + cast('GRAF ZEPPELIN II', 'as the Airship')
               + [ln('and', C), ln('THE ZERO'), ln('as herself', C), '', '', '',
                  ln('- STAFF -', C), '']
               + staff('ORIGINAL CONCEPT', 'suzuki-black') + staff('DIRECTION', 'suzuki-black')
               + staff('PROGRAM', 'Claude Code (Anthropic Claude)') + staff('GRAPHICS', 'Claude Code (Anthropic Claude)')
               + staff('MUSIC', 'Claude Code (Anthropic Claude)') + staff('VOICES', 'Flite (Carnegie Mellon Univ.)')
               + ['', '', ln('THANK YOU FOR PLAYING!', O), '',
                  '\x01' + chr(W | 0x10) + chr((256 - gen_font.advance('000000')) // 2), '',
                  ln('(C) 2026 suzuki-black'), '', '',
                  ln('PUSH SPACE KEY', C), '\x02'])
    return s

MODS = [opening(), s1(), s2(), s3(), s4(), s5(), s6(), s7(), ending(), seam1(), seam2(), seam3(), seam4(), seam5(), seam6()]
