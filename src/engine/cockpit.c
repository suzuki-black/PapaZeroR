/* cockpit.c — 下 52 ライン(SCREEN 5)の計器盤と黒帯(指示書 2.4)
 *
 * 絵は tools/gen_cockpit.py が作り、ROM のバンク COCKPIT_BANK〜 に置く(52 ライン × 128 バイト = 6656 バイト)。
 * VRAM の 2 ページ目(8000h-)の 160 ライン目から写す。4 ページ目(18000h-)は場面の黒帯。
 * 指示書では数字とバーを VDP コマンドで書くが、VDP コマンドは分割線でモードが変わると止まる(openMSX の実装でも V9958 でも、
 * SCREEN 3 の間は CMD ビットなしでは動かない)ので、CPU で書く。1 フレームに 1 項目だけ更新し、1 文字約 0.5ms で済ませる。
 */
#include "game.h"
#include "sound.h"

#define BOT_ROW 160
#define RAD_N 4
extern i16 g_fx, g_fz;
#define g_rad_fx g_fx
#define g_rad_fz g_fz
extern u8 g_r2_bot;              /* sys.s */
static u8 bot_hi;                /* VRAM の番地の A16〜A14: 2 = 計器盤、6 = 黒帯 */
u8 g_spd_show, g_alt_show, g_heat;
static u16 sh_score;
static u16 sh_mis;
static u8 sh_life, sh_spd, sh_alt, sh_clock, sh_heat, sh_crack;
static u8 sh_dig[6];
static u8 hud_rr;
static u8 rad_x[RAD_N], rad_y[RAD_N], rad_on[RAD_N];
static const char *sub_req;

/* (x バイト = 2 ドット単位, y ドット) の VRAM 番地を設定 */
static void bot_addr(u8 x, u8 y)
{
    u16 a = (u16)(y + BOT_ROW) * 128 + x;
    vdp_set_write_hi((u8)(bot_hi + (a >> 14)), a & 0x3FFF);
}

static void bot_rect(u8 x, u8 y, u8 w, u8 h, u8 c)
{
    u8 b = (u8)(c * 17);
    for (; h; h--, y++) {
        bot_addr(x, y);
        vdp_fill(b, w);
    }
}

/* 3×5 の字を 2 倍(6×10 ドット)で。字の幅 4 バイト */
static void bot_char(u8 x, u8 y, char ch, u8 fg, u8 bg)
{
    u8 r, i, row[4], f = (u8)(fg * 17), b = (u8)(bg * 17), n, bits;
    n = (ch >= 0x20 && ch <= 0x7F) ? font35_map[ch - 0x20] : 0xFF;
    for (r = 0; r < 5; r++) {
        bits = (n == 0xFF) ? 0 : font35[(u16)n * 5 + r];
        for (i = 0; i < 3; i++) row[i] = (bits & (4 >> i)) ? f : b;
        row[3] = b;
        bot_addr(x, (u8)(y + r * 2));
        vdp_out(row, 4);
        bot_addr(x, (u8)(y + r * 2 + 1));
        vdp_out(row, 4);
    }
}

static void bot_text(u8 x, u8 y, const char *s, u8 fg, u8 bg)
{
    for (; *s; s++, x += 4) bot_char(x, y, *s, fg, bg);
}

static void bot_num(u8 x, u8 y, u16 v, u8 digits, u8 fg, u8 bg)
{
    u8 i;
    x += (u8)(digits * 4);
    for (i = 0; i < digits; i++) {
        u16 q = 0;
        u8 d;
        while (v >= 1000) { v -= 1000; q += 100; }
        while (v >= 100) { v -= 100; q += 10; }
        while (v >= 10) { v -= 10; q++; }
        d = (u8)v;
        v = q;
        x -= 4;
        bot_char(x, y, (char)('0' + d), fg, bg);
    }
}

void cockpit_load(void)
{
    u8 i;
    /* 計器盤の絵: 2 バンク(16KB)をページ2へ写して VRAM へ。ページ2は面のモジュールなので、終わったら読み直す */
    rom_load(COCKPIT_BANK);
    vdp_set_write_hi(3, 0x1000);                  /* 8000h + 160 × 128 = D000h */
    vdp_out((const u8 *)0x8000, 6656);
    /* スプライトの絵(tools/gen_cockpit.py が後ろに付けた)。約 1KB 以上を一度に送ると分割画面の切り替えがずれ、
     * 数秒のあいだ上の画面が下の画面のモードで出た(タイトルの絵が化けて見えた)。帰線の直後に 4 回に分けて送る */
    for (i = 0; i < 4; i++) {
        wait_tick();
        vdp_set_write(0x1800 + i * (SPR_PAT_BYTES / 4));
        vdp_out((const u8 *)(0x8000 + 6656) + i * (SPR_PAT_BYTES / 4), SPR_PAT_BYTES / 4);
    }
    rom_load(MOD_BANK0 + 2 * g_mod);
    /* 黒帯(4 ページ目の 160〜211 ライン) */
    bot_hi = 6;
    for (i = 0; i < 52; i += 4) bot_rect(0, i, 128, 4, 1);
    bot_hi = 2;
}

void cockpit_mode(u8 letterbox)
{
    g_r2_bot = letterbox ? 0x7F : 0x3F;
    bot_hi = letterbox ? 6 : 2;
    sub_req = 0;
    if (letterbox) bot_rect(0, 18, 128, 12, 1);
}

void sub_text(const char *s) { sub_req = s; }

static void sub_draw(const char *s)
{
    u8 n = 0, x;
    const char *p = s;
    while (*p++) n++;
    if (n > 30) n = 30;
    x = (u8)(64 - n * 2);
    bot_rect(0, 18, 128, 12, 1);
    bot_text(x, 19, s, C_WHITE, C_BLACK);
}

void cockpit_reset(void)
{
    u8 i;
    sh_score = 0xFFFF; sh_life = 0xFF; sh_mis = 0xFFFF; sh_spd = 0xFF; sh_alt = 0xFF; sh_clock = 0xFF; sh_heat = 0xFF; sh_crack = 0;
    for (i = 0; i < 6; i++) sh_dig[i] = 0xFF;
    for (i = 0; i < RAD_N; i++) rad_on[i] = 0;
}

/* レーダー: 自機が中央、上が進む向き、右が右(視線が回っても左右は入れ替わらない)。1 フレームに 1 点。ボスは大きい点 */
#define RAD_CX 108                /* バイト */
#define RAD_CY 25
static u8 rad_k, rad_i;

static void radar_step(void)
{
    u8 k = rad_k;
    const Obj *o;
    u8 n;
    rad_k = (u8)(k + 1) & (RAD_N - 1);
    if (rad_on[k]) { bot_rect(rad_x[k], rad_y[k], rad_on[k], 3, C_BLACK); rad_on[k] = 0; }
    for (n = 0; n < MAX_OBJ; n++) {
        rad_i = rad_i + 1 < MAX_OBJ ? rad_i + 1 : 0;
        o = &obj[rad_i];
        if ((o->t >= T_E01 && o->t <= T_E08) || o->t == T_PART) break;
    }
    if (n == MAX_OBJ) return;
    {
        i16 dx = o->x - cam_x, dz = o->z - cam_z;
        i16 rt = fmul(dx, g_rad_fz) - fmul(dz, g_rad_fx);
        i16 fw = fmul(dx, g_rad_fx) + fmul(dz, g_rad_fz);
        i16 x = rt >> 11, y = fw >> 10;        /* 横 ±64 単位 = ±8 バイト、縦 ±64 単位 = ±16 ドット */
        if (x < -8 || x > 7 || y < -16 || y > 15) return;
        rad_x[k] = (u8)(RAD_CX + x);
        rad_y[k] = (u8)(RAD_CY - y);
        rad_on[k] = o->t == T_PART ? 2 : 1;
        bot_rect(rad_x[k], rad_y[k], rad_on[k], 3, o->t == T_PART ? C_RED : C_GREEN);
    }
}

void cockpit_vram(void)
{
    if (sub_req && bot_hi == 6) { sub_draw(sub_req); sub_req = 0; }
    else if (g_scene == 1 || g_scene == 2) hud_step();
}

/* 1 フレームに 1 項目だけ書く */
void hud_step(void)
{
    u8 i;
    if (bot_hi != 2) return;
    for (i = 0; i < 9; i++) {
        /* 0〜7 = 計器、8 = レーダー(奇数フレーム)。レーダーが計器の番を横取りすると、撃ち続けて過熱のバーが
         * 毎フレーム変わるときに高度の番がいつも奇数フレームに当たり、高度が一度も書かれなかった */
        hud_rr = hud_rr >= 8 ? 0 : (u8)(hud_rr + 1);
        if (hud_rr == 8) {
            if (g_scene == 1 && (g_frames & 1)) { radar_step(); return; }
            continue;
        }
        switch (hud_rr) {
        case 0:
            if (sh_life != life) {
                u8 k;
                sh_life = life;
                for (k = 0; k < 8; k++) bot_rect((u8)(37 + k * 4), 8, 3, 10, k < life ? (life <= 2 ? C_RED : C_GREEN) : C_BLACK);
                return;
            }
            break;
        case 1:
            if (sh_mis != mis_left) {
                sh_mis = mis_left;
                bot_num(37, 25, mis_left, 3, C_WHITE, C_BLACK);     /* 残りの数(面ごとに 500) */
                return;
            }
            break;
        case 2:
            if (sh_score != g_score) {
                /* 得点は 6 桁(表示の最後の桁は常に 0) */
                sh_score = g_score;
                bot_num(72, 8, g_score, 5, C_WHITE, C_BLACK);
                bot_char(92, 8, '0', C_WHITE, C_BLACK);
                return;
            }
            break;
        case 3:
            if (sh_spd != g_spd_show) { sh_spd = g_spd_show; bot_num(21, 8, (u16)g_spd_show * 10, 3, C_CYAN, C_BLACK); return; }
            break;
        case 4:
            if (sh_alt != g_alt_show) { sh_alt = g_alt_show; bot_num(21, 28, g_alt_show, 3, C_CYAN, C_BLACK); return; }
            break;
        case 5:
            if (sh_clock != g_clock) {
                sh_clock = g_clock;
                bot_char(76, 28, (char)('0' + (g_clock >> 4)), C_RED, C_BLACK);
                bot_char(80, 28, ':', C_RED, C_BLACK);
                bot_char(84, 28, (char)('0' + (g_clock & 15)), C_RED, C_BLACK);
                bot_char(88, 28, '0', C_RED, C_BLACK);
                return;
            }
            break;
        case 6:
            if (sh_heat != g_heat) { sh_heat = g_heat; bot_rect(37, 38, (u8)(g_heat + 1), 4, g_heat > 20 ? C_RED : C_ORANGE); bot_rect((u8)(38 + g_heat), 38, (u8)(23 - g_heat), 4, C_BLACK); return; }
            break;
        default: {
            u8 c = life <= 2 ? 3 : life <= 4 ? 2 : life <= 6 ? 1 : 0;
            if (c > sh_crack) {  /* 風防のひび(被弾の段階) */
                static const u8 cr[6] = { 34, 2, 60, 4, 92, 3 };
                u8 k = (u8)(sh_crack * 2), j;
                sh_crack++;
                for (j = 0; j < 8; j++) bot_rect((u8)(cr[k] + j), (u8)(cr[k + 1] + j), 1, 1, C_WHITE);
                return;
            }
            break; }
        }
    }
}
