/* main.c — 起動と 1 フレームの表示(指示書 8.2 / 8.4)
 *
 * 描画バッファ(RAM)に描く → 前回の切替が済むのを待つ → 裏のパターンジェネレータへ転送 → 切替を予約(垂直帰線で ISR が R#4 を書く)。
 * 20fps(3 ティック)を上限にする。
 */
#include "game.h"
#include "sound.h"
#include "pcm.h"

u8 g_spr_attr[N_SPR * 4 + 1];
u8 g_mod;
u8 g_scene;
u16 g_perf_frame;               /* 直前のフレームの時間(テストが読む。タイマ値 ≒ 3.9µs) */
u16 g_perf_xfer;
u8  g_perf_ticks;
u8  g_min_ticks = 3;

static u8 back_page = 1;
static u16 last_flip;
static const u8 *stage_pal;
static u8 pal_state;

/* 固定色 0〜8(指示書 2.2)。(0RRR0BBB, 00000GGG) */
const u8 pal_fixed[] = {
    0x00, 0,  0x00, 0,  0x77, 7,  0x71, 1,  0x71, 4,  0x12, 6,  0x37, 6,  0x57, 2,  0x33, 3,
};
static const u8 pal_red[14] = { 0x71, 1, 0x60, 0, 0x71, 1, 0x60, 0, 0x71, 1, 0x60, 0, 0x71, 1 };

void set_stage_palette(const u8 *pal)
{
    stage_pal = pal;
    vdp_set_palette(9, pal);
}

void flash_palette(void) { pal_state = 1; }

void (*g_poll)(void);       /* 表示を待つ間に毎ティック呼ぶ(game.c の照準)。0 = 呼ばない */

void present(void)
{
    u16 now;
    g_spr_live = 1;            /* 待つ間は VDP に触らない(照準は割り込みが書く) */
    while (g_flip_req) { wait_tick(); if (g_poll) g_poll(); }
    while ((u16)(g_tick - last_flip) < g_min_ticks) { wait_tick(); if (g_poll) g_poll(); }   /* 3 = 20fps(場面の多くはフレームで数えるのでこちら)、ゲームの本体だけ 2 = 30fps */
    g_spr_live = 0;            /* ここから VDP に触る(割り込みに照準を書かせない) */
    now = g_tick;
    g_perf_ticks = (u8)(now - last_flip);
    last_flip = now;
    if (pal_state == 1) { vdp_set_palette(9, pal_red); pal_state = 2; }
    else if (pal_state == 2) { vdp_set_palette(9, stage_pal); pal_state = 0; }
    /* 計器と字幕の VRAM への書き込みは、切替の予約が無い今だけ(割り込みの中のスプライトの転送が VRAM の番地を変えるため) */
    cockpit_vram();
    timer_reset();
    vdp_xfer(back_page);
    g_perf_xfer = timer_read();
    g_flip_page = back_page;
    g_flip_req = 1;
    back_page ^= 1;
}

static u8 mod_seg = SEG_MOD_A;      /* いま使っているセグメント */
static u8 next_mod, next_kb;

void mod_next_begin(u8 n)
{
    next_mod = n;
    next_kb = 0;
}

u8 mod_next_step(void)
{
    u8 cur = mod_seg;
    if (next_kb >= 16) return 1;
    sys_seg2(cur ^ (SEG_MOD_A ^ SEG_MOD_B));
    rom_chunk((u8)(MOD_BANK0 + 2 * next_mod), (u16)next_kb << 10);
    sys_seg2(cur);
    next_kb++;
    return 0;
}

void mod_next_use(void)
{
    mod_seg ^= SEG_MOD_A ^ SEG_MOD_B;
    g_mod = next_mod;
    sys_seg2(mod_seg);
}

void mod_load_now(u8 n)
{
    if (n == g_mod) return;
    mod_next_begin(n);
    while (!mod_next_step()) wait_tick();
    mod_next_use();
}

/* 分割画面の VDP を作り直す。上 = SCREEN 3、下 = SCREEN 5 の 2 ページ目 */
void screen3_init(void)
{
    static const u8 regs[] = {
        1, 0xA3,        /* 表示オフ、M2(マルチカラー)、16×16、拡大 */
        0, 0x00,
        2, 0x04, 3, 0x00, 4, 0x00, 5, 0x28, 6, 0x03,
        7, 0x01,        /* 周辺色 = 黒 */
        8, 0x08,
        9, 0x80,        /* 212 ライン */
        10, 0x00, 11, 0x00, 14, 0x00, 23, 0x00,
        25, 0x00, 26, 0x00, 27, 0x00,
        19, 159,
    };
    u8 i, r, c;
    pcm_stop();
    split_off();
    for (i = 0; i < sizeof(regs); i += 2) vdp_wreg(regs[i], regs[i + 1]);
    vdp_set_write(0x0000);
    vdp_fill(0, 0x4000);
    xfer_invalidate();
    /* 名前表。上 160 ライン(20 行)だけ使い、下の行は空の帯を指す。割り込みが遅れても黒く見える */
    vdp_set_write(0x1000);
    for (r = 0; r < 24; r++) {
        u8 row[32];
        for (c = 0; c < 32; c++) row[c] = (u8)((r >> 2) * 32 + c);
        vdp_out(row, 32);
    }
    for (i = 0; i < N_SPR * 4; i += 4) g_spr_attr[i] = 209;
    g_spr_attr[N_SPR * 4] = 208;
    vdp_set_write(0x1400);
    vdp_out(g_spr_attr, sizeof(g_spr_attr));
    vdp_set_palette(0, pal_fixed);
    vdp_wreg(1, 0xEB);
    g_split = g_cfg.split ^ 1;
}

void main(void)
{
    u8 n;
    g_buf_hi = BUF_A_HI;
    g_r1_mask = 0xFF;
    sys_install_loader();
    sys_install_isr();
    sys_page0_ram();
    sys_page0_data();
    sys_z80x_init();
    sys_seg2(SEG_SND);
    mod_load(SND_BANK);
    g_snd_ok = 1;
    sys_seg2(SEG_VOICE);
    rom_load(VOICE_BANK);
    sys_seg2(SEG_MOD_A);
    rom_load(MOD_BANK0);
    sound_init();
    g_cfg.damage = 1;
    g_cfg.stage = 1;
    g_cfg.life = 8;
#ifdef DEBUG_FPS
    g_cfg.fps = 1;
#endif
    screen3_init();
    cockpit_load();
    for (;;) {
        title_run();
        game_reset();
        if (g_auto) { stage_run(1); continue; }      /* デモ: 1 面の自動プレイ */
        for (n = g_cfg.stage; n <= 6; n++) {
            if (n == 1 && !stage_run(0)) break;     /* オープニング(飛ばしてもよい) */
            if (!stage_run(n)) { gameover_run(); n = 0xFF; break; }
            if (n < 6) seam_run(n, (u8)(n + 1));
        }
        if (n == 7) { stage_run(7); ending_run(); }
    }
}
