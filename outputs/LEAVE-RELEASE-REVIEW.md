# Leave update — local review ready

Status: APPROVED FOR PUBLISHING. Reviewed and approved 13 November 2026; production backup completed before push.

## Scope in the working tree

- Guided leave form with per-date full-day or part-day hours, lunch choice/confirmation and correction reasons.
- Mixed requests save a per-date breakdown; approval expands to daily rows and keeps request identity.
- Pending leave is read-only on the schedule; approved leave blocks schedule hours and fills matching time-sheet days.
- Direct paid hours retain actual start/finish; drafts, history and payables show work and leave details.
- Labour Excel export is seven columns (Name, Date, Start, Finish, Payable hours, Lunch hours, Notes), HH:mm actual times; supporting sheets retained.
- Import job removed from main navigation and from the quote editor; imported-job cleanup endpoint and recycle-bin restore are present.

## Verification completed

- Backend: 557 tests pass with the recorded performance workbook fixture.
- Frontend: 91 JS tests pass; eslint passes; production Vite build passes.
- Actual local UI run: submitted a 17–19 Nov request (8 / 3.5 / 8 = 19.5 h), approved it, confirmed the 8 h schedule block, 3.5 h + lunch detail, timesheet auto-fill to 8 / 3.5 / 8 and payables total 19.5.
- Actual XLSX download inspected: seven columns, leave notes and 0.5 h lunch exclusion present.
- Mobile (390x844) leave form checked; controls meet touch sizing.

## Preview

- App: http://127.0.0.1:18780/#leave
- API: http://127.0.0.1:18782 (local synthetic data in .local-data only)

## Publishing sequence

1. Explicit user approval of this reviewed local release — completed.
2. Live register/upload backup in authenticated Cloud Shell before push — completed at register revision 16603 with 35 upload objects checksum-verified.
3. Commit and push main; frontend and API deploy automatically.
4. Compare live business values, prior uploads, service environment, secrets, identity and runtime settings after deployment.
5. Live imported-job deletion is NOT part of publishing. It requires a separate action-time confirmation, a recoverable snapshot and recycle-bin entries.

