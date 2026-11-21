/* stgb.c — 面のコードのうち、0xE700- に置く関数(stg.c の op_hook が呼ぶ)。Makefile が --codeseg STGB で作る */
#include "stg.h"

/* 進む向きの前 f・右 r・上 u(8.8)だけ p を動かす */
void mv(i16 *p, i16 f, i16 r, i16 u)
{
    p[0] += fmul(g_fx, f) + fmul(g_fz, r);
    p[1] += u;
    p[2] += fmul(g_fz, f) - fmul(g_fx, r);
}

/* カメラから前 f・右 r・上 u(単位)の点 */
void ahead(i8 f, i8 r, i8 u, i16 *p)
{
    p[0] = cam_x; p[1] = cam_y; p[2] = cam_z;
    mv(p, (i16)f << 8, (i16)r << 8, (i16)u << 8);
}

Obj *spawn(u8 t, u8 ptn, const i16 *p)
{
    Obj *o = obj_new(t);
    if (o) { o->x = p[0]; o->y = p[1]; o->z = p[2]; o->ptn = ptn; o->yaw = cam_yaw_path; }
    return o;
}

/* 新しい敵の動き(P_WEAVE・P_ORBIT・P_SWOOP)と戦艦の砲撃 */
void objs_move(u8 dt)
{
    u8 i;
    Obj *o;
    /* obj_step は知らない番号なので、通り過ぎたら消すことと st を進めることだけをする */
    for (i = 0, o = obj; i < MAX_OBJ; i++, o++) {
        i16 f, *p = &o->x;
        u8 a;
        if (!o->t || o->t > T_ELAST) continue;
        f = fmul(g_fx, o->x - cam_x) + fmul(g_fz, o->z - cam_z);
        a = o->tm;
        switch (o->ptn) {
        case P_WEAVE:       /* 蛇行しながら近づき、途中で撃つ */
            o->tm = a + dt * 3;
            o->roll = (u8)(SIN(a) >> 3);
            mv(p, -0x20 * dt, (SIN(a) >> 3) * dt, (COS(a) >> 5) * dt);
            if (o->st >= 140 && f > 0x1000 && f < 0x4000) { o->st = 0; shot(T_FLAK, o->x, o->y, o->z, 60); }
            break;
        case P_ORBIT:       /* 40 単位先で輪を描いて回り、3 回撃ったら向かってくる */
            {
                i16 q[3];
                o->tm = a + dt * 2;
                ahead(40, (i8)(SIN(a) >> 5), (i8)(COS(a) >> 6), q);
                o->x += (q[0] - o->x) >> 3; o->y += (q[1] - o->y) >> 3; o->z += (q[2] - o->z) >> 3;
                o->yaw = (u8)(cam_yaw_path + 64 + (a & 128));
                o->roll = a;
                if (o->st >= 160) { o->st = 0; shot(T_FLAK, o->x, o->y, o->z, 70); o->ax++; if (o->ax >= 3) o->ptn = P_PASS; }
            }
            break;
        case P_SWOOP:       /* 後ろから頭上を追い越し、前で向きを変えて向かってくる */
            o->x += cam_vx * dt; o->z += cam_vz * dt;
            mv(p, 0x20 * dt, 0, o->y > cam_y + 0x0200 ? -0x18 * dt : 0);
            o->yaw = (u8)(cam_yaw_path + 128);
            if (f > 0x2800) { o->ptn = P_PASS; o->st = 0; o->yaw = cam_yaw_path; }
            break;
        }
        /* 戦艦: 前にいる間、約 2.5 秒ごとに砲塔から 2 発 */
        if (o->t == T_E09 && o->st >= 150 && f > 0x0C00 && f < 0x5000) {
            o->st = 0;
            shot(T_FLAK, o->x, o->y + 0x0300, o->z, 64);
            shot(T_FLAK, o->x - (g_fx >> 2), o->y + 0x0200, o->z - (g_fz >> 2), 76);
        }
    }
}

/* 映像の場面の字幕(下の黒帯)。op.c(映像の場面のモジュールの後ろに重ねるコード)から呼ぶ。8 つの場面のどれにも置くと、
 * オープニングのモジュールに入らなかったので、ここ(どの場面でもページ3に写してある)に 1 つだけ置く。
 * 誰の台詞かが分かるように、映画の字幕の作法にならう:
 *   話し手ごとに決まった色(BBC の字幕の指針: 白・黄・シアン・緑の順。黄は無いので橙)と、行頭に名前の札(色だけに頼らない。Xbox の指針)、
 *   無線の声とナレーションは斜体(Netflix の指針)。字体と並べ方は tools/gen_font.py(札の文字はそこの TAGS と同じにする)。
 * w は tools/stage_data.py の WHO_ と同じ並び */
typedef struct { const char *tag; u8 col, ital; } Who;
static const Who who[] = {
    { 0, C_CYAN, 1 },                  /* 0 ナレーション(第三者。札なし) */
    { "PAPA: ", C_WHITE, 0 },          /* 1 父 */
    { "HINA (radio): ", C_ORANGE, 1 }, /* 2 ヒナ(無線) */
    { "HINA: ", C_ORANGE, 0 },         /* 3 ヒナ(その場で) */
    { "ALERT: ", C_GREEN, 0 },         /* 4 機の警報 */
    { "KIDNAPPER: ", C_RED, 0 },       /* 5 敵 */
};

void lb_at(u8 x, u8 y);                                                     /* stg.c */
const char *lb_line(const char *s, u8 x0, u8 y, u8 c, u8 ital);            /* stg.c */

/* s は tools/gen_font.py の layout() が作る: [札の x][1 行目の y] { [行の x] 字… } を 1Fh でつなぐ */
void film_say(const char *s, u8 w)
{
    const Who *p = &who[w];
    u8 y;
    for (y = 160 + 4; y < 160 + 48; y++) { lb_at(0, y); vdp_fill(0x11, 128); }
    if (!*s) return;
    y = (u8)(s[1] + 160);
    if (p->tag) lb_line(p->tag, s[0], y, p->col, 0);
    for (s += 2;; y += 14) {
        s = lb_line(s + 1, (u8)*s, y, p->col, p->ital);
        if (!*s++) break;
    }
}
