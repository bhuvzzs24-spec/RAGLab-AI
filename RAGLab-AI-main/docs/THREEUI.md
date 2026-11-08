# Continuous Halftone opening

## Licensed local customization

GalleryHeading 1.2.0 has no headline-text props. Its vertical-loop strings are hardcoded in the authored Canvas document. This project therefore uses a minimal, explicitly adapted local document, not an overlay over demo wording.

- Upstream registry: https://threeui.com/source-code/gallery-heading.json
- Canonical HTML SHA-256: `8e42d2d5b4971bfc4d3c485112c3c51909e20a61b8842bc0dcd8db3ffe2d253a`
- Registered wrapper SHA-256: `fe9856234253bc3c1a13b3afb84f3d84644dfa6d578e7203bb3e1dd5eced1b75`
- Registered stylesheet SHA-256: `efe4447139f1358dd8e9be68edf6fa46cbefbd1de423a4d6c439ca61d2c8eccf`
- Original npm package and canonical source remain unchanged. `components/gallery/official-halftone.json` retains an unedited snapshot of the official component's SSR-generated vertical-loop `srcDoc`, its own SHA-256, and attribution. This configured document is distinct from the raw canonical HTML above.
- `raglab-document.ts` changes only the two Canvas headline strings, document title, headline ink and background. It draws **RAGLAB AI** and **RETRIEVE. EVALUATE. OPTIMIZE.** inside Canvas. The supporting subtitle is ordinary surrounding interface text.
- Ring geometry, halftone textures, Didone drawing functions, 15.015-second clock, hover/hold easing and stacking remain the authored implementation. The browser regression reverses the allowed substitutions and verifies byte equality with the retained original; actual `fillText` calls verify the rendered wording.
- MIT, copyright (c) 2026 Meng To; full retained notice: `docs/licenses/threeui-MIT.txt`.

The local frame retains `sandbox="allow-scripts"` and the official frame-leave handshake. It is lazy-loaded and its document/listeners are released when stopped, hidden or offscreen. Reduced motion loads no Canvas. Hover or hold touch input activates the authored orbit; it is not replaced with an approximation or an autoplay loop.

## One continuous website

`/` renders the hero followed by exactly one existing `Studio` Overview instance. Natural scrolling reveals an overlapping rounded workspace panel and progressively removes its inset mask. The palette blends near-black plum, eggplant, orchid, warm blush and cream surfaces. The embedded sidebar is sticky on desktop, uses the original mobile drawer, and permits wheel chaining back to the hero.

Enter Workspace and Skip Intro target `#workspace`, focus the real workspace and use native scrolling (immediate for Skip/reduced motion). No wheel or touch interception, pinned scene, duplicate dashboard, replacement API or new animation library is used. Reverse scrolling retains the same Studio instance. `/overview` and existing deep links remain direct; Explore Pipeline opens the existing separate tour.

## API and scope

FastAPI remains on `127.0.0.1:8000`; Next `/api/*` rewrites use API_URL, defaulting to that address. Set API_URL before a production build if changing it. Both services must be running. Health errors and the real workspace Retry connection action remain visible. No backend code, research logic, models, schemas, benchmarks or research documents are changed by this integration.
