/* shared_ram.c — 割り込みが読むページ2のセグメント。起動時のページ2 = セグメント 1 */
#include "engine.h"
u8 g_seg2 = 1;
