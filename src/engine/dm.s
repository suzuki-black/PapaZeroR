; dm.s — 矩形の集まりの敵モデルを描き、当たり判定の表に足す(LOD 2。COASTER HOME RUN の geom.s の draw_model)

	.module	dm
	.r800
	.include "r800.inc"

	.area	_CODE
; ---------------------------------------------------------------------------
; void draw_model(const V3 *c)   HL = モデルの足元(カメラ空間、z >= NEAR_Z + 32)
;   敵モデル = カメラ正対の矩形の集まり(仕様書 7.4)。g_dm_rects の g_dm_n 個の矩形
;   (x0, y0, x1, y1: 1/16m、色、部位)を、足元を投影した位置から z に反比例した大きさで塗る。
;   g_dm_flash が 0 以外ならその色で塗る(被弾・予備動作の点滅)。
;   g_dm_hit が 0 以外なら、塗った矩形を当たり判定の表 hits(game.c)に g_dm_id として足す。
;   g_dm_thin: 幅か高さ(1/16m)がこれ以下の矩形は描かない(当たり判定にも足さない)。game.c が (z - 1) >> 10 を入れる
;   = 画面で半ブロックに満たない部品(四捨五入で出たり消えたりする細い部品)を、遠くでは省く。4m より手前は 0(全部描く)
;   g_dm_grow が 0 以外なら、各矩形を上下左右に 1 ブロック広げて塗る(縁取り: 先に g_dm_flash = 縁の色で広げて塗り、
;   その上に普通に塗ると、絵の外周だけが縁の色で残る)。
;   部位 3(飾り: 目・模様・刃先など、ほかの矩形の内側の細部)は縁取りの回に塗らず、当たり判定の表にも足さない
;   (1 回塗るだけ。当たり判定の表 48 個も使わない)。g_dm_deco が 0 なら飾りは描かない(遠い敵。1 ブロックに満たない細部が
;   四捨五入で出たり消えたりして、ちらつく染みに見える)。
;   1/16m あたりの画面量 k = 2^21 / z は、投影で求めた p_q(= 2^23 / z)を 4 で割るだけ(割り算なし)。
; ---------------------------------------------------------------------------
	.globl	_project2, _rect_fill, _p_q
	.globl	_g_color, _g_rx, _g_ry, _g_rw, _g_rh
	.globl	_hits, _n_hits

MAX_HIT	= 48

	.area	_DATA
_g_dm_rects::	.ds	2
_g_dm_n::	.ds	1
_g_dm_flash::	.ds	1
_g_dm_id::	.ds	1
_g_dm_hit::	.ds	1
dm_h1:		.ds	1	; 1 = この物体の矩形をまだ当たり判定の表に入れていない
_g_dm_grow::	.ds	1
_g_dm_thin::	.ds	1
_g_dm_deco::	.ds	1	; 0 以外なら飾り(部位 3)も描く(game.c が近い敵だけ 1 にする)
dm_c:		.ds	2
dm_sx:		.ds	2
dm_sy:		.ds	2
DM_CMAX = 24			; 座標の表に入る矩形の数(モデルは最大 18)
dm_mode:	.ds	1	; 0 = 求める、1 = 求めて表に書く(縁取りの回)、2 = 表を使う(縁取りの直後の回)
dm_cv:		.ds	1	; 1 = 表が直前の縁取りの回のもの
dm_cc:		.ds	2	; 表を書いたときの足元の点と矩形の列
dm_cr:		.ds	2
dm_cache:	.ds	DM_CMAX * 4	; 矩形ごとの x0, x1, y0, y1(ブロック、広げる前)

	.area	_CODE

; dm_cx: A = x(1/16m、符号付き)→ A = clamp((sx + scale(x) + 7) >> 4, 0, 64)
; dm_cy: A = y(1/16m、符号付き)→ A = clamp((sy - scale(y) + 7) >> 4, 0, 46)
;   scale(v) = (|v| * k) >> 8 に v の符号を付けたもの(k = 1/16m あたりの画面量)。k・sx・sy は draw_model が
;   命令の即値(dm_k_i・dm_sx_i・dm_sy_i)に書く(メモリの変数を読まない)。BC・DE・HL を壊す
;   (値ごとに結果を覚えて使い回す形も試したが、覚える・戻す手間のほうが重く、ステージ 3 で +0.6ms だった)
dm_cx:
	call	dm_sc
dm_sx_i:
	ld	de, #0			; sx(draw_model が書く)
	add	hl, de
	ld	c, #64
	jr	dm_blk
dm_cy:
	call	dm_sc
	ex	de, hl
dm_sy_i:
	ld	hl, #0			; sy(draw_model が書く)
	or	a, a
	sbc	hl, de
	ld	c, #40
; HL(画面座標 12.4)→ A = clamp((HL + 7) >> 4, 0, C)。0 <= HL + 7 < 1024 なら (HL + 7) << 4 の上位バイトが答え
dm_blk:
	ld	de, #7
	add	hl, de
	bit	7, h
	jr	nz, 1$
	ld	a, h
	cp	a, #4
	jr	nc, 2$			; 1024 以上 = 64 ブロック以上
	add	hl, hl
	add	hl, hl
	add	hl, hl
	add	hl, hl
	ld	a, h
	cp	a, c
	ret	c
2$:
	ld	a, c
	ret
1$:
	xor	a, a
	ret
; dm_sc: A = v → HL = scale(v)
dm_sc:
	ld	d, a			; D = v(符号)
	bit	7, a
	jr	z, 1$
	neg
1$:
dm_k_i:
	ld	hl, #0			; k(draw_model が書く)
	inc	h
	dec	h
	jr	nz, 2$
	; 拡大率が 256 未満なら 8×8 の MULUB(14 サイクル。MULUW は 36)。積は 16bit に収まり、結果は同じ
	ld	e, l
	MULUB_A_E			; HL = A * E
	ld	l, h
	ld	h, #0
	jr	3$
2$:
	ld	c, a
	ld	b, #0
	ld	a, d
	ex	af, af'			; MULUW は DE を壊すので v を裏の A に(割り込み処理は裏のレジスタを使わない)
	MULUW_HL_BC			; DE:HL
	ld	l, h
	ld	h, e
	ex	af, af'
	ld	d, a
3$:
	bit	7, d
	ret	z
	xor	a, a
	sub	a, l
	ld	l, a
	sbc	a, a
	sub	a, h
	ld	h, a
	ret

_draw_model::
	push	ix
	push	iy
	ld	(dm_c), hl
	; 縁取りの回(広げて塗る)と直後の普通の回は、同じ敵の同じ矩形なので、座標を表で使い回す
	ld	a, (_g_dm_grow)
	or	a, a
	jr	z, 40$
	ld	a, (_g_dm_n)
	cp	a, #DM_CMAX + 1
	ld	a, #0
	jr	nc, 41$
	ld	(dm_cc), hl
	ld	hl, (_g_dm_rects)
	ld	(dm_cr), hl
	ld	a, #1
	jr	41$
40$:
	ld	a, (dm_cv)
	or	a, a
	jr	z, 41$			; A = 0
	ld	de, (dm_cc)
	or	a, a
	sbc	hl, de
	ld	a, #0
	jr	nz, 41$
	ld	hl, (_g_dm_rects)
	ld	de, (dm_cr)
	or	a, a
	sbc	hl, de
	jr	nz, 41$
	ld	a, #2
41$:
	ld	(dm_mode), a
	ld	b, a
	xor	a, a
	bit	0, b
	jr	z, 42$
	inc	a
42$:
	ld	(dm_cv), a		; 縁取りの回だけ、次の回のために表を残す
	ld	a, b
	cp	a, #2
	jr	z, 43$			; 中心の投影と拡大率は前の回のまま
	ld	hl, (dm_c)
	ld	de, #dm_sx		; dm_sx, dm_sy は連続
	call	_project2
	ld	hl, (_p_q)
	srl	h
	rr	l
	srl	h
	rr	l
	ld	(dm_k_i + 1), hl	; 座標の計算(dm_cx / dm_cy)の即値に書く
	ld	hl, (dm_sx)
	ld	(dm_sx_i + 1), hl
	ld	hl, (dm_sy)
	ld	(dm_sy_i + 1), hl
43$:
	; 当たり判定の表の書き先(IY = hits + n_hits * 7)と、奥行き・番号(矩形ごとに書く即値)は 1 体につき 1 回だけ用意する
	ld	a, (_g_dm_hit)
	or	a, a
	jr	z, 52$
	ld	(dm_h1), a
	ld	a, (_n_hits)
	ld	l, a
	ld	h, #0
	ld	d, h
	ld	e, l
	add	hl, hl
	add	hl, hl
	add	hl, hl
	or	a, a
	sbc	hl, de			; * 7
	ld	de, #_hits
	add	hl, de
	push	hl
	pop	iy
	ld	hl, (dm_c)
	ld	de, #4
	add	hl, de
	ld	a, (hl)
	ld	(55$ + 3), a		; z の下位
	inc	hl
	ld	a, (hl)
	ld	(56$ + 3), a		; z の上位
	ld	a, (_g_dm_id)
	ld	(57$ + 3), a
52$:
	; 矩形の x0, x1, y0, y1(ブロック)は裏の B, C, D, E に置く。裏の HL = 座標の表(縁取りの回と次の回で使い回す)。
	; 座標の計算(dm_cx / dm_cy)・塗り(rect_fill)・広げる(dm_grow1)は裏のレジスタを使わない(割り込み処理も使わない)
	exx
	ld	hl, #dm_cache
	exx
	ld	ix, (_g_dm_rects)
	ld	a, (_g_dm_n)
	ld	b, a
1$:
	push	bc
	; 飾り(部位 3)は g_dm_deco が 0(遠い敵)なら飛ばす。縁取りの回と次の回で同じに決まるので、座標の表はずれない
	ld	a, 5 (ix)
	cp	a, #3
	jr	nz, 48$
	ld	a, (_g_dm_deco)
	or	a, a
	jp	z, 8$
48$:
	; 細い部品(幅か高さが g_dm_thin 以下)は飛ばす。縁取りの回と次の回で同じに決まるので、座標の表はずれない
	ld	a, 2 (ix)
	sub	a, 0 (ix)
	ld	c, a			; C = 幅
	ld	a, 3 (ix)
	sub	a, 1 (ix)		; A = 高さ
	cp	a, c
	jr	c, 46$
	ld	a, c
46$:
	ld	hl, #_g_dm_thin
	cp	a, (hl)
	jp	z, 8$
	jp	c, 8$
	ld	a, (dm_mode)
	cp	a, #2
	jr	nz, 44$
	; 表から
	exx
	ld	b, (hl)
	inc	hl
	ld	c, (hl)
	inc	hl
	ld	d, (hl)
	inc	hl
	ld	e, (hl)
	inc	hl
	jp	45$
44$:
	; 左右 = sx + scale(x0 / x1)、上下 = sy - scale(y1 / y0)
	ld	a, 0 (ix)
	call	dm_cx
	exx
	ld	b, a
	exx
	ld	a, 2 (ix)
	call	dm_cx
	exx
	ld	c, a
	exx
	ld	a, 3 (ix)
	call	dm_cy
	exx
	ld	d, a
	exx
	ld	a, 1 (ix)
	call	dm_cy
	exx
	ld	e, a
	ld	a, (dm_mode)
	or	a, a
	jr	z, 45$
	; 縁取りの回: 表に書く
	ld	(hl), b
	inc	hl
	ld	(hl), c
	inc	hl
	ld	(hl), d
	inc	hl
	ld	(hl), e
	inc	hl
45$:
	; 飾り(部位 3: 目・模様・刃先など、ほかの矩形の内側の細部)は縁取りの回には塗らない(座標は上で表に書いてある)
	ld	a, 5 (ix)
	cp	a, #3
	jr	nz, 47$
	ld	a, (_g_dm_grow)
	or	a, a
	jp	nz, 58$
47$:
	; 空なら次へ(ここは裏のレジスタのまま)
	ld	a, c
	sub	a, b
	jp	z, 58$
	jp	c, 58$
	ld	(_g_rw), a
	ld	a, b
	ld	(_g_rx), a
	ld	a, e
	sub	a, d
	jp	z, 58$
	jp	c, 58$
	ld	(_g_rh), a
	ld	a, d
	ld	(_g_ry), a
	exx
	ld	a, (_g_dm_grow)
	or	a, a
	jr	z, 30$
	ld	hl, #_g_rx
	ld	de, #_g_rw
	ld	c, #64
	call	dm_grow1
	ld	hl, #_g_ry
	ld	de, #_g_rh
	ld	c, #40
	call	dm_grow1
30$:
	ld	a, (_g_dm_flash)
	or	a, a
	jr	nz, 2$
	ld	a, 4 (ix)
2$:
	ld	(_g_color), a
	call	_rect_fill
	; 当たり判定の表へ(x0, y0, x1, y1, z, id)。飾りは足さない(ほかの矩形の内側なので、当たりは変わらない)。
	; 1 体につき 1 つ: 2 枚目からは最初の矩形を広げる(矩形ごとに足すと、1 体に名前の札と印が 3〜4 個付いた)
	ld	a, (_g_dm_hit)
	or	a, a
	jr	z, 8$
	ld	a, 5 (ix)
	cp	a, #3
	jr	z, 8$
	ld	a, (dm_h1)
	or	a, a
	jr	z, 70$
	ld	a, (_n_hits)
	cp	a, #MAX_HIT
	jr	nc, 8$
	inc	a
	ld	(_n_hits), a
	xor	a, a
	ld	(dm_h1), a
	exx
	ld	0 (iy), b
	ld	1 (iy), d
	ld	2 (iy), c
	ld	3 (iy), e
	exx
55$:
	ld	4 (iy), #0		; z の下位(上で書く)
56$:
	ld	5 (iy), #0		; z の上位
57$:
	ld	6 (iy), #0		; 番号
	jr	8$
70$:	; 広げる(座標は 0〜64 のブロックなので符号なしで比べる)
	exx
	ld	a, b
	cp	a, 0 (iy)
	jr	nc, 71$
	ld	0 (iy), a
71$:
	ld	a, d
	cp	a, 1 (iy)
	jr	nc, 72$
	ld	1 (iy), a
72$:
	ld	a, c
	cp	a, 2 (iy)
	jr	c, 73$
	ld	2 (iy), a
73$:
	ld	a, e
	cp	a, 3 (iy)
	jr	c, 74$
	ld	3 (iy), a
74$:
	exx
8$:
	ld	de, #6
	add	ix, de
	pop	bc
	dec	b
	jp	nz, 1$
	pop	iy
	pop	ix
	ret
58$:
	exx
	jr	8$

; dm_grow1: HL = 位置、DE = 長さ、C = 画面の端 → 両側に 1 ブロックずつ広げる(画面の外へは出さない)
dm_grow1:
	ld	a, (hl)
	or	a, a
	jr	z, 1$
	dec	(hl)
	ex	de, hl
	inc	(hl)
	ex	de, hl
1$:
	ld	a, (de)
	add	a, (hl)
	cp	a, c
	ret	nc
	ex	de, hl
	inc	(hl)
	ret


; ---------------------------------------------------------------------------
; void rail_add(const RailSeg *segs)   HL = segs(RailSeg: u8 len、i16 dyaw、i8 dy、u8 spd の 5 バイト。len = 0 で終わり)
;   区間ごとに len / 2 個の点(2m ごと)を rail[rb_n] から足す(RAIL_MAX まで)。もと rail.c の C と同じ計算:
;   点 = (rb_x, rb_y, rb_z, rb_yaw)、rail_spd = spd。次へ: rb_yaw += dyaw / steps(0 へ切り捨て)、
;   rb_x += sin(rb_yaw の上位) × 2、rb_z += cos(…) × 2、rb_y += dy × 32。最後に rail_len = rb_n × 2。
;   C だと分岐を選んだフレームで約 190 点を作り直すのに 13ms かかっていた
