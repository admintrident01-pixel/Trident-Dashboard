# On-call roster — design mockup

Status: **mockup only**. No app code or live data was changed.

## Images

- `oncall-desktop.png` — main page, simplified layout.
- `oncall-handover.png` — hand-over dialog (technician list + open-to-everyone option).
- `oncall-mobile.png` — responsive phone layout.

## Page structure

1. **This week / Next week** — one two-part card. Current technician, acceptance state, hand-over and release to pool on the left; next technician, acceptance deadline and resend-email on the right.
2. **Roster** — one row per week (Week 46 onwards). Current week is highlighted. Assigned, awaiting-accept and open weeks all live in the same list, so there is no separate pool section. Open rows have a **Grab** action.
3. **Rotation order** — a single line showing the admin-defined order (Daniel → Mereana → Sione → Aroha → Ben) with **Edit order**.
4. **Email line** — one quiet footer inside the roster confirming every change is emailed, with a **Recent activity** link.

The hand-over dialog contains only the technician choice, the open-to-everyone option, the email notice and Cancel/Confirm.

## Behaviour assumed (please confirm)

1. On-call week runs **Monday 12:00 am to Sunday 11:59 pm** (NZDT).
2. Admins set the rotation order; technicians see it but cannot reorder it.
3. A technician accepts their own week from the page or email link. Until then it shows **Awaiting accept**.
4. Hand-over is immediate: outgoing and incoming technicians plus admins are emailed. No reason or note is captured.
5. Releasing a week puts it in the open pool; every technician is emailed and the first to grab it wins.
6. All technicians and admins are emailed on every change. Failed sends are retried and shown under Settings → Email reminders.
