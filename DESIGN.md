---
name: BuildMeLeads
description: A service-area dispatch desk for finding weak profile signals and starting relevant outreach.
colors:
  paper-fog: "hsl(84 15% 94%)"
  mineral-ink: "hsl(153 18% 11%)"
  field-paper: "hsl(70 22% 97%)"
  utility-green: "hsl(157 41% 27%)"
  secondary-wash: "hsl(93 10% 86%)"
  muted-paper: "hsl(88 11% 88%)"
  muted-ink: "hsl(150 8% 35%)"
  signal-yellow: "hsl(45 88% 66%)"
  divider: "hsl(103 10% 77%)"
  destructive-red: "hsl(5 68% 49%)"
typography:
  display:
    fontFamily: "Archivo, Segoe UI, sans-serif"
    fontSize: "clamp(3.1rem, 7.2vw, 6rem)"
    fontWeight: 700
    lineHeight: 0.94
    letterSpacing: "-0.04em"
  headline:
    fontFamily: "Archivo, Segoe UI, sans-serif"
    fontSize: "clamp(2.2rem, 4.6vw, 4rem)"
    fontWeight: 700
    lineHeight: 1
    letterSpacing: "-0.04em"
  title:
    fontFamily: "Archivo, Segoe UI, sans-serif"
    fontSize: "1.35rem"
    fontWeight: 700
    letterSpacing: "-0.025em"
  body:
    fontFamily: "Archivo, Segoe UI, sans-serif"
    fontSize: "1rem"
    fontWeight: 400
    lineHeight: 1.65
  label:
    fontFamily: "IBM Plex Mono, monospace"
    fontSize: "0.72rem"
    fontWeight: 500
    letterSpacing: "0.06em"
rounded:
  focus: "0.25rem"
  input: "0.65rem"
  control: "0.7rem"
  object: "0.75rem"
  menu: "0.85rem"
  panel: "1rem"
  board: "1.1rem"
  pill: "100vmax"
spacing:
  content-gutter: "1rem"
  mobile-content-gutter: "0.625rem"
  section-block: "clamp(4.5rem, 8vw, 7.5rem)"
  layout-gap: "clamp(2rem, 7vw, 7rem)"
components:
  button-primary:
    backgroundColor: "{colors.signal-yellow}"
    textColor: "{colors.mineral-ink}"
    rounded: "{rounded.control}"
    padding: "0.7rem 1.1rem"
    height: "3rem"
  button-secondary:
    backgroundColor: "transparent"
    textColor: "{colors.mineral-ink}"
    rounded: "{rounded.control}"
    padding: "0.7rem 1.1rem"
    height: "3rem"
  route-card:
    backgroundColor: "{colors.field-paper}"
    textColor: "{colors.mineral-ink}"
    rounded: "{rounded.object}"
    padding: "1rem"
  field-note:
    backgroundColor: "{colors.utility-green}"
    textColor: "{colors.field-paper}"
    rounded: "{rounded.panel}"
    padding: "clamp(1.5rem, 4vw, 3rem)"
  input:
    backgroundColor: "{colors.paper-fog}"
    textColor: "{colors.mineral-ink}"
    rounded: "{rounded.input}"
    padding: "0.7rem 0.85rem"
    height: "3rem"
---

# Design System: BuildMeLeads

## Overview

**Creative North Star: "The Service-Area Dispatch Desk"**

BuildMeLeads presents lead discovery as calm operational work: a dispatcher observes a weak public signal, qualifies the route, prepares a relevant opener, and deliberately hands it to the next action. Warm field-paper surfaces, route-card geometry, signal bars, precise checklists, and restrained operational labels make the product feel trustworthy and useful rather than futuristic or hype-driven.

The composition is editorial and left-led, with large compact headlines balanced by a concrete workflow object. The site uses cards only for real discrete objects, gives lists and ledgers visible structure, and treats yellow as an active signal rather than decoration. Public marketing remains visibly separate from the private application and never impersonates a live dashboard.

### Committed Direction Contract

- **Thesis:** A service-area dispatch desk turns weak profile signals into a clear reason to reach out; it refuses the generic centered AI-SaaS card stack.
- **Own world:** Mineral ink, paper-fog surfaces, utility green fields, one signal-yellow accent, route cards, field notes, and operational labels.
- **Story:** Agencies understand what is found, why a lead qualifies, how copy is generated, which safeguards apply, and can reserve a pre-launch place.
- **First viewport:** An oversized left-aligned offer and visible waitlist call to action share the frame with a tilted qualification route card.
- **Form:** Code-led service-call dispatch board; ordered direction 3, seed `adf3ebb7`.

**Key Characteristics:**

- Operational, specific, calm, and human.
- Oversized left-aligned type paired with one meaningful workflow object.
- Warm paper texture, mineral ink structure, utility green fields, and sparse signal yellow.
- Evidence-led copy with pre-launch and illustrative states labeled at the point of use.
- Restrained motion that settles or lifts objects without turning the site into a spectacle.

## Colors

The runtime palette is expressed in HSL custom properties; those shipped tokens in the frontmatter are normative for interface work. It creates a warm, low-chroma operational base with one deliberately scarce active accent.

### Primary

- **Utility Green:** Carries trust, qualified states, dispatch actions, field notes, and visible keyboard focus.

### Secondary

- **Signal Yellow:** Marks the primary call to action, weak-signal badges, progress fills, selection, and the dispatch arrow. It is the only active accent.

### Neutral

- **Mineral Ink:** Primary text, structural rules, the dispatch-board shell, and the full-width safeguard field.
- **Paper Fog:** Main public-site canvas and input fill.
- **Field Paper:** Raised route-card, waitlist, popover, and mobile-menu surfaces; also the light foreground on dark or green fields.
- **Secondary Wash and Muted Paper:** Quiet support surfaces and inactive meter tracks.
- **Muted Ink:** Supporting copy, metadata, helper text, and low-emphasis navigation.
- **Divider:** Hairline borders, input strokes, list rules, and section boundaries.
- **Destructive Red:** Error status only.

### Named Rules

**The One Signal Rule.** Signal yellow is the sole active accent and stays rare enough that it always means “notice or act.”

**The Operational Contrast Rule.** Mineral ink, utility green, and field paper must carry the structure; yellow never substitutes for long-form text color or large decorative fields.

**The Texture, Not Gradient Rule.** The canvas may use the shipped faint dot grid and its masked fade as field-paper texture. Do not add gradient text, colored decorative gradients, purple, or generic startup glow.

## Typography

**Display Font:** Archivo (with Segoe UI and sans-serif fallbacks)

**Body Font:** Archivo (with Segoe UI and sans-serif fallbacks)
**Label/Mono Font:** IBM Plex Mono (with monospace fallback)

**Character:** Archivo provides sturdy, compact editorial authority without changing personality between headlines and body copy. IBM Plex Mono is a narrow operational voice reserved for route labels, workflow stages, annotations, and data-like metadata.

### Hierarchy

- **Display** (700, fluid 3.1rem–6rem, 0.94 line-height, tight tracking): Hero and page-level promises, left aligned and held near 15–16 characters per line.
- **Headline** (700, fluid 2.2rem–4rem, 1 line-height, tight tracking): Major section turns and workflow outcomes.
- **Title** (700, 1.35rem, compact tracking): Process steps and discrete object titles.
- **Body** (400, 1rem, 1.65 line-height): Explanations and policy copy. Main reading measures stay near 60–64ch; legal copy may extend to 74ch.
- **Label** (500, 0.72rem, 0.06em tracking, uppercase): Operational metadata only, including “Route card,” “Workflow,” and illustrative-state labels.
- **Navigation and controls** (600–700, 0.88rem–1rem): Short, direct, and never styled as operational mono labels.

### Named Rules

**The Two-Voice Rule.** Archivo speaks to people; IBM Plex Mono labels the dispatch system. Never set paragraphs, major headlines, or promotional claims in mono.

**The Left-Led Rule.** Keep major copy left aligned with compact measures. Avoid long centered text blocks and generic center-stacked hero copy.

## Layout

The public site uses a centered shell capped at 1180px with 1rem side gutters. Sections use generous fluid vertical spacing and recurring fluid gaps, while borders mark sequence more often than containers do. Desktop compositions use asymmetric two-column grids: the hero favors copy over the dispatch board, process notes sit beside a wider ordered list, and proof/waitlist sections balance context with a concrete field object.

The header is sticky at the top with a 4.75rem navigation row and a translucent paper-fog backdrop. On wide screens, the process note and legal navigation may also remain sticky to support scanning. The first viewport must keep the large offer, visible waitlist action, and qualification route card in the same composition when space permits.

At 860px and below, navigation becomes a contained menu, every primary two-column narrative grid collapses to one column, and the dispatch board keeps a restrained tilt while centering inside an inset width that prevents horizontal overflow. Sticky secondary navigation becomes static. Pricing becomes two columns and footer content reflows to two columns. At 560px and below, side gutters tighten to 0.625rem, the primary waitlist action moves directly below the headline, and the dispatch board follows inside the first viewport before the supporting paragraph. The secondary hero pricing action is omitted at that width because pricing remains available in navigation. Forms, pricing, safeguards, and the footer become single column, and display type uses the narrower mobile fluid range. The system must remain usable from 320px upward; allow content to grow vertically rather than compressing controls or copy.

**The Object-or-Rule Rule.** Use a panel only for a discrete object such as a route card, field note, menu, or form. Use spacing and hairline rules for ordinary narrative grouping.

## Elevation & Depth

The system is flat by default and uses a hybrid of tonal layering, hairline borders, and selective ambient shadow. Depth belongs to actionable or handled objects: the yellow primary button, dispatch board, green field note, waitlist form, and open mobile menu. Ordinary sections, lists, ledgers, and secondary buttons remain flat.

### Shadow Vocabulary

- **Primary action** (`0 7px 18px hsl(var(--foreground) / .12)`): Default lift for the yellow call to action; hover increases to `0 10px 24px hsl(var(--foreground) / .16)`.
- **Dispatch object** (`0 30px 70px hsl(var(--foreground) / .2)`): The strongest depth, reserved for the hero’s signature board; a one-pixel offset outline reinforces handled-paper construction.
- **Field object** (`0 22px 50px hsl(var(--foreground) / .15)`): Green field notes that carry qualifying or policy context.
- **Form object** (`0 22px 50px hsl(var(--foreground) / .1)`): Quiet separation for the waitlist form.
- **Mobile menu** (`0 18px 45px hsl(var(--foreground) / .16)`): Temporary navigation elevation only while the menu is open.

### Named Rules

**The Handled Object Rule.** Shadows indicate that an object can be acted on, examined, or temporarily floats above the document; never shadow every section or list item.

## Shapes

Corners are gently rounded, not bubbly. Inputs and controls use compact radii, route cards and actions use slightly broader object corners, and large panels use 1–1.1rem corners. Pills are reserved for statuses and meter tracks; circles are reserved for compact directional action marks. A slight 1.25-degree rotation and offset outline belong only to the desktop dispatch board, where they make the object feel placed on a desk rather than rendered as a generic SaaS card.

Borders are one-pixel structural rules in the divider color or translucent light equivalent. They organize processes, coverage, pricing, safeguards, navigation, and legal content without multiplying containers.

**The Meaningful Silhouette Rule.** A pill means status or progress, a circle means a compact action, and a rounded rectangle means a discrete handled object. Do not spread these silhouettes indiscriminately.

## Components

### Buttons

Buttons feel direct, compact, and workmanlike.

- **Shape:** Gently rounded control with a 3rem minimum height, 0.7rem vertical/1.1rem horizontal padding, and bold Archivo text.
- **Primary:** Signal-yellow fill with mineral-ink text and a small ambient shadow. Use for “Reserve Your Spot” and the next committed action.
- **Hover / Focus / Active:** Hover lifts 2px over 180ms with the standard `cubic-bezier(.16, 1, .3, 1)` easing and gains shadow; active returns to the baseline. Keyboard focus always uses the shared 3px utility-green outline with 4px offset.
- **Secondary:** Transparent fill, divider border, mineral-ink text, and no shadow. Use for comparison or informational routes such as planned pricing.
- **Small:** Navigation-only reduction to a 2.55rem minimum height and tighter padding; all interactive targets must still provide at least a 44px usable hit area.
- **Disabled:** 55% opacity, no lift, no shadow, and a not-allowed cursor; status copy must explain why when the state is not obvious.

### Status Badge and Meters

- **Badge:** A compact signal-yellow pill with mineral-ink, bold 0.72rem text. It names a real or explicitly illustrative weak-signal state.
- **Meter:** A slim muted-paper pill track with a signal-yellow fill. It is supporting qualification context, not an invented performance metric.

### Cards / Containers

- **Route card:** Field-paper surface, 0.75rem corners, divider rules, and 1rem padding inside the mineral-ink dispatch board.
- **Field note:** Utility-green surface, field-paper text, 1rem corners, generous fluid padding, and selective ambient depth.
- **Waitlist form:** Field-paper surface with 1rem corners and softer elevation than the field note.
- **Lists and ledgers:** Use top and bottom rules instead of card wrappers for workflows, safeguards, qualifiers, pricing, and footer navigation.

### Inputs / Fields

- **Style:** Paper-fog fill, divider stroke, 0.65rem corners, 3rem minimum height, and comfortable 0.7rem/0.85rem padding.
- **Focus:** Shared visible utility-green focus outline; placeholder and help text use muted ink.
- **Status:** Success uses utility green and error uses destructive red, both with bold text. The status region remains present and uses polite live announcement behavior.
- **Composition:** Email input and submit action share one row until the 560px breakpoint, then stack to preserve target size and readable entry width.

### Navigation

The sticky header uses a bold mark/name lockup, restrained text links, and one compact primary action. Plain links underline on hover. At 860px the links move into a field-paper menu with a divider border and temporary shadow; the menu control exposes its expanded state and the menu closes after navigation.

### Dispatch Board

The signature object is a mineral-ink service-call board containing a header, one light route card, qualification meters, and a utility-green next-action row finished by a yellow circular arrow. It settles into a slight rotation on desktop and retains a restrained tilt on smaller screens, inset enough to avoid horizontal overflow. It must be labeled as an illustrative preview and must never be presented as a live product screenshot or evidence of current availability.

### Process, Qualifier, and Safeguard Lists

These are ordered operational records rather than card grids. Labels or line icons occupy a narrow first column, copy occupies the second, and rules separate items. Icons are simple stroked SVG marks with meaningful silhouettes; do not introduce sparkle, brain, generic location-pin, or abstract-blob imagery.

### Motion Behavior

The dispatch board uses one 700ms entrance that moves 10px, reduces a small blur, and settles from 2.2 to 1.25 degrees with the standard expressive easing. Buttons use the same easing over 180ms for lift and shadow. No looping, parallax, scroll-jacking, or attention-seeking motion belongs in this system. With reduced motion enabled, smooth scrolling is removed and all animations and transitions resolve effectively instantly; content remains fully visible in its static state.

## Do's and Don'ts

### Do:

- **Do** show the mechanism with route cards, observable signals, ordered workflow, and deliberate next actions.
- **Do** label planned pricing, pre-launch status, illustrative examples, and unavailable functionality exactly where visitors encounter them.
- **Do** keep body measures near 65–75 characters, headings compact, and major copy left aligned.
- **Do** maintain WCAG 2.2 AA contrast, semantic heading order, a working skip link, visible keyboard focus, polite form status announcements, and touch targets of at least 44px.
- **Do** preserve a complete static experience for reduced-motion users and a functional single-column layout from 320px upward.
- **Do** use seller identity, contact routes, and customer responsibility language plainly and accessibly.

### Don't:

- **Don't** build a generic centered AI-SaaS hero, a floating card stack, or a fake dashboard around the product story.
- **Don't** invent testimonials, customer logos, public screenshots, usage metrics, performance claims, availability claims, or proof that the product does not have.
- **Don't** imply checkout, account access, subscription availability, or successful waitlist integration before those capabilities are live and verified.
- **Don't** use purple, gradient text, decorative colored gradients, sparkles, brain icons, generic location pins, abstract startup blobs, or inflated “revolutionary,” “game-changing,” and “10x” language.
- **Don't** turn every section into a card, every label into a pill, every icon into a glyph, or every surface into a shadowed object.
- **Don't** use public scraped contact data as proof of consent or hide outreach responsibility and safeguards in fine print.
