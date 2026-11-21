; stgjt.s — 面のコード(stg.c)の先頭 0xD700 に置く飛び先の表。常駐部は面のコードより先にリンクするので、
; 名前では呼べない。エンドロール(scene.c の ending_run)が映像の場面の字幕の字体で書くために、ここを通して呼ぶ
	.module	stgjt
	.globl	_lb_at, _lb_line
	.area	_STGJT
	jp	_lb_at			; 0xD700: void lb_at(u8 x, u8 y)
	jp	_lb_line		; 0xD703: const char *lb_line(const char *s, u8 x0, u8 y, u8 c, u8 ital)
