# Accounting as a guided workflow

The accounting area of the admin dashboard (tab "المحاسبة") is organised as the steps of a month, in the order the work is done.
A bar at the top shows the steps; every step has a status and a mark when something needs a look. The month in work is chosen at the top.

| # | Step | What it holds | Done when |
|---|---|---|---|
| 0 | لوحة سير العمل (workflow board) | every step with status, progress and its open points, and the next step | – |
| 1 | الإعدادات الأساسية (basics) | exchange rate, opening cash per currency, the fixed items (categories), reset (admin) | cash opening (SYP) and a rate are saved |
| 2 | الموظفون والرواتب (staff) | employees, and a button that creates this month's salary line for every employee | every employee has a line this month |
| 3 | اشتراكات الأطفال (fees) | the fees of the month and what is still open; second tab: children and their parents | every active child has a fee line, none flagged for review |
| 4 | الإيرادات (income) | the daily sheet, income rows only; payments of parents come from step 3 | no open fee is left |
| 5 | المصروفات والإيصالات (expenses) | the daily sheet, expense rows only, with receipts per row | every expense row has a receipt number or file |
| 6 | دفع الرواتب (payroll) | the salary lines and their payment | every salary line is paid |
| 7 | المطابقة وجرد الصندوق (reconcile) | what is still open, and the cash count against the books | a count was made and has no difference |
| 8 | الملخص المالي (summary) | balance, income, expenses, development of the months | steps 3 to 7 are done |
| 9 | التقارير (reports) | day, week (with the weekly check), month and year, read only, print/PDF | the month is closed |
| 10 | إغلاق الشهر (close) | check list, then lock | the month is locked |
| 11 | التصدير والأرشيف (archive) | one Excel file per month, quick exports, the export log | the closed month was exported |

Status words: **معلّقة** (pending), **قيد التنفيذ** (in progress), **مكتملة** (complete). Issues (open fees, missing receipts, a cash
difference, lines flagged for review, unpaid salaries) are listed under the step and marked with a red dot.

## Confirming a step on purpose

The status of a step follows the data. Some steps can never complete by themselves: a month without expenses, a fee that will only be paid next month, a cash difference that is known. For these steps (`basics`, `staff`, `fees`, `income`, `expenses`, `payroll`, `reconcile`) a person can press **تأكيد اكتمال هذه الخطوة** (with an optional note). The step then counts as done for that month, with the name, the time and the note shown on the board; the open points stay listed and nothing is hidden. The confirmation can be taken back, is written to the log (`step.confirm` / `step.unconfirm`) and cannot be changed in a closed month. Confirming never lifts the real blockers of the closing (lines flagged for review). Migration `0024_step_confirmations`.

## Children and employees are the work of the management

Adding, changing and removing children (with their parents) and employees (with their usual salary and sign-in account) is done in the **management portal** (`/management/`, tabs الأطفال and الموظفون), not in the accounting.
The accountant can read both lists, picks from them (a child for a fee, an employee for a salary line) and gets a clear message when a name is not saved yet. The server enforces this: the write endpoints for children and employees, the class of a child and the creation of a child or an employee by typing a name are refused for the accountant (403 / 404).
The administrator keeps all rights.

## Rules that stay as they were

- Only the month closing locks. A week is never locked; the weekly check is for control only.
- A closed month cannot be changed (payments, salaries, sheet rows, receipts). Only the administrator can open it again, with a reason.
- Closing is refused while fee or salary lines are flagged "needs review". Missing receipts, unpaid salaries and a missing cash count are
  warnings: the screen lists them and asks for a confirmation.
- The accountant and the administrator see the same steps. The rights differ as before (reopening a month, resetting the data and the
  system log tab are for the administrator only).

## Several people on the same work

Every accountant works with their own account, so every step is written down with the person and the time.

- **Who changed a row last**: every sheet row, salary line and fee line shows `Last change: name, time`. The button `History` shows every step done to that row by everybody (for a fee line also its payments).
- **Conflicts**: when two people have the same row open and both save, the second save is refused (409) with the name of the first person, the time and the value that is saved now. What the second person typed stays in the row; after refreshing, a new save replaces the other's change on purpose. A row that two people create at the same time is noticed the same way.
- **The log** (`/api/admin/fees/audit`, the tab `سجل النظام` and the archive step) can be filtered by person, action, dates and text and exported to Excel. The administrator sees everybody's actions; an accountant sees only their own. The history of one row is open to everyone who works on the accounting.
- Migration `0022_row_versions` adds `version`, `updated_at` and `updated_by` to fee lines, salary lines and sheet rows.

## Receipts

Every expense row can carry the number of the paper receipt and up to five files (PDF, JPG, PNG, WEBP; 3 MB each; the first bytes of the file must match
its type). Either one counts as "documented". The files are kept in the database (`entry_receipts`), are read only after a month is closed, and are
removed with their row. Deleting or adding a receipt is written to the log.

## Server

- `backend/app/workflow.py`: `/api/admin/accounting/workflow` (steps, statuses, closing check), `/week-check`, `/periods/{year}/{month}/export.xlsx`.
- `backend/app/accounting.py`: receipt endpoints (`/entries/{id}/receipts`, `/receipts/{id}/download`), `receipt_no` on a row, the closing check in `/periods/close`.
- Migration `0021_entry_receipts`.
- Exports are real Excel files (openpyxl), made by the server. Every month export is logged as `export.month`.
- Tests: `backend/tests/test_workflow.py`.

## Screens

`admin/workflow.js` (the bar, the board, the basics, the archive, the receipt panel, the weekly check, the yearly table) and `admin/accounting.js`
(the screens of the steps; the sheet takes `focus` (income or expense) and `readOnly`, the overview takes a `mode`: summary, reconcile or close).
Arabic texts with English translations as in the rest of the admin area (`EN_TEXT` in `admin/admin.js`).
