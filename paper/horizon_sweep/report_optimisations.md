## A. what each optimisation costs, shipped protocol, 48 instances, one process
   (routes are 3 in every row: none of these changes the route count)

   configuration          routes  gmean EPR  gmean 38      time  vs shipped
   shipped                     3      163.7     365.6    293.5s       1.00x
   no work budget              3      163.7     365.6    302.2s       1.03x
   no frontier fix             3      163.7     365.6    309.5s       1.05x
   no walk bound               3      163.7     365.6    299.1s       1.02x
   no stall guard              3      163.7     365.6    451.7s       1.54x
   none of the four            3      163.7     365.6    501.1s       1.71x

   every configuration emits the identical op stream on 48/48 instances,
   so the EPR columns are constant by construction and only the time moves.

## B. what more routes would buy, same 48 instances, each option budgeted
   portfolio                routes  gmean EPR  gmean 38      time  vs shipped  worse
   shipped density branch        3      163.7     365.6    321.6s       1.00x      0
   {4,16,128} at w=0.5           3      164.1     366.7    421.4s       1.31x      5
   {16,128} x {.5,.25}           4      158.8     351.8    869.5s       2.70x      5
   {4,16,128} x {.5,.25}         6      156.5     345.4    988.3s       3.07x      2
   {16,128} x {.5,.25,0}         6      156.3     344.9   1307.2s       4.06x      2
   full 3x3                      9      155.1     341.4   1480.6s       4.60x      0
