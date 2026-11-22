/* view.c — カメラ行列、空と地面、メッシュの描画(指示書 8.2 / 8.3 / 8.5) */
#include <string.h>
#include "view.h"

i16 cam_x, cam_y, cam_z;
u8  cam_yaw, cam_pitch, cam_roll;
i16 cm[9];
i8  cm8[9];
HitRect hits[MAX_HIT];
u8 n_hits;

static u8 mm_ok;
/* 8 ビットの sin/cos(±127)の積 >> 7 */
#define M7(a, b) ((i16)(((i16)(a) * (i16)(b)) >> 7))

void cam_update(void)
{
    i16 sy = SIN(cam_yaw) >> 1, cy = COS(cam_yaw) >> 1;
    i16 sp = SIN(cam_pitch) >> 1, cp = COS(cam_pitch) >> 1;
    i16 sr = SIN(cam_roll) >> 1, cr = COS(cam_roll) >> 1;
    i16 r[3], u[3], f[3], t;
    u8 i;
    /* ヨー */
    r[0] = cy;  r[1] = 0;   r[2] = -sy;
    u[0] = 0;   u[1] = 128; u[2] = 0;
    f[0] = sy;  f[1] = 0;   f[2] = cy;
    /* ピッチ(正 = 上を向く) */
    for (i = 0; i < 3; i++) {
        t = u[i];
        u[i] = M7(t, cp) - M7(f[i], sp);
        f[i] = M7(t, sp) + M7(f[i], cp);
    }
    /* ロール(正 = 右へ傾く) */
    for (i = 0; i < 3; i++) {
        t = r[i];
        r[i] = M7(t, cr) - M7(u[i], sr);
        u[i] = M7(u[i], cr) + M7(t, sr);
    }
    for (i = 0; i < 3; i++) {
        i16 a = r[i], b = u[i], c = f[i];
        cm[i] = a << 1; cm[3 + i] = b << 1; cm[6 + i] = c << 1;
        cm8[i] = (i8)(a > 127 ? 127 : a < -127 ? -127 : a);
        cm8[3 + i] = (i8)(b > 127 ? 127 : b < -127 ? -127 : b);
        cm8[6 + i] = (i8)(c > 127 ? 127 : c < -127 ? -127 : c);
    }
    mm_ok = 0;
}

/* pt_cam は math.s */

u8 pt_screen(const V3 *c, i16 *sx, i16 *sy)
{
    i16 o[2];
    if (c->z < NEAR_Z) return 0;
    project2(c, o);
    *sx = o[0];
    *sy = o[1];
    return 1;
}

/* 画面全体の四角形を半平面 a x + b y + c > 0 で切って塗る。x, y は画面の中心からのブロック数(4 ビットの小数を落とす) */
static i16 hp_x[8], hp_y[8];

static void halfplane(i16 a, i16 b, i16 c, u8 color)
{
    static const i16 qx[4] = { 0, 1024, 1024, 0 };
    static const i16 qy[4] = { 0, 0, 640, 640 };
    i16 f0, f1, x0, y0, x1, y1, fq[4];
    i16 ax = a << 5, by = (b << 4) + (b << 2);     /* 四隅は中心から (±32, ±20) ブロック。掛け算を使わない */
    u8 i, n = 0;
    fq[0] = c - ax - by; fq[1] = c + ax - by; fq[2] = c + ax + by; fq[3] = c - ax + by;
    x0 = qx[3]; y0 = qy[3];
    f0 = fq[3];
    for (i = 0; i < 4; i++) {
        x1 = qx[i]; y1 = qy[i];
        f1 = fq[i];
        if ((f0 > 0) != (f1 > 0)) {
            i16 d = f0 - f1;
            hp_x[n] = x0 + muldiv(x1 - x0, f0, d);
            hp_y[n] = y0 + muldiv(y1 - y0, f0, d);
            n++;
        }
        if (f1 > 0) { hp_x[n] = x1; hp_y[n] = y1; n++; }
        x0 = x1; y0 = y1; f0 = f1;
    }
    if (n >= 3) {
        for (i = 0; i < n; i++) { scr[i * 2] = hp_x[i]; scr[i * 2 + 1] = hp_y[i]; }
        raster(n, color);
    }
}

/* 傾いた空: 境目の 3 本の線(a X + b Y + c_k = 0)の列を行ごとに求め、4 色を 1 回ずつ塗る。
   多角形 3 枚を全面に重ねるより、塗る量が 1 画面分で済む。X = 列の中心 - 32、Y = 行の中心 - 20(ブロック) */
void span_fill(u8 row0, u8 n);          /* face.s: span_a[r]〜span_b[r] を g_color で */
#define SPAN_A ((u8 *)0xDE00)
#define SPAN_B ((u8 *)0xDF00)
static u8 tb[3][GAME_ROWS];

extern i16 g_tx0, g_txf, g_ts, g_trnd;  /* face.s の tilt_rows: 行 0 の線の x = g_tx0 / 2 + g_txf / 256、行ごとの増分(8.8)、丸め */
void tilt_rows(u8 *t);

static void sky_tilt(i16 a, i16 b, i16 c)
{
    static const i16 off[3] = { 400, 0, -420 };   /* 線 0 の正の側 = 明るい地面より上、1 = 空、2 = 高い空 */
    static const u8 col_pos[4] = { C_GND2, C_GND1, C_SKY1, C_SKY2 };
    static const u8 col_neg[4] = { C_SKY2, C_SKY1, C_GND1, C_GND2 };
    const u8 *col = a < 0 ? col_neg : col_pos;
    u8 k, r, flat = a == 0;
    if (!flat) {
        g_ts = muldiv(-b, 256, a);
        g_trnd = a > 0 ? 8064 + 256 : 8064 + 255;   /* a > 0: floor(x + 31.5) + 1、a < 0: ceil(x + 31.5) */
    }
    for (k = 0; k < 3; k++) {
        u8 *t = tb[!flat && a < 0 ? (u8)(2 - k) : k];    /* tb は左から右へ並ぶ順 */
        i16 ck = c + off[k];
        if (flat) {
            /* 横一直線: 行ごとに全部か無しか(f = b Y + c_k の符号。Y は 0.5 ブロック単位で数える) */
            i16 f = 2 * ck - 39 * b;
            for (r = 0; r < GAME_ROWS; r++, f += 2 * b) t[r] = f > 0 ? 0 : 64;
        } else {
            /* x(r) = -(b Y + c_k) / a。行 0 の x = n / 2a は数千ブロックになることがあるので、商と余りに分けて渡す */
            i16 n = 39 * b - 2 * ck, q = n / a;
            g_tx0 = q;
            g_txf = muldiv(n - q * a, 128, a);
            tilt_rows(t);
        }
    }
    for (k = 0; k < 4; k++) {
        if (k == 0) memset(SPAN_A, 0, GAME_ROWS); else memcpy(SPAN_A, tb[k - 1], GAME_ROWS);
        if (k == 3) memset(SPAN_B, 64, GAME_ROWS); else memcpy(SPAN_B, tb[k], GAME_ROWS);
        g_color = col[k];
        span_fill(0, GAME_ROWS);
    }
}

/* 空と地面の境の行: (r - 20) * uy = k を丸めて 0..行数に収める。uy > 0 */
static i8 sky_row(i16 k, i16 uy)
{
    i16 r = 20 + k / uy;
    return (i8)(r < 0 ? 0 : r > GAME_ROWS ? GAME_ROWS : r);
}

static void sky_rows(i8 a, i8 b, u8 color)
{
    if (a >= b) return;
    g_rh = (u8)(b - a);
    buf_fill_rows(color, (u8)a);
}

void sky_draw(u8 space)
{
    /* 世界の上の向き(カメラ空間) = 行列の列 1。(sx, -sy, 32) との内積が正なら空 */
    i16 ux = cm8[1], uy = cm8[4], uz = cm8[7];
    i16 a = ux, b = -uy, c = uz * 32;
    if (space) {                        /* 宇宙: 黒い空の下に地球(青と、縁の白い雲)。深宇宙(4)は地球が無く、星は空の飾り(game.c の sky_marks)で描く */
        buf_fill(C_BLACK);
        if (!(space & 4)) {
            halfplane(-a, -b, -(c + 500), C_GND2);
            halfplane(-a, -b, -(c + 640), C_GND1);
        }
        return;
    }
    if (ux == 0 && uy > 32) {
        /* 傾いていないとき(ふだんのほとんど): 境目は水平なので行ごとに塗る。多角形 3 枚より約 5ms 軽い */
        i8 r0 = sky_row(c - 420, uy), r1 = sky_row(c, uy), r2 = sky_row(c + 400, uy);
        sky_rows(0, r0, C_SKY2);
        sky_rows(r0, r1, C_SKY1);
        sky_rows(r1, r2, C_GND1);
        sky_rows(r2, GAME_ROWS, C_GND2);
        return;
    }
    sky_tilt(a, b, c);
}

/* カメラ行列 × R(ヨー, ロール)。物体のローカル座標 → カメラ空間の行列(±127)。同じ向きが続くことが多いので、直前の結果を使い回す */
i8 g_mm[9];
static u8 mm_yaw, mm_roll;

void mat_yaw(u8 yaw, u8 roll)
{
    if (mm_ok && yaw == mm_yaw && roll == mm_roll) return;
    mm_ok = 1; mm_yaw = yaw; mm_roll = roll;
    mat_y(yaw, g_mm);
    if (roll) {
        i16 sr = SIN(roll) >> 1, cr = COS(roll) >> 1;
        u8 i;
        for (i = 0; i < 9; i += 3) {
            i16 lx = g_mm[i], b = g_mm[i + 1];
            g_mm[i] = (i8)(M7(lx, cr) + M7(b, sr));
            g_mm[i + 1] = (i8)(M7(b, cr) - M7(lx, sr));
        }
    }
}

/* 面の振り分けと当たり矩形は face.s。ニアクリップ面より手前の頂点を含む面だけ、game.c の face_near で切って塗る */
extern i16 g_hb[4];
void faces_draw(const Face *f);
void hit_bounds(u8 nv);

u8 g_lod_min, g_obj_yaw;
u8 g_perf_polys;
u16 g_perf_verts;

/* mesh_draw は face.s。当たり矩形(頂点の外接矩形、ブロック)だけここで登録する。nv = 変換した頂点の数 */
extern u8 g_md_id;

void hit_add(u8 nv, const V3 *c)
{
    i16 x0, x1, y0, y1;
    HitRect *h;
    if (n_hits >= MAX_HIT) return;
    hit_bounds(nv);
    x0 = g_hb[0]; x1 = g_hb[1]; y0 = g_hb[2]; y1 = g_hb[3];
    if (x1 < 0 || y1 < 0 || x0 >= 1024 || y0 >= 640 || x0 > x1) return;
    h = &hits[n_hits++];
    h->x0 = x0 < 0 ? 0 : (u8)(x0 >> 4);
    h->y0 = y0 < 0 ? 0 : (u8)(y0 >> 4);
    h->x1 = x1 >= 1024 ? 64 : (u8)((x1 >> 4) + 1);
    h->y1 = y1 >= 640 ? 40 : (u8)((y1 >> 4) + 1);
    h->z = c->z;
    h->id = g_md_id;
}

/* 帯: 中心線 (x0,y0)-(x1,y1) の両端にブロック数の太さを付けた四角形 */
void band_draw(i16 x0, i16 y0, i16 x1, i16 y1, u8 w0, u8 w1, u8 color)
{
    i16 dx = x1 - x0, dy = y1 - y0;
    i16 ax = dx < 0 ? -dx : dx, ay = dy < 0 ? -dy : dy;
    i16 w0p = (i16)w0 << 3, w1p = (i16)w1 << 3;
    if (ax > ay) {
        scr[0] = x0; scr[1] = y0 - w0p;
        scr[2] = x1; scr[3] = y1 - w1p;
        scr[4] = x1; scr[5] = y1 + w1p;
        scr[6] = x0; scr[7] = y0 + w0p;
    } else {
        scr[0] = x0 + w0p; scr[1] = y0;
        scr[2] = x1 + w1p; scr[3] = y1;
        scr[4] = x1 - w1p; scr[5] = y1;
        scr[6] = x0 - w0p; scr[7] = y0;
    }
    raster(4, color);
}
