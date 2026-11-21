# The accounting (three pages)

Navigation: **الإيرادات** (income) · **المصروفات** (expenses) · **الملخص الشهري** (month overview). Nothing else.
Backend `backend/app/money.py` (prefix `/api/admin/money`), web `admin/money.js` (+ `admin/ui.js`), tables in `backend/app/models.py`
(`CurrencyRate`, `IncomeCategory`, `Invoice`, `InvoiceItem`, `IncomeEntry`, `ExpenseEntry`, `MonthClosing`), migration `0038_money`.

## Money and currencies

* Amounts are `Decimal`. Every entry stores: the amount really paid, the currency really paid (USD/SYP), the rate used
  (SYP for one USD) and the value in the other currency. Rounding, one rule, half up: dollars → whole pounds, pounds → cents.
* The rate of the booking day is proposed. The management and the accountant may type another one. A new rate (valid from a day) is added on the
  rate strip at the top of every page; rates are never overwritten, old entries never change.
* **Rule for totals:** each column adds the money that was really paid in that currency (income in USD − expenses in USD, and the
  same for SYP). The value of an entry in the other currency is shown beside it but never counted again, so nothing is counted twice.
  The overview also shows, for comparison only, the surplus with every entry converted at its stored rate.

## Income page

* Form: date, reason, category, child (optional), payer (optional), amount, currency, rate (proposed), note.
* Categories: kindergarten fees, registration fees, additional fees, other income (built in); the management may add or switch off others.
* Table: date | description | category | USD | SYP | really paid; search, month or date span, category filter, history, change, cancel.
* **Invoices** live here: a claim with items, total in both currencies and the rate of the invoice. "Record payment" creates an income
  entry tied to the invoice (part payments and the other currency allowed; never more than what is open). Status open / partly paid /
  paid is calculated from the payments, never typed. An invoice with payments cannot be cancelled.

## Expenses page

* Form: date paid, reason, category, recipient (optional), staff member + salary month (only for salaries), amount, currency, rate, note.
* Categories (fixed): salaries, rent, food, teaching material, toys and equipment, electricity and water, maintenance, transport, other.
* Only money really paid is entered (there are no planned expenses).
* **Salaries book themselves:** on the 1st of every month (first visit of the accounting that day or later) the saved salary of every active
  person is booked as an expense for the month before (category salaries, in the salary's currency, at the rate of the 1st). People already
  paid by hand, cancelled salaries, people without a salary or hired later are skipped. The automatic start is the month of the first run
  (no older month is booked). An automatic salary can be changed or cancelled like any expense.
* **Salaries:** the block "salaries of the month" lists the staff (read from the management's staff list) as paid / not paid and has
  "pay salary" (prefilled with the usual salary). A person is paid once per month while that payment stands (not cancelled, not reversed).
* The management can export the staff list here (XLSX/CSV); the list itself is managed in the management portal.

## Month overview

Month picker with previous/next. Income, expenses, surplus per currency with the change against the month before; by category; numbers
of entries; salaries and other expenses; open and partly paid invoices. The management closes a finished month (and may reopen it with
a reason, logged). In a closed month nothing is added, changed or cancelled; a correction is a reversal entry in the open month.

## Rights (checked on the server)

| | Management / admin | Accountant |
|---|---|---|
| See and enter income, expenses, invoices, payments, salaries | yes | yes |
| Change and cancel entries, change and cancel invoices, cancel payments | yes | yes |
| Exports (income, expenses, summary, invoice, staff list; PDF only) | yes | yes |
| Rate, own rate in a form, month closing, income categories, cash balance | yes | yes |
| Staff list | manages | reads |

## Log

Every change is written to the activity log with user, time, before, after and reason (`/api/admin/money/history/{id}` for one entry;
`/api/admin/activity` for the log; an accountant only sees their own lines).

## Tests

`backend/tests/test_money.py` (both currencies, frozen rate, rounding, invoices open/partial/paid, double entry, salaries once per month,
month overview per currency, closing and reversal, cancelling, exports, rights, log), `test_people.py` (staff and export).
