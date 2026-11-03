; xf.s — モデルの頂点の変換(指示書 8.2 / 8.3)
;
; モデルの頂点は 8 ビット(i8、単位はモデルごと)、行列も 8 ビット(±127 = ±1.0)にして、MULUB(14 サイクル)だけで回す。
; R800 に符号付きの掛け算は無いので、頂点も行列の要素も +128 して符号なしで掛ける:
;   Σ(m - 128)(v - 128) = Σ m v - 128 Σ v - 128 Σ m + 3 * 128^2
; - 128 Σ v は頂点ごとに 1 回(3 行で同じ)、- 128 Σ m + 定数は行ごとに 1 回(xf_set の K)で済む。
; 行列の要素はコードの即値に書き込む(R800 はデータのメモリアクセスが重く、即値の読み出しは命令の読み出しと一緒に済む)。
; 結果は push で後ろから書く(XV + n * 10 から手前へ)。頂点は最後から処理するので、並びは元のまま。
; SP を変換バッファに向けたまま割り込みを受けても、書かれるのはこれから書く手前の所なので壊れない
; (XV の手前 0xE100-0xE1FF は空けてある)。

	.module	xf
	.r800
	.include "r800.inc"
	.include "pscale.inc"

	.globl	z2q, _sin_tab, _cm8

XV	= 0xE200		; 変換と投影の結果(記録 10 バイト × 128 まで: sx, sy, x, y, z。0xE200-0xE6FF)

	.area	_DATA
_g_xf_src::	.ds	2	; 頂点の並びの先頭
_g_xf_n::	.ds	1	; 頂点の数
_g_xf_t::	.ds	6	; 平行移動(カメラ空間、8.8。xf_trans で即値へ)
xf_sp:		.ds	2
my_o:		.ds	2
my_s:		.ds	1
my_c:		.ds	1
my_t:		.ds	1

	.area	_CODE

; void xf_set(const i8 *m)   HL = 行列(行 0 = 右、行 1 = 上、行 2 = 奥。各 3 要素)
_xf_set::
	ld	de, #0
	ld	a, (hl)
	inc	hl
	xor	a, #0x80
	ld	(xm00 + 1), a
	ld	e, a
	ld	a, (hl)
	inc	hl
	xor	a, #0x80
	ld	(xm10 + 1), a
	add	a, e
	ld	e, a
	jr	nc, 11$
	inc	d
11$:
	ld	a, (hl)
	inc	hl
	xor	a, #0x80
	ld	(xm20 + 1), a
	add	a, e
	ld	e, a
	jr	nc, 12$
	inc	d
12$:
	; K = 0xC000 - (DE << 7)
	ld	a, e
	rrca
	and	a, #0x80
	ld	c, a
	srl	d
	ld	a, e
	rra
	ld	b, a
	xor	a, a
	sub	a, c
	ld	(xk0 + 1), a
	ld	a, #0xC0
	sbc	a, b
	ld	(xk0 + 2), a
	ld	de, #0
	ld	a, (hl)
	inc	hl
	xor	a, #0x80
	ld	(xm01 + 1), a
	ld	e, a
	ld	a, (hl)
	inc	hl
	xor	a, #0x80
	ld	(xm11 + 1), a
	add	a, e
	ld	e, a
	jr	nc, 21$
	inc	d
21$:
	ld	a, (hl)
	inc	hl
	xor	a, #0x80
	ld	(xm21 + 1), a
	add	a, e
	ld	e, a
	jr	nc, 22$
	inc	d
22$:
	; K = 0xC000 - (DE << 7)
	ld	a, e
	rrca
	and	a, #0x80
	ld	c, a
	srl	d
	ld	a, e
	rra
	ld	b, a
	xor	a, a
	sub	a, c
	ld	(xk1 + 1), a
	ld	a, #0xC0
	sbc	a, b
	ld	(xk1 + 2), a
	ld	de, #0
	ld	a, (hl)
	inc	hl
	xor	a, #0x80
	ld	(xm02 + 1), a
	ld	e, a
	ld	a, (hl)
	inc	hl
	xor	a, #0x80
	ld	(xm12 + 1), a
	add	a, e
	ld	e, a
	jr	nc, 31$
	inc	d
31$:
	ld	a, (hl)
	inc	hl
	xor	a, #0x80
	ld	(xm22 + 1), a
	add	a, e
	ld	e, a
	jr	nc, 32$
	inc	d
32$:
	; K = 0xC000 - (DE << 7)
	ld	a, e
	rrca
	and	a, #0x80
	ld	c, a
	srl	d
	ld	a, e
	rra
	ld	b, a
	xor	a, a
	sub	a, c
	ld	(xk2 + 1), a
	ld	a, #0xC0
	sbc	a, b
	ld	(xk2 + 2), a
	ret

; smul: A, E(±127)→ A = (A * E) >> 7。B・C・HL を壊す
smul:
	ld	c, a
	or	a, a
	jp	p, 1$
	neg
1$:
	ld	b, a
	ld	a, e
	xor	a, c
	ld	c, a		; C の bit7 = 符号
	ld	a, e
	or	a, a
	jp	p, 2$
	neg
2$:
	MULUB_A_B
	add	hl, hl
	ld	a, h
	bit	7, c
	ret	z
	neg
	ret

; sincos8: sin_tab[HL 番目]/2 を A へ(±127)
sincos8:
	add	hl, hl
	ld	de, #_sin_tab
	add	hl, de
	ld	a, (hl)
	inc	hl
	ld	h, (hl)
	sra	h
	rra
	bit	0, h
	jr	nz, 1$		; 負(上位の下位ビットが 1)
	cp	a, #0x80
	ret	c
	ld	a, #127
	ret
1$:
	cp	a, #0x81
	ret	nc
	ld	a, #0x81
	ret

; void mat_y(u8 yaw, i8 *out)   A = yaw、DE = 出力。cm8 × ヨー。ローカルの x = (c, 0, -s)、z = (s, 0, c)
_mat_y::
	push	ix
	push	iy
	ld	(my_o), de
	ld	l, a
	ld	h, #0
	push	hl
	call	sincos8
	ld	(my_s), a
	pop	hl
	ld	de, #64
	add	hl, de
	call	sincos8
	ld	(my_c), a
	ld	ix, #_cm8
	ld	iy, (my_o)
	ld	d, #3
my_loop:
	push	de
	; lx = a*c - d*s
	ld	a, (my_c)
	ld	e, 0 (ix)
	call	smul
	ld	(my_t), a
	ld	a, (my_s)
	ld	e, 2 (ix)
	call	smul
	ld	e, a
	ld	a, (my_t)
	sub	a, e
	ld	0 (iy), a
	ld	a, 1 (ix)
	ld	1 (iy), a
	; lz = a*s + d*c
	ld	a, (my_s)
	ld	e, 0 (ix)
	call	smul
	ld	(my_t), a
	ld	a, (my_c)
	ld	e, 2 (ix)
	call	smul
	ld	e, a
	ld	a, (my_t)
	add	a, e
	ld	2 (iy), a
	ld	de, #3
	add	ix, de
	add	iy, de
	pop	de
	dec	d
	jr	nz, my_loop
	pop	iy
	pop	ix
	ret

; void xf_shift(u8 sh)   A = 右シフトの回数(0〜3): 単位 1/2m = 0、1/4m = 1、1/8m = 2、1/16m = 3
_xf_shift::
	ld	b, a
	ld	a, #3
	sub	a, b
	add	a, a
	add	a, a		; 飛ばすバイト数(sra h + rr l = 4 バイト)
	ld	(xs0 + 1), a
	ld	(xs1 + 1), a
	ld	(xs2 + 1), a
	ret

; void xf_trans(void)   g_xf_t の平行移動を即値へ
_xf_trans::
	ld	hl, (_g_xf_t)
	ld	(xt0 + 1), hl
	ld	hl, (_g_xf_t + 2)
	ld	(xt1 + 1), hl
	ld	hl, (_g_xf_t + 4)
	ld	(xt2 + 1), hl
	ret

; void xf_verts(void)   g_xf_src の g_xf_n 個の頂点(i8 × 3)を変換して投影し、XV へ。裏の HL = 読む所、裏の B = 残り
;   ニアクリップ面より手前の点は sy = 0x7FFF。関数を呼ばず、一時変数をメモリに置かない(project2 の 1/3 の時間で済む)
_xf_verts::
	ld	a, (_g_xf_n)
	or	a, a
	ret	z
	push	ix
	push	iy
	ld	(xf_sp), sp
	ld	c, a
	ld	b, #0
	ld	h, b
	ld	l, c
	add	hl, hl
	add	hl, bc
	push	hl		; 3n
	ld	h, b
	ld	l, c
	add	hl, hl
	add	hl, hl
	add	hl, bc
	add	hl, hl		; 10n
	ld	de, #XV
	add	hl, de
	pop	de
	ld	sp, hl		; 書き終わりの番地から手前へ
	ld	hl, (_g_xf_src)
	add	hl, de
	dec	hl
	ld	b, a
	exx
xf_loop:
	exx
	ld	a, (hl)
	dec	hl
	xor	a, #0x80
	ld	ixl, a		; z
	ld	a, (hl)
	dec	hl
	xor	a, #0x80
	ld	ixh, a		; y
	ld	a, (hl)
	dec	hl
	xor	a, #0x80	; x
	exx
	ld	b, a
	ld	c, ixh
	ld	e, ixl
	; 128 Σ v を IY へ
	ld	h, #0
	add	a, c
	rl	h
	add	a, e
	jr	nc, 1$
	inc	h
1$:
	ld	l, a
	rrca
	and	a, #0x80
	ld	iyl, a
	srl	h
	ld	a, l
	rra
	ld	iyh, a
xm22:	ld	a, #0
	MULUB_A_E
	ex	de, hl
xm02:	ld	a, #0
	MULUB_A_B
	add	hl, de
	ex	de, hl
xm12:	ld	a, #0
	MULUB_A_C
	add	hl, de
	ld	a, l
	sub	a, iyl
	ld	l, a
	ld	a, h
	sbc	a, iyh
	ld	h, a
xk2:	ld	de, #0
	add	hl, de
xs2:	jr	12$
12$:
	sra	h
	rr	l
	sra	h
	rr	l
	sra	h
	rr	l
xt2:	ld	de, #0
	add	hl, de
	push	hl
	ld	e, ixl
xm21:	ld	a, #0
	MULUB_A_E
	ex	de, hl
xm01:	ld	a, #0
	MULUB_A_B
	add	hl, de
	ex	de, hl
xm11:	ld	a, #0
	MULUB_A_C
	add	hl, de
	ld	a, l
	sub	a, iyl
	ld	l, a
	ld	a, h
	sbc	a, iyh
	ld	h, a
xk1:	ld	de, #0
	add	hl, de
xs1:	jr	11$
11$:
	sra	h
	rr	l
	sra	h
	rr	l
	sra	h
	rr	l
xt1:	ld	de, #0
	add	hl, de
	push	hl
	ld	e, ixl
xm20:	ld	a, #0
	MULUB_A_E
	ex	de, hl
xm00:	ld	a, #0
	MULUB_A_B
	add	hl, de
	ex	de, hl
xm10:	ld	a, #0
	MULUB_A_C
	add	hl, de
	ld	a, l
	sub	a, iyl
	ld	l, a
	ld	a, h
	sbc	a, iyh
	ld	h, a
xk0:	ld	de, #0
	add	hl, de
xs0:	jr	10$
10$:
	sra	h
	rr	l
	sra	h
	rr	l
	sra	h
	rr	l
xt0:	ld	de, #0
	add	hl, de
	; HL = x。積は終わったので BC・DE・IX・IY は自由に使える
	pop	de		; y
	pop	bc		; z
	push	bc
	push	de
	push	hl		; 記録の +4 = V3
	bit	7, b
	jr	nz, 20$
	ld	a, b
	or	a, a
	jr	nz, 21$
	bit	7, c
	jr	nz, 21$
20$:
	ld	hl, #0x7FFF	; ニアクリップ面より手前
	push	hl
	push	hl
	jp	22$
21$:
	ld	a, h
	ld	ixh, a
	ld	a, l
	ld	ixl, a
	ld	h, b
	ld	l, c
	push	de
	call	z2q
	pop	de
	ld	b, h
	ld	c, l
	ex	de, hl		; HL = y
	PSCALE
	ld	hl, #320
	or	a, a
	sbc	hl, de
	push	hl		; sy
	ld	a, ixh
	ld	h, a
	ld	a, ixl
	ld	l, a
	PSCALE
	ld	hl, #512
	add	hl, de
	push	hl		; sx
22$:
	exx
	dec	b
	exx
	jp	nz, xf_loop
	ld	sp, (xf_sp)
	pop	iy
	pop	ix
	ret
