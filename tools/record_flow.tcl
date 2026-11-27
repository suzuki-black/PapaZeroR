# record_flow.tcl — 魅せる自動プレイで、タイトルからエンドロールまでを通して録画する(docs/魅せるプレイ動画の依頼.md)
#
#   PZ_NOI=build/engine.noi PZ_OUT=<出力先> openmsx -setting <設定のコピー> -machine Panasonic_FS-A1ST \
#     -carta build/PapaZero.rom -romtype ASCII8 -script tools/record_flow.tcl
#   タイトルを 12 秒見せて始め、エンドロールの後はタイトルへ戻して数秒見せて終える。
#   任意: PZ_STAGE=<始める面> PZ_ONLY=1(その面だけ録って終える) PZ_SKIPOP=1(オープニングを飛ばす。試し撮り用)
#         PZ_REC=0(録画しない) PZ_MAX=<秒>(上限。既定 2400)
#
# 魅せる自動プレイは ROM には足さず(ROM の空きが無い)、このスクリプトが人と同じくキーボードを押す。
# g_auto は 0 のまま(人の操作)なので、照準は aim_step の加速(2→4→6 ドット)で動き、誘導弾は M キーの押し始めで撃つ。
# 当たり矩形(hits)・物体(obj)・レーザー(laser)を読んで、押すキーを決める(下の「魅せる自動プレイ」)。
#
# ★after time は相対時間。周期処理は [list proc args] で登録する。音量の設定は触らない。
set out $::env(PZ_OUT)
proc envd {n d} { expr {[info exists ::env($n)] ? $::env($n) : $d} }
set ::stage [envd PZ_STAGE 1]
set ::only  [envd PZ_ONLY 0]
set ::skipop [envd PZ_SKIPOP 0]
set ::rec   [envd PZ_REC 1]
set ::max   [envd PZ_MAX 2400]
set ::dbg   [envd PZ_DBG 0]
set ::f [open $out/record.txt w]
set fh [open $::env(PZ_NOI) r]
foreach line [split [read $fh] "\n"] { if {[regexp {^DEF (\S+) 0x([0-9A-Fa-f]+)} $line -> n h]} { set ::s($n) 0x$h } }
close $fh
proc m8 {n {o 0}} { debug read memory [expr {$::s($n)+$o}] }
proc m16 {n {o 0}} { expr {[m8 $n $o]|([m8 $n [expr {$o+1}]]<<8)} }
proc s16 {v} { expr {$v >= 0x8000 ? $v - 0x10000 : $v} }
set ::t0 0
proc now {} { expr {[machine_info time] - $::t0} }
proc ts {} { set t [now]; format "%d:%02d.%d" [expr {int($t)/60}] [expr {int($t)%60}] [expr {int($t*10)%10}] }
proc log {m} { puts $::f "[ts] $m"; flush $::f }

# ---- キー(行 8: SPACE=01 左=10 上=20 下=40 右=80。行 4: M=04) ----
set ::k8 0
set ::k4 0
proc keys {k8 k4} {
  if {$k8 != $::k8} {
    set up [expr {$::k8 & ~$k8 & 0xFF}]; set dn [expr {$k8 & ~$::k8 & 0xFF}]
    if {$up} { keymatrixup 8 $up }
    if {$dn} { keymatrixdown 8 $dn }
    set ::k8 $k8
  }
  if {$k4 != $::k4} {
    if {$k4} { keymatrixdown 4 4 } else { keymatrixup 4 4 }
    set ::k4 $k4
  }
}
proc tap {} { keymatrixdown 8 1; after time 0.2 {keymatrixup 8 1} }

# ---- 被弾の数(無敵でも damage() の入口で数える。inv_t が残っている間は本来も当たらない) ----
set ::hit 0
proc on_damage {} {
  if {[m8 _g_scene] != 1 || [m8 _inv_t]} return
  set sp [reg sp]
  set ra [expr {[debug read memory $sp] | ([debug read memory [expr {$sp+1}]] << 8)}]
  # 同じ番地(ページ 2)には音のモジュールなども割り込みの間に入るので、戻り先の直前が call damage のときだけ数える
  set d $::s(_damage)
  if {[debug read memory [expr {$ra-3}]] != 0xCD || [debug read memory [expr {$ra-2}]] != ($d & 0xFF) || [debug read memory [expr {$ra-1}]] != ($d >> 8)} return
  incr ::hit
  log [format "HIT #%d mod=%d n=%d from=%04X" $::hit [m8 _g_mod] [reg a] $ra]
}


# ---- 魅せる自動プレイ ----
# 2 段に分ける。
#   plan: 1 枚ごと(present の転送 vdp_xfer の入口。描画の途中の hits は書きかけ)に、狙う相手・撃ってよいか・誘導弾・機動を決める。
#   ctl : 毎フレーム(1/60 秒、after frame)に、照準を狙う所へ動かすキーと、撃つキーを押す。
# 描画は 15〜30fps なので、キーを 1 枚ごとにしか変えないと、照準の加速(1 ティック 6 ドット)で行き過ぎて揺れた。
proc tick16 {} { m16 _g_tick }
proc tdiff {a b} { expr {($a - $b) & 0xFFFF} }
array set ::seen {}
array set ::P {on 0 blt 0 tid -1 tx 128 ty 84 t0 0 fire 0 rects {} wait 0}
set ::cool 0
set ::vt -1
set ::vnext 0
set ::mq 0
set ::mt 0
set ::man 0
set ::prdone 0
set ::hold 0
proc ldef_stop {kind} { expr {$kind == 0 || $kind == 2 || $kind == 3} }
proc plan {} {
  set now [tick16]
  if {[m8 _g_scene] != 1} { set ::P(on) 0; array unset ::seen; set ::P(tid) -1; return }
  set ::P(on) 1
  # 物体: 消えた枠は見えた時刻を忘れる
  set ot {}
  for {set i 0} {$i < 30} {incr i} {
    set t [debug read memory [expr {$::s(_obj) + $i*28}]]
    lappend ot $t
    if {$t == 0 || ([info exists ::seen($i)] && [lindex $::seen($i) 1] != $t)} { unset -nocomplain ::seen($i) }
  }
  # 当たり矩形(id ごとにまとめる)
  set n [m8 _n_hits]
  array set R {}
  for {set i 0} {$i < $n} {incr i} {
    set b [expr {$::s(_hits) + $i*7}]
    set x0 [debug read memory $b]; set y0 [debug read memory [expr {$b+1}]]
    set x1 [debug read memory [expr {$b+2}]]; set y1 [debug read memory [expr {$b+3}]]
    set z [s16 [expr {[debug read memory [expr {$b+4}]] | ([debug read memory [expr {$b+5}]] << 8)}]]
    set id [debug read memory [expr {$b+6}]]
    if {[info exists R($id)]} {
      lassign $R($id) a0 b0 a1 b1 zz
      set R($id) [list [expr {min($a0,$x0)}] [expr {min($b0,$y0)}] [expr {max($a1,$x1)}] [expr {max($b1,$y1)}] [expr {min($zz,$z)}]]
    } else { set R($id) [list $x0 $y0 $x1 $y1 $z] }
    if {![info exists ::seen($id)]} { set ::seen($id) [list $now [lindex $ot $id]] }
  }
  set bi [m8 _boss_intro]; set bg [m8 _boss_grp]
  set prk [m8 _pr_kind]; set prt [m8 _pr_t]
  set bon [m8 _boss_on]
  set wp [m8 _g_stg 6]               ;# ボスの秘密兵器を撃っている間は 0 以外(stg.h の ST_WP)
  # 溜めているレーザー(止められるもの)の持ち主と残り
  array set LZ {}
  for {set i 0} {$i < 3} {incr i} {
    set b [expr {$::s(_laser) + $i*5}]
    set kind [debug read memory [expr {$b+1}]]
    if {$kind == 0xFF} continue
    if {[debug read memory [expr {$b+2}]] == 0 && [ldef_stop $kind]} { set LZ([debug read memory $b]) [debug read memory [expr {$b+3}]] }
  }
  # 撃つかを毎フレーム確かめるための矩形の表 {id x0 y0 x1 y1 z 撃ってよい}。
  # バルカンの当たりは、本体が次の描画の前に、この(前の描画の)矩形で調べる(fire_step の aim_target)。先の位置を予測して狙うと外れる
  set rects {}
  # 候補を選ぶ: 迫った敵弾 > 撃たれる直前のレーザー > ボスの部位・見せ終えた敵 > 見せている途中の敵(狙うだけ)
  set best -1; set bsc -1; set fire 0; set foes 0; set fl {}
  foreach id [array names R] {
    lassign $R($id) x0 y0 x1 y1 z
    set t [lindex $ot $id]
    set ob [expr {$::s(_obj) + $id*28}]
    set age [tdiff $now [lindex $::seen($id) 0]]
    set sc -1; set ok 0; set shoot 1
    if {$t == 13 || $t == 14} {
      set tm [debug read memory [expr {$ob+4}]]
      if {$tm < 1} { set tm 1 }
      set sc [expr {2000 - $tm}]; set ok 1
      if {$wp && $tm < 6} { set sc 1000 }   ;# 秘密兵器の間は、もう間に合わない弾より次の弾を狙う
    } elseif {$t == 18} {
      set fg [debug read memory [expr {$ob+11}]]
      if {$fg & 1} { set shoot 0 }   ;# ヒナのカプセル
      if {!$wp && !$bi && !($fg & 13) && [debug read memory [expr {$ob+10}]] == $bg} {
        set sc [expr {600 + (($fg & 2) ? 200 : 0) - ($z >> 8)}]; set ok 1
        incr foes; lappend fl $id    ;# ボスの部位も誘導弾の一斉発射に入れる(秘密兵器を何度も撃たせない)
        if {[info exists LZ($id)] && $LZ($id) <= 40} { set sc [expr {1500 - $LZ($id)}] }
      }
    } elseif {($t >= 1 && $t <= 12) || $t == 15} {
      if {$t <= 10} { incr foes; lappend fl $id }
      if {!$wp} {
        set ptn [debug read memory [expr {$ob+2}]]
        set need [expr {$ptn == 1 ? 130 : $ptn == 5 ? 110 : 80}]
        if {[info exists LZ($id)]} {
          if {$LZ($id) <= 40} { set sc [expr {1500 - $LZ($id)}]; set ok 1 } else { set sc [expr {100 + $age}] }
        } elseif {$age >= $need || $z < 0x0E00} { set sc [expr {500 + $age - ($z >> 9)}]; set ok 1 } else { set sc [expr {50 + $age}] }
      }
    } else { set shoot 0 }
    if {$wp && $t != 13 && $t != 14} { set shoot 0 }
    lappend rects [list $id $x0 $y0 $x1 $y1 $z $shoot]
    if {$sc > $bsc} { set bsc $sc; set best $id; set fire $ok }
  }
  # 誘導弾の一斉発射: 敵が 3 体以上見えていて、急ぎが無く、指示も出ていない。ロックの枠に順に入れてから続けて撃つ。
  # ボス戦は部位 1 つからでも撃つ(ボス戦が長いと残り時間が 1:00 を切り、エンディングの会話が変わる)
  set ln [m8 _lock_n]
  if {!$::mq && !$prk && !$wp && $bsc < 1500 && $foes >= ($bon ? 1 : 3) && [tdiff $now $::vnext] < 0x8000} {
    if {$::vt < 0} { set ::vt $now }
    set vol [tdiff $now $::vt]
    set lk {}
    for {set i 0} {$i < $ln} {incr i} { lappend lk [m8 _lock_id $i] }
    set nb -1; set nd 99999
    foreach id $fl {
      if {[lsearch $lk $id] >= 0} continue
      lassign $R($id) x0 y0 x1 y1
      set d [expr {abs(($x0+$x1)*2 - [m16 _aim_x]) + abs(($y0+$y1)*2 - [m16 _aim_y])}]
      if {$d < $nd} { set nd $d; set nb $id }
    }
    if {($ln >= 3 && ($nb < 0 || $ln >= 8 || $vol > 150)) || ($ln >= 2 && $vol > 220) || ($bon && $ln >= 1 && ($nb < 0 || $vol > 60))} {
      log [format "VOLLEY %d" $ln]
      set ::mq $ln; set ::mt 0; set ::vt -1
      set ::vnext [expr {($now + ($bon ? 90 : 300)) & 0xFFFF}]   ;# 次の一斉発射まで 5 秒、ボス戦は 1.5 秒(撃ってもロックは残るので、続けて撃たない)
    } elseif {$nb >= 0} { set best $nb; set fire 0 }
  } else { set ::vt -1 }
  # 狙う所(照準の単位。ブロック × 4)
  if {$best != $::P(tid)} {
    # 狙う相手を替えたら少し間を置く(人の反応)。急ぎ(敵弾・撃たれる直前のレーザー)は待たない
    set ::P(wait) [expr {$bsc >= 1500 ? 0 : 8}]
    if {$::dbg && $best >= 0} { log [format "TGT id=%d t=%d sc=%d" $best [lindex $ot $best] $bsc] }
  }
  set ::P(tid) $best
  set ::P(blt) [expr {$best >= 0 && ([lindex $ot $best] == 13 || [lindex $ot $best] == 14)}]   ;# 敵弾は速いので、止まりぎわまで速さを落とさない
  if {$wp} { set fire 1 }   ;# 秘密兵器の間は、照準に重なった敵弾だけを撃つ(ボスの部位は撃たない)
  if {$best >= 0} {
    lassign $R($best) x0 y0 x1 y1
    set ::P(tx) [expr {($x0+$x1)*2+2}]; set ::P(ty) [expr {($y0+$y1)*2+2}]
  } elseif {$wp} {
    # 秘密兵器: 弾が見える前に、弾の通り道(真ん中の少し上)で待つ
    set ::P(tx) 128; set ::P(ty) 40
  } else {
    # 何もいなければ真ん中の近くへゆっくり戻る
    set ::P(tx) 128; set ::P(ty) 84; set fire 0
  }
  set ::P(fire) $fire
  set ::P(rects) $rects
  set ::P(t0) $now
  set ::P(bon) $bon; set ::P(wp) $wp
  # 機動の指示: 受付の残りが少なくなってから M(ぎりぎりで避ける)
  if {$prk} {
    if {$prt < 20 && !$::prdone} { set ::man 3; set ::prdone 1; log [format "MANEUVER %d" $prk] }
  } else { set ::prdone 0 }
}

proc ctl {} {
  after frame ctl
  if {!$::P(on) || [m8 _g_scene] != 1} { keys 0 0; set ::hold 0; set ::mq 0; set ::man 0; return }
  set ax [m16 _aim_x]; set ay [m16 _aim_y]
  # ---- 照準 ----
  set k8 0
  set tx [expr {min(max($::P(tx), 12), 244)}]; set ty [expr {min(max($::P(ty), 12), 148)}]
  if {$::P(wait)} { incr ::P(wait) -1 } else {
    set dx [expr {$tx - $ax}]; set dy [expr {$ty - $ay}]
    set md [expr {max(abs($dx), abs($dy))}]
    set dz [expr {$::P(tid) >= 0 || $::P(wp) ? 2 : 20}]
    # 次に押したときの 1 ティックの速さ(game.c の aim_step: 押し続けて 6 ティックで 4、18 ティックで 6)
    set s [expr {$::hold + 1 >= 18 ? 6 : $::hold + 1 >= 6 ? 4 : 2}]
    if {$md > $dz} {
      if {$s > 2 && $md < $s * ($::P(blt) ? 1 : 4)} {
        set ::hold 0                 ;# 近づいたら 1 フレーム離して速さを 2 ドットへ戻す
      } else {
        set h [expr {max(3, $s / 2)}]
        if {$dx <= -$h} { set k8 [expr {$k8 | 0x10}] } elseif {$dx >= $h} { set k8 [expr {$k8 | 0x80}] }
        if {$dy <= -$h} { set k8 [expr {$k8 | 0x20}] } elseif {$dy >= $h} { set k8 [expr {$k8 | 0x40}] }
        if {$k8} { incr ::hold } else { set ::hold 0 }
      }
    } else { set ::hold 0 }
  }
  # ---- バルカン: 照準の下の一番手前が撃ってよいもので、熱が上がりきっていないときだけ ----
  set heat [m8 _g_heat]
  if {$::cool} { if {$heat <= 3} { set ::cool 0 } } elseif {$heat >= 17} { set ::cool 1; if {$::dbg} { log COOL } }
  if {$::P(fire) && !$::cool && !$::mq} {
    set bx [expr {$ax >> 2}]; set by [expr {$ay >> 2}]
    set under {}; set uz 99999
    foreach r $::P(rects) {
      lassign $r id x0 y0 x1 y1 z shoot
      if {$bx + 1 >= $x0 && $bx < $x1 + 1 && $by + 1 >= $y0 && $by < $y1 + 1 && $z < $uz} { set uz $z; set under $r }
    }
    if {[llength $under] && [lindex $under 6]} { set k8 [expr {$k8 | 1}] }
  }
  # ---- M: 機動の指示に応える / 誘導弾を続けて撃つ(押して 2 フレーム、離して 2 フレーム) ----
  set m 0
  if {$::man} { set m 1; incr ::man -1 } elseif {$::mq} {
    set m [expr {($::mt % 4) < 2}]
    if {($::mt % 4) == 3} { incr ::mq -1 }
    incr ::mt
  }
  if {$::dbg && $::P(wp)} {
    set bl {}
    foreach r $::P(rects) { lassign $r id x0 y0 x1 y1; lappend bl [format "%d:%d,%d-%d,%d" $id $x0 $y0 $x1 $y1] }
    log [format "W aim=%d,%d t=%d,%d k=%02X tid=%d %s" [expr {$ax>>2}] [expr {$ay>>2}] [expr {int($tx)>>2}] [expr {int($ty)>>2}] $k8 $::P(tid) $bl]
  }
  keys $k8 $m
}
# ---- 進行と録画 ----
set ::lastmod -1
set ::lastsc -1
set ::r23 -1
set ::r23t 0
set ::roll 0
set ::lastb 0
set ::lastw 0
proc mon {} {
  set mod [m8 _g_mod]; set sc [m8 _g_scene]
  if {$mod != $::lastmod || $sc != $::lastsc} {
    log [format "CHAPTER mod=%d scene=%d clock=%02X life=%d score=%d hits=%d" $mod $sc [m8 _g_clock] [m8 _life] [m16 _g_score] $::hit]
    set ::lastmod $mod; set ::lastsc $sc
  }
  if {$::skipop && $mod == 0 && $sc == 3} { tap }
  if {$::only && $::started && $mod != ($::stage == 7 ? 21 : $::stage) && $mod != 0} { finish "only" ; return }
  set b [m8 _boss_on]; set w [expr {[m8 _g_stg 6] != 0}]
  if {$b != $::lastb} { log [format "BOSS %s clock=%02X hits=%d" [expr {$b ? "on" : "off"}] [m8 _g_clock] $::hit]; set ::lastb $b }
  if {$w != $::lastw} { if {$w} { log "WEAPON" }; set ::lastw $w }
  # エンドロール: 縦スクロール(R#23)が動き出したら始まり、3 秒止まったら終わり
  if {$mod == 7} {
    set r [debug read {VDP regs} 23]
    if {$r != $::r23} {
      if {!$::roll && $::r23 >= 0} { set ::roll 1; log "CHAPTER staffroll" }
      set ::r23 $r; set ::r23t [now]
    } elseif {$::roll == 1 && [now] - $::r23t > 3} {
      # 流れ終わった: Space でタイトルへ戻り、数秒見せて終える
      set ::roll 2; log "CHAPTER back to title"; tap
      after time 6 { finish "staffroll" }
      return
    }
  }
  if {[now] > $::max} { finish "max"; return }
  after time 0.25 mon
}
set ::started 0
proc finish {why} {
  log [format "END %s clock=%02X life=%d score=%d hits=%d" $why [m8 _g_clock] [m8 _life] [m16 _g_score] $::hit]
  if {$::rec} { record stop }
  close $::f
  exit
}
proc begin {} {
  debug write memory [expr {$::s(_g_cfg)+2}] $::stage
  debug write memory [expr {$::s(_g_cfg)+1}] 1
  debug set_bp $::s(_damage) {} on_damage
  set ::t0 [machine_info time]
  if {$::rec} { record start $::env(PZ_OUT)/fullplay.avi }
  log "CHAPTER title"
  # タイトルは 12 秒ほど見せる(曲を少し聴かせる)。デモ(30 秒放置)と計器盤の説明には入らない
  after time 12 { tap; set ::started 1; mon; debug set_bp $::s(_vdp_xfer) {} plan; after frame ctl }
}
set throttle off
after time 7 begin
