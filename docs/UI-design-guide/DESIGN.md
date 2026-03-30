# Design System: Editorial Light

## 1. Overview & Creative North Star
**The Creative North Star: "The Digital Curator"**

This design system is a departure from the "utility-first" SaaS aesthetic. It is an editorial-inspired, high-end experience that treats data and interaction as curated content. By utilizing intentional asymmetry, expansive negative space, and deep tonal layering, the system moves away from rigid grid "boxes" and toward a fluid, architectural layout. 

The aesthetic is defined by **Soft Minimalism**. It rejects the industrial feel of heavy borders and shadows in favor of ambient depth and sophisticated typographic hierarchy. Every element is designed to feel "placed" with intention, rather than "snapped" into a template.

---

## 2. Colors
Our palette is rooted in high-chroma neutrals and vibrant accent "jewels." The goal is a workspace that feels clean but energized.

### The Foundation
*   **Background (`#f5f7f9`):** A cool, airy neutral that serves as the canvas.
*   **On-Surface (`#2c2f31`):** A deep charcoal for primary text, ensuring maximum readability without the harshness of pure black.

### The Accents
*   **Primary (`#4647d3`):** An authoritative, vibrant blue used for critical actions.
*   **Secondary (`#8126cf`):** A sophisticated purple for moments of delight or secondary focal points.
*   **Tertiary (`#963776`):** A deep raspberry used sparingly for specialized categorization or status.

### Color Rules for Premium Execution
*   **The "No-Line" Rule:** 1px solid borders for sectioning are strictly prohibited. Boundaries must be defined solely through background shifts (e.g., a `surface-container-low` section sitting on a `surface` background) or vertical whitespace.
*   **The "Glass & Gradient" Rule:** To provide visual "soul," use subtle linear gradients on main CTAs, transitioning from `primary` to `primary-container`. For floating overlays, apply a `surface-container-lowest` color with a 70% opacity and a `24px` backdrop-blur.
*   **Surface Hierarchy:** Use the nested scale to create depth:
    *   **Lowest (`#ffffff`):** For primary interactive cards and modals.
    *   **Low (`#eef1f3`):** For secondary content areas or sidebars.
    *   **Highest (`#d9dde0`):** For active states or deep inset elements.

---

## 3. Typography
We use a dual-typeface system to balance editorial personality with functional precision.

*   **Display & Headlines (Plus Jakarta Sans):** A modern geometric sans with an open, friendly character.
    *   **Display-LG (3.5rem):** Use for hero moments and welcoming the user.
    *   **Headline-SM (1.5rem):** The standard for section headers.
*   **Body & UI (Inter):** A workhorse typeface designed for screen legibility.
    *   **Body-MD (0.875rem):** The primary reading size.
    *   **Label-MD (0.75rem):** For metadata, micro-copy, and small UI labels.

**Editorial Hierarchy:** Always maintain a significant contrast between headline and body sizes. Avoid "middle-ground" weights; use **Bold** for headlines and **Regular** for body to ensure a clear, authoritative information architecture.

---

## 4. Elevation & Depth
Depth in this system is organic, mimicking natural light rather than digital "glow."

*   **The Layering Principle:** Achieve depth by "stacking" tones. Place a `surface-container-lowest` (#ffffff) card atop a `surface-container-low` (#eef1f3) background. This creates a soft, natural lift that is felt rather than seen.
*   **Ambient Shadows:** For floating elements (Modals, Dropdowns), use a `primary` tinted shadow at 6% opacity with a `32px` blur and `16px` Y-offset. This mimics the blue-light refraction found in glass.
*   **The "Ghost Border" Fallback:** If a container requires a border for accessibility, use the `outline-variant` token at **15% opacity**. High-contrast, 100% opaque borders are forbidden.

---

## 5. Components

### Buttons
*   **Primary:** A gradient from `primary` to `primary-container`. Corner radius: `md` (0.75rem). Text: `label-md` in `on-primary` (Bold).
*   **Secondary:** `surface-container-highest` background with `primary` text. No border.
*   **Tertiary:** Transparent background with `primary` text. Hover state utilizes a subtle `surface-container-low` fill.

### Input Fields
*   **Styling:** Large `3.5` spacing scale padding. Background is `surface-container-low`.
*   **Active State:** Transition the background to `surface-container-lowest` and apply a `ghost border` of `primary` at 20% opacity. Forbid the "focus ring" in favor of this subtle tonal shift.

### Cards & Lists
*   **Layout:** Forbid divider lines. Use `6` (2rem) of vertical whitespace or a transition from `surface-container-low` to `surface-container-lowest` to separate items.
*   **Radius:** Cards use the `lg` (1rem) radius to feel approachable and soft.

### Prompt/Search Bars
*   **Style:** A "pill" shape using `full` (9999px) roundedness. Use `surface-container-lowest` with a heavy ambient shadow to make it the focal point of the interface.

---

## 6. Do's and Don'ts

### Do
*   **Do** use asymmetrical margins (e.g., 80px left, 120px right) to create a dynamic, editorial feel.
*   **Do** leverage the `surface-container` tiers to nest content (e.g., a Sidebar in `surface-container-low` containing a search bar in `surface-container-lowest`).
*   **Do** use icons as "jewels"—small, high-contrast elements that guide the eye without overwhelming the text.

### Don't
*   **Don't** use 1px solid dividers. They clutter the UI and break the "curated" aesthetic.
*   **Don't** use pure grey shadows. Always tint shadows with the `primary` or `on-surface` hue to maintain color harmony.
*   **Don't** cram content. If a section feels crowded, double the spacing using the `spacing scale` (e.g., move from `8` to `16`).