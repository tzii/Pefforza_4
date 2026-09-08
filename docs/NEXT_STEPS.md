# Review of the desktop refresh

Reviewed on 7 September 2026, starting from `81689a2` on
`hoplite/metapontion-2c5eead6`. The local `main` branch was still at `5f56812`.

## Assessment

The refresh is a strong foundation for a student showcase. Separating the game
session, renderer, and cancellable search process makes the interface easier to
test and extend. Undo, explained hints, persistent results, and keyboard play
make experimentation inviting. The README already has a coherent visual identity
and a useful progression from playing to learning; another redesign would add
less value than finishing the release and validating real devices.

The prior verification numbers were reproduced on Windows with Python 3.13.15:
446 tests passed, with 88% package coverage. The initial Windows type check
failed because a multiprocessing pipe was annotated as a Unix connection.
The review fixes the platform-specific annotation and adds a Windows 3.13 CI
lane alongside the existing Linux versions. Remote CI still needs to run.

The Windows renderer also selected Arial Narrow for the requested DejaVu Sans
font. An explicit platform font preference improves the result. The difficulty
button now says that it starts a new round. The README explains how to access
the refresh while it remains off the default branch.

## Software follow-up implemented

- **Six tactical lessons:** reachable positions, exhaustive legal-answer checks,
  all replies checked for the fork, explanations, retry, hint, and next controls.
  Start with `pefforza-gui --lessons` or press L. Lessons do not start an AI worker.
- **Responsive physical assistant:** search runs outside the camera loop. A new
  analysis, resync, quit, or disconnect discards pending work. Synthetic tests
  cover ongoing frames, both player perspectives, and stale-result cancellation.
  The recommendation still refers to the last explicit Space analysis.
- **Visible fallback:** model-load failure reports the actual Medium opponent;
  worker errors show a legal fallback. Spawn-worker tests check reporting across
  successive turns and cancellation. Missing models avoid importing the ML stack.
- **Documentation and screenshots:** the README includes lesson controls and real
  renders of the updated desktop. The local browser preview supports lessons too.

Calibration, HSV detection, and board validation were not modified by this
follow-up. Changes to those areas in the original refresh still need hardware
acceptance. No new runtime dependencies or checkpoints were added.

Software verification on Windows / Python 3.13.15: **475 tests passed, 89%
package coverage**, clean Ruff lint/format and Mypy checks. The actual renderer
was inspected for gameplay and lesson states, and the browser remote was used
to solve a lesson and verify its persistent winning highlight. An explicit UTF-8
read also fixes garbled punctuation in that preview on Windows.

## Browser rendering follow-up · 8 September

The old browser remote encoded a 1040×820 Pygame image about every 66 ms, while
the page waited 80 ms between image fetches. This limited visible motion to less
than 12.5 frames per second and enlarged rasterized text on high-DPI/zoomed views.

The remote now sends coherent board and animation state from the same Python
controller. HTML renders text and controls; SVG renders pieces; the browser's
animation loop interpolates the authoritative drop between state updates. It
does not calculate legal moves, AI choices, or lesson answers. Repeated packets
do not restart an animation, and undo/reset clears it. Tests cover timing,
reduced motion, cancellation, and separation of falling and committed pieces.
This replaces the development `/frame.png` endpoint with `/preview_gui.mjs`.

Run browser motion tests with `node --test tests/test_preview_motion.mjs`.

## Remaining next steps

The subsequent [release verification pass](RELEASE_VERIFICATION.md) fixes the
free-play hint support trap, checks installed wheels outside the checkout, and
extends cancellation sequences. Use that report for current verification and
remaining native/hardware exclusions.

1. **Ship the existing refresh.** Review its public API changes in
   [PROJECT_STATUS.md](PROJECT_STATUS.md), run CI, and merge the reviewed branch.
   Remove the temporary branch-selection note once `main` contains the refresh.
   A normal clone should deliver the screenshot and controls promised by the README.
2. **Finish platform and hardware acceptance.** Exercise native resize, keyboard
   play, quitting during search, undo during animation, and model-load failure.
   On a physical board, check both AI colors, mirrored numbering, occlusion,
   calibration cancellation, win/draw handling, and speech shutdown. Record the
   OS, camera, lighting, result, and any failure. Headless coverage is not a
   substitute for these checks.
3. **Build an honest AI report card.** Compare fixed seeds and alternating sides
   against random, heuristic, and search opponents. Report wins/losses/draws,
   illegal-action fallbacks, and median/p95 move time separately. Label proven
   solver results separately from budget-expired choices. Establish this before
   investing in self-play or replacing the bundled checkpoint.
4. **Measure camera confidence.** Collect cropped, consented board fixtures under
   several lighting conditions. Separate tuning and held-out sets. Track per-cell
   errors, rejected boards, and plausible-but-wrong accepted boards. Tune HSV
   thresholds against those results before attempting automatic calibration.

## Remaining observations

- Very small windows scale all text and hit targets down. Define a supported
  minimum size or introduce a stacked layout before promising phone-sized play.
- Desktop practice currently always starts with the human. Alternating the
  first player would make a useful later experiment, but requires deliberate
  changes to undo semantics and session tests.
- Keep the current visual language. Focus visual work on readable fonts,
  clear disabled/hover/focus states, and visible outcomes of destructive controls.

The remaining items are proposals, not shipped features. This review did not repeat
the previous training run or certify webcam accuracy and audible speech.

## Primary references

- [Pygame event handling](https://www.pygame.org/docs/ref/event.html): process
  the event queue regularly to prevent lost input and unresponsive windows.
- [Gymnasium environment API](https://gymnasium.farama.org/api/env/): reset
  after episode termination; keep step and observation behavior explicit.

Recommendations above combine those contracts with inspection of this repository.
