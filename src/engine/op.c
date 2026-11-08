/* op.c — 映像の場面(オープニング・1 面の後の継ぎ目)の演出。モジュールの後ろ(Makefile の OPn_BASE〜0xA3FF)に置くコードで、本体からは Stage.hook で呼ぶ。
 *
 * 経路と台本(経路の位置で進む)では人物も機体も動かせないので、オープニングだけは時刻で動く映画にする。
 * カメラと役者(人物・機体・小道具)のキーフレームを、場面の始めからのティック t で補間する。
 * 曲も同じ 60Hz のティックで進むので、絵と曲はずれない。台本(film.h)は tools/stage_data.py の opening() が作る。
 *
 * 変数を持たない(モジュールは ROM のまま見えている)。出来事の番号には本体の ev_i を借りる(オープニングは台本の命令が 0 個)。
 */
#include "game_int.h"
#include "view.h"

typedef struct { u16 t; i16 x, y, z; u8 a, b, c, fl; } Key;   /* カメラ: a = ヨー、b = ピッチ、c = ロール。役者: a = ヨー、b = ロール、c = メッシュ */
typedef struct { u16 t; u8 kind, arg; const char *s; } FilmEv;
enum { FE_SUB = 1, FE_CAP, FE_VOICE, FE_SE, FE_COCKPIT, FE_END, FE_SHAKE };
#define FL_EASE  1      /* 次のキーまでをゆっくり始めてゆっくり止める */
#define FL_BOB   2      /* 走る・跳ねる(上下に揺らす) */
#define FL_C     4      /* c も補間する(カメラのロール) */
#define FL_SHAKE 8      /* 小刻みに揺らす(エンジン・滑走) */
#define FL_STEP  16     /* 次のキーまで動かさず、次のキーの時刻で切り替える */
/* カメラのキーの fl の上 3 ビット: 描く地形の区画(× 4) */

#define SPR_PEOPLE 17    /* 人物のスプライトの絵(tools/gen_data.py の PEOPLE)。絵ごとに 大・中・小 × 2 枚 */

typedef struct { u8 mesh, art, near, far, col, col2; } Look;
/* スプライトで描くもの: メッシュの番号 → 絵(tools/gen_data.py の PEOPLE の番号)、大と中・中と小の境目(単位)、2 枚の色 */
static const Look look[] = {
    { M_TERROR, 0, 5, 10, C_BLACK, C_IRON },    /* 0 立つ、1・2 走る */
    { M_HINA, 3, 5, 10, C_RED, C_WHITE },       /* 3・4 手を振る、5 担がれる */
    { M_RAIDER, 6, 48, 80, C_BLACK, C_WHITE },  /* 後ろから見た戦闘機と、ヒナを入れるカプセル(中の大きさだと塊になり、戦車に見えた) */
    { M_TANK, 7, 24, 255, C_IRON, C_BLACK },
    { 0 },
};

#include FILM_H                  /* 台本(film0.h = オープニング、film15.h = 1 面の後の継ぎ目。Makefile が選ぶ) */

/* キーの並び k(n 個)の、時刻 t の値を o に入れる。同じ時刻のキーが 2 つあれば後ろのほう(切り替え)。
 * 座標(i16 × 3)と角度(u8 × 3)を並びのまま回す(キーは 12 バイトなので、次のキーの同じ値は i16 で 6 個、u8 で 12 個先) */
static void key_at(const Key *k, u8 n, u16 t, Key *o)
{
    i16 f;
    u8 i = 0;
    while (i + 1 < n && k[i + 1].t <= t) i++;
    k += i;
    *o = *k;
    if (i + 1 >= n || t <= k->t || (k->fl & FL_STEP)) return;
    f = muldiv((i16)(t - k->t), 256, (i16)(k[1].t - k->t));
    if (k->fl & FL_EASE) f = fmul(fmul(f, f), 768 - 2 * f);
    {
        const i16 *a = &k->x;
        i16 *d = &o->x;
        for (i = 0; i < 3; i++) d[i] += fmul(a[i + 6] - a[i], f);
    }
    {
        const u8 *a = &k->a;
        u8 *d = &o->a;
        for (i = (k->fl & FL_C) ? 3 : 2; i--; ) d[i] += (u8)fmul((i8)(a[i + 12] - a[i]), f);
    }
}

static i16 bob(u16 t)
{
    i16 s = SIN((u8)(t * 9));
    return s < 0 ? -s : s;
}

void op_hook(u16 t)
{
    Key c;
    u8 i, n;
    Obj *o = obj;
    while (ev_i < N_FEV && film_ev[ev_i].t <= t) {
        const FilmEv *e = &film_ev[ev_i++];
        switch (e->kind) {
        case FE_SUB: sub_text(e->s); break;
        case FE_CAP: caption(e->s, e->arg, 150); break;
        case FE_VOICE: pcm_say(e->arg); break;
        case FE_SE: se_play(e->arg); break;
        case FE_COCKPIT: cockpit_mode(e->arg); break;
        case FE_END: scr_end = 1; break;
        case FE_SHAKE: g_shake = e->arg; break;
        }
    }
    key_at(cam_k, N_CAMK, t, &c);
    if (c.fl & FL_BOB) { i16 b = bob(t); c.y += b >> 3; c.b += (u8)(b >> 6); }
    if (c.fl & FL_SHAKE) c.c += (t & 2) ? 1 : (u8)-1;
    cam_x = c.x; cam_y = c.y; cam_z = c.z;
    cam_yaw = c.a; cam_pitch = c.b; cam_roll = c.c;
    cam_update();
    sect_i = (c.fl >> 5) << 2;                 /* 描く地形の区画(4 区画単位。町の場面は経路の先の町の区画) */
    n = 1;
    for (i = 0; i < N_ACT; i++, o++) {
        key_at(act_k + act_i[i], (u8)(act_i[i + 1] - act_i[i]), t, &c);
        o->t = T_PROP; o->ptn = P_NONE; o->mesh = c.c;
        o->x = c.x; o->y = c.y; o->z = c.z;
        o->yaw = c.a; o->roll = c.b;
        if (c.fl & FL_BOB) o->y += bob(t) >> 2;        /* 担ぐ人と担がれる人がそろって揺れるよう、位相は全員同じ */
        if (c.fl & FL_SHAKE) o->y += (t & 2) ? 4 : -4;
        /* 人物・誘拐の戦闘機・戦車はスプライト(モデルはモジュールに入れていないので描かれない)。
         * 足もとを下の真ん中に合わせ、近さ(単位)で大・中・小の絵を選ぶ。1 つにつき 2 枚を重ねて 2 色にする */
        {
            const Look *k = look;
            V3 v;
            i16 sx, sy;
            u8 art, zu, *a;
            while (k->mesh && k->mesh != c.c) k++;
            if (!k->mesh || n > 8) continue;
            pt_cam(o->x, o->y, o->z, &v);
            if (!pt_screen(&v, &sx, &sy)) continue;
            sx = (sx >> 2) - 16; sy = (sy >> 2) - 32;
            if (sx < 0 || sx > 255 || sy < -31 || sy > 150) continue;
            art = k->art;
            if (c.c == M_TERROR) art += (c.fl & FL_BOB) ? 1 + ((t >> 3) & 1) : 0;
            else if (c.c == M_HINA) art += c.b ? 2 : (t >> 4) & 1;
            zu = (u8)(v.z >> 8);
            zu = zu < k->near ? 0 : (zu < k->far || c.c == M_TANK) ? 1 : 2;   /* 戦車は大・中だけ */
            art = (u8)((SPR_PEOPLE + (art * 3 + zu) * 2) << 2);
            /* 1 枚目(形)は 1〜8 番、2 枚目(色)は 9〜16 番。横に 5 枚以上並ぶと番号の大きいほうが消えるので、
             * 消えるのは色だけで、形は残る */
            a = &g_spr_attr[n++ * 4];
            a[0] = a[32] = (u8)(sy - 1); a[1] = a[33] = (u8)sx;
            a[2] = art; a[34] = art + 4;
            a[3] = k->col; a[35] = k->col2;
        }
    }
    /* 使わなかった番号を隠す。先に全部を隠してから置くと、その間に割り込みが VRAM へ送ったフレームは何も映らなかった */
    for (i = 0; i < N_SPR; i++) if (i == 0 || (i >= n && i < 9) || i >= n + 8) g_spr_attr[i * 4] = 209;
}
