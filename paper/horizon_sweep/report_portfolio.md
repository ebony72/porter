  shipped 3-route protocol: gmean 365.6, 320s  (measured head to head, same process)

  portfolio                              routes    gmean  vs ship     time  x ship  worse
  {16,128} x {.5,.25}                         4    346.5    -5.2%    1376s   4.29x      4
  {4,16,128} x {.5,.25}                       6    342.3    -6.4%    1493s   4.66x      2
  {16,128} x {.5,.25,0}                       6    337.3    -7.7%    1959s   6.12x      1
  {4,16,128} x {.5,.25,0}  (full 3x3)         9    336.0    -8.1%    2131s   6.65x      0
  {4,16,128} at .5 only (horizon axis)        3    363.3    -0.6%     707s   2.21x      5
  shipped: gmean 365.6, 320s

  portfolio                             gmean  vs ship  budgeted  x ship  lost
  {16,128} x {.5,.25}                   351.8    -3.8%      868s   2.71x    13
  {4,16,128} x {.5,.25}                 345.4    -5.5%      986s   3.08x    13
  {16,128} x {.5,.25,0}                 344.9    -5.7%     1305s   4.07x    23
  {4,16,128} x {.5,.25,0} (full)        341.4    -6.6%     1477s   4.61x    23
  {4,16,128} at .5 only                 366.7     0.3%      420s   1.31x     4

  'lost' = completed cells a 4x budget would have abandoned
