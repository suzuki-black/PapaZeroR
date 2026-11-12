# test_flow.tcl — 自動プレイ(g_auto)で面を通し、0.2 秒より粗く状態を記録する(指示書 10.6)
#   PZ_NOI=build/engine.noi PZ_OUT=<出力先> PZ_STAGE=<始める面> PZ_MAX=<秒> PZ_GOD=1 openmsx ... -script test_flow.tcl
# ★after time は相対時間。周期処理は [list proc args] で登録する。音量は触らない。
set out $::env(PZ_OUT)
set ::f [open $out/flow.txt w]
proc log {m} { puts $::f $m; flush $::f }
set fh [open $::env(PZ_NOI) r]
foreach line [split [read $fh] "\n"] { if {[regexp {^DEF (\S+) 0x([0-9A-Fa-f]+)} $line -> n h]} { set ::s($n) 0x$h } }
close $fh
proc m8 {n {o 0}} { debug read memory [expr {$::s($n)+$o}] }
proc m16 {n} { expr {[m8 $n]|([m8 $n 1]<<8)} }
set throttle off
set ::fr 0
set ::last 0
set ::shot 0
set ::lastmod -1
set ::lastpath -1
set ::t7 0
proc press {} { keymatrixdown 8 1; after time 0.2 {keymatrixup 8 1} }
proc begin {} {
  debug write memory [expr {$::s(_g_cfg)+2}] $::env(PZ_STAGE)
  if {$::env(PZ_GOD)} { debug write memory [expr {$::s(_g_cfg)+1}] 1 }
  debug set_bp $::s(_vdp_xfer) {} {incr ::fr}
  screenshot -raw -prefix {} $::env(PZ_OUT)/title.png
  press
  after time 3 go
}
proc go { } {
  debug write memory $::s(_g_auto) 1
  # g_mod は use_mod だけが書く。ほかの所から書かれたらメモリ破壊
  debug set_watchpoint write_mem $::s(_g_mod) {} {
    set pc [reg pc]
    if {$pc<$::s(_mod_next_use) || $pc>$::s(_mod_next_use)+0x30} { log [format "WRITE g_mod pc=%04X sp=%04X" $pc [reg sp]]; incr ::bad; if {$::bad>2} {exit} }
  }
  tick
}
set ::bad 0
set ::ml 0
set ::cmp 0
set ::lm 0
proc tick {} {
  set t [machine_info time]
  set c 0
  for {set i 0} {$i<30} {incr i} { if {[debug read memory [expr {$::s(_obj)+$i*28}]]} {incr c} }
  set fps [expr {($::fr-$::last)/5.0}]
  set ::last $::fr
  debug write memory $::s(_g_auto) 1
  log [format "t=%6.1f scene=%d mod=%d path=%4d life=%d score=%d boss=%d grp=%d objs=%2d fps=%.1f ms=%.1f polys=%d" $t [m8 _g_scene] [m8 _g_mod] [expr {[m16 _path_s]/32}] [m8 _life] [m16 _g_score] [m8 _boss_on] [m8 _boss_grp] $c $fps [expr {[m16 _g_perf_frame]*0.0039}] [m8 _g_last_polys]]
  if {[m8 _g_mod]!=$::lastmod || $::shot%6==0 || [m8 _g_mod]==7} { screenshot -raw -prefix {} [format "%s/s%03d.png" $::env(PZ_OUT) $::shot] }
  set ::lastmod [m8 _g_mod]
  incr ::shot
  if {$t>$::env(PZ_MAX)} { log "end"; exit }
  # エンディング(モジュール 7。映像の場面で約 25 秒)が終わってエンドロールに入ったら終える(上限まで待たない)
  if {[m8 _g_mod] == 7} {
    if {$::t7 == 0} { set ::t7 $t }
    if {$t - $::t7 > 35} { log "end (ending)"; exit }
  }
  after time 5 tick
}
after time 8 begin
