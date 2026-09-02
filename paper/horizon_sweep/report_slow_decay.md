## coverage
  base      288 cells  {'completed': 271, 'timeout': 15, 'livelock': 2}  unverified=0
  floor0    288 cells  {'completed': 285, 'timeout': 2, 'livelock': 1}  unverified=0
  slow95    336 cells  {'completed': 332, 'timeout': 4}  unverified=0
  slow97    336 cells  {'completed': 328, 'timeout': 7, 'livelock': 1}  unverified=0
  slow99    336 cells  {'completed': 319, 'timeout': 15, 'livelock': 2}  unverified=0

## A. ONE slow route at each L vs the shipped 3-route rule (paired, non-trivial)
  arm/L            n  ref(3rt)  slow(1rt)    delta  W/L/T   completes
  slow95/4        38     365.6      474.5   +29.8%  4/32/2   38/38
  slow95/8        38     365.6      489.2   +33.8%  6/31/1   38/38
  slow95/16       37     353.9      442.3   +25.0%  2/32/3   37/38
  slow95/32       37     333.4      410.7   +23.2%  8/29/0   37/38
  slow95/64       38     365.6      439.9   +20.3%  6/32/0   38/38
  slow95/128      37     333.4      415.0   +24.5%  6/31/0   37/38
  slow95/256      37     333.4      411.7   +23.5%  7/30/0   37/38
  slow97/4        38     365.6      474.5   +29.8%  4/32/2   38/38
  slow97/8        37     354.3      458.4   +29.4%  4/31/2   37/38
  slow97/16       37     354.3      449.0   +26.7%  4/33/0   37/38
  slow97/32       37     354.3      445.5   +25.8%  7/30/0   37/38
  slow97/64       37     333.4      432.8   +29.8%  4/32/1   37/38
  slow97/128      36     322.8      403.6   +25.0%  9/27/0   36/38
  slow97/256      36     330.6      410.1   +24.1%  7/29/0   36/38
  slow99/4        38     365.6      474.5   +29.8%  4/32/2   38/38
  slow99/8        38     365.6      484.2   +32.4%  4/32/2   38/38
  slow99/16       37     333.4      436.9   +31.0%  5/32/0   37/38
  slow99/32       37     363.5      492.0   +35.4%  4/33/0   37/38
  slow99/64       37     354.3      467.9   +32.1%  6/31/0   37/38
  slow99/128      32     293.7      328.5   +11.8%  13/19/0   32/38
  slow99/256      30     285.9      322.0   +12.6%  11/19/0   30/38

  best single route completing every instance: slow95 at L=64 -> 439.9 vs 365.6 (+20.3%) on n=38

## A2. per suite, best slow single route vs the 3-route rule
  group      ref(3rt)                slow95                slow97                slow99
  main25        122.5    140.4@L16 (+14.7%)      134.6@L8 (+9.9%)     137.8@L8 (+12.5%)
  main64        447.3     467.0@L32 (+4.4%)     485.6@L32 (+8.6%)     460.9@L16 (+3.1%)
  main80       1035.7   1213.0@L64 (+17.1%)   1219.9@L32 (+17.8%)   1173.2@L32 (+13.3%)
  scaleup       508.7    884.7@L64 (+73.9%)   851.9@L256 (+67.4%)    523.4@L128 (+2.9%)
  ring          195.4    209.1@L128 (+7.0%)     222.3@L4 (+13.8%)   221.3@L128 (+13.2%)
  star          277.8     293.1@L64 (+5.5%)      305.3@L4 (+9.9%)      305.3@L4 (+9.9%)
  all           365.6    439.9@L64 (+20.3%)     474.5@L4 (+29.8%)     474.5@L4 (+29.8%)

## B. flatness of EPR in L (per-instance max/min over completed horizons)
  arm        median   gmean  >1.5x   >2x   best-L histogram
  base         1.59    1.64     24     8   {4: 3, 8: 4, 16: 9, 32: 3, 64: 4, 128: 15}
  floor0       1.38    1.35     14     1   {4: 5, 8: 3, 16: 9, 32: 3, 64: 10, 128: 8}
  slow95       1.45    1.43     16     4   {4: 6, 8: 4, 16: 5, 32: 6, 64: 11, 128: 4, 256: 2}
  slow97       1.44    1.46     15     4   {4: 7, 8: 8, 16: 7, 32: 1, 64: 3, 128: 8, 256: 4}
  slow99       1.75    1.71     27    10   {4: 4, 8: 8, 16: 4, 32: 2, 64: 2, 128: 12, 256: 6}

## B2. flatness restricted to deep horizons only (L >= 32)
  base      median 1.43  gmean 1.43  n=36
  floor0    median 1.11  gmean 1.19  n=37
  slow95    median 1.24  gmean 1.25  n=37
  slow97    median 1.27  gmean 1.24  n=37
  slow99    median 1.34  gmean 1.45  n=38

## C. scale-up detail (where floor0 lost 62%)
  instance                  3-route     95@64    95@128    95@256     97@64    97@128    97@256     99@64    99@128    99@256
  scaleup/100/qft               198       331       400       400       295       302       302       368       193       213
  scaleup/100/qpeexact          200       256       265       265       290       291       291       371       209       209
  scaleup/200/qft               579      1300       984      1114      1143      1112      1124      1122       552       606
  scaleup/200/qpeexact          528       916       917       837      1434      1125      1045       865       601       582
  scaleup/360/qft              1170      2497      2354      2422      2449      2307      1919         -      1283      1325
  scaleup/360/qpeexact         1224      1903      2182      2362      1951      1715      1929      2365      1198      1254

## D. best-of-3 within each slow arm (is a portfolio still needed?)
  slow95   best-of-(16, 64, 256)  n=38  410.1 vs 365.6 (+12.2%)
  slow95   best-of-(32, 128, 256)  n=37  375.8 vs 333.4 (+12.7%)
  slow95   best-of-(16, 128, 256)  n=38  416.2 vs 365.6 (+13.8%)
  slow97   best-of-(16, 64, 256)  n=38  417.0 vs 365.6 (+14.0%)
  slow97   best-of-(32, 128, 256)  n=38  421.9 vs 365.6 (+15.4%)
  slow97   best-of-(16, 128, 256)  n=38  415.2 vs 365.6 (+13.6%)
  slow99   best-of-(16, 64, 256)  n=38  379.9 vs 365.6 (+3.9%)
  slow99   best-of-(32, 128, 256)  n=38  394.1 vs 365.6 (+7.8%)
  slow99   best-of-(16, 128, 256)  n=37  344.8 vs 333.4 (+3.4%)

## E. per-instance: shipped 3-route vs the best single slow route
  (single route = slow95 at L=64)
  instance                    3-route   single    delta
  main/25/ae                       65       84   +29.2%
  main/25/qft                      74       91   +23.0%
  main/25/qnn                     119      202   +69.7%
  main/25/random                  393      413    +5.1%
  main/64/ae                      157      171    +8.9%
  main/64/qft                     262      339   +29.4%
  main/64/qnn_OLD_DEEP            638      709   +11.1%
  main/64/random                  737      746    +1.2%
  main/64/qpeexact                222      231    +4.1%
  main/64/qaoa                    775      802    +3.5%
  main/64/multiplier             1076     1269   +17.9%
  main/80/ae                      299      366   +22.4%
  main/80/qft                     446      465    +4.3%
  main/80/qnn_DEEP               1070     1337   +25.0%
  main/80/random                11040    11708    +6.1%
  main/80/qpeexact                291      314    +7.9%
  main/80/qaoa                   1122     1680   +49.7%
  main/80/multiplier             2486     2750   +10.6%
  scaleup/100/qft                 198      331   +67.2%
  scaleup/100/qpeexact            200      256   +28.0%
  scaleup/200/qft                 579     1300  +124.5%
  scaleup/200/qpeexact            528      916   +73.5%
  scaleup/360/qft                1170     2497  +113.4%
  scaleup/360/qpeexact           1224     1903   +55.5%
  heavyhex/ring/ae                 69      120   +73.9%
  heavyhex/ring/qft               109      130   +19.3%
  heavyhex/ring/qnn               240      236    -1.7%
  heavyhex/ring/random            465      454    -2.4%
  heavyhex/ring/qpeexact          105      119   +13.3%
  heavyhex/ring/qaoa              244      260    +6.6%
  heavyhex/ring/multiplier        506      343   -32.2%
  heavyhex/star/ae                149      156    +4.7%
  heavyhex/star/qft               117      119    +1.7%
  heavyhex/star/qnn               449      420    -6.5%
  heavyhex/star/random            547      548    +0.2%
  heavyhex/star/qpeexact          162      154    -4.9%
  heavyhex/star/qaoa              405      369    -8.9%
  heavyhex/star/multiplier        455      765   +68.1%

## F. wall time: one slow route vs three base routes
  slow95 at L=64: 351s for one route over 38 instances vs 3591s for the 3-route rule (0.10x)
  slow95 at L=128: 575s for one route over 38 instances vs 3591s for the 3-route rule (0.16x)
  slow95 at L=256: 662s for one route over 38 instances vs 3591s for the 3-route rule (0.18x)
  slow97 at L=64: 471s for one route over 38 instances vs 3591s for the 3-route rule (0.13x)
  slow97 at L=128: 839s for one route over 38 instances vs 3591s for the 3-route rule (0.23x)
  slow97 at L=256: 664s for one route over 38 instances vs 3591s for the 3-route rule (0.18x)
  slow99 at L=64: 637s for one route over 38 instances vs 3591s for the 3-route rule (0.18x)
  slow99 at L=128: 1957s for one route over 38 instances vs 3591s for the 3-route rule (0.55x)
  slow99 at L=256: 2597s for one route over 38 instances vs 3591s for the 3-route rule (0.72x)
