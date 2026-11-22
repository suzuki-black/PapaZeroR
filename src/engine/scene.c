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

/* エンドロール(7.4)は、エンディングのモジュール(7)の演出のコード(op.c の ending_roll)に置く(ページ0に空きが無いので) */
