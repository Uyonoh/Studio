---
name: Studio
colors:
  surface: '#121317'
  surface-dim: '#121317'
  surface-bright: '#38393e'
  surface-container-lowest: '#0d0e12'
  surface-container-low: '#1a1b20'
  surface-container: '#1f1f24'
  surface-container-high: '#292a2e'
  surface-container-highest: '#343439'
  on-surface: '#e3e2e8'
  on-surface-variant: '#c9c4d8'
  inverse-surface: '#e3e2e8'
  inverse-on-surface: '#2f3035'
  outline: '#938ea1'
  outline-variant: '#484555'
  surface-tint: '#cabeff'
  primary: '#cabeff'
  on-primary: '#31009a'
  primary-container: '#947dff'
  on-primary-container: '#2a0088'
  inverse-primary: '#603ce2'
  secondary: '#c4c6d1'
  on-secondary: '#2d3039'
  secondary-container: '#444750'
  on-secondary-container: '#b3b5bf'
  tertiary: '#c3c6d4'
  on-tertiary: '#2c303b'
  tertiary-container: '#8d909e'
  on-tertiary-container: '#262a34'
  error: '#ffb4ab'
  on-error: '#690005'
  error-container: '#93000a'
  on-error-container: '#ffdad6'
  primary-fixed: '#e6deff'
  primary-fixed-dim: '#cabeff'
  on-primary-fixed: '#1c0062'
  on-primary-fixed-variant: '#4816cb'
  secondary-fixed: '#e0e2ed'
  secondary-fixed-dim: '#c4c6d1'
  on-secondary-fixed: '#181b23'
  on-secondary-fixed-variant: '#444750'
  tertiary-fixed: '#dfe2f1'
  tertiary-fixed-dim: '#c3c6d4'
  on-tertiary-fixed: '#171b26'
  on-tertiary-fixed-variant: '#434652'
  background: '#121317'
  on-background: '#e3e2e8'
  surface-variant: '#343439'
typography:
  headline-xl:
    fontFamily: Inter
    fontSize: 32px
    fontWeight: '600'
    lineHeight: 40px
    letterSpacing: -0.025em
  headline-xl-mobile:
    fontFamily: Inter
    fontSize: 26px
    fontWeight: '600'
    lineHeight: 34px
    letterSpacing: -0.02em
  headline-lg:
    fontFamily: Inter
    fontSize: 22px
    fontWeight: '600'
    lineHeight: 28px
    letterSpacing: -0.02em
  headline-sm:
    fontFamily: Inter
    fontSize: 16px
    fontWeight: '500'
    lineHeight: 24px
    letterSpacing: -0.015em
  body-lg:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 22px
    letterSpacing: -0.01em
  body-md:
    fontFamily: Inter
    fontSize: 13px
    fontWeight: '400'
    lineHeight: 18px
    letterSpacing: -0.005em
  body-sm:
    fontFamily: Inter
    fontSize: 12px
    fontWeight: '400'
    lineHeight: 16px
    letterSpacing: 0em
  code-md:
    fontFamily: JetBrains Mono
    fontSize: 12px
    fontWeight: '500'
    lineHeight: 16px
    letterSpacing: -0.01em
  code-sm:
    fontFamily: JetBrains Mono
    fontSize: 11px
    fontWeight: '400'
    lineHeight: 14px
    letterSpacing: 0em
  label-caps:
    fontFamily: Inter
    fontSize: 10px
    fontWeight: '600'
    lineHeight: 12px
    letterSpacing: 0.06em
rounded:
  sm: 0.125rem
  DEFAULT: 0.25rem
  md: 0.375rem
  lg: 0.5rem
  xl: 0.75rem
  full: 9999px
spacing:
  gutter: 1rem
  gutter-mobile: 0.5rem
  margin: 1.5rem
  margin-mobile: 0.75rem
  space-xs: 0.25rem
  space-sm: 0.5rem
  space-md: 0.75rem
  space-lg: 1rem
  space-xl: 1.5rem
---

## Brand & Style

This design system establishes a high-performance, dark-first workspace tailored for technical creators, digital artists, and AI workflow operators. The aesthetic merges the ruthless efficiency of Linear, the creative precision of Runway, and the architectural restraint of Vercel.

The UI acts as an unobtrusive, precision instrument: disciplined, matte, and monochromatic. It yields stage presence entirely to user-generated generative media (video, imagery, audio waveforms, 3D assets). Visual noise is eliminated; interactions are snap-responsive, tactile, and engineered with micro-feedback.

### Key Tenets
- **Content-Forward Neutrality**: Chrome surfaces remain in low-key, near-black values so that generated assets provide 100% of the canvas chromatic energy.
- **Surgical Hierarchy**: Information density is balanced using strictly calibrated font tracking, line heights, and micro-delimiters rather than heavy blocks or arbitrary fills.
- **Restrained Kinetic Feedback**: Micro-interactions utilize brief cubic-bezier transitions (150ms–200ms `cubic-bezier(0.16, 1, 0.3, 1)`), avoiding gratuitous spring animations in favor of mechanical precision.

## Colors

The palette relies on deep cold-slate neutrals, precise structural borders, and a singular luminous violet accent reserved strictly for focal interactions.

### Palette Architecture
- **Base Canvas (`#0B0C10`)**: The deepest canvas level; hosts peripheral gutters, global navigation backdrops, and viewports.
- **Surface (`#14161C`)**: Workstation panels, inspect panels, toolbars, and inactive track regions.
- **Surface Raised (`#1B1E26`)**: Component containers, dropdown menus, segmented button groups, and hover states for surface items.
- **Borders & Dividers (`#262A35`)**: 1px structural boundaries defining the modular grid.
- **Accent Violet (`#7C5CFF`) & Accent Hover (`#8F75FF`)**: Strictly restricted to critical paths—primary generation triggers, selection bounding boxes, active toggle nodes, and focused inputs. It must never be used decoratively on large surface areas.

### Typography & Status Tokens
- **Text Primary (`#E8EAF0`)**: High contrast, crisp white-slate for active labels, primary headers, and parameters.
- **Text Muted (`#9AA1B2`)**: Neutral mid-tone for secondary metadata, keyboard shortcut badges, inactive labels, and hints.
- **Success (`#34D399`)**: Asset rendered, export finished, seed match confirmed.
- **Info (`#4DA3FF`)**: Active inference job running, queue position, frame interpolate status.
- **Warning (`#FBBF24`)**: Token limit threshold, upscale resolution ceiling warning, compute throttling.
- **Danger (`#F87171`)**: Generation failure, CUDA out-of-memory, destructive purge actions.

## Typography

The typographic engine uses a dual-font structure: **Inter** handles interface navigation, structured forms, and visual hierarchy; **JetBrains Mono** is employed for quantitative telemetry, runtime values, prompt variables, aspect ratios, seeds, and execution durations.

### Implementation Rules
- Apply `font-feature-settings: "cv02", "cv03", "cv04", "cv11"` to Inter for clinical, modernist glyph shapes.
- All numbers within tables, inspect properties, timeline scrubbers, and sliders must be set in `JetBrains Mono` with `font-variant-numeric: tabular-nums` to prevent layout shift during active generation loops.
- `label-caps` is used exclusively for panel category headers, input section labels, and modal grouping headers (always rendered in uppercase with muted text `#9AA1B2`).

## Layout & Spacing

The layout is built around a compact 4px mathematical grid system (`0.25rem` baseline increments). The viewport functions as an integrated IDE workspace composed of collapsible dock panels, contextual inspectors, and a dynamic infinite/fluid canvas.

### Layout Model
- **Studio Workspace (Desktop)**: 3-column layout consisting of a fixed 64px icon utility rail, a collapsible 280px generation/parameter configuration drawer, a flexible central canvas/timeline viewport, and an optional 320px contextual inspector rail.
- **Gutters & Dividers**: Structural divisions use zero-gap boundaries with a single `1px solid #262A35` separator to maximize usable screen real estate.
- **Reflow Architecture**:
  - *Desktop (>1280px)*: Multi-panel simultaneous views (Canvas + Prompt Deck + Inspect Panel).
  - *Tablet (768px–1279px)*: Canvas remains primary; parameters and inspector collapse into floating slide-over drawers with backdrop scrim.
  - *Mobile (<768px)*: Single active viewport mode; bottom tab navigation handles transitions between Generation Deck, Canvas Output, and Project Settings.

## Elevation & Depth

This system intentionally rejects diffuse ambient drop-shadows and Skeuomorphic gradients. Depth is established through structural layering and razor-sharp border contrasts.

### Layer Tiers
- **Layer 0 (Canvas Base - `#0B0C10`)**: The deepest layer. Contains the asset workspace, node graph matrix, and empty canvas space.
- **Layer 1 (Docked Surface - `#14161C`)**: Pinned toolbars, left parameter panels, bottom timelines. Outlined by `1px solid #262A35`.
- **Layer 2 (Floating Surface - `#1B1E26`)**: Context menus, dropdown pickers, popovers, and prompt autocomplete hints. Borders shift to `#262A35` with an ultra-subtle directional border light: a `1px` inner top border highlight of `rgba(255, 255, 255, 0.05)`.
- **Layer 3 (Overlay / Modal - `#1B1E26`)**: Model select dialogs, export screens, render queue manager. Accompanied by a `rgba(11, 12, 16, 0.8)` blurred backdrop scrim (`backdrop-filter: blur(8px)`) and a subtle boundary shadow: `0 16px 32px -8px rgba(0, 0, 0, 0.6)`.

Focus states reject fuzzy glows; they leverage a crisp, unblurred `0 0 0 1px #7C5CFF` or an offset dual ring (`box-shadow: 0 0 0 2px #0B0C10, 0 0 0 4px #7C5CFF`).

## Shapes

The geometry balances compact engineering utility with contemporary polish. Corner radiuses scale directly with the component's hierarchical footprint:

- **8px (Base Radius)**: Inputs, prompt text fields, segmented chips, parameter scrubbers, pill badges, and dropdown triggers.
- **12px (Container Radius)**: Media generation preview tiles, node cards, canvas tool pods, and inspector panels.
- **16px (Modal / Overlay Radius)**: Primary dialog windows, floating drawer panels, and full-screen export sheets.

No fully rounded circular pills are permitted for action buttons, preserving an architectural and professional workstation feel.

## Components

### Buttons
- **Primary CTA**: Background `#7C5CFF`, text `#FFFFFF`, border `none`, radius `8px`, height `36px`, padding `0 14px`. Hover state shifts to `#8F75FF`. Active state scales to `0.98`. Focus ring: `2px #7C5CFF` with `2px` offset.
- **Secondary**: Background `#1B1E26`, border `1px solid #262A35`, text `#E8EAF0`. Hover state triggers background `#262A35` and text `#FFFFFF`.
- **Ghost / Icon Action**: Background `transparent`, border `none`, text `#9AA1B2`. Hover shifts text to `#E8EAF0` and background to `rgba(255, 255, 255, 0.04)`.

### Inputs & Text Areas
- **Prompt Field**: Multi-line auto-expanding field. Background `#14161C`, border `1px solid #262A35`, text `#E8EAF0`, radius `8px`. Placeholder color `#9AA1B2` at 50% opacity. Focus state applies border color `#7C5CFF` without external fuzzy glow.
- **Numeric Scrubbers / Sliders**: Inline numerical control pairing a draggable scrub track with a tabular `JetBrains Mono` value box. Track color `#262A35`, active fill `#7C5CFF`.

### Parameter Chips & Badges
- **Model / Sampler Selectors**: Height `28px`, background `#14161C`, border `1px solid #262A35`, radius `8px`. Active/selected chip features border `#7C5CFF` and a 10% `#7C5CFF` alpha background tint with white text.
- **Telemetry Badges (Aspect Ratios, CFG, Seeds)**: Height `20px`, padding `2px 6px`, font `JetBrains Mono` at `11px`, background `#1B1E26`, text `#9AA1B2`, border `1px solid #262A35`.

### Checkboxes & Switch Toggles
- **Checkbox**: `16px x 16px`, radius `4px`, border `1px solid #262A35`, background `#14161C`. Checked state: background `#7C5CFF`, border `#7C5CFF`, checkmark icon white 1.5px stroke.
- **Switch Toggle**: Track width `36px`, height `20px`, radius `10px`, background `#262A35`. Thumb diameter `16px` white. Active checked state: track turns `#7C5CFF`.

### Media Cards & Asset Tiles
- **Preview Frame**: Background `#14161C`, border `1px solid #262A35`, radius `12px`, overflow `hidden`.
- **Hover Overlay**: Dark gradient overlay (`rgba(11, 12, 16, 0.75)`) revealing quick actions (upscale, variant, branch, download) using 28px ghost icon buttons.
- **Progressive Render State**: Unfinished renders display a skeleton pulse in `#1B1E26` layered with a progress track (`#7C5CFF`) and a micro tabular percentage badge in `JetBrains Mono`.

### Lists & Tree Views
- Row items possess a fixed height of `32px`, radius `6px`, text `#9AA1B2`. Hovering sets background to `#1B1E26` and text to `#E8EAF0`. Active selected tree node sets background to `rgba(124, 92, 255, 0.12)`, text to `#E8EAF0`, with an indicator bar (`2px` wide, `#7C5CFF`) pinned to the left edge.