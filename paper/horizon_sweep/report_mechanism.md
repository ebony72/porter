plans generated:            7710
distinct paper-tuple keys:  6507
COLLISIONS (same paper tuple, different plan): 1203 {'teleport': 1203}
  teleport: paper key ('teleport', (), 'control_to_target_core', 0, 3, (13, 49))
     plan A ('teleport', 2765, (), 28, 0, 3, 'localize_adjacent_control_to_target_core')
     plan B ('teleport', 2959, (), 29, 0, 3, 'localize_adjacent_control_to_target_core')
  teleport: paper key ('teleport', (), 'target_to_control_core', 3, 0, (49, 13))
     plan A ('teleport', 2769, (), 15, 3, 0, 'localize_adjacent_target_to_control_core')
     plan B ('teleport', 2959, (), 12, 3, 0, 'localize_adjacent_target_to_control_core')
  teleport: paper key ('teleport', (), 'control_to_target_core', 0, 3, (13, 49))
     plan A ('teleport', 2835, (), 27, 0, 3, 'localize_adjacent_control_to_target_core')
     plan B ('teleport', 2959, (), 29, 0, 3, 'localize_adjacent_control_to_target_core')
  teleport: paper key ('teleport', (), 'target_to_control_core', 3, 0, (49, 13))
     plan A ('teleport', 2839, (), 14, 3, 0, 'localize_adjacent_target_to_control_core')
     plan B ('teleport', 2959, (), 12, 3, 0, 'localize_adjacent_target_to_control_core')
  teleport: paper key ('teleport', (), 'target_to_control_core', 3, 0, (49, 13))
     plan A ('teleport', 2847, (), 14, 3, 0, 'localize_adjacent_target_to_control_core')
     plan B ('teleport', 2959, (), 12, 3, 0, 'localize_adjacent_target_to_control_core')
  teleport: paper key ('teleport', (), 'control_to_target_core', 0, 3, (13, 49))
     plan A ('teleport', 2913, (), 24, 0, 3, 'localize_adjacent_control_to_target_core')
     plan B ('teleport', 2959, (), 29, 0, 3, 'localize_adjacent_control_to_target_core')
## are the core graphs bipartite? (then a one-hop move changes every distance by exactly +-1)
  A                    K= 4  bipartite=True
  H                    K= 6  bipartite=True
  H_grid_2_3_5_5       K= 6  bipartite=True
  H_grid_3_4_5_5       K=12  bipartite=True
  H_grid_4_5_5_5       K=20  bipartite=True
  HeavyHex_ring4_27    K= 4  bipartite=True
  HeavyHex_star4_27    K= 4  bipartite=True

## sign split of Delta over the collected lookahead set
  main/25/ae             L=16   Delta {-1: 606, 1: 1347}  |Delta|=1 on 100.0%
                         past layer 7: 915 closer / 355 farther / 0 unchanged -> net +560
  main/80/qpeexact       L=128  Delta {-1: 72327, 1: 23103}  |Delta|=1 on 100.0%
                         past layer 7: 21442 closer / 70263 farther / 0 unchanged -> net -48821
  scaleup/100/qft        L=128  Delta {-1: 61851, 1: 11305}  |Delta|=1 on 100.0%
                         past layer 7: 10605 closer / 60548 farther / 0 unchanged -> net -49943
  heavyhex/star/qft      L=128  Delta {-1: 12417, 1: 3690}  |Delta|=1 on 100.0%
                         past layer 7: 3039 closer / 12093 farther / 0 unchanged -> net -9054
===== main/64/ae at L=16 : where the time is actually spent (tottime) =====
  
  ncalls  tottime  percall  cumtime  percall filename:lineno(function)
  57425    0.222    0.000    0.356    0.000 router.py:89(remove_gate_ids)
  1252097    0.143    0.000    0.143    0.000 {method 'get' of 'dict' objects}
  2425    0.095    0.000    0.456    0.000 router.py:1566(_collect_teleport_post_latent_lookahead_gates)
  113225/101012    0.062    0.000    0.202    0.000 {built-in method builtins.sorted}
  12182    0.061    0.000    0.146    0.000 router.py:781(_local_cx_distance_average)
  287639    0.057    0.000    0.076    0.000 layout.py:46(core_of)
  425577    0.053    0.000    0.053    0.000 {method 'add' of 'set' objects}
  2425    0.036    0.000    0.108    0.000 router.py:1504(_collect_teleport_latent_direct_gates_with_stop_state)
  168583    0.034    0.000    0.049    0.000 layout.py:57(is_phys_free)
  247943    0.031    0.000    0.031    0.000 router.py:84(<genexpr>)
  905    0.030    0.000    0.142    0.000 router.py:740(_local_swap_extended_local_cx_gates)
  408472    0.027    0.000    0.027    0.000 layout.py:43(is_real_logical)
  
  

===== scaleup/100/qft at L=128 : where the time is actually spent (tottime) =====
  
  ncalls  tottime  percall  cumtime  percall filename:lineno(function)
  264319    2.301    0.000    3.775    0.000 router.py:89(remove_gate_ids)
  10527345    1.171    0.000    1.171    0.000 {method 'get' of 'dict' objects}
  2440    1.079    0.000    5.913    0.002 router.py:1566(_collect_teleport_post_latent_lookahead_gates)
  4397300    0.478    0.000    0.478    0.000 {method 'add' of 'set' objects}
  526746/469219    0.431    0.000    1.317    0.000 {built-in method builtins.sorted}
  36206    0.398    0.000    0.951    0.000 router.py:781(_local_cx_distance_average)
  1412493    0.257    0.000    0.342    0.000 layout.py:46(core_of)
  2384739    0.225    0.000    0.225    0.000 router.py:84(<genexpr>)
  2098718    0.206    0.000    0.206    0.000 {method 'discard' of 'set' objects}
  2334860    0.179    0.000    0.179    0.000 {built-in method builtins.len}
  2556783    0.175    0.000    0.175    0.000 model.py:32(is_cx)
  717649    0.129    0.000    0.170    0.000 layout.py:51(phys_of)
  
  

  instance                    L   shipped   patched  speedup  stream identical?
  main/25/ae                 16     0.10s     0.09s    1.04x  YES  (epr 65 vs 65)
  main/64/ae                 16     0.34s     0.33s    1.02x  YES  (epr 177 vs 177)
  main/64/qft                16     0.52s     0.53s    1.00x  YES  (epr 262 vs 262)
  main/80/qpeexact          128     2.42s     2.29s    1.06x  YES  (epr 291 vs 291)
  scaleup/100/qft           128     2.00s     1.80s    1.11x  YES  (epr 198 vs 198)
  scaleup/100/qpeexact      128     1.46s     1.28s    1.14x  YES  (epr 200 vs 200)
  heavyhex/ring/qft         128     0.97s     0.88s    1.10x  YES  (epr 109 vs 109)

  overall 7.82s -> 7.20s = 1.09x

## scaleup/100/qft at L=128
  remote decisions scoring teleports: 197
  lookahead walks: 2438  ->  12.4 per decision
  distinct moving qubits per decision: 6.5
  48% of walks re-walk a qubit already walked in that same decision
  walks-per-decision (most common): {4: 77, 2: 71, 6: 22, 78: 13, 76: 5, 52: 4}

## main/64/ae at L=16
  remote decisions scoring teleports: 176
  lookahead walks: 2423  ->  13.8 per decision
  distinct moving qubits per decision: 7.1
  49% of walks re-walk a qubit already walked in that same decision
  walks-per-decision (most common): {4: 57, 2: 48, 49: 22, 6: 20, 32: 7, 47: 7}

## heavyhex/star/qft at L=128
  remote decisions scoring teleports: 116
  lookahead walks: 1514  ->  13.1 per decision
  distinct moving qubits per decision: 11.3
  13% of walks re-walk a qubit already walked in that same decision
  walks-per-decision (most common): {4: 40, 2: 30, 6: 11, 32: 7, 30: 2, 28: 2}
