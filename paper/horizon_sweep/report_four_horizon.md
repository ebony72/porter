## PORTER+R with one fixed four-value horizon set, main suite, paper's basis

  basis        dSABRE  +R shipped    +R (4, 8, 16, 128)   +R (4, 16, 64, 128)
  25q (6)        45.8        38.9          38.9 (0.85x)          38.9 (0.85x)
  64q (9)       173.1       185.3         185.3 (1.07x)         185.0 (1.07x)
  80q (9)       412.1       373.0         373.0 (0.91x)         370.4 (0.90x)
  all (24)      171.9       163.1         163.1 (0.95x)         162.5 (0.95x)

  routes:  dSABRE 9 | +R shipped 7 | +R four-set 8
  time:    dSABRE 182s | +R shipped 386s (2.1x) | (4, 8, 16, 128) 499s (2.7x) | (4, 16, 64, 128) 668s (3.7x)
  (4, 8, 16, 128) vs +R shipped: 0 better, 0 worse, 24 tied
  (4, 16, 64, 128) vs +R shipped: 2 better, 2 worse, 20 tied
     better main/64/multiplier         1076 -> 989    (  -8.1%)
     WORSE  main/64/qaoa                586 -> 607    (  +3.6%)
     WORSE  main/64/qnn_OLD_DEEP        638 -> 658    (  +3.1%)
     better main/80/qft                 393 -> 369    (  -6.1%)
