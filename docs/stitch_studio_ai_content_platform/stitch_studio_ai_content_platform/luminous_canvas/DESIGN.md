---
name: Luminous Canvas
colors:
  surface: '#f9f9fa'
  surface-dim: '#d9dadb'
  surface-bright: '#f9f9fa'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#f3f3f4'
  surface-container: '#eeeeef'
  surface-container-high: '#e8e8e9'
  surface-container-highest: '#e2e2e3'
  on-surface: '#1a1c1d'
  on-surface-variant: '#484555'
  inverse-surface: '#2f3132'
  inverse-on-surface: '#f0f1f2'
  outline: '#797587'
  outline-variant: '#c9c4d8'
  surface-tint: '#5d3ae8'
  primary: '#4c21d8'
  on-primary: '#ffffff'
  primary-container: '#6544f0'
  on-primary-container: '#e7e0ff'
  inverse-primary: '#c9bfff'
  secondary: '#575e6e'
  on-secondary: '#ffffff'
  secondary-container: '#d9dff2'
  on-secondary-container: '#5c6373'
  tertiary: '#4b4e57'
  on-tertiary: '#ffffff'
  tertiary-container: '#63666f'
  on-tertiary-container: '#e3e4ef'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#e5deff'
  primary-fixed-dim: '#c9bfff'
  on-primary-fixed: '#1a0063'
  on-primary-fixed-variant: '#4510d1'
  secondary-fixed: '#dce2f5'
  secondary-fixed-dim: '#c0c6d9'
  on-secondary-fixed: '#151c29'
  on-secondary-fixed-variant: '#404756'
  tertiary-fixed: '#e0e2ed'
  tertiary-fixed-dim: '#c4c6d0'
  on-tertiary-fixed: '#181b23'
  on-tertiary-fixed-variant: '#44474f'
  background: '#f9f9fa'
  on-background: '#1a1c1d'
  surface-variant: '#e2e2e3'
typography:
  display-lg:
    fontFamily: Inter
    fontSize: 40px
    fontWeight: '600'
    lineHeight: 48px
    letterSpacing: -0.025em
  display-lg-mobile:
    fontFamily: Inter
    fontSize: 32px
    fontWeight: '600'
    lineHeight: 40px
    letterSpacing: -0.02em
  headline-lg:
    fontFamily: Inter
    fontSize: 28px
    fontWeight: '600'
    lineHeight: 36px
    letterSpacing: -0.02em
  headline-lg-mobile:
    fontFamily: Inter
    fontSize: 24px
    fontWeight: '600'
    lineHeight: 32px
    letterSpacing: -0.015em
  headline-md:
    fontFamily: Inter
    fontSize: 20px
    fontWeight: '600'
    lineHeight: 28px
    letterSpacing: -0.015em
  title-md:
    fontFamily: Inter
    fontSize: 16px
    fontWeight: '600'
    lineHeight: 24px
    letterSpacing: -0.01em
  title-sm:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '600'
    lineHeight: 20px
    letterSpacing: -0.005em
  body-lg:
    fontFamily: Inter
    fontSize: 16px
    fontWeight: '400'
    lineHeight: 24px
    letterSpacing: 0em
  body-md:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 20px
    letterSpacing: 0em
  body-sm:
    fontFamily: Inter
    fontSize: 13px
    fontWeight: '400'
    lineHeight: 18px
    letterSpacing: 0em
  mono-metric:
    fontFamily: JetBrains Mono
    fontSize: 13px
    fontWeight: '500'
    lineHeight: 16px
    letterSpacing: -0.01em
  mono-code:
    fontFamily: JetBrains Mono
    fontSize: 12px
    fontWeight: '400'
    lineHeight: 18px
    letterSpacing: 0em
  label-sm:
    fontFamily: JetBrains Mono
    fontSize: 11px
    fontWeight: '500'
    lineHeight: 14px
    letterSpacing: 0.04em
rounded:
  sm: 0.25rem
  DEFAULT: 0.5rem
  md: 0.75rem
  lg: 1rem
  xl: 1.5rem
  full: 9999px
spacing:
  gutter: 1rem
  gutter-desktop: 1.5rem
  margin: 1rem
  margin-desktop: 2rem
  space-xs: 0.25rem
  space-sm: 0.5rem
  space-md: 1rem
  space-lg: 1.5rem
  space-xl: 2.5rem
---

## Brand & Style

This design system embodies an ultra-refined, generative AI creative studio rendered in an immaculate light mode. The visual language blends computational precision with minimalist elegance—avoiding visual noise to let synthetic media, prompt workflows, and spatial canvases take focus.

The core aesthetic combines:
- **Pristine Precision:** Surgical layout structures, razor-sharp geometric alignment, and deliberate typographic pacing inspired by high-end design tooling and technical workspaces.
- **Controlled Warmth & Vibrancy:** A deep electric violet primary accent that signals creative intelligence and forward momentum, set against ultra-clean, desaturated cool-neutral architecture.
- **Architectural Layering:** Subtle planar elevations with crisp, low-contrast boundary lines rather than heavy simulated shadows, framing canvas tools and node graphs with absolute clarity.

The target audience spans creative directors, prompt engineers, AI artists, and digital product designers demanding uncompromised ergonomics and fast scanning during high-density generation sessions.

## Colors

The palette establishes hierarchy through fine luminance differentials, balancing crisp light surfaces with assertive, legible darks:

- **Canvas & Base Surfaces:**
  - `Canvas / App Background`: `#FAFAFB` (Subtly cool off-white baseline that eliminates display glare)
  - `Surface / Container`: `#FFFFFF` (Pristine structural background for panels, inspectors, and toolbars)
  - `Raised / Container High`: `#F3F4F7` (Interactive surfaces, active states, card headers, and drop zones)
  - `Borders & Separators`: `#E3E5EB` (Crisp 1px boundary line providing structural delineation without visual weight)

- **Brand & Accent:**
  - `Primary / Accent`: `#6544F0` (Electric violet representing computational creation, generative triggers, and primary focus)
  - `Primary Hover / Focus`: `#5434DF` (Deepened tone for interactive confidence)
  - `Primary Muted / Tint`: `#F0EDFD` (Subtle selection washes, badge backdrops, and active toggle rails)

- **Typography & Content Hierarchy:**
  - `Text Primary`: `#14161C` (Near-black with a hint of slate for uncompromised contrast on light surfaces)
  - `Text Secondary / Muted`: `#5B6272` (Balanced neutral for secondary labels, parameters, and metadata)
  - `Text Tertiary / Disabled`: `#8E95A5` (Inactive options, empty states, and subtle keyboard hints)

- **Feedback Accents:**
  - `Success`: `#12A573` (Generation completed, asset synced)
  - `Warning`: `#E08518` (High GPU load, context limit warning)
  - `Critical`: `#E53E3E` (Synthesizer error, generation failed)

## Typography

The typographic strategy relies on a dual-engine hierarchy:

1. **Inter for Structural Typography:** Provides clean, neutral, highly legible headlines and operational interfaces. Feature settings `tnum` (tabular numbers) and `cv05` / `cv08` are activated for crisp numerical workflows and refined letterforms.
2. **JetBrains Mono for Computational Metrics:** Deployed strictly for AI telemetry, parameter tags (e.g., `cfg_scale: 7.5`, `seed: 884192`, `denoise: 0.35`), prompt weightings, runtime statistics, and model version identifiers.

All display titles employ negative tracking to ensure compact presence, while micro metadata labels leverage uppercase monospaced characters with positive tracking to optimize scannability at small sizes.

## Layout & Spacing

The layout is built upon an 8-point rhythmic grid with a 4-point micro-step scale:

- **Grid Architecture:**
  - **Desktop (>= 1280px):** 12-column dynamic modular grid or 3-pane workbench layout (Sidebar: 280px fixed, Canvas: flexible min 640px, Inspector: 360px fixed) with `gutter-desktop` (24px) and `margin-desktop` (32px).
  - **Tablet (768px – 1279px):** 8-column flexible grid with collapsible collateral drawers; `gutter` (16px) and `margin` (24px).
  - **Mobile (< 768px):** 4-column flow layout; toolbars dock to bottom sheet overlays; `gutter` (16px) and `margin` (16px).

- **Spacing Rules:**
  - Micro-gaps between related parameters and icons use `space-xs` (4px).
  - Component-internal padding and compact input clusters use `space-sm` (8px).
  - Intra-card element separation and stack gaps use `space-md` (16px).
  - Card-to-card gaps and inspector module splits use `space-lg` (24px).
  - Section demarcations and canvas borders use `space-xl` (40px).

## Elevation & Depth

Visual depth is achieved through structural layering and fine-line borders rather than heavy simulated shadows, keeping UI rendering crisp and focused on visual content:

- **Level 0 (Base Canvas):** `#FAFAFB` background. Flat, continuous work plane.
- **Level 1 (Panels & Canvases):** `#FFFFFF` with a 1px solid `#E3E5EB` boundary. Used for dock panels, sidebars, and static studio surfaces.
- **Level 2 (Cards & Inspectors):** `#FFFFFF` fill with an inset or outer 1px `#E3E5EB` perimeter line and a micro ambient shadow: `0 1px 3px rgba(20, 22, 28, 0.04), 0 1px 2px rgba(20, 22, 28, 0.02)`. Used for generation tiles, prompt inputs, and node properties.
- **Level 3 (Floating Overlays & Context Menus):** `#FFFFFF` with a 1px `#E3E5EB` border and an ambient depth drop: `0 10px 24px -4px rgba(20, 22, 28, 0.08), 0 4px 8px -2px rgba(20, 22, 28, 0.03)`.
- **Level 4 (Modals & Focus Engines):** `#FFFFFF` with `0 24px 48px -12px rgba(20, 22, 28, 0.14)`. Backdrop is tinted with `#14161C` at 20% opacity with a subtle `backdrop-blur(4px)` to sustain environmental context without clutter.

## Shapes

The shape system strictly balances mechanical precision with touch-friendly refinement:

- **Cards & Primary Modules:** 10px to 12px corner radii (`rounded-lg`), providing a contemporary tool aesthetic that softens grid intersections.
- **Interactive Controls (Buttons, Form Inputs, Dropdowns):** 8px corner radii (`rounded`), ensuring snug alignment with structural containers.
- **Micro Badges, Model Chips, and Parameters:** 6px corner radii to maintain rectangular legibility without severe sharp edges.
- **Avatar & Status Dots:** Fully circular (`rounded-full`) to contrast against rectangular data cards.

## Components

### Buttons
- **Primary:** Solid `#6544F0` fill, `#FFFFFF` text, 8px border radius. Height 40px (desktop), padding 0 16px. Hover shifts to `#5434DF`; active state scales slightly down to 98.5%.
- **Secondary / Outline:** Background `#FFFFFF`, 1px border `#E3E5EB`, `#14161C` text. Hover transitions to `#F3F4F7` background with `#D0D4DD` border.
- **Ghost:** Transparent background, `#5B6272` text. Hover transitions to `#F3F4F7` and `#14161C` text.
- **Icon / Tool Action:** 36x36px square with 8px radius. Neutral `#5B6272` icon color; active tool selection takes `#F0EDFD` background with `#6544F0` icon color and 1px `#6544F0` outline.

### Cards & Media Tiles
- **Standard Card:** Background `#FFFFFF`, border 1px solid `#E3E5EB`, border radius 12px, padding 16px.
- **Raised / Preview Tile:** Background `#F3F4F7` perimeter housing generative media; inner media radius 8px; footer row displaying monospace metrics (`mono-metric`) with `#5B6272` muted metadata.
- **Active / Selected State:** Outer border shifts to 1.5px solid `#6544F0` with a subtle 2px ring offset in `#F0EDFD`.

### Inputs & Prompt Engines
- **Prompt TextArea:** `#FFFFFF` background, 1px `#E3E5EB` border, 10px border radius, text `#14161C`, placeholder `#8E95A5`. Focus state brings 1.5px `#6544F0` border and soft focus ring (`0 0 0 3px rgba(101, 68, 240, 0.12)`).
- **Parameter Steppers & Sliders:** Sleek 4px track in `#E3E5EB`; active fill in `#6544F0`; thumb is 16px circle `#FFFFFF` with 1px `#E3E5EB` border and subtle drop shadow. Accompanying values rendered in `JetBrains Mono` (`label-sm`).

### Chips & Parameter Tags
- **Filter & Model Chips:** Height 28px, border radius 6px, background `#F3F4F7`, text `#5B6272` in `mono-metric` font. Selected state uses `#F0EDFD` fill, `#6544F0` text, and 1px border `#6544F0`.

### Lists & Tree Views
- **Tree Rows:** 32px height, 6px hover radius, `#14161C` text. Hover state `#F3F4F7`. Selected item uses `#F0EDFD` background with a 3px vertical accent strip in `#6544F0` on the leading border.

### Checkboxes & Switches
- **Checkbox:** 18x18px, 4px border radius, 1.5px border `#D0D4DD`. Checked state fills `#6544F0` with white vector checkmark.
- **Toggle Switch:** 36x20px capsule track in `#E3E5EB` (checked: `#6544F0`); 16px white circular thumb with 2px margin.

### Studio Specific: Generation History Bar
- Horizontal dock of thumbnail strips wrapped in `#FFFFFF` container with 1px `#E3E5EB` top border. Real-time generation progress uses an animated 2px linear gradient bar flowing from `#6544F0` to `#A795FA`.