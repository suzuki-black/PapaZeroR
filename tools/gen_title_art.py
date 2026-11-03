#!/usr/bin/env python3
"""タイトルの絵の元(朝焼けの納屋の前の零戦のコクピットと、父の背中)を手続きで描く(指示書 7.3)。
  gen_title_art.py data/title_art.png
"""
import math
import sys
from PIL import Image, ImageDraw, ImageFilter

W, H = 800, 600


def lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def main(out):
    im = Image.new('RGB', (W, H))
    d = ImageDraw.Draw(im)
    stops = [(0, (40, 30, 90)), (.3, (180, 70, 110)), (.5, (250, 150, 80)), (.62, (255, 225, 150))]
    for y in range(H):
        t = y / H
        for i in range(len(stops) - 1):
            if stops[i][0] <= t <= stops[i + 1][0]:
                c = lerp(stops[i][1], stops[i + 1][1], (t - stops[i][0]) / (stops[i + 1][0] - stops[i][0]))
                break
        else:
            c = stops[-1][1]
        d.line((0, y, W, y), fill=c)
    d.ellipse((520, 280, 640, 400), fill=(255, 245, 200))
    # 山
    for k, (base, col) in enumerate(((360, (90, 60, 110)), (390, (60, 45, 80)))):
        pts = [(0, H)]
        for x in range(0, W + 20, 20):
            pts.append((x, base - 50 * math.sin(x / (90 + k * 50) + k * 2) - 24 * math.sin(x / 31 + k)))
        pts.append((W, H))
        d.polygon(pts, fill=col)
    # 地面
    d.rectangle((0, 430, W, H), fill=(44, 62, 36))
    # 納屋
    d.polygon([(70, 440), (70, 270), (190, 200), (310, 270), (310, 440)], fill=(92, 40, 34))
    d.polygon([(50, 276), (190, 190), (330, 276), (310, 276), (190, 212), (70, 276)], fill=(40, 26, 30))
    d.rectangle((150, 320, 230, 440), fill=(30, 20, 24))
    d.line((150, 320, 230, 440), fill=(120, 60, 50), width=4)
    d.line((230, 320, 150, 440), fill=(120, 60, 50), width=4)
    # 零戦の機首と翼(手前)
    d.polygon([(0, 520), (800, 470), (800, 520), (0, 600)], fill=(190, 195, 180))
    d.polygon([(330, 600), (390, 370), (640, 370), (720, 600)], fill=(205, 210, 196))
    d.ellipse((560, 505, 640, 585), fill=(190, 30, 34))
    # 風防
    d.polygon([(400, 372), (440, 280), (590, 280), (632, 372)], fill=(120, 170, 190))
    d.line((515, 280, 515, 372), fill=(50, 60, 70), width=6)
    d.line((400, 372, 632, 372), fill=(50, 60, 70), width=8)
    d.line((440, 280, 590, 280), fill=(50, 60, 70), width=6)
    # 父の背中
    d.ellipse((488, 300, 542, 354), fill=(60, 50, 44))
    d.polygon([(466, 372), (480, 345), (550, 345), (564, 372)], fill=(50, 66, 50))
    # 機首の HINA
    for i, seg in enumerate(([(0, 0, 0, 30), (24, 0, 24, 30), (0, 15, 24, 15)], [(12, 0, 12, 30)], [(0, 30, 0, 0), (0, 0, 24, 30), (24, 30, 24, 0)], [(0, 30, 12, 0), (12, 0, 24, 30), (6, 18, 18, 18)])):
        for x0, y0, x1, y1 in seg:
            d.line((400 + i * 38 + x0, 500 + y0, 400 + i * 38 + x1, 500 + y1), fill=(40, 40, 50), width=5)
    im.filter(ImageFilter.GaussianBlur(.6)).save(out)


if __name__ == '__main__':
    main(sys.argv[1])
