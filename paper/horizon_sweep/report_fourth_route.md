## G. would a 4th route at a slow schedule help the shipped portfolio?
   (shipped 3 routes at the base schedule, plus one slow route)
   shipped 3-route baseline: 365.6 over 38
   + floor25@L128: 348.2 (-4.8%)
   + slow99@L256: 351.3 (-3.9%)
   + slow99@L128: 352.4 (-3.6%)
   + floor0@L64: 354.0 (-3.2%)
   + slow97@L128: 356.1 (-2.6%)
   + floor0@L128: 356.7 (-2.4%)

## H. oracle headroom across EVERY arm and horizon
   full oracle over 7 schedules x 7 horizons: 325.2 vs shipped 3-route 365.6 (-11.0%)
   oracle over horizons at the SHIPPED schedule only: 352.7 (-3.5%)
   -> extra schedules add -7.8% beyond a horizon oracle

## I. which schedule wins each instance (oracle over L within each arm)
   base     wins 10: 25/ae, 25/qft, 25/qnn, 64/ae, 80/qaoa, 100/qpeexact ...
   floor0   wins  4: 80/qft, ring/qnn, star/random, star/qaoa
   floor25  wins  6: 100/qft, 200/qft, ring/ae, ring/random, ring/qpeexact, star/qpeexact
   flat     wins  3: 80/ae, 80/qnn_DEEP, ring/qaoa
   slow95   wins  4: 64/qnn_OLD_DEEP, 64/qpeexact, 64/qaoa, ring/multiplier
   slow97   wins  3: 25/random, 64/qft, 64/multiplier
   slow99   wins  8: 64/random, 80/random, 80/qpeexact, 80/multiplier, 360/qpeexact, ring/qft ...
## grouped hold-out: pick the 4th route on training folds, score on the held-out group
  leave-one-suite-out    n=38 3-route 365.6 -> +1 route 352.1 (-3.7%) W/L=10/0
    picks: {'heavyhexring': 'floor25@L128', 'heavyhexstar': 'floor25@L128', 'main25': 'floor25@L128', 'main64': 'floor25@L128', 'main80': 'floor25@L128', 'scaleup': 'slow99@L256'}
  leave-one-family-out   n=38 3-route 365.6 -> +1 route 348.2 (-4.8%) W/L=12/0
    picks: {'ae': 'floor25@L128', 'multiplier': 'floor25@L128', 'qaoa': 'floor25@L128', 'qft': 'floor25@L128', 'qnn': 'floor25@L128', 'qpeexact': 'floor25@L128', 'random': 'floor25@L128'}

## the best 4th route in-sample, per suite (floor25@L128) and its family
  --- 4th route = floor25@L128
     main25              43.0 ->     43.0 ( +0.0%)  improves 0/6
     main64             196.1 ->    193.7 ( -1.2%)  improves 2/9
     main80             398.0 ->    391.1 ( -1.7%)  improves 1/9
     scaleup            508.7 ->    474.1 ( -6.8%)  improves 2/6
     ring                86.1 ->     82.2 ( -4.6%)  improves 3/9
     star               122.3 ->    112.7 ( -7.9%)  improves 4/9
     non-trivial 38     365.6 ->    348.2 ( -4.8%)  improves 12/38
     all 48             163.7 ->    157.5 ( -3.8%)  improves 12/48
  --- 4th route = slow99@L256
     main25              43.0 ->     43.0 ( +0.0%)  improves 0/6
     main64             196.1 ->    195.3 ( -0.4%)  improves 1/9
     main80             398.0 ->    383.5 ( -3.6%)  improves 2/9
     scaleup            508.7 ->    508.7 ( +0.0%)  improves 0/6
     ring                86.1 ->     82.4 ( -4.4%)  improves 3/9
     star               122.3 ->    112.7 ( -7.9%)  improves 5/9
     non-trivial 38     365.6 ->    351.3 ( -3.9%)  improves 11/38
     all 48             163.7 ->    158.6 ( -3.1%)  improves 11/48
  --- 4th route = slow99@L128
     main25              43.0 ->     43.0 ( +0.0%)  improves 0/6
     main64             196.1 ->    194.2 ( -1.0%)  improves 2/9
     main80             398.0 ->    382.4 ( -3.9%)  improves 3/9
     scaleup            508.7 ->    500.8 ( -1.6%)  improves 3/6
     ring                86.1 ->     83.5 ( -3.1%)  improves 2/9
     star               122.3 ->    114.8 ( -6.2%)  improves 3/9
     non-trivial 38     365.6 ->    352.4 ( -3.6%)  improves 13/38
     all 48             163.7 ->    159.0 ( -2.9%)  improves 13/48
  --- 4th route = floor0@L64
     main25              43.0 ->     43.0 ( +0.0%)  improves 0/6
     main64             196.1 ->    193.1 ( -1.6%)  improves 3/9
     main80             398.0 ->    380.6 ( -4.4%)  improves 1/9
     scaleup            508.7 ->    508.7 ( +0.0%)  improves 0/6
     ring                86.1 ->     85.3 ( -1.0%)  improves 4/9
     star               122.3 ->    114.6 ( -6.3%)  improves 5/9
     non-trivial 38     365.6 ->    354.0 ( -3.2%)  improves 13/38
     all 48             163.7 ->    159.6 ( -2.5%)  improves 13/48

## cost of the 4th route (wall seconds over the 38, this machine, 4-way load)
  floor25@L128: +1408s on top of 3591s -> 1.39x the 3-route protocol
  slow99@L256: +2597s on top of 3591s -> 1.72x the 3-route protocol
  slow99@L128: +1957s on top of 3591s -> 1.55x the 3-route protocol
  floor0@L64: +576s on top of 3591s -> 1.16x the 3-route protocol

## comparison with simply adding a 4th/5th HORIZON at the shipped schedule
  base best-of-(4, 8, 16, 128): 361.6 on n=38 (-1.1%)
  base best-of-(4, 16, 64, 128): 358.0 on n=38 (-2.1%)
  base best-of-(4, 16, 32, 64, 128): 354.4 on n=38 (-3.1%)
basis       dSABRE  PORTER 3rt   ratio    +4th route   ratio
main24       171.9       175.0    1.02x        173.0    1.01x   (4th=floor25@L128)
scaleup      705.7       508.7    0.72x        508.7    0.72x   (4th=slow99@L256)
ring          85.2        86.1    1.01x         82.2    0.96x   (4th=floor25@L128)
star         101.1       122.3    1.21x        112.7    1.11x   (4th=floor25@L128)

uniform 4th route floor25@L128 everywhere:
  main24      175.0 ->   173.0   vs dSABRE 171.9: 1.02x -> 1.01x
  scaleup     508.7 ->   474.1   vs dSABRE 705.7: 0.72x -> 0.67x
  ring         86.1 ->    82.2   vs dSABRE 85.2: 1.01x -> 0.96x
  star        122.3 ->   112.7   vs dSABRE 101.1: 1.21x -> 1.11x

instances the 4th route (floor25@L128) actually improves:
  main/64/qft                   262 ->    250  (-4.6%)
  main/64/multiplier           1076 ->   1007  (-6.4%)
  main/80/qft                   446 ->    381  (-14.6%)
  scaleup/100/qft               198 ->    168  (-15.2%)
  scaleup/200/qft               579 ->    447  (-22.8%)
  heavyhex/ring/ae               69 ->     67  (-2.9%)
  heavyhex/ring/qft             109 ->    103  (-5.5%)
  heavyhex/ring/qpeexact        105 ->     75  (-28.6%)
  heavyhex/star/ae              149 ->    118  (-20.8%)
  heavyhex/star/qft             117 ->    109  (-6.8%)
  heavyhex/star/qnn             449 ->    399  (-11.1%)
  heavyhex/star/qpeexact        162 ->    118  (-27.2%)
