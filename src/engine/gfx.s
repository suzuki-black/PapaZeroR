; gfx.s — 描画バッファへの塗りつぶし・矩形・絵・文字・点
;
; 描画バッファは VRAM のパターンジェネレータと同じ並びに詰めた形(1280 バイト、0xC000-0xC4FF。上 160 ライン = 40 行)。
;   番地 = バッファ + (行 >> 3) * 256 + (列 >> 1) * 8 + (行 & 7)
;   1 バイト = 横 2 ブロック。上位 4bit が左(偶数の列)、下位 4bit が右(奇数の列)
; 転送(vdp.s の vdp_xfer)は頭から送るだけでよい。横に隣り合うバイトは 8 バイト離れる(+8 で進む)。
; 多角形の塗りは raster.s。

	.module	gfx


	.area	_DATA
_g_buf_hi::	.ds	1	; 描画バッファの上位バイト(0xC0)
_g_color::	.ds	1	; 塗る色
_g_rx::		.ds	1	; rect_fill・pset・glyph1: 左上(と幅・高さ。クリップ済み)
_g_ry::		.ds	1
_g_rw::		.ds	1
_g_rh::		.ds	1

	.area	_CODE

; PADDR: B = 列、C = 行 → HL = その列のバイトの番地(列の bit0 は見ない)。A を壊す
	.macro	PADDR
	ld	a, c
	rrca
	rrca
	rrca
	and	a, #0x1F
	ld	h, a
	ld	a, (_g_buf_hi)
	add	a, h
	ld	h, a
	ld	a, b
	and	a, #0x3E
	add	a, a
	add	a, a
	ld	l, a
	ld	a, c
	and	a, #7
	or	a, l
	ld	l, a
	.endm

; ---------------------------------------------------------------------------
; pf_band: H = 帯の上位バイト、A = 色のバイト → 帯の 256 バイトを push で塗る(2 バイトずつ。ld (hl), a より約 3 倍速い)
;   SP を帯の終わりに向けるので、その間は割り込みを止める(割り込みが積むと前の帯やバッファの外を壊す)。HL・DE を壊す
; ---------------------------------------------------------------------------
pf_band:
	ld	e, a
	ld	d, a
	inc	h
	ld	l, #0			; 帯の終わり(push は先に SP を減らしてから書く)
	ld	(pf_sp), sp
	di
	ld	sp, hl
	.rept	128
	push	de
	.endm
	ld	sp, (pf_sp)
	ei
	ret

; ---------------------------------------------------------------------------
; void buf_fill(u8 color)   A = 色。バッファ全体(40 行)を塗る
; ---------------------------------------------------------------------------
_buf_fill::
	ld	c, a
	add	a, a
	add	a, a
	add	a, a
	add	a, a
	or	a, c			; 両方のブロックが同じ色のバイト
	ld	c, a
	ld	a, (_g_buf_hi)
	ld	h, a
	ld	b, #5			; 帯 5 本
1$:
	ld	a, c
	push	hl
	call	pf_band
	pop	hl
	inc	h
	djnz	1$
	ret

; ---------------------------------------------------------------------------
; void buf_fill_rows(u8 color, u8 row)   A = 色、L = 最初の行。row から g_rh 行を塗る
;   8 行の帯をまるごと含むところは 256 バイト続けて、残りの行は 1 行 32 バイトを +8 ずつ
; ---------------------------------------------------------------------------
_buf_fill_rows::
	ld	c, a
	add	a, a
	add	a, a
	add	a, a
	add	a, a
	or	a, c
	ld	(fr_cc), a
	ld	c, l			; C = 行
	ld	a, (_g_rh)
	or	a, a
	ret	z
	add	a, c
	ld	b, a			; B = 終わりの行(含まない)
1$:
	ld	a, c
	cp	a, b
	ret	nc
	; 帯の頭で、帯の終わり(+8)まで塗るなら 256 バイトまとめて
	and	a, #7
	jp	nz, 3$
	ld	a, c
	add	a, #8
	cp	a, b
	jr	z, 2$
	jp	nc, 3$
2$:
	push	bc
	ld	a, c
	rrca
	rrca
	rrca
	and	a, #0x1F
	ld	h, a
	ld	a, (_g_buf_hi)
	add	a, h
	ld	h, a
	ld	a, (fr_cc)
	call	pf_band
	pop	bc
	ld	a, c
	add	a, #8
	ld	c, a
	jp	1$
3$:
	; 1 行: 32 バイトを +8 ずつ
	push	bc
	ld	b, #0
	PADDR
	ld	bc, #8
	ld	a, (fr_cc)
	.rept	32
	ld	(hl), a
	add	hl, bc
	.endm
	pop	bc
	inc	c
	jp	1$

	.area	_DATA
fr_cc:		.ds	1
fr_lo:		.ds	1
fr_hi:		.ds	1
pf_sp:		.ds	2	; pf_band の間の SP の退避
	.area	_CODE

; ---------------------------------------------------------------------------
; void rect_fill(void)   g_rx, g_ry, g_rw, g_rh(クリップ済み、幅・高さ 1 以上)を g_color で塗る
;   列(バイトの列)ごとに縦に塗る。詰めた並びでは、帯の中の上下の行は隣のバイト(+1)なので、
;   1 バイトあたり書いて inc l だけで済む(帯をまたぐときだけ上位を +1、下位を -8)。
;   色は塗る命令の即値に書き込む(自己書き換え。コードは RAM 上)。敵の矩形は小さい(平均 3×4 ブロック)ので、準備を軽くする
; ---------------------------------------------------------------------------
	.area	_DATA
rq_tail:	.ds	1	; 1 = 右端に左半分だけの列が残る
	.area	_CODE

_rect_fill::
	ld	a, (_g_color)
	and	a, #0x0F
	ld	(rq_lo + 1), a
	ld	b, a
	add	a, a
	add	a, a
	add	a, a
	add	a, a
	ld	(rq_hi + 1), a
	or	a, b
	ld	(rq_cc + 1), a
	ld	a, (_g_rx)
	ld	b, a
	ld	a, (_g_ry)
	ld	c, a
	PADDR				; HL = 左上のバイト
	ld	a, c
	and	a, #7
	ld	c, a
	ld	a, #8
	sub	a, c
	ld	d, a			; 帯の終わりまでの行数
	ld	a, (_g_rh)
	ld	e, a			; E = 行数
	cp	a, d
	jr	nc, rqx1
	ld	d, a			; D = 最初の帯の中で塗る行数
rqx1:
	ld	a, (_g_rw)
	ld	c, a			; C = 幅
	bit	0, b
	jr	z, rqx3
	; 左端が奇数: 右半分だけの列
	push	hl
	push	bc
	; 縦に 1 列: HL = 一番上のバイト、D = 最初の帯の中の行数、E = 行数
	ld	b, d
	ld	a, e
	sub	a, d
	ld	c, a			; 最初の区切りの後に残る行数
rql1:
	ld	a, (hl)
	and	a, #0xF0
rq_lo:
	or	a, #0			; 色(書き換える)
	ld	(hl), a
	inc	l
	djnz	rql1
	ld	a, c
	or	a, a
	jr	z, rql9
	inc	h			; 次の帯の同じ列
	ld	a, l
	sub	a, #8
	ld	l, a
	ld	a, c
	cp	a, #8
	jr	c, rql2
	ld	b, #8
	sub	a, b
	ld	c, a
	jr	rql1
rql2:
	ld	b, c
	ld	c, #0
	jr	rql1
rql9:
	pop	bc
	pop	hl
	ld	a, l
	add	a, #8
	ld	l, a
	dec	c
	ret	z
rqx3:
	ld	a, c
	and	a, #1
	ld	(rq_tail), a
	ld	a, c
	srl	a			; 丸ごとの列の数
	jr	z, rqx5
	ld	b, a
rqx4:
	push	hl
	push	bc
	; 縦に 1 列: HL = 一番上のバイト、D = 最初の帯の中の行数、E = 行数
	ld	b, d
	ld	a, e
	sub	a, d
	ld	c, a			; 最初の区切りの後に残る行数
rqc1:
rq_cc:
	ld	(hl), #0		; 両方のブロックが同じ色のバイト(書き換える)
	inc	l
	djnz	rqc1
	ld	a, c
	or	a, a
	jr	z, rqc9
	inc	h			; 次の帯の同じ列
	ld	a, l
	sub	a, #8
	ld	l, a
	ld	a, c
	cp	a, #8
	jr	c, rqc2
	ld	b, #8
	sub	a, b
	ld	c, a
	jr	rqc1
rqc2:
	ld	b, c
	ld	c, #0
	jr	rqc1
rqc9:
	pop	bc
	pop	hl
	ld	a, l
	add	a, #8
	ld	l, a
	djnz	rqx4
rqx5:
	ld	a, (rq_tail)
	or	a, a
	ret	z
	; 右端が奇数で残った列: 左半分だけ
	; 縦に 1 列: HL = 一番上のバイト、D = 最初の帯の中の行数、E = 行数
	ld	b, d
	ld	a, e
	sub	a, d
	ld	c, a			; 最初の区切りの後に残る行数
rqh1:
	ld	a, (hl)
	and	a, #0x0F
rq_hi:
	or	a, #0			; 色 << 4(書き換える)
	ld	(hl), a
	inc	l
	djnz	rqh1
	ld	a, c
	or	a, a
	jr	z, rqh9
	inc	h			; 次の帯の同じ列
	ld	a, l
	sub	a, #8
	ld	l, a
	ld	a, c
	cp	a, #8
	jr	c, rqh2
	ld	b, #8
	sub	a, b
	ld	c, a
	jr	rqh1
rqh2:
	ld	b, c
	ld	c, #0
	jr	rqh1
rqh9:
	ret

; ---------------------------------------------------------------------------
; void pset(void)   (g_rx, g_ry) の 1 ブロックを g_color にする(画面内であること)
; ---------------------------------------------------------------------------
_pset::
	ld	a, (_g_rx)
	ld	b, a
	ld	a, (_g_ry)
	ld	c, a
	PADDR
	ld	a, (_g_color)
	and	a, #0x0F
	ld	c, a
	bit	0, b
	jr	nz, 1$
	add	a, a
	add	a, a
	add	a, a
	add	a, a
	ld	c, a
	ld	a, (hl)
	and	a, #0x0F
	or	a, c
	ld	(hl), a
	ret
1$:
	ld	a, (hl)
	and	a, #0xF0
	or	a, c
	ld	(hl), a
	ret

;---------------------------------------------------------------------------
; void marks4(void)   敵の印: 矩形 (g_rx, g_ry)-(g_rw, g_rh) の四隅に鉤(各 3 ブロック)を g_color で描く(game.c の marks_draw)
;   座標は符号付き 8bit。画面の外の点は描かない
; ---------------------------------------------------------------------------
	.area	_DATA
mk_lo:		.ds	1
mk_hi:		.ds	1
	.area	_CODE
_marks4::
	ld	a, (_g_color)
	and	a, #0x0F
	ld	(mk_lo), a
	add	a, a
	add	a, a
	add	a, a
	add	a, a
	ld	(mk_hi), a
	ld	a, (_g_rx)
	ld	d, a			; D = 左
	ld	a, (_g_rw)
	ld	e, a			; E = 右
	ld	a, (_g_ry)
	ld	c, a			; 上の辺
	ld	b, d
	call	mk_pt
	inc	b
	call	mk_pt
	ld	b, e
	call	mk_pt
	dec	b
	call	mk_pt
	inc	c
	ld	b, d
	call	mk_pt
	ld	b, e
	call	mk_pt
	ld	a, (_g_rh)
	ld	c, a			; 下の辺
	ld	b, d
	call	mk_pt
	inc	b
	call	mk_pt
	ld	b, e
	call	mk_pt
	dec	b
	call	mk_pt
	dec	c
	ld	b, d
	call	mk_pt
	ld	b, e
; B = 列、C = 行の 1 ブロック(画面の外なら何もしない)。B, C, D, E を保つ
mk_pt:
	ld	a, b
	cp	a, #64
	ret	nc
	ld	a, c
	cp	a, #40
	ret	nc
	PADDR
	bit	0, b
	jr	nz, 1$
	ld	a, (hl)
	and	a, #0x0F
	ld	(hl), a
	ld	a, (mk_hi)
	or	a, (hl)
	ld	(hl), a
	ret
1$:
	ld	a, (hl)
	and	a, #0xF0
	ld	(hl), a
	ld	a, (mk_lo)
	or	a, (hl)
	ld	(hl), a
	ret

; ---------------------------------------------------------------------------
; void glyph1(const u8 *g)   HL = 3×5 の字形(5 バイト、下位 3bit。bit2 が左)。g_rx, g_ry の位置に g_color で描く
;   倍率 1 の文字用。画面内(x <= 61, y <= 43)であること(hud.c が確かめる)
;   列ごとに縦に描く: 先に 3 列それぞれの「5 行分のビット」を作り、番地は 1 回だけ求める。
;   次の列へは、いまの列が偶数なら同じバイトの右半分、奇数なら次のバイト(+8)の左半分
; ---------------------------------------------------------------------------
	.area	_DATA
gl_col:		.ds	3	; 列 0, 1, 2 のビット(bit0 = 一番上の行)
	.area	_CODE
_glyph1::
	; 列ごとのビット: 下の行から順に、bit0 → 列 2、bit1 → 列 1、bit2 → 列 0 へ送り込む
	ld	de, #4
	add	hl, de			; 一番下の行
	ld	e, #5
1$:
	ld	a, (hl)
	dec	hl
	rra
	rl	d			; 列 2
	rra
	rl	c			; 列 1
	rra
	rl	b			; 列 0
	dec	e
	jr	nz, 1$
	ld	a, b
	ld	(gl_col), a
	ld	a, c
	ld	(gl_col + 1), a
	ld	a, d
	ld	(gl_col + 2), a
	ld	a, (_g_color)
	and	a, #0x0F
	ld	(gl_lo + 1), a
	add	a, a
	add	a, a
	add	a, a
	add	a, a
	ld	(gl_hi + 1), a
	ld	a, (_g_rx)
	ld	b, a
	ld	a, (_g_ry)
	ld	c, a
	PADDR
	ld	e, b			; E の bit0 = いまの列の偶奇
	ld	a, (gl_col)
	call	gl_one
	ld	a, (gl_col + 1)
	call	gl_one
	ld	a, (gl_col + 2)
	; そのまま gl_one へ

; 1 列: A = ビット、HL = 一番上のバイト、E の bit0 = 列の偶奇。描いたら HL・E を次の列へ進める
gl_one:
	push	hl
	ld	c, a
	ld	b, #5
	bit	0, e
	jr	nz, glx5
glx2:
	; 偶数の列: 上位 4bit
	srl	c
	jr	nc, glx3
	ld	a, (hl)
	and	a, #0x0F
gl_hi:
	or	a, #0			; 色 << 4(書き換える)
	ld	(hl), a
glx3:
	inc	l
	ld	a, l
	and	a, #7
	jr	nz, glx4
	inc	h			; 帯をまたぐ
	ld	a, l
	sub	a, #8
	ld	l, a
glx4:
	djnz	glx2
	pop	hl
	inc	e			; 次の列は同じバイトの右半分
	ret
glx5:
	; 奇数の列: 下位 4bit
	srl	c
	jr	nc, glx6
	ld	a, (hl)
	and	a, #0xF0
gl_lo:
	or	a, #0			; 色(書き換える)
	ld	(hl), a
glx6:
	inc	l
	ld	a, l
	and	a, #7
	jr	nz, glx7
	inc	h
	ld	a, l
	sub	a, #8
	ld	l, a
glx7:
	djnz	glx5
	pop	hl
	ld	a, l			; 次の列は次のバイト(+8)の左半分
	add	a, #8
	ld	l, a
	inc	e
	ret

; ---------------------------------------------------------------------------
; void char_big(void) — 倍率 g_cb_s の字形 g_cb_g(3 × 5、行ごとに 3bit)を (g_cb_x, g_cb_y) に g_color で描く(hud.c の char_draw)
;   列ごと(左から)に、縦につながった点(上から)を 1 つの長方形にして、画面(64 × 48)に切り詰めて塗る。
;   切り詰めは、もと hud.c の box と同じ(座標は符号つき 8bit、足し算は 8bit で桁あふれ)
; ---------------------------------------------------------------------------
	.area	_DATA
_g_cb_g::	.ds	2
_g_cb_x::	.ds	1
_g_cb_y::	.ds	1
_g_cb_s::	.ds	1
cb_cx:		.ds	1	; 今の列の左
cb_bits:	.ds	1	; 今の列のビット(4 → 2 → 1)

	.area	_CODE
_char_big::
	ld	a, (_g_cb_x)
	ld	(cb_cx), a
	ld	a, #4
	ld	(cb_bits), a
1$:
	ld	hl, (_g_cb_g)
	ld	c, #0			; C = 行
2$:
	ld	a, c
	cp	a, #5
	jr	nc, 8$
	ld	a, (cb_bits)
	and	a, (hl)
	jr	nz, 3$
	inc	hl
	inc	c
	jr	2$
3$:
	ld	b, c			; B = つながりの始まりの行
4$:
	inc	hl
	inc	c
	ld	a, c
	cp	a, #5
	jr	nc, 5$
	ld	a, (cb_bits)
	and	a, (hl)
	jr	nz, 4$
5$:
	push	hl
	push	bc
	call	cb_box
	pop	bc
	pop	hl
	jr	2$
8$:
	ld	a, (_g_cb_s)
	ld	b, a
	ld	a, (cb_cx)
	add	a, b
	ld	(cb_cx), a
	ld	a, (cb_bits)
	srl	a
	ld	(cb_bits), a
	jr	nz, 1$
	ret

; cb_box: B = 始まりの行、C = 終わりの行(含まない)→ 列 cb_cx、幅 g_cb_s の長方形を切り詰めて塗る
cb_box:
	ld	a, (_g_cb_s)
	ld	e, a			; E = 倍率
	ld	a, c
	sub	a, b
	ld	d, a			; D = 行数
	xor	a, a
	inc	b
	jr	12$
11$:
	add	a, e
12$:
	djnz	11$			; A = 始まりの行 × 倍率
	ld	hl, #_g_cb_y
	add	a, (hl)
	ld	l, a			; L = y
	xor	a, a
	ld	b, d
	inc	b
	jr	14$
13$:
	add	a, e
14$:
	djnz	13$			; A = 高さ
	add	a, l
	ld	d, a			; D = y1
	ld	a, (cb_cx)
	ld	c, a			; C = x
	add	a, e
	ld	b, a			; B = x1
	; x < 0 → 0、y < 0 → 0、x1 > 64 → 64、y1 > 48 → 48(符号つき: 上位ビットを反転して符号なしで比べる)
	bit	7, c
	jr	z, 21$
	ld	c, #0
21$:
	bit	7, l
	jr	z, 22$
	ld	l, #0
22$:
	ld	a, b
	xor	a, #0x80
	cp	a, #0xC1		; x1 > 64
	jr	c, 23$
	ld	b, #64
23$:
	ld	a, d
	xor	a, #0x80
	cp	a, #0xA9		; y1 > 40
	jr	c, 24$
	ld	d, #40
24$:
	; x >= x1 か y >= y1 なら塗らない
	ld	a, c
	xor	a, #0x80
	ld	h, a
	ld	a, b
	xor	a, #0x80
	cp	a, h
	ret	c
	ret	z
	ld	a, l
	xor	a, #0x80
	ld	h, a
	ld	a, d
	xor	a, #0x80
	cp	a, h
	ret	c
	ret	z
	ld	a, c
	ld	(_g_rx), a
	ld	a, b
	sub	a, c
	ld	(_g_rw), a
	ld	a, l
	ld	(_g_ry), a
	ld	a, d
	sub	a, l
	ld	(_g_rh), a
	jp	_rect_fill
