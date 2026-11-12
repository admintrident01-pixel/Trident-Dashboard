# On-call roster — design mockup

Status: **mockup only**. No app code or live data was changed.

## Images

- `oncall-desktop.png` — main roster page (admin view, desktop).
- `oncall-handover.png` — "Hand over on-call" dialog with technician selection, public-pool option and email notice. No reason or free-text note fields.
- `oncall-mobile.png` — responsive phone layout.

## What the page covers

- New compact **On call** item in the main navigation.
- **On call now** card: current technician, contact details, week covered, acceptance timestamp and weekend backup.
- **Next on call** card: next technician, acceptance deadline, fallback in the order, reminder timeline.
- **Roster by week**: one technician per week (Monday–Sunday), including the current week, with status and email confirmation.
- **Public pool**: unassigned weeks anyone can grab; shows who released it, when and why.
- **Allocation order**: admin-only ordering, visible to everyone; position 1 is on call now, position 2 is next.
- **Upcoming weeks**: assignment, backup, status and who was emailed.
- **Recent changes**: audit feed with "Emailed N people" markers.
- **Who gets emailed**: the notification rules for accept, handover, public pool and weekly reminder.

## Behaviour the mockup assumes (please confirm)

1. The on-call week runs **Monday 12:00 am to Sunday 11:59 pm** (NZDT).
2. Admins set the order; technicians can see it but not reorder it.
3. Position 1 covers the current week, position 2 the next week, and so on. The order rolls forward each week.
4. A technician accepts their own week from the page or an email link. Until accepted it shows **Awaiting accept**.
5. Handover is immediate after confirmation: the outgoing technician, incoming technician and admins are emailed. No second approval step.
6. A released week enters the **public pool**; every technician is emailed and the first to grab it wins.
7. Emails go to all technicians plus admins by default. Failed sends are retried and surfaced in Settings → Email reminders.
8. The existing Google backend remains authoritative; this adds on-call records, it does not replace current data.

## Design notes

- Reuses the dashboard palette, type, spacing, Feather icons and compact control sizing.
- Admin-only actions are labelled; destructive release uses a quieter red outline.
- Mobile keeps the same priority order: current on call, next, this week, pool, order, upcoming weeks.
