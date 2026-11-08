/* game.h — ゲーム全体の宣言(指示書 3〜7 章) */
#ifndef GAME_H
#define GAME_H
#include "view.h"

/* ---- ROM と RAM の割り当て(tools/mkrom.py と一致させる) ---- */
#define SEG_XFER   6            /* 6・7 は差分転送の写し(vdp.s) */
#define SEG_SND    8
#define SEG_VOICE  9
/* FS-A1ST の主記憶は 256KB = 16 セグメントで、しかも DRAM モードでは上の 64KB に BIOS が入る。空きは少ないので、
 * モジュールは今の面と次の面の 2 つだけ RAM に置き、セグメント 1 と 5 を交互に使う(継ぎ目で 1KB ずつ読む。指示書 7.2) */
#define SEG_MOD_A  1
#define SEG_MOD_B  5
#define MOD_COUNT  8
#define MOD_BANK0  5            /* モジュール n は ROM のバンク 5 + 2n〜 */
#define SND_BANK   21
#define VOICE_BANK 23
#define COCKPIT_BANK 25         /* コクピットの絵(2 バンク) */
#define TITLE_BANK 27           /* タイトルの絵(8 バンク) */

/* ---- モジュールの見出し(tools/gen_stage.py) ---- */
typedef struct { i16 x, y, z; u8 yaw; i8 pitch; } PathPt;           /* 2 単位ごと */
typedef struct { const u8 *mesh; i16 x, y, z; u8 spd; u8 yaw; } Sect;   /* 8 単位ごと。spd = 速度(単位/秒 × 4) */
typedef struct { u16 at; u8 cmd, a, b, c; i16 x, y, z; } Event;     /* at = 経路の位置(単位) */
typedef struct {
    const PathPt *path; u16 npath;
    const Sect *sect;   u16 nsect;
    const Event *ev;    u16 nev;
    const u8 *pal;                 /* 9〜15 の 7 色 */
    const u8 * const *meshes;      /* メッシュ番号 → メッシュ */
    const char * const *str;       /* 字幕 */
    const u8 *boss;                /* ボスの定義 */
    const char *name;
    u8 bgm, flags, clock, pad;     /* flags: bit0 = 宇宙、bit1 = 場面(操作なし、下は黒帯) */
    const u8 *pal2;                /* EV_FADE で移る色(エンディング) */
    void (*hook)(u16 t);           /* 場面の演出(モジュールの中のコード。t = 場面の始めからのティック。0 = なし) */
} Stage;
#define MOD ((const Stage *)0x8000)
#define SF_SPACE 1
#define SF_SCENE 2

/* 台本の命令(10.5) */
enum { EV_SPAWN, EV_BOSS, EV_ROLL, EV_PROMPT, EV_TEXT, EV_SUB, EV_VOICE, EV_BGM, EV_PAL, EV_LOOP, EV_END, EV_CAM, EV_ITEM, EV_PROP, EV_FADE };
enum { PR_NONE, PR_ROLL, PR_LOOP, PR_DIVE };

/* 物体 */
enum { T_NONE, T_E01, T_E02, T_E03, T_E04, T_E05, T_E06, T_E07, T_E08, T_SUPPLY, T_MEDIC,
       T_FLAK, T_MISSILE, T_MINE, T_MYMIS, T_PROP, T_PART, T_COUNT };
enum { P_NONE, P_PARALLEL, P_HOLD, P_PASS, P_TAIL, P_CROSS, P_DRIFT, P_BOUNCE, P_FALL, P_LIFT };
#define MAX_OBJ 30
typedef struct {
    u8 t, hp, ptn, st;
    u8 tm, flash, yaw, roll;
    u8 mesh, tgt, group, flags;
    i16 x, y, z;
    i16 vx, vy, vz;
    i8 ox, oy, oz, ax;
} Obj;
#define OF_CAPSULE 1
#define OF_WEAK    2
#define OF_HIDDEN  4
#define OF_DECOR   8     /* 飾り(撃てない。数えない) */
#define OF_SPIN    16    /* ボスの中心のまわりを回る */
extern Obj obj[MAX_OBJ];

/* 隠しコンフィグ(7.3) */
typedef struct { u8 damage, god, stage, life, oneshot, fps, xfer, split, roll; } Config;
extern Config g_cfg;
extern u8 g_auto;               /* 1 = 自動プレイ(デモと test_flow) */
extern u8 g_scene;              /* 0 = タイトル 1 = ゲーム 2 = 継ぎ目 3 = 場面 */

extern u8 life;
extern u16 mis_left;            /* 誘導弾の残り。面の始めに MIS_MAX */
#define MIS_MAX 500
extern u16 g_score;             /* 得点 / 10 */
extern u16 g_hiscore;
extern u8 g_clock;              /* 残り時間(0x60 = 06:00 の分) */
extern u16 g_frames;
extern u16 g_anim;              /* 演出の時計: 3 ティック(20fps の 1 枚)ごとに 1 進む。fps が変わっても点滅や揺れの速さは同じ */
extern u8 g_an;                 /* このフレームで g_anim が進んだ数(0〜) */
extern u8 g_shake;              /* 計器盤の揺れの残り(g_anim の数) */
extern u8 g_min_ticks;          /* present が 1 枚に待つ最小のティック数(3 = 20fps、2 = 30fps) */
extern u8 g_r18_bot;            /* sys.s: 下の画面の R#18 */
extern u8 g_r18_top;            /* sys.s: 上の画面の R#18(被弾の揺れ。横だけ: 縦にずらすと分割の行も動く) */

/* game.c */
u8 stage_run(u8 mod);           /* 1 = クリア、0 = ゲームオーバー */
void seam_run(u8 from, u8 to);
void game_reset(void);

/* main.c */
void present(void);
extern void (*g_poll)(void);  /* present が表示を待つ間に毎ティック呼ぶ */
void set_stage_palette(const u8 *pal);
void flash_palette(void);
void screen3_init(void);
void mod_load_now(u8 n);         /* モジュール n を読み込んで使う(16 ティックほど止まる) */
void mod_next_begin(u8 n);       /* 裏のセグメントへ読み始める */
u8   mod_next_step(void);        /* 1KB 読む。読み終わったら 1 */
void mod_next_use(void);         /* 読み終えたモジュールへ切り替える */
#define N_SPR 19          /* 照準 1 + 敵の名前の札 6 + 引き出し線 12(game.c の marks_draw) */
extern u8 g_spr_attr[N_SPR * 4 + 1];
extern u8 g_mod;
extern const u8 pal_fixed[];

/* cockpit.c */
void cockpit_load(void);
void cockpit_mode(u8 letterbox);
void cockpit_reset(void);
void hud_step(void);
void cockpit_vram(void);         /* present の中から: 字幕か計器を 1 項目だけ VRAM へ */
void sub_text(const char *s);    /* 黒帯に字幕 */
extern u8 g_spd_show;
extern u8 g_alt_show;
extern u8 g_heat;

/* scene.c */
void title_run(void);
void gameover_run(void);
void ending_run(void);
#endif
