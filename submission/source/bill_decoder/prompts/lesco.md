# Provider: LESCO (Lahore Electric Supply Company)

## Where to read each field

- **Header cells** (values sit below their labels): `SAN LOAD`, `TARIFF` (the code next to or below TARIFF, for example `A-2a(04)` or `A-1b(03)T`; the word COMMERCIAL / DOMESTIC beside it is the category, not the tariff), `BILL MONTH`, `READING DATE`, `ISSUE DATE`, `DUE DATE`. Ignore MDI.
- **Meter table:** every row under PREVIOUS READING / PRESENT READING / UNITS goes into `meter_rows` in printed order (a row with a blank units cell uses `null`). Do not copy the meter number.
- **Charges:** one `energy` entry from "Total Electricity Charges". Add a `subsidy` entry only when "Subsidies" has a printed, non-zero amount. Any line labelled FPA or FCA anywhere in the breakdown is an `fpa` entry.
- **Totals:** `total_charges` = "Net Electricity Charges". The single "Taxes" figure goes in `total_taxes` and `tax_lines` stays empty.
- **`current_bill`** = "Current Bill". **`arrears`** = "Arrears" (copy as printed, even `39411 / 2`; code drops the `/ 2`). **`payable_within_due_date`** = "Payable within due date" (the large amount under the Due Date; copy a `CR` suffix).
- **Late amounts:** the "Upto dd/mm/yy" and "After dd/mm/yy" values under "Payable after due date" go in `payable_after_due_date_amounts`. If text such as `NOT TO BE PAID` is printed instead, put that text in `payable_after_due_date_text` and leave the list empty.
- **`breakdown_values`:** the numbers in the breakdown value column, top to bottom (Total Electricity Charges, Subsidies if printed, Net, Taxes, Current Bill, Grand Total).

- **`bill_history`:** every row of the "Bill History" table (columns MONTH, STATUS, UNITS, BILL (RS.), PAYMENT (RS.)), both halves (left half first, then right half), in printed order. `month` as printed (`JUL 25`); keep a minus sign on units/bill; blank payment cells are `null`.

## Traps to ignore

- The L.P Surcharge row (its amounts are surcharge, not payable amounts).
- Installment and Adjustments; the Grand Total label itself (its value belongs only in `breakdown_values`); the Bill History table.
- Phone photos: values can sit one row off their label. Copy each value as printed, list the column in vertical order in `breakdown_values`, and give your best mapping in the named fields. Code checks the mapping against the bill's arithmetic.

## Example (bill LESCO_0006)

```json
{
  "tariff": "A-2a(04)",
  "sanctioned_load": "1",
  "bill_month": "AUG 2026",
  "reading_date": "26 AUG 26",
  "issue_date": "29 AUG 26",
  "due_date": "09 SEP 26",
  "meter_rows": [{"label": null, "previous": "22238", "present": "22303", "units": "65"}],
  "billed_units_headline": null,
  "charge_lines": [{"label": "Total Electricity Charges", "amount": "3,777.49", "type": "energy"}],
  "total_charges": "3,777.49",
  "tax_lines": [],
  "total_taxes": "1,723.51",
  "current_bill": "5501",
  "arrears": "39411 / 2",
  "payable_within_due_date": "44912",
  "payable_after_due_date_amounts": ["45088", "45263"],
  "payable_after_due_date_text": null,
  "breakdown_values": ["3,777.49", "3,777.49", "1,723.51", "5501", "44912"],
  "bill_history": [
    {"month": "AUG 25", "units": "440", "bill": "52,906", "payment": "52,906", "status": null},
    {"month": "SEP 25", "units": "407", "bill": "23,954", "payment": "25,632", "status": null}
  ]
}
```
