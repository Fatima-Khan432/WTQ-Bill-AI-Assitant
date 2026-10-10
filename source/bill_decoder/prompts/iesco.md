# Provider: IESCO (Islamabad Electric Supply Company)

## Where to read each field

- **Header:** `SAN LOAD`, `TARIFF` (the code, for example `A-1A(01)`; "TARIFF CATEGORY: Domestic" is not the tariff), `BILL MONTH`, `READING DATE`, `ISSUE DATE`, `DUE DATE`. Ignore CURR MDI.
- **Meter Info:** every row of the table (PREVIOUS READING, PRESENT READING, UNITS) goes into `meter_rows`. Do not copy the meter number or MF.
- **Charges:** `energy` from "Total Electricity Charges"; `subsidy` from "Subsidies" (copy the number as printed; code makes it negative); `fpa` from "Total FPA" in the right-hand column of the breakdown. Skip lines printed as 0.
- **Totals:** `total_charges` = "Net Electricity Charges". The single "Taxes" figure goes in `total_taxes` and `tax_lines` stays empty. The percentages printed beside both labels (for example 84.76 %, 15.24 %) are NOT amounts: never copy them.
- **`current_bill`** = "Current Bill". **`arrears`** = "Arrears". **`payable_within_due_date`** = "Payable within Due Date" (the large amount in the right-hand box).
- **Late amounts:** the "Till dd-MMM-yy" and "After dd-MMM-yy" values under "Payable after due date" go in `payable_after_due_date_amounts`. (The L.P Surcharge row above them is surcharge, not an amount payable.)
- **`breakdown_values`:** the numbers in the left breakdown value column, top to bottom (Total Electricity Charges, Subsidies, Net Electricity Charges, Taxes, Current Bill, Grand Total). Do not include the right-hand column (Arrears, Installment, Adjustments, W.E Credit, Lock Open Credit, Total FPA).

- **`bill_history`:** every row of the "Bill History" table (MONTH, STATUS, UNITS, BILL (RS.), PAYMENT (RS.)), both halves (left half first, then right half), in printed order. `month` as printed (`Sep25`); `status` as printed (`EX`) or `null`; keep minus signs; blank cells are `null`. Ignore "Deferred Amount" and "Outstanding Install." lines.

## Traps to ignore

- L.P Surcharge; Installment, Adjustments, W.E Credit, Lock Open Credit.
- Grand Total as a field (its value belongs only in `breakdown_values`).
- The Urdu notices, the bank-stamp slip at the bottom, the bill history table.

## Example (bill IESCO_0004)

```json
{
  "tariff": "A-1A(01)",
  "sanctioned_load": "3",
  "bill_month": "SEP 26",
  "reading_date": "25 SEP 26",
  "issue_date": "26 SEP 26",
  "due_date": "08 OCT 26",
  "meter_rows": [{"label": null, "previous": "9301", "present": "9459", "units": "158"}],
  "billed_units_headline": null,
  "charge_lines": [
    {"label": "Total Electricity Charges", "amount": "6102", "type": "energy"},
    {"label": "Subsidies", "amount": "3332", "type": "subsidy"},
    {"label": "Total FPA", "amount": "267", "type": "fpa"}
  ],
  "total_charges": "2770",
  "tax_lines": [],
  "total_taxes": "498",
  "current_bill": "3267",
  "arrears": "0",
  "payable_within_due_date": "3535",
  "payable_after_due_date_amounts": ["3,674", "3,812"],
  "payable_after_due_date_text": null,
  "breakdown_values": ["6102", "3332", "2770", "498", "3267", "3535"],
  "bill_history": [
    {"month": "Sep25", "units": "20", "bill": "215", "payment": "215", "status": null},
    {"month": "Jan26", "units": "105", "bill": "1415", "payment": "1415", "status": "EX"}
  ]
}
```
