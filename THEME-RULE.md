# Trident interaction theme — “Deep Current”

Effective 14 November 2026. Every future UI change in this project must follow this
rule. The working implementation is `public/trident-ui-theme.css`; the older
`public/trident-theme.css` remains the layout/compatibility layer.

## Non-negotiable rules

- Use the shared tokens below. Do not add one-off button colours, radii, shadows,
  focus rings, hover lifts or animation timings in component CSS.
- Every interactive element must define hover, keyboard focus-visible, pressed and
  disabled states. Card-like buttons must keep their own padding and height.
- Use the hierarchy: primary (navy), accent (amber for create/book/confirm),
  secondary (white), quiet (transparent text/icon), danger (red text on white).
- Keep compact schedule controls compact. Standard controls are 34px high, dense
  schedule controls 32px, touch/mobile controls 44px. Inputs are 36px.
- Preserve all existing behaviour, labels, keyboard support, data and online state.
- Use the supplied Feather icons at 16–20px with `currentColor`; draw any missing
  icon in the same 24px, 2px rounded-outline style.
- Respect `prefers-reduced-motion`. Motion must explain a change, not decorate.
- The portal header gradient starts at the logo asset's own black (`#202020`, sampled
  from `public/trident-logo.png`) and holds across the logo before deepening through
  `#060c13` to `--td-ink` and `--td-navy`. Matching the asset exactly removes the
  rectangular seam; do not start at pure `#000`.

## Tokens

| Token | Value | Use |
| --- | --- | --- |
| `--td-ink` | `#0b2239` | Body text, darkest header stop |
| `--td-navy` | `#12395c` | Primary actions, headings, active tabs |
| `--td-navy-2` | `#1b4e78` | Primary gradient top, hover |
| `--td-navy-3` | `#245f8f` | Primary hover top |
| `--td-teal` | `#0e7c86` | Focus, selection, live state |
| `--td-teal-deep` | `#0a5c66` | Teal text and links |
| `--td-teal-soft` | `#e8f4f4` | Selected rows, soft highlights |
| `--td-teal-line` | `#9fcdd1` | Selected/hover borders |
| `--td-amber` | `#e08a34` | Create/book/confirm accent |
| `--td-amber-2` | `#f2a64e` | Accent gradient top |
| `--td-amber-soft` | `#fdf3e5` | Pending/warning surfaces |
| `--td-bg` | `#eef3f8` | App background |
| `--td-surface` | `#ffffff` | Cards, fields, dialogs |
| `--td-surface-2` | `#f6f9fc` | Field hover, secondary surfaces |
| `--td-surface-3` | `#edf3f9` | Table headers, tab tracks |
| `--td-line` | `#d3dfea` | Dividers and resting borders |
| `--td-line-strong` | `#aec2d5` | Control borders |
| `--td-muted` | `#5c7187` | Secondary text |
| `--td-danger` | `#b42318` | Destructive actions |
| `--td-success` | `#1d7a46` | Success/live state |

Geometry: `7px` compact, `9px` standard, `14px` cards/dialogs, `999px` pills.

Elevation: `--td-shadow-1` resting, `--td-shadow-2` hover, `--td-shadow-3` dialog.

Motion: `140ms` colour/press, `220ms` transform/dialog, ease
`cubic-bezier(.2,.75,.3,1)`.

## Component rules

### Buttons

- Base: white surface, `1px` strong line, `9px` radius, 34px high, navy text,
  `--td-shadow-1`.
- Hover: `surface-2`, teal-leaning border, `--td-shadow-2`, `translateY(-1px)`.
- Pressed: no lift, `scale(.985)`, inset shadow.
- Focus-visible: `2px` solid teal, `2px` offset, `--td-ring`. On the dark portal
  header, use the amber focus ring so it stays visible.
- Disabled: 55% opacity, `not-allowed`, no transform or shadow.
- Primary: navy gradient, white text. Accent: amber gradient, dark text. Danger:
  white with red text, red-tinted hover. Quiet: transparent, text only.

### Inputs, selects and textareas

- `36px` minimum height, `9px` radius, `#c8d7e6` border, white surface.
- Hover border `#9fb9ce`; focus border teal plus `--td-ring`; disabled grey.
- Selects use the shared 12px chevron; search fields are pill-shaped.
- Checkbox/radio use `accent-color: var(--td-teal)`.
- Tiny time controls (`AM`/`PM`, digit fields) keep their compact 18/38px geometry.

### Tabs, filters and pills

- Tab tracks use `surface-3`; inactive tabs are quiet; active tabs are navy with an
  amber bottom inset, or a white rail item with a teal left inset.
- Filter buttons are pills. Selected filters are navy with an amber underline inset.
- Status pills keep their semantic green/amber/red/grey fills and use 999px radius.

### Tables and sorting

- Header cells use `surface-3` with navy text.
- Sort headers are transparent and quiet. Hover turns them teal. The active
  triangular arrow uses teal; both triangles remain visible.
- Row hover uses a very light teal wash.

### Cards, rows and schedule blocks

- Cards use `14px` radius, resting shadow, and a 2–3px hover lift.
- Clickable rows use a teal inset bar on hover/focus, not a full colour fill.
- Schedule blocks keep their status fills, gain a `7px` radius, a resting shadow,
  `translateY(-1px)` on hover, a teal selected ring, and clear drag/drop states.
- Resize handles turn teal on hover; the office splitter uses a pale tint plus a
  small grip, never a full-height saturated stripe.

### Dialogs and motion

- Dialogs use `14px` radius, strong shadow, blurred navy backdrop, and a short
  `td-dialog-in` entrance.
- First paint of a page uses `td-fade-up` (opacity/translate only). Live sync uses
  the existing spin plus `td-sync-glow`; live activity dots use `td-live-pulse`.
- Arrow buttons nudge 2px toward their direction on hover. Disclosure chevrons
  rotate 180 degrees when open.
- All of the above is disabled under `prefers-reduced-motion`.

### Loading

- The first paint shows the `.td-boot` splash: a 30px teal ring on the app
  background tint with "Loading Trident…". It fades out as soon as React mounts.
- Every in-flight message uses `.module-loading`, which pairs the same 16px teal
  spinner ring with the existing status text. Never show a bare "Loading…".
- Keep spinners on `td-spin` (720ms linear); do not invent skeleton colours or a
  second accent for loading.

## Ownership and review

- Add reusable visual rules to `public/trident-ui-theme.css`; component CSS should
  describe structure and layout only.
- Keep the stylesheet linked after every base stylesheet in `index.html`,
  `public/quote-builder.html` and `public/timesheet.html` (`trident-theme.css`,
  `timesheet-form.css`, `time-entry.css`). Base CSS owns layout and geometry; it
  must consume the `--td-*` tokens, never hard-code a colour that the theme would
  then have to fight.
- Before release, review the full interaction map in
  `outputs/UI-INTERACTION-MAP.md`, test keyboard focus on every screen, verify
  mobile layouts at 390px, and confirm no business data was changed.
