# Provider: LESCO, "web bill" layout (itemised LESCO CHARGES and GOVT. CHARGES blocks)

This layout is an itemised web-style bill. It has a "LESCO CHARGES" block, a "GOVT. CHARGES" block and a "TOTAL CHARGES" section. `breakdown_values` stays `[]` for this layout.

## Where to read each field

- **Header:** `S. LOAD` (sanctioned load), `TARIFF` (the code, for example `A-1a(01)`), `BILL MONTH`, `READING DATE`, `ISSUE DATE`, `DUE DATE`. Ignore MDI.
- **Meter table:** every row of the meter table into `meter_rows` (previous, present, units). Do not copy meter numbers.
- **Charges:** one entry for every non-blank, non-zero line inside the "LESCO CHARGES" block, in printed order, with the amount printed beside it:
  - Cost of Electricity -> `energy`
  - Meter Rent / Service Rent -> `meter_rent`
  - Fuel Price Adjustment -> `fpa`
  - F.C Surcharge -> `surcharge`
  - Quarterly Tariff Adjustment -> `quarterly_adjustment`
  - Fixed Charges -> `fixed`
  - any other line -> `other`
  "UNITS CONSUMED" is a quantity, NOT a charge: never add it to `charge_lines`.
- **Total FPA:** if "TOTAL FPA" is printed in the "TOTAL CHARGES" section with a non-zero amount, ALSO add one extra `fpa` entry labelled "TOTAL FPA" with that amount (project decision), after the LESCO CHARGES lines.
- **`total_charges`** = the "TOTAL" of the LESCO CHARGES block.
- **Taxes:** one entry for every non-blank, non-zero line inside "GOVT. CHARGES", in printed order:
  - Electricity Duty -> `electricity_duty`
  - GST -> `gst`
  - Income Tax -> `income_tax`
  - Extra Tax / Further Tax / RS Tax -> `other_tax`
  - GST ON FPA -> `gst`; ED ON FPA -> `electricity_duty`; any other "... ON FPA" line -> `other_tax`
  **`total_taxes`** = the "TOTAL" of the GOVT. CHARGES block.
- **`current_bill`** = "CURRENT BILL". **`arrears`** = "ARREAR / AGE" (blank -> `null`; a printed 0 stays `"0"`). **`payable_within_due_date`** = "PAYABLE WITHIN DUE DATE".
- **Late amounts:** the "Upto dd/mm/yy" and "After dd/mm/yy" values go in `payable_after_due_date_amounts` (both tiers).
- **`bill_history`:** every row of the Bill History table, both halves, in printed order (MONTH, STATUS, UNITS, BILL, PAYMENT).

## Traps to ignore

- L.P.SURCHARGE (late-payment surcharge amounts) and the "ED@ 1.5%" note.
- GRAND TOTAL as a field, installment lines, the bill history for every field except `bill_history`.
- Handwriting, stamps and pen marks on photographed bills.
