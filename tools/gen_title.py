#!/usr/bin/env python3
"""タイトル画面の絵を SCREEN 11(V9958 の YJK + YAE。自然画にパレットの色の文字を重ねる)の VRAM の並びにする。

  gen_title.py art out.bin title.h [preview.png]

- 絵(data/title_art.webp)を 4:3 に切って 256×212 に縮め、YJK で表す(横 4 ドットで色 J・K を共有し、明るさ Y は 1 ドットごと。
  YAE なので Y は 4 ビット)。明るさは誤差拡散でならす。
- 文字は絵と同じ所にある title_text.png(tools/gen_title_text.py が書体 Anton で描いた、パレットの番号の絵)を、
  パレットの色のドット(A = 1)として重ねる。YJK の色の共有でにじまない。
    上: PAPA ZERO(金から赤茶のグラデーション、黒い縁取りと影)
    中: PUSH SPACE KEY(点滅させる。文字の無い 2 ページ目を作り、表示するページを切り替える)
    下: © 2026 suzuki-black
- out.bin = 1 ページ目(文字あり、256×212 = 54272 バイト)+ 文字の無い PUSH SPACE KEY の帯(2 ページ目の同じ行に書く)。
  title.h = 帯の行と大きさ、パレット(16 色、0RRR0BBB / 00000GGG)。
- preview.png は VRAM の値を V9958 と同じ式で色に戻した絵(4:3 に引き伸ばして)。
"""
import os
import sys
from PIL import Image

W, H = 256, 212
# パレット(YAE の文字の色。0RRR0BBB, 00000GGG)。0 は使わない。番号は tools/gen_title_text.py と同じ
PAL = {
    1: (0, 0, 0),       # 縁取り・影
    2: (7, 7, 5),       # PAPA ZERO の上(淡い金)
    3: (7, 7, 2),       # 金
    4: (7, 5, 0),       # 琥珀
    5: (7, 3, 0),       # 橙
    9: (4, 1, 0),       # 下(赤茶)
    6: (7, 7, 7),       # PUSH SPACE KEY(白)
    8: (5, 5, 6),       # 著作権表示(明るい灰色。タイトルより目立たせない)
}
PUSH = 6


def layout(text_png):
    """文字の配置。戻り値: 1 ページ目の文字(各ドットのパレット番号、0 = 絵)、2 ページ目(PUSH SPACE KEY 無し)、帯の行"""
    t = Image.open(text_png)
    if t.size != (W, H) or t.mode != 'P':
        sys.exit('gen_title: %s は 256×212 のパレットの番号の絵(P)にする' % text_png)
    px = t.load()
    m = [[px[x, y] for x in range(W)] for y in range(H)]
    for row in m:
        for v in row:
            if v and v not in PAL:
                sys.exit('gen_title: 文字の絵にパレットに無い番号 %d がある' % v)
    rows = [y for y in range(H) if PUSH in m[y]]
    band = (rows[0] - 2, rows[-1] + 3)                 # 縁取りを含めた PUSH SPACE KEY の帯
    page2 = [r[:] if not band[0] <= y < band[1] else [0] * W for y, r in enumerate(m)]
    return m, page2, band


def clamp(v, lo, hi):
    return lo if v < lo else hi if v > hi else v


def yjk_decode(y, j, k):
    """V9958: R = Y + J、G = Y + K、B = (5Y - 2J - K) / 4(5 ビット、0〜31 に切る)"""
    return (clamp(y + j, 0, 31), clamp(y + k, 0, 31), clamp((5 * y - 2 * j - k) // 4, 0, 31))


def encode(img, mask):
    """img: 256×212 の RGB(0〜255)。mask: パレット番号(0 = 絵)。戻り値: VRAM のバイト列"""
    px = img.load()
    rgb = [[[px[x, y][c] * 31 / 255 for c in range(3)] for x in range(W)] for y in range(H)]
    err = [[0.0] * (W + 2) for _ in range(H + 1)]       # 明るさの誤差拡散(Y の段数のずれ)
    out = bytearray(W * H)
    for y in range(H):
        for g in range(0, W, 4):
            idx = [x for x in range(g, g + 4) if not mask[y][x]]
            # 色(J・K)は絵のドットの平均から
            if idx:
                ys = [(4 * rgb[y][x][2] + 2 * rgb[y][x][0] + rgb[y][x][1]) / 8 for x in idx]
                j = round(sum(rgb[y][x][0] - yy for x, yy in zip(idx, ys)) / len(idx))
                k = round(sum(rgb[y][x][1] - yy for x, yy in zip(idx, ys)) / len(idx))
            else:
                j = k = 0
            j, k = clamp(j, -32, 31), clamp(k, -32, 31)
            ju, ku = j & 63, k & 63
            low = [ku & 7, ku >> 3, ju & 7, ju >> 3]
            for i, x in enumerate(range(g, g + 4)):
                if mask[y][x]:
                    out[y * W + x] = (mask[y][x] << 4) | 8 | low[i]
                    continue
                tr, tg, tb = rgb[y][x]
                e = err[y][x + 1]
                best, bd, bv = 0, 1e9, 0
                for y4 in range(16):                    # YAE: Y は 4 ビット(5 ビットの偶数)
                    yy = y4 * 2
                    r, gg, b = yjk_decode(yy, j, k)
                    lum_t = (2 * tr + 4 * tg + tb) / 7 + e
                    lum = (2 * r + 4 * gg + b) / 7
                    d = (r - tr) ** 2 + (gg - tg) ** 2 + (b - tb) ** 2 + 3 * (lum - lum_t) ** 2
                    if d < bd:
                        bd, best, bv = d, y4, lum_t - lum
                out[y * W + x] = (best << 4) | low[i]
                # Floyd–Steinberg(明るさだけ)
                err[y][x + 2] += bv * 7 / 16
                err[y + 1][x] += bv * 3 / 16
                err[y + 1][x + 1] += bv * 5 / 16
                err[y + 1][x + 2] += bv * 1 / 16
    return out


def decode(vram):
    """VRAM の値を色に戻す(確かめ用)"""
    img = Image.new('RGB', (W, H))
    p = img.load()
    for y in range(H):
        for g in range(0, W, 4):
            b = vram[y * W + g: y * W + g + 4]
            k = (b[0] & 7) | ((b[1] & 7) << 3)
            j = (b[2] & 7) | ((b[3] & 7) << 3)
            k = k - 64 if k >= 32 else k
            j = j - 64 if j >= 32 else j
            for i in range(4):
                v = b[i]
                if v & 8:
                    r, gg, bb = PAL[v >> 4]
                    p[g + i, y] = (r * 255 // 7, gg * 255 // 7, bb * 255 // 7)
                else:
                    r, gg, bb = yjk_decode((v >> 4) * 2, j, k)
                    p[g + i, y] = (r * 255 // 31, gg * 255 // 31, bb * 255 // 31)
    return img


def main(art, out_bin, out_h, preview=None):
    src = Image.open(art).convert('RGB')
    sw, sh = src.size
    cw = sh * 4 // 3                                   # 4:3 に切る(左右を同じだけ)
    x0 = (sw - cw) // 2
    img = src.crop((x0, 0, x0 + cw, sh)).resize((W, H), Image.LANCZOS)
    mask, mask2, band = layout(os.path.join(os.path.dirname(art), 'title_text.png'))
    page1 = encode(img, mask)
    page2 = encode(img, mask2)
    b0, b1 = band
    data = bytes(page1) + bytes(page2[b0 * W: b1 * W])
    open(out_bin, 'wb').write(data)
    with open(out_h, 'w') as f:
        f.write('/* tools/gen_title.py が作る。タイトル画面の絵(SCREEN 11)の配置とパレット */\n')
        f.write(f'#define TITLE_BAND_Y   {b0}      /* PUSH SPACE KEY の帯の先頭の行(2 ページ目に文字の無い帯を書く) */\n')
        f.write(f'#define TITLE_BAND_LEN {(b1 - b0) * W}  /* 帯のバイト数(1 ページ目の後ろに続く) */\n')
        f.write(f'#define TITLE_BYTES    {len(data)}\n')
        pal = []
        for i in range(16):
            r, g, b = PAL.get(i, (0, 0, 0))
            pal += [f'0x{r:x}{b:x}', f'{g}']
        f.write('#define TITLE_PAL { ' + ', '.join(pal) + ' }\n')
    if preview:
        decode(page1).resize((W * 3 * 4 // 3 * 256 // 256 * 1, H * 3), Image.NEAREST).save(preview)


if __name__ == '__main__':
    main(*sys.argv[1:])
