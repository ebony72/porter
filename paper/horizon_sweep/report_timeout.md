## 7 cells that timed out at 300 s, re-run at 900 s (3x)

  instance                    L   outcome     run    last    idle  retired      of  verdict
  main/64/ae                256   timeout    900s    0.0s    900s     3356    4616  FROZEN: retirement stopped, router span on
  main/64/qnn_OLD_DEEP      256   timeout    900s    6.0s    894s     2515   13061  FROZEN: retirement stopped, router span on
  main/80/qft               128   timeout    900s    2.0s    898s     2639    5481  FROZEN: retirement stopped, router span on
  main/80/qnn_DEEP           64   timeout    900s    6.2s    894s     3354   20165  FROZEN: retirement stopped, router span on
  main/80/random              8  livelock    490s   18.2s    471s    34968   64306  FROZEN: retirement stopped, router span on
  main/80/random            128   timeout    900s   14.8s    885s     1380   64306  FROZEN: retirement stopped, router span on
  scaleup/360/qpeexact        8  livelock    223s    2.2s    221s    26797   29761  FROZEN: retirement stopped, router span on

    7  FROZEN: retirement stopped, router span on

  0 of 7 completed when given 3x the time

  In the frozen cases retirement stops after a median of 6s and the router then spins for the rest of the guard.
  EPR and SWAP counts at the last sample vs the start, showing work continued:
    scaleup/360/qpeexact    L=8    gates 360->18218, epr 0->1324, swaps 0->10732
    main/80/random          L=8    gates 35->32840, epr 0->5746, swaps 0->32418
    main/80/random          L=128  gates 35->1335, epr 0->239, swaps 0->1079
    main/80/qnn_DEEP        L=64   gates 80->2988, epr 0->273, swaps 0->1865
    main/64/qnn_OLD_DEEP    L=256  gates 64->2405, epr 0->235, swaps 0->1319
    main/80/qft             L=128  gates 1->2564, epr 0->192, swaps 0->1241
