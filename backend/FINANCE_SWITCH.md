# Switching the real database to the new accounting

The old accounting (fee lines, payments, payroll lines, day/week/month sheets, cash book, exchange rates of the old kind,
closed periods, cash counts) is gone from the code. Its tables are removed by migration `0039_drop_old_finance`, but only when
that is safe. Decision: **clean start** (option A). The new accounting begins empty; the old data are kept as a checked backup.

## What the deploy does by itself

* `0038_money` adds the new tables (`currency_rates`, `income_categories` with the four built-in categories, `invoices`,
  `invoice_items`, `income_entries`, `expense_entries`, `month_closings`). Nothing old is touched.
* `0039_drop_old_finance` removes the rights `books.view` / `books.write` (from 0037) and then:
  * old tables that are **empty** are dropped;
  * old tables that **hold rows** are **kept unchanged** unless the variable `OLD_FINANCE_BACKUP_DIR` names a backup folder that
    matches the database exactly (every file there, unchanged, the same row counts). The deploy log says which tables were kept.
* There is no downgrade of 0039: the old tables can only come back from the backup.

So a normal deploy can never lose old financial data.

## Steps on the real database (only with the owner's explicit OK)

1. Neon: make a branch / snapshot of the database (Neon console). Note its name.
2. With the real `DATABASE_URL`, from `backend/`:
   `python -m app.manage finance-backup --out backups/finance-YYYY-MM-DD`
   It writes one CSV per old table (receipt files next to it), a `manifest.json` with row counts and checksums, and checks the
   backup right away. Result `"ok": true` is required. Keep the folder outside Git (it holds personal and financial data).
3. Check it again at any time: `python -m app.manage finance-backup --out backups/finance-YYYY-MM-DD --verify-only`.
4. Deploy (Render "Deploy latest commit"). The old tables with rows stay (see above); the new accounting works at once.
5. When the owner agrees to remove the old tables:
   `python -m app.manage drop-old-finance --backup backups/finance-YYYY-MM-DD`
   It checks the backup against the database first and refuses on any difference.
6. The management sets the first exchange rate on the income page; then income, expenses and invoices can be entered.

## Rules of the new accounting (short)

* Three pages: income (with invoices and their payments), expenses (with salaries), month overview (with closing and the rate).
* Every entry keeps amount, the currency really paid, the rate used and the value in the other currency. Later rates change nothing.
* Totals are per currency of the money really paid; the converted value is shown for comparison only and never added on top.
* An invoice is a claim; only a payment (an income tied to it) is income. Paid/open/status are always calculated.
* Nothing is deleted: open month = cancel with a reason; closed month = reversal entry in the open month.
* Rights (since 2026-11-21): management, admin and the accountant may do everything in the accounting; every change is logged.
  The staff list itself is managed by the management.
