# Provider: LESCO, "digital" layout (looks like IESCO)

This LESCO bill uses the IESCO-style "Bill Charges Breakdown": Total Electricity Charges, Subsidies, Net Electricity Charges, Taxes, Current Bill, Grand Total, plus a right-hand column with Arrears, Installment, Adjustments, W.E Credit, Lock Open Credit and Total FPA.

## Where to read each field

- **Header:** `SAN LOAD` / `S.LOAD`, `TARIFF` (the code, for example `A-1b(03)T`; the category word beside it is not the tariff), `BILL MONTH`, `READING DATE`, `ISSUE DATE`, `DUE DATE`. Ignore MDI.
- **Meter table:** every row of PREVIOUS READING / PRESENT READING / UNITS into `meter_rows`. Do not copy meter numbers.
- **Charges:** `energy` from "Total Electricity Charges"; `subsidy` from "Subsidies" (copy the number as printed; code makes it negative; skip if 0 or blank); `fpa` from "Total FPA" (skip if 0 or blank).
- **Totals:** `total_charges` = "Net Electricity Charges". The single "Taxes" figure goes in `total_taxes`; `tax_lines` stays empty. Percentages printed beside labels (for example 84.76 %) are NOT amounts: never copy them.
- **`current_bill`** = "Current Bill". **`arrears`** = "Arrears". **`payable_within_due_date`** = "Payable within due date" (copy a `CR` suffix).
- **Late amounts:** the "Upto/Till dd/mm/yy" and "After dd/mm/yy" values under "Payable after due date" go in `payable_after_due_date_amounts`. Printed text such as `NOT TO BE PAID` goes in `payable_after_due_date_text` with an empty list.
- **`breakdown_values`:** the numbers in the left breakdown value column, top to bottom (Total Electricity Charges, Subsidies if printed, Net, Taxes, Current Bill, Grand Total). Never include the right-hand column. On phone photos values may sit one row off their labels; list them in vertical order anyway.
- **`bill_history`:** every row of the Bill History table, both halves, in printed order.

## Traps to ignore

- L.P Surcharge; Installment, Adjustments, W.E Credit, Lock Open Credit; Grand Total as a field; Urdu notices; the bill history for every field except `bill_history`.
- Handwriting, stamps and pen marks on photographed bills.
