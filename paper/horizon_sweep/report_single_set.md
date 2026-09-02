universe: 47 candidate routes (8 at the shipped schedule); basis = 38 non-trivial instances
shipped rho-branch rule (3 routes): gmean 365.6

## single-set portfolios, in-sample (regret-free view: gmean over the 38)
### horizon only, contains base@16
  r=3    363.3  ( -0.6%)  1.09x time  {base@16, base@4, base@128}
  r=3    365.7  ( +0.0%)  1.25x time  {base@16, base@8, base@128}
  r=3    365.7  ( +0.0%)  1.17x time  {base@16, base@32, base@128}
  r=4    358.0  ( -2.1%)  1.35x time  {base@16, base@4, base@64, base@128}
  r=4    358.8  ( -1.9%)  1.20x time  {base@16, base@4, base@32, base@128}
  r=4    359.4  ( -1.7%)  1.26x time  {base@16, base@4, base@48, base@128}
  r=5    354.4  ( -3.1%)  1.46x time  {base@16, base@4, base@32, base@64, base@128}
  r=5    355.7  ( -2.7%)  1.37x time  {base@16, base@4, base@32, base@48, base@128}
  r=5    355.8  ( -2.7%)  1.62x time  {base@16, base@8, base@32, base@64, base@128}

### horizon only, unconstrained
  r=3    363.3  ( -0.6%)  1.09x time  {base@4, base@16, base@128}
  r=3    365.7  ( +0.0%)  1.25x time  {base@8, base@16, base@128}
  r=3    365.7  ( +0.0%)  1.17x time  {base@16, base@32, base@128}
  r=4    358.0  ( -2.1%)  1.35x time  {base@4, base@16, base@64, base@128}
  r=4    358.8  ( -1.9%)  1.20x time  {base@4, base@16, base@32, base@128}
  r=4    359.4  ( -1.7%)  1.26x time  {base@4, base@16, base@48, base@128}
  r=5    354.4  ( -3.1%)  1.46x time  {base@4, base@16, base@32, base@64, base@128}
  r=5    355.7  ( -2.7%)  1.37x time  {base@4, base@16, base@32, base@48, base@128}
  r=5    355.8  ( -2.7%)  1.62x time  {base@8, base@16, base@32, base@64, base@128}

### joint (schedule x horizon), contains base@16
  r=3    352.3  ( -3.6%)  1.22x time  {base@16, base@128, floor0@64}
  r=3    355.9  ( -2.7%)  1.45x time  {base@16, base@128, floor25@128}
  r=3    355.9  ( -2.7%)  0.62x time  {base@16, floor0@64, floor25@128}
  r=4    339.8  ( -7.1%)  1.61x time  {base@16, base@128, floor0@64, floor25@128}
  r=4    343.8  ( -6.0%)  1.76x time  {base@16, base@128, floor0@64, slow99@128}
  r=4    343.8  ( -6.0%)  1.61x time  {base@16, base@128, floor25@128, slow95@128}
  r=5    333.6  ( -8.7%)  1.77x time  {base@16, base@128, floor0@64, floor25@128, slow95@128}
  r=5    335.8  ( -8.2%)  1.84x time  {base@16, base@128, floor0@64, floor0@128, floor25@128}
  r=5    335.9  ( -8.1%)  1.67x time  {base@16, base@128, floor0@16, floor25@128, slow95@128}

### joint (schedule x horizon), unconstrained
  r=3    352.3  ( -3.6%)  1.22x time  {base@16, base@128, floor0@64}
  r=3    353.3  ( -3.4%)  1.45x time  {base@128, floor0@16, floor25@128}
  r=3    355.2  ( -2.8%)  1.28x time  {base@128, floor0@16, floor0@128}
  r=4    339.8  ( -7.1%)  1.61x time  {base@16, base@128, floor0@64, floor25@128}
  r=4    341.8  ( -6.5%)  1.67x time  {base@128, floor0@16, floor0@128, floor25@128}
  r=4    342.3  ( -6.4%)  1.61x time  {base@128, floor0@16, floor25@128, slow95@128}
  r=5    333.6  ( -8.7%)  1.77x time  {base@16, base@128, floor0@64, floor25@128, slow95@128}
  r=5    335.7  ( -8.2%)  1.77x time  {base@128, floor0@16, floor0@64, floor25@128, slow95@128}
  r=5    335.8  ( -8.2%)  1.84x time  {base@16, base@128, floor0@64, floor0@128, floor25@128}

## grouped hold-out: refit the whole portfolio per fold, score the held-out group
### leave-one-suite-out
  horizon only  r=3    366.7 vs   365.6 ( +0.3%)  W/L=3/6  n=38  2 distinct picks
  horizon only  r=4    363.8 vs   365.6 ( -0.5%)  W/L=6/6  n=38  3 distinct picks
  horizon only  r=5    362.0 vs   365.6 ( -1.0%)  W/L=7/4  n=38  3 distinct picks
  joint         r=3    370.8 vs   365.6 ( +1.4%)  W/L=11/9  n=38  4 distinct picks
  joint         r=4    349.3 vs   365.6 ( -4.5%)  W/L=20/4  n=38  2 distinct picks
  joint         r=5    340.4 vs   365.6 ( -6.9%)  W/L=23/1  n=38  3 distinct picks

### leave-one-family-out
  horizon only  r=3    369.3 vs   365.6 ( +1.0%)  W/L=3/6  n=38  2 distinct picks
  horizon only  r=4    364.9 vs   365.6 ( -0.2%)  W/L=5/5  n=38  3 distinct picks
  horizon only  r=5    358.5 vs   365.6 ( -2.0%)  W/L=9/4  n=38  3 distinct picks
  joint         r=3    369.1 vs   365.6 ( +0.9%)  W/L=10/7  n=38  3 distinct picks
  joint         r=4    344.2 vs   365.6 ( -5.9%)  W/L=18/5  n=38  2 distinct picks
  joint         r=5    338.0 vs   365.6 ( -7.6%)  W/L=21/2  n=38  2 distinct picks

## recommended sets, per suite and against dSABRE
  portfolio                       main24         scaleup            ring            star   time
  dSABRE                           171.9           705.7            85.2           101.1
  horizon-only r=4         173.9 (1.01x)   508.7 (0.72x)    83.6 (0.98x)   117.1 (1.16x)  1.35x
  horizon-only r=5         173.5 (1.01x)   508.7 (0.72x)    80.7 (0.95x)   117.1 (1.16x)  1.46x
  joint r=4                171.0 (0.99x)   474.1 (0.67x)    81.3 (0.95x)   106.0 (1.05x)  1.61x
  joint r=5                169.3 (0.98x)   474.1 (0.67x)    77.3 (0.91x)   106.0 (1.05x)  1.77x
  shipped rho-branch       175.0 (1.02x)   508.7 (0.72x)    86.1 (1.01x)   122.3 (1.21x)  1.00x

  horizon-only r=4: {base@16, base@4, base@64, base@128}
  horizon-only r=5: {base@16, base@4, base@32, base@64, base@128}
  joint r=4: {base@16, base@128, floor0@64, floor25@128}
  joint r=5: {base@16, base@128, floor0@64, floor25@128, slow95@128}
shipped 3-route rule: 365.6 at 1.00x time

## best joint portfolio subject to a wall-clock cap (must contain base@16, must complete all 38)
  r=3  <=0.80x:   355.9 ( -2.7%)  0.62x  {base@16, floor0@64, floor25@128}
  r=3  <=1.00x:   355.9 ( -2.7%)  0.62x  {base@16, floor0@64, floor25@128}
  r=3  <=1.25x:   352.3 ( -3.6%)  1.22x  {base@16, base@128, floor0@64}
  r=3  <=1.50x:   352.3 ( -3.6%)  1.22x  {base@16, base@128, floor0@64}
  r=3   no cap:   352.3 ( -3.6%)  1.22x  {base@16, base@128, floor0@64}

  r=4  <=0.80x:   347.1 ( -5.1%)  0.78x  {base@16, floor0@64, floor25@128, slow95@128}
  r=4  <=1.00x:   347.0 ( -5.1%)  0.86x  {base@16, floor0@64, floor25@128, slow97@128}
  r=4  <=1.25x:   347.0 ( -5.1%)  0.86x  {base@16, floor0@64, floor25@128, slow97@128}
  r=4  <=1.50x:   345.8 ( -5.4%)  1.49x  {base@16, base@128, floor25@128, flat@4}
  r=4   no cap:   339.8 ( -7.1%)  1.61x  {base@16, base@128, floor0@64, floor25@128}

  r=5  <=0.80x:   344.0 ( -5.9%)  0.80x  {base@16, floor0@16, floor25@128, flat@4, slow97@128}
  r=5  <=1.00x:   342.6 ( -6.3%)  0.89x  {base@16, base@32, floor0@64, floor25@128, slow95@128}
  r=5  <=1.25x:   341.3 ( -6.6%)  1.02x  {base@16, floor0@64, floor25@128, slow95@128, slow97@128}
  r=5  <=1.50x:   340.9 ( -6.8%)  1.40x  {base@16, floor0@64, floor25@128, slow97@128, slow99@128}
  r=5   no cap:   333.6 ( -8.7%)  1.77x  {base@16, base@128, floor0@64, floor25@128, slow95@128}

## stability: which joint r=4 set each hold-out fold picks
  hold out suite=heavyhexring   -> {base@16, base@128, floor0@64, floor25@128}
  hold out suite=heavyhexstar   -> {base@16, floor25@128, slow95@32, slow95@128}
  hold out suite=main25         -> {base@16, base@128, floor0@64, floor25@128}
  hold out suite=main64         -> {base@16, base@128, floor0@64, floor25@128}
  hold out suite=main80         -> {base@16, base@128, floor0@64, floor25@128}
  hold out suite=scaleup        -> {base@16, base@128, floor0@64, floor25@128}
  hold out family=ae             -> {base@16, base@128, floor0@64, floor25@128}
  hold out family=multiplier     -> {base@16, base@128, floor0@64, floor25@128}
  hold out family=qaoa           -> {base@16, base@128, floor25@128, slow95@128}
  hold out family=qft            -> {base@16, base@128, floor0@64, floor25@128}
  hold out family=qnn            -> {base@16, base@128, floor0@64, floor25@128}
  hold out family=qpeexact       -> {base@16, base@128, floor0@64, floor25@128}
  hold out family=random         -> {base@16, base@128, floor0@64, floor25@128}
## held-out, WITH a wall-clock cap (portfolio refit per fold under the same cap)
  <=1.00x (no dearer than today)   suite   r=4    352.0 vs 365.6 ( -3.7%)  W/L=21/11  2 distinct
  <=1.00x (no dearer than today)   suite   r=5    350.6 vs 365.6 ( -4.1%)  W/L=21/12  5 distinct
  <=1.00x (no dearer than today)   family  r=4    359.5 vs 365.6 ( -1.7%)  W/L=16/16  4 distinct
  <=1.00x (no dearer than today)   family  r=5    353.5 vs 365.6 ( -3.3%)  W/L=20/12  4 distinct

  <=1.25x                          suite   r=4    364.6 vs 365.6 ( -0.3%)  W/L=16/13  4 distinct
  <=1.25x                          suite   r=5    352.7 vs 365.6 ( -3.5%)  W/L=21/12  4 distinct
  <=1.25x                          family  r=4    366.6 vs 365.6 ( +0.3%)  W/L=14/18  6 distinct
  <=1.25x                          family  r=5    355.2 vs 365.6 ( -2.8%)  W/L=20/12  4 distinct

  no cap                           suite   r=4    349.3 vs 365.6 ( -4.5%)  W/L=20/4  2 distinct
  no cap                           suite   r=5    340.4 vs 365.6 ( -6.9%)  W/L=23/1  3 distinct
  no cap                           family  r=4    344.2 vs 365.6 ( -5.9%)  W/L=18/5  2 distinct
  no cap                           family  r=5    338.0 vs 365.6 ( -7.6%)  W/L=21/2  2 distinct

## final candidates: gmean (ratio vs dSABRE), and cost relative to today's 3 routes
  portfolio                               main24         scaleup            ring            star  38-gmean   time
  dSABRE                                   171.9           705.7            85.2           101.1
  shipped rho-branch (3)           175.0 (1.02x)   508.7 (0.72x)    86.1 (1.01x)   122.3 (1.21x)     365.6  1.00x
  horizon-only single set (5)      173.5 (1.01x)   508.7 (0.72x)    80.7 (0.95x)   117.1 (1.16x)     354.4  1.46x
  joint, cheap (4)                 173.7 (1.01x)   494.2 (0.70x)    78.4 (0.92x)   112.0 (1.11x)     347.0  0.86x
  joint, best (4)                  171.0 (0.99x)   474.1 (0.67x)    81.3 (0.95x)   106.0 (1.05x)     339.8  1.61x
  joint, best (5)                  169.3 (0.98x)   474.1 (0.67x)    77.3 (0.91x)   106.0 (1.05x)     333.6  1.77x

## per-instance, shipped rho-branch vs the cheap joint 4-set
  main/64/ae                     157 ->     163  (  +3.8%)
  main/64/qft                    262 ->     248  (  -5.3%)
  main/64/qnn_OLD_DEEP           638 ->     664  (  +4.1%)
  main/64/random                 737 ->     701  (  -4.9%)
  main/64/qpeexact               222 ->     210  (  -5.4%)
  main/64/qaoa                   775 ->     748  (  -3.5%)
  main/64/multiplier            1076 ->     959  ( -10.9%)
  main/80/ae                     299 ->     388  ( +29.8%)
  main/80/qft                    446 ->     298  ( -33.2%)
  main/80/qnn_DEEP              1070 ->    1140  (  +6.5%)
  main/80/qpeexact               291 ->     353  ( +21.3%)
  main/80/multiplier            2486 ->    2352  (  -5.4%)
  scaleup/100/qft                198 ->     168  ( -15.2%)
  scaleup/100/qpeexact           200 ->     210  (  +5.0%)
  scaleup/200/qft                579 ->     447  ( -22.8%)
  scaleup/200/qpeexact           528 ->     579  (  +9.7%)
  scaleup/360/qft               1170 ->    1178  (  +0.7%)
  scaleup/360/qpeexact          1224 ->    1355  ( +10.7%)
  heavyhex/ring/ae                69 ->      67  (  -2.9%)
  heavyhex/ring/qft              109 ->     103  (  -5.5%)
  heavyhex/ring/qnn              240 ->     187  ( -22.1%)
  heavyhex/ring/random           465 ->     456  (  -1.9%)
  heavyhex/ring/qpeexact         105 ->      75  ( -28.6%)
  heavyhex/ring/qaoa             244 ->     243  (  -0.4%)
  heavyhex/ring/multiplier       506 ->     435  ( -14.0%)
  heavyhex/star/ae               149 ->     118  ( -20.8%)
  heavyhex/star/qft              117 ->     109  (  -6.8%)
  heavyhex/star/qnn              449 ->     399  ( -11.1%)
  heavyhex/star/random           547 ->     474  ( -13.3%)
  heavyhex/star/qpeexact         162 ->     118  ( -27.2%)
  heavyhex/star/qaoa             405 ->     339  ( -16.3%)
  heavyhex/star/multiplier       455 ->     593  ( +30.3%)
shipped rho-branch (3 routes): 365.6, 1.00x time

## structured sets = horizon set x floor set (pre-specified shape, nothing postselected)
    gmean   delta routes   time  set
    332.0   -9.2%     12  2.65x  {4,16,64,128} x {base,floor25,floor0}
    332.5   -9.1%      9  2.55x  {16,64,128} x {base,floor25,floor0}
    336.0   -8.1%      9  1.98x  {4,16,128} x {base,floor25,floor0}
    337.0   -7.8%      9  2.18x  {8,16,128} x {base,floor25,floor0}
    337.3   -7.7%      6  1.87x  {16,128} x {base,floor25,floor0}
    340.9   -6.8%      8  2.17x  {4,16,64,128} x {base,floor25}
    342.3   -6.4%      6  1.65x  {4,16,128} x {base,floor25}
    342.3   -6.4%      8  1.84x  {4,16,64,128} x {base,floor0}
    342.9   -6.2%      6  1.76x  {16,64,128} x {base,floor0}
    343.3   -6.1%      6  1.83x  {8,16,128} x {base,floor25}
    344.4   -5.8%      6  2.09x  {16,64,128} x {base,floor25}
    346.0   -5.4%      6  1.92x  {8,128} x {base,floor25,floor0}
    346.5   -5.2%      4  1.58x  {16,128} x {base,floor25}
    347.0   -5.1%      6  1.72x  {4,128} x {base,floor25,floor0}
    349.1   -4.5%      6  1.42x  {4,16,128} x {base,floor0}
    349.1   -4.5%      8  1.30x  {4,16,64,128} x {floor25,floor0}

## per suite (ratio vs dSABRE) and losses against the shipped rule
  portfolio                                 main24         scaleup            ring            star      38   time     W/L
  dSABRE                                     171.9           705.7            85.2           101.1
  shipped rho-branch (3)             175.0 (1.02x)   508.7 (0.72x)    86.1 (1.01x)   122.3 (1.21x)   365.6  1.00x     0/0
  {16,128} x {0.5,0.25} (4)          175.9 (1.02x)   474.1 (0.67x)    81.6 (0.96x)   106.5 (1.05x)   346.5  1.58x    15/4
  {16,128} x {0.5,0.25,0.0} (6)      171.2 (1.00x)   474.1 (0.67x)    79.2 (0.93x)   105.3 (1.04x)   337.3  1.87x    21/1
  {4,16,128} x {0.5,0.25} (6)        173.3 (1.01x)   474.1 (0.67x)    81.6 (0.96x)   105.1 (1.04x)   342.3  1.65x    16/2
  fitted joint 4-set                 171.0 (0.99x)   474.1 (0.67x)    81.3 (0.95x)   106.0 (1.05x)   339.8  1.61x    21/2

## does adding {4} rescue the dense circuits the 2x2 grid drops?
  {16,128} x {0.5,0.25}    gmean 346.5  losses 4  worst instance +41.8%  1.58x
  + base@4                 gmean 342.3  losses 2  worst instance +10.2%  1.62x
  + base@4 + floor25@4     gmean 342.3  losses 2  worst instance +10.2%  1.65x
portfolio                                rt  38-gmean   delta    W/L   worst   time   main24  scaleup  ring  star
dSABRE (9 routes)                         9                                           171.9  705.7  85.2  101.1
shipped rho-branch {4,8,16}/{8,16,128}    3     365.6   +0.0%    0/0   +0.0%  1.00x     175.0(1.02x)    508.7(0.72x)     86.1(1.01x)    122.3(1.21x)
horizon-only {4,16,64,128}                4     358.0   -2.1%    7/5  +10.2%  1.35x     173.9(1.01x)    508.7(0.72x)     83.6(0.98x)    117.1(1.16x)
horizon-only {4,16,32,64,128}             5     354.4   -3.1%   10/4  +10.2%  1.46x     173.5(1.01x)    508.7(0.72x)     80.7(0.95x)    117.1(1.16x)
{16,128} x {.5,.25}                       4     346.5   -5.2%   15/4  +41.8%  1.58x     175.9(1.02x)    474.1(0.67x)     81.6(0.96x)    106.5(1.05x)
{4,16,128} x {.5,.25}                     6     342.3   -6.4%   16/2  +10.2%  1.65x     173.3(1.01x)    474.1(0.67x)     81.6(0.96x)    105.1(1.04x)
{16,128} x {.5,.25,0}                     6     337.3   -7.7%   21/1  +14.5%  1.87x     171.2(1.00x)    474.1(0.67x)     79.2(0.93x)    105.3(1.04x)
{4,16,128} x {.5,.25,0}                   9     336.0   -8.1%   21/0   +0.0%  1.98x     170.2(0.99x)    474.1(0.67x)     79.2(0.93x)    105.1(1.04x)

## the two structured recommendations, per instance vs the shipped rule
  {4,16,128} x {.5,.25}: 16 better, 2 worse (over all 48)
     WORSE  main/64/qaoa                775 ->    854  (+10.2%)
     WORSE  main/64/qnn_OLD_DEEP        638 ->    653  (+2.4%)
     best   heavyhex/star/qnn           449 ->    318  (-29.2%)
     best   heavyhex/ring/qpeexact      105 ->     75  (-28.6%)
     best   heavyhex/star/qaoa          405 ->    290  (-28.4%)
     best   heavyhex/star/qpeexact      162 ->    118  (-27.2%)
     best   scaleup/200/qft             579 ->    447  (-22.8%)

  {16,128} x {.5,.25,0}: 21 better, 1 worse (over all 48)
     WORSE  main/80/qnn_DEEP           1070 ->   1225  (+14.5%)
     best   heavyhex/star/qnn           449 ->    318  (-29.2%)
     best   heavyhex/ring/qpeexact      105 ->     75  (-28.6%)
     best   heavyhex/star/qaoa          405 ->    290  (-28.4%)
     best   heavyhex/star/qpeexact      162 ->    118  (-27.2%)
     best   heavyhex/ring/qnn           240 ->    184  (-23.3%)

