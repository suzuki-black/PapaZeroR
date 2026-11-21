/* fx.c — 爆発の描画(常駐部。HICODE とページ0に入りきらなかった) */
#include "game_int.h"

/* 爆発: 広がる火の玉(白 → 橙 → 赤)と、放物線で飛ぶ破片 4 つ。遠くでも 2 ブロックより小さくしない
 * (前は 16 ティックで、遠くの敵では 3 ブロックほどしかなく、倒したのが見えなかった) */
static const i8 fx_dv[8] = { 4, -6, -4, -6, 6, -3, -6, -3 };    /* 破片の速さ(1/16 ブロック/ティック。x, y)。40 ティックで横に 10〜15 ブロック */

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
        /* 火の玉: 12 ティックまで広がり、あとはゆっくり縮む */
        r = (i16)(f->big ? 32 : 16) * (k < 12 ? k : (i16)(f->t > 24 ? 12 : f->t / 2 + 1));
        r >>= sh;
        if (r < 32) r = 32;
        if (r > 256) r = 256;                              /* 近くでも半径 16 ブロックまで(画面を覆うと何が起きたか見えない) */
        x0 = (sx - r) >> 4; x1 = (sx + r) >> 4; y0 = (sy - r) >> 4; y1 = (sy + r) >> 4;
        if (x0 < 0) x0 = 0;
        if (y0 < 0) y0 = 0;
        if (x1 > 64) x1 = 64;
        if (y1 > 40) y1 = 40;
        g_color = f->t > 30 ? C_WHITE : f->t > 14 ? C_ORANGE : C_RED;
        if (x0 < x1 && y0 < y1) { g_rx = (u8)x0; g_ry = (u8)y0; g_rw = (u8)(x1 - x0); g_rh = (u8)(y1 - y0); rect_fill(); }
        /* 破片: 速さ × 経過 + 重力 */
        g_color = f->t & 2 ? C_WHITE : C_ORANGE;
        for (j = 0; j < 8; j += 2) {
            i16 px = sx + (((i16)fx_dv[j] * k) >> sh);
            i16 py = sy + ((((i16)fx_dv[j + 1] * k) + ((MOD->flags & SF_SPACE) ? 0 : (i16)k * k / 4)) >> sh);   /* 上へ跳ねてから落ちる(宇宙ではまっすぐ飛び散る) */
            px >>= 4; py >>= 4;
            if (px < 0 || px > 61 || py < 0 || py > 37) continue;   /* 大きい破片(3 ブロック)も画面の中に収める(rect_fill は切らない) */
            g_rx = (u8)px; g_ry = (u8)py; g_rw = f->big ? 3 : 1; g_rh = g_rw;
            rect_fill();
        }
    }
}

/* パレットの補間(ページ0に空きが無いので game.c からこちらへ)。成分ごとの補間を 1 つの関数にまとめて小さくした(常駐部に空きが無い) */
static u8 lerp1(u8 a, u8 b, u8 k)      /* a + (b - a) * k / 16 */
{
    return (u8)(a + (((i16)b - a) * k >> 4));
}

void lerp_pal(const u8 *a, const u8 *b, u8 k, u8 *o)   /* k = 0..16 */
{
    u8 i;
    for (i = 0; i < 14; i += 2) {
        o[i] = (u8)((lerp1(a[i] >> 4, b[i] >> 4, k) << 4) | lerp1(a[i] & 7, b[i] & 7, k));
        o[i + 1] = lerp1(a[i + 1], b[i + 1], k);
    }
}
