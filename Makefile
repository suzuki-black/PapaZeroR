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
LDFLAGS = -mr800 --no-std-crt0 --code-loc 0x4008 --data-loc 0xCC00 -Wl-b_PAGE0=0x0200 -Wl-b_HICODE=0xA400 -Wl-j -Wl-m -Wl-u
MODFLAGS = -mr800 --no-std-crt0 --data-loc 0xBC00 -Wl-j -Wl-m -Wl-u

ASM = crt0 sys vdp gfx math raster dm xf face pcm
CRES = view shared_ram sound hud main fx
CP0 = game scene cockpit
SND = modhead_snd sndfm
RELS = $(patsubst %,$(BUILD)/%.rel,$(ASM) $(CRES) $(CP0) game_ai gen_data)
HDRS = $(wildcard $(ENG)/*.h) $(BUILD)/songs.h $(BUILD)/title.h $(BUILD)/ids.h
MODS = $(foreach n,0 1 2 3 4 5 6 7,$(BUILD)/mod$(n).bin)
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

$(BUILD)/title.h: data/title_art.png $(TOOLS)/gen_title.py | $(BUILD)
	$(PYTHON) $(TOOLS)/gen_title.py data/title_art.png $(BUILD)/title.bin $(BUILD)/title.h
$(BUILD)/title.bin: $(BUILD)/title.h

$(BUILD)/cockpit.bin: $(TOOLS)/gen_cockpit.py $(TOOLS)/gen_data.py | $(BUILD)
	$(PYTHON) $(TOOLS)/gen_cockpit.py $@

$(BUILD)/ids.h: $(TOOLS)/gen_stage.py $(TOOLS)/stage_data.py $(TOOLS)/content.py $(TOOLS)/meshlib.py src/sound/songs.mml | $(BUILD)
	$(PYTHON) $(TOOLS)/gen_stage.py $(BUILD)
$(MODS): $(BUILD)/ids.h

$(patsubst %,$(BUILD)/%.rel,$(CP0)): $(BUILD)/%.rel: $(ENG)/%.c $(HDRS) | $(BUILD)
	$(CC) $(CFLAGS) $(P0FLAGS) -c -o $@ $<

$(BUILD)/game_ai.rel: $(ENG)/game_ai.c $(HDRS) | $(BUILD)
	$(CC) $(CFLAGS) --constseg HICODE --codeseg HICODE --opt-code-size -c -o $@ $<

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

$(BUILD)/sndtick.rel: $(ENG)/sndtick.c $(HDRS) | $(BUILD)
	$(CC) $(CFLAGS) --max-allocs-per-node 100000 -c -o $@ $<
	@if grep -qiE '\b(multu|multuw|ixh|ixl|iyh|iyl)\b' $(BUILD)/sndtick.asm; then echo "sndtick.c: Z80 でも動くコードに R800 専用・非公式の命令が入った"; rm -f $@; exit 1; fi
$(BUILD)/sndmod.ihx: $(BUILD)/modhead_snd.rel $(BUILD)/sndtick.rel $(BUILD)/sndfm.rel $(BUILD)/ressyms.rel
	$(CC) $(MODFLAGS) --code-loc 0x8009 -o $@ $^

$(ROM): $(BUILD)/boot.ihx $(BUILD)/engine.ihx $(BUILD)/sndmod.ihx $(MODS) $(BUILD)/songs.bin $(BUILD)/cockpit.bin $(BUILD)/title.bin src/sound/voicemod.bin
	$(PYTHON) $(TOOLS)/mkrom.py $(BUILD)/boot.ihx $(BUILD)/engine.ihx $(BUILD)/engine.noi $@ $(MODS) \
	  $(BUILD)/sndmod.ihx $(BUILD)/sndmod.noi $(BUILD)/songs.bin src/sound/voicemod.bin $(BUILD)/cockpit.bin $(BUILD)/title.bin
	cp $@ "$(BUILD)/$(ROMNAME) [ASCII8].rom"

fpsrom:
	$(MAKE) BUILD=build/fps EXTRA_CFLAGS=-DDEBUG_FPS ROMNAME=PapaZero_FPS

clean:
	rm -rf $(BUILD)
