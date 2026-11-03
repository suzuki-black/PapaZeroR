/* view.h — カメラ・メッシュの描画(指示書 8 章)
 *
 * 座標は 8.8 固定小数点(1.0 = 1 単位。ワールドの差は ±128 単位の中で正しく出る)。カメラ空間は x=右 y=上 z=奥。
 */
#ifndef VIEW_H
#define VIEW_H
#include "engine.h"

typedef struct { i16 x, y, z; } V3;

#define NEAR_Z   128
#define FAR_U    100           /* 描く距離(単位) */
typedef struct { i16 sx, sy, x, y, z; } XRec;   /* 投影後(12.4)とカメラ空間(8.8)の頂点(xf.s) */
#define XR ((XRec *)0xE200)
#define OFF_NEAR 0x7FFF        /* sy がこの値ならニアクリップ面より手前 */

/* メッシュのバイト列(tools/gen_models.py): nv nf sh r nrect, rects の番地(dw), nv0(細部を除く面が使う頂点の数), 頂点(i8 × 3 × nv), 面(6 バイト × nf) */
#define MESH_HDR 8
typedef struct { u8 hdr, color, v[4]; } Face;   /* hdr: bit0-2 = 頂点数、bit7 = 細部(LOD 1 で省く) */

extern i16 cam_x, cam_y, cam_z;
extern u8  cam_yaw, cam_pitch, cam_roll;
extern i16 cm[9];              /* カメラ行列(8.8)。行 0 = 右、1 = 上、2 = 奥 */
extern i8  cm8[9];             /* 同じ(±127) */
extern u8 g_lod_min, g_obj_yaw;   /* LOD の下限(遠い区画は細部を省く)、物体の向き(LOD 2 の方向) */

void cam_update(void);                   /* cam_yaw / pitch / roll から行列を作る */
void pt_cam(i16 wx, i16 wy, i16 wz, V3 *o);   /* ワールド → カメラ空間 */
u8   pt_screen(const V3 *c, i16 *sx, i16 *sy);   /* 12.4 の画面座標。手前なら 0 */
void sky_draw(u8 space);                 /* 空と地面(傾いた地平線) */
void mat_yaw(u8 yaw, u8 roll);           /* カメラ行列 × 物体の向き(ヨー → ロール)を g_mm へ */
void mat_y(u8 yaw, i8 *out);             /* xf.s: ロールなし */
extern i8 g_mm[9];
extern u8 g_perf_polys;
extern u16 g_perf_verts;
/* メッシュを描く。c = 中心(カメラ空間)、m = 0 ならカメラの向きのまま。戻り値 0 = 画面に出ていない */
u8   mesh_draw(const u8 *mesh, const V3 *c, const i8 *m, u8 flash, u8 hit_id);
void band_draw(i16 x0, i16 y0, i16 x1, i16 y1, u8 w0, u8 w1, u8 color);   /* 帯(レーザー): 2 点を太さ付きで結ぶ */

/* asm */
extern const u8 *g_xf_src;
extern u8  g_xf_n;
extern i16 g_xf_t[3];
void xf_set(const i8 *m);
void xf_shift(u8 sh);
void xf_trans(void);
void xf_verts(void);
void poly3p(const V3 *const *pv, u8 n, u8 color);
extern const void *g_dm_rects;
extern u8 g_dm_n, g_dm_flash, g_dm_id, g_dm_hit, g_dm_grow, g_dm_thin, g_dm_deco;
void draw_model(const V3 *c);

typedef struct { u8 x0, y0, x1, y1; i16 z; u8 id; } HitRect;
#define MAX_HIT 48
extern HitRect hits[MAX_HIT];
extern u8 n_hits;

#endif
