# Trident Dashboard working preferences

- Before each update is pushed to GitHub or deployed online, complete and test it locally, open a local preview for the user, and ask for explicit approval of that reviewed release. Wait for approval before pushing or publishing. This preference was requested on 13 October 2026 and replaces the earlier automatic-publishing workflow.
- Keep the output folders tidy during each update. Maintain one master web app source with supporting documents, one current cumulative update package, and a separate project/conversation history folder. Archive superseded packages instead of deleting needed history. Preserve all business records, credentials and user files.
- Source/local preview: C:/Users/TECH11/Documents/Trident-Complete-Computer-Transfer/outputs/Version C/Online. GitHub clone: C:/Users/TECH11/Documents/GitHub/Trident-Dashboard. Local preview: http://127.0.0.1:18780/.
- The online dashboard is https://trident-dashboard.admintrident01.workers.dev/. A push to main automatically starts frontend and API deployments, so a GitHub push is also a publishing action requiring the approval above.

## Icon style

- Use the supplied Feather icon pack and shared `src/Icon.jsx` component. For a missing icon, draw one in the same 24px, 2px rounded-outline style. Follow `ICON-STYLE.md`; preserve compact controls and accessible labels. This preference was requested on 18 October 2026.

## Usage

- Check account usage during sustained work. At 3% remaining or less in a usage window, stop work until that window resets. Resume when the user returns after reset. Requested on 18 October 2026.
- The user explicitly authorized publishing the current stocktake update after local completion and testing on 18 October 2026; this authorization applies to this release only.
