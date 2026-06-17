# CodePilot Design System

> Version: 1.0
> Created: 2026-06-17
> Purpose: Define CodePilot's visual language for AI code review and report reading.

---

## 1. Product Personality

CodePilot is a **dark developer cockpit** for evidence-grounded code review. It is:

- **Trustworthy** — every finding cites evidence; the UI never hides errors or masks failures.
- **Precise** — information density matters more than visual flair. Every pixel earns its place.
- **Calm** — dark surfaces, muted text, and a single chromatic accent reduce cognitive load during long reading sessions.
- **Bilingual-ready** — typography and layout must work cleanly with both English and Chinese text.
- **Evidence-first** — the report reading experience is the product, not the submission form.

**What CodePilot is NOT:**

- Not a consumer app. No playful gradients, cartoon icons, or gamification.
- Not a marketing site. No hero sections, parallax, or splashy landing pages.
- Not an IDE. It reads reports, not edits code.

---

## 2. Layout Principles

### Grid

- **Max width:** 1600px, centered.
- **Two-column layout:** 340px sidebar + fluid main content on `lg+`.
- **Single-column:** sidebar stacks above content on `sm`/`md`.
- **Section rhythm:** 20px gap between cards, 32px vertical padding inside cards.

### Whitespace

- Dark canvas IS the whitespace. Do not fill every gap with borders or cards.
- Generous padding inside cards (20px–28px). Tight gaps between related elements (8px–12px).
- Report sections: 20px gap between sections, 28px padding inside each section card.

### Responsive

- Breakpoints: `sm` (640px), `md` (768px), `lg` (1024px), `xl` (1280px), `min-[1200px]` for report sidebar.
- Sidebar becomes full-width on mobile; report outline nav hides below 1200px.
- Minimum touch target: 44px.

---

## 3. Color Tokens

### Surface Depth System

CodePilot uses a **surface ladder** (no drop shadows for elevation). Background color steps carry hierarchy.

| Token | Light Mode | Dark Mode | Use |
|-------|-----------|-----------|-----|
| `background` | `hsl(210 40% 98%)` | `hsl(222 47% 11%)` | Page canvas |
| `card` | `hsl(0 0% 100%)` | `hsl(222 42% 13%)` | Default cards, panels |
| `panel` | `hsl(210 40% 97%)` | `hsl(222 44% 10%)` | Nested panels, sidebar sections |
| `muted` | `hsl(210 40% 96%)` | `hsl(217 33% 18%)` | Hover states, subtle backgrounds |

### Text Hierarchy

| Role | Token | Dark Mode | Use |
|------|-------|-----------|-----|
| Primary | `foreground` | `hsl(210 40% 98%)` | Headings, body text |
| Secondary | `muted-foreground` | `hsl(215 20% 67%)` | Descriptions, labels |
| Tertiary | — | `hsl(215 16% 50%)` | Captions, timestamps, footnotes |

### Chromatic Accent

| Role | Token | Dark Mode | Use |
|------|-------|-----------|-----|
| Primary | `primary` | `hsl(172 66% 50%)` | CTAs, focus rings, links, brand mark |
| Primary FG | `primary-foreground` | `hsl(222 47% 9%)` | Text on primary background |

The accent is **cyan-emerald** — a calm, technical color. Use it sparingly:

- Focus rings, primary buttons, active tab indicators, status dot for running state.
- Never use it as a large background fill or decorative gradient.

### Semantic Colors

| Role | Token | Dark Mode | Use |
|------|-------|-----------|-----|
| Success | `success` | `hsl(158 64% 52%)` | Completed status, positive findings |
| Warning | `warning` | `hsl(38 92% 56%)` | Caution states, medium severity |
| Destructive | `destructive` | `hsl(0 73% 62%)` | Errors, failed status, critical severity |
| Border | `border` | `hsl(217 27% 24%)` | Card borders, dividers |

### Agent Status Colors

Derived from Cursor's timeline pill palette, adapted for CodePilot's agent pipeline:

| Agent Stage | Color | Hex | Use |
|-------------|-------|-----|-----|
| Pending | Muted | `hsl(215 16% 50%)` | Queued agents |
| Running | Cyan | `hsl(172 66% 50%)` | Active agent (pulse animation) |
| Completed | Emerald | `hsl(158 64% 52%)` | Finished agents |
| Failed | Red | `hsl(0 73% 62%)` | Failed agents |

### Severity Colors

| Severity | Color | Use |
|----------|-------|-----|
| Critical | `destructive` | Red badge, left border |
| High | `hsl(25 95% 53%)` | Orange badge |
| Medium | `warning` | Amber badge |
| Low | `muted-foreground` | Gray badge |
| Informational | `primary` | Cyan badge |

---

## 4. Typography Rules

### Font Stack

```css
--font-sans: "Segoe UI Variable", "Segoe UI", ui-sans-serif, system-ui, sans-serif;
--font-mono: "Cascadia Code", "JetBrains Mono", "Fira Code", ui-monospace, monospace;
```

- **Sans** for all UI text (headings, body, labels, buttons).
- **Mono** for code, evidence IDs, task IDs, file paths, and technical data.

### Type Scale

| Role | Size | Weight | Tracking | Use |
|------|------|--------|----------|-----|
| Display | 20px | 600 | -0.02em | Page title ("CodePilot") |
| Heading | 18px–20px | 600 | -0.01em | Section headings |
| Subheading | 14px–16px | 600 | normal | Card titles, panel headers |
| Body | 14px | 400 | normal | Paragraph text, descriptions |
| Body SM | 13px | 400 | normal | Secondary text, list items |
| Caption | 11px | 600 | 0.08em | Uppercase labels ("CONTROL PANEL", "SECTION") |
| Mono SM | 11px | 400 | normal | Task IDs, evidence refs, file paths |
| Code | 13px | 400 | normal | Code blocks, inline code |

### Uppercase Eyebrow Labels

Used for section labels, tab group headers, and metadata labels:

```css
font-family: var(--font-mono);
font-size: 10px;
font-weight: 600;
letter-spacing: 0.16em;
text-transform: uppercase;
color: var(--muted-foreground);
```

---

## 5. Spacing, Radius, and Shadow

### Spacing Scale (4px base)

`2 / 4 / 8 / 12 / 16 / 20 / 24 / 32 / 48 / 64 / 96px`

### Border Radius

| Element | Radius | Token |
|---------|--------|-------|
| Cards | 12px | `rounded-xl` |
| Buttons | 8px | `rounded-lg` |
| Inputs | 8px | `rounded-lg` |
| Status badges | 9999px | `rounded-full` |
| Small badges | 6px | `rounded-md` |
| Code blocks | 8px | `rounded-lg` |

### Shadows

CodePilot uses **minimal shadows** — the surface ladder carries elevation. Shadows are decorative polish, not structural:

```css
--shadow-panel: 0 1px 2px rgba(15, 23, 42, 0.04), 0 8px 24px -20px rgba(15, 23, 42, 0.3);
--shadow-soft: 0 14px 38px -24px rgba(15, 23, 42, 0.34);
```

In dark mode, shadows are nearly invisible. Do not rely on them for hierarchy.

---

## 6. Card Styles

### Default Card

```css
background: hsl(var(--card));
border: 1px solid hsl(var(--border));
border-radius: 12px;
padding: 20px;
box-shadow: var(--shadow-panel);
```

### Panel Card (nested)

```css
background: hsl(var(--panel));
border: 1px solid hsl(var(--border));
border-radius: 12px;
padding: 16px;
```

### Interactive Card (hoverable)

Same as default card, plus:

```css
transition: background 200ms;
&:hover { background: hsl(var(--muted) / 0.6); }
```

### Status Card (selected)

```css
border-color: hsl(var(--primary) / 0.4);
background: hsl(var(--primary) / 0.05);
```

### Evidence Card

```css
background: hsl(var(--panel));
border: 1px solid hsl(var(--border));
border-left: 3px solid hsl(var(--primary));
border-radius: 8px;
padding: 12px 16px;
```

The left accent border signals "this is evidence" without competing with severity colors.

---

## 7. Status States

### Review Status

| State | Visual | Badge |
|-------|--------|-------|
| **Idle** | Muted radio icon, "Idle" text | No badge |
| **Running** | Pulsing primary radio icon, progress bar | Animated dot |
| **Completed** | Emerald status dot, "Completed" text | Emerald badge |
| **Failed** | Red status dot, error message visible | Red badge |
| **Completed with warnings** | Emerald dot + warning icon, error text shown | Emerald + amber |
| **Stale/missing** | History item shows "Review unavailable" | Muted badge, retry CTA |

### Agent Status

| State | Visual |
|-------|--------|
| **Pending** | Muted circle, gray text |
| **Running** | Primary circle with pulse animation, "Running" label |
| **Completed** | Emerald circle with checkmark, finding count shown |
| **Failed** | Red circle with X, error message in tooltip |

### Export State

| State | Visual |
|-------|--------|
| **Available** | Outline button with download icon |
| **Exporting** | Button shows spinner, disabled |
| **Not available** | Button hidden (review not completed) |
| **Error** | Toast notification with retry option |

---

## 8. Report Reading Style

The report is the product. Optimize for **long-form reading** on dark backgrounds.

### Report Layout

- **Two-column on wide screens:** 220px outline nav + report content.
- **Single-column on narrow screens:** outline nav hidden.
- **Section cards:** each major section is a card with section eyebrow label, heading, and content.
- **Appendices:** collapsed in a `<details>` element, de-emphasized.

### Report Typography

- Section headings: 20px, weight 600, tracking -0.01em.
- Body text: 14px, weight 400, line-height 1.7 (generous for long reading).
- Inline code: `hsl(var(--primary))` color, `hsl(var(--muted))` background, 4px horizontal padding, 4px radius.
- Code blocks: mono 13px, panel background, 12px radius, 20px padding, hairline border.
- Lists: 8px spacing between items, 24px left indent.

### Section Outline Nav

- Sticky at `top-24`.
- Eyebrow label: "OUTLINE".
- Links: 14px, muted-foreground, hover → foreground + muted background.
- Active link: foreground color, primary left border (2px).

### Evidence References in Report

- Inline evidence refs: `[E1]`, `[E2]` — primary color, monospace, clickable.
- Evidence appendix: file path, line range, symbol, evidence type, short snippet.
- Evidence IDs (`ev_xxx`) hidden by default, shown in a collapsed detail or tooltip.

---

## 9. Evidence Display Style

### Evidence Reference Badges

```html
<span class="font-mono text-xs text-primary cursor-pointer hover:underline">[E1]</span>
```

- Monospace, primary color, clickable.
- Hover: underline.
- Click: scrolls to evidence in appendix or opens evidence panel.

### Evidence Cards

Each evidence item in the Evidence tab or appendix:

```
┌─────────────────────────────────────────────┐
│ E1  backend/api/reviews.py:42-58            │ ← eyebrow: evidence ID + file:line
│ Function: export_review                     │ ← symbol name
│ Type: function_definition                   │ ← evidence type
│ "The export endpoint returns raw JSON..."   │ ← snippet or summary
└─────────────────────────────────────────────┘
```

- Left border: 3px primary color.
- Eyebrow: mono 10px uppercase, evidence ID + file path.
- Body: 13px, muted-foreground for snippet text.
- File paths: mono, primary color on hover.

---

## 10. Animation Rules

### Permitted Animations

| Animation | Duration | Easing | Use |
|-----------|----------|--------|-----|
| Pulse | 2s infinite | ease-in-out | Running status dot, active agent |
| Fade in | 200ms | ease-out | Toast notifications, error messages |
| Width transition | 250ms | ease-out | Progress bar |
| Color transition | 200ms | ease-out | Hover states on cards, buttons |
| Spin | 1s linear | — | Loading spinners only |

### Forbidden Animations

- No page-wide entrance animations.
- No staggered list animations (too slow for large finding lists).
- No parallax, scroll-triggered reveals, or intersection-observer fade-ins.
- No WebGL backgrounds or canvas effects.
- No cursor-following spotlight effects.
- No text scramble/decrypt animations.
- No bouncing, spring, or elastic easing.

### Rationale

CodePilot users read long reports and scan dense finding lists. Animations that delay content visibility or add visual noise hurt the core use case. The only justified animations are:

1. **Status indicators** (pulse for running, spin for loading) — communicate state.
2. **Progress feedback** (width transitions) — show completion.
3. **Micro-interactions** (hover color changes) — signal interactivity.

---

## 11. What Not to Do

### Visual Anti-Patterns

- ❌ No atmospheric gradients, mesh backgrounds, or aurora effects.
- ❌ No true `#000000` black. Use the defined dark background tokens.
- ❌ No second chromatic accent. One accent (cyan-emerald) is enough.
- ❌ No generous pill-rounded CTAs (16px+ radius on buttons). Keep buttons at 8px.
- ❌ No decorative illustrations or empty-state mascots.
- ❌ No flashy loading animations (skeleton screens are fine).
- ❌ No tooltip-heavy UI. Show information inline where possible.

### Layout Anti-Patterns

- ❌ No full-page modals for non-critical information.
- ❌ No hamburger menus on desktop.
- ❌ No infinite scroll for findings. Use pagination or "show more".
- ❌ No auto-playing animations on page load.

### Content Anti-Patterns

- ❌ No raw error stack traces shown to users. Sanitize and summarize.
- ❌ No raw evidence IDs (`ev_d0b430fe6ccd2d0f552c`) in the main report view. Use `E1`, `E2`.
- ❌ No English natural language in Chinese report sections. Code symbols stay English.
- ❌ No placeholder text ("Lorem ipsum", "Coming soon") in production UI.

---

## 12. Component Inventory

### Existing Components (keep as-is)

| Component | Location | Notes |
|-----------|----------|-------|
| `Button` | `components/ui/button.tsx` | CVA-based, supports variants |
| `Card` | `components/ui/card.tsx` | Standard card wrapper |
| `Input` | `components/ui/input.tsx` | Form input |
| `EmptyState` | `components/workspace/EmptyState.tsx` | Icon + title + description + action |
| `MarkdownContent` | `components/MarkdownContent.tsx` | react-markdown with rehype-highlight |
| `ReportPanel` | `components/workspace/ReportPanel.tsx` | Report sections with outline nav |
| `ReviewHistoryPanel` | `components/workspace/ReviewHistoryPanel.tsx` | History list with delete |
| `ControlSidebar` | `components/workspace/ControlSidebar.tsx` | Form + status + export + history |
| `WorkspaceShell` | `components/workspace/WorkspaceShell.tsx` | Main layout orchestrator |

### Components to Improve (V3.5.12)

| Component | Improvement |
|-----------|-------------|
| Export button | Fetch + Blob download, no raw JSON navigation |
| Error display | Sanitized messages, provider/network distinction |
| Empty states | Context-specific messages for each tab |
| Status badges | Consistent color + icon system |
| Evidence cards | E1/E2 style with file:line:symbol |
| History panel | Stale review detection and handling |

### Optional React Bits Components (evaluated, not required)

| Component | Dependency | Verdict |
|-----------|------------|---------|
| SpotlightCard | None (0 KB) | **Skip** — mouse-following effects are distracting for a reading tool |
| GradualBlur | None (0 KB) | **Maybe** — useful for scroll fade on findings list, but CSS-only alternative exists |
| AnimatedList | `motion` (~30 KB) | **Skip** — staggered animations delay content visibility |
| Stepper | `motion` (shared) | **Skip** — current progress bar is sufficient |
| DarkVeil | `ogl` (~15 KB) | **Skip** — WebGL background is anti-pattern for this product |

**Recommendation:** Do not add React Bits dependencies. The current component set is sufficient. If scroll fade is desired, implement a 20-line CSS-only `GradualBlur` equivalent using `mask-image` gradient.

---

## 13. Design Token Reference (Quick Copy)

### CSS Custom Properties (Dark Mode)

```css
--background: 222 47% 11%;
--foreground: 210 40% 98%;
--card: 222 42% 13%;
--panel: 222 44% 10%;
--muted: 217 33% 18%;
--muted-foreground: 215 20% 67%;
--primary: 172 66% 50%;
--primary-foreground: 222 47% 9%;
--destructive: 0 73% 62%;
--border: 217 27% 24%;
--success: 158 64% 52%;
--warning: 38 92% 56%;
```

### Tailwind Classes Quick Reference

```
Cards:          bg-card border border-border rounded-xl p-5 shadow-panel
Panels:         bg-panel border border-border rounded-xl p-4
Eyebrow label:  font-mono text-[10px] font-semibold uppercase tracking-[0.16em] text-muted-foreground
Status badge:   inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-semibold
Evidence ref:   font-mono text-xs text-primary cursor-pointer hover:underline
Code inline:    font-mono text-primary bg-muted px-1 py-0.5 rounded text-sm
Error alert:    rounded-xl border border-destructive/35 bg-destructive/5 p-4 text-sm text-destructive
```

---

## References

- Linear DESIGN.md — surface depth system, dark palette, hairline borders
- Warp DESIGN.md — tight information density, terminal aesthetics, restraint
- Cursor DESIGN.md — agent timeline pills, AI workflow visualization
- Source: [awesome-design-md](https://github.com/VoltAgent/awesome-design-md) (MIT License)
