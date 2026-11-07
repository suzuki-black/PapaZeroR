/* fx.c — 爆発の描画(常駐部。HICODE とページ0に入りきらなかった) */
#include "game_int.h"

/* 爆発: 広がる火の玉(白 → 橙 → 赤)と、放物線で飛ぶ破片 4 つ。遠くでも 2 ブロックより小さくしない
 * (前は 16 ティックで、遠くの敵では 3 ブロックほどしかなく、倒したのが見えなかった) */
static const i8 fx_dv[8] = { 5, -7, -5, -7, 8, -3, -8, -3 };    /* 破片の速さ(1/16 ブロック/ティック。x, y)。28 ティックで横に 8〜14 ブロック */

void fx_draw(u8 dt)
{
    u8 i, j;
    Fx *f = fx;
    for (i = 0; i < MAX_FX; i++, f++) {
        V3 c;
        i16 sx, sy, r, x0, y0, x1, y1;
        u8 k, sh = 0;
        if (!f->t) continue;
        f->t = f->t > dt ? f->t - dt : 0;
        pt_cam(f->x, f->y, f->z, &c);
        if (!pt_screen(&c, &sx, &sy)) continue;
        k = (u8)(FX_T + 1 - f->t);                         /* 経過ティック */
        if (c.z > 0x1000) sh = 1;
        if (c.z > 0x3000) sh = 2;
        /* 火の玉: 10 ティックまで広がり、あとは縮む */
        r = (i16)(f->big ? 24 : 14) * (k < 10 ? k : (i16)(f->t > 18 ? 10 : f->t / 2 + 1));
        r >>= sh;
        if (r < 32) r = 32;
        x0 = (sx - r) >> 4; x1 = (sx + r) >> 4; y0 = (sy - r) >> 4; y1 = (sy + r) >> 4;
        if (x0 < 0) x0 = 0;
        if (y0 < 0) y0 = 0;
        if (x1 > 64) x1 = 64;
        if (y1 > 40) y1 = 40;
        g_color = f->t > 20 ? C_WHITE : f->t > 10 ? C_ORANGE : C_RED;
        if (x0 < x1 && y0 < y1) { g_rx = (u8)x0; g_ry = (u8)y0; g_rw = (u8)(x1 - x0); g_rh = (u8)(y1 - y0); rect_fill(); }
        /* 破片: 速さ × 経過 + 重力 */
        g_color = f->t & 2 ? C_WHITE : C_ORANGE;
        for (j = 0; j < 8; j += 2) {
            i16 px = sx + (((i16)fx_dv[j] * k) >> sh);
            i16 py = sy + ((((i16)fx_dv[j + 1] * k) + (i16)k * k / 4) >> sh);   /* 上へ跳ねてから落ちる */
            px >>= 4; py >>= 4;
            if (px < 0 || px > 62 || py < 0 || py > 38) continue;
            g_rx = (u8)px; g_ry = (u8)py; g_rw = f->big ? 2 : 1; g_rh = g_rw;
            rect_fill();
        }
    }
}

/* パレットの補間(ページ0に空きが無いので game.c からこちらへ) */
void lerp_pal(const u8 *a, const u8 *b, u8 k, u8 *o)   /* k = 0..16 */
{
    u8 i;
    for (i = 0; i < 14; i += 2) {
        u8 r0 = a[i] >> 4, b0 = a[i] & 7, g0 = a[i + 1], r1 = b[i] >> 4, b1 = b[i] & 7, g1 = b[i + 1];
        u8 r = (u8)(r0 + (((i16)r1 - r0) * k >> 4));
        u8 bl = (u8)(b0 + (((i16)b1 - b0) * k >> 4));
        u8 g = (u8)(g0 + (((i16)g1 - g0) * k >> 4));
        o[i] = (u8)((r << 4) | bl);
        o[i + 1] = g;
    }
}
