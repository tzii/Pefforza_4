# Pefforza: design and research

## Direction

An experimental game object presented with the discipline of an editorial design studio: near-black charcoal, cobalt, acidic yellow, and a warm red. Large Space Grotesk headings establish scale; italic serif accents add a human voice; Space Mono labels reference the engineering behind the game. The custom product still is the main visual asset. The playable board and explanatory diagrams are functional interface geometry.

The narrative follows the actual system: perceive a board, evaluate a position, communicate a move. Visitors can jump directly from the header or hero to the working game. The site presents the Python project accurately and explicitly labels the browser opponent and illustrative diagrams.

## Research references

Research combined the repository README, architecture and rules with primary motion documentation, indexed posts on X, and Chinese-language design work on ZCOOL. Weibo and Xiaohongshu searches did not yield accessible references of comparable usefulness; no claim is made to have viewed inaccessible social videos.

- [GSAP on X: Raine Architects](https://x.com/greensock/status/1967619880087416952): indexed description of immersive navigation and 3D scrollable content. A useful lead toward spatial, object-led storytelling. The post itself was not accessible beyond its search excerpt.
- [Raine Architects on Awwwards](https://www.awwwards.com/sites/raine-architects): an independently accessible reference for the project identified on X. Inspired the idea of a clear sequence through an experience, without copying layouts or assets.
- [Rupesh Kumar: GTA VI scroll recreation](https://x.com/rupesh30_21/status/1949086734270050696): indexed post discussing split-text reveals, parallax, pinned scenes, and scroll-linked sequences. Used as a technique reference, not a claim of direct video inspection.
- [ZCOOL: Spline 3D interaction for websites](https://www.zcool.com.cn/article/ZMTYxOTkzMg%3D%3D.html): Chinese-language creator workflow combining an interactive product object and a web layout. Informed the dimensional game-object treatment. The generated image is original, not a Spline asset or copied model.
- [ZCOOL: 2.5D web design](https://www.zcool.com.cn/work/ZNjcyMTYxNjg%3D.html): dimensional brand composition and a digital/physical relationship. No images reproduced.
- [ZCOOL: Muyun visual interaction explorations](https://www.zcool.com.cn/work/ZNjg5MjAyMDQ%3D.html): an industrial visualization reference for calibration marks, diagram overlays, and careful technical labels. Pefforza’s illustration labels avoid fabricated performance statistics.
- [Made With GSAP](https://madewithgsap.com/): the creators’ collection of scroll, drag, and pointer interaction work. Informed timing, restrained interaction feedback, and continuous visual rhythm.
- [GSAP ScrollTrigger documentation](https://gsap.com/docs/v3/Plugins/ScrollTrigger/): authoritative implementation reference for pinning, scrub, responsive measurements, and refresh behavior.
- [GSAP React integration](https://gsap.com/resources/React/): authoritative guidance for scoped animations and lifecycle cleanup.

## Motion implementation

- Hero: staged text entrance and a product-image reveal, followed by scroll-linked image drift.
- Diagonal band: continuously moving type, independently pausable with the global motion control.
- Introduction: gradual entrance and a rotating typographic asterisk.
- Anatomy: a pinned horizontal progression on desktop; native vertical content on mobile and in reduced-motion mode.
- Perception: an illustrative scanner pass over a valid sample board.
- Intelligence: an animated search-tree path.
- Interaction: an AR arrow and an illustrative voice waveform.
- Playground: physical disc drops, column focus/hover affordances, and winning-disc emphasis.
- Footer: large-type reveal and an asterisk rotation as it enters the viewport.

Native page scrolling is preserved. All animation effects are disposed on cleanup. The global motion button disables continuous CSS animation and GSAP timelines; no animation is required to understand or play the game.

## Image asset

- Tool: built-in `image_gen`; one request, no variants.
- Output: `public/images/pefforza-hero.webp`, 1536 × 1024; compressed from the generated PNG for a roughly 100 KB payload.
- Inspected: full seven-column, six-row board, stacked discs, dark text-safe negative space, blue/red/yellow palette, no text or watermarks.
- Prompt:

> Use case: product-mockup — right-hand website hero. Nearly black pure charcoal (#090a09) studio background blending into a dark webpage. A Connect Four game: deep cobalt-blue machined acrylic board with a true grid of seven columns and six rows of circular holes, entire board visible, floating at subtle 3/4 perspective rotated 12 degrees; red-orange and luminous chartreuse-yellow discs with thick beveled edges arranged as a plausible partially played game stacked from the bottom up; a few red/yellow discs gently suspended above and around. Landscape 1536x1024; huge negative space on the left 45% for text, subject fills the right 55%. High-end CGI product still life; sleek editorial industrial toy design meets experimental Swiss art direction; tactile satin materials; dramatic focused softbox lighting, fine rim light, crisp physical shadows. Vibrant acid chartreuse/cobalt/red-orange contrast. No text, logos, watermarks, or interface; no pink/purple neon; no sci-fi clutter.
