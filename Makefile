# ============================================================================
#  PapaZeroR — MSX turbo R 専用 コクピット視点シューター
#
#  make          ASCII8 メガロム build/PapaZero.rom(WebMSX 用に "PapaZero [ASCII8].rom" も)
#  make fpsrom   計測用 ROM(fps 表示)
# ============================================================================
.DELETE_ON_ERROR:
.SECONDARY:

CC = sdcc
AS = sdasz80
PYTHON = python3
BUILD ?= build
BOOT = src/boot
ENG = src/engine
TOOLS = tools
ROMNAME ?= PapaZero
ALLOCS ?= 100000

CFLAGS = -mr800 --std-c11 -I$(ENG) -I$(BUILD) --max-allocs-per-node $(ALLOCS) $(EXTRA_CFLAGS)
P0FLAGS = --constseg PAGE0 --codeseg PAGE0 --opt-code-size
LDFLAGS = -mr800 --no-std-crt0 --code-loc 0x4008 --data-loc 0xCC00 -Wl-b_PAGE0=0x0200 -Wl-b_HICODE=0xA300 -Wl-j -Wl-m -Wl-u
MODFLAGS = -mr800 --no-std-crt0 --data-loc 0xBC00 -Wl-j -Wl-m -Wl-u

ASM = crt0 sys vdp gfx math raster dm xf face pcm
CRES = view shared_ram sound hud main fx
CP0 = game scene cockpit
SND = modhead_snd sndfm
RELS = $(patsubst %,$(BUILD)/%.rel,$(ASM) $(CRES) $(CP0) game_ai sndtest gen_data)
HDRS = $(wildcard $(ENG)/*.h) $(BUILD)/songs.h $(BUILD)/title.h $(BUILD)/ids.h
MODS = $(foreach n,0 1 2 3 4 5 6 7 15 16 17 18 19 20 21 22,$(BUILD)/mod$(n).bin)
# 映像の場面(オープニング = 0、n 面の後の継ぎ目 = 14 + n)の演出のコード(op.c)の置き場所。モジュールの中身の後ろ
# (tools/stage_data.py の op_base と同じ値。mkrom.py が重なりを確かめる)
OP0_BASE = 0x9420
OP15_BASE = 0x9000
OP16_BASE = 0x8800
OP17_BASE = 0x8800
OP18_BASE = 0x8800
OP19_BASE = 0x8800
OP7_BASE = 0x8E00
OP20_BASE = 0x8800
# 計器盤の説明(モジュール 22)のコード(guide.c。op.c ではない)
OP22_BASE = 0x8800
FILMS = 0 7 15 16 17 18 19 20
# 面のコード(stg.c: 新しい敵の動き・ボスの秘密兵器・残り時間)。ページ3の空き 2 か所に置き、ROM ではコクピットの絵のバンクの後ろ
STG_A = 0xD700
STG_B = 0xE700
ROM = $(BUILD)/$(ROMNAME).rom

.PHONY: all fpsrom clean
all: $(ROM)

$(BUILD):
	@mkdir -p $(BUILD)

$(BUILD)/gen_data.c: $(TOOLS)/gen_data.py | $(BUILD)
	$(PYTHON) $< $@
$(BUILD)/gen_data.rel: $(BUILD)/gen_data.c $(HDRS)
	$(CC) $(CFLAGS) --constseg PAGE0 -c -o $@ $<

$(BUILD)/songs.h: src/sound/songs.mml $(TOOLS)/gen_music.py | $(BUILD)
	$(PYTHON) $(TOOLS)/gen_music.py src/sound/songs.mml $(BUILD)/songs.bin $(BUILD)/songs.h
$(BUILD)/songs.bin: $(BUILD)/songs.h

# タイトルの絵(data/title_art.webp)に、文字の絵(data/title_text.png。tools/gen_title_text.py が書体 Anton で描いたもの)を重ねる
$(BUILD)/title.h: data/title_art.webp data/title_text.png $(TOOLS)/gen_title.py | $(BUILD)
	$(PYTHON) $(TOOLS)/gen_title.py data/title_art.webp $(BUILD)/title.bin $(BUILD)/title.h
$(BUILD)/title.bin: $(BUILD)/title.h

$(BUILD)/cockpit.bin: $(TOOLS)/gen_cockpit.py $(TOOLS)/gen_data.py $(TOOLS)/gen_font.py | $(BUILD)
	$(PYTHON) $(TOOLS)/gen_cockpit.py $@

$(BUILD)/ids.h: $(TOOLS)/gen_stage.py $(TOOLS)/stage_data.py $(TOOLS)/content.py $(TOOLS)/meshlib.py $(TOOLS)/film_spr.py $(TOOLS)/gen_font.py src/sound/songs.mml | $(BUILD)
	$(PYTHON) $(TOOLS)/gen_stage.py $(BUILD)
$(MODS): $(BUILD)/ids.h
$(patsubst %,$(BUILD)/film%.h,$(FILMS)): $(BUILD)/ids.h

$(patsubst %,$(BUILD)/%.rel,$(CP0)): $(BUILD)/%.rel: $(ENG)/%.c $(HDRS) | $(BUILD)
	$(CC) $(CFLAGS) $(P0FLAGS) -c -o $@ $<

$(BUILD)/game_ai.rel $(BUILD)/sndtest.rel: $(BUILD)/%.rel: $(ENG)/%.c $(HDRS) | $(BUILD)
	$(CC) $(CFLAGS) --constseg HICODE --codeseg HICODE --opt-code-size -c -o $@ $<

# 爆発(fx.c)・計器の字と数字(hud.c)・起動と表示(main.c)は大きさを優先する(常駐部が足りない。fx.c は約 370 バイト小さい)。
# どれも重いのは呼び先(塗り・字形・転送のアセンブラ)で、1・3 面の自動プレイ 90 秒で fps は変わらなかった
$(BUILD)/fx.rel $(BUILD)/hud.rel $(BUILD)/main.rel: $(BUILD)/%.rel: $(ENG)/%.c $(HDRS) | $(BUILD)
	$(CC) $(CFLAGS) --opt-code-size -c -o $@ $<

$(BUILD)/%.rel: $(ENG)/%.c $(HDRS) | $(BUILD)
	$(CC) $(CFLAGS) --opt-code-speed -c -o $@ $<

$(BUILD)/%.rel: $(ENG)/%.s $(ENG)/r800.inc $(ENG)/pscale.inc | $(BUILD)
	$(AS) -g -l -I$(ENG) -o $@ $<

$(BUILD)/boot.rel: $(BOOT)/boot.s | $(BUILD)
	$(AS) -g -o $@ $<
$(BUILD)/boot.ihx: $(BUILD)/boot.rel
	$(CC) -mz80 --no-std-crt0 --code-loc 0x4000 --data-loc 0xC000 -o $@ $<

$(BUILD)/engine.ihx: $(RELS)
	$(CC) $(LDFLAGS) -o $@ $(RELS)

$(BUILD)/ressyms.s: $(BUILD)/engine.ihx $(TOOLS)/ressyms.py
	$(PYTHON) $(TOOLS)/ressyms.py $(BUILD)/engine.noi $@
$(BUILD)/ressyms.rel: $(BUILD)/ressyms.s
	$(AS) -l -o $@ $<

# 映像の場面の演出: モジュール n の後ろに重ねる(常駐部・ページ0の関数と変数は ressyms で番地を引く。変数は持たない)。
# コードは同じ op.c で、台本 filmN.h だけが違う
$(BUILD)/op%.rel: $(ENG)/op.c $(HDRS) $(BUILD)/film%.h | $(BUILD)
	$(CC) $(CFLAGS) --opt-code-size -DFILM_H='"film$*.h"' $(if $(filter 7,$*),-DENDING_ROLL) -c -o $@ $<
$(BUILD)/op%.ihx: $(BUILD)/op%.rel $(BUILD)/ressyms.rel $(BUILD)/stgsyms.rel
	$(CC) $(MODFLAGS) --code-loc $(OP$*_BASE) -o $@ $^
$(BUILD)/op22.rel: $(ENG)/guide.c $(HDRS) | $(BUILD)
	$(CC) $(CFLAGS) --opt-code-size -c -o $@ $<
# 映像の場面から呼ぶ面のコードの関数(字幕の film_say)の番地
$(BUILD)/stgsyms.s: $(BUILD)/stg.ihx $(TOOLS)/ressyms.py
	$(PYTHON) $(TOOLS)/ressyms.py $(BUILD)/stg.noi $@ _film_say
$(BUILD)/stgsyms.rel: $(BUILD)/stgsyms.s
	$(AS) -l -o $@ $<

$(BUILD)/sndtick.rel: $(ENG)/sndtick.c $(HDRS) | $(BUILD)
	$(CC) $(CFLAGS) --max-allocs-per-node 100000 -c -o $@ $<
	@if grep -qiE '\b(multu|multuw|ixh|ixl|iyh|iyl)\b' $(BUILD)/sndtick.asm; then echo "sndtick.c: Z80 でも動くコードに R800 専用・非公式の命令が入った"; rm -f $@; exit 1; fi
$(BUILD)/sndmod.ihx: $(BUILD)/modhead_snd.rel $(BUILD)/sndtick.rel $(BUILD)/sndfm.rel $(BUILD)/ressyms.rel
	$(CC) -mr800 --no-std-crt0 --data-loc 0xBE00 -Wl-j -Wl-m -Wl-u --code-loc 0x800B -o $@ $^

# 面のコード: 1 つだけ作り、ページ3の 2 か所に分けて置く
$(BUILD)/stg.rel: $(ENG)/stg.c $(HDRS) | $(BUILD)
	$(CC) $(CFLAGS) --opt-code-size -c -o $@ $<
$(BUILD)/stgb.rel: $(ENG)/stgb.c $(HDRS) | $(BUILD)
	$(CC) $(CFLAGS) --opt-code-size --codeseg STGB --constseg STGB -c -o $@ $<
$(BUILD)/stg.ihx: $(BUILD)/stgjt.rel $(BUILD)/stg.rel $(BUILD)/stgb.rel $(BUILD)/ressyms.rel
	$(CC) $(MODFLAGS) -Wl-b_STGJT=$(STG_A) --code-loc 0xD706 -Wl-b_STGB=$(STG_B) -o $@ $^   # 先頭 6 バイトは飛び先の表(stgjt.s)

OPS = $(patsubst %,$(BUILD)/op%.ihx,$(FILMS)) $(BUILD)/op22.ihx $(BUILD)/stg.ihx
$(ROM): $(BUILD)/boot.ihx $(BUILD)/engine.ihx $(BUILD)/sndmod.ihx $(MODS) $(BUILD)/songs.bin $(BUILD)/cockpit.bin $(BUILD)/title.bin src/sound/voicemod.bin $(OPS)
	$(PYTHON) $(TOOLS)/mkrom.py $(BUILD)/boot.ihx $(BUILD)/engine.ihx $(BUILD)/engine.noi $@ $(MODS) \
	  $(BUILD)/sndmod.ihx $(BUILD)/sndmod.noi $(BUILD)/songs.bin src/sound/voicemod.bin $(BUILD)/cockpit.bin $(BUILD)/title.bin \
	  $(OPS)
	cp $@ "$(BUILD)/$(ROMNAME) [ASCII8].rom"

fpsrom:
	$(MAKE) BUILD=build/fps EXTRA_CFLAGS=-DDEBUG_FPS ROMNAME=PapaZero_FPS

clean:
	rm -rf $(BUILD)
