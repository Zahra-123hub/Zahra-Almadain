# Visitors of the website

The admin tab **الزوّار** shows how many people looked at the public site and who signed in to the portals.

## What is counted

- The public page sends one small message ("beacon") to `/api/track` once per browser tab and visit. It is not sent when the browser asks not to be
  tracked (Do Not Track) or while the site is opened on `localhost`.
- The server stores: the day, the page, the **website** the visitor came from (the name only, nothing after it), the kind of device (phone,
  computer, tablet) and the language. Table `site_visits`, migration `0023_site_visits`.
- **Not stored:** the address (IP), the browser string, any name or cookie. The address and the browser are only mixed into a fingerprint that
  **changes every day**, so one person counts once per day and nobody can be followed from one day to the next.
- Robots (Googlebot, curl, scripts...) are ignored. The private areas (`/admin`, `/login`, `/parents`, `/teachers`, `/management`, `/api`) are never counted.
- A single visitor cannot add more than 100 views a day. Visits older than 400 days are deleted now and then.
- The unique visitors of a period are the sum of the daily unique visitors (a person who comes on three days counts three times).

## Who is known

Visitors of the public site are anonymous. **Names exist only for accounts:** the tab lists the accounts that signed in to the portals in the chosen
period (name, role, number of sign-ins, last sign-in) and how many signed in during the last 30 minutes.

## Settings

`SITE_HOSTS` (comma separated, optional) lists the website names that count as "our own site" for the origin of a visit
(default: `zahratalmadain.com`, `www.zahratalmadain.com`, `zahra-123hub.github.io`, `localhost`, `127.0.0.1`).

## Data protection

The counting is built to keep as little as possible. Because it is still a form of measuring, mention it in the privacy statement of the website
(for example: "We count visits without cookies and without storing addresses.").
