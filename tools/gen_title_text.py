#!/usr/bin/env python3
"""タイトル画面の文字(PAPA ZERO・PUSH SPACE KEY・著作権表示)を、パレットの番号の絵にする。

  gen_title_text.py <Anton-Regular.ttf> data/title_text.png [preview.png]

- 書体は Anton(Google Fonts。SIL Open Font License 1.1)。書体のファイルはリポジトリに入れず、描いた絵だけを入れる
  (OFL は書体で描いた絵や文書を縛らない)。書体を変えたり文字を直したりするときだけ、手で実行する。
  毎回のビルド(tools/gen_title.py)はこの絵を使うので、書体が無くても ROM は作れる。
- 出力は 256 × 212 の 'P' の PNG。画素の値がタイトルのパレットの番号(tools/gen_title.py の PAL。0 = 絵)。
  SCREEN 11 の YAE の文字はパレットの色のドットなので、YJK の色の共有でにじまない。
- 4 倍の大きさで描いて縮め、半分以上かかった画素を文字にする。MSX の 256 × 212 は 4:3 に引き伸ばして映るので
  (1 ドットが横に約 1.1 倍)、文字は横を 0.9 倍に詰めて描く。
"""
import sys
from PIL import Image, ImageDraw, ImageFont

W, H = 256, 212
S = 4                  # 描く倍率
SQUEEZE = 0.9          # 横の詰め(ドットの縦横比)
# パレットの番号(tools/gen_title.py の PAL と同じ)
EDGE, G1, G2, G3, G4, G5, WHITE, COPY = 1, 2, 3, 4, 5, 9, 6, 8


def text_alpha(font_path, text, cap, cx, top, track=0):
    """text を、大文字の高さ cap ドット・上端 top・中央 cx で描いた 256 × 212 の濃さ(0〜255)。戻り値: (画像, 上端, 下端)"""
    size = 10
    while True:     # 大文字の高さが cap × S になる大きさを探す
        f = ImageFont.truetype(font_path, size)
        b = f.getbbox('H')
        if b[3] - b[1] >= cap * S:
            break
        size += 1
    # 1 字ずつ並べる(字間 track)
    widths = [f.getlength(ch) for ch in text]
    tw = int(sum(widths) + track * S * (len(text) - 1)) + 8
    th = int(cap * S * 1.6) + 8
    tmp = Image.new('L', (tw, th), 0)
    d = ImageDraw.Draw(tmp)
    x = 4
    for ch, w in zip(text, widths):
        d.text((x, 4 - b[1]), ch, font=f, fill=255)
        x += w + track * S
    tmp = tmp.crop(tmp.getbbox())
    tmp = tmp.resize((max(1, int(tmp.width * SQUEEZE)), tmp.height), Image.LANCZOS)
    big = Image.new('L', (W * S, H * S), 0)
    big.paste(tmp, (int(cx * S - tmp.width / 2), int(top * S)))
    return big.resize((W, H), Image.BOX)


def on(a, x, y):
    return 0 <= x < W and 0 <= y < H and a[x, y] >= 128


def main(font_path, out, preview=None):
    m = [[0] * W for _ in range(H)]

    def put(a, fill, edge=EDGE, shadow=0):
        """濃さ a の文字を fill(y → 番号)で塗り、外側 1 ドットを edge で縁取る。shadow なら右下へ影を落とす"""
        px = a.load()
        if shadow:
            for y in range(H):
                for x in range(W):
                    if on(px, x - 1, y - shadow) and not on(px, x, y) and m[y][x] == 0:
                        m[y][x] = edge
        for y in range(H):
            for x in range(W):
                if on(px, x, y):
                    m[y][x] = fill(y)
                elif m[y][x] == 0 and any(on(px, x + dx, y + dy) for dx in (-1, 0, 1) for dy in (-1, 0, 1)):
                    m[y][x] = edge

    # 題: PAPA ZERO(上に 1 行で大きく。空の部分に置き、右上のロケットと、その下の戦闘機を隠さない)
    top, cap = 6, 34
    a = text_alpha(font_path, 'PAPA ZERO', cap, W / 2, top, track=2)
    bands = [(0.16, G1), (0.36, G2), (0.58, G3), (0.80, G4), (1.01, G5)]   # 上から金 → 橙 → 赤茶のグラデーション

    def grad(y):
        t = (y - top) / cap
        for lim, c in bands:
            if t < lim:
                return c
        return G5
    put(a, grad, shadow=2)
    # PUSH SPACE KEY(白。点滅させるので、ほかの文字と行を分ける)
    put(text_alpha(font_path, 'PUSH SPACE KEY', 11, W / 2, 166, track=3), lambda y: WHITE)
    # 著作権表示(一番下。目立たせない)
    put(text_alpha(font_path, '© 2026 suzuki-black', 10, W / 2, 195, track=2), lambda y: COPY)   # 7 ドットでは読めなかった

    img = Image.new('P', (W, H), 0)
    img.putdata([v for row in m for v in row])
    # 見るための色(ゲームの色は tools/gen_title.py の PAL)
    pal = {0: (40, 120, 40), EDGE: (0, 0, 0), G1: (255, 250, 200), G2: (255, 225, 90), G3: (255, 180, 30),
           G4: (235, 120, 10), G5: (150, 50, 10), WHITE: (255, 255, 255), COPY: (200, 200, 215)}
    flat = []
    for i in range(256):
        flat += pal.get(i, (0, 0, 0))
    img.putpalette(flat)
    img.save(out)
    if preview:
        img.convert('RGB').resize((W * 3, H * 3), Image.NEAREST).save(preview)


if __name__ == '__main__':
    main(*sys.argv[1:])
