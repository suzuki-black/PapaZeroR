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
u16 g_frames;
u16 g_anim;
u8 g_an;
static u8 an_acc;

/* 経路 */
u16 path_s;                     /* 位置(1/64 単位) */
static u16 path_max;
u8  sect_i;
static u8  spd_cur;             /* 単位/秒 × 4 */
i8  cam_pitch_path;
u8  cam_yaw_path;
i16 g_fx, g_fz;
u8  boss_yaw;
i16 boss_y0;
u8  g_shake;
static u8 g_space, g_fade;
static u8 pal_w[14];
i16 cam_vx, cam_vy, cam_vz;   /* 1 ティックの移動(8.8) */
u16 loop_b, loop_len;    /* 周回区間の終わりと長さ(単位)。0 = なし。長さを引き算で毎回出すと SDCC が番地を読み違えるので持っておく */
/* 台本 */
static u16 ev_i;
u8  boss_on, boss_dead;
i16 boss_x, boss_y, boss_z;
u8  boss_t, boss_mov, boss_dist, boss_grp;
u8  boss_intro;
static u8  scr_end;
/* 入力・照準 */
u16 aim_x, aim_y;
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
static const char *cap_s;
static u8 cap_t, cap_c;
Laser laser[MAX_LASER];
/* 爆発 */
Fx fx[MAX_FX];

const ObjDef odef[T_COUNT] = {
    { 0, 0, 0 },
    { M_BIKE, 1, 10 }, { M_TANK, 4, 40 }, { M_LTANK, 4, 40 }, { M_MUSTANG, 2, 20 },
    { M_SHIP, 6, 60 }, { M_RMUSTANG, 3, 30 }, { M_MINE, 2, 20 }, { M_LSAT, 5, 50 },
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

void caption(const char *s, u8 color, u8 t)
{
    cap_s = s; cap_c = color; cap_t = t;
}

void damage(u8 n)
{
    if (inv_t || g_cfg.god || g_auto == 2) return;
    n = (u8)(n * g_cfg.damage);
    life = life > n ? (u8)(life - n) : 0;
    flash_palette();
    se_play(SE_DAMAGE);
    g_shake = 10;
    inv_t = 12;
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
    fx_add(o->x, o->y, o->z, t >= T_E01 && t <= T_E08);
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

/* ---- 経路 ---- */
static void path_step(u8 dt)
{
    const PathPt *p;
    u16 s, idx;
    i16 f;
    i16 x0, y0, z0;
    s = path_s + (u16)(((u32)spd_cur * dt * 546u) >> 10);    /* 速度 20 で 1 秒に 10 単位(前は 5。揚力で飛ぶにしては遅すぎた) */
    if (loop_b && (s >> 6) >= loop_b) s -= loop_len << 6;
    if (s >= path_max) { s = path_max - 1; scr_end |= 2; }
    path_s = s;
    idx = s >> 7;
    f = (i16)(s & 127);
    p = &MOD->path[idx];
    x0 = cam_x; y0 = cam_y; z0 = cam_z;
    /* 点の間は 2 単位(512)あるので、差 × f を 16bit で掛けると f >= 64 で桁があふれ、カメラが点の中ほどで後ろへ飛んでいた。
     * fmul(差, 2f) = 差 × f / 128 を 32bit の途中結果で求める */
    cam_x = p->x + fmul(p[1].x - p->x, f << 1);
    cam_y = p->y + fmul(p[1].y - p->y, f << 1);
    cam_z = p->z + fmul(p[1].z - p->z, f << 1);
    cam_yaw_path = (u8)(p->yaw + (i8)(((i16)(i8)(p[1].yaw - p->yaw) * f) >> 7));
    cam_pitch_path = (i8)(p->pitch + (i8)(((i16)(i8)(p[1].pitch - p->pitch) * f) >> 7));
    if (dt) { cam_vx = (cam_x - x0) / dt; cam_vy = (cam_y - y0) / dt; cam_vz = (cam_z - z0) / dt; }
    g_fx = SIN(cam_yaw_path);
    g_fz = COS(cam_yaw_path);
    sect_i = (u8)(idx >> 2);
    spd_cur = MOD->sect[sect_i].spd;
}

/* ---- 台本 ---- */
static void script_step(void)
{
    u16 at = path_s >> 6;
    const Stage *m = MOD;
    while (ev_i < m->nev) {
        const Event *e = &m->ev[ev_i];
        if (e->cmd != EV_END && e->at > at) break;
        if (e->cmd == EV_LOOP) {      /* 敵が残っていれば周回。a = 始まり[単位 / 2] */
            u8 i, alive = 0;
            for (i = 0; i < MAX_OBJ; i++) if (obj[i].t >= T_E01 && obj[i].t <= T_E08) alive = 1;
            if (boss_on || alive) {
                loop_b = e->at + 2; loop_len = loop_b - (u16)e->x;
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

static u8 aim_target(void)
{
    u8 ax = (u8)(aim_x >> 2), ay = (u8)(aim_y >> 2), i, best = 0xFF;
    i16 bz = 0x7FFF;
    HitRect *h = hits;
    for (i = 0; i < n_hits; i++, h++) {
        /* 照準の 3×3 ブロックが矩形に重なれば当たる(1 ブロックだけだと遠くの敵に当たらなかった) */
        if (ax + 1 >= h->x0 && ax < h->x1 + 1 && ay + 1 >= h->y0 && ay < h->y1 + 1 && h->z < bz) { bz = h->z; best = h->id; }
    }
    return best;
}

static void auto_input(void)
{
    /* 自動プレイ: 一番手前の敵を狙い、指示が出たら B を押す */
    u8 i, best = 0xFF;
    i16 bz = 0x7FFF;
    HitRect *h = hits;
    in_cur = 0;
    for (i = 0; i < n_hits; i++, h++) {
        const Obj *o = &obj[h->id];
        if (o->t == T_PART && (o->flags & OF_CAPSULE)) continue;
        if (o->t == T_PART && o->group != boss_grp) continue;
        if (h->z < bz) { bz = h->z; best = i; }
    }
    if (best != 0xFF) {
        h = &hits[best];
        aim_x = (u16)(h->x0 + h->x1) * 2;
        aim_y = (u16)(h->y0 + h->y1) * 2;
        if (aim_x < 12) aim_x = 12;
        if (aim_y < 12) aim_y = 12;
        if (aim_y > 148) aim_y = 148;
        in_cur = IN_A;
    }
    if (pr_kind && pr_t < 20) in_cur |= IN_B;
    else if (!pr_kind && lock_n && !(in_prev & IN_B) && !(g_anim & 3)) in_cur |= IN_B;   /* ロックがあれば誘導弾も撃つ(デモと試験) */
}

static void man_start(u8 kind, u8 len)
{
    man_kind = kind; man_t = 0; man_len = len;
}

static u8 lockable(u8 id)
{
    u8 t = obj[id].t;
    return t >= T_E01 && t <= T_E08 || t == T_PART;
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

/* ロックの枠(ブロック。照準を中心に横 LB_W × 縦 LB_H、画面の中に切る)。描くのは overlay_draw */
#define LB_W 24
#define LB_H 16
static u8 lb_x0, lb_y0, lb_x1, lb_y1;

static void lock_scan(void)
{
    u8 ax = (u8)(aim_x >> 2), ay = (u8)(aim_y >> 2), i, k, id;
    HitRect *h = hits;
    lb_x0 = ax > LB_W / 2 ? ax - LB_W / 2 : 0;
    lb_x1 = ax + LB_W / 2 - 1 < 63 ? ax + LB_W / 2 - 1 : 63;
    lb_y0 = ay > LB_H / 2 ? ay - LB_H / 2 : 0;
    lb_y1 = ay + LB_H / 2 - 1 < 39 ? ay + LB_H / 2 - 1 : 39;
    for (i = 0; i < n_hits; i++, h++) {
        if (h->x1 < lb_x0 || h->x0 > lb_x1 || h->y1 < lb_y0 || h->y0 > lb_y1) continue;
        id = h->id;
        if (!lockable(id)) continue;
        for (k = 0; k < lock_n && lock_id[k] != id; k++) ;
        if (k < lock_n) lock_t[k] = LOCK_HOLD;
        else if (lock_n < MAX_LOCK) { lock_id[lock_n] = id; lock_t[lock_n++] = LOCK_HOLD; se_play(SE_LOCK); }
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
    /* 機動の指示に応える(指示が出ている間は B は機動) */
    if (pr_kind) {
        if (b) {
            b = 0;
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
     * 撃っても外さない。外すのは時間切れ・倒した・通り過ぎたとき */
    for (i = 0; i < lock_n; ) {
        if (lock_t[i] <= dt || !lock_keep(lock_id[i])) { lock_drop(i); continue; }
        lock_t[i] -= dt;
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
    for (k = boss_on ? 4 : 10; k >= 0; k--) {   /* 背後の区画は描かない。ボス戦は地形を減らす(8.1) */
        i16 si = (i16)base + k;
        const Sect *s;
        if (si < 0) continue;
        if (loop_b && (u16)si >= (loop_b >> 3)) si -= (i16)(loop_len >> 3);
        if (si >= n) continue;
        s = &s0[si];
        if (!s->mesh) continue;
        pt_cam(s->x, s->y, s->z, &c);
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
        if (o->t == T_PART && !o->yaw && !o->roll) {
            mesh_draw(mesh, &ord_c[id], 0, o->flash ? C_WHITE : 0, id);
        } else {
            mat_yaw(o->yaw, o->roll);
            mesh_draw(mesh, &ord_c[id], g_mm, o->flash ? C_WHITE : 0, id);
        }
    }
}

/* 敵の印: 攻撃してくるもの(敵・敵弾・今のボスの部位)の当たり矩形の四隅に鉤を描く。照準が重なっている敵は赤、補給は緑。
 * 描いた直後の当たり矩形を使うので、照準の色もこのフレームの絵と一致する */
static u8 aim_foe;      /* 照準の下に攻撃してくるものがいる(照準を赤くする) */

static u8 is_foe(const Obj *o)
{
    if (o->t >= T_E01 && o->t <= T_E08) return 1;
    if (o->t >= T_FLAK && o->t <= T_MINE) return 1;
    return o->t == T_PART && o->group == boss_grp && !(o->flags & (OF_CAPSULE | OF_DECOR | OF_HIDDEN));
}

static void marks_draw(void)
{
    u8 i, tgt = aim_target();
    HitRect *h = hits;
    aim_foe = tgt != 0xFF && is_foe(&obj[tgt]);
    for (i = 0; i < n_hits; i++, h++) {
        const Obj *o = &obj[h->id];
        if (!o->t) continue;
        if (is_foe(o)) {                   /* 照準が重なっているか、ロックしている敵は赤 */
            u8 k;
            for (k = 0; k < lock_n && lock_id[k] != h->id; k++) ;
            g_color = h->id == tgt || k < lock_n ? C_RED : C_WHITE;
        }
        else if (o->t == T_SUPPLY || o->t == T_MEDIC) g_color = C_GREEN;
        else continue;
        g_rx = (u8)(h->x0 - 1); g_ry = (u8)(h->y0 - 1); g_rw = h->x1; g_rh = h->y1;
        marks4();
    }
}

static void spr_set(u8 n, i16 x, i16 y, u8 pat, u8 col)
{
    u8 *a = &g_spr_attr[n * 4];
    if (y < -16 || y > 143) { a[0] = 209; return; }
    a[0] = (u8)(y - 1); a[1] = (u8)x; a[2] = (u8)(pat * 4); a[3] = col;
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
    if (g_cfg.fps) {
        extern u16 g_perf_frame;
        extern u8 g_perf_ticks;
        num_draw(0, 34, g_perf_ticks, 2, C_WHITE);
        num_draw(10, 34, g_perf_frame >> 8, 3, C_WHITE);
    }
    if (!scene && g_scene == 1) lock_box_draw();
    /* 照準(スプライト 0) */
    if (scene) { spr_set(0, 0, 200, 0, 2); g_spr_attr[0] = 209; }
    else spr_set(0, (i16)aim_x - 16, (i16)aim_y - 16, 0,
                 over_t ? ((g_anim & 1) ? C_RED : C_WHITE) : aim_foe ? C_RED : C_WHITE);   /* 敵に重なると赤(撃てば当たる・ロックできる) */
    g_spr_attr[4] = 209; g_spr_attr[8] = 209; g_spr_attr[12] = 209;   /* スプライト 1〜3 は使わない(ロックは敵の印を赤くして示す) */
}

static void lerp_pal(const u8 *a, const u8 *b, u8 k, u8 *o)   /* k = 0..16 */
{
    u8 i;
    for (i = 0; i < 14; i += 2) {
        u8 r0 = a[i] >> 4, b0 = a[i] & 7, g0 = a[i + 1], r1 = b[i] >> 4, b1 = b[i] & 7, g1 = b[i + 1];
        u8 r = (u8)(r0 + (((i16)r1 - r0) * k >> 4));
        u8 bl = (u8)(b0 + (((i16)b1 - b0) * k >> 4));
        u8 g = (u8)(g0 + (((i16)g1 - g0) * k >> 4));
        o[i] = (u8)((r << 4) | bl);
        o[i + 1] = g;
    }
}

/* ---- 1 面 ---- */
static void stage_reset(void)
{
    u8 i;
    for (i = 0; i < MAX_OBJ; i++) obj[i].t = T_NONE;
    for (i = 0; i < MAX_LASER; i++) laser[i].kind = 0xFF;
    for (i = 0; i < MAX_FX; i++) fx[i].t = 0;
    path_s = 0; ev_i = 0; scr_end = 0; loop_b = 0;
    g_space = MOD->flags & SF_SPACE; g_fade = 0; g_shake = 0;
    boss_on = 0; boss_dead = 0; boss_grp = 0;
    mis_left = MIS_MAX;                /* 誘導弾は面ごとに満タン */
    pr_kind = 0; man_t = 0; man_len = 0; inv_t = 0; env_rt = 0; env_roll = 0; lock_n = 0; cam_spin = 0;
    cap_t = 0; heat_t = 0; over_t = 0;
    n_hits = 0;
    aim_x = 128; aim_y = 80;
    path_max = (u16)(MOD->npath - 2) << 7;
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
    u16 t0, t_demo;
    mod_load_now(mod);
    stage_reset();
    g_scene = (MOD->flags & SF_SCENE) ? 3 : 1;
    set_stage_palette(MOD->pal);
    cockpit_mode(g_scene == 3);
    cockpit_reset();
    if (MOD->clock) g_clock = MOD->clock;
    if (MOD->bgm) bgm_play(MOD->bgm);
    if (g_scene == 1) {
        caption(MOD->name + 10, C_WHITE, 120);   /* 「STAGE n / 」を除く。字幕は 16 文字まで */
    }
    t0 = g_tick;
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
            if (g_auto) auto_input();
            aim_poll();
            fire_step(dt);
        }
        path_step(dt);
        script_step();
        if (g_fade) {                      /* エンディング: 再突入の色へ移り、白く光って朝の町へ */
            lerp_pal(MOD->pal, MOD->pal2, g_fade >> 1, pal_w);
            vdp_set_palette(9, pal_w);
            if ((g_fade += g_an) > 32) { g_fade = 0; g_space = 0; set_stage_palette(MOD->pal2); }
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
        obj_step(dt);
        if (boss_on) boss_step(dt);
        {
            extern u16 g_perf_frame;
            u16 t = timer_read();
            g_perf_polys = 0; g_perf_verts = 0;
            g_spr_live = 1;                /* 描画の間は VDP に触らない。照準は割り込みが書く */
            sky_draw(g_space);
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
        g_alt_show = (u8)(cam_y >> 8);
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
        if (boss_dead == 1) {
            boss_dead = 2;
            caption("STAGE CLEAR!", C_WHITE, 120);
        }
    }
    g_hiscore = g_score > g_hiscore ? g_score : g_hiscore;
    return 1;
}

/* ---- 継ぎ目(指示書 7.2): 海の上を飛びながら時刻の色を移し、次の面のセグメントへ切り替える。多角形は 6 枚以下 ---- */
void seam_run(u8 from, u8 to)
{
    static u8 pa[14], pb[14], pc[14];
    static const u8 cloud_rect[] = { 0x90, 0xF8, 0x70, 0x08, C_CLOUD, 0, 0xB0, 0x00, 0x50, 0x10, C_CLOUD, 0 };
    u8 i;
    u16 t;
    (void)from;
    for (i = 0; i < 14; i++) pa[i] = MOD->pal[i];
    mod_next_begin(to);
    g_scene = 2;
    cam_x = cam_y = cam_z = 0; cam_yaw = 0; cam_pitch = 0; cam_roll = 0;
    cam_update();
    n_hits = 0;
    g_spr_attr[0] = 209; g_spr_attr[4] = 209; g_spr_attr[8] = 209; g_spr_attr[12] = 209;
    bgm_play(SONG_BRIDGE);
    for (t = 0; t < 300; t++) {   /* 15 秒 */
        g_frames++;
        /* 1 フレームに 1KB ずつ読み、読み終えたら切り替える(7.2)。常駐部とページ0だけで動くのでセグメントを替えても続く */
        if (t < 18) {
            if (t < 16) mod_next_step();
            else if (t == 16) {            /* 16KB 読み終えたので 1 回だけ切り替える */
                mod_next_use();
                for (i = 0; i < 14; i++) pb[i] = MOD->pal[i];
                if (MOD->clock) g_clock = MOD->clock;
            }
            sky_draw(0);
            present();
            continue;
        }
        if (t <= 100 && !(t & 3)) { lerp_pal(pa, pb, (u8)(t >> 2 > 16 ? 16 : t >> 2), pc); vdp_set_palette(9, pc); }
        sky_draw(MOD->flags & SF_SPACE);
        /* 雲のビルボード 5 個 */
        for (i = 0; i < 5; i++) {
            V3 c;
            c.x = (i16)(i * 53 - 106) << 8;
            c.y = (i16)(i & 1 ? -6 : -3) << 8;
            c.z = 0x7000 - (i16)((t * 16 + (u16)i * 0x1600) & 0x6FFF);
            if (c.z < 0x0400) continue;
            g_dm_rects = cloud_rect; g_dm_n = 2; g_dm_flash = 0; g_dm_id = 0; g_dm_hit = 0; g_dm_grow = 0; g_dm_thin = 0; g_dm_deco = 1;
            draw_model(&c);
        }
        if (t > 110 && t < 180) { text_center(10, MOD->name + 10, C_WHITE, 1); }
        if (t == 200) pcm_say(to == 6 ? VOICE_SEE : VOICE_HURRY);
        if (t > 200 && t < 280) text_center(1, MOD->str[0], C_WHITE, 1);
        present();
        if (input_raw() & IN_B && t > 30) t = 299;
    }
    set_stage_palette(MOD->pal);
}
