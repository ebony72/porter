# Horizon grid analysis  (source=jsonl/base)

## Phase 0: validation

attempted routes: 384; by status: {'completed': 352, 'timeout': 30, 'livelock': 2}
instances: 48, horizon-sensitive (non GHZ/Graphstate): 38; of those lacking a completed L=16 route: ['heavyhex/star/multiplier']
non-completions (32): main/80/random@8:timeout, main/80/random@128:timeout, main/80/random@256:timeout, main/80/random@64:timeout, main/80/random@48:timeout, scaleup/360/qpeexact@8:timeout, main/80/qnn_DEEP@64:timeout, main/80/qnn_DEEP@128:timeout, main/80/qnn_DEEP@256:timeout, main/64/ae@256:timeout, main/64/qnn_OLD_DEEP@256:timeout, main/64/qnn_OLD_DEEP@128:timeout, main/80/qft@128:timeout, main/80/qft@256:timeout, main/64/qft@128:timeout, main/64/qft@256:timeout, main/64/random@128:timeout, main/64/random@256:timeout, main/64/qpeexact@128:timeout, main/64/qpeexact@256:timeout, main/64/qaoa@128:timeout, main/64/qaoa@256:timeout, main/80/qaoa@128:timeout, main/80/qaoa@256:timeout, heavyhex/ring/qaoa@128:timeout, heavyhex/ring/qaoa@256:timeout, heavyhex/star/qaoa@128:timeout, heavyhex/star/qaoa@256:timeout, heavyhex/ring/multiplier@32:livelock, heavyhex/star/multiplier@16:livelock, heavyhex/ring/random@256:timeout, heavyhex/star/random@256:timeout

## Headline: shipped density rule vs fixed 16 vs oracle (non-trivial instances)

- all, H6 [sweep-guard]: n=38 rule=365.6 oracle=352.7 (headroom -3.5%), fixed16=454.4 on n=37 (penalty +25.0%), gain captured 86%, optimum found 28/38, optimum outside assigned set 10
  outside: ['main/64/qpeexact', 'main/64/multiplier', 'main/80/qft', 'heavyhex/ring/qnn', 'heavyhex/ring/random', 'heavyhex/ring/qpeexact', 'heavyhex/ring/multiplier', 'heavyhex/star/qnn', 'heavyhex/star/random', 'heavyhex/star/qaoa']
- all, H6 [live-budget-feasible]: n=38 rule=365.6 oracle=352.7 (headroom -3.5%), fixed16=454.4 on n=37 (penalty +25.0%), gain captured 86%, optimum found 28/38, optimum outside assigned set 10
- main+scaleup, H8 [sweep-guard]: n=24 rule=475.5 oracle=466.8 (headroom -1.8%), fixed16=628.8 on n=24 (penalty +32.2%), gain captured 94%, optimum found 20/24, optimum outside assigned set 4
  outside: ['main/64/qpeexact', 'main/64/multiplier', 'main/80/qft', 'main/80/multiplier']
- main+scaleup, H8 [live-budget-feasible]: n=24 rule=475.5 oracle=466.8 (headroom -1.8%), fixed16=628.8 on n=24 (penalty +32.2%), gain captured 94%, optimum found 20/24, optimum outside assigned set 4

## Phase 1: exhaustive portfolios over H6 = {4,8,16,32,64,128}, non-trivial instances (regret vs H6 oracle)

### r = 1
  (4,)                   cover=38 gmean=  475.3 regret med=32.2% p90=108.9% max=152.0% >10%=27 exact= 3 routes-time=   2.1min
  (16,)                  cover=37 gmean=  454.4 regret med=19.4% p90= 95.3% max=154.4% >10%=24 exact= 9 routes-time=   4.1min
  (32,)                  cover=37 gmean=  455.6 regret med=22.9% p90= 91.3% max=119.8% >10%=26 exact= 3 routes-time=   6.6min
  (64,)                  cover=36 gmean=  419.8 regret med=36.8% p90= 83.3% max=105.9% >10%=26 exact= 4 routes-time=  15.3min
### r = 2
  (16, 128)              cover=38 gmean=  373.3 regret med= 0.0% p90= 20.9% max= 41.8% >10%=10 exact=24 routes-time=  63.4min
  (32, 128)              cover=38 gmean=  383.9 regret med= 3.9% p90= 32.6% max= 42.0% >10%=13 exact=18 routes-time=  65.8min
  (4, 128)               cover=38 gmean=  385.3 regret med= 1.1% p90= 38.7% max= 54.5% >10%=12 exact=18 routes-time=  61.4min
  (16, 64)               cover=38 gmean=  415.5 regret med= 8.7% p90= 68.2% max= 91.7% >10%=19 exact=13 routes-time=  19.4min
### r = 3
  (4, 16, 128)           cover=38 gmean=  363.3 regret med= 0.0% p90= 11.0% max= 29.7% >10%= 5 exact=27 routes-time=  65.5min
  (8, 16, 128)           cover=38 gmean=  365.7 regret med= 0.0% p90= 20.7% max= 41.8% >10%= 5 exact=28 routes-time=  74.9min
  (16, 32, 128)          cover=38 gmean=  365.7 regret med= 0.0% p90= 18.0% max= 32.6% >10%= 7 exact=27 routes-time=  70.0min
  (16, 64, 128)          cover=38 gmean=  366.8 regret med= 0.0% p90= 18.0% max= 41.8% >10%= 6 exact=28 routes-time=  78.6min
### r = 4
  (4, 16, 64, 128)       cover=38 gmean=  358.0 regret med= 0.0% p90=  6.2% max= 29.7% >10%= 2 exact=31 routes-time=  80.8min
  (4, 16, 32, 128)       cover=38 gmean=  358.8 regret med= 0.0% p90= 10.0% max= 20.7% >10%= 4 exact=30 routes-time=  72.1min
  (8, 16, 64, 128)       cover=38 gmean=  360.3 regret med= 0.0% p90=  6.2% max= 41.8% >10%= 2 exact=32 routes-time=  90.2min
  (8, 16, 32, 128)       cover=38 gmean=  360.3 regret med= 0.0% p90= 10.0% max= 32.6% >10%= 4 exact=31 routes-time=  81.5min
### r = 5
  (4, 16, 32, 64, 128)   cover=38 gmean=  354.4 regret med= 0.0% p90=  1.2% max= 10.2% >10%= 1 exact=34 routes-time=  87.4min
  (8, 16, 32, 64, 128)   cover=38 gmean=  355.8 regret med= 0.0% p90=  0.0% max= 32.6% >10%= 1 exact=35 routes-time=  96.8min
  (4, 8, 16, 64, 128)    cover=38 gmean=  356.2 regret med= 0.0% p90=  0.0% max= 29.7% >10%= 1 exact=35 routes-time=  92.3min
  (4, 8, 16, 32, 128)    cover=38 gmean=  357.2 regret med= 0.0% p90=  8.8% max= 20.7% >10%= 3 exact=34 routes-time=  83.6min
### named 3-sets
  {4,32,128}                       cover=38 gmean=  372.2 regret med= 0.0% p90= 20.7% max= 38.7% >10%= 9 exact=21 routes-time=  68.0min
  {8,32,128}                       cover=38 gmean=  373.6 regret med= 0.0% p90= 25.7% max= 42.0% >10%= 9 exact=22 routes-time=  77.4min
  {4,16,64}                        cover=38 gmean=  402.6 regret med= 3.2% p90= 64.6% max= 83.3% >10%=15 exact=16 routes-time=  21.5min
  {8,16,64}                        cover=38 gmean=  408.0 regret med= 4.0% p90= 68.2% max= 91.7% >10%=15 exact=17 routes-time=  30.9min
  {8,16,128} (sparse set alone)    cover=38 gmean=  365.7 regret med= 0.0% p90= 20.7% max= 41.8% >10%= 5 exact=28 routes-time=  74.9min
  {4,8,16} (dense set alone)       cover=38 gmean=  430.8 regret med= 8.6% p90= 91.3% max=125.3% >10%=19 exact=16 routes-time=  17.8min
### named 4-sets
  {4,16,64,128}                    cover=38 gmean=  358.0 regret med= 0.0% p90=  6.2% max= 29.7% >10%= 2 exact=31 routes-time=  80.8min
### named 5-sets
  {4,16,32,64,128}                 cover=38 gmean=  354.4 regret med= 0.0% p90=  1.2% max= 10.2% >10%= 1 exact=34 routes-time=  87.4min
  shipped density rule           cover=38 gmean=  365.6 regret med= 0.0% p90= 20.7% max= 41.2% >10%= 5 exact=28

## Phase 1b: same over H8 on the 30 main+scale-up instances (regret vs H8 oracle)

### r = 1
  (16,)                      cover=24 gmean=  628.8 regret med=30.7% p90=125.3% max=154.4% >10%=15 exact= 8 routes-time=   3.1min
  (32,)                      cover=24 gmean=  631.3 regret med=31.5% p90=108.0% max=119.8% >10%=19 exact= 1 routes-time=   5.3min
  (4,)                       cover=24 gmean=  674.7 regret med=39.7% p90=111.7% max=152.0% >10%=19 exact= 1 routes-time=   1.7min
### r = 2
  (16, 128)                  cover=24 gmean=  490.6 regret med= 0.0% p90= 30.4% max= 41.8% >10%= 4 exact=17 routes-time=  50.3min
  (16, 256)                  cover=24 gmean=  507.8 regret med= 1.0% p90= 35.1% max= 41.8% >10%= 7 exact=11 routes-time=  56.3min
  (32, 128)                  cover=24 gmean=  515.7 regret med= 6.5% p90= 32.6% max= 42.0% >10%= 9 exact=10 routes-time=  52.5min
### r = 3
  (4, 16, 128)               cover=24 gmean=  478.0 regret med= 0.0% p90=  8.8% max= 30.4% >10%= 2 exact=18 routes-time=  52.0min
  (8, 16, 128)               cover=24 gmean=  482.5 regret med= 0.0% p90=  8.8% max= 41.8% >10%= 2 exact=19 routes-time=  61.3min
  (16, 48, 128)              cover=24 gmean=  483.4 regret med= 0.0% p90= 10.2% max= 41.8% >10%= 3 exact=19 routes-time=  58.8min
### r = 4
  (4, 16, 48, 128)           cover=24 gmean=  471.0 regret med= 0.0% p90=  3.1% max= 10.2% >10%= 1 exact=20 routes-time=  60.6min
  (4, 16, 64, 128)           cover=24 gmean=  472.6 regret med= 0.0% p90=  6.2% max= 10.2% >10%= 1 exact=19 routes-time=  65.6min
  (4, 16, 32, 128)           cover=24 gmean=  475.0 regret med= 0.0% p90=  8.8% max= 18.7% >10%= 2 exact=19 routes-time=  57.3min
### r = 5
  (4, 8, 16, 48, 128)        cover=24 gmean=  468.5 regret med= 0.0% p90=  0.0% max=  6.2% >10%= 0 exact=22 routes-time=  71.6min
  (4, 16, 32, 48, 128)       cover=24 gmean=  469.8 regret med= 0.0% p90=  2.7% max= 10.2% >10%= 1 exact=21 routes-time=  65.8min
  (4, 8, 16, 64, 128)        cover=24 gmean=  470.1 regret med= 0.0% p90=  3.4% max=  7.9% >10%= 0 exact=21 routes-time=  76.7min
  shipped density rule           cover=24 gmean=  475.5 regret med= 0.0% p90=  6.2% max= 30.4% >10%= 1 exact=20

## Phase 2: instance-level rules, grouped hold-out (H6, non-trivial instances)

### in-sample (fit and evaluated on all instances)
  shipped density rule                       cover=38 gmean=  365.6 regret med= 0.0% p90= 20.7% max= 41.2% >10%= 5 exact=28
  refit density form (2 sets + threshold)    cover=38 gmean=  360.7 regret med= 0.0% p90= 11.7% max= 29.7% >10%= 4 exact=28
  best global 3-set                          cover=38 gmean=  363.3 regret med= 0.0% p90= 11.0% max= 29.7% >10%= 5 exact=27
  L(K)                                       cover=38 gmean=  475.3 regret med=32.2% p90=108.9% max=152.0% >10%=27 exact= 3
  L(D)                                       cover=38 gmean=  475.3 regret med=32.2% p90=108.9% max=152.0% >10%=27 exact= 3
  L(K,D)                                     cover=38 gmean=  454.4 regret med=19.6% p90= 91.7% max=227.3% >10%=25 exact= 5
  fixed 16                                   cover=37 gmean=  454.4 regret med=19.4% p90= 95.3% max=154.4% >10%=24 exact= 9
  fixed 128                                  cover=27 gmean=  314.5 regret med= 0.0% p90= 56.2% max=105.0% >10%=11 exact=15
### leave-one-suite-out
  shipped density rule                       cover=38 gmean=  365.6 regret med= 0.0% p90= 20.7% max= 41.2% >10%= 5 exact=28
  refit density form (2 sets + threshold)    cover=38 gmean=  376.6 regret med= 0.0% p90= 32.6% max= 41.2% >10%= 9 exact=21
  best global 3-set                          cover=38 gmean=  366.7 regret med= 0.0% p90= 20.7% max= 41.8% >10%= 6 exact=26
  L(K)                                       cover=34 gmean=  408.8 regret med=24.3% p90=105.3% max=152.0% >10%=24 exact= 4
  L(D)                                       cover=34 gmean=  408.8 regret med=24.3% p90=105.3% max=152.0% >10%=24 exact= 4
  L(K,D)                                     cover=34 gmean=  402.7 regret med=19.6% p90=105.3% max=152.0% >10%=23 exact= 5
  fixed 16                                   cover=37 gmean=  454.4 regret med=19.4% p90= 95.3% max=154.4% >10%=24 exact= 9
  fixed 128                                  cover=27 gmean=  314.5 regret med= 0.0% p90= 56.2% max=105.0% >10%=11 exact=15
### leave-one-family-out
  shipped density rule                       cover=38 gmean=  365.6 regret med= 0.0% p90= 20.7% max= 41.2% >10%= 5 exact=28
  refit density form (2 sets + threshold)    cover=38 gmean=  373.5 regret med= 0.0% p90= 30.4% max= 59.4% >10%= 8 exact=25
  best global 3-set                          cover=38 gmean=  369.3 regret med= 0.0% p90= 20.9% max= 41.8% >10%= 7 exact=26
  L(K)                                       cover=36 gmean=  437.6 regret med=33.7% p90=108.9% max=152.0% >10%=27 exact= 2
  L(D)                                       cover=36 gmean=  439.9 regret med=34.6% p90=108.9% max=152.0% >10%=27 exact= 2
  L(K,D)                                     cover=37 gmean=  459.1 regret med=19.7% p90=105.3% max=124.2% >10%=26 exact= 3
  fixed 16                                   cover=37 gmean=  454.4 regret med=19.4% p90= 95.3% max=154.4% >10%=24 exact= 9
  fixed 128                                  cover=27 gmean=  314.5 regret med= 0.0% p90= 56.2% max=105.0% >10%=11 exact=15

## Identical circuits across architectures: best horizon (EPR) with K, D, hub ratio

  family      64q grid                    hh ring                     hh star                     
  ae          L=128 (157) K=6 D=3 hub=1.29L=128 (69) K=4 D=2 hub=1.00 L=8 (149) K=4 D=2 hub=2.00  
  qft         L=16 (262) K=6 D=3 hub=1.29 L=128 (109) K=4 D=2 hub=1.00L=128 (117) K=4 D=2 hub=2.00
  qnn         L=8 (638) K=6 D=3 hub=1.29  L=32 (185) K=4 D=2 hub=1.00 L=128 (318) K=4 D=2 hub=2.00
  random      L=16 (737) K=6 D=3 hub=1.29 L=32 (442) K=4 D=2 hub=1.00 L=4 (510) K=4 D=2 hub=2.00  
  qpeexact    L=32 (209) K=6 D=3 hub=1.29 L=64 (87) K=4 D=2 hub=1.00  L=16 (162) K=4 D=2 hub=2.00 
  qaoa        L=8 (775) K=6 D=3 hub=1.29  L=8 (244) K=4 D=2 hub=1.00  L=4 (401) K=4 D=2 hub=2.00  
  multiplier  L=64 (989) K=6 D=3 hub=1.29 L=64 (456) K=4 D=2 hub=1.00 L=128 (455) K=4 D=2 hub=2.00

## Per-instance oracle horizon and features

  key                           n  K  D  hub   rho  depth     cx bestL   best    @16
  main/25/ae                   25  4  2 1.00  0.93    395    558    16     65     65
  main/25/qft                  25  4  2 1.00  0.92    173    580    16     74     74
  main/25/qnn                  25  4  2 1.00  1.00    259   1223    16    119    119
  main/25/random               25  4  2 1.00  0.85    589   1124    16    393    393
  main/64/ae                   64  6  3 1.29  0.49   1058   1962   128    157    177
  main/64/qft                  64  6  3 1.29  0.48    446   1966    16    262    262
  main/64/qnn_OLD_DEEP         64  6  3 1.29  1.00    650   8126     8    638    864
  main/64/random               64  6  3 1.29  0.33    403   1627    16    737    737
  main/64/qpeexact             64  6  3 1.29  0.53    626   2139    32    209    222
  main/64/qaoa                 64  6  3 1.29  0.49    493   3920     8    775    854
  main/64/multiplier           64  6  3 1.29  0.47  22469  13040    64    989   1358
  main/80/ae                   80  6  3 1.29  0.44    905   2780   128    299    490
  main/80/qft                  80  6  3 1.29  0.42    555   2660    48    342    446
  main/80/qnn_DEEP             80  6  3 1.29  1.00    809  12718     4   1070   1517
  main/80/random               80  6  3 1.29  0.97   3478  23381    16  11040  11040
  main/80/qpeexact             80  6  3 1.29  0.44    786   2779   128    291    526
  main/80/qaoa                 80  6  3 1.29  0.48    583   6096    16   1122   1122
  main/80/multiplier           80  6  3 1.29  0.45  35127  20378    48   2405   3501
  scaleup/100/qft             100  6  3 1.29  0.35    695   3420   128    198    446
  scaleup/100/qpeexact        100  6  3 1.29  0.36    986   3579   128    200    262
  scaleup/200/qft             200 12  5 1.41  0.18   1395   7220   128    579   1131
  scaleup/200/qpeexact        200 12  5 1.41  0.19   1986   7579   128    528   1343
  scaleup/360/qft             360 20  7 1.29  0.10   2515  13300   128   1170   2720
  scaleup/360/qpeexact        360 20  7 1.29  0.11   3588  13979   128   1224   2342
  heavyhex/ring/ae             64  4  2 1.00  0.49   1058   1962   128     69    116
  heavyhex/ring/qft            64  4  2 1.00  0.48    446   1966   128    109    141
  heavyhex/ring/qnn            64  4  2 1.00  1.00    650   8126    32    185    240
  heavyhex/ring/random         64  4  2 1.00  0.33    403   1627    32    442    506
  heavyhex/ring/qpeexact       64  4  2 1.00  0.53    626   2139    64     87    116
  heavyhex/ring/qaoa           64  4  2 1.00  0.49    493   3920     8    244    248
  heavyhex/ring/multiplier     64  4  2 1.00  0.47  22469  13040    64    456    506
  heavyhex/star/ae             64  4  2 2.00  0.49   1058   1962     8    149    161
  heavyhex/star/qft            64  4  2 2.00  0.48    446   1966   128    117    124
  heavyhex/star/qnn            64  4  2 2.00  1.00    650   8126   128    318    535
  heavyhex/star/random         64  4  2 2.00  0.33    403   1627     4    510    609
  heavyhex/star/qpeexact       64  4  2 2.00  0.53    626   2139    16    162    162
  heavyhex/star/qaoa           64  4  2 2.00  0.49    493   3920     4    401    473
  heavyhex/star/multiplier     64  4  2 2.00  0.47  22469  13040   128    455   None
