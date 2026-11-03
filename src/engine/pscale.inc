; PSCALE: DE = clamp((HL * BC) >> 14, ±15000)(HL 符号付き、BC = q)。BC は保つ。A・HL・F を壊す
;   負の数は絶対値で掛けて最後に符号を戻す(0 へ向けて切り捨て)。呼び出しの多い所(1 フレーム 170〜240 回)なので展開する
	.macro	PSCALE	?neg, ?sat, ?satn, ?done
	bit	7, h
	jr	nz, neg
	MULUW_HL_BC			; DE:HL
	ld	a, d
	cp	a, #0x0E
	jr	nc, sat			; 14336 以上は飽和
	add	hl, hl			; DE:HL >> 14 → DE(= DE << 2 | H >> 6)
	rl	e
	rl	d
	add	hl, hl
	rl	e
	rl	d
	jr	done
sat:
	ld	de, #15000
	jr	done
neg:
	xor	a, a
	sub	a, l
	ld	l, a
	sbc	a, a
	sub	a, h
	ld	h, a
	MULUW_HL_BC
	ld	a, d
	cp	a, #0x0E
	jr	nc, satn
	add	hl, hl
	rl	e
	rl	d
	add	hl, hl
	rl	e
	rl	d
	xor	a, a
	sub	a, e
	ld	e, a
	sbc	a, a
	sub	a, d
	ld	d, a
	jr	done
satn:
	ld	de, #-15000
done:
	.endm

