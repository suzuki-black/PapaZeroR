/* game.c — ゲーム本体(指示書 3〜7 章): 経路・台本・照準・バルカン・誘導弾・機動・レーザー・敵・ボス・継ぎ目
 *
 * 1 回の更新で dt ティック(60Hz)進める。描画は 20fps が上限で、重いフレームでも遊びの速さは変わらない。
 */

#include "game_int.h"

Obj obj[MAX_OBJ];
u8 g_last_polys;
u16 g_ph[3];
u16 g_last_verts;
Config g_cfg;
u8 g_auto;
u8 life;
u16 mis_left;
u16 g_score, g_hiscore;
u8 g_clock;
u8 g_stg[16];                   /* 面のモジュールのコード(stg.c)が使う値。モジュールは変数を持てない */
u16 g_frames;
u16 g_anim;
u8 g_an;
static u8 an_acc;

/* 経路 */
u16 path_s;                     /* 位置(1/32 単位。2047 単位まで) */
static u16 path_max;
u8  sect_i;
static u8  spd_cur;             /* 単位/秒 × 4 */
i8  cam_pitch_path;
u8  cam_yaw_path;
i16 g_fx, g_fz;
u8  boss_yaw;
i16 boss_y0;
u8  g_shake;
static u8 g_space;
u8 g_fade;                      /* 静的にしない(エンディングの映像 op.c が宇宙から夕焼けへ移す) */
static u8 pal_w[14];
i16 cam_vx, cam_vy, cam_vz;   /* 1 ティックの移動(8.8) */
u16 loop_b, loop_len;    /* 周回区間の終わりと長さ(単位)。0 = なし。長さを引き算で毎回出すと SDCC が番地を読み違えるので持っておく */
static i16 loop_dx, loop_dz;   /* 周回で区間の初めへ戻るときの、カメラの動き(世界ごと同じだけずらす) */
/* 台本 */
u16 ev_i;                       /* 静的にしない(オープニングの演出 op.c が出来事の番号に使う) */
u8  boss_on, boss_dead;
i16 boss_x, boss_y, boss_z;
u8  boss_t, boss_mov, boss_dist, boss_grp;
u8  boss_intro;
u8  scr_end;                    /* 静的にしない(op.c が場面を終える) */
/* 入力・照準 */
u16 aim_x, aim_y;
i16 shot_tx, shot_ty, shot_tz;     /* 敵弾の狙う先(game_ai.c の obj_step が使う) */
static u8 in_cur, in_prev, aim_hold;
static u8 fire_t, heat_t, over_t;
#define MAX_LOCK 8
#define LOCK_HOLD 60                     /* 照準が外れてもロックが残るティック(約 1 秒) */
u8 lock_n, lock_id[MAX_LOCK], lock_t[MAX_LOCK];   /* 静的にしない(試験のスクリプトが読む) */
static u8 lock_rr;                       /* 次に撃つロックの番 */
static u16 fire_tick;                    /* 最後に「Fire!」と言ったティック */
/* 機動 */
u8 pr_kind, pr_t, man_kind, man_t, man_len, inv_t;
static u8 env_roll, env_rt;     /* 演出のロール: 残りフレーム */
static i8 env_rs;
static u8 cam_spin;             /* 宇宙でゆっくり回る(ティックごとに足す 1/8 度) */
/* 字幕 */
const char *cap_s;               /* 静的にしない(caption は game_ai.c) */
u8 cap_t, cap_c;
Laser laser[MAX_LASER];
/* 爆発 */
Fx fx[MAX_FX];

const ObjDef odef[T_COUNT] = {
    { 0, 0, 0 },
    { M_BIKE, 1, 10 }, { M_TANK, 4, 40 }, { M_LTANK, 4, 40 }, { M_MUSTANG, 2, 20 },
    { M_SHIP, 6, 60 }, { M_RMUSTANG, 3, 30 }, { M_MINE, 2, 20 }, { M_LSAT, 5, 50 },
    { M_BATTLESHIP, 30, 120 }, { M_PTBOAT, 3, 30 },
    { M_SUPPLY, 1, 0 }, { M_MEDIC, 1, 0 },
    { M_FLAK, 1, 5 }, { M_ROCKET, 2, 5 }, { M_FLAK, 0, 0 }, { M_ROCKET, 0, 0 }, { 0, 1, 0 }, { 0, 1, 20 },
};

/* 乱数 */
static u16 rnd_s = 0x5A3C;
u8 rnd(void)
{
    rnd_s = (u16)(rnd_s * 25173u + 13849u);
    return (u8)(rnd_s >> 8);
}

void fx_add(i16 x, i16 y, i16 z, u8 big)
{
    u8 i;
    for (i = 0; i < MAX_FX; i++) if (!fx[i].t) {
        fx[i].x = x; fx[i].y = y; fx[i].z = z; fx[i].t = FX_T; fx[i].big = big;
        return;
    }
}

Obj *obj_new(u8 t)
{
    u8 i;
    Obj *o = obj;
    for (i = 0; i < MAX_OBJ; i++, o++) if (!o->t) {
        u8 k;
        u8 *p = (u8 *)o;
        for (k = 0; k < sizeof(Obj); k++) p[k] = 0;
        o->t = t;
        o->hp = odef[t].hp;
        o->mesh = odef[t].mesh;
        return o;
    }
    return 0;
}

void obj_kill(Obj *o, u8 scored)
{
    u8 t = o->t;
    if (scored) g_score += odef[t].score;
    fx_add(o->x, o->y, o->z, t >= T_E01 && t <= T_ELAST);
    if (t == T_SUPPLY) { mis_left = mis_left + 50 > MIS_MAX ? MIS_MAX : mis_left + 50; se_play(SE_HEAL); }
    else if (t == T_MEDIC) { life = (u8)(life + 2 > 8 ? 8 : life + 2); se_play(SE_HEAL); }
    else se_play(t == T_PART ? SE_BOSS : SE_KILL);
    o->t = T_NONE;
}

void obj_damage(Obj *o, u8 n)
{
    if (o->t == T_PART && (o->flags & OF_CAPSULE)) {   /* 娘を撃たない */
        o->flash = 3;
        damage(1);
        pcm_say(VOICE_NOPAPA);
        return;
    }
    if (o->t == T_PART && boss_intro) return;   /* 登場の間は撃てない(6.1) */
    if (o->t == T_PART && ((o->flags & OF_DECOR) || o->group != boss_grp)) return;   /* 飾り・まだ開いていない部位 */
    if (o->t == T_PART && (o->flags & OF_WEAK)) n = (u8)(n * 3);
    if (g_cfg.oneshot) n = 255;
    o->flash = 2;
    if (o->hp > n) { o->hp -= n; return; }
    obj_kill(o, 1);
}

/* ニアクリップ面より手前の頂点を含む面を切って塗る(face.s の faces_draw から。常駐部に空きが無いのでページ0に置く) */
extern u8 g_fd_flash;
static const V3 *fp[4];
void face_near(const Face *f)
{
    u8 i, n = f->hdr & 7;
    for (i = 0; i < n; i++) fp[i] = (const V3 *)&XR[f->v[i]].x;
    poly3p(fp, n, g_fd_flash ? g_fd_flash : f->color);
}

/* ---- 経路 ---- */
static void path_step(u8 dt)
{
    const Sect *p;
    u16 s;
    u8 idx;
    i16 f;
    i16 x0, y0, z0;
    s = path_s + (u16)(((u32)spd_cur * dt * 546u) >> 11);    /* 速度 20 で 1 秒に 10 単位(前は 5。揚力で飛ぶにしては遅すぎた) */
    x0 = cam_x; y0 = cam_y; z0 = cam_z;
    if (loop_b && (s >> 5) >= loop_b) {
        /* 周回: まっすぐな区間の初めへ戻る。物体・爆発・ボスも同じだけずらすので、見た目は前へ進み続ける
         * (前は経路の円を回っていて、同じ所を旋回しているように見えた) */
        u8 i;
        s -= loop_len << 5;
        x0 += loop_dx; z0 += loop_dz;
        for (i = 0; i < MAX_OBJ; i++) { obj[i].x += loop_dx; obj[i].z += loop_dz; }
        for (i = 0; i < MAX_FX; i++) { fx[i].x += loop_dx; fx[i].z += loop_dz; }
        boss_x += loop_dx; boss_z += loop_dz;
    }
    if (s >= path_max) { s = path_max - 1; scr_end |= 2; }
    path_s = s;
    idx = (u8)(s >> 8);
    f = (i16)(s & 255);
    p = &MOD->sect[idx];
    /* 点の間は 8 単位(2048)。fmul(差, f) = 差 × f / 256 を 32bit の途中結果で求める */
    cam_x = p->x + fmul(p[1].x - p->x, f);
    cam_y = p->py + fmul(p[1].py - p->py, f);
    cam_z = p->z + fmul(p[1].z - p->z, f);
    cam_yaw_path = (u8)(p->yaw + (i8)(((i16)(i8)(p[1].yaw - p->yaw) * f) >> 8));
    cam_pitch_path = (i8)(p->pitch + (i8)(((i16)(i8)(p[1].pitch - p->pitch) * f) >> 8));
    if (dt) { cam_vx = (cam_x - x0) / dt; cam_vy = (cam_y - y0) / dt; cam_vz = (cam_z - z0) / dt; }
    g_fx = SIN(cam_yaw_path);
    g_fz = COS(cam_yaw_path);
    sect_i = idx;
    spd_cur = p->spd;
}

/* ---- 台本 ---- */
static void script_step(void)
{
    u16 at = path_s >> 5;
    const Stage *m = MOD;
    while (ev_i < m->nev) {
        const Event *e = &m->ev[ev_i];
        if (e->cmd != EV_END && e->at > at) break;
        if (e->cmd == EV_LOOP) {      /* 敵が残っていれば周回。a = 始まり[単位 / 2] */
            u8 i, alive = 0;
            for (i = 0; i < MAX_OBJ; i++) if (obj[i].t >= T_E01 && obj[i].t <= T_ELAST) alive = 1;
            if (boss_on || alive) {
                if (!loop_b) {
                    const Sect *q = MOD->sect;
                    loop_b = e->at + 2; loop_len = loop_b - (u16)e->x;
                    loop_dx = q[e->x >> 3].x - q[loop_b >> 3].x;
                    loop_dz = q[e->x >> 3].z - q[loop_b >> 3].z;
                }
                return;
            }
            loop_b = 0;
            ev_i++;
            continue;
        }
        if (e->cmd == EV_END) {
            if (e->at > at && !(scr_end & 2)) break;
            if (boss_on) return;
            scr_end |= 1;
            return;
        }
        ev_i++;
        switch (e->cmd) {
        case EV_SPAWN: {
            Obj *o = obj_new(e->a);
            if (o) {
                o->x = e->x; o->y = e->y; o->z = e->z; o->ptn = e->b; o->yaw = cam_yaw_path;
                o->tm = rnd();
            }
            break; }
        case EV_PROP: {
            Obj *o = obj_new(T_PROP);
            if (o) { o->mesh = e->a; o->x = e->x; o->y = e->y; o->z = e->z; o->yaw = cam_yaw_path; o->ptn = e->b; }
            break; }
        case EV_ITEM: {
            Obj *o = obj_new(e->a);
            if (o) { o->x = e->x; o->y = e->y; o->z = e->z; o->ptn = P_HOLD; o->yaw = cam_yaw_path; }
            break; }
        case EV_BOSS:
            boss_y0 = boss_y = e->y;
            boss_begin();
            {   /* 遠景から近づく(6.1) */
                i16 d = (i16)(boss_dist + 40) << 8;
                boss_x = cam_x + fmul(g_fx, d); boss_z = cam_z + fmul(g_fz, d);
            }
            break;
        case EV_ROLL:
            env_rs = (i8)e->b; env_rt = e->a;
            break;
        case EV_PROMPT:
            pr_kind = e->a; pr_t = e->b;
            se_play(SE_ALARM);
            pcm_say(e->a == PR_ROLL ? VOICE_ROLL : e->a == PR_LOOP ? VOICE_LOOP : VOICE_DIVE);
            break;
        case EV_TEXT:
            caption(m->str[e->a], e->b ? e->b : C_WHITE, 120);
            break;
        case EV_SUB:
            sub_text(m->str[e->a]);
            break;
        case EV_VOICE: pcm_say(e->a); break;
        case EV_BGM: bgm_play(e->a); break;
        case EV_PAL: cam_spin = e->a; break;
        case EV_CAM: cam_x += e->x; break;
        case EV_FADE: g_fade = 1; break;
        }
    }
}

/* ---- 入力 ---- */
static void aim_step(u8 in, u8 dt)
{
    u8 step;
    if (in & (IN_UP | IN_DOWN | IN_LEFT | IN_RIGHT)) { if (aim_hold < 200) aim_hold += dt; } else aim_hold = 0;
    /* 1 ティックに 2 ドット、押し続けて 0.1 秒で 4、0.3 秒で 6(画面の端から端まで約 0.7 秒) */
    step = (u8)((aim_hold >= 18 ? 6 : aim_hold >= 6 ? 4 : 2) * dt);
    if (in & IN_LEFT) aim_x = aim_x > 8 + step ? aim_x - step : 8;
    if (in & IN_RIGHT) aim_x = aim_x + step < 247 ? aim_x + step : 247;
    if (in & IN_UP) aim_y = aim_y > 8 + step ? aim_y - step : 8;
    if (in & IN_DOWN) aim_y = aim_y + step < 151 ? aim_y + step : 151;
}

/* 照準を毎ティック動かす。描画(20fps)を待たずに、描画の合間と表示待ちの間に呼ぶ。
 * スプライト 0 の位置だけ書き換え、割り込み(sys.s)が VRAM へ送る */
static u16 ap_tick;
static void aim_poll(void)
{
    u8 d = (u8)(g_tick - ap_tick);
    if (!d) return;
    ap_tick += d;
    if (g_scene != 1 || g_auto) return;
    aim_step(input_raw(), d);
    g_spr_attr[0] = (u8)(aim_y - 17);
    g_spr_attr[1] = (u8)(aim_x - 16);
    g_spr0_req = 1;
}



/* 空の飾り(筋雲・星。tools/stage_data.py の Mod.sky)。空の決まった方角(ワールド。どの面も経路は北から ±40 度に収まる)に貼り付け、
 * カメラの向きで画面に写すので、
 * ロールや宙返りでは地平線と一緒に回る。シリアスな映画の空に合うよう、地平線の帯と同じ色の筋雲と、灰色の星だけにする(記号の太陽や月は描かない)。
 * データは [点の数][色] { 方角(x 東, y 上, z 北。長さ 127) } × 点の数 を 0 まで繰り返す(筋雲の点も、ビルドのときに 1 つずつ並べる)。
 * 色に 80h が立った組は海の白波: { x, z(0〜63 単位) } × 点の数。64 単位四方の並びを海の面(y = 0)に敷き詰め、2 ブロックの横線で描く */
static void sky_marks(void)
{
    const u8 *p = MOD->sky;
    u8 n, g;
    i16 x, y, wx, wy, wz;
    V3 c;
    g_rh = 1;
    while ((n = *p++)) {
        g = *p++;
        g_color = g & 15;
        g_rw = (g >> 7) + 1;                  /* 白波は 2 ブロック、ほかは 1 */
        for (; n; n--) {
            if (g & 0x80) {
                wx = ((((u16)p[0] << 8) - cam_x) & 0x3FFF) - 0x2000;
                wz = (((u16)p[1] << 8) - cam_z) & 0x3FFF;
                wy = -cam_y;
                p += 2;
            } else {                          /* カメラから約 64 単位先の点 */
                wx = (i8)p[0] << 7; wy = (i8)p[1] << 7; wz = (i8)p[2] << 7;
                p += 3;
            }
            pt_cam(cam_x + wx, cam_y + wy, cam_z + wz, &c);
            if (!pt_screen(&c, &x, &y)) continue;
            x >>= 4; y >>= 4;
            if ((u16)x < 63 && (u16)y < GAME_ROWS) { g_rx = (u8)x; g_ry = (u8)y; rect_fill(); }
        }
    }
}

static void man_start(u8 kind, u8 len)
{
    man_kind = kind; man_t = 0; man_len = len;
}

/* ロックできるもの: 敵と、今撃てるボスの部位(登場中・飾り・まだ開いていない部位・隠れた部位・ヒナのカプセルは除く。
 * 除かないと、効かない部位が 8 つの枠を埋め、撃てる敵がロックされなかった) */
static u8 lockable(u8 id)
{
    const Obj *o = &obj[id];
    if (o->t >= T_E01 && o->t <= T_ELAST) return 1;
    return o->t == T_PART && !boss_intro && o->group == boss_grp && !(o->flags & (OF_CAPSULE | OF_DECOR | OF_HIDDEN));
}

static void lock_drop(u8 i)
{
    if (i < lock_rr) lock_rr--;            /* 撃つ順番をずらさない */
    for (lock_n--; i < lock_n; i++) { lock_id[i] = lock_id[i + 1]; lock_t[i] = lock_t[i + 1]; }
}

/* ロックせずに撃った誘導弾: 進む向きへまっすぐ飛んで外れる(game_ai.c の obj_step から。そちらに書くと obj_step が 800 B 膨らんだ) */
void mis_straight(Obj *o, u8 dt)
{
    if (o->tm <= dt) { o->t = T_NONE; return; }
    o->x += (g_fx >> 1) * dt; o->z += (g_fz >> 1) * dt;
    o->tm -= dt;
}

/* ロックを続けてよいか: 撃てる敵で、まだ前にいる(通り過ぎた敵には撃たない) */
static u8 lock_keep(u8 id)
{
    const Obj *o = &obj[id];
    return lockable(id) && fmul(g_fx, o->x - cam_x) + fmul(g_fz, o->z - cam_z) > 0;
}

/* ロックの枠(ブロック。照準を中心に、隠しコンフィグの LOCKBOX で横 8・16・24・32 × 縦はその約 2/3。画面の中に切る)。描くのは overlay_draw */
static u8 lb_x0, lb_y0, lb_x1, lb_y1;

static void lock_scan(void)
{
    u8 ax = (u8)(aim_x >> 2), ay = (u8)(aim_y >> 2), i, k, id;
    HitRect *h = hits;
    u8 hw = (u8)(g_cfg.lockbox << 2), hh = (u8)(hw - (hw >> 2) - (hw >> 3));   /* 枠の半分の幅と高さ(3 なら 12 と 8) */
    lb_x0 = ax > hw ? ax - hw : 0;
    lb_x1 = ax + hw - 1 < 63 ? ax + hw - 1 : 63;
    lb_y0 = ay > hh ? ay - hh : 0;
    lb_y1 = ay + hh - 1 < 39 ? ay + hh - 1 : 39;
    for (i = 0; i < n_hits; i++, h++) {
        if (h->x1 < lb_x0 || h->x0 > lb_x1 || h->y1 < lb_y0 || h->y0 > lb_y1) continue;
        id = h->id;
        if (!lockable(id)) continue;
        for (k = 0; k < lock_n && lock_id[k] != id; k++) ;
        if (k < lock_n) { lock_t[k] = LOCK_HOLD; continue; }
        if (lock_n == MAX_LOCK) {
            /* 満杯なら、枠を出て残っているだけのロックのうち一番古いものを譲る(枠の中の敵は lock_t が LOCK_HOLD - 8 以上) */
            u8 j = 0;
            for (k = 1; k < MAX_LOCK; k++) if (lock_t[k] < lock_t[j]) j = k;
            if (lock_t[j] >= LOCK_HOLD - 8) continue;
            lock_drop(j);
        }
        lock_id[lock_n] = id; lock_t[lock_n++] = LOCK_HOLD; se_play(SE_LOCK);
    }
}

static void lock_box_draw(void)
{
    /* 四隅に長さ 3 の鉤(水色)。敵の印(白・赤の小さな鉤)と見分けられるように */
    g_color = C_CYAN;
    g_rw = 3; g_rh = 1;
    g_rx = lb_x0; g_ry = lb_y0; rect_fill();
    g_rx = lb_x1 - 2; rect_fill();
    g_ry = lb_y1; rect_fill();
    g_rx = lb_x0; rect_fill();
    g_rw = 1; g_rh = 3;
    g_ry = lb_y0; rect_fill();
    g_rx = lb_x1; rect_fill();
    g_ry = lb_y1 - 2; rect_fill();
    g_rx = lb_x0; rect_fill();
}

static void fire_step(u8 dt)
{
    u8 in = in_cur, pressed = (u8)(in & ~in_prev), b = pressed & IN_B, i, id;
    /* 機動の指示に応える(指示が出ている間は B で機動。ロックがあれば誘導弾も撃つ。
     * 前は B が機動だけになり、撃ったつもりの誘導弾が出ず、消えたように見えた) */
    if (pr_kind) {
        if (b) {
            if (!lock_n) b = 0;
            man_start(pr_kind, pr_kind == PR_ROLL ? 24 : 32);
            inv_t = pr_kind == PR_ROLL ? 80 : 40;
            g_score += 50;
            se_play(SE_LOCK);
            if (pr_kind == PR_LOOP) {
                /* 後ろの敵を正面へ */
                u8 i;
                Obj *o = obj;
                for (i = 0; i < MAX_OBJ; i++, o++) if (o->t && o->ptn == P_TAIL) {
                    i16 d = 0x3C00;
                    o->ptn = P_PASS; o->st = 0;
                    o->x = cam_x + fmul(g_fx, d); o->z = cam_z + fmul(g_fz, d);
                }
            }
            pr_kind = PR_NONE;
        } else if (pr_t <= dt) {
            pr_kind = PR_NONE;
        } else {
            if ((pr_t ^ (u8)(pr_t - dt)) & 16) se_play(SE_LOCK);     /* 受付の間のピッ・ピッ */
            pr_t -= dt;
        }
    }
    /* バルカン: 6 ティックごと。3 秒連続で過熱 */
    if (fire_t) fire_t = fire_t > dt ? fire_t - dt : 0;
    if (over_t) {
        over_t = over_t > dt ? over_t - dt : 0;
        if (!over_t) heat_t = 0;
    } else if (in & IN_A) {
        heat_t += dt;
        if (heat_t >= 180) { over_t = 60; heat_t = 180; }
        else if (!fire_t) {
            fire_t = 6;
            se_play(SE_SHOT);
            id = aim_target();
            if (id != 0xFF) {
                Obj *o = &obj[id];
                obj_damage(o, 1);
                if (o->t) se_play(SE_HIT);
            }
        }
    } else {
        if (heat_t) heat_t = heat_t > dt * 2 ? heat_t - dt * 2 : 0;
    }
    g_heat = heat_t >> 3;
    /* 誘導弾のロック: 照準のまわりの大きな枠に敵の枠が少しでもかかれば自動(8 体まで。外れても約 1 秒残る)。
     * 撃っても外さない。外すのは時間切れ・倒した・通り過ぎたとき。機動の間は画面が回って敵が枠を出るので、
     * 残り時間を減らさず、終わってから約 1 秒残す(前はロールの後にロックが外れていた) */
    for (i = 0; i < lock_n; ) {
        if (lock_t[i] <= dt || !lock_keep(lock_id[i])) { lock_drop(i); continue; }
        lock_t[i] = man_len ? LOCK_HOLD : lock_t[i] - dt;
        i++;
    }
    lock_scan();
    /* 誘導弾: B で 1 発。ロックした敵へ順に撃つ(3 体なら A → B → C → A → B → C。倒れていない前提で回す)。
     * ロックが無ければまっすぐ飛んで外れる。撃つたびに「Fire!」(続けて撃てば前の Fire! を切って頭から) */
    if (b && mis_left) {
        Obj *o = obj_new(T_MYMIS);
        if (o) {
            o->x = cam_x - (cm[3] >> 1); o->y = cam_y - 0x80; o->z = cam_z - (cm[5] >> 1);
            o->tm = 72;
            if (lock_n) {
                if (lock_rr >= lock_n) lock_rr = 0;
                o->tgt = lock_id[lock_rr++];
            }
            else { o->tgt = 0xFF; o->tm = 60; }
            mis_left--;
            /* ほかの声(ヒナの台詞など)が鳴っている間は割り込まない。Fire! どうしは差し替える */
            se_play(SE_MISSILE);
            if (!pcm_mode || (u16)(g_tick - fire_tick) < 24) { pcm_say(VOICE_FIRE); fire_tick = g_tick; }
        }
    }
}

/* ---- 描画 ---- */
static u8 ord[MAX_OBJ];
static i16 ord_z[MAX_OBJ];
static V3 ord_c[MAX_OBJ];

static void sects_draw(void)
{
    const Sect *s0 = MOD->sect;
    u8 n = MOD->nsect > 255 ? 255 : (u8)MOD->nsect;
    i8 k;
    u8 base = sect_i;
    V3 c;
    /* 背後の区画は描かない。道中は面ごとの数(ふつう 8 区画 = 64 単位先まで。11 区画だと地形が道中の 1 フレームの大半を使った)、
     * ボス戦は 5 区画(8.1) */
    for (k = boss_on ? 4 : (i8)MOD->ahead; k >= 0; k--) {
        i16 si = (i16)base + k;
        const Sect *s;
        if (si < 0) continue;
        {
            i16 ox = 0, oz = 0;
            /* 周回の終わりより先は、区間の初めの区画を、戻る分だけ先へずらして描く(戻った後と同じ絵になる) */
            if (loop_b && (u16)si >= (loop_b >> 3)) { si -= (i16)(loop_len >> 3); ox = loop_dx; oz = loop_dz; }
            if (si >= n) continue;
            s = &s0[si];
            if (!s->mesh) continue;
            pt_cam(s->x - ox, s->y, s->z - oz, &c);
        }
        mat_yaw(s->yaw, 0);
        g_lod_min = boss_on ? k > 1 : k > 3;
        mesh_draw(s->mesh, &c, g_mm, 0, 0xFF);
        aim_poll();
    }
}

static void objs_draw(void)
{
    u8 i, n = 0, k;
    Obj *o = obj;
    for (i = 0; i < MAX_OBJ; i++, o++) {
        V3 *c;
        if (!o->t || (o->t == T_PROP && !o->mesh)) continue;
        c = &ord_c[i];
        pt_cam(o->x, o->y, o->z, c);
        if (c->z < 0x0100 || c->z > 0x7800) continue;
        k = n;
        while (k && ord_z[k - 1] < c->z) { ord[k] = ord[k - 1]; ord_z[k] = ord_z[k - 1]; k--; }
        ord[k] = i; ord_z[k] = c->z;
        n++;
    }
    for (k = 0; k < n; k++) {
        u8 id = ord[k];
        const u8 *mesh;
        o = &obj[id];
        mesh = MOD->meshes[o->mesh];
        if (!mesh) continue;
        g_obj_yaw = o->yaw;
        g_lod_min = o->t == T_PART;        /* ボスの部位は常に細部を省く(大きい面が多く、1 面のボスで 10fps まで落ちた) */
        if (o->mesh == M_ROCKET) g_lod_min = 2;   /* 誘導弾はいつも矩形で描く(64×40 では点にしか見えない。カメラのすぐ前を飛ぶので、面で描くと 1 本 2.7ms かかった) */
        if (o->t == T_MYMIS) id = 0xFF;    /* 自分の誘導弾は当たり矩形を作らない(バルカンが手前の誘導弾に当たって壊していた) */
        if (o->t == T_PART && !o->yaw && !o->roll) {
            mesh_draw(mesh, &ord_c[ord[k]], 0, o->flash ? C_WHITE : 0, id);
        } else {
            mat_yaw(o->yaw, o->roll);
            mesh_draw(mesh, &ord_c[ord[k]], g_mm, o->flash ? C_WHITE : 0, id);
        }
    }
}

/* 敵の印: 攻撃してくるもの(敵・敵弾・今のボスの部位)の当たり矩形の四隅に鉤を描く。照準が重なっている敵は赤、補給は緑。
 * 描いた直後の当たり矩形を使うので、照準の色もこのフレームの絵と一致する */
static u8 aim_foe;      /* 照準の下に攻撃してくるものがいる(照準を赤くする) */

static u8 is_foe(const Obj *o)
{
    if (o->t >= T_E01 && o->t <= T_ELAST) return 1;
    if (o->t >= T_FLAK && o->t <= T_MINE) return 1;
    return o->t == T_PART && o->group == boss_grp && !(o->flags & (OF_CAPSULE | OF_DECOR | OF_HIDDEN));
}

static void spr_set(u8 n, i16 x, i16 y, u8 pat, u8 col)
{
    u8 *a = &g_spr_attr[n * 4];
    if (y < -16 || y > 143) { a[0] = 209; return; }
    a[0] = (u8)(y - 1); a[1] = (u8)x; a[2] = (u8)(pat * 4); a[3] = col;
}

/* 敵の名前の札と引き出し線(零戦の画像認識が付ける、という体裁。背景との前後は気にしない)。
 * SCREEN 3 のスプライトは横に 4 枚までで、5 枚目からは番号の大きいものが消える。
 * 札(スプライト 1〜)は、上下 32 ドット以内に札が 3 枚以上あれば置かない(どの走査線でも照準と合わせて 4 枚以下)。
 * 置けなければ敵の高さから ±32・±64 ドットずらし、ずらした分だけ斜めの線をつなぐ。
 * 線は札のあとの番号で、毎フレーム順番を回す。線が 4 枚を超えた行では線だけが交代で消え(ちらつき)、札は消えない */
#define N_LABEL 6
#define N_LINE (N_SPR - 1 - N_LABEL)
#define PAT_H 13                               /* 線の絵: 横・「/」・「\」(tools/gen_data.py) */
#define PAT_UP 14
#define PAT_DN 15
#define PAT_BOSS 16                            /* ボスの部位の札 */
static u8 lb_x[N_LABEL], lb_y[N_LABEL];        /* 置いた札の左上(ドット) */
static u8 ln_x[N_LINE], ln_y[N_LINE], ln_p[N_LINE], ln_c[N_LINE];
static u8 line_n, line_rot;
static u16 hk[MAX_HIT];                        /* 札の候補の強さ(小さいほど強い。0xFFFF = 付けない) */

/* 札 n を、敵の当たり矩形 h の横に置く。置けなければ 0 */
static u8 label_place(u8 n, const HitRect *h, u8 col)
{
    static const i8 dys[5] = { 0, -1, 1, -2, 2 };   /* ずらす段(32 ドット単位) */
    u8 cy = (u8)((h->y0 + h->y1) * 2), i, j;
    i16 xr = (i16)h->x1 * 4, xl = (i16)h->x0 * 4;
    if (cy < 16) return 0;
    for (i = 0; i < 5; i++) {
        i8 d = dys[i];
        u8 k = d < 0 ? (u8)-d : d ? (u8)d : 1, right, c;   /* k = 線の本数(横 32 ドットずつ) */
        i16 y = cy + d * 32 - 10, x;                         /* 字の真ん中(上から 10 ドット)を線の先に合わせる */
        right = xr + k * 32 + 30 <= 255;
        x = right ? xr + k * 32 : xl - k * 32 - 32;
        if (x < 0 || y < 0 || y > 160 - 22) continue;
        for (c = 0, j = 0; j < n; j++) {
            i16 dy = lb_y[j] - y, dx = lb_x[j] - x;
            if (dy > -32 && dy < 32) { c++; if (dx > -32 && dx < 32) c = 9; }   /* 字が重なるなら置かない */
        }
        if (c >= 3) continue;
        lb_x[n] = (u8)x; lb_y[n] = (u8)y;
        { u8 t = obj[h->id].t; spr_set(1 + n, x, y, t == T_PART ? PAT_BOSS : t, col); }   /* 札の絵は 1 番から T_E01 の順。ボスの部位は「BOSS」 */
        for (j = 0; j < k && line_n < N_LINE; j++, line_n++) {
            ln_x[line_n] = (u8)(right ? xr + j * 32 : xl - (j + 1) * 32);
            ln_y[line_n] = !d ? cy - 15 : d < 0 ? cy - (j + 1) * 32 : cy + j * 32;
            ln_p[line_n] = !d ? PAT_H : (d < 0) == right ? PAT_UP : PAT_DN;
            ln_c[line_n] = col;
        }
        return 1;
    }
    return 0;
}

static void marks_draw(void)
{
    u8 i, tgt = aim_target(), np;
    HitRect *h = hits;
    aim_foe = tgt != 0xFF && is_foe(&obj[tgt]);
    for (i = 0; i < n_hits; i++, h++) {
        const Obj *o = &obj[h->id];
        u8 pr = 2;
        hk[i] = 0xFFFF;
        if (!o->t) continue;
        if (is_foe(o)) {                   /* 照準が重なっているか、ロックしている敵は赤 */
            u8 k;
            for (k = 0; k < lock_n && lock_id[k] != h->id; k++) ;
            if (h->id == tgt) pr = 0; else if (k < lock_n) pr = 1;
            g_color = pr < 2 ? C_RED : C_WHITE;
        }
        else if ((u8)(o->t - T_SUPPLY) < 2) g_color = C_GREEN;
        else continue;
        g_rx = (u8)(h->x0 - 1); g_ry = (u8)(h->y0 - 1); g_rw = h->x1; g_rh = h->y1;
        marks4();
        if (o->t <= T_MEDIC || o->t == T_PART) hk[i] = ((u16)pr << 14) | ((u16)h->z >> 2 & 0x3FFF);   /* 名前は敵・補給・ボスの部位(弾には付けない) */
    }
    /* 強い順(照準 → ロック → 近い)に置く。先に置いた札ほど敵のすぐ横に来る */
    line_n = 0;
    for (np = 0; np < N_LABEL; ) {
        u8 b = 0xFF;
        u16 bk = 0xFFFF;
        for (i = 0; i < n_hits; i++) if (hk[i] < bk) { bk = hk[i]; b = i; }
        if (b == 0xFF) break;
        hk[b] = 0xFFFF;
        h = &hits[b];
        if (label_place(np, h, (u8)(obj[h->id].t - T_SUPPLY) < 2 ? C_GREEN : bk >> 14 < 2 ? C_RED : C_WHITE)) np++;
    }
    for (i = np; i < N_LABEL; i++) g_spr_attr[(1 + i) * 4] = 209;
    /* 線は毎フレーム番号を回す(4 枚を超えた行で、消える線が毎回変わる) */
    line_rot++;
    for (i = 0; i < N_LINE; i++) {
        u8 n = 1 + N_LABEL + i;
        if (i < line_n) { u8 k = (u8)((i + line_rot) % line_n); spr_set(n, ln_x[k], ln_y[k], ln_p[k], ln_c[k]); }
        else g_spr_attr[n * 4] = 209;
    }
}


static void overlay_draw(void)
{
    u8 scene = MOD->flags & SF_SCENE;
    if (cap_t) {
        text_center(1, cap_s, cap_c, 1);
    } else if (pr_kind && (g_anim & 2)) {
        text_center(1, pr_kind == PR_ROLL ? "ROLL!" : pr_kind == PR_LOOP ? "LOOP!" : "DIVE!", C_RED, 1);
    }
    if (fire_t > 3 && !(MOD->flags & SF_SCENE)) {     /* 曳光弾: 照準の手前から奥へ流れる白い 2 個(演出のみ) */
        u8 ax = (u8)(aim_x >> 2), ay = (u8)(aim_y >> 2), k = (u8)(fire_t - 3);
        g_color = C_WHITE;
        g_rx = (u8)(ax + (32 - ax) / (k + 1)); g_ry = (u8)(ay + (38 - ay) / (k + 1));
        if (g_rx < 64 && g_ry < 40) pset();
    }
    if (scene && g_mod == 0 && (g_anim & 8)) text_center(1, "SPACE: SKIP", C_WHITE, 1);   /* オープニングは飛ばせる */
    /* ボスを倒した後: 連続爆発が終わったら(stg.c の g_stg[10])、次の場面まで真ん中に大きく「STAGE CLEAR!」 */
    if (boss_dead && !g_stg[10]) { text_center(9, "STAGE", C_WHITE, 2); text_center(21, "CLEAR!", (g_anim & 4) ? C_ORANGE : C_WHITE, 2); }
    if (g_cfg.fps) {
        extern u16 g_perf_frame;
        extern u8 g_perf_ticks;
        num_draw(0, 34, g_perf_ticks, 2, C_WHITE);
        num_draw(10, 34, g_perf_frame >> 8, 3, C_WHITE);
    }
    if (!scene && g_scene == 1) lock_box_draw();
    /* 照準(スプライト 0) */
    if (scene) { u8 n; if (!MOD->hook) for (n = 0; n < N_SPR; n++) g_spr_attr[n * 4] = 209; }   /* 演出のある場面(オープニング)は op.c が人物をスプライトで描く */
    else spr_set(0, (i16)aim_x - 16, (i16)aim_y - 16, 0,
                 over_t ? ((g_anim & 1) ? C_RED : C_WHITE) : aim_foe ? C_RED : C_WHITE);   /* 敵に重なると赤(撃てば当たる・ロックできる) */
}


/* ---- 1 面 ---- */
static void stage_reset(void)
{
    u8 i;
    for (i = 0; i < MAX_OBJ; i++) obj[i].t = T_NONE;
    for (i = 0; i < MAX_LASER; i++) laser[i].kind = 0xFF;
    for (i = 0; i < MAX_FX; i++) fx[i].t = 0;
    path_s = 0; ev_i = 0; scr_end = 0; loop_b = 0;
    g_space = MOD->flags & (SF_SPACE | SF_DEEP); g_fade = 0; g_shake = 0;
    boss_on = 0; boss_dead = 0; boss_grp = 0;
    mis_left = MIS_MAX;                /* 誘導弾は面ごとに満タン */
    pr_kind = 0; man_t = 0; man_len = 0; inv_t = 0; env_rt = 0; env_roll = 0; lock_n = 0; cam_spin = 0;
    cap_t = 0; heat_t = 0; over_t = 0;
    n_hits = 0;
    aim_x = 128; aim_y = 80;
    path_max = (u16)(MOD->nsect - 2) << 8;
    spd_cur = MOD->sect[0].spd;
}

void game_reset(void)
{
    life = g_cfg.life; mis_left = MIS_MAX; g_score = 0; g_clock = 0x60;
    cockpit_reset();
}

static u8 stage_body(u8 mod);
u8 stage_run(u8 mod)
{
    u8 r = stage_body(mod);
    g_r18_top = 0; g_r18_bot = 0;          /* 揺れの途中で面を抜けても、ほかの場面にずれを残さない */
    return r;
}

static u8 stage_body(u8 mod)
{
    u16 t0, t_demo, ts;
    mod_load_now(mod);
    stage_reset();
    g_scene = (MOD->flags & SF_SCENE) ? 3 : 1;
    set_stage_palette(MOD->pal);
    cockpit_mode(g_scene == 3);
    cockpit_reset();
    if (MOD->bgm) bgm_play(MOD->bgm);
    if (g_scene == 1) {
        caption(MOD->name + 10, C_WHITE, 120);   /* 「STAGE n / 」を除く。字幕は 16 文字まで */
    }
    ts = t0 = g_tick;
    ap_tick = t0;
    g_poll = aim_poll;
    t_demo = g_anim;
    for (;;) {
        u16 now = g_tick;
        u8 dt = (u8)(now - t0);
        t0 = now;
        if (dt > 8) dt = 8;
        if (!dt) dt = 1;
        g_frames++;
        an_acc += dt;                      /* 演出の時計は 3 ティックで 1 つ(20fps のときの 1 枚と同じ速さ) */
        g_an = an_acc / 3;
        an_acc -= g_an * 3;
        g_anim += g_an;
        in_prev = in_cur;
        in_cur = input_raw();
        if (g_auto == 2 && ((in_cur & IN_A) || (u16)(g_anim - t_demo) >= 800)) { bgm_stop(); return 1; }   /* デモは 40 秒か、キーで終わる */
        if (g_scene == 3) {
            if ((in_cur & IN_A) && !(in_prev & IN_A) && mod == 0) { bgm_stop(); return 1; }
        } else {
            if (g_auto) in_cur = auto_input(in_prev);
            aim_poll();
            fire_step(dt);
        }
        path_step(dt);
        script_step();
        if (g_fade) {                      /* エンディング: 再突入の色へ移り、白く光って朝の町へ */
            lerp_pal(MOD->pal, MOD->pal2, g_fade >> 1, pal_w);
            vdp_set_palette(9, pal_w);
            /* 足すのと比べるのを 1 つの式に書くと、SDCC 4.x は足した値を書き戻さず(32 を超えたときの 0 だけを書く)、色が移らなかった */
            g_fade += g_an;
            if (g_fade > 32) { g_fade = 0; g_space = 0; set_stage_palette(MOD->pal2); }
        }
        /* カメラの向き: 経路 + 機動 + 演出のロール */
        {
            u8 roll = 0, pitch = (u8)cam_pitch_path, k;
            for (k = g_an; k && env_rt; k--) { env_roll = (u8)(env_roll + env_rs); env_rt--; }
            roll = env_roll;
            if (cam_spin) roll = (u8)(g_anim * cam_spin >> 2);
            if (man_len) {
                u16 ang = (u16)man_t * 256 / man_len;
                man_t += g_an;
                if (man_kind == PR_ROLL) roll += (u8)ang;
                else if (man_kind == PR_LOOP) pitch += (u8)ang;
                else {                     /* 急降下: 半ロール + 機首下げ */
                    u8 a = man_t < man_len / 2 ? (u8)ang : (u8)(255 - ang);
                    pitch -= a >> 2;
                    roll += a;
                }
                if (man_t >= man_len) man_len = 0;
            }
            cam_yaw = cam_yaw_path;
            cam_pitch = pitch;
            cam_roll = g_cfg.roll ? 0 : roll;
            if (life && g_shake > 4 && !man_len) cam_roll += (g_shake & 1) ? 4 : (u8)-4;   /* 被弾の揺れ(傾きも左右に) */
            cam_update();
        }
        if (inv_t) inv_t = inv_t > dt ? inv_t - dt : 0;
        if (cap_t) cap_t = cap_t > dt ? cap_t - dt : 0;
        /* 敵弾の狙う先: 自機の少し前(SHOT_AHEAD)。自機そのものを狙うと、近づくほど画面の端へ流れて外へ出てしまい、
         * 撃ち落とせなかった(1 面のボスの弾は、映るのが撃たれた直後の 0.2 秒ほどで、全弾が当たっていた)。
         * 前の点を狙えば、弾は画面の真ん中へ向かって大きくなりながら飛んでくる(Starblade と同じ見せ方) */
        shot_tx = cam_x + fmul(g_fx, SHOT_AHEAD); shot_ty = cam_y; shot_tz = cam_z + fmul(g_fz, SHOT_AHEAD);
        obj_step(dt);
        if (boss_on) boss_step(dt);
        if (MOD->hook) MOD->hook(g_tick - ts);   /* オープニング: カメラと人物・機体を時刻で動かす(曲と同じ時計) */
        {
            extern u16 g_perf_frame;
            u16 t = timer_read();
            g_perf_polys = 0; g_perf_verts = 0;
            g_spr_live = 1;                /* 描画の間は VDP に触らない。照準は割り込みが書く */
            sky_draw(g_space);
            sky_marks();
            aim_poll();
            g_ph[0] = timer_read() - t;
            sects_draw();
            g_ph[1] = timer_read() - t;
            g_lod_min = 0;
            n_hits = 0;
            objs_draw();
            aim_poll();
            g_ph[2] = timer_read() - t;
            fx_draw(dt);
            lasers_draw();
            if (!(MOD->flags & SF_SCENE)) marks_draw();
            overlay_draw();
            g_spr_live = 0;                /* 描画の外では割り込みに照準を書かせない(場面を飛ばすと present を通らずに抜ける) */
            g_perf_frame = timer_read() - t;
            g_last_polys = g_perf_polys; g_last_verts = g_perf_verts;
        }
        g_spd_show = (u8)(spd_cur + 30);
        g_alt_show = g_space ? 0xFF : (u8)(cam_y >> 8);   /* 宇宙には高さが無い(計器は「---」) */
        g_min_ticks = 2;                   /* ゲームの本体だけ 30fps まで(ほかの場面はフレームで数えるので 20fps のまま) */
        present();
        g_min_ticks = 3;
        g_shake = g_shake > g_an ? g_shake - g_an : 0;
        g_r18_bot = g_shake ? (g_shake & 2 ? 0x03 : 0x0D) : 0;
        g_r18_top = g_shake ? (g_shake & 1 ? (g_shake > 5 ? 0x06 : 0x03) : (g_shake > 5 ? 0x0A : 0x0D)) : 0;   /* ゲーム画面も左右に(初めは大きく) */
        if (life == 0) {
            /* ENGINE FIRE: 黒煙(色を灰へ移す)→ ゲームオーバー */
            static const u8 gray[14] = { 0x22, 2, 0x11, 1, 0x33, 3, 0x22, 2, 0x22, 2, 0x11, 1, 0x33, 3 };
            u8 i;
            bgm_stop();
            g_r18_bot = 0; g_r18_top = 0;
            for (i = 0; i <= 32; i++) {
                lerp_pal(MOD->pal, gray, i >> 1, pal_w);
                vdp_set_palette(9, pal_w);
                sky_draw(g_space);
                text_center(16, "ENGINE FIRE", C_RED, 1);
                present();
            }
            return 0;
        }
        if (scr_end & 1 || (scr_end & 2 && !boss_on)) break;
    }
    g_hiscore = g_score > g_hiscore ? g_score : g_hiscore;
    return 1;
}

