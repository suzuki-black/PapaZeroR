# PAPA ZERO(仮)

MSX turbo R 専用のコクピット視点 3D シューター。COASTER HOME RUN のエンジンを土台にした試作版。

```bash
make
openmsx -machine Panasonic_FS-A1ST -carta build/PapaZero.rom -romtype ASCII8
```

WebMSX では `build/PapaZero [ASCII8].rom` を使う。必要なもの: SDCC、Python 3 と Pillow、声を作り直すときは flite。

操作: カーソル = 照準、スペース = バルカン、スペースを押したまま M = 誘導弾、M = 機動(`ROLL!` などの指示に応える)。

## 指示書から変えたこと

- 画面の分割: 上 160 ライン(64×40)/ 下 52 ライン。指示書の 128 / 84 ではゲーム画面が狭すぎた。
- 計器の更新: VDP コマンドは分割線のモード切り替えで止まるので、CPU で 1 フレーム 1 項目だけ書く。

## クレジット

声: Flite(Carnegie Mellon University)。
