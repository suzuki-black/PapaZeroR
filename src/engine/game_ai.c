/* game_ai.c — 敵・弾・レーザー・ボスの動き(指示書 5・6 章)
 *
 * ページ0に入り切らないので、全部のモジュールの後ろ(0xA400-、エリア HICODE。tools/mkrom.py が各モジュールへ重ねる)に置く。
 * ここから ROM を読み込む処理は呼ばない(読み込むとコード自身を上書きする)。
 */
#include "game_int.h"

const LaserDef ldef[5] = {
    { C_ORANGE, 120, 30, 2, 6, 2, 3 },     /* 化学 */
    { C_GREEN,   30, 24, 1, 3, 1, 99 },    /* 固体(撃って止める時間がない) */
    { C_CYAN,    60, 90, 1, 2, 1, 4 },     /* ファイバー(横に掃く) */
    { C_WHITE,  180, 60, 4, 21, 3, 6 },    /* 自由電子 */
    { C_PURPLE,  90, 40, 2, 8, 3, 99 },    /* 超電磁(止められない) */
};
/* 弾を撃つ: 物体 t を (x, y, z) から tm ティックでカメラへ */
void shot(u8 t, i16 x, i16 y, i16 z, u8 tm)
{
    Obj *o = obj_new(t);
    if (!o) return;
    o->x = x; o->y = y; o->z = z; o->tm = tm;
}

void laser_start(u8 owner, u8 kind)
{
    u8 i;
    Laser *l = laser;
    if (kind >= 5) return;
    for (i = 0; i < MAX_LASER; i++, l++) {
        if (l->kind != 0xFF && l->owner == owner) return;
    }
    l = laser;
    for (i = 0; i < MAX_LASER; i++, l++) if (l->kind == 0xFF) {
        l->owner = owner; l->kind = kind; l->st = 0; l->t = ldef[kind].charge; l->mhp = ldef[kind].mhp;
        se_play(SE_ALARM);
        if (!pr_kind) { pr_kind = PR_ROLL; pr_t = l->t > 90 ? 90 : l->t; pcm_say(VOICE_ROLL); }
        return;
    }
}

/* ---- ボス(指示書 6 章): 定義のバイト列から部位の物体を作る ---- */
/* 定義: 動き, 距離, 部位数, (メッシュ, ox, oy, oz, 耐久, 組, flags, 攻撃) × n。攻撃: 0 なし、1 砲弾、0x10 + k レーザー k */
void boss_begin(void)
{
    const u8 *d = MOD->boss;
    u8 n, i;
    boss_on = 1; boss_dead = 0; boss_t = 0; boss_grp = 0; boss_intro = 180;
    boss_mov = d[0]; boss_dist = d[1];
    n = d[2];
    d += 3;
    for (i = 0; i < n; i++, d += 8) {
        Obj *o = obj_new(T_PART);
        if (!o) break;
        o->mesh = d[0]; o->ox = (i8)d[1]; o->oy = (i8)d[2]; o->oz = (i8)d[3];
        o->hp = d[4]; o->group = d[5]; o->flags = d[6]; o->ax = (i8)d[7];
    }
    caption("WARNING!", C_RED, 150);
    pcm_say(VOICE_WARNING);
    bgm_play(g_mod == 6 ? SONG_KING1 : SONG_BOSS);
    se_play(SE_ALARM);
}

void boss_step(u8 dt)
{
    u8 i, alive = 0, grp_left = 0, any = 0;
    Obj *o;
    i16 sy, cy;                     /* ボスの向き */
    /* 動き: 0 = カメラの前 dist 単位に留まる。1 = 世界に固定 */
    if (boss_mov == 0) {
        i16 d = (i16)boss_dist << 8;
        i16 tx = cam_x + fmul(g_fx, d), tz = cam_z + fmul(g_fz, d);
        /* カメラの動きを先に足してから寄せる(寄せるだけだと速いほど遅れて近づき、大きく描かれて重くなる) */
        boss_x += cam_vx * dt; boss_z += cam_vz * dt;
        boss_x += (tx - boss_x) >> 3;
        boss_y = boss_y0 + (SIN((u8)(g_anim << 2)) >> 1);
        boss_z += (tz - boss_z) >> 3;
    }
    /* ボスはカメラの進む向きに合わせて回す。部位の位置を世界に固定すると、周回で視線が逆を向いたときに左右も前後も入れ替わる */
    boss_yaw = cam_yaw_path;
    if (boss_intro) {
        boss_intro = boss_intro > dt ? boss_intro - dt : 0;
        if (!boss_intro && g_mod == 6) bgm_play(SONG_KING2);
    }
    boss_t += dt;
    sy = SIN(boss_yaw); cy = COS(boss_yaw);
    for (i = 0, o = obj; i < MAX_OBJ; i++, o++) {
        if (o->t != T_PART) continue;
        {
            i16 lx = (i16)o->ox << 8, ly = (i16)o->oy << 8, lz = (i16)o->oz << 8;
            if (o->flags & OF_SPIN) {      /* 風車のように回る(ムスタング・ヒュドラ) */
                u8 a = (u8)(g_anim << 1);
                i16 s = SIN(a), c = COS(a);
                lx = o->ox * c - o->oy * s;
                ly = o->ox * s + o->oy * c;
                o->roll = a;
            }
            o->x = boss_x + fmul(lx, cy) + fmul(lz, sy);
            o->y = boss_y + ly;
            o->z = boss_z - fmul(lx, sy) + fmul(lz, cy);
            o->yaw = boss_yaw;
        }
        any = 1;
        if (!(o->flags & (OF_CAPSULE | OF_DECOR))) {
            alive = 1;
            if (o->group == boss_grp) grp_left = 1;
        }
        if (o->group == boss_grp && (o->flags & OF_WEAK) && !(g_anim & 2)) o->flash = 1;
    }
    if (!any) alive = 0;
    if (alive && !grp_left) { boss_grp++; }
    if (!alive && boss_on) {
        for (i = 0, o = obj; i < MAX_OBJ; i++, o++) {
            if (o->t == T_PART) {          /* 部位を 1 つずつ落とす(6.2)。ヒナのカプセルだけ残す */
                fx_add(o->x, o->y, o->z, 1);
                o->t = T_PROP; o->tm = (u8)(50 + i * 6); o->st = 0; o->vy = 0;
                o->ptn = (o->flags & OF_CAPSULE) ? P_NONE : P_FALL;
            }
            else if (o->t >= T_FLAK && o->t <= T_MINE) o->t = T_NONE;
        }
        for (i = 0; i < MAX_LASER; i++) laser[i].kind = 0xFF;
        boss_on = 0; boss_dead = 1;
        se_play(SE_BOSS);
        mis_left = MIS_MAX;
        g_score += (u16)g_mod * 500;
        bgm_play(SONG_CLEAR);
        caption(MOD->str[1], C_WHITE, 170);
        return;
    }
    if (boss_intro) return;
    /* 攻撃: 約 2 秒ごとに、今の組の攻撃できる部位から順に */
    if (boss_t >= 120) {
        u8 pick = rnd() & 15;
        boss_t = 0;
        for (i = 0, o = obj; i < MAX_OBJ; i++, o++) {
            u8 k = (u8)(i + pick) % MAX_OBJ;
            Obj *q = &obj[k];
            if (q->t != T_PART || !q->ax) continue;
            if ((u8)q->ax == 1) shot(T_FLAK, q->x, q->y, q->z, 75);
            else if ((u8)q->ax == 2) shot(T_MISSILE, q->x, q->y, q->z, 90);
            else laser_start(k, (u8)q->ax & 15);
            break;
        }
    }
}

/* ---- 敵 ---- */
void obj_step(u8 dt)
{
    u8 i;
    Obj *o = obj;
    for (i = 0; i < MAX_OBJ; i++, o++) {
        u8 t = o->t;
        i16 dx, dy, dz;
        if (!t) continue;
        o->flash = o->flash > g_an ? o->flash - g_an : 0;
        if (t == T_FLAK || t == T_MISSILE || t == T_MYMIS) {
            /* 残りティックで目標へ近づく。弾はカメラへ、誘導弾は目標へ */
            i16 tx = cam_x, ty = cam_y, tz = cam_z;
            u8 rem = o->tm;
            if (t == T_MYMIS) {
                Obj *g;
                if (o->tgt == 0xFF) { mis_straight(o, dt); continue; }   /* ロックせずに撃った(game.c) */
                g = &obj[o->tgt];
                if (!g->t) { o->t = T_NONE; continue; }
                tx = g->x; ty = g->y; tz = g->z;
            }
            if (rem <= dt) {
                if (t == T_MYMIS) { obj_damage(&obj[o->tgt], 3); }
                else damage(t == T_MISSILE ? 2 : 1);
                o->t = T_NONE;
                continue;
            }
            o->x += muldiv(tx - o->x, dt, rem);
            o->y += muldiv(ty - o->y, dt, rem);
            o->z += muldiv(tz - o->z, dt, rem);
            o->tm = (u8)(rem - dt);
            continue;
        }
        if (t == T_PART) continue;
        dx = cam_x - o->x; dy = cam_y - o->y; dz = cam_z - o->z;
        /* 通り過ぎた(前方の内積が負で 10 単位以上) */
        {
            i16 fwd = fmul(g_fx, -dx) + fmul(g_fz, -dz);   /* 視線ではなく進む向きで測る(宙返りの間も変わらない) */
            if (o->ptn != P_TAIL && fwd < -0x0A00) { o->t = T_NONE; continue; }
            o->st += dt;
            /* 撃つ間隔(ティック)は、速さを 2 倍にしたときに約 1.5 倍へ延ばした。st は u8 で dt <= 8 なので 240 までにする */
            switch (o->ptn) {
            case P_PARALLEL:
                /* 自機と同じ速さで並走し、左右に振れる */
                o->x += cam_vx * dt + (g_fz >> 6) * (SIN(o->tm) >> 6) * dt;
                o->z += cam_vz * dt - (g_fx >> 6) * (SIN(o->tm) >> 6) * dt;
                o->yaw = cam_yaw_path;
                o->tm += 2 * dt;
                if (o->st >= 225) {
                    o->st = 0;
                    if (fwd > 0x0400) shot(T_FLAK, o->x, o->y, o->z, 80);
                    if (++o->roll >= 3) { o->t = T_NONE; break; }    /* 3 回撃ったら道をそれて消える */
                }
                break;
            case P_HOLD:
                o->yaw = cam_yaw_path;              /* モデルの正面は -z。進む向きと同じヨーでカメラのほうを向く */
                if (t == T_E03 && o->st >= 240 && fwd > 0x1000 && fwd < 0x4000) { o->st = 0; laser_start(i, 0); }
                else if (t == T_E08 && o->st >= 240 && fwd > 0x1000 && fwd < 0x5000) { o->st = 0; laser_start(i, 3); }
                else if ((t == T_E02) && o->st >= 180 && fwd > 0x0C00 && fwd < 0x5000) { o->st = 0; shot(T_FLAK, o->x, o->y, o->z, 70); }
                break;
            case P_PASS:
                /* 正面からまっすぐ来る */
                o->x -= (g_fx >> 2) * dt >> 1;
                o->z -= (g_fz >> 2) * dt >> 1;
                o->yaw = cam_yaw_path;
                if (o->st >= 150 && fwd < 0x5000 && fwd > 0x1000) {
                    o->st = 0;
                    if (t == T_E06) shot(T_MISSILE, o->x, o->y, o->z, 90);
                    else if (rnd() & 1) laser_start(i, 1);
                    else shot(T_FLAK, o->x, o->y, o->z, 60);
                }
                break;
            case P_TAIL:
                /* 後ろ 30 単位に付く。LOOP! の指示を出し、失敗すると 2 秒ごとに機銃 */
                if (o->st < 200) {
                    o->x -= (g_fx >> 2) * dt >> 1;
                    o->z -= (g_fz >> 2) * dt >> 1;
                    o->yaw = cam_yaw_path;
                } else {
                    i16 d = -0x1E00;
                    o->x = cam_x + fmul(g_fx, d) + (SIN(o->tm) >> 1);
                    o->y = cam_y;
                    o->z = cam_z + fmul(g_fz, d);
                    o->tm += dt;
                    if (o->st == 200 || (o->st >= 200 && o->st < 203)) {
                        if (!pr_kind) { pr_kind = PR_LOOP; pr_t = 120; pcm_say(VOICE_LOOP); se_play(SE_ALARM); }
                        o->st = 204;
                    }
                    if (o->st >= 250) { o->st = 204; damage(1); }
                }
                break;
            case P_CROSS:
                /* ゆっくり横切る。中央で溜めて撃つ */
                o->x += (g_fz >> 4) * dt >> 2;                 /* 右へ = (fz, -fx) */
                o->z -= (g_fx >> 4) * dt >> 2;
                o->yaw = (u8)(cam_yaw_path - 64);              /* 機首(-z)を右へ */
                if (o->st >= 240 && fwd < 0x6000) { o->st = 0; laser_start(i, 2); }
                break;
            case P_DRIFT:
                o->x += SIN(o->tm) >> 5;
                o->y += COS(o->tm) >> 5;
                o->tm += dt;
                if (fwd < 0x0400 && fwd > -0x0200) { damage(1); fx_add(o->x, o->y, o->z, 1); o->t = T_NONE; }
                break;
            case P_FALL:                       /* ボスの破片: 回りながら落ちて消える */
                o->x += cam_vx * dt; o->z += cam_vz * dt;
                o->vy += (i16)dt * 3;
                o->y -= o->vy;
                o->roll += (u8)(dt * 6);
                if (o->tm <= dt) { fx_add(o->x, o->y, o->z, 0); o->t = T_NONE; } else o->tm -= dt;
                break;
            case P_LIFT:                       /* 場面: ヒナが吊り上げられる */
                if (o->st > 90) o->y += (i16)dt << 3;
                break;
            case P_BOUNCE:
                o->yaw = cam_yaw_path;
                /* 上へ抜けて、3 秒後に上から戻る */
                if (o->st < 90) o->y += 0x40 * dt;
                else if (o->st < 180) { o->x += cam_vx * dt; o->z += cam_vz * dt; }
                else {
                    o->y -= 0x40 * dt;
                    o->x += cam_vx * dt; o->z += cam_vz * dt;
                    if (o->st >= 250) { o->st = 0; if (fwd > 0) shot(T_MISSILE, o->x, o->y, o->z, 90); }
                }
                break;
            }
        }
    }
    /* レーザー */
    {
        Laser *l = laser;
        for (i = 0; i < MAX_LASER; i++, l++) {
            const LaserDef *d;
            if (l->kind == 0xFF) continue;
            d = &ldef[l->kind];
            if (!obj[l->owner].t) { if (l->st == 0) g_score += 30; l->kind = 0xFF; continue; }
            if (l->t > dt) { l->t -= dt; continue; }
            if (l->st == 0) { l->st = 1; l->t = d->fire; se_play(SE_LASER); damage(d->dmg); }
            else l->kind = 0xFF;
        }
    }
}

/* レーザーの描画(game.c の描画から呼ぶ。ページ 0 に空きが無いのでこちらに置く) */
void lasers_draw(void)
{
    u8 i;
    Laser *l = laser;
    for (i = 0; i < MAX_LASER; i++, l++) {
        const LaserDef *d;
        const Obj *o;
        V3 c;
        i16 sx, sy;
        if (l->kind == 0xFF) continue;
        d = &ldef[l->kind];
        o = &obj[l->owner];
        pt_cam(o->x, o->y, o->z, &c);
        if (!pt_screen(&c, &sx, &sy)) continue;
        if (l->st == 0) {
            /* 溜め: 発射口の点滅 */
            if (g_anim & 1) {
                i16 x = sx >> 4, y = sy >> 4;
                if (x >= 1 && x < 62 && y >= 1 && y < 38) { g_rx = (u8)(x - 1); g_ry = (u8)(y - 1); g_rw = 3; g_rh = 3; g_color = d->color; rect_fill(); }
            }
            if (l->kind == 3 && (g_anim & 2)) { /* 自由電子: 画面全体が白く脈打つ */
                g_rx = 0; g_ry = 0; g_rw = 64; g_rh = 1; g_color = C_WHITE; rect_fill();
                g_ry = 39; rect_fill();
            }
        } else {
            i16 ex = 512, ey = 630;
            if (l->kind == 2) ex = 512 + (SIN((u8)(g_anim * 8)) >> 0);   /* ファイバー: 掃く */
            if (sx < -2000 || sx > 3000 || sy < -2000 || sy > 3000) continue;
            band_draw(sx, sy, ex, ey, d->w0, d->w1, d->color);
        }
    }
}
