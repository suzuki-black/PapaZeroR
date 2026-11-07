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


def glyph(d, x, y, s, c):
    for ch in s:
        rows = gen_data.FONT.get(ch)
        if rows:
            for j, r in enumerate(rows):
                for i, k in enumerate(r):
                    if k == '#':
                        d.rectangle((x + i * 2, y + j * 2, x + i * 2 + 1, y + j * 2 + 1), fill=c)
        x += 8


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
    # 中: 耐久・誘導弾・温度
    d.rectangle((72, 6, 140, 20), fill=1, outline=6)
    d.rectangle((72, 22, 140, 34), fill=1, outline=6)
    d.rectangle((72, 36, 122, 44), fill=1, outline=6)
    # 右: 得点・時計・レーダー・ヒナの写真
    d.rectangle((142, 6, 194, 20), fill=1, outline=6)
    d.rectangle((150, 26, 186, 40), fill=1, outline=3)
    d.rectangle((198, 6, 234, 44), fill=1, outline=5)
    d.rectangle((215, 23, 217, 26), fill=5)                # 自機
    d.rectangle((238, 6, 253, 44), fill=2, outline=1)
    d.ellipse((240, 10, 251, 22), fill=4)
    d.rectangle((241, 23, 250, 43), fill=3)
    d.point((243, 15), fill=1)
    d.point((248, 15), fill=1)
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
