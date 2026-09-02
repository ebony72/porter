# Horizon grid analysis  (source=prev)

## Phase 0: validation

attempted routes: 348; by status: {'completed': 320, 'timeout': 26, 'livelock': 2}
instances: 48, horizon-sensitive (non GHZ/Graphstate): 38; of those lacking a completed L=16 route: ['heavyhex/star/multiplier']
non-completions (28): main/64/ae@256:timeout, main/64/qft@128:timeout, main/64/qft@256:timeout, main/64/qnn_OLD_DEEP@128:timeout, main/64/qnn_OLD_DEEP@256:timeout, main/64/random@128:timeout, main/64/random@256:timeout, main/64/qpeexact@128:timeout, main/64/qpeexact@256:timeout, main/64/qaoa@128:timeout, main/64/qaoa@256:timeout, main/80/qft@128:timeout, main/80/qft@256:timeout, main/80/qnn_DEEP@64:timeout, main/80/qnn_DEEP@128:timeout, main/80/qnn_DEEP@256:timeout, main/80/random@8:timeout, main/80/random@128:timeout, main/80/random@256:timeout, main/80/qaoa@64:timeout, main/80/qaoa@128:timeout, main/80/qaoa@256:timeout, scaleup/360/qft@48:timeout, scaleup/360/qpeexact@8:timeout, heavyhex/ring/qaoa@128:timeout, heavyhex/ring/multiplier@32:livelock, heavyhex/star/qaoa@128:timeout, heavyhex/star/multiplier@16:livelock

## Headline: shipped density rule vs fixed 16 vs oracle (non-trivial instances)

- all, H6 [sweep-guard]: n=38 rule=365.4 oracle=352.2 (headroom -3.6%), fixed16=455.0 on n=37 (penalty +25.3%), gain captured 86%, optimum found 27/38, optimum outside assigned set 11
  outside: ['main/64/qpeexact', 'main/64/multiplier', 'main/80/qft', 'main/80/multiplier', 'heavyhex/ring/qnn', 'heavyhex/ring/random', 'heavyhex/ring/qpeexact', 'heavyhex/ring/multiplier', 'heavyhex/star/qnn', 'heavyhex/star/random', 'heavyhex/star/qaoa']
- all, H6 [live-budget-feasible]: n=38 rule=378.3 oracle=352.2 (headroom -6.9%), fixed16=455.0 on n=37 (penalty +20.9%), gain captured 73%, optimum found 25/38, optimum outside assigned set 13
- main+scaleup, H8 [sweep-guard]: n=24 rule=475.1 oracle=466.7 (headroom -1.8%), fixed16=630.3 on n=24 (penalty +32.7%), gain captured 94%, optimum found 20/24, optimum outside assigned set 4
  outside: ['main/64/qpeexact', 'main/64/multiplier', 'main/80/qft', 'main/80/multiplier']
- main+scaleup, H8 [live-budget-feasible]: n=24 rule=501.8 oracle=466.7 (headroom -7.0%), fixed16=630.3 on n=24 (penalty +25.6%), gain captured 76%, optimum found 18/24, optimum outside assigned set 6

## Phase 1: exhaustive portfolios over H6 = {4,8,16,32,64,128}, non-trivial instances (regret vs H6 oracle)

### r = 1
  (4,)                   cover=38 gmean=  475.3 regret med=32.2% p90=108.9% max=152.0% >10%=27 exact= 3 routes-time=   1.0min
  (16,)                  cover=37 gmean=  455.0 regret med=19.4% p90= 94.8% max=154.4% >10%=24 exact= 9 routes-time=   1.9min
  (32,)                  cover=37 gmean=  458.6 regret med=26.0% p90= 92.2% max=149.8% >10%=26 exact= 4 routes-time=   3.2min
  (8,)                   cover=36 gmean=  429.7 regret med=31.2% p90=109.1% max=227.3% >10%=26 exact= 4 routes-time=  10.7min
### r = 2
  (16, 128)              cover=38 gmean=  373.1 regret med= 0.0% p90= 21.5% max= 41.8% >10%=10 exact=23 routes-time=  59.6min
  (32, 128)              cover=38 gmean=  383.5 regret med= 2.8% p90= 32.6% max= 42.0% >10%=13 exact=18 routes-time=  60.9min
  (4, 128)               cover=38 gmean=  384.8 regret med= 1.5% p90= 38.7% max= 54.5% >10%=12 exact=17 routes-time=  58.7min
  (16, 64)               cover=38 gmean=  412.0 regret med= 8.7% p90= 68.2% max= 91.7% >10%=19 exact=13 routes-time=  17.3min
### r = 3
  (4, 16, 128)           cover=38 gmean=  363.1 regret med= 0.0% p90= 11.0% max= 29.7% >10%= 5 exact=26 routes-time=  60.6min
  (16, 32, 128)          cover=38 gmean=  365.2 regret med= 0.0% p90= 18.0% max= 32.6% >10%= 7 exact=27 routes-time=  62.9min
  (8, 16, 128)           cover=38 gmean=  365.4 regret med= 0.0% p90= 20.7% max= 41.8% >10%= 5 exact=27 routes-time=  70.4min
  (16, 64, 128)          cover=38 gmean=  366.6 regret med= 0.0% p90= 18.0% max= 41.8% >10%= 6 exact=27 routes-time=  75.0min
### r = 4
  (4, 16, 64, 128)       cover=38 gmean=  357.7 regret med= 0.0% p90=  6.2% max= 29.7% >10%= 2 exact=30 routes-time=  76.0min
  (4, 16, 32, 128)       cover=38 gmean=  358.2 regret med= 0.0% p90= 10.2% max= 20.7% >10%= 4 exact=30 routes-time=  63.8min
  (8, 16, 32, 128)       cover=38 gmean=  359.7 regret med= 0.0% p90= 10.6% max= 32.6% >10%= 4 exact=31 routes-time=  73.6min
  (8, 16, 64, 128)       cover=38 gmean=  360.0 regret med= 0.0% p90=  7.1% max= 41.8% >10%= 2 exact=31 routes-time=  85.7min
### r = 5
  (4, 16, 32, 64, 128)   cover=38 gmean=  353.8 regret med= 0.0% p90=  1.2% max= 10.2% >10%= 1 exact=34 routes-time=  79.2min
  (8, 16, 32, 64, 128)   cover=38 gmean=  355.2 regret med= 0.0% p90=  0.0% max= 32.6% >10%= 1 exact=35 routes-time=  88.9min
  (4, 8, 16, 64, 128)    cover=38 gmean=  355.9 regret med= 0.0% p90=  1.7% max= 29.7% >10%= 1 exact=34 routes-time=  86.7min
  (4, 8, 16, 32, 128)    cover=38 gmean=  356.6 regret med= 0.0% p90=  8.8% max= 20.7% >10%= 3 exact=34 routes-time=  74.5min
### named 3-sets
  {4,32,128}                       cover=38 gmean=  371.9 regret med= 0.0% p90= 21.6% max= 38.7% >10%= 9 exact=21 routes-time=  61.9min
  {8,32,128}                       cover=38 gmean=  373.0 regret med= 0.0% p90= 25.7% max= 42.0% >10%= 9 exact=22 routes-time=  71.7min
  {4,16,64}                        cover=38 gmean=  399.2 regret med= 3.2% p90= 64.6% max= 83.4% >10%=15 exact=16 routes-time=  18.2min
  {8,16,64}                        cover=38 gmean=  404.6 regret med= 4.4% p90= 68.2% max= 91.7% >10%=15 exact=17 routes-time=  28.0min
  {8,16,128} (sparse set alone)    cover=38 gmean=  365.4 regret med= 0.0% p90= 20.7% max= 41.8% >10%= 5 exact=27 routes-time=  70.4min
  {4,8,16} (dense set alone)       cover=38 gmean=  431.0 regret med= 9.1% p90= 91.3% max=125.3% >10%=19 exact=16 routes-time=  13.6min
### named 4-sets
  {4,16,64,128}                    cover=38 gmean=  357.7 regret med= 0.0% p90=  6.2% max= 29.7% >10%= 2 exact=30 routes-time=  76.0min
### named 5-sets
  {4,16,32,64,128}                 cover=38 gmean=  353.8 regret med= 0.0% p90=  1.2% max= 10.2% >10%= 1 exact=34 routes-time=  79.2min
  shipped density rule           cover=38 gmean=  365.4 regret med= 0.0% p90= 20.7% max= 41.2% >10%= 5 exact=27

## Phase 1b: same over H8 on the 30 main+scale-up instances (regret vs H8 oracle)

### r = 1
  (16,)                      cover=24 gmean=  630.3 regret med=30.7% p90=125.3% max=154.4% >10%=15 exact= 8 routes-time=   1.3min
  (32,)                      cover=24 gmean=  638.1 regret med=31.5% p90=108.0% max=149.8% >10%=19 exact= 2 routes-time=   2.4min
  (4,)                       cover=24 gmean=  674.7 regret med=39.7% p90=114.3% max=152.0% >10%=19 exact= 1 routes-time=   0.7min
### r = 2
  (16, 128)                  cover=24 gmean=  490.1 regret med= 0.0% p90= 30.4% max= 41.8% >10%= 4 exact=17 routes-time=  47.6min
  (16, 256)                  cover=24 gmean=  508.8 regret med= 1.6% p90= 35.1% max= 41.8% >10%= 8 exact=11 routes-time=  53.6min
  (32, 128)                  cover=24 gmean=  515.3 regret med= 2.8% p90= 32.6% max= 42.0% >10%= 9 exact=11 routes-time=  48.7min
### r = 3
  (4, 16, 128)               cover=24 gmean=  477.6 regret med= 0.0% p90=  8.8% max= 30.4% >10%= 2 exact=18 routes-time=  48.3min
  (8, 16, 128)               cover=24 gmean=  482.0 regret med= 0.0% p90=  8.8% max= 41.8% >10%= 2 exact=19 routes-time=  58.0min
  (16, 48, 128)              cover=24 gmean=  483.4 regret med= 0.0% p90= 10.2% max= 41.8% >10%= 3 exact=18 routes-time=  55.9min
### r = 4
  (4, 16, 48, 128)           cover=24 gmean=  471.0 regret med= 0.0% p90=  3.1% max= 10.2% >10%= 1 exact=19 routes-time=  56.6min
  (4, 16, 64, 128)           cover=24 gmean=  472.1 regret med= 0.0% p90=  6.2% max= 10.2% >10%= 1 exact=19 routes-time=  62.5min
  (4, 16, 32, 128)           cover=24 gmean=  474.2 regret med= 0.0% p90=  8.8% max= 18.7% >10%= 2 exact=20 routes-time=  50.6min
### r = 5
  (4, 8, 16, 48, 128)        cover=24 gmean=  468.5 regret med= 0.0% p90=  1.7% max=  6.2% >10%= 0 exact=21 routes-time=  67.0min
  (4, 16, 32, 48, 128)       cover=24 gmean=  469.5 regret med= 0.0% p90=  1.8% max= 10.2% >10%= 1 exact=21 routes-time=  59.0min
  (4, 8, 16, 64, 128)        cover=24 gmean=  469.6 regret med= 0.0% p90=  1.7% max=  7.3% >10%= 0 exact=21 routes-time=  72.9min
  shipped density rule           cover=24 gmean=  475.1 regret med= 0.0% p90=  6.2% max= 30.4% >10%= 1 exact=20

## Phase 2: instance-level rules, grouped hold-out (H6, non-trivial instances)

### in-sample (fit and evaluated on all instances)
  shipped density rule                       cover=38 gmean=  365.4 regret med= 0.0% p90= 20.7% max= 41.2% >10%= 5 exact=27
  refit density form (2 sets + threshold)    cover=38 gmean=  360.4 regret med= 0.0% p90= 11.7% max= 29.7% >10%= 4 exact=27
  best global 3-set                          cover=38 gmean=  363.1 regret med= 0.0% p90= 11.0% max= 29.7% >10%= 5 exact=26
  L(K)                                       cover=38 gmean=  475.3 regret med=32.2% p90=108.9% max=152.0% >10%=27 exact= 3
  L(D)                                       cover=38 gmean=  475.3 regret med=32.2% p90=108.9% max=152.0% >10%=27 exact= 3
  L(K,D)                                     cover=38 gmean=  452.6 regret med=22.4% p90= 91.7% max=227.3% >10%=25 exact= 6
  fixed 16                                   cover=37 gmean=  455.0 regret med=19.4% p90= 94.8% max=154.4% >10%=24 exact= 9
  fixed 128                                  cover=27 gmean=  314.6 regret med= 0.0% p90= 56.8% max=114.3% >10%=11 exact=14
### leave-one-suite-out
  shipped density rule                       cover=38 gmean=  365.4 regret med= 0.0% p90= 20.7% max= 41.2% >10%= 5 exact=27
  refit density form (2 sets + threshold)    cover=38 gmean=  375.8 regret med= 0.0% p90= 32.6% max= 41.2% >10%= 9 exact=20
  best global 3-set                          cover=38 gmean=  366.5 regret med= 0.0% p90= 20.7% max= 41.8% >10%= 6 exact=25
  L(K)                                       cover=34 gmean=  429.3 regret med=18.7% p90=105.3% max=152.0% >10%=24 exact= 4
  L(D)                                       cover=34 gmean=  429.3 regret med=18.7% p90=105.3% max=152.0% >10%=24 exact= 4
  L(K,D)                                     cover=34 gmean=  423.7 regret med=19.6% p90=105.3% max=152.0% >10%=23 exact= 5
  fixed 16                                   cover=37 gmean=  455.0 regret med=19.4% p90= 94.8% max=154.4% >10%=24 exact= 9
  fixed 128                                  cover=27 gmean=  314.6 regret med= 0.0% p90= 56.8% max=114.3% >10%=11 exact=14
### leave-one-family-out
  shipped density rule                       cover=38 gmean=  365.4 regret med= 0.0% p90= 20.7% max= 41.2% >10%= 5 exact=27
  refit density form (2 sets + threshold)    cover=38 gmean=  373.8 regret med= 0.0% p90= 30.4% max= 59.4% >10%= 8 exact=24
  best global 3-set                          cover=38 gmean=  369.1 regret med= 0.0% p90= 21.5% max= 41.8% >10%= 7 exact=25
  L(K)                                       cover=36 gmean=  437.0 regret med=33.7% p90=108.9% max=152.0% >10%=27 exact= 3
  L(D)                                       cover=36 gmean=  439.3 regret med=34.6% p90=108.9% max=152.0% >10%=27 exact= 3
  L(K,D)                                     cover=37 gmean=  458.8 regret med=23.1% p90=105.3% max=124.2% >10%=26 exact= 4
  fixed 16                                   cover=37 gmean=  455.0 regret med=19.4% p90= 94.8% max=154.4% >10%=24 exact= 9
  fixed 128                                  cover=27 gmean=  314.6 regret med= 0.0% p90= 56.8% max=114.3% >10%=11 exact=14

## Identical circuits across architectures: best horizon (EPR) with K, D, hub ratio

  family      64q grid                    hh ring                     hh star                     
  ae          L=128 (157) K=6 D=3 hub=1.29L=128 (69) K=4 D=2 hub=1.00 L=8 (149) K=4 D=2 hub=2.00  
  qft         L=16 (262) K=6 D=3 hub=1.29 L=128 (109) K=4 D=2 hub=1.00L=128 (117) K=4 D=2 hub=2.00
  qnn         L=8 (638) K=6 D=3 hub=1.29  L=32 (185) K=4 D=2 hub=1.00 L=128 (318) K=4 D=2 hub=2.00
  random      L=16 (737) K=6 D=3 hub=1.29 L=32 (434) K=4 D=2 hub=1.00 L=4 (510) K=4 D=2 hub=2.00  
  qpeexact    L=32 (209) K=6 D=3 hub=1.29 L=64 (87) K=4 D=2 hub=1.00  L=16 (162) K=4 D=2 hub=2.00 
  qaoa        L=8 (775) K=6 D=3 hub=1.29  L=8 (244) K=4 D=2 hub=1.00  L=4 (401) K=4 D=2 hub=2.00  
  multiplier  L=64 (989) K=6 D=3 hub=1.29 L=64 (456) K=4 D=2 hub=1.00 L=128 (455) K=4 D=2 hub=2.00

## Per-instance oracle horizon and features

  key                           n  K  D  hub   rho  depth     cx bestL   best    @16
  main/25/ae                   25  4  2 1.00  0.93    395    558    16     65     65
  main/25/qft                  25  4  2 1.00  0.92    173    580    16     74     74
  main/25/qnn                  25  4  2 1.00  1.00    259   1223    16    119    119
  main/25/random               25  4  2 1.00  0.85    589   1124    16    401    401
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
  main/80/multiplier           80  6  3 1.29  0.45  35127  20378    32   2371   3501
  scaleup/100/qft             100  6  3 1.29  0.35    695   3420   128    198    446
  scaleup/100/qpeexact        100  6  3 1.29  0.36    986   3579   128    200    262
  scaleup/200/qft             200 12  5 1.41  0.18   1395   7220   128    579   1128
  scaleup/200/qpeexact        200 12  5 1.41  0.19   1986   7579   128    528   1343
  scaleup/360/qft             360 20  7 1.29  0.10   2515  13300   128   1156   2822
  scaleup/360/qpeexact        360 20  7 1.29  0.11   3588  13979   128   1224   2342
  heavyhex/ring/ae             64  4  2 1.00  0.49   1058   1962   128     69    116
  heavyhex/ring/qft            64  4  2 1.00  0.48    446   1966   128    109    141
  heavyhex/ring/qnn            64  4  2 1.00  1.00    650   8126    32    185    240
  heavyhex/ring/random         64  4  2 1.00  0.33    403   1627    32    434    506
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
