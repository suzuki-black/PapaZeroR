/* guide.c — 計器盤の説明(モジュール 22 の後ろ、Makefile の OP22_BASE〜に置くコード)。
 *
 * タイトルで 30 秒放っておくと、デモの前に main.c が Stage.hook で呼ぶ。画面を SCREEN 5 の 2 ページ目だけにして、
 * 下 52 ラインの本物の計器盤(cockpit_load が置いたもの)に計器を 1 つずつ橙の枠と線で指し、
 * 上に映像の場面の字幕の字体(面のコードの lb_line)で説明を出す。文面はモジュールの字幕 2 番から(tools/stage_data.py の guide())。
 * キーを押すと 1 を返して終わる(デモに進まず、タイトルへ戻る)。
 *
 * 変数を持たない(モジュールは ROM のまま見えている)。
 */
#include "game.h"
#include "pcm.h"

__sfr __at 0x98 VD;
#define lb_at (*(void (*)(u8, u8))0xD700)
typedef const char *(*LbLine)(const char *, u8, u8, u8, u8);
#define lb_line ((LbLine)0xD703)
#define PANEL 160
#define N_ITEM 9

/* 計器の枠(tools/gen_cockpit.py と同じ。x0, y0, x1, y1 は計器盤の中のドット)、枠の色、線の x。
 * 下の段の計器へは上の段の計器を通って線を引くので、線の x は上の段の名札・数字・目盛りの隙間にする */
static const u8 box[N_ITEM][6] = {
    { 4, 6, 68, 22, C_CYAN, 41 }, { 4, 26, 68, 42, C_CYAN, 41 },
    { 72, 6, 140, 20, C_CYAN, 97 }, { 72, 22, 140, 34, C_CYAN, 97 }, { 72, 36, 140, 44, C_CYAN, 97 },
    { 142, 6, 194, 20, C_CYAN, 167 }, { 142, 24, 194, 46, C_RED, 167 },
    { 198, 6, 234, 44, C_GREEN, 216 }, { 237, 5, 254, 45, C_WHITE, 245 },
};

/* 枠を色 c で描き直す。1 バイト = 2 ドットなので、端のバイトのもう片方は元の色(外は鉄灰 8、中は黒)にする。
 * 左端が偶数の枠は、左のバイトの右のドットが中(黒)。奇数(ヒナの写真)は左のドットが外。右端はどれも偶数で、右のドットが外 */
static void frame(const u8 *b, u8 c)
{
    u8 y, l = b[0] >> 1, r = b[2] >> 1, cc = (u8)(c * 17), hi = (u8)(c << 4);
    for (y = b[1]; y <= b[3]; y++) {
        u8 edge = y == b[1] || y == b[3];
        lb_at(l, (u8)(y + PANEL));
        VD = (b[0] & 1) ? (u8)(0x80 | c) : edge ? cc : (u8)(hi | C_BLACK);
        if (edge) vdp_fill(cc, (u16)(r - l - 1));
        else lb_at(r, (u8)(y + PANEL));
        VD = hi | 8;
    }
}

/* 線が通る所の、計器盤の元の色(計器の縁・計器の中の黒・盤の上の 2 本の線・鋲・鉄灰) */
static u8 panel_px(u8 x, u8 r)
{
    u8 i;
    for (i = 0; i < N_ITEM; i++) {
        const u8 *b = box[i];
        if (x >= b[0] && x <= b[2] && r >= b[1] && r <= b[3])
            return (x == b[0] || x == b[2] || r == b[1] || r == b[3]) ? b[4] : C_BLACK;
    }
    return r < 2 ? C_BLACK : r == 2 ? C_WHITE : (r == 4 && (x & 15) == 8) ? C_BLACK : 8;
}

/* 説明の文から枠の上端の 1 つ上までの縦線(1 ドット)。restore = 1 で元の色に戻す */
static void leader(u8 x, u8 y, u8 r1, u8 c, u8 restore)
{
    u8 r;
    for (; y < PANEL; y++) {
        lb_at(x >> 1, y);
        VD = (x & 1) ? (u8)(0x10 | (restore ? C_BLACK : c)) : (u8)(((restore ? C_BLACK : c) << 4) | C_BLACK);
    }
    for (r = 0; r < r1; r++) {
        u8 me = restore ? panel_px(x, r) : c, other = panel_px(x ^ 1, r);
        lb_at(x >> 1, (u8)(r + PANEL));
        VD = (x & 1) ? (u8)((other << 4) | me) : (u8)((me << 4) | other);
    }
}

u8 op_hook(void)
{
    static const u8 regs[] = { 1, 0xA0, 0, 0x06, 2, 0x3F, 7, 0x01, 8, 0x0A, 9, 0x80, 23, 0x00, 25, 0 };
    u8 i, k, t, key = 0;
    const char *p;
    while (g_flip_req) wait_tick();
    pcm_stop();
    split_off();
    for (i = 0; i < sizeof(regs); i += 2) vdp_wreg(regs[i], regs[i + 1]);
    vdp_set_palette(0, pal_fixed);
    for (i = 0; i < PANEL; i++) { lb_at(0, i); vdp_fill(0x11, 128); }
    /* 計器に見本の値を出す(得点 012340、残り 5:50) */
    life = 8; mis_left = MIS_MAX; g_score = 1234; g_clock = 0x55; g_spd_show = 33; g_alt_show = 12; g_heat = 12;
    cockpit_reset();
    for (i = 0; i < 9; i++) hud_step();
    vdp_wreg(1, 0xE0);
    for (k = 0; k < N_ITEM && !key; k++) {
        const u8 *b = box[k];
        u8 cx = b[5], ly;
        for (i = 8; i < PANEL; i++) { lb_at(0, i); vdp_fill(0x11, 128); }
        p = MOD->str[2 + k];
        ly = (u8)(*p++ * 2);
        while (*p) p = lb_line(p + 3, (u8)p[1], (u8)(p[2] * 2), (u8)(*p & 15), 0);
        frame(b, C_ORANGE);
        leader(cx, ly, b[1], C_ORANGE, 0);
        for (t = 0; t < 160; t++) {
            wait_tick();
            if (input_raw()) { key = 1; break; }
        }
        leader(cx, ly, b[1], C_ORANGE, 1);
        frame(b, b[4]);
        /* 線が通った上の段の数字を書き直す */
        cockpit_reset();
        for (i = 0; i < 9; i++) hud_step();
    }
    screen3_init();
    return key;
}
