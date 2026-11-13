# On-call roster — design mockup

Status: **published and verified on 13 November 2026**. The screenshots below
show the approved design, the running local page and the production page.

## Images

- `oncall-desktop.png` — main page, simplified layout.
- `oncall-handover.png` — hand-over dialog (technician list + open-to-everyone option).
- `oncall-mobile.png` — responsive phone layout.
- `oncall-live-desktop.png` — running local page at desktop width.
- `oncall-live-mobile.png` — running local page at 390px width.
- `oncall-live-handover.png` — running hand-over dialog.
- `oncall-live-order.png` — admin rotation-order editor.
- `oncall-live-production.png` — published page after release verification.

## Page structure

1. **This week / Next week** — one two-part card. Current technician and confirmation state on the left; next technician, acceptance deadline and resend-email on the right. The current week does not show a past deadline.
2. **Roster** — one row per week (Week 46 onwards). Current week is highlighted. Assigned, awaiting-accept and open weeks all live in the same list, so there is no separate pool section. Open rows have a **Grab** action.
3. **Rotation order** — a single line showing the admin-defined order (Daniel → Mereana → Sione → Aroha → Ben) with **Edit order**.
4. **Email line** — one quiet footer inside the roster confirming every change is emailed, with a **Recent activity** link.

The hand-over dialog contains only the technician choice, the open-to-everyone option, the email notice and Cancel/Confirm.

## Behaviour assumed (please confirm)

1. On-call week runs **Monday 12:00 am to Sunday 11:59 pm** (NZDT).
2. Admins set the rotation order; technicians see it but cannot reorder it.
3. A technician accepts their own week from the page or email link. Until then it shows **Awaiting accept**.
4. Hand-over is immediate: all active, verified technicians and admins are emailed. No reason or note is captured.
5. Releasing a week puts it in the open pool; every technician is emailed and the first to grab it wins. An admin can assign an open week back to a technician.
6. All active, verified technicians and admins are emailed on every change. Local previews are kept under Settings → Email reminders and are never sent.
