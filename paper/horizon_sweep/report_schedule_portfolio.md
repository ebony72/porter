## single forward pass: shipped PORTER (3 routes) vs the six-pair portfolio (6 routes)

  basis                  PORTER  six-pair    gain    time   W   L   T
  main 25q                 43.0      43.0    0.0%   5.49x   0   0   6
  main 64q                196.1     194.7   -0.7%   1.97x   3   2   4
  main 80q                398.0     391.1   -1.7%   4.45x   1   0   8
  main all 24             175.0     173.3   -0.9%   3.74x   4   2  18
  scale-up (6)            508.7     474.1   -6.8%   1.96x   2   0   4
  heavy-hex ring (9)       86.1      81.6   -5.3%   2.23x   4   0   5
  heavy-hex star (9)      122.3     109.2  -10.8%   2.19x   5   0   4
  every instance where the six-pair portfolio differs from shipped PORTER

  better main/64/qft                   262 -> 250    (  -4.6%)  winner w=0.25,L=128
  better main/64/qpeexact              222 -> 206    (  -7.2%)  winner w=0.25,L=16
  better main/64/multiplier           1076 -> 1007   (  -6.4%)  winner w=0.25,L=128
  WORSE  main/64/qnn_OLD_DEEP          638 -> 653    (  +2.4%)  winner w=0.25,L=16
  better main/80/qft                   446 -> 381    ( -14.6%)  winner w=0.25,L=128
  WORSE  main/64/qaoa                  775 -> 854    ( +10.2%)  winner w=0.5,L=16
  better scaleup/100/qft               198 -> 168    ( -15.2%)  winner w=0.25,L=128
  better scaleup/200/qft               579 -> 447    ( -22.8%)  winner w=0.25,L=128
  better heavyhex/ring/ae               69 -> 67     (  -2.9%)  winner w=0.25,L=128
  better heavyhex/ring/qft             109 -> 103    (  -5.5%)  winner w=0.25,L=128
  better heavyhex/ring/qpeexact        105 -> 75     ( -28.6%)  winner w=0.25,L=128
  better heavyhex/ring/random          465 -> 434    (  -6.7%)  winner w=0.25,L=16
  better heavyhex/star/ae              149 -> 118    ( -20.8%)  winner w=0.25,L=128
  better heavyhex/star/qft             117 -> 109    (  -6.8%)  winner w=0.25,L=128
  better heavyhex/star/random          547 -> 510    (  -6.8%)  winner w=0.25,L=4
  better heavyhex/star/qpeexact        162 -> 118    ( -27.2%)  winner w=0.25,L=128
  better heavyhex/star/qaoa            405 -> 290    ( -28.4%)  winner w=0.25,L=16

  and for +R over the six-pair portfolio vs the shipped +R:

  better main/64/qpeexact              222 -> 206    (  -7.2%)  w=0.25,L=16
  better main/64/qft                   262 -> 214    ( -18.3%)  w=0.25,L=128
  better main/64/qnn_OLD_DEEP          638 -> 453    ( -29.0%)  w=0.25,L=16
  WORSE  main/64/qaoa                  586 -> 607    (  +3.6%)  w=0.5,L=16
  better main/64/multiplier           1076 -> 1007   (  -6.4%)  w=0.25,L=128
  better main/80/qft                   393 -> 320    ( -18.6%)  w=0.25,L=128
  PORTER+R with the horizon portfolio replaced by a (schedule, horizon) portfolio
  main suite, paper's basis (every circuit), 24 instances

  basis        dSABRE  +R shipped    +R six   +R nine   ratios vs dSABRE
  25q (6)        45.8        38.9      38.9      38.6   0.85x / 0.85x / 0.84x
  64q (9)       173.1       185.3     172.4     173.7   1.07x / 1.00x / 1.00x
  80q (9)       412.1       373.0     364.5     369.9   0.91x / 0.88x / 0.90x
  all (24)      171.9       163.1     157.4     158.4   0.95x / 0.92x / 0.92x

  routes: dSABRE 9 | +R shipped 7 | +R six 10 | +R nine 13
  time:   dSABRE 182s | +R shipped 386s (2.1x) | +R six 1445s (7.9x) | +R nine 1881s (10.3x)
  +R six vs +R shipped: 5 better, 1 worse, 18 tied
  +R nine vs +R shipped: 8 better, 0 worse, 16 tied

  instances the nine-pair portfolio changes:
    main/25/ae                   65 -> 62      (  -4.6%)   winner w=0.0,L=16
    main/64/qpeexact            222 -> 196     ( -11.7%)   winner w=0.0,L=128
    main/64/qft                 262 -> 214     ( -18.3%)   winner w=0.25,L=128
    main/64/qnn_OLD_DEEP        638 -> 552     ( -13.5%)   winner w=0.0,L=128
    main/64/qaoa                586 -> 560     (  -4.4%)   winner w=0.0,L=16
    main/64/multiplier         1076 -> 1007    (  -6.4%)   winner w=0.25,L=128
    main/80/qft                 393 -> 368     (  -6.4%)   winner w=0.0,L=128
    main/80/random            11013 -> 10921   (  -0.8%)   winner w=0.0,L=16
