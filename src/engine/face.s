; face.s — モデルの面の振り分けと当たり矩形(view.c の mesh_draw から呼ぶ)
;
; C で書いていたときは、裏表の判定の 32 ビットの掛け算(SDCC のライブラリ)と構造体の読み出しで、
; 4 面のボス戦の CPU 時間の 15% を使っていた。掛け算は MULUW(符号なし 16×16)に符号を付けて済ませる。

	.module	face
	.r800
	.include "r800.inc"

	.globl	_scr, _raster, _g_perf_polys, _face_near, fill
	.globl	_cm8, _cam_yaw, _g_obj_yaw, _g_lod_min, _g_perf_verts, _hit_add
	.globl	_xf_set, _xf_shift, _xf_trans, _xf_verts, _g_xf_t, _g_xf_src, _g_xf_n
	.globl	_draw_model, _g_dm_rects, _g_dm_n, _g_dm_flash, _g_dm_id, _g_dm_hit, _g_dm_grow, _g_dm_thin, _g_dm_deco

XV	= 0xE200		; 変換と投影の結果(xf.s。記録 10 バイト: sx, sy, x, y, z)

	.area	_DATA
_g_fd_nf::	.ds	1	; 面の数
_g_fd_lod::	.ds	1	; 0 でなければ細部の面(hdr の bit7)を省く
_g_fd_flash::	.ds	1	; 0 でなければこの色で塗る
_g_hb::		.ds	8	; hit_bounds の結果: x0, x1, y0, y1(i16)
_g_tx0::	.ds	2	; tilt_rows の入力
_g_txf::	.ds	2
_g_ts::		.ds	2
_g_trnd::	.ds	2
md_mesh:	.ds	2
md_c:		.ds	2
md_m:		.ds	2
_g_md_id::	.ds	1	; mesh_draw の hit_id(hit_add が読む)
md_zm:		.ds	1
md_r384:	.ds	2
md_lod:		.ds	1
fd_f:		.ds	2
fd_n:		.ds	1
fd_near:	.ds	1
fd_p:		.ds	2
fd_q:		.ds	2
fd_r:		.ds	2
fd_s:		.ds	2
fd_a:		.ds	2
fd_b:		.ds	2
fd_c:		.ds	2
fd_m:		.ds	4

	.area	_CODE

	.macro	SRA2_HL
	sra	h
	rr	l
	sra	h
	rr	l
	.endm

; ---------------------------------------------------------------------------
; void faces_draw(const Face *f)   HL = f。数と細部と色は g_fd_nf / g_fd_lod / g_fd_flash
;   ニアクリップ面より手前の頂点を含む面は face_near(f)(C)へ。ほかは画面上の向きで裏を捨てて raster
; ---------------------------------------------------------------------------
_faces_draw::
	ld	(fd_f), hl
	ld	a, (_g_fd_nf)
	or	a, a
	ret	z
	push	ix
fd_loop:
	ld	hl, (fd_f)
	ld	a, (hl)
	bit	7, a
	jr	z, 1$
	ld	a, (_g_fd_lod)
	or	a, a
	jp	nz, fd_next
	ld	a, (hl)
1$:
	and	a, #7
	ld	(fd_n), a
	xor	a, a
	ld	(fd_near), a
	inc	hl
	inc	hl
	call	vrec
	ld	(fd_p), de
	call	vrec
	ld	(fd_q), de
	call	vrec
	ld	(fd_r), de
	ld	a, (fd_n)
	cp	a, #4
	jr	nz, 2$
	call	vrec
	ld	(fd_s), de
2$:
	ld	a, (fd_near)
	or	a, a
	jr	z, 3$
	ld	hl, (fd_f)
	call	_face_near
	jp	fd_next
3$:
	; cross = a * b - c * d。a = (qsx - psx) >> 2, b = (rsy - psy) >> 2, c = (qsy - psy) >> 2, d = (rsx - psx) >> 2
	ld	ix, (fd_p)
	ld	e, 0 (ix)
	ld	d, 1 (ix)
	ld	c, 2 (ix)
	ld	b, 3 (ix)
	ld	ix, (fd_q)
	ld	l, 0 (ix)
	ld	h, 1 (ix)
	or	a, a
	sbc	hl, de
	SRA2_HL
	ld	(fd_a), hl
	ld	l, 2 (ix)
	ld	h, 3 (ix)
	or	a, a
	sbc	hl, bc
	SRA2_HL
	ld	(fd_c), hl
	ld	ix, (fd_r)
	ld	l, 2 (ix)
	ld	h, 3 (ix)
	or	a, a
	sbc	hl, bc
	SRA2_HL
	ld	(fd_b), hl
	ld	l, 0 (ix)
	ld	h, 1 (ix)
	or	a, a
	sbc	hl, de
	SRA2_HL
	ld	bc, (fd_c)
	call	smul32
	ld	(fd_m), hl
	ld	(fd_m + 2), de
	ld	hl, (fd_a)
	ld	bc, (fd_b)
	call	smul32
	ld	bc, (fd_m)
	or	a, a
	sbc	hl, bc
	ex	de, hl			; DE = 下位、HL = 上位
	ld	bc, (fd_m + 2)
	sbc	hl, bc			; 積は 2^26 未満なので桁あふれしない
	jp	m, fd_next
	jr	nz, 4$
	ld	a, d
	or	a, e
	jp	z, fd_next		; 0 は裏扱い(C と同じ)
4$:
	ld	de, #_scr
	ld	hl, (fd_p)
	ldi
	ldi
	ldi
	ldi
	ld	hl, (fd_q)
	ldi
	ldi
	ldi
	ldi
	ld	hl, (fd_r)
	ldi
	ldi
	ldi
	ldi
	ld	a, (fd_n)
	cp	a, #4
	jr	nz, 5$
	ld	hl, (fd_s)
	ldi
	ldi
	ldi
	ldi
5$:
	ld	hl, #_g_perf_polys
	inc	(hl)
	ld	a, (_g_fd_flash)
	or	a, a
	jr	nz, 6$
	ld	hl, (fd_f)
	inc	hl
	ld	a, (hl)
6$:
	ld	l, a
	ld	a, (fd_n)
	call	_raster
fd_next:
	ld	hl, (fd_f)
	ld	de, #6
	add	hl, de
	ld	(fd_f), hl
	ld	hl, #_g_fd_nf
	dec	(hl)
	jp	nz, fd_loop
	pop	ix
	ret

; HL = 頂点番号の番地 → DE = XV の記録、HL は次の番号へ。sy が 0x7FFF(ニア面より手前)なら fd_near = 1
vrec:
	ld	a, (hl)
	inc	hl
	push	hl
	ld	l, a
	ld	h, #0
	ld	e, l
	ld	d, h
	add	hl, hl
	add	hl, hl
	add	hl, de
	add	hl, hl
	ld	de, #XV + 2
	add	hl, de			; HL = sy
	ld	a, (hl)
	inc	a
	jr	nz, 1$
	inc	hl
	ld	a, (hl)
	dec	hl
	cp	a, #0x7F
	jr	nz, 1$
	ld	a, #1
	ld	(fd_near), a
1$:
	dec	hl
	dec	hl
	ex	de, hl
	pop	hl
	ret

; DE:HL = HL × BC(符号付き 16 ビット)
smul32:
	ld	a, h
	xor	a, b
	push	af			; bit7 = 積の符号
	bit	7, h
	jr	z, 1$
	xor	a, a
	sub	a, l
	ld	l, a
	sbc	a, a
	sub	a, h
	ld	h, a
1$:
	bit	7, b
	jr	z, 2$
	xor	a, a
	sub	a, c
	ld	c, a
	sbc	a, a
	sub	a, b
	ld	b, a
2$:
	MULUW_HL_BC
	pop	af
	ret	p
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
	ret

; ---------------------------------------------------------------------------
; void hit_bounds(u8 nv)   A = 頂点の数。XV の先頭 nv 個のうちニア面より奥の頂点の sx, sy の最小と最大を g_hb へ
;   1 つも無ければ x0 = 32767 > x1 = -32767 のまま
; ---------------------------------------------------------------------------
_hit_bounds::
	push	ix
	ld	b, a
	ld	hl, #0xFFFF		; 32767 に 0x8000 を足した値(符号なしで比べる)
	ld	(_g_hb + 0), hl
	ld	(_g_hb + 4), hl
	ld	hl, #0x0001		; -32767 に 0x8000 を足した値
	ld	(_g_hb + 2), hl
	ld	(_g_hb + 6), hl
	ld	a, b
	or	a, a
	jr	z, hb_end
	ld	ix, #XV
hb_loop:
	ld	a, 2 (ix)
	inc	a
	jr	nz, 1$
	ld	a, 3 (ix)
	cp	a, #0x7F
	jr	z, hb_next
1$:
	ld	e, 0 (ix)
	ld	a, 1 (ix)
	xor	a, #0x80
	ld	d, a
	ld	hl, (_g_hb + 0)
	or	a, a
	sbc	hl, de
	jr	c, 2$
	ld	(_g_hb + 0), de
2$:
	ld	hl, (_g_hb + 2)
	or	a, a
	sbc	hl, de
	jr	nc, 3$
	ld	(_g_hb + 2), de
3$:
	ld	e, 2 (ix)
	ld	a, 3 (ix)
	xor	a, #0x80
	ld	d, a
	ld	hl, (_g_hb + 4)
	or	a, a
	sbc	hl, de
	jr	c, 4$
	ld	(_g_hb + 4), de
4$:
	ld	hl, (_g_hb + 6)
	or	a, a
	sbc	hl, de
	jr	nc, hb_next
	ld	(_g_hb + 6), de
hb_next:
	ld	de, #10
	add	ix, de
	djnz	hb_loop
hb_end:
	ld	hl, #_g_hb + 1
	ld	b, #4
5$:
	ld	a, (hl)
	xor	a, #0x80
	ld	(hl), a
	inc	hl
	inc	hl
	djnz	5$
	pop	ix
	ret

; void span_fill(u8 row0, u8 n)   A = 最初の行、L = 行数。span_a[r] と span_b[r] の間を g_color で塗る(raster.s の fill)
_span_fill::
	ld	c, a
	ld	b, l
	jp	fill

; ---------------------------------------------------------------------------
; void tilt_rows(u8 *t)   HL = 書き込み先(40 行)
;   x = g_tx0 / 2 + g_txf / 256(8.8 の 24 ビット)から始めて、行ごとに t = clamp((x + g_trnd) >> 8, 0, 64)、x += g_ts(8.8)
;   傾いた空の境目の列(view.c の sky_tilt)。E:H:L = x、D:B:C = 増分、IY = 書き込み先、IXL = 残りの行
; ---------------------------------------------------------------------------
_tilt_rows::
	push	ix
	push	iy
	push	hl
	pop	iy
	ld	a, (_g_trnd)
	ld	(tr_l + 1), a
	ld	a, (_g_trnd + 1)
	ld	(tr_h + 1), a
	ld	bc, (_g_ts)
	ld	a, b
	rla
	sbc	a, a
	ld	d, a
	; x = (g_tx0 << 8) / 2 + g_txf(24 ビット)
	ld	hl, (_g_tx0)
	ld	e, h
	ld	h, l
	ld	l, #0
	sra	e
	rr	h
	rr	l
	push	bc
	ld	bc, (_g_txf)
	ld	a, b
	rla
	sbc	a, a			; g_txf の符号の拡張
	add	hl, bc
	adc	a, e
	ld	e, a
	pop	bc
	ld	ixl, #40
tr_loop:
	ld	a, l
tr_l:
	add	a, #0			; 丸めの下位(書き換える)
	ld	a, h
tr_h:
	adc	a, #0			; 丸めの上位(書き換える)
	ld	0 (iy), a
	ld	a, e
	adc	a, #0
	jr	z, 3$			; 上位が 0: 0..255
	rla
	ld	a, #64
	jr	nc, 4$			; 正の大きな値 → 64
	xor	a, a			; 負 → 0
	jr	4$
3$:
	ld	a, 0 (iy)
	cp	a, #64
	jr	c, 5$
	ld	a, #64
4$:
	ld	0 (iy), a
5$:
	inc	iy
	add	hl, bc
	ld	a, e
	adc	a, d
	ld	e, a
	dec	ixl
	jr	nz, tr_loop
	pop	iy
	pop	ix
	ret

; ---------------------------------------------------------------------------
; u8 mesh_draw(const u8 *mesh, const V3 *c, const i8 *m, u8 flash, u8 hit_id)
;   HL = mesh, DE = c、スタックに m, flash, hit_id(呼ばれた側が片付ける)。描いたら 1
;   視野の外を捨て、LOD を決め、LOD 2 は矩形(draw_model)、ほかは頂点を変換して面を塗る。
;   C で書いていたときと同じ判定(16 ビットの桁あふれも同じ。lim は遠い大きな物で負になり、そこで切られる)
; ---------------------------------------------------------------------------
MESH_HDR = 8
NEAR_Z	= 128

_mesh_draw::
	ld	(md_mesh), hl
	ld	(md_c), de
	pop	bc			; 戻り番地
	pop	hl
	ld	(md_m), hl
	pop	de			; E = flash、D = hit_id
	push	bc
	ld	a, e
	ld	(_g_fd_flash), a
	ld	a, d
	ld	(_g_md_id), a
	push	ix
	push	iy
	ld	ix, (md_c)		; +0 x、+2 y、+4 z
	ld	iy, (md_mesh)		; +0 nv、+1 nf、+2 sh、+3 r、+4 nrect、+5 矩形、+7 nv(LOD 1)
	; r * 384
	ld	a, 3 (iy)
	ld	d, a
	ld	e, #0
	srl	a
	ld	h, a
	ld	a, #0
	rra
	ld	l, a
	add	hl, de
	ld	(md_r384), hl
	; 奥: z < -(r << 8) と z >= 0x7E00 を捨てる。zm = z < 0 ? 0 : z >> 8
	ld	h, 5 (ix)
	bit	7, h
	jr	nz, 1$
	ld	a, h
	cp	a, #0x7E
	jp	nc, md_no
	jr	2$
1$:
	ld	a, 3 (iy)
	add	a, h
	jp	m, md_no
	xor	a, a
2$:
	ld	(md_zm), a
	; 左右: lim = z + r * 384
	ld	l, 4 (ix)
	ld	h, 5 (ix)
	ld	de, (md_r384)
	add	hl, de
	bit	7, h
	jp	nz, md_no
	ld	e, 0 (ix)
	ld	d, 1 (ix)
	call	md_out
	jp	c, md_no
	; 上下: lim = (z >> 1) + (z >> 3) + r * 384
	ld	l, 4 (ix)
	ld	h, 5 (ix)
	sra	h
	rr	l
	ld	e, l
	ld	d, h
	sra	h
	rr	l
	sra	h
	rr	l
	add	hl, de
	ld	de, (md_r384)
	add	hl, de
	bit	7, h
	jp	nz, md_no
	ld	e, 2 (ix)
	ld	d, 3 (ix)
	call	md_out
	jp	c, md_no
	; LOD: zm * 3 <= r * 16 → 0、<= r * 32 → 1、ほかは 2
	ld	a, (md_zm)
	ld	l, a
	ld	h, #0
	ld	e, l
	ld	d, h
	add	hl, hl
	add	hl, de
	ex	de, hl			; DE = zm * 3
	ld	l, 3 (iy)
	ld	h, #0
	add	hl, hl
	add	hl, hl
	add	hl, hl
	add	hl, hl			; HL = r * 16
	ld	b, #0
	or	a, a
	sbc	hl, de
	jr	nc, 3$
	add	hl, de
	add	hl, hl
	inc	b
	or	a, a
	sbc	hl, de
	jr	nc, 3$
	inc	b
	; LOD 2 は矩形があり、z >= NEAR_Z + 32 のときだけ
	ld	a, 4 (iy)
	or	a, a
	jr	z, 4$
	ld	a, 5 (ix)
	bit	7, a
	jr	nz, 4$
	or	a, a
	jr	nz, 3$
	ld	a, 4 (ix)
	cp	a, #NEAR_Z + 32
	jr	nc, 3$
4$:
	ld	b, #1
3$:
	ld	a, (_g_lod_min)
	cp	a, b
	jr	c, 5$
	ld	b, a
5$:
	ld	a, b
	ld	(md_lod), a
	cp	a, #2
	jp	nz, md_mesh_go
	; ---- LOD 2: 向き 8 方向の矩形
	ld	a, (_g_obj_yaw)
	ld	c, a
	ld	a, (_cam_yaw)
	sub	a, c
	add	a, #16
	rlca
	rlca
	rlca
	and	a, #7			; d
	ld	b, 4 (iy)		; nrect
	MULUB_A_B			; HL = d * nrect
	ld	e, l
	ld	d, h
	add	hl, hl
	add	hl, de
	add	hl, hl			; × 6
	ld	e, 5 (iy)
	ld	d, 6 (iy)
	add	hl, de
	ld	(_g_dm_rects), hl
	ld	a, 4 (iy)
	ld	(_g_dm_n), a
	ld	a, (_g_fd_flash)
	ld	(_g_dm_flash), a
	ld	a, (_g_md_id)
	ld	(_g_dm_id), a
	inc	a
	jr	z, 6$
	ld	a, #1
6$:
	ld	(_g_dm_hit), a
	xor	a, a
	ld	(_g_dm_grow), a
	ld	(_g_dm_thin), a
	inc	a
	ld	(_g_dm_deco), a
	ld	hl, (md_c)
	call	_draw_model
	jp	md_yes
md_mesh_go:
	; ---- 頂点を変換して面を塗る
	ld	hl, (md_m)
	ld	a, h
	or	a, l
	jr	nz, 7$
	ld	hl, #_cm8
7$:
	call	_xf_set
	ld	iy, (md_mesh)
	ld	a, 2 (iy)
	call	_xf_shift
	ld	hl, (md_c)
	ld	de, #_g_xf_t
	ldi
	ldi
	ldi
	ldi
	ldi
	ldi
	call	_xf_trans
	ld	iy, (md_mesh)
	ld	a, (md_lod)
	or	a, a
	ld	a, 0 (iy)
	jr	z, 8$
	ld	a, 7 (iy)
8$:
	ld	(_g_xf_n), a
	ld	e, a
	ld	d, #0
	ld	hl, (_g_perf_verts)
	add	hl, de
	ld	(_g_perf_verts), hl
	ld	de, #MESH_HDR
	push	iy
	pop	hl
	add	hl, de
	ld	(_g_xf_src), hl
	call	_xf_verts
	ld	iy, (md_mesh)
	ld	a, 1 (iy)
	ld	(_g_fd_nf), a
	ld	a, (md_lod)
	ld	(_g_fd_lod), a
	ld	l, 0 (iy)
	ld	h, #0
	ld	e, l
	ld	d, h
	add	hl, hl
	add	hl, de			; nv * 3
	ld	de, #MESH_HDR
	add	hl, de
	ex	de, hl			; DE = 面の並びまでの距離
	push	iy
	pop	hl
	add	hl, de
	call	_faces_draw
	ld	a, (_g_md_id)
	inc	a
	jr	z, md_yes
	ld	a, (_g_xf_n)
	ld	de, (md_c)
	call	_hit_add		; 当たり矩形(C)
md_yes:
	pop	iy
	pop	ix
	ld	a, #1
	ret
md_no:
	pop	iy
	pop	ix
	xor	a, a
	ret

; HL = lim(0 以上)、DE = v → |v| > lim ならキャリー
md_out:
	bit	7, d
	jr	nz, 1$
	or	a, a
	sbc	hl, de
	ret
1$:
	add	hl, de
	ld	a, h
	rla
	ret
