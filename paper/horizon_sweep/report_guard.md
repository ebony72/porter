## stall guard (1,000 iterations) validated on all 48 instances, shipped protocol (selection=True)
  identical op stream, EPR, SWAPs, depth, tie count AND selected horizon: 48/48
  differing: 0

  total protocol wall time: guard off 509.8s -> guard on 323.1s  (1.58x)
  instances where the guard saved >1s:
    main/80/random                236.4s ->    71.3s  ( 165.0s saved, 3.3x)
    scaleup/360/qpeexact           32.6s ->    20.3s  (  12.3s saved, 1.6x)
    heavyhex/star/multiplier       14.5s ->     4.7s  (   9.8s saved, 3.1x)
    main/80/qaoa                   27.8s ->    25.6s  (   2.2s saved, 1.1x)
    heavyhex/ring/random           12.7s ->    11.5s  (   1.2s saved, 1.1x)

  instances not completing under either arm: 0

  candidate horizons abandoned during selection: off 13, on 13 (same set expected)
