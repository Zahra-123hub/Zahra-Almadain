# Portals of the kindergarten platform

Four sign-in areas share one account system (`/login`). After sign-in the server tells which portals the account may enter
(`portals` in the answer of `/api/auth/entry`); with several roles the person chooses.

| Portal | Path | Roles | Files |
|---|---|---|---|
| Login | `/login/` | all | `portal.js`, `portal-text.js`, `portal.css` |
| Parents | `/parents/` | parent | `portal.js` |
| Teachers | `/teachers/` | teacher (admin sees posts and material of everybody) | `portal.js` |
| Management | `/management/` | manager, admin | `management.js` (+ helpers from `portal.js`) |
| Admin and accounting | `/admin/` | admin, accountant (teacher for the website content) | `admin/admin.js`, `admin/accounting.js` |

Every portal is a set of sections behind one navigation bar (`viewShell` in `portal.js`). The browser never decides who may see what:
each call is authorised again by the server (`require_platform_role`, `require_manage`, the fees guard).

## What each role sees

- **Parent**: only the children linked to the account (`parent_child_links`). Published reports (with activities and meals), posts for everybody or
  for their child, notifications, the names of the other guardians of the child (no phone or e-mail), the notices of the management.
- **Teacher**: every child the management has saved (no assignment step; a child appears for all teachers at once, and a removed child disappears). Report editor (draft, attachments, submit for review, status and a hint
  whether parents can see it), posts with a preview, teaching material with the storage meter (250 MB), notifications.
- **Management**: adds, changes and removes the children (with father / mother and their portal account) and the employees (with salary and account); numbers, children with group, teachers and parent accounts (assign and remove), groups (rename), registration requests
  (approve with a one-time code, reject), approval of reports, notices for parents and teachers.
- **Admin**: everything above plus accounts and roles, website content, settings, the system log (read only, CSV), the teachers' files (download, delete), a security overview (numbers only) and accounting (CSV export of fees and salaries).

## Where a finished report goes

A teacher chooses for every report:

- **Save draft** - stays with the teacher, nobody else sees it.
- **Send to the management for review** - state `submitted`; the management reviews it and publishes it to the parents (or returns it). The management is notified.
- **Send to parents directly** - state `published` at once (after a confirmation question); the parents of that child see it and are notified, the management is told (`report_direct`) but is not asked. The teacher cannot change it afterwards.

Only one destination per report (the server refuses both). Attachments of a report stay private to the teacher and the management in every case. A returned (`rejected`) report can be sent again to either side.

## Notifications

Created by the server when: a report is submitted (management), published (parents of the child), returned (the teacher), a post is made (parents
concerned) and a notice is published (all parents and teachers). A notification stores only a kind and a short subject; the portal translates it.

## Server parts

- `backend/app/community.py`: notifications, notices, groups, statistics, guardians view, storage use, list of teacher/parent accounts.
- `backend/app/main.py`: `require_manage` (admin or manager) is used for children, assignments and registration requests.
- Migration `0020_community`: tables `notifications`, `announcements`, columns `activities` and `meals` of `daily_reports`.
- Groups are the class names of the children (`children.class_name`), so the accounting lists and the groups always agree.

## Tests

`backend/tests/test_community.py` (notifications, notices, management rights, guardians, storage, manager sign-in). Run all with
`python -m unittest tests.test_api tests.test_accounting tests.test_accounting_controls tests.test_children_admin tests.test_community tests.test_fees tests.test_security tests.test_database`
inside `backend/`.

## Cache versions

After a change to `portal.js`, `management.js`, `portal.css` or the admin files raise the `?v=` number in the HTML files that load them
 (`login/`, `teachers/`, `parents/`, `management/`, `admin/index.html`).

## Files

- `portal-text.js`: every word of the portals in Arabic and English (change texts here only).
- `portal.js`: session, navigation, parent and teacher screens, shared parts (notifications, profile, notices).
- `management.js`: the management screens.
- `admin/admin.js`, `admin/accounting.js`: the admin dashboard and the accounting area (CSV export, system log, files, security).
