# Elbasan Pulse civic interface

The user approved the Civic workspace preview and requested implementation with distinctive, purposeful animation. This supplements the approved product architecture; it does not implement the future municipal API.

## Design and scope

Use Source Sans 3, navy text, light stone surfaces, and Elbasan-inspired blue and yellow. The user's requested heritage palette follows the familiar verdhëblu identity, referenced at [AF Elbasani](https://afelbasani.al/); these are screen-adapted shades, not claimed official municipal color specifications. Deep blue navigation (#153574) and golden yellow (#edc443) establish the identity. Yellow uses dark blue text (#172c54); the light-theme chart uses a darker gold (#a07812) for contrast. Amber/green status colors retain their semantic meaning. A compact persistent sidebar contains Overview, Sources, Ask the data, and Monthly briefing. Albanian and English have equal coverage. Light is the initial appearance; dark and system themes remain available.

Dark mode uses charcoal surfaces (#15191f canvas, #1d232b panels) with muted gold (#d7b768) and soft blue accents. Selected navigation uses a quiet slate fill with gold text. Filled actions use a separate medium blue (#345c98) and white text, while text links use a lighter blue for contrast. This refines the palette in response to the user's feedback that the original dark treatment was too strong.

The overview presents received requests, on-time resolution, and overdue requests, followed by a trend chart, actionable exceptions, and a department table. Month and department filters update all relevant quantities. Every derived value comes from one explicitly synthetic dataset. Sources and department details open accessible side sheets.

Sources includes an honest local CSV preview: choose a sample or a local CSV, validate size/content, map columns, review, and confirm a preview. Nothing is represented as written to the warehouse. No personal file content is transmitted. Source preview state is session-local.

Ask the data provides deterministic, labeled sample questions and answers with query/source evidence. Unknown questions receive an explanatory unavailable state, never a fabricated answer. Monthly briefing uses the same sample metrics and can download a labeled Markdown report or print.

The identity mark combines a civic tower with a short pulse line. A brief trace on deliberate brand interaction and a source-to-result diagram make the integration story tangible. Motion responds to selection, disclosure, and import progress; reduced-motion users receive static equivalents. There are no endless decorative animations.

Iconography is plain line work without decorative backgrounds, borders, tiles, or circles. This applies to the brand mark, department icons, source diagram, file icons, and success indicator. Copy uses simple punctuation with no em dashes; date ranges use a short hyphen. Empty CSV values have localized text labels.

## Validation

Use Node's built-in test runner for aggregate calculations and CSV parsing/validation. Check the full existing API suite, frontend lint, and production build. Inspect and interact with all four routes in the browser at desktop and narrow phone widths, in both languages and themes. Verify keyboard-accessible controls, sheet focus/escape, empty and invalid inputs, consistent sample labels, and reduced-motion rules.
