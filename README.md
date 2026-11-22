# PAPA ZERO(仮題 / working title)

<p align="center">
  <img src="docs/media/title.png" width="640" alt="PAPA ZERO — title screen">
</p>

> ⚠️ **This is a prototype** (work in progress). The repository is private for now; this README will be
> rewritten before it is made public.
> **試作品（プロトタイプ・開発中）です。** いまは非公開で、公開の前にこの README は書き直します。

A cockpit-view 3D rail shooter for the **MSX turboR** (V9958 VDP · R800). A father climbs into a
heavily modified Zero fighter and chases the terrorists who kidnapped his daughter — across a captured
town, a harbor, a canyon, a sea of clouds, the stratosphere, and into orbit.

**Repository:** <https://github.com/suzuki-black/PapaZeroR>. The 3D engine grew out of
**[CoasterHomeRunR](https://github.com/suzuki-black/CoasterHomeRunR)** (a 3D rail shooter in SCREEN 3).

<p align="center">
  <img src="docs/media/opening_zero.png" width="300" alt="Opening — the Zero parked by the barn">
  <img src="docs/media/stage2_harbor.png" width="300" alt="Stage 2 — the harbor">
  <br><sub>Opening · the Zero by the barn / オープニング 納屋の前の零戦　　Stage 2 · the harbor / 2面 港</sub>
</p>

**Language:** [🇬🇧 English](#english) · [🇯🇵 日本語](#japanese)

---

<a name="english"></a>
## English

- [Story](#story)
- [Overview](#overview)
- [Features](#features)
- [Controls](#controls)
- [Requirements](#requirements)
- [Building](#building)
- [Running](#running)
- [Project structure](#project-structure)
- [Documentation](#documentation)
- [Scope & honest positioning](#scope--honest-positioning)
- [Credits](#credits)
- [License](#license)
- [Disclaimer](#disclaimer)

### Story

> A quiet morning on the farm. The father looks away for a moment — and in that moment a terrorist
> group that has already seized the nearest town lands a jet on his road, and two of its men carry his
> daughter Hina away. In six hours she will be put on a rocket. He does not call the police.
> He runs to the barn, where an old Zero stands, rebuilt far beyond anything its makers imagined.

### Overview
- **Platform:** MSX turboR software (4 Mbit (512 KB) ASCII8 MegaROM). The engine assumes the R800.
- **Genre:** Single-player cockpit-view 3D rail shooter.
- **Screen:** the top 160 lines are the 3D view in SCREEN 3 (64 × 40 blocks, double-buffered);
  the bottom 52 lines are the cockpit instruments in a bitmap mode, split by a raster interrupt.
- **Structure:** opening → 7 stages (the town, the harbor, the canyon, the cloud sea, the stratosphere,
  the orbit, deep space), each ending with a boss and its secret weapon → a short film between stages →
  ending film and staff roll. The TIME LEFT clock counts down from 06:00 as you play; how much is left
  changes the father-and-daughter talk in the ending.

### Features
- **Real-time 3D in SCREEN 3** at up to 30 fps: flat-shaded polygons, a tilting horizon, LOD down to
  pre-drawn rectangles for distant objects.
- **Vulcan and homing missiles.** Anything inside the lock frame around the sight is locked (up to 8);
  each press of the missile key fires at the locked enemies in turn.
- **Enemy shots can be shot down** — the main way to defend yourself, as in other games of this kind.
- **Manoeuvre prompts** (`ROLL!` `LOOP!` `DIVE!`) with spoken calls.
- **"AI recognition" name labels.** The Zero's image recognition tags enemies and supplies with sprite
  labels and leader lines. Labels are staggered so no more than three share a line, so they never flicker.
- **Opening and between-stage scenes are films** timed to their music: key-framed cameras and actors
  driven by the same 60 Hz clock as the music, so picture and score never drift. People, the kidnappers'
  jet and tanks are drawn as two-layer magnified sprites so they can be told apart at 64 × 40.
- **Music:** MSX-MUSIC (YM2413) with a PSG layer, all original. **Voices** on the turboR internal PCM
  ("Fire!", "Papa, hurry!" …), generated with Flite.
- **Attract mode** (a cockpit guide, then a demo) after 30 seconds on the title screen, and a hidden settings menu.

### Controls
| Input | Action |
|-------|--------|
| Arrow keys | Move the sight |
| Space | Vulcan · start · skip the opening |
| **M** or **B** | Homing missile (while a prompt is shown it also performs the manoeuvre; a missile still fires if anything is locked) |
| ↑↑↓↓←→←→ B A on the title screen | Hidden settings menu (damage, invincibility, starting stage, lives, one-shot, FPS display, transfer, split, roll, size of the missile lock-on box) |

- **Vulcan:** hold Space to fire at whatever is under the sight (the sight turns red over a target).
  Firing heats the gun (HEAT); when it is full the gun stops for about a second.
- **Missiles:** any enemy that touches the cyan box around the sight is locked (up to 8; they get red marks
  and name tags). Each press of M fires one missile at the locked targets in turn. You get 500 per stage (MSL);
  green AMMO balloons add 50, MED balloons repair HP.
- **ROLL! / LOOP! / DIVE!:** press M while the prompt flashes to dodge a laser or shake off a pursuer.

### Cockpit
The bottom of the screen is the instrument panel. Leave the title screen alone for 30 seconds and a short guide
walks through it, one instrument at a time, before the demo.

| Instrument | What it shows |
|------------|---------------|
| KM/H | Air speed |
| ALT | Altitude (`---` in space) |
| HP | Armor, 8 segments. Turns red when only 2 are left; the windshield cracks as you take hits |
| MSL | Homing missiles left (500 per stage) |
| HEAT | Gun heat. When full, the Vulcan stops for about a second |
| Top right | Score |
| TIME LEFT | Hours left to save Hina. Starts at 6:00 and runs down as you play; at 1:00 Hina calls for you. It changes what she says in the ending |
| RADAR | You are in the middle, facing up. Green dots are enemies, red dots the boss |
| HINA | Your daughter's photo |

### Requirements
- **Target hardware: MSX turboR** (FS-A1ST / FS-A1GT).
- The turboR system ROM is copyrighted and is **not** included. Development and testing are done in
  [openMSX](https://openmsx.org/) with a machine built from a dumped turboR BIOS.
- The ROM also runs in [WebMSX](https://webmsx.org/) (turboR machine); the official WebMSX does not
  emulate the turboR PCM, so the voices may be silent there.

### Building
Requires [SDCC](https://sdcc.sourceforge.net/) and Python 3 with Pillow. [Flite](http://www.festvox.org/flite/)
is needed only to regenerate the voices (`sh tools/gen_voice.sh`).

```bash
make
```

This produces `build/PapaZero.rom` and a copy named `build/PapaZero [ASCII8].rom` for WebMSX.
`make fpsrom` builds a ROM with an FPS counter. If the default `python3` has no Pillow,
pass the interpreter: `make PYTHON=python3.14`.

### Running
```bash
openmsx -machine Panasonic_FS-A1ST -carta build/PapaZero.rom -romtype ASCII8
```

In WebMSX, drag and drop `build/PapaZero [ASCII8].rom` onto a turboR machine.

### Project structure
```
src/boot/      cartridge loader (bank 0)
src/engine/    engine: VDP and raster split, 3D transform and polygon fill, game loop, HUD, sound, PCM,
               op.c (the film player for the opening and the scenes between stages)
src/sound/     songs.mml (all music) and the voice module
tools/         generators: stage_data.py / content.py (stages, models, films), gen_stage.py, gen_music.py,
               gen_data.py (fonts, sprites), gen_cockpit.py, gen_title.py / gen_title_text.py, mkrom.py (MegaROM packer),
               test_flow.tcl (openMSX autoplay test)
data/          title illustration (title_art.webp) and its lettering (title_text.png)
docs/          development notes
```

### Documentation
- **[Design spec / 指示書](docs/指示書.md)** — what the game is and how it is built (screens, rules, enemies, stages, rendering, sound, memory map).
- **[Verification log / 検証記録](docs/検証記録.md)** — every problem found in testing, how it was measured and fixed.
- **[TODO](docs/TODO.md)** — what is left.
- **[View-direction bug notes / 視線の向きの不具合](docs/視線の向きの不具合_TrolleyHomeRun向け.md)** — a bug report written for a sibling project.

### Scope & honest positioning
This is an **experimental prototype**. The stages, bosses, films and music are all in place and an autoplay
test runs from the opening to the staff roll, but difficulty is not tuned yet and the timbres are under review.

### Credits
- **Original Concept / Direction:** suzuki-black
- **Program / Graphics / Music:** Claude Code (Anthropic Claude) — all music is original
- **Title illustration:** Microsoft Copilot (from a brief written with Claude Code: [docs/タイトル画像の依頼.md](docs/タイトル画像の依頼.md))
- **Title lettering font:** [Anton](https://fonts.google.com/specimen/Anton) — SIL Open Font License 1.1 (the font file is not
  included in this repository; `tools/gen_title_text.py` renders the lettering once into `data/title_text.png`)
- **Voices:** [Flite](http://www.festvox.org/flite/) (Carnegie Mellon University)

### License
**MIT** © 2026 suzuki-black. See [LICENSE](LICENSE).

### Disclaimer
The aircraft and vehicles that appear (the Zero, the P-51 and others) only borrow historical names and
shapes. Their shapes, colors and performance are changed for the game and are not accurate depictions
of real equipment. No specific game's names, characters, images or audio are used.

---

<a name="japanese"></a>
## 日本語

- [あらすじ](#あらすじ)
- [概要](#概要)
- [特徴](#特徴)
- [操作](#操作)
- [動作環境](#動作環境)
- [ビルド](#ビルド)
- [実行](#実行)
- [ディレクトリ構成](#ディレクトリ構成)
- [ドキュメント](#ドキュメント)
- [位置づけ](#位置づけ)
- [クレジット](#クレジット)
- [ライセンス](#ライセンス)
- [免責](#免責)

### あらすじ

> 農場の静かな朝。父がほんの少し目を離した隙に、すでに一番近い町を制圧していたテロ集団が
> 戦闘機で家の前の道に降り、2 人組が娘のヒナをさらっていった。6 時間後、ヒナはロケットに乗せられる。
> 父は警察を呼ばなかった。納屋へ走る。そこには、作った者の想像をはるかに超えて手を入れた、古い零戦がある。

### 概要
- **対応機種:** MSX turboR 用ソフト（4 メガビット（512KB）の ASCII8 メガROM）。R800 を前提に設計しています。
- **ジャンル:** 1 人用・コクピット視点の 3D レールシューター。
- **画面:** 上 160 ラインが SCREEN 3（64 × 40 ブロック、ダブルバッファ）の 3D、下 52 ラインがビットマップのモードの
  計器盤。走査線割込みで分けています。
- **構成:** オープニング → 全 7 面（町・港・谷・雲海・成層圏・軌道・深宇宙。各面の最後に秘密兵器を持つボス）→
  面と面の間の短い映像 → エンディングの映像とスタッフロール。残り時間（TIME LEFT）は 06:00 から遊んだ時間で減り、
  エンディングの親子の会話が、残った時間で変わります。

### 特徴
- **SCREEN 3 でリアルタイムの 3D**（上限 30fps）。面の塗りつぶし、傾く地平線、遠くの物体は前もって描いた矩形へ落とす LOD。
- **バルカンと誘導弾**。照準のまわりの枠に入った敵をロックし（8 体まで）、誘導弾のキーを押すたびに、ロックした敵へ順に撃ちます。
- **敵弾を撃ち落とせる**。同じ系統のゲームと同じく、これが主な守りです。
- **機動の指示**（`ROLL!` `LOOP!` `DIVE!`）と声。
- **「AI 画像認識」の名前の札**。零戦の画像認識という体裁で、敵と補給にスプライトの札と引き出し線を付けます。
  札は同じ高さに 3 枚までになるよう上下にずらすので、ちらつきません。
- **オープニングと面の間の場面は、曲に合わせて動く映像**。カメラと役者のキーフレームを、曲と同じ 60Hz の時計で
  動かすので、絵と曲はずれません。人物・誘拐の戦闘機・戦車は 2 枚重ねの拡大スプライトで描き、64 × 40 でも見分けがつきます。
- **音楽:** MSX-MUSIC（YM2413）に PSG を重ねた、すべてオリジナルの曲。**声**は turboR 内蔵 PCM（「Fire!」「Papa, hurry!」など。Flite で作成）。
- タイトルで 30 秒待つと計器盤の説明とデモ。隠しの設定メニュー。曲・効果音・声を聴けるサウンドテスト。

### 操作
| 入力 | 動作 |
|------|------|
| カーソルキー | 照準を動かす |
| スペース | バルカン・開始・オープニングを飛ばす |
| **M** または **B** | 誘導弾（指示が出ている間は機動もする。ロックがあれば誘導弾も撃つ） |
| タイトルで ↑↑↓↓←→←→ B A | 隠しの設定メニュー（ダメージ・無敵・開始面・残機・一撃・FPS 表示・転送・分割・ロール・誘導弾のロックの枠の大きさ・映像の場面だけを見る FILM） |
| タイトルで M | サウンドテスト（↑↓ で選ぶ、←→ で曲・効果音・声を切り替え、スペースで鳴らす、M で戻る） |

- **バルカン:** スペースを押している間、照準の下の敵を撃ちます（敵に重なると照準が赤くなります）。
  撃ち続けると銃が熱くなり（HEAT）、いっぱいになると 1 秒ほど撃てません。
- **誘導弾:** 照準のまわりの水色の枠に少しでもかかった敵をロックします（8 体まで。赤い印と名前の札が付きます）。
  M を押すたびに、ロックした敵へ順に 1 発ずつ撃ちます。面ごとに 500 発（MSL）。緑の AMMO の気球で 50 発、
  MED の気球で耐久（HP）が戻ります。
- **ROLL! / LOOP! / DIVE!:** 文字が点滅している間に M を押すと、レーザーを避けたり、後ろの敵を振り切ったりします。

### 計器盤
画面の下は計器盤です。タイトルで 30 秒待つと、デモの前に計器を 1 つずつ指して説明する画面が流れます。

| 計器 | 表すもの |
|------|----------|
| KM/H | 速度 |
| ALT | 高度（宇宙では `---`） |
| HP | 機体の耐久（8 目盛り）。残り 2 で赤くなる。被弾が重なると風防にひびが入る |
| MSL | 誘導弾の残り（面ごとに 500） |
| HEAT | 機銃の熱。いっぱいになると 1 秒ほどバルカンが撃てない |
| 右上 | 得点 |
| TIME LEFT | ヒナを助けるまでの残り時間。6:00 から遊んだ時間で減り、1:00 でヒナが呼ぶ。エンディングのヒナの台詞が変わる |
| RADAR | 真ん中が自機（上が進む向き）。緑の点は敵、赤い点はボス |
| HINA | 娘の写真 |

### 動作環境
- **MSX turboR**（FS-A1ST / FS-A1GT）。
- turboR 本体 ROM は著作物のため**同梱していません**。開発と検証は [openMSX](https://openmsx.org/) で、
  実機の BIOS を吸い出した機種定義を使って行っています。
- [WebMSX](https://webmsx.org/)（turboR 機種）でも動きます。本家の WebMSX は turboR の PCM を鳴らさないので、声は出ないことがあります。

### ビルド
[SDCC](https://sdcc.sourceforge.net/) と Python 3（Pillow）が必要です。[Flite](http://www.festvox.org/flite/) は声を作り直すときだけ使います（`sh tools/gen_voice.sh`）。

```bash
make
```

`build/PapaZero.rom` と、WebMSX 用に同じ中身の `build/PapaZero [ASCII8].rom` ができます。`make fpsrom` で FPS 表示付きの ROM を作ります。
既定の `python3` に Pillow が無いときは、`make PYTHON=python3.14` のように Python を指定してください。

### 実行
```bash
openmsx -machine Panasonic_FS-A1ST -carta build/PapaZero.rom -romtype ASCII8
```

WebMSX では turboR 機種に `build/PapaZero [ASCII8].rom` をドラッグ&ドロップします。

### ディレクトリ構成
```
src/boot/      カートリッジのローダー(バンク 0)
src/engine/    エンジン: VDP と走査線での画面分割、3D の変換と多角形の塗り、ゲームの流れ、計器、音、PCM、
               op.c(オープニングと面の間の映像の再生)
src/sound/     songs.mml(全曲)と声のモジュール
tools/         生成ツール: stage_data.py / content.py(面・モデル・映像の台本)、gen_stage.py、gen_music.py、
               gen_data.py(字・スプライト)、gen_cockpit.py、gen_title.py / gen_title_text.py、mkrom.py(メガROM の組み立て)、
               test_flow.tcl(openMSX の自動プレイの試験)
data/          タイトルの絵(title_art.webp)と、その文字(title_text.png)
docs/          開発ノート
```

### ドキュメント
- **[指示書](docs/指示書.md)** — ゲームの仕様と作り(画面・遊びの決まり・敵・面・描画・音・メモリの配置)。
- **[検証記録](docs/検証記録.md)** — 試験で見つけた問題と、測り方・直し方の記録。
- **[TODO](docs/TODO.md)** — 残っていること。
- **[視線の向きの不具合](docs/視線の向きの不具合_TrolleyHomeRun向け.md)** — 兄弟プロジェクト向けに書いた不具合の報告。

### 位置づけ
**実験的な試作品**です。面・ボス・映像・曲はひととおり揃い、オープニングからスタッフロールまで自動プレイの試験が通りますが、
難易度はまだ調整しておらず、音色も見直し中です。

### クレジット
- **原案・監督:** suzuki-black
- **プログラム・グラフィック・音楽:** Claude Code (Anthropic Claude)。曲はすべてオリジナル
- **タイトルの絵:** Microsoft Copilot（依頼書は Claude Code と作成: [docs/タイトル画像の依頼.md](docs/タイトル画像の依頼.md)）
- **タイトルの文字の書体:** [Anton](https://fonts.google.com/specimen/Anton) — SIL Open Font License 1.1（書体のファイルはリポジトリに入れていません。
  `tools/gen_title_text.py` が一度だけ `data/title_text.png` に描き出します）
- **声:** [Flite](http://www.festvox.org/flite/)（Carnegie Mellon University）

### ライセンス
**MIT** © 2026 suzuki-black。[LICENSE](LICENSE) を参照してください。

### 免責
登場する航空機や車両（零戦・P-51 など）は、実在の名前と形を借りただけのものです。形・色・性能はゲームのために変えてあり、
実物を正確に描いたものではありません。特定のゲームの名前・キャラクター・画像・音声は使っていません。
