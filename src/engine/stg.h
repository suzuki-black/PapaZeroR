/* stg.h — 面のコード(stg.c と stgb.c)で分け合う宣言 */
#ifndef STG_H
#define STG_H
#include "game_int.h"


extern u8 g_stg[16];
extern u8 g_clock;
#define ST_ACC   0       /* 0〜1: 残り時間の 10 分を数えるティック(ゲームを通して) */
#define ST_LAST  2       /* 2〜3: 前のフレームの t */
#define ST_WT    4       /* 4〜5: 秘密兵器を次に撃つ時刻(撃っている間は撃ち始めの時刻) */
#define ST_WP    6       /* 秘密兵器: 次に撃つ段 + 1。0 = 撃っていない */
#define ST_WN    7       /* 何回目(7 面は順に替える) */
#define ST_TIP   8       /* 遊び方の字幕を出した番号 */
#define ST_FL    9       /* 画面の光の残り(フレーム)。0 で面の色に戻す */
#define ST_BX    10      /* ボスを倒した後の連続爆発の残り(ティック / 4) */
#define ST_BD    11      /* 1 = このボスの連続爆発を始めた */

#define STG_WEAPON (MOD->weapon)

enum { W_NONE, W_BOMBS, W_SALVO, W_DRONES, W_CURTAIN, W_MEGA, W_MINES };
extern const char * const w_name[];

#define CLOCK_STEP 2400  /* 残り時間の 10 分 = 遊んだ 40 秒 */


void mv(i16 *p, i16 f, i16 r, i16 u);
void ahead(i8 f, i8 r, i8 u, i16 *p);
Obj *spawn(u8 t, u8 ptn, const i16 *p);
void weapon(u8 w, u8 ph);
void objs_move(u8 dt);
#endif
