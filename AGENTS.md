# Trident Dashboard working preferences

- Before each update is pushed to GitHub or deployed online, complete and test it locally, open a local preview for the user, and ask for explicit approval of that reviewed release. Wait for approval before pushing or publishing. This preference was requested on 13 October 2026 and replaces the earlier automatic-publishing workflow.
- Keep the output folders tidy during each update. Maintain one master web app source with supporting documents, one current cumulative update package, and a separate project/conversation history folder. Archive superseded packages instead of deleting needed history. Preserve all business records, credentials and user files.
- Source/local preview: C:/Users/TECH11/Documents/Trident-Complete-Computer-Transfer/outputs/Version C/Online. GitHub clone: C:/Users/TECH11/Documents/GitHub/Trident-Dashboard. Local preview: http://127.0.0.1:18780/.
- The online dashboard is https://trident-dashboard.admintrident01.workers.dev/. A push to main automatically starts frontend and API deployments, so a GitHub push is also a publishing action requiring the approval above.

## Icon style

- Use the supplied Feather icon pack and shared `src/Icon.jsx` component. For a missing icon, draw one in the same 24px, 2px rounded-outline style. Follow `ICON-STYLE.md`; preserve compact controls and accessible labels. This preference was requested on 18 October 2026.

## Usage

- Check account usage during sustained work. Stop at 20% remaining or less in either usage window. Resume when the user returns after reset or explicitly changes the limit. Latest limit requested on 9 November 2026 supersedes earlier thresholds.
- The user explicitly authorized publishing the current stocktake update after local completion and testing on 18 October 2026; this authorization applies to this release only.

## Online data preservation

- Online business values are authoritative and must survive every release. Before and after updating, back up and compare the live register and uploaded files; do not replace online state with a local database or seed values. Preserve quotes, schedules, stock and asset identities/history, Shared resources, settings, users and all other online records. Merge missing local content only when requested, keeping existing online values and retaining recoverable backups. Requested on 18 October 2026.

## Usability and performance

- For every future update, review clarity, compact spacing, button placement, responsiveness and loading cost. Prioritise the main working content, especially schedule blocks. Preserve all existing functionality and business data; verify improvements locally. Requested on 20 October 2026.

## Supabase migration priority — 9 November 2026

- Full migration to Supabase is the target architecture and takes priority in future implementation choices. Keep the frontend on Cloudflare. Use Supabase Postgres, private Storage, Auth and Edge Functions as appropriate for the completed backend; retaining the existing Python/Google backend or one large compatibility JSON record is a temporary migration step, not completion.
- Use free services only for now. Do not enable paid plans, hosting or add-ons without explicit authorization. Replace existing Python functions where needed rather than making a new paid Python host a requirement.
- Keep the existing app running while creating and verifying a separate replica. Google remains authoritative until an explicitly approved cutover. Preserve all records, identities, permissions, files, business rules, financial values, history and existing functionality. Retain only Maps and specifically needed Google integrations at the end; manual-only paid routing remains mandatory. Google deletion is a separate approved step after acceptance and recoverable backups.
- Verified migration project: Trident Migration Sydney, asxogtpndlsgwdjcxxdv, Free, ap-southeast-2. Preserve the original Singapore project. Do not store passwords or service-role keys in source or chat.
- Eventually migrate MobilityDB/dbFLEX data and functionality into the integrated Supabase-backed app. A job-page scrape is not a full database/functionality migration; inventory and reconcile the full source separately.
- Current planning/checkpoints: outputs/SUPABASE-MIGRATION-PLAN.txt and outputs/SUPABASE-MIGRATION-INVENTORY.json. Initial SQL is an unexecuted local draft; no data replication or production cutover has occurred.

- PDF/file storage: use private Supabase Storage for PDFs and other required files in the replica. Preserve original keys/references and checksum-verify copies; keep existing live objects intact until the approved cutover. Requested on 9 November 2026.

- Chat separation: the user paused Supabase migration and reserved it for a separate chat. This chat is for new features on the existing app; do not resume migration here. Retain migration checkpoints for the separate chat and keep current production behavior intact. The long-term Supabase target remains documented. Latest user instruction on 9 November 2026.
