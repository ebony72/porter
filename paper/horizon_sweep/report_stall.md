  instance                    L    epr    iters  worst gap gap/iters
  main/25/ae                 16     65     1329          5     0.4%
  main/25/random             16    393     3619          5     0.1%
  main/64/ae                 16    177     4936          7     0.1%
  main/64/qft                16    262     4749          8     0.2%
  main/64/multiplier         64    989    34839          7     0.0%
  main/80/qpeexact          128    291     5213          7     0.1%
  main/80/multiplier         32   2586    54395          7     0.0%
  scaleup/100/qft           128    198     7578          9     0.1%
  scaleup/360/qft           128   1170    28800         13     0.0%
  heavyhex/star/qft         128    117     5340         12     0.2%
  heavyhex/ring/multiplier   64    456    38625         15     0.0%
## healthy routes: does the guard ever fire, and is the stream unchanged?
  instance                      L    epr  guard fired?  stream identical?
  main/25/ae                   16     65  no            YES
  main/64/ae                   16    177  no            YES
  main/64/qft                  16    262  no            YES
  main/64/multiplier           64    989  no            YES
  main/80/qpeexact            128    291  no            YES
  main/80/multiplier           32   2586  no            YES
  scaleup/100/qft             128    198  no            YES
  scaleup/360/qft             128   1170  no            YES
  heavyhex/star/qft           128    117  no            YES
  heavyhex/ring/multiplier     64    456  no            YES

## frozen routes: how fast does the guard abandon them?  (grid spent 300 s each)
  instance                      L  abandoned after    iters
  main/80/qnn_DEEP             64            37.2s     4803
  main/80/random              128            73.0s     2334
  main/80/random                8            20.6s    41949
  scaleup/360/qpeexact          8             4.0s    26422
  main/64/qft                 128            12.9s     2260
  main/80/qft                 128            17.9s     3928
## stall-gap separation over 96 routes (all 48 instances at L=16 and L=128)
  completed routes:      84   longest run with no gate retired: max 17, median 10
  non-completed routes:  12   same quantity: min 5084, max 165762
  separation: 299x   -> a threshold of 1000 is 59x above healthy and 5.1x below stuck

  worst healthy:
    heavyhex/star/ae           L=128  gap= 17  iters=4917
    heavyhex/star/qft          L=16   gap= 16  iters=5565
    heavyhex/star/random       L=16   gap= 15  iters=6266
    scaleup/360/qft            L=16   gap= 14  iters=28156
    heavyhex/ring/random       L=16   gap= 14  iters=7001

  every non-completed route:
    main/80/qaoa               L=128  HorizonTimeout   gap=   5084 of 7074 iters
    main/80/random             L=128  HorizonTimeout   gap=   6072 of 7405 iters
    main/64/random             L=128  HorizonTimeout   gap=   6095 of 7108 iters
    main/64/qnn_OLD_DEEP       L=128  HorizonTimeout   gap=   7149 of 10303 iters
    heavyhex/star/qaoa         L=128  HorizonTimeout   gap=   7339 of 9811 iters
    main/80/qnn_DEEP           L=128  HorizonTimeout   gap=   7480 of 11789 iters
    heavyhex/ring/qaoa         L=128  HorizonTimeout   gap=   8252 of 12696 iters
    main/64/qaoa               L=128  HorizonTimeout   gap=  14901 of 16476 iters
    main/64/qpeexact           L=128  HorizonTimeout   gap=  16653 of 18859 iters
    main/80/qft                L=128  HorizonTimeout   gap=  22008 of 24935 iters
    main/64/qft                L=128  HorizonTimeout   gap=  24604 of 25863 iters
    heavyhex/star/multiplier   L=16   RuntimeError     gap= 165762 of 200000 iters
