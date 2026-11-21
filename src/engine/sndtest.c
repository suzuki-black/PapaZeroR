/* sndtest.c — サウンドテスト(タイトルで M)。曲・効果音・声を並べて、選んで鳴らす
 *
 * 上下で選び、左右で種類(MUSIC / EFFECT / VOICE)を替え、スペースで鳴らす。M で戻る。
 * ページ0と常駐部に空きが無いので HICODE に置く(game_ai.c と同じ。ここから ROM を読み込む処理は呼ばない)。
 * 画面の用意(screen3_init・cockpit_load)とタイトルの絵の描き直しは、呼ぶ側(scene.c)でする。
 */
#include "game.h"
#include "hud.h"
#include "sound.h"
#include "pcm.h"

static const char * const st_song[SONG_COUNT] = {
    "TITLE", "OPENING", "STAGE 1", "STAGE 2", "STAGE 3", "STAGE 4", "STAGE 5", "STAGE 6",
    "BOSS", "BRIDGE", "CLEAR", "ENDING", "GAME OVER", "KING 1", "KING 2", "FINALE",
};
static const char * const st_se[SE_COUNT - 1] = {
    "HEAL", "SHOT", "HIT", "ALARM", "KILL", "MISSILE", "DAMAGE", "LOCK", "TALLY", "BOSS", "LASER",
};
static const char * const st_voice[VOICE_GIVE] = {
    "ROLL", "LOOP", "DIVE", "FIRE", "WARNING", "HURRY", "I SEE", "NO PAPA", "PAPA", "GIVE BACK",
};
static const char * const st_kind[3] = { "- MUSIC -", "- EFFECT -", "- VOICE -" };
static const char * const * const st_list[3] = { st_song, st_se, st_voice };
static const u8 st_n[3] = { SONG_COUNT, SE_COUNT - 1, VOICE_GIVE };

void sound_test(void)
{
    u8 kind = 0, prev = 0xFF, in, i;
    u8 sel[3] = { 0, 0, 0 };
    bgm_stop();                 /* タイトルの曲を止める(鳴らした曲と聞き分けられるように) */
    for (;;) {
        u8 n = st_n[kind], s = sel[kind];
        u8 top = s > 1 ? (s + 2 < n ? s - 1 : n - 3) : 0;   /* 3 行を、選んだ行が真ん中に来るように送る */
        buf_fill(C_BLACK);
        text_center(1, "SOUND TEST", C_WHITE, 1);
        text_center(8, st_kind[kind], C_CYAN, 1);
        for (i = 0; i < 3; i++) {
            u8 k = top + i;
            num_draw(4, (i8)(15 + i * 6), k + 1, 2, k == s ? C_RED : C_WHITE);
            text_draw(14, (i8)(15 + i * 6), st_list[kind][k], k == s ? C_RED : C_WHITE, 1);
        }
        text_center(34, "SPC:PLAY M:BACK", C_CYAN, 1);
        present();
        in = input_raw();
        {
            u8 e = in & ~prev;
            prev = in;
            if (e & IN_UP) sel[kind] = s ? s - 1 : n - 1;
            if (e & IN_DOWN) sel[kind] = s + 1 < n ? s + 1 : 0;
            if (e & IN_LEFT) kind = kind ? kind - 1 : 2;
            if (e & IN_RIGHT) kind = kind < 2 ? kind + 1 : 0;
            if (e & IN_A) {
                if (kind == 0) bgm_play(s + 1);
                else if (kind == 1) se_play(s + 1);
                else pcm_say(s + 1);
            }
            if (e & IN_B) break;
        }
    }
    bgm_stop();
    pcm_stop();
}
