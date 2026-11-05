/* pcm.h — 声(英語)を、ゲームを止めずにターボ R の内蔵 PCM で鳴らす(実体は pcm.s。仕組みはそちらの冒頭) */
#ifndef PCM_H_INC
#define PCM_H_INC
#include "engine.h"

extern u8 pcm_mode;          /* 0 = ふだん / 1 = 走査線割込みで鳴らしている */
extern u8 g_dbg_fire;        /* (調べ用)1 を書くと game.c が「FIRE」を鳴らす */
void pcm_fire(const u8 *p, u16 len);   /* p は声のモジュールの中。次の垂直帰線から鳴らす(鳴っていれば頭から差し替える) */
/* 声の番号(tools/gen_voice.sh の並び) */
enum { VOICE_NONE, VOICE_ROLL, VOICE_LOOP, VOICE_DIVE, VOICE_FIRE, VOICE_WARNING, VOICE_HURRY, VOICE_SEE, VOICE_NOPAPA, VOICE_PAPA, VOICE_GIVE };
void pcm_say(u8 voice);                /* 声を鳴らす(Fire! / Enemy ahead! / Enemy behind! / Warning! / 最後のボスの台詞) */
void pcm_stop(void);                   /* すぐ止めて、ふだんの割込みに戻す */

#endif
