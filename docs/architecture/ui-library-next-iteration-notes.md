# UI Library Next Iteration Notes

Purpose: track fixes and component extractions that should move into `@kairosstack/ui` so app repos stay thin and consistent.

## Immediate Issues Observed in `kairos-core`

- Select/dropdown content appears transparent, compressed, and incorrectly layered.
- React warning appears for refs through `SlotClone` when using `DropdownMenuTrigger asChild` with current `Button` implementation.
- App-level Tailwind scanning did not include UI package classes, causing style drop-off for library components.

## Consumer-Side Baseline (Done in this repo)

- Added UI package path to Tailwind sources in `frontend/src/styles/tailwind.css`.
- Temporary shell trigger buttons are native `button` elements to avoid ref warnings until UI `Button` is fully `forwardRef`-safe.
- Added app-level overlay fallbacks in `frontend/src/styles/overrides.css` and explicit `kairos-*` classes on select/menu content/items to stabilize opacity, spacing, width, and z-index while UI primitives are being normalized.

## UI Library Work Items

### 1) Ref forwarding and `asChild` compatibility

- Ensure `Button` uses `React.forwardRef` and passes `ref` to the underlying DOM element.
- Verify all trigger-style components used with Radix `Slot` support refs.
- Add regression examples/tests for `DropdownMenuTrigger asChild` + `Button`.

### 2) Overlay primitives: Select/Dropdown/Popover

- Ensure content is rendered with `Portal` by default.
- Standardize content layering tokens (`z-index`) across all overlays.
- Enforce non-transparent content defaults (`bg-popover`, border, shadow).
- Ensure width behavior matches trigger for Select via Radix variables:
  - `w-[var(--radix-select-trigger-width)]`
  - `min-w-[var(--radix-select-trigger-width)]`
- Normalize item spacing and line-height so lists are not visually squished.

### 3) Tailwind distribution strategy

- Decide on one supported strategy for consumers:
  1) ship precompiled CSS with the UI package, or
  2) require consumer `@source` for package files.
- Document chosen strategy in UI package README with framework-specific examples (Vite/Tailwind v4).
- If keeping source scan strategy, publish stable path guidance and verify monorepo + npm install layouts.

### 4) Field focus context API (for contextual helper panels)

- Add `FieldFocusProvider` and `useFieldFocus()` hook.
- Add a `Field` wrapper primitive with metadata:
  - `fieldId`, `label`, `description`, `step`, `group`
- Emit focus metadata with `onFocusCapture`/`onBlurCapture` for input/select/textarea controls.
- Keep API optional and non-invasive so existing fields can migrate incrementally.

### 5) Accessibility and interaction audits

- Validate keyboard interactions for Select and Dropdown across open/close/select flows.
- Validate focus ring visibility and contrast in light mode.
- Validate overlay collision handling and viewport boundaries.

## Candidates to Move from `kairos-core` into UI Library

- Reusable step-navigation/sidebar pattern used by setup wizard (`StepSidebar`) after generic API extraction.
- Reusable tag/chip entry field (`TagInput`) once generalized and tested.
- Generic status row/summary card patterns used in preflight/runtime/result panels.

## Suggested Implementation Order

1. Ref forwarding fixes (`Button` and trigger-related primitives).
2. Overlay styling + portal + width behavior normalization.
3. Tailwind distribution/documentation finalization.
4. Field focus context primitives.
5. Optional extraction of wizard-adjacent reusable composites.

## Verification Checklist for Next Iteration

- No ref warnings in dev console when using `asChild` triggers.
- Select and dropdown overlays are opaque, layered correctly, and width-aligned to trigger.
- Overlay options have consistent spacing and are fully readable.
- Focus events update context panel consistently for input, select, and textarea.
- Consumer setup docs are sufficient to avoid style regression without repo-specific hacks.
