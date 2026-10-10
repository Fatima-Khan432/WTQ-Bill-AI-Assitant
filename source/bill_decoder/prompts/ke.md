# Provider: K-Electric (KE)

## Where to read each field

- **Header:** `Bill Month:` and `Issue Date:` top left. `Sanc Load` and `Tariff` in the Customer Information box (not `Conn Load`).
- **Due date:** the large "Due Date" box, for example `21st Apr 2026`.
- **Reading date:** in the Bill Calculation header, `Reading Date: 03-Apr-26`.
- **Meter:** the "Electricity You Have Used" table: every row goes into `meter_rows` (Previous Reading, Current Reading, Units (KWh)). Ignore the MDI column. The "N units =" figure in the Current Month box goes to `billed_units_headline`.
- **Charges:** the Bill Calculation lines from `Fixed Charges` down to the `Electricity Charges` subtotal, one entry each, taking the Amount column (rightmost). A repeated line (two Uniform Quarterly Adjustment rows) gives two entries. Negative amounts keep their minus sign. `total_charges` = the "Electricity Charges" subtotal.
- **Taxes:** the lines between the "Electricity Charges" subtotal and "Taxes and Duties" (Electricity Duty, Sales Tax, MUCT (KMC), ...). `total_taxes` = "Taxes and Duties".
- **`current_bill`** = "Electricity Charges for current month" (the black bar), NOT the "Current Bill Amount" row further down and not "Outstanding Balance".
- **`arrears`** = "Previous Dues".
- **`payable_within_due_date`** = the "Amount Due" box (`Rs. 3,430`).
- **Late amounts** (`payable_after_due_date_amounts`): the "Amount Payable from ... with 5% LPS" and "Amount Payable after ... with 10% LPS" rows of Bill Calculation. If those rows are missing, use the amounts after "Till ..." and "After ..." in the "Amount Payable after Due Date" box. Use `[]` if none are printed.

- **`bill_history`:** merge two sources by month into one entry per month.
  1. "13 Month Usage History" bar chart: each bar's printed number is `units`; the month is the label under the bar, and the year comes from the "2025 / 2026" labels above the chart (write `Apr 2025`, `May 2025`, ..., the last bar is the current month). Include all 13 bars in order.
  2. "Billing & Payment History" rows (`MM / YY`, Billed Amount, Pay-Date, Payment): `month` as printed (`03/26`), `bill` = Billed Amount, `payment` = Payment. If a row's month matches a chart bar, put the `bill` and `payment` on that bar's entry; otherwise add a separate entry with `units` null.

## Traps to ignore

- The Due Date box lines such as `Till 21-Apr-2026 Rs.286.06` (that is surcharge saved, not an amount payable).
- Late Payment Surcharge rows.
- Opening Balance, Payments/Adjustment, Remaining Dues, Net Metering Benefit, Outstanding Balance.
- The footer percentages (83.39 %, 16.61 %) and the footer Energy Charges / Taxes and Duties totals.
- The Billing & Payment History table and the 13 Month Usage History chart.

## Example (bill KESC_0008, a K-Electric bill)

```json
{
  "tariff": "A1-R",
  "sanctioned_load": "3",
  "bill_month": "Apr-26",
  "reading_date": "03-Apr-26",
  "issue_date": "07-Apr-2026",
  "due_date": "21st Apr 2026",
  "meter_rows": [{"label": "Energy", "previous": "8819", "present": "8970", "units": "151"}],
  "billed_units_headline": "151 units =",
  "charge_lines": [
    {"label": "Fixed Charges", "amount": "900.00", "type": "fixed"},
    {"label": "Variable Upto 100 Units (Protected)", "amount": "1,054.00", "type": "energy"},
    {"label": "Variable Upto 200 Units (Protected)", "amount": "663.51", "type": "energy"},
    {"label": "Uniform Quarterly Adjustment", "amount": "52.91", "type": "quarterly_adjustment"},
    {"label": "FCA :Feb-26", "amount": "125.27", "type": "fpa"},
    {"label": "Additional Surcharge (PHL)", "amount": "64.93", "type": "surcharge"}
  ],
  "total_charges": "2,860.62",
  "tax_lines": [
    {"label": "Electricity Duty", "amount": "29.41", "type": "electricity_duty"},
    {"label": "Sales Tax u/s 3(1)*", "amount": "520.21", "type": "gst"},
    {"label": "MUCT (KMC)", "amount": "20.00", "type": "municipal_tax"}
  ],
  "total_taxes": "569.62",
  "current_bill": "3,430.24",
  "arrears": "Rs. -0.53",
  "payable_within_due_date": "Rs. 3,430",
  "payable_after_due_date_amounts": ["3,574", "3,716"],
  "payable_after_due_date_text": null,
  "breakdown_values": [],
  "bill_history": [
    {"month": "Apr 2025", "units": "141", "bill": null, "payment": null, "status": null},
    {"month": "Jan 2026", "units": "96", "bill": "2,780.55", "payment": "2780.00", "status": null},
    {"month": "Apr 2026", "units": "151", "bill": null, "payment": null, "status": null}
  ]
}
```
