## data coverage (cells per arm over H6 x 48 instances)
  base     cells=288/288 status={'completed': 271, 'timeout': 15, 'livelock': 2} unverified_completions=0
  floor0   cells=288/288 status={'completed': 285, 'timeout': 2, 'livelock': 1} unverified_completions=0
  floor25  cells=288/288 status={'completed': 277, 'timeout': 8, 'livelock': 3} unverified_completions=0
  flat     cells=288/288 status={'completed': 265, 'timeout': 23} unverified_completions=0

## paired gmean EPR by policy: each arm vs base, on instances both complete
### fixed L=16
  main25   floor0: n=4 base=122.5 arm=135.3 (+10.5%) W/L=0/3 completes 4 vs 4 | floor25: n=4 base=122.5 arm=148.7 (+21.5%) W/L=0/4 completes 4 vs 4 | flat: n=4 base=122.5 arm=148.7 (+21.4%) W/L=1/3 completes 4 vs 4
  main64   floor0: n=7 base=498.1 arm=522.1 (+4.8%) W/L=3/4 completes 7 vs 7 | floor25: n=7 base=498.1 arm=525.1 (+5.4%) W/L=2/5 completes 7 vs 7 | flat: n=7 base=498.1 arm=492.5 (-1.1%) W/L=5/2 completes 7 vs 7
  main80   floor0: n=7 base=1335.1 arm=1346.7 (+0.9%) W/L=5/2 completes 7 vs 7 | floor25: n=6 base=938.9 arm=923.5 (-1.6%) W/L=4/2 completes 6 vs 7 | flat: n=7 base=1335.1 arm=1158.0 (-13.3%) W/L=4/3 completes 7 vs 7
  scaleup  floor0: n=6 base=1020.7 arm=964.1 (-5.5%) W/L=4/2 completes 6 vs 6 | floor25: n=6 base=1020.7 arm=985.2 (-3.5%) W/L=4/2 completes 6 vs 6 | flat: n=5 base=966.2 arm=985.0 (+2.0%) W/L=2/3 completes 5 vs 6
  ring     floor0: n=7 base=224.7 arm=235.0 (+4.6%) W/L=5/2 completes 7 vs 7 | floor25: n=6 base=196.3 arm=187.6 (-4.4%) W/L=3/1 completes 6 vs 7 | flat: n=7 base=224.7 arm=233.4 (+3.9%) W/L=4/3 completes 7 vs 7
  star     floor0: n=6 base=281.6 arm=269.3 (-4.4%) W/L=2/4 completes 7 vs 6 | floor25: n=6 base=281.6 arm=276.4 (-1.8%) W/L=2/4 completes 7 vs 6 | flat: n=6 base=281.6 arm=300.7 (+6.8%) W/L=2/4 completes 7 vs 6
  all      floor0: n=37 base=454.4 arm=460.5 (+1.3%) W/L=19/17 completes 38 vs 37 | floor25: n=35 base=413.5 arm=418.9 (+1.3%) W/L=15/18 completes 36 vs 37 | flat: n=36 base=440.9 arm=446.5 (+1.3%) W/L=18/18 completes 37 vs 37
### fixed L=4
  main25   floor0: n=4 base=153.3 arm=153.3 (+0.0%) W/L=0/0 completes 4 vs 4 | floor25: n=4 base=153.3 arm=153.3 (+0.0%) W/L=0/0 completes 4 vs 4 | flat: n=4 base=153.3 arm=157.5 (+2.7%) W/L=2/1 completes 4 vs 4
  main64   floor0: n=7 base=562.6 arm=562.6 (+0.0%) W/L=0/0 completes 7 vs 7 | floor25: n=7 base=562.6 arm=562.6 (+0.0%) W/L=0/0 completes 7 vs 7 | flat: n=7 base=562.6 arm=549.8 (-2.3%) W/L=3/3 completes 7 vs 7
  main80   floor0: n=7 base=1340.8 arm=1340.8 (+0.0%) W/L=0/0 completes 7 vs 7 | floor25: n=7 base=1340.8 arm=1340.8 (+0.0%) W/L=0/0 completes 7 vs 7 | flat: n=7 base=1340.8 arm=1160.6 (-13.4%) W/L=5/1 completes 7 vs 7
  scaleup  floor0: n=6 base=1004.9 arm=1004.9 (+0.0%) W/L=0/0 completes 6 vs 6 | floor25: n=6 base=1004.9 arm=1004.9 (+0.0%) W/L=0/0 completes 6 vs 6 | flat: n=6 base=1004.9 arm=1072.8 (+6.8%) W/L=2/4 completes 6 vs 6
  ring     floor0: n=7 base=222.6 arm=222.6 (+0.0%) W/L=0/0 completes 7 vs 7 | floor25: n=7 base=222.6 arm=222.6 (+0.0%) W/L=0/0 completes 7 vs 7 | flat: n=7 base=222.6 arm=217.8 (-2.2%) W/L=2/0 completes 7 vs 7
  star     floor0: n=7 base=305.3 arm=305.3 (+0.0%) W/L=0/0 completes 7 vs 7 | floor25: n=7 base=305.3 arm=305.3 (+0.0%) W/L=0/0 completes 7 vs 7 | flat: n=7 base=305.3 arm=316.6 (+3.7%) W/L=0/5 completes 7 vs 7
  all      floor0: n=38 base=475.3 arm=475.3 (+0.0%) W/L=0/0 completes 38 vs 38 | floor25: n=38 base=475.3 arm=475.3 (+0.0%) W/L=0/0 completes 38 vs 38 | flat: n=38 base=475.3 arm=468.2 (-1.5%) W/L=14/14 completes 38 vs 38
### fixed L=128
  main25   floor0: n=4 base=190.9 arm=148.6 (-22.2%) W/L=3/1 completes 4 vs 4 | floor25: n=4 base=190.9 arm=180.7 (-5.3%) W/L=3/1 completes 4 vs 4 | flat: n=2 base=245.9 arm=279.3 (+13.6%) W/L=0/2 completes 2 vs 4
  main64   floor0: n=2 base=411.0 arm=481.4 (+17.1%) W/L=0/2 completes 7 vs 2 | floor25: n=2 base=411.0 arm=410.1 (-0.2%) W/L=1/1 completes 6 vs 2 | flat: n=1 base=1076.0 arm=1307.0 (+21.5%) W/L=0/1 completes 2 vs 2
  main80   floor0: n=3 base=600.3 arm=819.1 (+36.5%) W/L=0/3 completes 6 vs 3 | floor25: n=3 base=600.3 arm=732.3 (+22.0%) W/L=0/3 completes 5 vs 3 | flat: n=3 base=600.3 arm=682.7 (+13.7%) W/L=0/3 completes 3 vs 3
  scaleup  floor0: n=6 base=508.7 arm=835.9 (+64.3%) W/L=0/6 completes 6 vs 6 | floor25: n=6 base=508.7 arm=494.2 (-2.9%) W/L=2/4 completes 6 vs 6 | flat: n=6 base=508.7 arm=582.0 (+14.4%) W/L=0/6 completes 6 vs 6
  ring     floor0: n=6 base=204.3 arm=217.7 (+6.5%) W/L=2/4 completes 7 vs 6 | floor25: n=6 base=204.3 arm=185.1 (-9.4%) W/L=5/1 completes 7 vs 6 | flat: n=5 base=190.6 arm=221.2 (+16.1%) W/L=2/3 completes 5 vs 6
  star     floor0: n=6 base=276.4 arm=312.4 (+13.0%) W/L=3/3 completes 7 vs 6 | floor25: n=6 base=276.4 arm=261.6 (-5.4%) W/L=3/3 completes 7 vs 6 | flat: n=5 base=238.5 arm=256.4 (+7.5%) W/L=2/3 completes 5 vs 6
  all      floor0: n=27 base=314.5 arm=369.4 (+17.4%) W/L=8/19 completes 37 vs 27 | floor25: n=27 base=314.5 arm=306.2 (-2.6%) W/L=14/13 completes 35 vs 27 | flat: n=22 base=339.4 arm=384.6 (+13.3%) W/L=4/18 completes 23 vs 27
### shipped rule (3 routes)
  main25   floor0: n=4 base=122.5 arm=135.3 (+10.5%) W/L=0/3 completes 4 vs 4 | floor25: n=4 base=122.5 arm=140.3 (+14.5%) W/L=0/4 completes 4 vs 4 | flat: n=4 base=122.5 arm=132.0 (+7.8%) W/L=1/3 completes 4 vs 4
  main64   floor0: n=7 base=447.3 arm=444.7 (-0.6%) W/L=3/4 completes 7 vs 7 | floor25: n=7 base=447.3 arm=436.3 (-2.4%) W/L=4/3 completes 7 vs 7 | flat: n=7 base=447.3 arm=477.0 (+6.6%) W/L=3/4 completes 7 vs 7
  main80   floor0: n=7 base=1035.7 arm=1150.9 (+11.1%) W/L=2/4 completes 7 vs 7 | floor25: n=7 base=1035.7 arm=1119.9 (+8.1%) W/L=1/5 completes 7 vs 7 | flat: n=7 base=1035.7 arm=1121.2 (+8.3%) W/L=1/6 completes 7 vs 7
  scaleup  floor0: n=6 base=508.7 arm=824.9 (+62.1%) W/L=0/6 completes 6 vs 6 | floor25: n=6 base=508.7 arm=494.2 (-2.9%) W/L=2/4 completes 6 vs 6 | flat: n=6 base=508.7 arm=582.0 (+14.4%) W/L=0/6 completes 6 vs 6
  ring     floor0: n=7 base=195.4 arm=226.8 (+16.1%) W/L=1/6 completes 7 vs 7 | floor25: n=7 base=195.4 arm=183.3 (-6.2%) W/L=4/2 completes 7 vs 7 | flat: n=7 base=195.4 arm=206.7 (+5.8%) W/L=5/2 completes 7 vs 7
  star     floor0: n=7 base=277.8 arm=287.4 (+3.4%) W/L=4/2 completes 7 vs 7 | floor25: n=7 base=277.8 arm=264.6 (-4.8%) W/L=5/1 completes 7 vs 7 | flat: n=7 base=277.8 arm=292.1 (+5.1%) W/L=2/4 completes 7 vs 7
  all      floor0: n=38 base=365.6 arm=420.1 (+14.9%) W/L=10/25 completes 38 vs 38 | floor25: n=38 base=365.6 arm=365.2 (-0.1%) W/L=16/19 completes 38 vs 38 | flat: n=38 base=365.6 arm=394.2 (+7.8%) W/L=12/25 completes 38 vs 38
### global {4,16,128}
  main25   floor0: n=4 base=122.5 arm=127.6 (+4.2%) W/L=0/3 completes 4 vs 4 | floor25: n=4 base=122.5 arm=140.3 (+14.5%) W/L=0/4 completes 4 vs 4 | flat: n=4 base=122.5 arm=145.1 (+18.5%) W/L=1/3 completes 4 vs 4
  main64   floor0: n=7 base=455.5 arm=444.8 (-2.4%) W/L=3/4 completes 7 vs 7 | floor25: n=7 base=455.5 arm=450.5 (-1.1%) W/L=4/3 completes 7 vs 7 | flat: n=7 base=455.5 arm=483.0 (+6.0%) W/L=3/3 completes 7 vs 7
  main80   floor0: n=7 base=1035.7 arm=1175.9 (+13.5%) W/L=2/4 completes 7 vs 7 | floor25: n=7 base=1035.7 arm=1136.2 (+9.7%) W/L=1/5 completes 7 vs 7 | flat: n=7 base=1035.7 arm=1054.1 (+1.8%) W/L=3/4 completes 7 vs 7
  scaleup  floor0: n=6 base=508.7 arm=824.9 (+62.1%) W/L=0/6 completes 6 vs 6 | floor25: n=6 base=508.7 arm=494.2 (-2.9%) W/L=2/4 completes 6 vs 6 | flat: n=6 base=508.7 arm=582.0 (+14.4%) W/L=0/6 completes 6 vs 6
  ring     floor0: n=7 base=196.2 arm=211.1 (+7.6%) W/L=2/4 completes 7 vs 7 | floor25: n=7 base=196.2 arm=183.3 (-6.5%) W/L=5/2 completes 7 vs 7 | flat: n=7 base=196.2 arm=205.8 (+4.9%) W/L=4/2 completes 7 vs 7
  star     floor0: n=7 base=262.7 arm=276.5 (+5.2%) W/L=3/3 completes 7 vs 7 | floor25: n=7 base=262.7 arm=253.6 (-3.5%) W/L=4/2 completes 7 vs 7 | flat: n=7 base=262.7 arm=297.1 (+13.1%) W/L=0/7 completes 7 vs 7
  all      floor0: n=38 base=363.3 arm=410.7 (+13.0%) W/L=10/24 completes 38 vs 38 | floor25: n=38 base=363.3 arm=365.5 (+0.6%) W/L=16/20 completes 38 vs 38 | flat: n=38 base=363.3 arm=395.4 (+8.8%) W/L=11/25 completes 38 vs 38
### oracle over H6
  main25   floor0: n=4 base=122.5 arm=126.9 (+3.6%) W/L=1/2 completes 4 vs 4 | floor25: n=4 base=122.5 arm=135.1 (+10.3%) W/L=0/3 completes 4 vs 4 | flat: n=4 base=122.5 arm=132.0 (+7.8%) W/L=1/3 completes 4 vs 4
  main64   floor0: n=7 base=438.1 arm=439.7 (+0.4%) W/L=4/3 completes 7 vs 7 | floor25: n=7 base=438.1 arm=433.1 (-1.1%) W/L=4/3 completes 7 vs 7 | flat: n=7 base=438.1 arm=465.6 (+6.3%) W/L=2/5 completes 7 vs 7
  main80   floor0: n=7 base=1008.1 arm=1105.8 (+9.7%) W/L=2/4 completes 7 vs 7 | floor25: n=7 base=1008.1 arm=1092.0 (+8.3%) W/L=0/6 completes 7 vs 7 | flat: n=7 base=1008.1 arm=1032.1 (+2.4%) W/L=3/4 completes 7 vs 7
  scaleup  floor0: n=6 base=508.7 arm=824.9 (+62.1%) W/L=0/6 completes 6 vs 6 | floor25: n=6 base=508.7 arm=494.2 (-2.9%) W/L=2/4 completes 6 vs 6 | flat: n=6 base=508.7 arm=582.0 (+14.4%) W/L=0/6 completes 6 vs 6
  ring     floor0: n=7 base=179.3 arm=205.5 (+14.6%) W/L=2/5 completes 7 vs 7 | floor25: n=7 base=179.3 arm=178.8 (-0.3%) W/L=4/2 completes 7 vs 7 | flat: n=7 base=179.3 arm=196.8 (+9.7%) W/L=2/5 completes 7 vs 7
  star     floor0: n=7 base=261.5 arm=271.3 (+3.8%) W/L=4/3 completes 7 vs 7 | floor25: n=7 base=261.5 arm=253.6 (-3.0%) W/L=4/2 completes 7 vs 7 | flat: n=7 base=261.5 arm=273.1 (+4.4%) W/L=3/4 completes 7 vs 7
  all      floor0: n=38 base=352.7 arm=401.6 (+13.8%) W/L=13/23 completes 38 vs 38 | floor25: n=38 base=352.7 arm=357.1 (+1.2%) W/L=14/20 completes 38 vs 38 | flat: n=38 base=352.7 arm=378.3 (+7.2%) W/L=11/27 completes 38 vs 38

## horizon sensitivity per arm (non-trivial instances with >=2 completed horizons)
  base     n=38 spread max/min: median 1.59 gmean 1.64 | unimodal 11/38 mean minima 1.95 | best-L histogram {4: 3, 8: 4, 16: 9, 32: 3, 64: 4, 128: 15} | timeouts 15 livelocks 2
  floor0   n=38 spread max/min: median 1.38 gmean 1.35 | unimodal 12/38 mean minima 1.74 | best-L histogram {4: 5, 8: 3, 16: 9, 32: 3, 64: 10, 128: 8} | timeouts 2 livelocks 1
  floor25  n=38 spread max/min: median 1.62 gmean 1.63 | unimodal 9/38 mean minima 1.87 | best-L histogram {4: 4, 8: 4, 16: 5, 32: 6, 64: 1, 128: 18} | timeouts 8 livelocks 3
  flat     n=38 spread max/min: median 1.45 gmean 1.56 | unimodal 8/38 mean minima 1.95 | best-L histogram {4: 5, 8: 7, 16: 9, 64: 6, 128: 11} | timeouts 23 livelocks 0

## per-horizon gmean per arm (instances completed at that L in ALL arms)
  L=4    n=38 base=   475.3 floor0=   475.3 floor25=   475.3 flat=   468.2
  L=8    n=34 base=   392.5 floor0=   389.3 floor25=   389.3 flat=   386.8
  L=16   n=34 base=   399.4 floor0=   402.1 floor25=   406.8 flat=   405.5
  L=32   n=33 base=   372.1 floor0=   378.3 floor25=   374.5 flat=   414.4
  L=64   n=32 base=   360.2 floor0=   333.7 floor25=   375.3 flat=   380.5
  L=128  n=22 base=   339.4 floor0=   431.4 floor25=   330.8 flat=   384.6

## per-instance oracle (best over H6) per arm
  key                                   base          floor0         floor25            flat
  main/25/ae                           65@16           65@16            68@4            81@8
  main/25/qft                          74@16          79@128           96@32            75@8
  main/25/qnn                         119@16          130@16          130@16          128@16
  main/25/random                      393@16          388@32          393@32          391@16
  main/64/ae                         157@128          163@64         167@128           180@8
  main/64/qft                         262@16         263@128         250@128          301@64
  main/64/qnn_OLD_DEEP                 638@8           571@8           571@8           658@4
  main/64/random                      737@16          701@64          747@16           706@8
  main/64/qpeexact                    209@32         196@128          206@16          214@16
  main/64/qaoa                         775@8          679@16          774@32          738@16
  main/64/multiplier                  989@64          1391@4        1007@128         1193@64
  main/80/ae                         299@128          379@32          354@32           297@4
  main/80/qft                         369@64          298@64         381@128          333@64
  main/80/qnn_DEEP                    1070@4          1070@4          1070@4         1048@16
  main/80/random                    11040@16        10921@16         11067@8        11138@16
  main/80/qpeexact                   291@128          394@32         354@128         320@128
  main/80/qaoa                       1122@16          1247@8          1247@8          1350@4
  main/80/multiplier                2486@128        3118@128         2627@64         2502@16
  scaleup/100/qft                    198@128          438@16         168@128         248@128
  scaleup/100/qpeexact               200@128          260@64         210@128         215@128
  scaleup/200/qft                    579@128         873@128         447@128         626@128
  scaleup/200/qpeexact               528@128         730@128         579@128         637@128
  scaleup/360/qft                   1170@128         2385@16        1178@128        1338@128
  scaleup/360/qpeexact              1224@128        1820@128        1355@128        1366@128
  heavyhex/ring/ae                    69@128           113@4          67@128           75@64
  heavyhex/ring/qft                  109@128           125@8         103@128         108@128
  heavyhex/ring/qnn                   185@32         184@128          227@32          239@16
  heavyhex/ring/random                442@32          456@64          434@16           453@4
  heavyhex/ring/qpeexact               87@64           113@4          75@128           113@4
  heavyhex/ring/qaoa                   244@8          243@16           244@8           243@8
  heavyhex/ring/multiplier            456@64          476@64          469@32          474@16
  heavyhex/star/ae                     149@8          135@64         118@128          125@64
  heavyhex/star/qft                  117@128          126@16         109@128         122@128
  heavyhex/star/qnn                  318@128          423@64         399@128         421@128
  heavyhex/star/random                 510@4          474@64           510@4          477@64
  heavyhex/star/qpeexact              162@16          145@64         118@128           163@8
  heavyhex/star/qaoa                   401@4          290@16          290@16           381@8
  heavyhex/star/multiplier           455@128           754@4           754@4         595@128

## base arm vs 2026-09-01 sweep (old selection key): 24 differing completed cells
   ('main/25/qnn', 64, 250, 245)
   ('main/25/qnn', 128, 255, 244)
   ('main/25/random', 16, 401, 393)
   ('main/25/random', 32, 414, 428)
   ('main/64/qft', 32, 330, 313)
   ('main/64/random', 32, 791, 805)
   ('main/64/qaoa', 32, 943, 915)
   ('main/80/qft', 64, 367, 369)
   ('main/80/random', 32, 11302, 11507)
   ('main/80/qaoa', 32, 1364, 1331)
   ('main/80/multiplier', 32, 2371, 2586)
   ('main/80/multiplier', 64, 2651, 3126)
   ('main/80/multiplier', 128, 2411, 2486)
   ('scaleup/200/qft', 16, 1128, 1131)
   ('scaleup/200/qft', 32, 1113, 1096)
   ('scaleup/200/qpeexact', 64, 652, 741)
   ('scaleup/360/qft', 16, 2822, 2720)
   ('scaleup/360/qft', 32, 2888, 2572)
   ('scaleup/360/qft', 128, 1156, 1170)
   ('scaleup/360/qpeexact', 32, 2278, 1909)
   ('scaleup/360/qpeexact', 64, 1828, 1906)
   ('heavyhex/ring/qnn', 128, 290, 289)
   ('heavyhex/ring/random', 32, 434, 442)
   ('heavyhex/ring/qaoa', 64, 414, 397)
