; raster.s — 凸多角形のラスタライズ(ホットパス)
;
; 入力: _scr[n] = { i16 x, i16 y }(画面座標 12.4、±15512 以内に収めてあること)
;   → 差が 16bit 符号付きに収まるので、比較は sbc hl,de の符号だけで行える。
;
; 標本化(render.c と同じ約束):
;   行 r はブロック中心 y = r*16+8。辺 (y0 < y1) が覆う行 = [(y0+7)>>4, (y1+7)>>4)
;   スパン = [round(xl), round(xr))。下り辺は span_a、上り辺は span_b に x を書く。
;
; 辺ごとの計算(割り算 2〜3 回):
;   slope(16.16 ブロック/行) = |dx| * 65536 / dy          … div_core 1〜2 回
;   x_start(12.4)            = x0 ± |dx| * t / dy(t = 最初の行の中心 - y0) … MULUW + div_core 1 回
; 行ごとのループは exx で 32bit の加算をレジスタだけで回す(その間は DI)。

	.module	raster
	.r800				; IYL(edge)
	.include "r800.inc"

	.globl	div_core
	.globl	_recip9
	.globl	_g_color
	.globl	_g_buf_hi

ROWS	= 40
FILLBLK	= 0x0100		; 塗りの展開ブロック(ページ0の RAM。sys_page0_ram が _fillblk_tpl を写す)
FILLJP	= FILLBLK + 2
FILLEND	= FILLJP + 3 + 64
; 各行の左右端(0..64)。256 境界に置き、fill が inc d / dec d だけで左右を行き来する
_span_a	== 0xDE00
_span_b	== 0xDF00
SPAN_A_HI = 0xDE

; ROWCLAMP: HL = y(12.4)→ A = (y + 7) >> 4 を 0..ROWS に丸めた値(関数呼び出しをしない)。DE・HL を壊す
;   0 <= y < 768 なら (y + 7) << 4 の上位バイトが答え(y + 7 < 4096 なので桁あふれしない)
	.macro	ROWCLAMP ?rc_n, ?rc_b, ?rc_d
	bit	7, h
	jr	nz, rc_n
	ld	a, h
	cp	a, #3
	jr	nc, rc_b			; y >= 768 → 48 行以上
	ld	de, #7
	add	hl, de
	add	hl, hl
	add	hl, hl
	add	hl, hl
	add	hl, hl
	ld	a, h
	cp	a, #ROWS + 1
	jr	c, rc_d
rc_b:
	ld	a, #ROWS
	jr	rc_d
rc_n:
	xor	a, a
rc_d:
	.endm

	.include "pscale.inc"

	.area	_DATA
e_fast:		.ds	1
_scr::		.ds	4 * 10
r_n:		.ds	1
r_ymin:		.ds	2
r_ymax:		.ds	2
r_xmin:		.ds	2
r_xmax:		.ds	2
e_x0:		.ds	2
e_y0:		.ds	2
e_x1:		.ds	2
e_y1:		.ds	2
e_dst:		.ds	2
e_rs:		.ds	1
e_neg:		.ds	1
e_dy:		.ds	2
e_adx:		.ds	2
e_sh:		.ds	2
e_sl:		.ds	2
e_xl:		.ds	2
e_cnt:		.ds	1
e_t:		.ds	2
e_ol:		.ds	2
e_oh:		.ds	2
e_xh:		.ds	2
_p_q::		.ds	2	; 直前の投影の 2^23 / z(geom.s の draw_model が使う)

	.area	_CODE

; HL = (HL + 7) >> 4(算術)
row_of:
	ld	de, #7
	add	hl, de
	sra	h
	rr	l
	sra	h
	rr	l
	sra	h
	rr	l
	sra	h
	rr	l
	ret

; HL(符号付き)を 0..ROWS に丸めて A に
clamp_row:
	bit	7, h
	jr	nz, 1$
	ld	a, h
	or	a, a
	jr	nz, 2$
	ld	a, l
	cp	a, #ROWS + 1
	ret	c
2$:
	ld	a, #ROWS
	ret
1$:
	xor	a, a
	ret

; ---------------------------------------------------------------------------
; void raster(u8 n, u8 color)   A=n, L=color
; ---------------------------------------------------------------------------
_raster::
	push	af
	pop	af
	ld	c, a
	ld	a, l
	ld	(_g_color), a
	ld	a, c
	ld	(r_n), a
	push	ix
	push	iy

	; ---- 外接矩形(最初の頂点で初期化する。0x7FFF などの番兵は差が 16bit を超えて比較が壊れる)
	ld	hl, (_scr)
	ld	(r_xmin), hl
	ld	(r_xmax), hl
	ld	hl, (_scr + 2)
	ld	(r_ymin), hl
	ld	(r_ymax), hl
	ld	ix, #_scr
	ld	b, c
10$:
	ld	e, 2 (ix)
	ld	d, 3 (ix)
	ld	hl, (r_ymin)
	or	a, a
	sbc	hl, de
	jp	m, 11$
	ld	(r_ymin), de
11$:
	ld	hl, (r_ymax)
	or	a, a
	sbc	hl, de
	jp	p, 12$
	ld	(r_ymax), de
12$:
	ld	e, 0 (ix)
	ld	d, 1 (ix)
	ld	hl, (r_xmin)
	or	a, a
	sbc	hl, de
	jp	m, 13$
	ld	(r_xmin), de
13$:
	ld	hl, (r_xmax)
	or	a, a
	sbc	hl, de
	jp	p, 14$
	ld	(r_xmax), de
14$:
	inc	ix
	inc	ix
	inc	ix
	inc	ix
	djnz	10$

	; 画面の左右に完全に外れていれば描かない
	ld	a, (r_xmax + 1)
	bit	7, a
	jp	nz, r_done
	ld	hl, (r_xmin)
	ld	de, #64 * 16 + 1
	or	a, a
	sbc	hl, de
	jp	p, r_done

	; 行の範囲
	ld	hl, (r_ymin)
	call	row_of
	call	clamp_row
	ld	c, a			; C = r0
	ld	hl, (r_ymax)
	call	row_of
	call	clamp_row		; A = r1
	sub	a, c
	jp	z, r_done
	jp	c, r_done
	push	bc			; C = r0
	push	af			; A = 行数

	; ---- 辺
	ld	ix, #_scr
	ld	a, (r_n)
	ld	b, a
20$:
	push	bc
	; 次の頂点(最後は先頭へ)
	push	ix
	pop	iy
	inc	iy
	inc	iy
	inc	iy
	inc	iy
	dec	b
	jr	nz, 21$
	ld	iy, #_scr
21$:
	; y0 = 2(ix), y1 = 2(iy)
	ld	l, 2 (ix)
	ld	h, 3 (ix)
	ld	e, 2 (iy)
	ld	d, 3 (iy)
	or	a, a
	sbc	hl, de			; y0 - y1
	jr	z, 29$			; 水平な辺は無視
	jp	p, 22$
	; y0 < y1: 下り辺 (ix → iy) を span_a へ
	ld	l, 0 (ix)
	ld	h, 1 (ix)
	ld	(e_x0), hl
	ld	l, 2 (ix)
	ld	h, 3 (ix)
	ld	(e_y0), hl
	ld	l, 0 (iy)
	ld	h, 1 (iy)
	ld	(e_x1), hl
	ld	(e_y1), de
	ld	hl, #_span_a
	jr	23$
22$:
	; y0 > y1: 上り辺。上端 (iy) から下端 (ix) を span_b へ
	ld	l, 0 (iy)
	ld	h, 1 (iy)
	ld	(e_x0), hl
	ld	(e_y0), de
	ld	l, 0 (ix)
	ld	h, 1 (ix)
	ld	(e_x1), hl
	ld	l, 2 (ix)
	ld	h, 3 (ix)
	ld	(e_y1), hl
	ld	hl, #_span_b
23$:
	ld	(e_dst), hl
	call	edge
29$:
	inc	ix
	inc	ix
	inc	ix
	inc	ix
	pop	bc
	djnz	20$

	; ---- 塗る
	pop	af			; 行数
	pop	bc			; C = r0
	ld	b, a
	call	fill
r_done:
	pop	iy
	pop	ix
	ret

; ---------------------------------------------------------------------------
; edge: e_x0,e_y0(上端)→ e_x1,e_y1(下端)が覆う行の x を e_dst[行] に書き、e_rs = 最初の行、e_cnt = 行数(行があるとき)
;   IY は壊してよい。IX は壊さない(slot_ensure の呼び出し元が使う)
;   ほとんどの辺は「始点・終点の x が ±1792 以内、t < 4096、傾きが 128 ブロック/行 未満」の速い経路に乗る。
;   速い経路はここで、途中の値をメモリに置かずに計算する(R800 はデータのメモリアクセスのたびにページが変わって待たされる)。
;   乗らない辺は edge_gen(はじめから、一般の経路も含めて計算する)。どちらも同じ値を書く
; ---------------------------------------------------------------------------
edge::
	ld	a, (e_x0 + 1)
	add	a, #7
	cp	a, #14
	jp	nc, edge_gen		; 上位バイトが 0..6 か 0xF9..0xFF でなければ ±1792 の外
	ld	a, (e_x1 + 1)
	add	a, #7
	cp	a, #14
	jp	nc, edge_gen
	; ---- 覆う行 [rs, re)
	ld	hl, (e_y0)
	ROWCLAMP
	ld	(e_rs), a
	ld	c, a
	ld	hl, (e_y1)
	ROWCLAMP
	sub	a, c
	ret	z
	ret	c
	ld	(e_cnt), a
	; ---- t = rs*16 + 8 - y0(>= 0)
	ld	l, c
	ld	h, #0
	add	hl, hl
	add	hl, hl
	add	hl, hl
	add	hl, hl
	ld	de, #8
	add	hl, de
	ld	de, (e_y0)
	or	a, a
	sbc	hl, de
	ld	a, h
	cp	a, #0x10
	jp	nc, edge_gen		; t >= 4096
	push	hl			; t
	; ---- |dx| と符号
	ld	hl, (e_x1)
	push	de
	ld	de, (e_x0)
	or	a, a
	sbc	hl, de
	pop	de			; DE = y0
	ld	a, h
	ld	(e_neg), a		; bit7 = 左へ
	bit	7, h
	jr	z, 1$
	xor	a, a
	sub	a, l
	ld	l, a
	sbc	a, a
	sub	a, h
	ld	h, a
1$:
	push	hl			; |dx|
	; ---- dy = y1 - y0 を 9bit の仮数 m(256..511)にそろえる。k = 8 + ずらした回数(裏の A に置く)
	ld	hl, (e_y1)
	or	a, a
	sbc	hl, de
	ld	b, #8
2$:
	ld	a, h
	cp	a, #2
	jr	c, 4$
	srl	h
	rr	l
	inc	b
	jr	2$
4$:
	bit	0, h
	jr	nz, 5$
	add	hl, hl
	dec	b
	jr	4$
5$:
	ld	a, b
	ex	af, af'			; A' = k(割り込み処理は裏のレジスタを使わない)
	ld	h, #0
	add	hl, hl
	ld	de, #_recip9
	add	hl, de
	ld	a, (hl)
	inc	hl
	ld	h, (hl)
	ld	l, a
	pop	bc			; |dx|
	MULUW_HL_BC			; DE:HL = P = |dx| * recip9[m]
	; ---- step88 = P >> (k + 8)
	ex	af, af'
	sub	a, #8
	jr	c, 7$
	ex	de, hl			; HL = P >> 16
	jr	z, 9$
	ld	b, a
6$:
	srl	h
	rr	l
	djnz	6$
	jr	9$
7$:
	neg				; k < 8: 左へ 8 - k ずらしてから上位 16bit
	ld	b, a
8$:
	add	hl, hl
	rl	e
	rl	d
	djnz	8$
	ex	de, hl
9$:
	bit	7, h
	jr	z, 10$
	pop	hl			; 傾き >= 128 ブロック/行: 一般の経路(はじめから)
	jp	edge_gen
10$:
	; ---- off88 = step88 * (t << 4) >> 8(MULUW の中央 2 バイト)
	ld	b, h
	ld	c, l			; BC = |step88|
	pop	hl			; t
	add	hl, hl
	add	hl, hl
	add	hl, hl
	add	hl, hl
	MULUW_HL_BC
	ld	l, h
	ld	h, e
	ex	de, hl			; DE = off88
	; ---- x88 = (x0 + 8) << 4 ± off88、DE = ±step88
	ld	hl, (e_x0)
	add	hl, hl
	add	hl, hl
	add	hl, hl
	add	hl, hl
	ld	a, l
	add	a, #0x80		; + 8 << 4
	ld	l, a
	jr	nc, 11$
	inc	h
11$:
	ld	a, (e_neg)
	rla
	jr	c, 12$
	add	hl, de
	ld	d, b
	ld	e, c
	jr	13$
12$:
	or	a, a
	sbc	hl, de
	xor	a, a
	sub	a, c
	ld	e, a
	sbc	a, a
	sub	a, b
	ld	d, a
13$:
	; ---- 書く: BC = 書き込み先(e_dst + rs。行は 256 バイトの中で収まる)、IYL = 行数
	ld	a, (e_dst + 1)
	ld	b, a
	ld	a, (e_rs)
	ld	c, a
	ld	a, (e_dst)
	add	a, c
	ld	c, a
	ld	a, (e_cnt)
	ld	iyl, a
	; 始点・終点とも画面の中(0 <= x < 1024)なら丸めずに書くだけ
	ld	a, (e_x0 + 1)
	cp	a, #4
	jr	nc, 16$
	ld	a, (e_x1 + 1)
	cp	a, #4
	jr	nc, 16$
14$:
	ld	a, h
	ld	(bc), a
	inc	c
	add	hl, de
	dec	iyl
	jr	nz, 14$
	ret
16$:
	ld	a, h
	bit	7, a
	jr	nz, 18$
	cp	a, #65
	jr	c, 19$
	ld	a, #64
	jr	19$
18$:
	xor	a, a
19$:
	ld	(bc), a
	inc	c
	add	hl, de
	dec	iyl
	jr	nz, 16$
	ret

; edge_gen: edge のはじめからの計算(一般の経路を含む。速い経路に乗る辺も同じ値になる)
edge_gen:
	; ---- 覆う行 [rs, re)
	ld	hl, (e_y0)
	ROWCLAMP
	ld	(e_rs), a
	ld	c, a
	ld	hl, (e_y1)
	ROWCLAMP
	sub	a, c
	ret	z
	ret	c
	ld	(e_cnt), a		; 辺キャッシュ(slot_ensure)が行の範囲を記録する
	; ---- 両端とも画面の左に 16 ブロック以上外(x < -256)なら全部の行が 0、右に 16 ブロック以上外(x >= 1280)なら 64。
	;   傾きの誤差(逆数表の仮数 9bit、|dx| / 256 = 128 以内)では値が変わらない。仮リングの頂点のような画面のずっと外の辺
	ld	b, a			; B = 行数
	ld	a, (e_x0 + 1)
	cp	a, #0x80
	jr	c, 60$
	cp	a, #0xFF
	jr	z, 69$			; -256 <= x0 < 0
	ld	a, (e_x1 + 1)
	cp	a, #0x80
	jr	c, 69$
	cp	a, #0xFF
	jr	z, 69$
	xor	a, a
	jr	65$
60$:
	cp	a, #5
	jr	c, 69$			; x0 < 1280
	ld	a, (e_x1 + 1)
	cp	a, #5
	jr	c, 69$
	cp	a, #0x80
	jr	nc, 69$
	ld	a, #64
65$:
	ld	hl, (e_dst)
	ld	e, c
	ld	d, #0
	add	hl, de
66$:
	ld	(hl), a
	inc	hl
	djnz	66$
	ret
69$:
	; ---- t = rs*16 + 8 - y0(>= 0)
	ld	l, c
	ld	h, #0
	add	hl, hl
	add	hl, hl
	add	hl, hl
	add	hl, hl
	ld	de, #8
	add	hl, de
	ld	de, (e_y0)
	or	a, a
	sbc	hl, de
	ld	(e_t), hl
	; ---- dy = y1 - y0(> 0)
	ld	hl, (e_y1)
	or	a, a
	sbc	hl, de
	push	hl
	; ---- dx と符号
	ld	hl, (e_x1)
	ld	de, (e_x0)
	or	a, a
	sbc	hl, de
	ld	a, h
	ld	(e_neg), a		; bit7 = 左へ
	bit	7, h
	jr	z, 51$
	xor	a, a
	sub	a, l
	ld	l, a
	sbc	a, a
	sub	a, h
	ld	h, a
51$:
	ld	(e_adx), hl
	; ---- 速い経路に乗るか: 始点・終点の x が ±1792(12.4、±112 ブロック)以内、t < 4096
	;   上位バイトが 0..6 か 0xF9..0xFF なら ±1792 以内
	ld	a, (e_x0 + 1)
	add	a, #7
	cp	a, #14
	jr	nc, 52$
	ld	a, (e_x1 + 1)
	add	a, #7
	cp	a, #14
	jr	nc, 52$
	ld	a, (e_t + 1)
	cp	a, #0x10
	jr	nc, 52$
	ld	a, #1
	jr	53$
52$:
	xor	a, a
53$:
	ld	(e_fast), a
	pop	hl			; dy
	; ---- |dx| / dy を逆数表で: dy を 9bit の仮数 m(256..511)にそろえ、P = |dx| * recip9[m]
	;   16.16 の傾き = P >> k、8.8 の傾き = P >> (k + 8)(k = 8 + ずらした回数)
	ld	c, #8
10$:
	ld	a, h
	cp	a, #2
	jr	c, 11$
	srl	h
	rr	l
	inc	c
	jr	10$
11$:
	bit	0, h
	jr	nz, 12$
	add	hl, hl
	dec	c
	jr	11$
12$:
	ld	h, #0
	add	hl, hl
	ld	de, #_recip9
	add	hl, de
	ld	a, (hl)
	inc	hl
	ld	h, (hl)
	ld	l, a
	push	bc
	ld	bc, (e_adx)
	MULUW_HL_BC			; DE:HL = P
	pop	bc			; C = k
	ld	a, (e_fast)
	or	a, a
	jp	z, 30$
	; ---- 速い経路: step88 = P >> (k + 8)
	push	de			; P を取っておく(急すぎたら一般の経路へ)
	push	hl
	ld	a, c
	sub	a, #8
	jr	c, 20$
	ex	de, hl			; HL = P >> 16
	jr	z, 22$
	ld	b, a
21$:
	srl	h
	rr	l
	djnz	21$
	jr	22$
20$:
	neg				; k < 8: 左へ 8 - k ずらしてから上位 16bit
	ld	b, a
23$:
	add	hl, hl
	rl	e
	rl	d
	djnz	23$
	ex	de, hl
22$:
	bit	7, h
	jr	z, 24$
	pop	hl			; 傾き >= 128 ブロック/行: 一般の経路へ
	pop	de
	jp	30$
24$:
	pop	af			; 取っておいた P は要らない
	pop	af
	; off88 = step88 * (t << 4) >> 8(MULUW の中央 2 バイト)
	ld	b, h
	ld	c, l			; BC = |step88|
	ld	hl, (e_t)
	add	hl, hl
	add	hl, hl
	add	hl, hl
	add	hl, hl
	MULUW_HL_BC			; DE:HL
	ld	l, h
	ld	h, e
	ex	de, hl			; DE = off88
	; x88 = (x0 + 8) << 4 ± off88、DE = ±step88
	ld	hl, (e_x0)
	push	bc
	ld	bc, #8
	add	hl, bc
	add	hl, hl
	add	hl, hl
	add	hl, hl
	add	hl, hl
	pop	bc
	ld	a, (e_neg)
	rla
	jr	c, 25$
	add	hl, de
	ld	d, b
	ld	e, c
	jr	26$
25$:
	or	a, a
	sbc	hl, de
	xor	a, a
	sub	a, c
	ld	e, a
	sbc	a, a
	sub	a, b
	ld	d, a
26$:
	; HL = x88、DE = step88。書き込み先 IY = e_dst + rs、B = 行数
	ld	a, (e_cnt)
	ld	b, a
	ld	a, (e_rs)
	ld	iy, (e_dst)
	push	de
	ld	e, a
	ld	d, #0
	add	iy, de
	pop	de
	; 始点・終点とも画面の中(0 <= x < 1024)なら丸めずに書くだけ
	ld	a, (e_x0 + 1)
	cp	a, #4
	jr	nc, 43$
	ld	a, (e_x1 + 1)
	cp	a, #4
	jr	nc, 43$
27$:
	ld	0 (iy), h
	inc	iy
	add	hl, de
	djnz	27$
	ret
43$:
	ld	a, h
	bit	7, a
	jr	nz, 44$
	cp	a, #65
	jr	c, 45$
	ld	a, #64
	jr	45$
44$:
	xor	a, a
45$:
	ld	0 (iy), a
	inc	iy
	add	hl, de
	djnz	43$
	ret

	; ---- 一般の経路へ: 16.16 の傾き S = P >> k を e_sl / e_sh に
30$:
	ld	a, c
	cp	a, #8
	jr	c, 35$
	ld	l, h			; まず 8bit はバイトの入れ替えで
	ld	h, e
	ld	e, d
	ld	d, #0
	sub	a, #8
35$:
	or	a, a
	jr	z, 34$
	ld	b, a
33$:
	srl	d
	rr	e
	rr	h
	rr	l
	djnz	33$
34$:
	ld	(e_sl), hl
	ld	(e_sh), de
	; ---- 一般の経路: 32bit のずれ計算
40$:
	ld	hl, (e_sl)
	; ---- 最初の行の中心までのずれ off(16.16) = slope * t / 16 = (sh*t << 12) + (sl*t >> 4)
	ld	bc, (e_t)
	MULUW_HL_BC			; DE:HL = sl * t
	.rept	4
	srl	d
	rr	e
	rr	h
	rr	l
	.endm
	ld	(e_ol), hl
	ld	(e_oh), de
	ld	hl, (e_sh)
	MULUW_HL_BC			; DE:HL = sh * t(BC は保存される)
	ld	a, d
	or	a, a
	jr	nz, 2$
	ld	a, e
	and	a, #0xF0
	jr	nz, 2$			; sh*t >= 2^20 → 画面の遥か外。飽和
	ld	a, l
	and	a, #0x0F
	rlca
	rlca
	rlca
	rlca
	ld	c, a
	.rept	4
	srl	e
	rr	h
	rr	l
	.endm
	ld	a, (e_ol + 1)
	add	a, c
	ld	(e_ol + 1), a
	ld	de, (e_oh)
	adc	hl, de
	ld	(e_oh), hl
	bit	7, h
	jr	z, 3$
2$:
	ld	hl, #0x7FFF
	ld	(e_oh), hl
3$:
	; ---- x(16.16) = (x0 + 8) << 12 ± off(+8 = +0.5 ブロックの丸め)
	ld	hl, (e_x0)
	ld	de, #8
	add	hl, de
	ld	a, l
	and	a, #0x0F
	rlca
	rlca
	rlca
	rlca
	ld	d, a
	ld	e, #0
	.rept	4
	sra	h
	rr	l
	.endm
	ld	bc, (e_ol)
	ld	a, (e_neg)
	rla
	jr	c, 4$
	ex	de, hl
	add	hl, bc
	ex	de, hl
	ld	bc, (e_oh)
	adc	hl, bc
	jr	5$
4$:
	ex	de, hl
	or	a, a
	sbc	hl, bc
	ex	de, hl
	ld	bc, (e_oh)
	sbc	hl, bc
5$:
	; HL:DE = x の開始(16.16)
	ld	(e_xh), hl
	ld	(e_xl), de
	ld	a, (e_neg)
	rla
	jr	nc, 6$
	ld	hl, (e_sl)
	ld	de, (e_sh)
	xor	a, a
	sub	a, l
	ld	l, a
	ld	a, #0
	sbc	a, h
	ld	h, a
	ld	a, #0
	sbc	a, e
	ld	e, a
	ld	a, #0
	sbc	a, d
	ld	d, a
	ld	(e_sl), hl
	ld	(e_sh), de
6$:
	ld	a, (e_cnt)
	ld	b, a
	ld	a, (e_rs)
	ld	e, a
	ld	d, #0
	ld	iy, (e_dst)
	add	iy, de
	di
	exx
	ld	hl, (e_xh)
	ld	de, (e_sh)
	exx
	ld	hl, (e_xl)
	ld	de, (e_sl)
7$:
	exx
	ld	a, h
	or	a, a
	jr	nz, 8$
	ld	a, l
	cp	a, #65
	jr	c, 9$
	ld	a, #64
	jr	9$
8$:
	bit	7, h
	ld	a, #0
	jr	nz, 9$
	ld	a, #64
9$:
	exx
	ld	0 (iy), a
	inc	iy
	add	hl, de
	exx
	adc	hl, de
	exx
	djnz	7$
	ei
	ret

; ---------------------------------------------------------------------------
; fill: C = 最初の行、B = 行数。span_a[r] と span_b[r] の間を g_color で塗る
; ---------------------------------------------------------------------------
fill::
	; 詰めたバッファ(gfx.s の並び)へ塗る。行ごとに左右を決め、展開した書き込みの途中へ飛ぶ。
	;   奇数の端は半バイトだけ読み書きする。横に隣り合うバイトは +8(展開ブロックは ld (hl),a / add hl,bc の 32 組)
	push	ix
	ld	ix, #FILLBLK		; IXH = 展開ブロックの上位(行ごとに IXL だけ書いて jp (ix))
	ld	a, c
	add	a, b
	ld	(f_endi + 1), a		; 終わりの行(行ごとの比べる即値)
	; 色とバッファの上位バイトを、行ごとの命令の即値へ書き込んでおく(自己書き換え。行ごとにメモリから読まない)
	ld	a, (_g_buf_hi)
	ld	(f_buf + 1), a
	ld	a, (_g_color)
	and	a, #0x0F
	ld	(f_lo + 1), a
	ld	b, a
	add	a, a
	add	a, a
	add	a, a
	add	a, a
	ld	(f_hi + 1), a
	or	a, b
	ld	(f_cc + 1), a		; 両方のブロックが同じ色のバイト
	ld	d, #SPAN_A_HI
	ld	e, c
fill_row:
	inc	d
	ld	a, (de)			; span_b
	ld	c, a
	dec	d
	ld	a, (de)			; span_a
	sub	a, c			; 大小と幅を 1 回の引き算で
	jr	z, fill_next
	jr	c, fill_lt
	ld	b, a			; span_a > span_b: 幅 = A、左端 = span_b(C)
	jr	fill_go
fill_lt:
	neg				; span_a < span_b: 幅 = -A、左端 = span_b - 幅
	ld	b, a
	ld	a, c
	sub	a, b
	ld	c, a
fill_go:
	; H = バッファ + (行 >> 3)、L = (左端 >> 1) * 8 + (行 & 7)
	ld	a, e
	rrca
	rrca
	rrca
	and	a, #0x1F
f_buf:
	add	a, #0			; + バッファの上位バイト(書き換える)
	ld	h, a
	ld	a, c
	and	a, #0xFE
	add	a, a
	add	a, a
	ld	l, a
	ld	a, e
	and	a, #7
	or	a, l
	ld	l, a
	bit	0, c
	jr	z, fill_even
	; 左端が奇数: そのバイトの右半分だけ
	ld	a, (hl)
	and	a, #0xF0
f_lo:
	or	a, #0			; 色(書き換える)
	ld	(hl), a
	ld	a, l
	add	a, #8
	ld	l, a
	dec	b
	jr	z, fill_next
fill_even:
	ld	a, b
	srl	a			; 丸ごと塗るバイトの数、キャリー = 右端に半分が残る
	jr	z, fill_tail		; 丸ごとのバイトが無ければキャリーはそのまま
	ld	b, a
	ex	af, af'			; キャリーを裏の F に置く(展開ブロックの add hl,bc がキャリーを壊すため。割り込みは裏を使わない)
	ld	a, b
	add	a, a
	ld	b, a
	ld	a, #<FILLEND
	sub	a, b
	ld	ixl, a			; 飛び先 = 終わり - 数 * 2(ブロックは 256 境界の中なので下位だけ)
	ld	bc, #8
f_cc:
	ld	a, #0			; 両方のブロックが同じ色のバイト(書き換える)
	jp	(ix)			; 展開ブロックの途中へ
fill_ret::
	ex	af, af'			; 裏に置いたキャリー
fill_tail:
	jr	nc, fill_next
	; 右端が奇数: そのバイトの左半分だけ
	ld	a, (hl)
	and	a, #0x0F
f_hi:
	or	a, #0			; 色 << 4(書き換える)
	ld	(hl), a
fill_next:
	inc	e
	ld	a, e
f_endi:
	cp	a, #0			; 終わりの行(書き換える)
	jp	nz, fill_row
fill_done::				; 計測用(塗りの終わりを捕まえる)
	pop	ix
	ret


; 展開した 32 回の書き込みの元(sys_page0_ram がページ0の FILLBLK = 0x0100 へ写す)。
;   256 境界の中で動くので、飛び先は下位バイトだけを書き換える
_fillblk_tpl::
	ld	a, #0			; FILLBLK(使わない。fill は色を A に入れて、下の展開の途中へ jp (ix) で飛ぶ)
	jp	0x0100			; FILLJP(使わない)
	.rept	32
	ld	(hl), a
	add	hl, bc
	.endm
	jp	fill_ret		; FILLEND
_fillblk_end::

; ---------------------------------------------------------------------------
; void project2(const V3 *v, i16 *out)   HL=v, DE=out。z >= 128(0.5m)が前提
;   out[0] = 512 + x*512/z、out[1] = 320 - y*512/z(12.4、±15000 に飽和)
;   割り算は q = 2^23 / z の 1 回だけ。x*q >> 14 = x*512/z
; ---------------------------------------------------------------------------
_project2::
	; 変数をメモリに置かず、スタックとレジスタで回す(R800 はデータのメモリアクセスが重い)
	push	de			; 出力先
	ld	e, (hl)
	inc	hl
	ld	d, (hl)
	inc	hl
	push	de			; x
	ld	e, (hl)
	inc	hl
	ld	d, (hl)
	inc	hl
	push	de			; y
	ld	a, (hl)
	inc	hl
	ld	h, (hl)
	ld	l, a			; HL = z
	call	z2q
	ld	(_p_q), hl
	ld	b, h
	ld	c, l			; BC = q(PSCALE の間は保たれる)
	pop	hl			; y
	PSCALE
	ld	hl, #320
	or	a, a
	sbc	hl, de			; sy
	ex	(sp), hl		; スタック = sy、HL = x
	PSCALE
	ld	hl, #512
	add	hl, de			; sx
	pop	de			; sy
	ex	(sp), hl		; スタック = sx、HL = 出力先
	pop	bc			; sx
	ld	(hl), c
	inc	hl
	ld	(hl), b
	inc	hl
	ld	(hl), e
	inc	hl
	ld	(hl), d
	ret

; z2q: HL = z → HL = q(2^23 / z)。AF・DE を壊す
z2q::
	; q = 2^23 / z を逆数表で。z を 9bit の仮数 m(256..511)にそろえ(右へ k 回)、q = recip9[m] >> (k + 1)。
	; z < 256(0.5〜1m)は左へ 1 回そろえて q = recip9[m]。k は上位バイトの桁で決め、シフトはループせずに並べる
	ld	a, h
	cp	a, #2
	jr	c, 20$
	cp	a, #8
	jr	c, 21$
	cp	a, #32
	jr	c, 22$
	cp	a, #64
	jp	c, 25$
	jp	26$
21$:
	cp	a, #4
	jr	c, 31$
	jp	32$
22$:
	cp	a, #16
	jp	c, 33$
	jp	34$
20$:
	or	a, a
	jr	nz, 30$
	; z < 256: 左へ 1 回
	add	hl, hl
	ld	h, #0
	add	hl, hl
	ld	de, #_recip9
	add	hl, de
	ld	a, (hl)
	inc	hl
	ld	h, (hl)
	ld	l, a			; HL = recip9[m]
	jp	14$
30$:
	ld	h, #0
	add	hl, hl
	ld	de, #_recip9
	add	hl, de
	ld	a, (hl)
	inc	hl
	ld	h, (hl)
	ld	l, a			; HL = recip9[m]
	srl	h
	rr	l
	jp	14$
31$:
	srl	h
	rr	l
	ld	h, #0
	add	hl, hl
	ld	de, #_recip9
	add	hl, de
	ld	a, (hl)
	inc	hl
	ld	h, (hl)
	ld	l, a			; HL = recip9[m]
	srl	h
	rr	l
	srl	h
	rr	l
	jp	14$
32$:
	srl	h
	rr	l
	srl	h
	rr	l
	ld	h, #0
	add	hl, hl
	ld	de, #_recip9
	add	hl, de
	ld	a, (hl)
	inc	hl
	ld	h, (hl)
	ld	l, a			; HL = recip9[m]
	srl	h
	rr	l
	srl	h
	rr	l
	srl	h
	rr	l
	jp	14$
33$:
	srl	h
	rr	l
	srl	h
	rr	l
	srl	h
	rr	l
	ld	h, #0
	add	hl, hl
	ld	de, #_recip9
	add	hl, de
	ld	a, (hl)
	inc	hl
	ld	h, (hl)
	ld	l, a			; HL = recip9[m]
	srl	h
	rr	l
	srl	h
	rr	l
	srl	h
	rr	l
	srl	h
	rr	l
	jp	14$
34$:
	srl	h
	rr	l
	srl	h
	rr	l
	srl	h
	rr	l
	srl	h
	rr	l
	ld	h, #0
	add	hl, hl
	ld	de, #_recip9
	add	hl, de
	ld	a, (hl)
	inc	hl
	ld	h, (hl)
	ld	l, a			; HL = recip9[m]
	srl	h
	rr	l
	srl	h
	rr	l
	srl	h
	rr	l
	srl	h
	rr	l
	srl	h
	rr	l
	jp	14$
25$:
	srl	h
	rr	l
	srl	h
	rr	l
	srl	h
	rr	l
	srl	h
	rr	l
	srl	h
	rr	l
	ld	h, #0
	add	hl, hl
	ld	de, #_recip9
	add	hl, de
	ld	a, (hl)
	inc	hl
	ld	h, (hl)
	ld	l, a			; HL = recip9[m]
	srl	h
	rr	l
	srl	h
	rr	l
	srl	h
	rr	l
	srl	h
	rr	l
	srl	h
	rr	l
	srl	h
	rr	l
	jp	14$
26$:
	srl	h
	rr	l
	srl	h
	rr	l
	srl	h
	rr	l
	srl	h
	rr	l
	srl	h
	rr	l
	srl	h
	rr	l
	ld	h, #0
	add	hl, hl
	ld	de, #_recip9
	add	hl, de
	ld	a, (hl)
	inc	hl
	ld	h, (hl)
	ld	l, a			; HL = recip9[m]
	srl	h
	rr	l
	srl	h
	rr	l
	srl	h
	rr	l
	srl	h
	rr	l
	srl	h
	rr	l
	srl	h
	rr	l
	srl	h
	rr	l
14$:
	ret

P3_NEAR	= 128
	.area	_DATA
p3_cv:	.ds	6 * 10		; 切った後の頂点(V3)
p3_pl:	.ds	2 * 8		; poly3 の頂点のポインタの並び
p3_pp:	.ds	2		; 次の終点のポインタの位置
p3_a:	.ds	2		; 辺の始点
p3_b:	.ds	2		; 辺の終点
p3_o:	.ds	2		; 書き先
p3_t:	.ds	2		; NEAR_Z - a.z
p3_dz:	.ds	2		; b.z - a.z
p3_k:	.ds	1		; 残りの辺
p3_m:	.ds	1		; 切った後の頂点の数
p3_in:	.ds	1		; 1 = a が手前
p3_col:	.ds	1

	.area	_CODE
_poly3::
	pop	de
	pop	bc			; C = n、B = color
	push	de
	; 頂点のポインタの並びを作る
	ld	de, #p3_pl
	push	bc
	ld	b, c
21$:
	ld	a, l
	ld	(de), a
	inc	de
	ld	a, h
	ld	(de), a
	inc	de
	push	bc
	ld	bc, #6
	add	hl, bc
	pop	bc
	djnz	21$
	pop	bc
	ld	hl, #p3_pl
	jr	p3_core
_poly3p::
	pop	de
	pop	bc			; C = n、B = color
	push	de
p3_core:
	ld	a, b
	ld	(p3_col), a
	ld	a, c
	ld	(p3_k), a
	ld	(p3_pp), hl		; 終点は並びの頭から
	dec	a
	add	a, a
	ld	e, a
	ld	d, #0
	add	hl, de
	ld	a, (hl)
	inc	hl
	ld	h, (hl)
	ld	l, a
	ld	(p3_a), hl		; a = 並びの最後
	ld	de, #p3_cv
	ld	(p3_o), de
	xor	a, a
	ld	(p3_m), a
	call	p3_inz
	ld	(p3_in), a
1$:
	ld	hl, (p3_pp)
	ld	a, (hl)
	inc	hl
	ld	h, (hl)
	ld	l, a
	ld	(p3_b), hl
	call	p3_inz
	ld	c, a			; C = b が手前か
	ld	a, (p3_in)
	cp	a, c
	jr	z, 5$
	; 交点: t = NEAR_Z - a.z、dz = b.z - a.z
	push	bc
	ld	hl, (p3_a)
	ld	de, #4
	add	hl, de
	ld	e, (hl)
	inc	hl
	ld	d, (hl)			; DE = a.z
	ld	hl, #P3_NEAR
	or	a, a
	sbc	hl, de
	ld	(p3_t), hl
	ld	hl, (p3_b)
	ld	bc, #4
	add	hl, bc
	ld	a, (hl)
	inc	hl
	ld	h, (hl)
	ld	l, a			; HL = b.z
	or	a, a
	sbc	hl, de
	ld	(p3_dz), hl
	ld	c, #0
	call	p3_lerp			; x
	ld	c, #2
	call	p3_lerp			; y
	ld	hl, (p3_o)
	ld	de, #4
	add	hl, de
	ld	(hl), #<P3_NEAR
	inc	hl
	ld	(hl), #>P3_NEAR
	inc	hl
	ld	(p3_o), hl
	ld	hl, #p3_m
	inc	(hl)
	pop	bc
5$:
	ld	a, c
	ld	(p3_in), a
	or	a, a
	jr	z, 6$
	; b を写す
	ld	hl, (p3_b)
	ld	de, (p3_o)
	ldi
	ldi
	ldi
	ldi
	ldi
	ldi
	ld	(p3_o), de
	ld	hl, #p3_m
	inc	(hl)
6$:
	ld	hl, (p3_b)
	ld	(p3_a), hl
	ld	hl, (p3_pp)
	inc	hl
	inc	hl
	ld	(p3_pp), hl
	ld	hl, #p3_k
	dec	(hl)
	jp	nz, 1$
	ld	a, (p3_m)
	cp	a, #3
	ret	c
	; 投影して塗る
	ld	b, a
	ld	hl, #p3_cv
	ld	de, #_scr
7$:
	push	bc
	push	hl
	push	de
	call	_project2		; HL = 点、DE = 出力
	pop	hl
	ld	de, #4
	add	hl, de
	ex	de, hl
	pop	hl
	ld	bc, #6
	add	hl, bc
	pop	bc
	djnz	7$
	ld	a, (p3_col)
	ld	l, a
	ld	a, (p3_m)
	jp	_raster

; p3_inz: HL = 頂点 → A = 1(z >= NEAR_Z)/ 0。符号つきの比較は上位ビットを反転して符号なしで比べる
p3_inz:
	ld	de, #4
	add	hl, de
	ld	a, (hl)
	inc	hl
	ld	h, (hl)
	ld	l, a
	ld	a, h
	xor	a, #0x80
	ld	h, a
	ld	de, #P3_NEAR ^ 0x8000
	or	a, a
	sbc	hl, de
	sbc	a, a			; 小さい = 0xFF
	inc	a
	ret

; p3_lerp: C = 成分の位置(0 = x、2 = y)→ o の成分 = a + muldiv(b - a, t, dz)
p3_lerp:
	ld	b, #0
	ld	hl, (p3_a)
	add	hl, bc
	ld	e, (hl)
	inc	hl
	ld	d, (hl)			; DE = a の成分
	push	de
	push	bc
	ld	hl, (p3_b)
	add	hl, bc
	ld	a, (hl)
	inc	hl
	ld	h, (hl)
	ld	l, a
	or	a, a
	sbc	hl, de			; HL = b - a
	ld	de, (p3_dz)
	push	de			; muldiv の 3 つ目(muldiv が捨てる)
	ld	de, (p3_t)
	call	_muldiv			; DE = (b - a) * t / dz
	pop	bc
	pop	hl
	add	hl, de
	ex	de, hl
	ld	hl, (p3_o)
	add	hl, bc
	ld	(hl), e
	inc	hl
	ld	(hl), d
	ret
