# Online reminder connection — reviewed release, activation pending approval

Project: `trident-dashboard-511203`. Region: `australia-southeast1`.

On 20 October 2026, the live register had automatic timesheet reminders enabled, a Saturday 15:00 Auckland deadline and a 24-hour lead. This means the first reminder is Friday 15:00. Eight active technician accounts were verified. No recent automatic timesheet emails were queued. The Cloud Scheduler API was disabled and the deployed API had no `REMINDER_JOB_TOKEN`. SMTP was configured and other emails had been sent. Do not change the saved deadline or import local data.

## Connection to activate after release approval

1. Back up the current live register and compare uploaded-file metadata before publication. Preserve all online business values.
2. Publish the reviewed frontend/API changes and verify both deployments.
3. Enable Cloud Scheduler in the existing project, subject to the owner's approval of the Google Cloud terms shown by the console.
4. Generate a random, private token of at least 32 bytes. Configure it as `REMINDER_JOB_TOKEN` on the API. Keep all existing environment variables and SMTP secrets. Never put the token in source, screenshots, logs, query strings or release packages.
5. Create one HTTP job named `trident-automatic-reminders`, region `australia-southeast1`, frequency `*/5 * * * *`, timezone `Pacific/Auckland`, method POST, target `https://trident-quote-api-383423323438.australia-southeast1.run.app/api/reminders/run`, body `{}`, Content-Type `application/json`, Authorization `Bearer <private token>`. The token only authorizes reminder processing and a count-only connection check, not admin access or business data retrieval. Start the job paused while verifying the connection. Do not create duplicate jobs.
6. Call `/api/reminders/check` with the same authorization. This read-only check must return `checked: true` without altering records or sending emails. Never manually run `/api/reminders/run` merely to test authentication.
7. After approval to activate automatic reminders, resume the job. Existing enabled reminder rules now run independently of an open browser or local computer. Due reminders may begin sending immediately; daily deduplication and submission checks remain active. Check scheduler execution results, Settings last-run status, and Email history. A successful SMTP handoff does not by itself prove inbox delivery. Send an individual test only to a recipient explicitly approved by the owner.
8. Compare the live business sections and uploaded-file metadata to the checkpoint. Only expected reminder queue/deduplication/job-status changes may differ. Keep recoverable backups.

## Operational checks

- Every check uses Auckland local time and its daylight-saving offset. The first reminder boundary is exact; rounded display hours do not control delivery.
- Repeated scheduler executions do not duplicate a recipient/week/day reminder. Submitted sheets stop that week's reminders. Other enabled reminder types retain their existing rules.
- Settings shows missing connection, no successful execution, healthy execution or checks stopped (20 minutes without a successful run). Last successful check time is persisted separately from business records.
- Failed or ambiguous SMTP deliveries remain visible in Email history and are not silently retried, preventing accidental duplicates.
- Pause the job to stop automatic sending; keep its private token and historical records recoverable. Do not disable SMTP or overwrite the register as a rollback.

Reference: [Google Cloud Scheduler schedules and time zones](https://docs.cloud.google.com/scheduler/docs/configuring/cron-job-schedules).
