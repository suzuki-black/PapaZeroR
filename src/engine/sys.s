; sys.s — 割り込み(H.TIMI)・入力・PSG・タイマ
;
; ■ 割り込み(仕様書 7.6)
;   起動直後は BIOS の割り込み処理(ページ0)が垂直帰線ごとに H.TIMI(FD9Fh)を呼び、そこから htimi へ飛ぶ。
;   sys_page0_ram の後はページ0が自前の RAM になり、0x0038 の isr0 が S#0 を読んで htimi を呼ぶ。
;   htimi がすること:
;     ・g_tick(60Hz のフレームカウンタ)を +1
;     ・表示ページ切替の予約(g_flip_req)があり、前の切替から 2 ティック経っていれば
;       R#4 を書き換え、スプライトアトリビュートを転送(30fps が上限)
;     ・サウンドドライバの 1 ティック(sound_tick)
;
; ■ VDP の取り決め(ISR と本体の干渉を避ける)
;   本体はストリーム転送(vdp.s)を「切替の予約が消えてから」始め、送り切ってから予約を立てる。
;   つまり ISR が VRAM アドレスを設定するのは、本体が VDP を触っていない間だけ。
;   本体の 99h への 2 バイト書き込み(アドレス・レジスタ設定)は DI で囲む。
;
; ■ 入力(仕様書 2 章)
;   キーボード(PPI 直読み)とジョイスティック ポート1(PSG R#14/R#15)を毎フレーム読む。
;   BIOS ISR もキーボードを走査するので、読んでいる間は DI。

	.module	sys

	.globl	_g_snd_ok
	.globl	_g_spr_attr, _g_vdp_r1
	.globl	_g_seg2
	.globl	_pcm_mode, _pcm_req, _pcm_r0, _pcm_isr, _pcm_begin, _pcm_stop

; ページ2(0x8000-0xBFFF)のマッパーのセグメント(仕様書 7.3 のオーバーレイ)
SEG_SND	= 8			; 音のモジュール(効果音・FM の曲のドライバと曲。起動時に 1 回読み込む)
SND_TICK = 0x8000		; 音のモジュールの入口(modhead_snd.s)
SND_PLAY = 0x8003
SND_STOP = 0x8006
MOD_ADDR = 0x8000		; モジュールの先頭(0x8000: 入口の jp、0x8003: ゲームは Stage へのポインタ / 地形は 2 つ目の jp)
MOD_BSS	= 0xBC00		; モジュールの変数(読み込んだら 0 で埋める)。〜0xBFFF

H_TIMI	= 0xFD9F
; ページ3 の固定番地(常駐ローダーからも使う)
V_CART	= 0xE0F0		; カートリッジのスロット ID(ローダーが書く)
V_RAM	= 0xE0F1		; RAM のスロット ID(F000SSPP)
P0_BIOS	= 0xE0F2		; 起動時のページ0の基本スロット(BIOS)
P0_SEG	= 4			; ページ0に使うマッパーのセグメント(0-3 は起動時のページ0-3)

; ページ0を自前の RAM(V_RAM のスロット、セグメント P0_SEG)にする。
;   RAM は拡張スロットでもページ3と同じ基本スロットなので、拡張スロットのレジスタ(FFFF)はそのまま書ける
	.macro	P0_TO_RAM ?skip
	in	a, (0xA8)
	and	a, #0xFC
	ld	b, a
	ld	a, (V_RAM)
	and	a, #0x03
	or	a, b
	out	(0xA8), a
	ld	a, (V_RAM)
	bit	7, a
	jr	z, skip
	rrca
	rrca
	and	a, #0x03
	ld	b, a
	ld	a, (0xFFFF)
	cpl
	and	a, #0xFC
	or	a, b
	ld	(0xFFFF), a
skip:
	.endm

; ページ0を BIOS に戻す。基本スロットのレジスタだけ戻せばよい
;   (BIOS 側の拡張スロットのレジスタは触っていない。実機の BIOS はスロット 0-0)
	.macro	P0_TO_BIOS
	in	a, (0xA8)
	and	a, #0xFC
	ld	b, a
	ld	a, (P0_BIOS)
	or	a, b
	out	(0xA8), a
	.endm
SPR_BYTES = 19 * 4 + 1		; スプライト 19 枚分 + 終端(Y=208)。game.h の N_SPR と合わせる

	.area	_DATA
_g_tick::	.ds	2	; 60Hz ごとに +1
_g_flip_req::	.ds	1	; 1 = 次の垂直帰線で g_flip_page を表示する
_g_flip_page::	.ds	1	; R#4 に書く値(0 または 1)
_g_spr_live::	.ds	1	; 1 = 本体が VDP に触らない間(描画中と表示待ち)。このときだけ割り込みが照準を書く
_g_spr0_req::	.ds	1	; 1 = g_spr_attr の照準(スプライト 0 の Y, X)を次の割り込みで VRAM へ
flip_tick:	.ds	1	; 最後に切り替えたときの g_tick(下位)

	.area	_CODE

; ---------------------------------------------------------------------------
; void sys_install_isr(void)
; ---------------------------------------------------------------------------
_sys_install_isr::
	di
	ld	a, #0xC3		; JP htimi
	ld	(H_TIMI), a
	ld	hl, #htimi
	ld	(H_TIMI + 1), hl
	ld	a, #0xC9
	ld	(H_TIMI + 3), a
	ld	(H_TIMI + 4), a
	ei
	ret

htimi::
	ld	hl, (_g_tick)
	inc	hl
	ld	(_g_tick), hl
	ld	a, (_g_flip_req)
	or	a, a
	jr	z, 1$
	ld	a, (_g_tick)		; 前の切替から 2 ティック以上(30fps が上限)
	ld	hl, #flip_tick
	sub	a, (hl)
	cp	a, #2
	jr	c, 1$
	ld	a, (_g_tick)
	ld	(hl), a
	ld	a, (_g_flip_page)
	out	(0x99), a
	ld	a, #0x84		; R#4 = パターンジェネレータ
	out	(0x99), a
	xor	a, a
	out	(0x99), a
	ld	a, #0x8E		; R#14 = 0
	out	(0x99), a
	xor	a, a
	out	(0x99), a		; VRAM 0x1400(スプライトアトリビュート)へ書き込み
	ld	a, #0x54
	out	(0x99), a
	ld	hl, #_g_spr_attr
	ld	bc, #(SPR_BYTES << 8) | 0x98
	otir
	xor	a, a
	ld	(_g_flip_req), a
1$:
	; 照準だけ毎ティック動かす(描画の 20fps を待たない)。Y と X の 2 バイトだけ書く
	ld	a, (_g_spr_live)
	or	a, a
	jr	z, 2$
	ld	a, (_g_spr0_req)
	or	a, a
	jr	z, 2$
	xor	a, a
	ld	(_g_spr0_req), a
	out	(0x99), a
	ld	a, #0x8E		; R#14 = 0
	out	(0x99), a
	xor	a, a
	out	(0x99), a		; VRAM 0x1400(スプライト 0)
	ld	a, #0x54
	out	(0x99), a
	ld	a, (_g_spr_attr)
	out	(0x98), a
	ld	a, (_g_spr_attr + 1)
	out	(0x98), a
2$:
	; サウンドは音のモジュール(セグメント SEG_SND の 0x8000 = sndtick.c の sndm_tick)にある。ページ2を音のセグメントにしてから
	; 呼び、元に戻す。音のモジュールを読み込む前(起動の途中)は呼ばない
	ld	a, (_g_snd_ok)
	or	a, a
	ret	z
	ld	a, #SEG_SND
	out	(0xFE), a
	call	SND_TICK
	ld	a, (_g_seg2)
	out	(0xFE), a
	ret

; ---------------------------------------------------------------------------
; void bgm_play(u8 song)   A = 曲の番号(songs.h の SONG_。0 = 止める)
; void bgm_stop(void)
;   音のモジュールの sndm_play / sndm_stop を、ページ2を音のセグメントにして呼び、元に戻す
;   (割り込みが戻す先も音のセグメントにする: g_seg2 も切り替える)
; ---------------------------------------------------------------------------
_bgm_play::
	ld	c, a
	ld	a, (_g_seg2)
	push	af
	ld	a, #SEG_SND
	call	_sys_seg2
	ld	a, c
	call	SND_PLAY
	pop	af
	jp	_sys_seg2
_bgm_stop::
	ld	a, (_g_seg2)
	push	af
	ld	a, #SEG_SND
	call	_sys_seg2
	call	SND_STOP
	pop	af
	jp	_sys_seg2

; ---------------------------------------------------------------------------
; void sys_seg2(u8 seg) — ページ2のセグメントを切り替える(割り込みが戻せるよう g_seg2 に先に書く)
; ---------------------------------------------------------------------------
_sys_seg2::
	ld	(_g_seg2), a
	out	(0xFE), a
	ret

; ---------------------------------------------------------------------------
; void sys_page0_ram(void) — ページ0(0x0000-0x3FFF)を自前の RAM にする(起動時に 1 回)
;   ゲーム中は BIOS を呼ばない(入力・PSG・VDP はポート直接)ので、ページ0も使える 16KB にする。
;   0x0038 に自前の割り込み処理(isr0)、0x0100 に塗りの展開ブロック(raster.s)を置く。
;   BIOS が要るのはステージの読み込み(ENASLT)だけで、そのときは常駐ローダーがページ0を BIOS に戻す。
; ---------------------------------------------------------------------------
	.globl	_fillblk_tpl, _fillblk_end
_sys_page0_ram::
	di
	in	a, (0xA8)
	and	a, #0x03
	ld	(P0_BIOS), a
	ld	a, #P0_SEG
	out	(0xFC), a		; ページ0のセグメント(RAM スロットに切り替えたときに効く)
	P0_TO_RAM
	ld	a, #0xC3		; 0x0038: JP isr0
	ld	(0x0038), a
	ld	hl, #isr0
	ld	(0x0039), hl
	ld	hl, #_fillblk_end
	ld	de, #_fillblk_tpl
	or	a, a
	sbc	hl, de
	ld	b, h
	ld	c, l
	ex	de, hl
	ld	de, #0x0100
	ldir
	ei
	ret

; 分割画面(指示書 8.4)。上 160 ライン = SCREEN 3、下 52 ライン = SCREEN 5(ページ 1 = 8000h)。
;   R#19 の走査線割込みで下のモードへ、垂直帰線で上のモードへ戻す。割込みはこの 2 つが交互に来るので、どちらかを
;   split_phase で知って S#n を読まずに切り替える(S#1 を読む手順を先に踏むと 1 ライン近く遅れる)。
;   R800 からの VDP ポートは 1 回 8.7µs 空くので、5 レジスタで約 87µs = 1.4 ライン。乱れを見せないよう、最初の R#1 で
;   表示を止めて(黒)、モードを全部書いてから表示を戻す。遅れたときも上の画面の帯 4・5 は空なので黒く見えるだけ。
R0_TOP	= 0x10			; IE1 を立てたまま(M3-M5 = 0)
R0_BOT	= 0x16			; G4
R1_BOT	= 0x63			; 表示、IE0、16×16 拡大(スプライトは止めるので値は関係しない)、M2 = 0
R2_TOP	= 0x04			; 名前表 1000h
R2_BOT	= 0x3F			; 名前表 8000h(SCREEN 5 の 2 ページ目)
R8_TOP	= 0x08			; スプライトあり
R8_BOT	= 0x0A			; スプライトなし(SCREEN 3 と SCREEN 5 でスプライトのモードが違う。下では使わない)
SPLIT_LINE == 159		; R#19

	.macro	VREG val, reg
	ld	a, val
	out	(0x99), a
	ld	a, #0x80 + reg
	out	(0x99), a
	.endm

	.area	_DATA
_g_split::	.ds	1	; 1 = 分割画面を使う
split_phase::	.ds	1	; 0 = 次は走査線割込み、1 = 次は垂直帰線
_g_r1_cur::	.ds	1	; いま R#1 に入っている値(Z80 転送が IE0 を止めるときに使う)
_g_r1_mask::	.ds	1	; R#1 に掛けるマスク(ふだん 0xFF、声の間は IE0 を落とす 0xDF。main が起動時に 0xFF にする)
_g_r18_bot::	.ds	1	; 下の R#18
_g_r18_top::	.ds	1	; 上の R#18(被弾でゲーム画面を横に揺らす。ふだん 0)
_g_r2_bot::	.ds	1	; 下の名前表: 0x3F = 計器盤(8000h)、0x7F = 黒帯(18000h)
_g_split_t::	.ds	1	; 分割線を通ったときのシステムタイマの上位(1 カウント = 約 1ms)
	.area	_CODE

; void split_off(void) — 分割をやめる。IE1 を切り、たまった FH を落とす(立てたまま g_split だけ 0 にすると、
;   割込みの処理が S#1 を読まなくなり、割込みが入り続けて固まる)
_split_off::
	di
	xor	a, a
	ld	(_g_split), a
	ld	(split_phase), a
	VREG	#0, 0
	VREG	#1, 15
	in	a, (0x99)
	VREG	#0, 15
	ei
	ret

; 下のモードへ(AF だけ壊す)。pcm.s の声の割込みからも呼ぶ
split_to_bot::
	ld	a, (_g_r1_mask)
	and	a, #(R1_BOT & 0xBF)
	out	(0x99), a
	ld	a, #0x81
	out	(0x99), a
	VREG	#R0_BOT, 0
	ld	a, (_g_r2_bot)
	out	(0x99), a
	ld	a, #0x82
	out	(0x99), a
	VREG	#R8_BOT, 8
	ld	a, (_g_r18_bot)		; 被弾で計器盤を揺らす(0 の間は書かない)
	or	a, a
	jr	z, 1$
	out	(0x99), a
	ld	a, #0x80 + 18
	out	(0x99), a
1$:
	ld	a, (_g_r1_mask)
	and	a, #R1_BOT
	ld	(_g_r1_cur), a
	out	(0x99), a
	ld	a, #0x81
	out	(0x99), a
	in	a, (0xE7)
	ld	(_g_split_t), a
	ret
; 上のモードへ。垂直帰線の中なので順番は問わない
split_to_top::
	ld	a, (_g_r18_top)
	out	(0x99), a
	ld	a, #0x80 + 18
	out	(0x99), a
	VREG	#R0_TOP, 0
	VREG	#R2_TOP, 2
	VREG	#R8_TOP, 8
	ld	a, (_g_r1_mask)
	ld	hl, #_g_vdp_r1
	and	a, (hl)
	ld	(_g_r1_cur), a
	out	(0x99), a
	ld	a, #0x81
	out	(0x99), a
	ret

; 自前の割り込み処理(ページ0の 0x0038 から)。裏レジスタは使わない(描画側が exx を使うため)
isr0:
	push	af
	ld	a, (_pcm_mode)
	or	a, a
	jp	nz, _pcm_isr		; 声を鳴らしている間は走査線割込み(pcm.s)
	ld	a, (split_phase)
	or	a, a
	jr	nz, 5$
	ld	a, (_g_split)
	or	a, a
	jr	z, 5$
	call	split_to_bot
	ld	a, #1
	ld	(split_phase), a
	VREG	#1, 15			; S#1 を読んで FH を落とす
	in	a, (0x99)
	VREG	#0, 15
	pop	af
	ei
	ret
5$:
	in	a, (0x99)
	rlca
	jr	nc, 9$
	push	bc
	push	de
	push	hl
	push	ix
	push	iy
	xor	a, a
	ld	(split_phase), a
	ld	a, (_g_split)
	or	a, a
	call	nz, split_to_top
	call	htimi
	ld	a, (_pcm_req)
	or	a, a
	call	nz, _pcm_begin		; 声を頼まれていれば、ここから走査線割込みで鳴らす形に切り替える
	pop	iy
	pop	ix
	pop	hl
	pop	de
	pop	bc
9$:
	pop	af
	ei
	ret

; ---------------------------------------------------------------------------
; void wait_tick(void) — g_tick が変わるまで待つ
; ---------------------------------------------------------------------------
_wait_tick::
	ld	hl, #_g_tick
	ld	a, (hl)
1$:
	ei
	halt
	cp	a, (hl)
	jr	z, 1$
	ret

; ---------------------------------------------------------------------------
; u8 input_raw(void)
;   bit0=上 bit1=下 bit2=左 bit3=右(照準) bit4=A(射撃) bit5=B(前後切替)。1 = 押下
;   キーボード: カーソルキー / スペース=A / M・B=B(B ボタン相当キーは仕様書 2 章【要確認】)
;   ジョイスティック ポート1: 方向 / トリガ A / トリガ B
; ---------------------------------------------------------------------------
_input_raw::
	di
	in	a, (0xAA)
	and	a, #0xF0
	or	a, #8
	out	(0xAA), a
	in	a, (0xA9)
	cpl
	ld	e, a			; 行8: bit0=SPACE 4=左 5=上 6=下 7=右
	in	a, (0xAA)
	and	a, #0xF0
	or	a, #4
	out	(0xAA), a
	in	a, (0xA9)
	cpl
	ld	d, a			; 行4: bit2=M
	in	a, (0xAA)
	and	a, #0xF0
	or	a, #2
	out	(0xAA), a
	in	a, (0xA9)
	cpl
	ld	h, a			; 行2: bit7=B
	ld	a, #15
	out	(0xA0), a
	in	a, (0xA2)
	and	a, #0xAF		; ポート1 選択、ピン8 = L
	or	a, #0x03
	out	(0xA1), a
	ld	a, #14
	out	(0xA0), a
	in	a, (0xA2)
	ei
	cpl
	and	a, #0x3F		; ジョイスティックの並びがそのまま戻り値の並び
	bit	5, e
	jr	z, 1$
	or	a, #0x01
1$:
	bit	6, e
	jr	z, 2$
	or	a, #0x02
2$:
	bit	4, e
	jr	z, 3$
	or	a, #0x04
3$:
	bit	7, e
	jr	z, 4$
	or	a, #0x08
4$:
	bit	0, e
	jr	z, 5$
	or	a, #0x10
5$:
	bit	2, d
	jr	z, 6$
	or	a, #0x20
6$:
	bit	7, h
	jr	z, 7$
	or	a, #0x20
7$:
	ld	l, a
	ld	a, h
	and	a, #0xC0		; 行2: bit6 = A キー、bit7 = B キー → 戻り値の bit6・bit7(隠しコマンド用)
	or	a, l
	ret

; ---------------------------------------------------------------------------
; u8 sys_cpu_status(void) — S1990 のレジスタ 6(bit5: 0 = R800 / bit6: 0 = DRAM モード)。確認表示用
; ---------------------------------------------------------------------------
_sys_cpu_status::
	di
	ld	a, #6
	out	(0xE4), a
	in	a, (0xE5)
	ei
	ret

; ---------------------------------------------------------------------------
; void psg_write(u8 reg, u8 val)   A=reg, L=val
; ---------------------------------------------------------------------------
_psg_write::
	out	(0xA0), a
	ld	a, l
	out	(0xA1), a
	ret

; ---------------------------------------------------------------------------
; void fm_write(u8 reg, u8 val)   A=reg, L=val。FM 音源(MSX-MUSIC = YM2413、ポート 7Ch/7Dh)のレジスタに書く
;   YM2413 は、番地を書いてから 12 クロック(3.4µs)、値を書いてから 84 クロック(23.5µs)待たないと次を受け取れない
;   (クロックは 3.58MHz)。R800 はそれより速く次を書けてしまうので、ここで待つ(R800 で約 4µs と約 28µs)。
;   待ちのループの回数 fmw_n は、Z80 転送の間(CPU が Z80)だけ短くする(_xfer_z80。Z80 で 50 回だと 1 回 220µs かかり、
;   和音の切り替わりで割り込みが 4.7ms になっていた)。Z80 では 6 回で約 30µs
; ---------------------------------------------------------------------------
FMW_WAIT = 50			; 値を書いた後の待ちのループの回数(R800 で 1 回約 4 サイクル)
FMW_Z80	= 6			; Z80 のとき(1 回 16 クロック)
	.area	_DATA
_g_fmw_n::	.ds	1	; 待ちのループの回数(sound_init が FMW_WAIT にする)
	.area	_CODE
_fm_write::
	out	(0x7C), a
	ex	(sp), hl
	ex	(sp), hl
	ld	a, l
	out	(0x7D), a
	ld	a, (_g_fmw_n)
1$:
	dec	a
	jr	nz, 1$
	ret

; ---------------------------------------------------------------------------
; turbo R システムタイマ(E6h/E7h、約 3.911µs/カウント)。処理時間の計測用
; ---------------------------------------------------------------------------
;   タイマ自体は 0 に戻さない(書き込むと 0 に戻るが、声の割込み(pcm.s)が同じタイマで時刻の差を取るので、
;   毎フレーム 0 に戻すと遅れを計算できなかった)。今の値を基準として覚え、timer_read は基準からの差を返す
	.area	_DATA
tmr_base:	.ds	2
	.area	_CODE
_timer_reset::
	call	timer_raw
	ld	(tmr_base), de
	ret

; u16 timer_read(void) — timer_reset からのカウント
_timer_read::
	call	timer_raw
	push	hl
	ld	hl, (tmr_base)
	ex	de, hl
	or	a, a
	sbc	hl, de
	ex	de, hl
	pop	hl
	ret

; DE = システムタイマの値
timer_raw:
	in	a, (0xE6)
	ld	e, a
	in	a, (0xE7)
	ld	d, a
	in	a, (0xE6)
	cp	a, e
	ret	nc
	ld	e, a
	in	a, (0xE7)
	ld	d, a
	ret

; ---------------------------------------------------------------------------
; ROM バンクからの読み込み(仕様書 7.3「ステージ切替時は、常駐ローダーが一時的にページ1を ROM に戻し、
; 該当バンクのデータを RAM へコピーする」)
;
;   ASCII8 のバンクレジスタ(6000h-7FFFh)はページ1にしか無く、読み出す窓もページ1にある。
;   ページ1(エンジンのコード)を一時的にカートリッジへ切り替えるので、コピー処理はページ3の
;   常駐領域(RL_ADDR)に置いて実行する。切り替えている間は割り込みを止める
;   (割り込みの飛び先がページ0・1にあるため)。スロット切替は BIOS の ENASLT(ページ1/2 用)なので、
;   その間はページ0も BIOS に戻す。読み出し先はページ2・3(ページ0・1 は切り替え中なので不可)。
;   常駐ローダーは位置に依存しない書き方にする(内部の call や絶対ジャンプを使わない)。
; ---------------------------------------------------------------------------
ENASLT	= 0x0024
RL_ADDR	= 0xE000		; 常駐ローダー(0xE0F0 からはスロット ID など)
RL_LEN	= 0xE0F4		; 常駐ローダーが写す大きさ(rom_load が書く)
RL_SRC	= 0xE0F6		; 常駐ローダーが読む番地(ページ1 の窓の中)
P0D_BANK = 1			; ページ0に置く表(エリア _PAGE0)の ROM バンク
P0D_TMP	= 0x8000		; その一時置き場(起動時はページ2がまだ空き)

; void sys_install_loader(void) — 常駐ローダーをページ3へ写す(起動時に 1 回)
_sys_install_loader::
	ld	hl, #rl_blob
	ld	de, #RL_ADDR
	ld	bc, #rl_end - rl_blob
	ldir
	ret

; void rom_load(u8 bank)   A = 最初のバンク。bank と bank+1(16KB)を、いまページ2に出ているセグメントの 0x8000- へそのまま写す
;   (モジュールでないデータ用。変数の所を 0 で埋めない。タイトルの絵)
_rom_load::
	push	af
	call	_pcm_stop
	pop	af
	ld	hl, #0x4000
	ld	(RL_LEN), hl
	ld	(RL_SRC), hl
	ld	de, #MOD_ADDR
	jp	RL_ADDR

; void rom_chunk(u8 bank, u16 off)   A = 最初のバンク、DE = オフセット。bank, bank+1 の off から 1KB を、いまページ2に出ている
;   セグメントの同じオフセットへ写す(継ぎ目で 1 フレームに 1 回)。声は止めない(写す間だけ割り込みを待たせる)
_rom_chunk::
	ld	hl, #0x4000
	add	hl, de
	ld	(RL_SRC), hl
	ld	hl, #0x0400
	ld	(RL_LEN), hl
	ld	hl, #MOD_ADDR
	add	hl, de
	ex	de, hl
	jp	RL_ADDR

; void mod_load(u8 bank)   A = 最初のバンク。bank と bank+1(16KB)を、いまページ2に出ているセグメントの 0x8000- へ写し、
;   モジュールの変数(0xBC00-0xBFFF)を 0 で埋める
_mod_load::
	push	af
	call	_pcm_stop		; ゲームモジュール(声のデータもここ)を上書きし、ページ0を BIOS に戻すので、声を止める
	pop	af
	ld	hl, #0x4000
	ld	(RL_LEN), hl
	ld	(RL_SRC), hl
	ld	de, #MOD_ADDR
	call	RL_ADDR
	ld	hl, #MOD_BSS
	ld	de, #MOD_BSS + 1
	ld	bc, #0x03FF
	ld	(hl), #0
	ldir
	ret

; void bios_font(u8 *dst) — BIOS のフォント(CGTABL の指す 2KB。ひらがなを含む)を dst(ページ2・3)へ写す。
;   エンディングの SCREEN 1 で使う。写す間だけページ0を BIOS に戻す
_bios_font::
	push	hl
	call	_pcm_stop		; ページ0を BIOS に戻すので、声を止める
	pop	hl
	ex	de, hl
	di
	P0_TO_BIOS
	ld	hl, (0x0004)		; CGTABL
	ld	bc, #2048
	ldir
	P0_TO_RAM
	ei
	ret

; void sys_page0_data(void) — ページ0の表(sin 表・逆数表・フォント・敵の絵など、エリア _PAGE0)を
;   ROM のバンク P0D_BANK から読み込む。sys_page0_ram の後、表を使う前に 1 回。
;   ページ0へは直接写せない(読み込み中はページ0が BIOS)ので、ページ2の空きを経由する
	.globl	s__PAGE0, l__PAGE0
_sys_page0_data::
	ld	hl, #l__PAGE0
	ld	(RL_LEN), hl
	ld	hl, #0x4000
	ld	(RL_SRC), hl
	ld	a, #P0D_BANK
	ld	de, #P0D_TMP
	call	RL_ADDR
	ld	hl, #P0D_TMP
	ld	de, #s__PAGE0
	ld	bc, #l__PAGE0
	ldir
	ret

; 常駐ローダー本体(RL_ADDR で動く。位置に依存しない: 相対・内部ジャンプなし、固定番地だけ使う)
rl_blob:
	di
	push	de
	push	af
	P0_TO_BIOS			; ENASLT のためにページ0を BIOS に戻す
	ld	a, (V_CART)
	ld	h, #0x40
	call	ENASLT			; ページ1 = カートリッジ
	pop	af
	ld	(0x6000), a		; 0x4000-0x5FFF = bank
	inc	a
	ld	(0x6800), a		; 0x6000-0x7FFF = bank + 1
	pop	de
	ld	hl, (RL_SRC)
	ld	bc, (RL_LEN)
	ldir
	ld	a, (V_RAM)
	ld	h, #0x40
	call	ENASLT			; ページ1 = RAM(エンジン)に戻す
	P0_TO_RAM			; ページ0 = 自前の RAM に戻す
	ei
	ret
rl_end:

; ---------------------------------------------------------------------------
; Z80 転送(vdp.s の vdp_xfer から)。A = ページ(0/1)
;   S1990 は R800 から VDP への書き込みに 1 バイト 8.67µs の待ちを入れるが、Z80 には入れない(5.45µs。
;   実機の FS-A1ST と openMSX で同じ。docs/検証記録.md)。送る量が多いフレームは、CPU を Z80 に切り替えて、
;   xfer_prep(vdp.s)が書き出した転送のコード(変わった区間ごとに書き込み先を付け直して OUTI の列へ call)を走らせる。
;   切り替えは BIOS の CHGCPU(往復 約 0.9ms)。
;   ・CHGCPU を呼ぶ間はページ0を BIOS に戻す。CHGCPU は戻るときに割り込みを許可するので、その間は VDP の割り込み
;     (R#1 の IE0)を止めておく。止めている間に帰線が始まっても S#0 の F は立つので、IE0 を戻すとすぐ割り込みが入る
;   ・転送中はページ0を自前の RAM に戻して割り込みを許可する(割り込み処理と音は Z80 でも動く。R800 専用の命令なし)
;   ・CHGCPU に渡す値の bit7 は立てない(立てるとターボ LED が毎フレーム点滅する)
; ---------------------------------------------------------------------------
CHGCPU	= 0x0180
MSXVER	= 0x002D

	.area	_DATA
_g_z80x::	.ds	1	; 1 = Z80 で転送する(隠しコンフィグの XFER で R800 に固定できる)
_g_z80x_ok::	.ds	1	; 1 = ファームウェアに CHGCPU がある(sys_z80x_init が決める)
	.area	_CODE

	.globl	_g_vdp_r1, XF_CODE, xfer_r800

; void sys_z80x_init(void) — ファームウェアに CHGCPU があるか(MSXVER >= 3)で g_z80x_ok と g_z80x を決める。起動時に 1 回
_sys_z80x_init::
	di
	P0_TO_BIOS
	ld	a, (MSXVER)
	ld	c, a
	P0_TO_RAM
	ei
	xor	a, a
	ld	b, a
	ld	a, c
	cp	a, #3
	ccf
	rl	b			; MSXVER >= 3 なら 1
	ld	a, b
	ld	(_g_z80x_ok), a
	ld	(_g_z80x), a
	ret

; IE0 を止める / 戻す(割り込みを止めた状態で呼ぶ)。声を鳴らしている間(pcm.s)は CPU を切り替えないので、ここには来ない
z80x_ie_off:
	ld	a, (_g_r1_cur)
	and	a, #0xDF
	jr	z80x_r1
z80x_ie_on:
	ld	a, (_g_r1_cur)
z80x_r1:
	out	(0x99), a
	ld	a, #0x81
	out	(0x99), a
	ret

; CPU を切り替える: A = CHGCPU の値(0x00 = Z80、0x02 = R800 DRAM)。割り込みを許可して戻る
z80x_switch:
	di
	push	af
	call	z80x_ie_off
	P0_TO_BIOS
	pop	af
	call	CHGCPU
	di
	P0_TO_RAM
	call	z80x_ie_on
	ei
	ret

; CHGCPU の間は割り込みが止まる。分割線の割込みがそこに当たると下の画面が数ライン遅れるので、切り替えが 2 回とも分割線に
; 当たらない頃合い(分割線を過ぎてから 8ms 以内。転送は全部送っても約 8ms)まで待つ(指示書 8.4)
XF_PHASE = 8
_xfer_z80::
	ld	a, (_g_split)
	or	a, a
	jr	z, 2$
	in	a, (0xE7)
	ld	hl, #_g_split_t
	sub	a, (hl)
	cp	a, #XF_PHASE
	jp	nc, xfer_r800		; 分割線に当たる頃合いなら、待たずに R800 のまま送る(待つより約 3ms 得)
2$:
	xor	a, a
	call	z80x_switch		; → Z80
	ld	a, #FMW_Z80		; Z80 に切り替えた後で、FM の待ちを短く(切り替える前の割り込みは長い待ちのまま = 安全)
	ld	(_g_fmw_n), a
	di
	xor	a, a
	out	(0x99), a
	ld	a, #0x8E
	out	(0x99), a		; R#14 = 0
	ei
	ld	c, #0x98
	call	XF_CODE			; vdp.s の xfer_prep が書き出した転送のコード
	ld	a, #FMW_WAIT		; R800 に戻す前に、FM の待ちを長く
	ld	(_g_fmw_n), a
	ld	a, #2
	jp	z80x_switch		; → R800(DRAM モード)

; OUTI を 256 個並べたもの。途中へ飛び込めば n 個だけ送る(終わりの番地 - n * 2)
z80x_out256::
	.rept	256
	outi
	.endm
z80x_out_end::
	ret

