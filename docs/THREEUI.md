# ThreeUI landing integration

- Official package: `@designcodeio/threeui@1.2.0`; React peer `>=18 <20` matches React 19. Required Three peer is installed and locked. GalleryHeading itself uses Canvas 2D.
- Official source: https://threeui.com/source-code/gallery-heading.json
- Reference: https://threeui.com/text-animation/gallery-heading/vertical-loop
- Canonical `gallery-heading.html` SHA-256, verified against both the registered manifest and the published package: `8e42d2d5b4971bfc4d3c485112c3c51909e20a61b8842bc0dcd8db3ffe2d253a`.
- MIT, copyright 2026 Meng To. The retained notice is in `docs/licenses/threeui-MIT.txt`. This scene has no registered external assets or licensed media to copy; it uses procedural Canvas artwork and system sans typography.
- Uses the exact public `@designcodeio/threeui` import, mapped by Next modularizeImports to the documented official `@designcodeio/threeui/components/GalleryHeading` entry point. The root barrel imports unrelated Vite asset modules incompatible with Next's asset pipeline; the official component subpath avoids that graph without modifying the authored implementation.
- The user explicitly approved the official component's internal `srcDoc` iframe after inspection. It is the package's own sandboxed `allow-scripts` Canvas document, not an embedded ThreeUI website or a video.
- Configuration: vertical-loop, dark, didone, weight 400, headlineSize 1.25, hue 0, saturation 1, brightness 1. No authored source or interactions were changed.
- Client-only, lazy-loaded on `/`. Reduced motion loads no animation. Stop, hidden tabs and route departure unmount the iframe, releasing its document/RAF and library listeners. Replay creates a fresh scene. No scroll interception or new animation library.
- `/overview` is the existing workspace. Workspace links always remain inside it; visiting other pages never forces the landing animation. `/overview?experience=tour` opens the separate existing Pipeline Tour and consumes that parameter.

## Local API

FastAPI runs on `127.0.0.1:8000`; Next proxies `/api/*` to `API_URL` (default `http://127.0.0.1:8000`). Configure API_URL before `npm run build`, since rewrites are built into the production application. Run FastAPI and Next as separate processes; installing dependencies does not start the API. Verify `/api/health` through the frontend. The landing reports health failures and the workspace retains actionable API errors.

The recovery machine's previous temporary checkout was removed and the original working directory had cloud-only dependencies/build assets. A downloaded local checkout and runtime were restored; archived workspace databases were left untouched. Do not put the active build/venv in a temporary directory or a cloud-evictable parent dependency tree. RAGLAB_DATA_DIR selects an existing persistent data folder; changing it does not migrate previous data automatically.

Workspace entry uses a shared near-white mask: 780ms desktop, 380ms mobile, immediate for reduced motion and Skip Intro. Routing occurs only while the mask covers the page; internal dashboard links never invoke it.

The official animation rests until hover/touch and eases back down when the pointer leaves; this authored behavior is retained. Browser movement checks use real pointer/touch input and compare actual Canvas frames. It is not forced into a replacement autoplay loop.
