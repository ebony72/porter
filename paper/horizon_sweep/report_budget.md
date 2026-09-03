  rule                                   gmean EPR   total time   deterministic?
  wall clock, 4x first route (shipped)       160.2      271.8s   NO
  peeled layers,  4x first route              163.6      246.3s   yes   (+2.1% EPR, 0.91x time)
  peeled layers,  6x first route              160.2      267.0s   yes   (+0.0% EPR, 0.98x time)
  peeled layers,  8x first route              160.2      290.2s   yes   (+0.0% EPR, 1.07x time)
  peeled layers, 10x first route              160.2      319.9s   yes   (+0.0% EPR, 1.18x time)
  peeled layers, 12x first route              160.2      399.3s   yes   (+0.0% EPR, 1.47x time)
  peeled layers, 16x first route              160.2      399.3s   yes   (+0.0% EPR, 1.47x time)
  no budget at all (route every candidate)    160.2      597.6s   yes   (+0.0% EPR, 2.20x time)

  basis: 47 instances that complete at the configured horizon
  largest work ratios against the configured horizon (shipped counter):
      16.79x  heavyhex/star/qpeexact     L=128  epr=240
      14.79x  heavyhex/star/ae           L=128  epr=190
       9.29x  heavyhex/ring/random       L=128  epr=556
       8.34x  heavyhex/ring/multiplier   L=128  epr=573
       7.95x  heavyhex/star/random       L=128  epr=578
       6.47x  main/80/multiplier         L=128  epr=2486
       6.24x  scaleup/360/qpeexact       L=128  epr=1224
       6.05x  main/64/multiplier         L=128  epr=1076
       4.70x  main/80/ae                 L=128  epr=299
       4.56x  scaleup/200/qft            L=128  epr=579

  a factor must exceed 16.79 to admit every candidate that completes
## work budget (6x peeled layers) vs the wall-clock share, all 48 instances, shipped protocol
  identical op stream, EPR, SWAPs, depth, ties AND selected horizon: 45/48
   DIFFERS main/64/multiplier {'status': 'completed', 'epr': 1076, 'sha': 'ab28fc4e85414922', 'swaps': 8649, 'depth': 32976, 'ties': 3520, 'horizon': 128, 'horizon_eprs': {'16': 1358, '8': 1619, '128': 1076}, 'failed': [], 'seconds': 5.06} {'status': 'completed', 'epr': 1358, 'sha': '377e7688fb508834', 'swaps': 9878, 'depth': 34703, 'ties': 4375, 'horizon': 16, 'horizon_eprs': {'16': 1358, '8': 1619}, 'failed': [128], 'seconds': 4.81}
   DIFFERS main/80/multiplier {'status': 'completed', 'epr': 2486, 'sha': 'e19b22099dcb8d2e', 'swaps': 15462, 'depth': 55507, 'ties': 6757, 'horizon': 128, 'horizon_eprs': {'16': 3501, '8': 4098, '128': 2486}, 'failed': [], 'seconds': 9.95} {'status': 'completed', 'epr': 3501, 'sha': '0045866d80a78a2f', 'swaps': 18863, 'depth': 60964, 'ties': 9215, 'horizon': 16, 'horizon_eprs': {'16': 3501, '8': 4098}, 'failed': [128], 'seconds': 9.75}
   DIFFERS scaleup/360/qpeexact {'status': 'completed', 'epr': 1224, 'sha': '4c3b0e646eff9cc0', 'swaps': 12561, 'depth': 26754, 'ties': 4283, 'horizon': 128, 'horizon_eprs': {'16': 2342, '128': 1224}, 'failed': [8], 'seconds': 18.85} {'status': 'completed', 'epr': 2342, 'sha': 'bed31fba2d226a87', 'swaps': 18834, 'depth': 31323, 'ties': 7220, 'horizon': 16, 'horizon_eprs': {'16': 2342}, 'failed': [128, 8], 'seconds': 18.38}
  total protocol wall time: clock 302.2s -> work 285.2s (0.94x)
  instances failing under either rule: 0
