#!/usr/bin/env python3
"""コクピットの絵(SCREEN 5、256×52、16 色)を作る(指示書 2.4)。

  gen_cockpit.py out.bin [preview.png]

計器盤を手続きで描く。色は指示書 2.2 の固定色(0〜8)だけ使う: 面は鉄灰、窓は黒、目盛りは水色。
数字とバーは実行時に cockpit.c が書くので、ここでは枠とラベルだけ描く。
"""
import sys
from PIL import Image, ImageDraw
import gen_data

W, H = 256, 52
PAL = [(0, 0, 0), (0, 0, 0), (7, 7, 7), (7, 1, 1), (7, 4, 1), (1, 6, 2), (3, 6, 7), (5, 2, 7), (3, 3, 3)]


def glyph(d, x, y, s, c, k=2):
    """3×5 の字を k 倍で(k = 1 は小さな名札)"""
    for ch in s:
        rows = gen_data.FONT.get(ch)
        if rows:
            for j, r in enumerate(rows):
                for i, b in enumerate(r):
                    if b == '#':
                        d.rectangle((x + i * k, y + j * k, x + i * k + k - 1, y + j * k + k - 1), fill=c)
        x += 4 * k


def main(out, preview=None):
    im = Image.new('L', (W, H), 8)
    d = ImageDraw.Draw(im)
    d.rectangle((0, 0, W - 1, 1), fill=1)                  # 風防の下枠
    d.rectangle((0, 2, W - 1, 2), fill=2)
    for x in range(8, W, 16):                              # リベット
        d.point((x, 4), fill=1)
        d.point((x, 50), fill=1)
    # 左: 速度計・高度計(数字は cockpit.c が書く)
    d.rectangle((4, 6, 68, 22), fill=1, outline=6)
    glyph(d, 8, 9, 'KM/H', 6)
    d.rectangle((4, 26, 68, 42), fill=1, outline=6)
    glyph(d, 8, 29, 'ALT', 6)
    # 中: 耐久(HP)・誘導弾の残り(MSL)・機銃の熱(HEAT。満ちると少しの間撃てない)。名札は左、目盛りは cockpit.c が書く
    d.rectangle((72, 6, 140, 20), fill=1, outline=6)
    glyph(d, 75, 9, 'HP', 6)
    d.rectangle((72, 22, 140, 34), fill=1, outline=6)
    glyph(d, 75, 24, 'MSL', 6)
    d.rectangle((72, 36, 140, 44), fill=1, outline=6)
    glyph(d, 75, 38, 'HEAT', 6, 1)
    # 右: 得点・残り時間・レーダー・ヒナの写真
    d.rectangle((142, 6, 194, 20), fill=1, outline=6)
    d.rectangle((142, 24, 194, 46), fill=1, outline=3)
    glyph(d, 151, 40, 'TIME LEFT', 3, 1)
    d.rectangle((198, 6, 234, 44), fill=1, outline=5)
    d.rectangle((215, 23, 217, 26), fill=5)                # 自機
    glyph(d, 207, 46, 'RADAR', 5, 1)
    # ヒナの写真(白い縁。水色の空を背に、おさげ・赤い服。ゲームの中の絵と同じ)
    d.rectangle((237, 5, 254, 45), fill=2)
    d.rectangle((239, 7, 252, 43), fill=6)
    d.ellipse((241, 10, 250, 21), fill=1)                  # 髪
    d.rectangle((239, 14, 240, 23), fill=1)                # おさげ
    d.rectangle((251, 14, 252, 23), fill=1)
    d.point((239, 14), fill=3)
    d.point((252, 14), fill=3)
    d.ellipse((242, 13, 249, 21), fill=4)                  # 顔
    d.point((244, 16), fill=1)
    d.point((247, 16), fill=1)
    d.line((245, 19, 246, 19), fill=3)
    d.polygon([(243, 22), (248, 22), (251, 39), (240, 39)], fill=3)   # 赤い服
    d.line((244, 22, 247, 22), fill=2)
    d.rectangle((243, 40, 244, 43), fill=4)                # 足
    d.rectangle((247, 40, 248, 43), fill=4)
    glyph(d, 238, 46, 'HINA', 2, 1)
    px = im.load()
    data = bytearray()
    for y in range(H):
        for x in range(0, W, 2):
            data.append((px[x, y] << 4) | px[x + 1, y])
    # 後ろにスプライトの絵(照準・敵の名前の札・引き出し線)を付ける。cockpit_load が VRAM 1800h へ送る(ページ0を空けるため)
    for s in gen_data.SPRITES:
        data += bytes(gen_data.sprite_bytes(s))
    with open(out, 'wb') as f:
        f.write(data)
    if preview:
        rgb = Image.new('RGB', (W, H))
        q = rgb.load()
        for y in range(H):
            for x in range(W):
                r, g, b = PAL[px[x, y]]
                q[x, y] = (r * 36, g * 36, b * 36)
        rgb.save(preview)


if __name__ == '__main__':
    main(*sys.argv[1:])
