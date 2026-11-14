# Switching the accounting to the cash book (runbook)

Nothing here happens by itself. The schema (Alembic `0029_cash_ledger`) is additive and runs with the normal deploy.
The take-over of the old sheets is a separate, deliberate step on the server (`python -m app.manage ...`).

## States
| State | Truth | What it means |
|---|---|---|
| (no row) | old sheets | nothing changed; the cash book answers with "not switched on" |
| `shadow` | old sheets | the old rows are taken over and checked; the cash book is for preview only; old sheets stay writable |
| `live` | cash book | old sheets are read-only; bookings and cancellations are written to the cash book |

## Order
1. **Backup first** (a Neon branch). Never run this on the real database without one.
2. `python -m app.manage ledger-migrate --report-file report.json` — only looks. Prints the parity report: per currency and month
   *old*, *new historical* and *new cash* figures. `"ok": true` means every figure agrees (or the difference is explained).
   An unexplained difference makes the command stop with exit code 2 and nothing is written.
3. Read `report.json`: `not_counted` (old rows that did not count and stay in the archive), `parity.currencies.*.months`,
   `adjustments_not_in_cash` (salaries nobody paid out, shown as historical adjustments, never real money).
4. `python -m app.manage ledger-migrate --apply --by <name>` — writes the taken-over bookings and the switch row (state `shadow`)
   in ONE transaction, then proves the stored bookings reproduce the old books and that the old tables (receipt files included)
   are byte-for-byte unchanged. Any difference rolls everything back.
5. Look at the web page *Cash book* (state `shadow`): overview and book show the taken-over figures.
6. `python -m app.manage ledger-live --by <name>` — proves the parity once more with today's data, then switches to `live`.
   (`ledger-migrate --apply --go-live` does steps 4 and 6 together.)

## After going live
* Every new booking, cancellation, receipt or automatic settlement counts as a "live write".
* `python -m app.manage ledger-rollback` goes back to the old sheets **only while nothing new exists** (no live write, no manual
  booking, no cancellation). Afterwards there is no way back: corrections are made with cancellations and new bookings.
* `ledger-discard` (only in `shadow`) removes the taken-over rows again.
* `ledger-status` shows the state and what blocks a way back.

## Rules the system enforces
* Cash balance = opening + incomes − expenses, per currency. USD and SYP are never added.
* A salary without a payment date moves no money. Old salaries without a payment date in a finished month are kept as
  *historical adjustments* (not in the cash balance). When the salary is paid: an adjustment in an open month is cancelled,
  an adjustment in a closed month stays and a counter-booking in the month of the payment cancels it historically.
* Nothing financial is deleted: it is cancelled with a reason (at least 5 characters) and stays visible.
* Resets (`/accounting/reset`, `reset-part`) are blocked once live; only possible on SQLite with `ALLOW_FINANCE_RESET=1`.
* Business dates and month ends follow `Asia/Damascus` (`APP_TIMEZONE` can change it; time stamps are stored in UTC).
