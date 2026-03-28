# Design System Document

## 1. Overview & Creative North Star
**The Creative North Star: "The Digital Curator"**

This design system moves away from the utility-only look of traditional financial apps, adopting a "Digital Curator" aesthetic. It treats financial data and receipt captures as editorial content. By utilizing high-contrast typography, generous negative space, and a monochromatic palette, we create an experience that feels sophisticated, intentional, and premium. 

The system breaks the "template" look through **intentional asymmetry**—such as off-grid alignment of secondary labels—and **tonal depth**, where elements are separated by soft shifts in luminance rather than rigid lines.

---

## 2. Colors
Our palette is a study in grayscale sophistication, designed to make the user’s content (receipts and merchant logos) the primary focal point.

*   **Surface Hierarchy:** We utilize the `surface-container` tiers to create a physical sense of "nesting." 
    *   **The "No-Line" Rule:** 1px solid borders for sectioning are strictly prohibited. Boundaries must be defined solely through background color shifts. For instance, a `surface-container-low` list item should sit directly on a `surface` background to create a "floating" container effect without an outline.
    *   **The "Glass & Gradient" Rule:** To provide visual "soul," use subtle gradients. Main CTAs should transition from `primary` (#5d5e61) to `primary_dim` (#515255). 
    *   **Signature Textures:** For floating scanning overlays, use Glassmorphism. Apply `surface_container_lowest` at 70% opacity with a 20px backdrop blur to ensure legibility over complex camera feeds.

---

## 3. Typography
The typography system uses a pairing of **Manrope** for structural authority and **Inter** for functional clarity.

*   **Display & Headline (Manrope):** Use `display-lg` and `headline-md` for high-impact numbers (like balance amounts) and section headers. The wider tracking of Manrope gives it a modern, editorial feel.
*   **Title & Body (Inter):** Use `title-md` for merchant names and `body-md` for line items. Inter’s high x-height ensures maximum legibility during the OCR verification process.
*   **Editorial Labeling:** `label-sm` should be used for secondary metadata (dates, tax rates), set in `on_surface_variant` (#586064) to create a clear visual hierarchy through tonal contrast rather than font weight alone.

---

## 4. Elevation & Depth
Depth is achieved through **Tonal Layering** rather than structural shadows.

*   **The Layering Principle:** Stacking follows a logical order:
    1.  Base: `surface` (#f8f9fa)
    2.  Sectioning: `surface-container-low` (#f1f4f6)
    3.  Interactive Card: `surface-container-lowest` (#ffffff)
*   **Ambient Shadows:** Traditional drop shadows are replaced by "Ambient Lifts." When a card needs to float, use a shadow with a 40px blur, 0% spread, and 6% opacity of `on_surface`.
*   **The Ghost Border Fallback:** If accessibility requirements demand a container boundary, use a "Ghost Border": `outline-variant` (#abb3b7) at 15% opacity. Never use 100% opaque borders.

---

## 5. Components

### Buttons
*   **Primary:** A pill-shaped (`rounded-full`) container using the `primary` to `primary_dim` gradient. Text is `on_primary`.
*   **Secondary/Action:** Use `surface_container_high` with `on_surface`. These should feel like "tactile depressions" in the UI.
*   **Scanning Trigger:** A large, floating circular button with a high-diffusion ambient shadow.

### Cards & Lists
*   **Forbid Dividers:** Do not use line dividers between list items. Use a `1.5` (0.375rem) or `2` (0.5rem) vertical spacing gap.
*   **OCR Overlay Card:** A `surface_container_lowest` card with 80% opacity and a `lg` (1rem) corner radius. Use `tertiary` (#006c59) for successful OCR "confidence" indicators.

### Input Fields
*   **Minimalist State:** No bottom line or box. Inputs are defined by a `surface_container_low` background and `sm` (0.25rem) rounding.
*   **Error State:** Transitions to `error_container` background with `on_error_container` text.

### OCR Scanning Overlays
*   **The Viewfinder:** Use a `rounded-xl` frame with a `px` width "Ghost Border" to guide the user. 
*   **Live Tags:** As items are detected, use `surface_container_lowest` chips with `label-sm` text that "pop" into existence with a subtle 200ms ease-out.

---

## 6. Do's and Don'ts

### Do
*   **Do** use asymmetrical margins (e.g., more padding on the left than the right) for title headers to create an editorial layout.
*   **Do** use `tertiary` (#006c59) sparingly—only for "Success" or "Money In" actions to maintain the monochrome prestige.
*   **Do** favor `title-lg` for monetary values, making them the anchor of the page.

### Don'ts
*   **Don't** use pure black (#000000) for text. Always use `on_surface` (#2b3437) to maintain a soft, premium feel.
*   **Don't** use standard Material Design "elevated" shadows. They feel too "app-like" and break the editorial North Star.
*   **Don't** use dividers. If content feels cluttered, increase the spacing scale (from `4` to `6`) rather than adding a line.