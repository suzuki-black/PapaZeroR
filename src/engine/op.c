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
enum { FE_SUB = 1, FE_CAP, FE_VOICE, FE_SE, FE_COCKPIT, FE_END, FE_SHAKE, FE_FADE, FE_SPR };
extern u8 g_fade, g_clock;
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

/* 見せたいもの(主役)のスプライト(tools/film_spr.py が台本といっしょに作る)。主役のモデルはモジュールに入れず、時刻で表を引いて絵を置く。
 * SprSub: 役者の番号、2 枚の色、表の始まりと数。SprEnt: その時刻からの絵(パターン 17〜62 の番号)と種類(0 = 出さない、1 = 1 枚、2 = 2×2) */
typedef struct { u8 a, c1, c2, first, n; } SprSub;
typedef struct { u16 t; u8 slot, kind; } SprEnt;
#define SPR_SLOT0 17

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

void film_say(const char *s, u8 w);    /* 字幕(下の黒帯)。話し手 w ごとに色・名前の札・斜体。面のコード(stg.c)に置く */

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
        case FE_SUB: {                         /* arg の下 2 ビット: 0 = いつも、1 = 間に合った(残り 1 時間以上)、2 = 遅れた。上は話し手 */
            u8 m = e->arg & 3;
            if (!m || (m == 1) == (g_clock >= 0x10)) film_say(e->s, e->arg >> 2);
            break;
        }
        case FE_FADE: g_fade = 1; break;
        case FE_VOICE: pcm_say(e->arg); break;
        case FE_SE: se_play(e->arg); break;
        case FE_COCKPIT: cockpit_mode(e->arg); break;
        case FE_END: scr_end = 1; break;
        case FE_SHAKE: g_shake = e->arg; break;
#ifdef N_SUBJ
        case FE_SPR: {                     /* 場面の絵をパターン 17〜へ送る。一度に約 1KB 以上を送ると分割画面がずれたので、帰線ごとに 12 枚ずつ */
            u8 k;
            for (k = 0; k < N_SPRPAT; k += 12) {
                wait_tick();
                vdp_set_write(0x1800 + (u16)(SPR_SLOT0 + k) * 32);
                vdp_out(spr_pat + (u16)k * 32, (u16)(N_SPRPAT - k > 12 ? 12 : N_SPRPAT - k) * 32);
            }
            break;
        }
#endif
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
            if (!k->mesh || n > 8 || MOD->meshes[c.c]) continue;   /* モデルを入れた場面では 3D で描く(スプライトは重ねない) */
#ifdef N_SUBJ
            if (spr_sub_of[i] != 0xFF) continue;          /* 主役は下で */
#endif
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
#ifdef N_SUBJ
    /* 主役: 時刻の表から絵を選び、物体の中心に置く(2×2 は 64×64 ドット)。2 枚目(色)は 8 つ後ろの番号 */
    for (i = 0; i < N_SUBJ; i++) {
        const SprSub *s = &spr_sub[i];
        const SprEnt *e = &spr_ent[s->first];
        u8 j = s->n, k, w, *a;
        V3 v;
        i16 sx, sy;
        while (--j && e[1].t <= t) e++;
        if (!e->kind) continue;
        w = e->kind;
        if (n + w * w > 9) continue;
        o = &obj[s->a];
        pt_cam(o->x, o->y, o->z, &v);
        if (!pt_screen(&v, &sx, &sy)) continue;
        sx = (sx >> 2) - 16 * w; sy = (sy >> 2) - 16 * w;
        for (k = 0; k < w * w; k++) {
            i16 x = sx + ((k & 1) << 5), y = sy + ((k >> 1) << 5);
            if (x < 0 || x > 255 || y < -31 || y > 150) continue;
            a = &g_spr_attr[n++ * 4];
            a[0] = a[32] = (u8)(y - 1); a[1] = a[33] = (u8)x;
            a[2] = (u8)((e->slot + k) << 2); a[34] = (u8)((e->slot + w * w + k) << 2);
            a[3] = s->c1; a[35] = s->c2;
        }
    }
#endif
    /* 使わなかった番号を隠す。先に全部を隠してから置くと、その間に割り込みが VRAM へ送ったフレームは何も映らなかった */
    for (i = 0; i < N_SPR; i++) if (i == 0 || (i >= n && i < 9) || i >= n + 8) g_spr_attr[i * 4] = 209;
}
