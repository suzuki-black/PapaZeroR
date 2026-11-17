#!/usr/bin/env python3
"""ASCII8 メガロム(512KB = 8KB × 64 バンク)を組み立てる。

  mkrom.py boot.ihx engine.ihx engine.noi out.rom modN.bin × 8 snd.ihx snd.noi songs.bin voicemod.bin cockpit.bin title.bin

bank0      ローダー
bank1-2    ページ0に置く表とコード(エリア _PAGE0 = RAM 0x0200-。起動時に sys_page0_data が読み込む)
bank3-4    エンジンの常駐部(RAM ページ1 0x4000-0x7FFF)
bank5-20   モジュール 0〜7(2 バンクずつ。起動時と継ぎ目でセグメント 1・5 へ読む)
bank21-22  音のモジュール(0x8000- にドライバ、SONG_BASE- に曲)
bank23-24  声のモジュール
bank25-26  コクピットの絵
bank27-34  タイトルの絵
"""
import re
import sys

BANK = 0x2000
ROM_BANKS = 64
HICODE_BASE = 0xA300  # 全モジュールの後ろに重ねるコード(game_ai.c・sndtest.c)。Makefile の -Wl-b_HICODE、gen_stage.py の DATA_LIMIT と同じ
DATA_BASE, DATA_LIMIT = 0xCC00, 0xD700   # 0xD700- は面のコード(stg.c)
CODE_LIMIT = 0x8000
P0D_BASE, P0D_LIMIT = 0x0200, 0x4000
SONG_BASE = 0x8D00
HOOK_OFS = 24        # モジュールの見出しの中の、場面の演出のコードの番地(tools/gen_stage.py の HOOK_OFS)
MOD_BANK0, SND_BANK, VOICE_BANK, COCKPIT_BANK, TITLE_BANK = 5, 21, 23, 25, 27
# 面のコード(stg.c): ページ3の 2 か所。ROM ではコクピットの絵のバンクの STG_OFS_A / STG_OFS_B から(src/engine/engine.h と同じ値)
STG_A, STG_A_LEN, STG_OFS_A = 0xD700, 0x0700, 0x2200
STG_B, STG_B_LEN, STG_OFS_B = 0xE700, 0x0800, 0x2900
STAGES = (1, 2, 3, 4, 5, 6, 21)      # 面のコードを呼ぶモジュール


def read_ihx(path):
    mem = {}
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line.startswith(':'):
                continue
            n = int(line[1:3], 16)
            addr = int(line[3:7], 16)
            typ = int(line[7:9], 16)
            if typ == 1:
                break
            if typ != 0:
                continue
            for i, b in enumerate(bytes.fromhex(line[9:9 + n * 2])):
                mem[addr + i] = b
    return mem


def read_noi(path):
    syms = {}
    with open(path) as f:
        for line in f:
            m = re.match(r'DEF (\S+) 0x([0-9A-Fa-f]+)', line)
            if m:
                syms[m.group(1)] = int(m.group(2), 16)
    return syms


def main(boot_ihx, eng_ihx, eng_noi, out_path, *args):
    # modN.bin(モジュール N。ROM のバンク MOD_BANK0 + 2N〜)、opN.ihx(モジュール N の後ろに重ねる演出のコード)と、決まった順のファイル
    mods = {int(re.search(r'mod(\d+)\.bin$', a).group(1)): a for a in args if re.search(r'mod\d+\.bin$', a)}
    ops = {int(re.search(r'op(\d+)\.ihx$', a).group(1)): a for a in args if re.search(r'op\d+\.ihx$', a)}
    stg_ihx = [a for a in args if a.endswith('stg.ihx')][0]
    snd_ihx, snd_noi, songs_bin, voice_bin, cockpit_bin, title_bin = [a for a in args if a not in mods.values() and a not in ops.values() and a != stg_ihx]
    stg = read_ihx(stg_ihx)
    stg_hook = read_noi(stg_ihx[:-4] + '.noi')['_op_hook']
    for a in stg:
        if not (STG_A <= a < STG_A + STG_A_LEN or STG_B <= a < STG_B + STG_B_LEN):
            sys.exit('mkrom: 面のコードが置き場所を超えた: 0x%04X' % a)
    if read_noi(stg_ihx[:-4] + '.noi').get('l__DATA', 0):
        sys.exit('mkrom: 面のコードに変数がある(持たない作り)')
    rom = bytearray(b'\xFF' * (ROM_BANKS * BANK))
    boot = read_ihx(boot_ihx)
    if min(boot) < 0x4000 or max(boot) >= 0x6000:
        sys.exit('mkrom: ローダーが bank0 に収まっていない')
    for a, b in boot.items():
        rom[a - 0x4000] = b
    eng = read_ihx(eng_ihx)
    p0 = [a for a in eng if a < 0x4000]
    code = [a for a in eng if 0x4000 <= a < 0x8000]
    hi = {a - 0x8000: b for a, b in eng.items() if HICODE_BASE <= a < 0xC000}   # 全モジュールの後ろに重ねるコード(game_ai.c)
    if [a for a in eng if 0x8000 <= a < HICODE_BASE]:     # 常駐部の後ろの領域(初期化のコードなど)があふれると、ここに来て ROM に載らない
        sys.exit('mkrom: 常駐部があふれた(0x%04X-)' % min(a for a in eng if 0x8000 <= a < HICODE_BASE))
    if [a for a in eng if a >= 0xC000]:
        sys.exit('mkrom: エンジンのイメージに 0xC000 以降のデータがある')
    if max(code) >= CODE_LIMIT:
        sys.exit('mkrom: 常駐部が 0x%04X を超えた: 0x%04X' % (CODE_LIMIT, max(code)))
    syms = read_noi(eng_noi)
    if syms.get('s__DATA', 0) < DATA_BASE or syms.get('s__HEAP', 0) > DATA_LIMIT:
        sys.exit('mkrom: 変数域 0x%04X-0x%04X が範囲を超えた' % (syms.get('s__DATA', 0), syms.get('s__HEAP', 0)))
    if syms.get('s__CODE', 0) + syms.get('l__CODE', 0) > CODE_LIMIT:     # 0x8000 を超えた分は上の code に入らず、黙って落ちる
        sys.exit('mkrom: 常駐部が %d B あふれた' % (syms['s__CODE'] + syms['l__CODE'] - CODE_LIMIT))
    plen = syms.get('l__PAGE0', 0)
    if p0 and (min(p0) != P0D_BASE or max(p0) >= P0D_LIMIT):
        sys.exit('mkrom: ページ0の表が範囲を超えた (0x%04X-0x%04X)' % (min(p0), max(p0)))
    if plen > 2 * BANK:
        sys.exit('mkrom: ページ0が 16KB を超えた')
    if P0D_BASE + plen > P0D_LIMIT:     # あふれた分は 0x4000 以降(常駐部)のアドレスになり、上の検査では見えない
        sys.exit('mkrom: ページ0が %d B あふれて常駐部に重なった' % (P0D_BASE + plen - P0D_LIMIT))
    for a in p0:
        rom[BANK + a - P0D_BASE] = eng[a]
    for a in code:
        rom[3 * BANK + a - 0x4000] = eng[a]
    # 映像の場面の演出(op.c): モジュールの中身の後ろ、HICODE の手前に重ね、見出しに入口の番地を書く
    opimg = {}
    for n, ihx in ops.items():
        op = read_ihx(ihx)
        osyms = read_noi(ihx[:-4] + '.noi')
        if min(op) < 0x8000 or max(op) >= HICODE_BASE:
            sys.exit('mkrom: モジュール %d の演出が 0x%04X-0x%04X で、0x%04X を超えた' % (n, min(op), max(op), HICODE_BASE))
        if osyms.get('l__DATA', 0) or osyms.get('l__INITIALIZED', 0):
            sys.exit('mkrom: モジュール %d の演出に変数がある(持たない作り)' % n)
        opimg[n] = (op, osyms['_op_hook'])
    for i, m in sorted(mods.items()):
        d = bytearray(open(m, 'rb').read())
        for a, b in hi.items():
            d[a] = b
        if i in STAGES:
            d[HOOK_OFS:HOOK_OFS + 2] = stg_hook.to_bytes(2, 'little')
        if i in opimg:
            op, hook = opimg[i]
            if any(d[a - 0x8000] for a in op):
                sys.exit('mkrom: モジュール %d の演出がモジュールの中身に重なった' % i)
            for a, b in op.items():
                d[a - 0x8000] = b
            d[HOOK_OFS:HOOK_OFS + 2] = hook.to_bytes(2, 'little')
            print('mkrom: モジュール %d の演出 %d B(0x%04X-0x%04X)' % (i, len(op), min(op), max(op)))
        if MOD_BANK0 + 2 * i + 2 > SND_BANK and MOD_BANK0 + 2 * i < TITLE_BANK + 8:
            sys.exit('mkrom: モジュール %d のバンクがほかのデータに重なる' % i)
        rom[(MOD_BANK0 + 2 * i) * BANK:(MOD_BANK0 + 2 * i) * BANK + len(d)] = d
    snd = read_ihx(snd_ihx)
    ssyms = read_noi(snd_noi)
    if max(snd) >= SONG_BASE:
        sys.exit('mkrom: 音のドライバが 0x%04X を超えた: 0x%04X' % (SONG_BASE, max(snd)))
    for a, b in snd.items():
        rom[SND_BANK * BANK + a - 0x8000] = b
    songs = open(songs_bin, 'rb').read()
    rom[SND_BANK * BANK + SONG_BASE - 0x8000:SND_BANK * BANK + SONG_BASE - 0x8000 + len(songs)] = songs
    v = open(voice_bin, 'rb').read()
    rom[VOICE_BANK * BANK:VOICE_BANK * BANK + len(v)] = v
    c = open(cockpit_bin, 'rb').read()
    if len(c) > STG_OFS_A:
        sys.exit('mkrom: コクピットの絵が面のコードの場所に重なった')
    rom[COCKPIT_BANK * BANK:COCKPIT_BANK * BANK + len(c)] = c
    for a, b in stg.items():
        rom[COCKPIT_BANK * BANK + (STG_OFS_A + a - STG_A if a < STG_B else STG_OFS_B + a - STG_B)] = b
    t = open(title_bin, 'rb').read()
    if len(t) > 8 * BANK:
        sys.exit('mkrom: タイトルの絵が大きすぎる')
    rom[TITLE_BANK * BANK:TITLE_BANK * BANK + len(t)] = t
    with open(out_path, 'wb') as f:
        f.write(rom)
    print('mkrom: HICODE %d B / %d、面のコード %d B / %d + %d B / %d' % (len(hi), 0xC000 - HICODE_BASE, len([a for a in stg if a < STG_B]), STG_A_LEN,
                                                                          len([a for a in stg if a >= STG_B]), STG_B_LEN))
    print('mkrom: 常駐部 %d B / 16384、ページ0 %d B / 15872、変数 %d B、曲 %d B / %d' % (
        max(code) - 0x4000 + 1, plen, syms['s__HEAP'] - syms['s__DATA'], len(songs), 0xBE00 - SONG_BASE))


if __name__ == '__main__':
    main(*sys.argv[1:])
