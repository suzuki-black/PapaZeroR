/* scene.c — タイトル・ゲームオーバー・エンドロール(指示書 7.3 / 7.4) */
#include "game.h"
#include "hud.h"
#include "sound.h"
#include "pcm.h"
#include "title.h"

static const u8 title_pal[32] = TITLE_PAL;
#define TITLE_PAGE 54272u
#define MENU_N 11

static const char * const menu_name[MENU_N] = { "DAMAGE", "NODAMAGE", "STAGE", "LIFE", "ONESHOT", "FPS", "XFER", "SPLIT", "ROLL", "LOCKBOX", "FILM" };
static const u8 menu_lo[MENU_N] = { 1, 0, 1, 1, 0, 0, 0, 0, 0, 1, 0 };
static const u8 menu_hi[MENU_N] = { 8, 1, 7, 8, 1, 1, 1, 1, 1, 4, 8 };

/* 隠しコンフィグ: 上下で項目、左右で値。スペースで戻る */
static void config_show(void)
{
    u8 sel = 0, prev = 0xFF, in, i;
    u8 *v = (u8 *)&g_cfg;
    for (;;) {
        /* 字は 5 行あるので 6 行おきに 6 項目だけ出し、選んだ項目に合わせて送る(3 行おきで 9 項目だと重なった) */
        u8 top = sel > 5 ? sel - 5 : 0;
        buf_fill(C_BLACK);
        for (i = 0; i < 6; i++) {
            u8 k = top + i;
            text_draw(4, (i8)(i * 6 + 3), menu_name[k], k == sel ? C_RED : C_WHITE, 1);
            num_draw(44, (i8)(i * 6 + 3), v[k], 2, C_CYAN);
        }
        present();
        in = input_raw();
        if ((in & ~prev) & IN_UP) sel = sel ? sel - 1 : MENU_N - 1;
        if ((in & ~prev) & IN_DOWN) sel = sel + 1 < MENU_N ? sel + 1 : 0;
        if (((in & ~prev) & IN_LEFT) && v[sel] > menu_lo[sel]) v[sel]--;
        if (((in & ~prev) & IN_RIGHT) && v[sel] < menu_hi[sel]) v[sel]++;
        g_z80x = g_cfg.xfer ? 0 : g_z80x_ok;
        if ((in & ~prev) & IN_A) return;
        prev = in;
    }
}

static void title_pic(void);

/* タイトルから入る画面(隠しコンフィグ・サウンドテスト): 下は黒帯にして f を呼び、終わったらタイトルの絵を描き直す */
static void sub_screen(void (*f)(void))
{
    screen3_init();
    cockpit_load();            /* 下の帯にタイトルの絵が残らないように */
    cockpit_mode(1);           /* 下は黒帯 */
    f();
    title_pic();
}

static void title_pic(void)
{
    static const u8 regs[] = { 1, 0x20, 0, 0x0E, 8, 0x0A, 9, 0x80, 2, 0x1F, 7, 0x00, 23, 0x00, 25, 0x18 };
    u8 i;
    u16 len;
    while (g_flip_req) wait_tick();
    pcm_stop();
    split_off();
    for (i = 0; i < sizeof(regs); i += 2) vdp_wreg(regs[i], regs[i + 1]);
    vdp_set_palette(0, title_pal);
    for (i = 0; i < 4; i++) {
        len = (i < 3) ? 0x4000 : (u16)(TITLE_PAGE - 0xC000);
        rom_load(TITLE_BANK + i * 2);
        vdp_set_write_hi(i, 0);
        vdp_out((const u8 *)0x8000, len);
        vdp_set_write_hi(4 + i, 0);
        vdp_out((const u8 *)0x8000, len);
    }
    vdp_set_write_hi((u8)((0x10000ul + TITLE_BAND_Y * 256u) >> 14), (u16)(TITLE_BAND_Y * 256u) & 0x3FFF);
    vdp_out((const u8 *)0x8000 + (TITLE_PAGE - 0xC000), TITLE_BAND_LEN);
    /* ページ2はいまのモジュールを読み直す */
    rom_load(MOD_BANK0 + 2 * g_mod);
    vdp_wreg(1, 0x60);
}

void title_run(void)
{
    static const u8 konami[10] = { IN_UP, IN_UP, IN_DOWN, IN_DOWN, IN_LEFT, IN_RIGHT, IN_LEFT, IN_RIGHT, IN_KEY_B, IN_KEY_A };
    u16 t = 0;
    u8 prev = 0xFF, in, key, kn = 0;
    g_scene = 0;
    g_auto = 0;
    mod_load_now(0);
    bgm_play(SONG_TITLE);
    title_pic();
    for (;;) {
        wait_tick();
        t++;
        if (!(t & 31)) vdp_wreg(2, (t & 32) ? 0x3F : 0x1F);
        in = input_raw();
        key = in & ~prev & (IN_UP | IN_DOWN | IN_LEFT | IN_RIGHT | IN_KEY_A | IN_KEY_B);
        if (key) {
            if (key == konami[kn]) kn++;
            else kn = (key == konami[0]);
            if (kn == sizeof(konami)) {
                kn = 0;
                sub_screen(config_show);
                prev = 0xFF;
                continue;
            }
        }
        /* M(B キーではない。B は隠しコマンドに使う)でサウンドテスト */
        if ((in & ~prev & IN_B) && !(in & IN_KEY_B)) {
            sub_screen(sound_test);
            bgm_play(SONG_TITLE);
            prev = 0xFF;
            continue;
        }
        if ((in & IN_A) && !(prev & IN_A)) break;
        prev = in;
        if (t >= 1800) { g_auto = 2; break; }     /* 30 秒放置でデモ */
    }
    bgm_stop();
    screen3_init();
    cockpit_load();
}

void gameover_run(void)
{
    u8 t;
    bgm_play(SONG_GAMEOVER);
    for (t = 0; t < N_SPR; t++) g_spr_attr[t * 4] = 209;   /* 照準と敵の名前の札・線 */
    for (t = 0; t < 120; t++) {
        buf_fill(C_BLACK);
        text_center(10, "ENGINE FIRE", C_RED, 1);
        text_center(18, "GAME OVER", C_WHITE, 1);
        num_draw(18, 26, g_score, 5, C_WHITE);
        text_draw(38, 26, "0", C_WHITE, 1);
        text_draw(10, 32, "HI", C_CYAN, 1);
        num_draw(18, 32, g_hiscore, 5, C_CYAN);
        text_draw(38, 32, "0", C_CYAN, 1);
        present();
    }
    g_hiscore = g_score > g_hiscore ? g_score : g_hiscore;
}

/* 文面はエンディングのモジュール(7)の字幕の 2 番から(tools/stage_data.py の ending()。ページ0に空きが無いので)。
 * 1 行 = [色 + 10h][左端の x(ドット)] 字…(並べ方はビルドのときに tools/gen_font.py で決める)。空の行は ""。
 * "\x01" [色][x] = 得点の行、"\x02" = 終わり */
#define roll (MOD->str + 2)
static u16 roll_n;
#define ROLL_N roll_n
static char roll_score[8];
#define ROLL_LH 13                 /* 1 行の高さ(ライン) */
#define ROLL_TOP 15                /* 始めは画面 1 枚ぶん(192 ライン)を空ける */
extern u8 bot_hi;
/* 面のコード(stg.c)の字幕を書く関数。面のコードの先頭の飛び先の表(stgjt.s)を通して呼ぶ */
#define lb_at (*(void (*)(u8, u8))0xD700)
typedef const char *(*LbLine)(const char *, u8, u8, u8, u8);
#define lb_line ((LbLine)0xD703)

/* 輪の行 k(1 ページ目の 256 ラインを輪にして、k × 13 ライン目から)に、文の k - 15 行目を映像の場面の字幕の字体で書く */
static void roll_row(u16 k)
{
    const char *t;
    i16 li = (i16)k - ROLL_TOP;
    u8 y = (u8)(k * ROLL_LH), r;
    for (r = 0; r < ROLL_LH; r++) { lb_at(0, (u8)(y + r)); vdp_fill(0x11, 128); }
    if (li < 0 || li >= (i16)ROLL_N) return;
    t = roll[li];
    if (*t == 1) lb_line(roll_score, (u8)t[2], y, t[1] & 15, 0);
    else if (*t) lb_line(t + 2, (u8)t[1], y, t[0] & 15, 0);
}

/* エンドロール(7.4): SCREEN 5 に切り替え、映像の場面の字幕の字体(VRAM 0EA00h。cockpit_load が置く)で
 * 下から上へ流す(R#23 で 1 ドットずつ)。スペースで速く流す */
void ending_run(void)
{
    static const u8 regs[] = { 1, 0xA0, 0, 0x06, 2, 0x1F, 7, 0x01, 8, 0x0A, 9, 0x00, 23, 0x00, 25, 0 };
    u16 s, y = 0, k;
    u8 i;
    for (roll_n = 0; roll[roll_n][0] != 2; roll_n++) ;
    g_score += (u16)life * 100;
    g_hiscore = g_score > g_hiscore ? g_score : g_hiscore;
    {   /* 得点(6 桁目は常に 0) */
        u16 v = g_score, d = 10000;
        for (i = 0; i < 5; i++) { char c = '0'; while (v >= d) { v -= d; c++; } roll_score[i] = c; d = i == 0 ? 1000 : i == 1 ? 100 : i == 2 ? 10 : 1; }
        roll_score[5] = '0'; roll_score[6] = 0;
    }
    while (g_flip_req) wait_tick();
    pcm_stop();
    split_off();
    for (i = 0; i < sizeof(regs); i += 2) vdp_wreg(regs[i], regs[i + 1]);
    vdp_set_write_hi(0, 0);
    vdp_fill(0x11, 0x8000);
    vdp_set_palette(0, pal_fixed);
    bot_hi = 0;
    xfer_invalidate();
    vdp_wreg(1, 0xE0);
    bgm_play(SONG_ENDING);
    k = ROLL_TOP;
    for (;;) {
        wait_tick();
        s = (input_raw() & IN_A) ? 1 : (g_tick & 3) == 0;
        if (k < ROLL_TOP + ROLL_N + 8) {
            for (; s; s--) vdp_wreg(23, (u8)++y);
            while (k * ROLL_LH < y + 192 + ROLL_LH) roll_row(k++);   /* 画面の下に入る前に描く */
        } else if (input_raw() & IN_A) break;
    }
    bgm_stop();
}
