## coverage (H6 x 48 per arm)
  gamma=0.85   floor bites at layer  5   288 cells  {'completed': 273, 'timeout': 14, 'livelock': 1}
  gamma=0.90*  floor bites at layer  7   288 cells  {'completed': 271, 'timeout': 15, 'livelock': 2}
  gamma=0.95   floor bites at layer 14   288 cells  {'completed': 275, 'timeout': 11, 'livelock': 2}
  gamma=0.99   floor bites at layer 59   288 cells  {'completed': 274, 'timeout': 12, 'livelock': 2}

## EPR by policy, paired against the shipped gamma=0.90
### fixed L=16
  gamma=0.85   n=37  0.90=  454.4  arm=  439.2  ( -3.3%)  W/L=13/13
  gamma=0.95   n=37  0.90=  454.4  arm=  465.1  ( +2.4%)  W/L=16/16
  gamma=0.99   n=36  0.90=  415.8  arm=  429.0  ( +3.2%)  W/L=13/23
### fixed L=128
  gamma=0.85   n=26  0.90=  315.4  arm=  324.4  ( +2.8%)  W/L=7/11
  gamma=0.95   n=27  0.90=  314.5  arm=  325.3  ( +3.4%)  W/L=11/14
  gamma=0.99   n=24  0.90=  327.9  arm=  334.8  ( +2.1%)  W/L=9/15
### shipped 3-route rule
  gamma=0.85   n=38  0.90=  365.6  arm=  368.5  ( +0.8%)  W/L=14/12
  gamma=0.95   n=38  0.90=  365.6  arm=  376.0  ( +2.8%)  W/L=13/20
  gamma=0.99   n=38  0.90=  365.6  arm=  375.6  ( +2.7%)  W/L=13/22
### oracle over H6
  gamma=0.85   n=38  0.90=  352.7  arm=  352.5  ( -0.1%)  W/L=13/13
  gamma=0.95   n=38  0.90=  352.7  arm=  361.3  ( +2.4%)  W/L=14/19
  gamma=0.99   n=38  0.90=  352.7  arm=  363.0  ( +2.9%)  W/L=10/23

## per suite, shipped 3-route rule
  suite          g=0.85     g=0.90*      g=0.95      g=0.99
  main25          123.9       122.5       147.0       134.0
  main64          453.4       447.3       452.5       460.9
  main80         1087.0      1035.7      1053.1      1047.1
  scaleup         508.1       508.7       535.0       555.0
  ring            197.2       195.4       197.0       195.7
  star            268.4       277.8       269.3       271.7

## per-horizon gmean (instances all four arms complete at that L)
  L=4    n=37 g=0.85:  435.8  g=0.90*:  436.4  g=0.95:  435.8  g=0.99:  435.8
  L=8    n=36 g=0.85:  426.3  g=0.90*:  429.7  g=0.95:  429.3  g=0.99:  426.5
  L=16   n=36 g=0.85:  401.6  g=0.90*:  415.8  g=0.95:  426.3  g=0.99:  429.0
  L=32   n=35 g=0.85:  431.5  g=0.90*:  430.0  g=0.95:  434.1  g=0.99:  468.6
  L=64   n=31 g=0.85:  361.2  g=0.90*:  357.4  g=0.95:  374.0  g=0.99:  366.3
  L=128  n=23 g=0.85:  338.5  g=0.90*:  329.6  g=0.95:  344.3  g=0.99:  333.6

## does a wider graded region rescue deep horizons? (completions at L=128)
  gamma=0.85   completes 27/38 at L=128  (fails: 11)
  gamma=0.90*  completes 27/38 at L=128  (fails: 11)
  gamma=0.95   completes 30/38 at L=128  (fails: 8)
  gamma=0.99   completes 27/38 at L=128  (fails: 11)

## horizon sensitivity
  gamma=0.85   spread median 1.62 gmean 1.68  best-L {4: 3, 8: 6, 16: 8, 32: 4, 64: 4, 128: 13}
  gamma=0.90*  spread median 1.59 gmean 1.64  best-L {4: 3, 8: 4, 16: 9, 32: 3, 64: 4, 128: 15}
  gamma=0.95   spread median 1.55 gmean 1.63  best-L {4: 5, 8: 6, 16: 4, 32: 7, 64: 1, 128: 15}
  gamma=0.99   spread median 1.69 gmean 1.67  best-L {4: 3, 8: 9, 16: 5, 32: 3, 64: 4, 128: 14}
