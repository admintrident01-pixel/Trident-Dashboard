# Trident Dashboard — UI interaction map

Generated 14 November 2026 from the local preview at `http://127.0.0.1:18780/`.
The crawl covered all 12 portal screens plus the embedded quote builder and time
sheet. It recorded 714 rendered interactive nodes; after removing the shared shell
and nested SVG/text nodes, that is 377 page-level native controls plus the card,
row, drag and resize targets listed below.

The visual rule for every item in this map is documented in `THEME-RULE.md` and
implemented in `public/trident-ui-theme.css`.

## Shared shell (every screen)

| Object | Behaviour | Themed treatment |
| --- | --- | --- |
| Skip to page content | Keyboard skip link | Visible only on focus, teal focus ring |
| Trident logo / home | Returns to the role home | Black-to-navy header field, soft opacity lift |
| 13 navigation tabs | My day, Quotes, Tech schedule, On call, Time sheet, Leave forms, Labour payables, Vehicle checks, Stock, Settings, Shared resources, Reminders | Active tab has a white wash and amber underline; hover reveals a partial amber rule |
| Unpin / Pin | Toggles persistent navigation | Amber-tinted pressed state, ghost white button |
| Hide navigation | Collapses the header | Ghost icon button, chevron-up |
| Sign out | Ends the session | Ghost outlined button |
| Account label | Email and role | Hidden below 1600px to protect the last navigation tab |
| Local-development notice | Environment message | Amber dot, warm strip |

The header gradient begins at `#202020`, the exact background sampled from
`public/trident-logo.png`, holds across the logo, then deepens through `#060c13`
to ink and navy. Matching the asset removes the rectangular seam around the logo.

## Screen map

| Screen | Page-level controls | Main interactive objects | Theme notes |
| --- | ---: | --- | --- |
| My day | 21 | Refresh, previous/next day, date field, Today, Day summary, Finish day, Custom job, reminder rows, history sort headers, pagination, preview email | Reminder rows use a teal hover wash and a nudging chevron; Finish day is the primary action |
| Reminders | 10 | Refresh deadlines, rows-per-page, pagination, four sort headers, preview email | Compact table controls, teal sort triangles |
| Quotes (dashboard) | 19 | Quote dashboard, New quote, All/Drafts/Completed filters, search, five sort headers, pagination, Open draft, Delete, Quote dashboard | Amber New quote; pill filters; navy active filter with amber inset |
| Quotes (editor) | 20+ form fields, line editors | Quote details/Calculate labour tabs, quote type, number/date/by, customer and client fields, job details, equipment/vehicle, wording, line items, Add item, notes, Save draft, Load draft, Email quote, Finalise & save PDF, Delete draft | Ghost actions on the navy toolbar; amber Finalise; navy active tab with amber rule |
| Tech schedule | 30 | Search, messages disclosure, cancelled checkbox, previous/next day, date, compact first-name technician filter, weekday buttons with undo/redo pinned at the right of Friday, sync refresh, Book appointment, eight technician swap selects, eight appointment tracks, appointment cards, zoom controls. Bulk Move/Book/Unbook/Optional/Delete stay in the block context menu | 32px dense buttons; amber Book appointment; teal selection and drop states; 13px block checkboxes centred in the colour rail; travel labels clipped to 9px/10px icon so they cannot bleed into neighbouring blocks |
| On call | 11 | Previous/next week, This week, Hand over, Release to pool, Resend email, Recent activity, Resend, Edit order | Teal avatar rings, navy Hand over, quiet text actions |
| Time sheet | 117 | Back to My day, history search/sort/pagination, refresh, technician/week fields, seven day rows (work/leave, entry method, direct hours, start/finish AM/PM, lunch, notes), signature, on-call radios, Save draft, New sheet, Generate PDF, Sign and submit, Download, history actions | Standard fields; compact time geometry; amber Sign and submit; white secondary actions |
| Leave forms | 17 | Back to My day, leave type, dates, day editor, timed leave fields, reason, submit, status pills, detail/review actions | Semantic status pills; teal focus and row hover |
| Labour payables | 79 | Week/date fields, 56 numeric hour cells, submit, weekly history, sort headers, export actions | Dense numeric grid; table header wash and teal sort |
| Vehicle checks | 15 | Back to My day, refresh, Manage vehicles, New vehicle check, history vehicle select, check form fields, matrix actions | Navy primary; consistent compact controls; existing red/amber/green status colours retained |
| Stock & assets | 20 visible + product tree | Start stock take, refresh, Export, Movement history, Stock settings, five metric tiles, flow filters, search, Add product, Custom move, Review supplied workbook, product/asset toggles, asset moves | Metric tiles lift on hover; flow filters use teal selection; product rows use a teal wash |
| Settings | 31 on Staff & vehicles | Six-section rail, Staff/vehicle and Dashboard tabs, Refresh, Add staff member, Add vehicle, search/filter, Edit, More actions, pagination, forms, save/delete, reminder controls | Rail items get a teal left inset; active top tab is navy with amber rule; table header wash |
| Shared resources | 12 | Search, Upload files, Folder, All files, view/size selects, Trash, Copy/Cut/Paste/Clear, file rows, Reset layout, divider, eight resize edges | Teal row inset; pale splitter with a small grip; resize handles tint teal |

## Control families

| Family | Examples | Shared treatment |
| --- | --- | --- |
| Primary | Finish day, Start stock take, Hand over, New vehicle check | Navy gradient, white text, stronger shadow |
| Accent | Book appointment, New quote, Finalise & save PDF, Sign and submit | Amber gradient, dark text, used only for create/book/confirm |
| Secondary | Refresh, Today, Add vehicle, Save draft, Generate PDF | White surface, strong border, hover lift |
| Quiet / text | On-call Resend, Recent activity, text links | Transparent, teal text, underline on hover |
| Danger | Delete selected, Delete draft, Delete quote, staff delete | White with red text, red-tinted hover |
| Icon-only | Search, pin, hide, more actions, previous/next, refresh, zoom | Square/round 28–34px controls with accessible labels |
| Tabs | Settings rail, Staff/Dashboard tabs, quote editor tabs | Navy/white active state, amber underline or teal inset |
| Filters / segmented | Quote filters, schedule weekday selection, AM/PM | Pills or compact segmented controls; selected state teal or navy |
| Status pills | Leave approved/pending/declined/cancelled | Semantic fills retained, 999px radius |
| Fields | Text, date, search, number, select, textarea | 36px, 9px radius, teal focus ring, shared select chevron |
| Check / radio | Vehicle checklist, schedule cancelled, on-call yes/no | Teal accent; 44px labels where the form is touch-oriented |
| Sort headers | History, reports, stock, settings | Transparent, teal hover, up/down triangles |
| Cards / rows | Module cards, My day jobs, stock metrics, office rows, on-call cards | 14px radius, resting shadow, hover lift |
| Dialogs | Schedule appointment, My day, vehicle, stock, office, settings, quote | 14px radius, blurred navy backdrop, short entrance |
| Drag / resize | Appointment cards, schedule selection, office divider, eight edges | Teal drag preview, teal selected ring, teal-tinted handles |
| Disclosure | Schedule messages, time-sheet help, reminder secondary rules | Pointer cursor, teal hover, rotating chevron |

## Arrow and icon map

| Icon | Where it appears | Interaction |
| --- | --- | --- |
| `chevron-left` / `chevron-right` | Day/week navigation, pagination | Nudges 2px in its direction on hover |
| `chevron-up` | Hide navigation | Collapses the header |
| `chevron-down` | Select fields, disclosures | Shared 12px select chevron; disclosure rotates 180° |
| `arrow-left` | Back to My day | Nudges left on hover |
| `arrow-right` | Recent activity, module links | Nudges right on hover |
| Up/down triangles | All sortable tables | Teal active arrow, quiet inactive arrow |
| `refresh-cw` | My day, vehicle dashboard, stock, schedule | Idle hover lift; spinning while syncing |
| `rotate-ccw` / `rotate-cw` | Schedule undo/redo | Standard secondary controls |
| `repeat` | Schedule hours view, On-call handover | Standard secondary controls |
| `plus` / `minus` | Schedule zoom | Compact zoom pair around the percentage reset |
| `search` | Schedule, stock, settings, office, quote search | Icon button or pill search field |
| `calendar` | My day, On-call This week, date fields | Teal hover and focus |
| `download` / `upload` | Stock export, shared resources | Standard secondary controls |
| `edit-2`, `more-horizontal`, `sliders` | Settings row actions, schedule order | Compact icon controls |
| `mail`, `users`, `truck`, `clock`, `clipboard`, `grid`, `tool`, `package`, `user-plus`, `folder-plus`, `copy`, `scissors`, `trash-2`, `alert-triangle`, `file-text` | Page-specific actions and status rows | 16–20px Feather outline, currentColor |

## Animation and motion map

| Motion | Where | Purpose |
| --- | --- | --- |
| `schedule-sync-spin` (existing) | Schedule sync refresh icon | Shows a live sync in progress |
| `td-dialog-in` (new) | All dialogs | Short opacity/scale/translate entrance |
| `td-fade-up` (new) | First paint of page content and quote dashboard | Soft orientation without delaying input |
| `td-sync-glow` (new) | Schedule sync button while syncing | Reinforces the spinning icon |
| `td-live-pulse` (new) | On-call activity dot | Quiet live indicator |
| `td-spin` (new) | Boot splash and every "Opening page…" / "Loading…" state | Teal ring spinner sized to the theme |
| Navigation underline | Header tabs | Amber rule scales from the centre |
| Card top rule | Module cards | Teal-to-amber rule expands on hover |
| Hover lift | Buttons, cards, stock metrics, appointment blocks | 1–3px lift with shadow increase |
| Press | Buttons | `scale(.985)` plus inset shadow |
| Arrow nudge | Directional icon buttons | 2px movement toward the destination |
| Disclosure rotation | Reminder/schedule/time-sheet summaries | 180° rotation when open |
| Drag states | Schedule appointments | Source fades, preview dashes, moving block lifts |
| Resize feedback | Office divider and resize edges | Pale teal tint and visible grip |

All non-essential motion is disabled under `prefers-reduced-motion: reduce`.

## Embedded workspaces

- `public/quote-builder.html` — body class `trident-quote`: navy toolbar with ghost
  actions, amber finalise, pill quote filters, navy editor tabs, shared fields,
  tables and line editors.
- `public/timesheet.html` — body class `trident-timesheet`: navy header, compact
  time controls, shared fields, white secondary actions and an amber submit action.
- Both documents load `/trident-ui-theme.css` after the base theme.

## Files changed for this pass

- `public/trident-ui-theme.css` — new shared interaction theme.
- `index.html` — loads the interaction theme after the base theme.
- `public/quote-builder.html` — loads the interaction theme last in the head.
- `public/timesheet.html` — loads the interaction theme after the time-entry styles.
- `THEME-RULE.md` — the rule future changes must follow.
- `outputs/UI-INTERACTION-MAP.md` — this inventory.

No business records, database values, API behaviour, credentials or online state
were changed.

## Verification

- Full crawl completed on all 12 screens and both embedded workspaces.
- No browser console errors during the crawl.
- `npm run build` passed.
- `npx eslint src public/*.js` passed.
- Repo-wide `npm run lint` still reports pre-existing errors from bundled copies
  under `.local-runtime`; those are not source files and were not modified.
