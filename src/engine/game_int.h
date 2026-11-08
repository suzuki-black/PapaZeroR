/* game_int.h — game.c と game_ai.c で分け合う状態 */
#ifndef GAME_INT_H
#define GAME_INT_H
#include "game.h"
#include "hud.h"
#include "sound.h"
#include "pcm.h"
#include "ids.h"

#define MAX_LASER 3
typedef struct { u8 owner, kind, st, t, mhp; } Laser;
typedef struct { u8 color, charge, fire, w0, w1, dmg, mhp; } LaserDef;
typedef struct { u8 mesh, hp, score; } ObjDef;
extern Laser laser[MAX_LASER];
extern const LaserDef ldef[5];
void lasers_draw(void);
void mis_straight(Obj *o, u8 dt);
extern const ObjDef odef[T_COUNT];

extern i16 g_fx, g_fz;          /* 経路の進む向き(水平、8.8)。機動で視線が回っても変わらない */
extern u8  boss_yaw;
extern i16 boss_y0;
extern i8  cam_pitch_path;
extern u8  cam_yaw_path;
extern i16 cam_vx, cam_vy, cam_vz;
extern u8  boss_on, boss_dead, boss_t, boss_mov, boss_dist, boss_grp, boss_intro;
extern i16 boss_x, boss_y, boss_z;
extern u8  pr_kind, pr_t, man_kind, man_t, man_len, inv_t;

u8 rnd(void);
void fx_add(i16 x, i16 y, i16 z, u8 big);
/* 爆発(fx_add で置き、fx_draw が描く。fx_draw は fx.c) */
#define MAX_FX 8
#define FX_T 28                          /* 爆発が続くティック(約 0.47 秒) */
typedef struct { i16 x, y, z; u8 t, big; } Fx;
extern Fx fx[MAX_FX];
void fx_draw(u8 dt);
void lerp_pal(const u8 *a, const u8 *b, u8 k, u8 *o);   /* fx.c。k = 0..16 */
u8 auto_input(u8 in_prev);
u8 aim_target(void);                                       /* game_ai.c */                                /* game_ai.c。自動プレイの入力を返す */
extern u16 aim_x, aim_y;
extern i16 shot_tx, shot_ty, shot_tz;
#define SHOT_AHEAD 0x0400                                  /* 敵弾の狙う先: 自機の前 4 単位 */
extern u8 lock_n;
extern u8 sect_i, scr_end;                                /* op.c(オープニングの演出)が書く */
extern u16 ev_i;
void caption(const char *s, u8 color, u8 t);
void damage(u8 n);
Obj *obj_new(u8 t);
void obj_kill(Obj *o, u8 scored);
void obj_damage(Obj *o, u8 n);
void shot(u8 t, i16 x, i16 y, i16 z, u8 tm);
void laser_start(u8 owner, u8 kind);
void boss_begin(void);
void boss_step(u8 dt);
void obj_step(u8 dt);
#endif
