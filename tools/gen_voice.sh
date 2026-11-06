#!/bin/sh
# 声(内蔵 PCM で鳴らす英語の声)を作り、声のモジュール src/sound/voicemod.bin へ書く(指示書 9.3)。
#   sh tools/gen_voice.sh
#   読み上げは flite(Carnegie Mellon University。著作権表示を残すこと = README のクレジット)。
#   並び(番号は pcm.h の VOICE_。1 から): Roll! Loop! Dive! Fire! Warning! Papa, hurry! I can see you! Papa, no! Papa! Give her back.
#   (4 番は前は Lock!。ロックを音だけにしたので Fire! に替えた。声のモジュールは 16KB で、両方は入らない)
# モジュールの形(0x8000-): db 声の数、(dw 番地, dw サンプル数) × 声の数、続けてサンプル(8bit unsigned、中心 0x80、3,996Hz)
set -e
cd "$(dirname "$0")/.."
OUT=build/voice
mkdir -p "$OUT"
# 父の声(cmu_us_rms を低く)
for p in "roll:Roll!" "loop:Loop!" "dive:Dive!" "give:Give her back."; do
  name=${p%%:*}
  text=${p#*:}
  flite -voice rms --setf duration_stretch=0.7 --setf int_f0_target_mean=85 -t "$text" -o "$OUT/$name.raw.wav"
  afconvert -f WAVE -d LEI16@3996 -c 1 "$OUT/$name.raw.wav" "$OUT/$name.wav"
done
# Fire!: 撃つたびに言うので、半分の速さで読ませて短く(0.15 秒ほど)。声を鳴らしている間は転送が遅くなり fps が落ちるため
#   甲高く叫ぶ声にする(低すぎるという指摘): ヒナの声と同じく標本化周波数を KF 倍と見なして、声の高さと響きを両方上げる。
#   rms は高さを 240Hz と指定しても 115Hz ほどで頭打ちになるので、KF を 2.6 にした(もっと高くという指摘。測ると約 290Hz、語尾は 200Hz。父のほかの声は約 85Hz)。
#   読む速さは duration_stretch に KF を掛けて戻す
KF=2.6
flite -voice rms --setf duration_stretch=$(echo "0.35 * $KF" | bc -l) --setf int_f0_target_mean=240 --setf int_f0_target_stddev=25 -t "Fire!" -o "$OUT/fire.slow.wav"
python3 - "$OUT/fire.slow.wav" "$OUT/fire.raw.wav" "$KF" <<'PY'
import sys, wave
r = wave.open(sys.argv[1])
w = wave.open(sys.argv[2], 'wb')
w.setparams(r.getparams())
w.setframerate(int(r.getframerate() * float(sys.argv[3])))
w.writeframes(r.readframes(r.getnframes()))
PY
afconvert -f WAVE -d LEI16@3996 -c 1 "$OUT/fire.raw.wav" "$OUT/fire.wav"
# 無線の声(cmu_us_slt を高く)
flite -voice slt --setf duration_stretch=0.66 --setf int_f0_target_mean=320 --setf int_f0_target_stddev=45 -t "Warning!" -o "$OUT/warning.raw.wav"
afconvert -f WAVE -d LEI16@3996 -c 1 "$OUT/warning.raw.wav" "$OUT/warning.wav"
# ヒナの声(子供): cmu_us_slt をゆっくり読ませ、標本化周波数を K 倍と見なして速く再生する。
#   声の高さと声道の響き(フォルマント)が両方 K 倍になり、大人の女声を高くしただけより子供らしく聞こえる。
#   読む速さは duration_stretch に K を掛けて戻す。声の高さは 330 × K ≒ 450Hz
K=1.36
for p in "hurry:Papa, hurry!" "see:I can see you!" "nopapa:Papa, no!" "papa:Papa!"; do
  name=${p%%:*}
  text=${p#*:}
  flite -voice slt --setf duration_stretch=$(echo "0.66 * $K" | bc -l) --setf int_f0_target_mean=330 --setf int_f0_target_stddev=50 -t "$text" -o "$OUT/$name.slow.wav"
  python3 - "$OUT/$name.slow.wav" "$OUT/$name.raw.wav" "$K" <<'PY'
import sys, wave
r = wave.open(sys.argv[1])
w = wave.open(sys.argv[2], 'wb')
w.setparams(r.getparams())
w.setframerate(int(r.getframerate() * float(sys.argv[3])))
w.writeframes(r.readframes(r.getnframes()))
PY
  afconvert -f WAVE -d LEI16@3996 -c 1 "$OUT/$name.raw.wav" "$OUT/$name.wav"
done

python3 - "$OUT" src/sound/voicemod.bin <<'PY'
import struct, sys, wave
names = ['roll', 'loop', 'dive', 'fire', 'warning', 'hurry', 'see', 'nopapa', 'papa', 'give']
voices = []
for n in names:
    w = wave.open('%s/%s.wav' % (sys.argv[1], n))
    k = w.getnframes()
    d = struct.unpack('<%dh' % k, w.readframes(k))
    m = max(abs(x) for x in d)
    th = m * 0.04
    i0 = next(i for i, x in enumerate(d) if abs(x) > th)
    i1 = k - next(i for i, x in enumerate(reversed(d)) if abs(x) > th)
    s = d[max(0, i0 - 8):i1 + 8]
    voices.append(bytes(max(1, min(255, int(round(128 + x * 127.0 / m)))) for x in s))   # 中心 0x80
head = 1 + 4 * len(voices)
out = bytearray([len(voices)]) + bytes(4 * len(voices))
for j, v in enumerate(voices):
    out[1 + 4 * j:5 + 4 * j] = struct.pack('<HH', 0x8000 + len(out), len(v))
    out += v
if len(out) > 0x4000:
    sys.exit('gen_voice: 声のモジュールが %d バイトで 16KB を超えた' % len(out))
open(sys.argv[2], 'wb').write(out)
for n, v in zip(names, voices):
    print('  %-8s %5d サンプル %.2f 秒' % (n, len(v), len(v) / 3996))
print('gen_voice: %s %d バイト' % (sys.argv[2], len(out)))
PY
