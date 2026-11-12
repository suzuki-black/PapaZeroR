/* stg.c — 面のコード。本体からは Stage.hook で毎フレーム呼ぶ(obj_step と boss_step の後、描く前)。
 * ページ0・常駐部・モジュールの後ろ(game_ai.c)に空きが無いので、ページ3の空き(0xD700- と 0xE700-)に置く。
 * ROM ではコクピットの絵のバンクの後ろにあり、cockpit_load が起動時に写す(tools/mkrom.py)。どの面も同じコードで、
 * 面ごとの違い(ボスの秘密兵器)はモジュールの見出しの weapon で決める。
 *
 * - 残り時間(g_clock)を遊んだ時間で減らす(前は面ごとに決まった値を出すだけで、意味が無かった)
 * - 新しい敵の動き(P_WEAVE・P_ORBIT・P_SWOOP)と、戦艦の砲撃
 * - ボスの秘密兵器(面ごとに 1 つ。モジュールの見出しの weapon)
 *
 * 変数を持たない(値は本体の g_stg[] に置く)。
 */
#include "stg.h"

/* 爆発を派手にする: 新しく起きた爆発で画面を揺らし、ボスの部位なら橙に光らせる。ボスを倒したら約 1.5 秒、白い閃光・大きな揺れ・
 * ボスのまわりの連続爆発を繰り返す。色を替えるのと揺らすのは塗る量が増えないので、重さはほとんど変わらない
 * (普通の敵は光らせない。倒すたびに画面が点滅すると目に負担なので、揺れだけにする) */
static const u8 pal_white[14] = { 0x77, 7, 0x77, 7, 0x77, 7, 0x77, 7, 0x77, 7, 0x77, 7, 0x77, 7 };
static const u8 pal_orange[14] = { 0x72, 5, 0x71, 4, 0x72, 5, 0x71, 3, 0x72, 5, 0x71, 4, 0x72, 5 };

static void fx_flash(u8 dt)
{
    u8 i, fl = 0;
    for (i = 0; i < MAX_FX; i++) if (fx[i].t == FX_T) {           /* このフレームに起きた爆発 */
        if (g_shake < 5) g_shake = 5;
        if (boss_on) fl = 1;
    }
    if (boss_on) g_stg[ST_BD] = 0;
    else if (boss_dead && !g_stg[ST_BD]) { g_stg[ST_BD] = 1; g_stg[ST_BX] = 24; }
    if (g_stg[ST_BX]) {
        u8 k = g_stg[ST_BX];
        g_stg[ST_BX] = k > (u8)((dt + 3) >> 2) ? k - ((dt + 3) >> 2) : 0;
        if ((k & 3) == 0 && (u8)(k - g_stg[ST_BX])) {             /* 約 0.27 秒ごと */
            fx_add(boss_x + ((i16)(rnd() & 15) - 8) * 256, boss_y + ((i16)(rnd() & 7) - 4) * 256, boss_z, 1);
            g_shake = 14;
            fl = 2;
        }
    }
    if (fl) { vdp_set_palette(9, fl == 2 ? pal_white : pal_orange); g_stg[ST_FL] = fl == 2 ? 3 : 2; }
    else if (g_stg[ST_FL] && !--g_stg[ST_FL]) set_stage_palette(MOD->pal);
}

const char * const w_name[] = { 0, "BALLOON BOMBS!", "CRAB MISSILES!", "DRONE SWARM!", "FLAK CURTAIN!", "MEGA MISSILE!", "SPACE MINES!" };

/* 秘密兵器の 1 段(ph = 0〜12) */
void weapon(u8 w, u8 ph)
{
    i16 p[3];
    i8 side = (ph & 1) ? 6 : -6;
    p[0] = boss_x; p[1] = boss_y; p[2] = boss_z;
    switch (w) {
    case W_BOMBS:       /* 気球から爆弾: 前の上から降ってくる */
        ahead(26, (i8)(rnd() & 15) - 8, 18, p);
        break;
    case W_SALVO:       /* 左右から誘導弾 */
        if (ph > 7) return;
        mv(p, 0, (i16)side << 8, 0);
        shot(T_MISSILE, p[0], p[1], p[2], 80 + ph * 3);
        return;
    case W_DRONES:      /* ボスの前から P-51 が蛇行して向かってくる */
        if ((ph & 1) || ph > 5) return;
        ahead(48, side, 2, p);
        spawn(T_E04, P_WEAVE, p);
        return;
    case W_CURTAIN:     /* 横一列の弾幕 */
        if (ph > 9) return;
        mv(p, 0, (i16)(ph - 5) * 0x0300, -0x0200);
        break;
    case W_MEGA:        /* 大きな誘導弾 1 発(遅い。撃ち落とせる) */
        if (ph) return;
        {
            Obj *o = obj_new(T_MISSILE);
            if (o) { o->x = p[0]; o->y = p[1]; o->z = p[2]; o->tm = 200; o->mesh = M_ROCKETL; o->hp = 6; }
        }
        return;
    default:            /* 機雷をばらまく */
        if ((ph & 1) || ph > 7) return;
        ahead(36 + ph * 3, (i8)(rnd() & 15) - 8, (i8)(rnd() & 7) - 4, p);
        spawn(T_E07, P_DRIFT, p);
        return;
    }
    shot(T_FLAK, p[0], p[1], p[2], 72);
}


void op_hook(u16 t)
{
    u8 dt, w;
    u16 *acc = (u16 *)&g_stg[ST_ACC], *last = (u16 *)&g_stg[ST_LAST], *wt = (u16 *)&g_stg[ST_WT];
    if (t < *last) *last = 0;                 /* 面の始め */
    dt = (u8)(t - *last);
    *last = t;
    if (!dt || dt > 8) return;
    /* 遊び方(1 面の始めに、上の字幕で順に出す) */
    if (g_mod == 1 && t < 1100) {
        static const char * const tip[] = { "ARROWS: AIM", "SPACE: GUN", "WATCH GUN HEAT", "BOX LOCKS FOES", "M: MISSILE", "ON ROLL! PRESS M" };
        u8 k = (u8)(t / 160);
        if (!k) g_stg[ST_TIP] = 0;
        else if (k <= 6 && g_stg[ST_TIP] != k) { g_stg[ST_TIP] = k; caption(tip[k - 1], C_CYAN, 150); }
    }
    /* 残り時間: 遊んだ時間で減らす(g_clock は時と 10 分の位の BCD。0 で止まる) */
    *acc += dt;                               /* 足すのと比べるのは分けて書く(SDCC は 1 つの式だと書き戻しを落とすことがある) */
    if (*acc >= CLOCK_STEP) {
        *acc = 0;
        if (g_clock & 15) g_clock--;
        else if (g_clock) g_clock -= 16 - 5;
        if (g_clock == 0x10) { pcm_say(VOICE_HURRY); caption("1 HOUR LEFT!", C_RED, 120); }
    }
    objs_move(dt);
    fx_flash(dt);
    /* ボスの秘密兵器: 登場の後、約 7 秒ごと。名前を出して警告し、8 ティックごとに 1 段ずつ、13 段撃つ */
    w = STG_WEAPON == 7 ? (u8)(1 + g_stg[ST_WN] % 6) : STG_WEAPON;
    if (!boss_on || boss_intro) { *wt = t + 240; g_stg[ST_WP] = 0; return; }
    if (!g_stg[ST_WP]) {
        if ((i16)(t - *wt) < 0) return;
        *wt = t;                              /* 撃ち始めの時刻 */
        g_stg[ST_WP] = 1;
        caption(w_name[w], C_RED, 90);
        se_play(SE_ALARM);
    }
    dt = (u8)((t - *wt) >> 3);
    while (g_stg[ST_WP] <= 13 && g_stg[ST_WP] <= dt + 1) { weapon(w, (u8)(g_stg[ST_WP] - 1)); g_stg[ST_WP]++; }
    if (dt > 13) { g_stg[ST_WP] = 0; g_stg[ST_WN]++; *wt = t + 420; }
}
