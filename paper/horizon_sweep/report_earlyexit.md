## Q3: termination reasons at L=16 -- 'budget' is the only one a deeper L can relieve
  instance                      calls      cap      dag  budget   bud% deepest  deeper-L can differ?
  main/25/ae                      546        9        2     534  97.8%      16  yes
  main/25/ghz                      10        0        9       1  10.0%       1  yes
  main/25/graphstate               56        0       56       0   0.0%       0  NO -- provably identical
  main/25/qft                     742        2      183     557  75.1%      16  yes
  main/25/qnn                    1052        0        5    1047  99.5%      15  yes
  main/25/random                 3112        2        3    3097  99.5%      16  yes
  main/64/ae                     2425       13        3    2263  93.3%      16  yes
  main/64/ghz                      14        0        3      11  78.6%       1  yes
  main/64/graphstate              330        0      330       0   0.0%       0  NO -- provably identical
  main/64/qft                    3830        6      184    3636  94.9%      16  yes
  main/64/qnn_OLD_DEEP          11395        0        5   11390 100.0%      16  yes
  main/64/random                11264       12       36   11121  98.7%      16  yes
  main/64/qpeexact               3018       35        2    2660  88.1%      16  yes
  main/64/qaoa                  13335       40        2   13244  99.3%      16  yes
  main/64/multiplier             8816        0        6    8588  97.4%      16  yes
  main/80/ae                     4965       13        3    4342  87.5%      16  yes
  main/80/ghz                      16        0        3      13  81.2%       1  yes
  main/80/graphstate              780        0      780       0   0.0%       0  NO -- provably identical
  main/80/qft                    4307       18        1    3626  84.2%      16  yes
  main/80/qnn_DEEP              23834        0        4   23830 100.0%      16  yes
  main/80/random               216910       11       10  216829 100.0%      16  yes
  main/80/qpeexact               5229       18       24    4655  89.0%      16  yes
  main/80/qaoa                  19728       18        4   19678  99.7%      16  yes
  main/80/multiplier            21277        4        6   20085  94.4%      16  yes
  scaleup/100/qft                5242       65        2    3744  71.4%      16  yes
  scaleup/100/qpeexact           5530       87        2    4016  72.6%      16  yes
  scaleup/200/qft               16852      169        1   13004  77.2%      16  yes
  scaleup/200/qpeexact          19450      111        4   12851  66.1%      16  yes
  scaleup/360/qft               38956      342        2   25960  66.6%      16  yes
  scaleup/360/qpeexact          29488      174        1   20091  68.1%      16  yes
  heavyhex/ring/ae               2158       69        2    1357  62.9%      16  yes
  heavyhex/ring/ghz                 4        0        3       1  25.0%       0  yes
  heavyhex/ring/graphstate        156        0      156       0   0.0%       0  NO -- provably identical
  heavyhex/ring/qft              3356        2     1192    2142  63.8%      16  yes
  heavyhex/ring/qnn              4642        0        1    4641 100.0%      15  yes
  heavyhex/ring/random           7656        0       46    7610  99.4%      16  yes
  heavyhex/ring/qpeexact         2158       69        2    1499  69.5%      16  yes
  heavyhex/ring/qaoa             4890       22        2    4802  98.2%      16  yes
  heavyhex/ring/multiplier       5182        0        1    4803  92.7%      16  yes
  heavyhex/star/ae               1230       15        2    1132  92.0%      16  yes
  heavyhex/star/ghz                 6        0        5       1  16.7%       1  yes
  heavyhex/star/graphstate        180        0      180       0   0.0%       0  NO -- provably identical
  heavyhex/star/qft              4370       18      429    3743  85.7%      16  yes
  heavyhex/star/qnn              7520        0        5    7515  99.9%      16  yes
  heavyhex/star/random           9354       34       14    9039  96.6%      16  yes
  heavyhex/star/qpeexact         1372       12        2    1326  96.6%      16  yes
  heavyhex/star/qaoa             7852       11        3    7832  99.7%      16  yes
  heavyhex/star/multiplier    FAILED RuntimeError

  5 of 47 instances never hit the layer budget at L=16: for those, every deeper horizon is provably a wasted route.
