# Wiii Avatar — Rive File Specification

## Overview

This document specifies the requirements for `wiii-avatar.riv` — the Rive animation file
that powers Wiii's avatar. Place the exported `.riv` file at:

```
wiii-desktop/public/animations/wiii-avatar.riv
```

## Artboard

- **Name**: `wiii` (or default)
- **Size**: 400 x 400 px
- **Background**: Transparent

## Character Design — Manga Chibi Style

Wiii is a blob-shaped character with a simple, expressive face.
Think: Tamagotchi meets Duolingo owl meets manga chibi.

```
        *  <3                  <- Manga indicators (sparkle, heart, sweatdrop)
     .--------.
    |  O    O  |  <- Big round eyes (sclera + iris + pupil + 2 highlights)
    |          |
    |   //  // |  <- Blush hash marks (3 diagonal lines per cheek)
    |    w     |  <- Mouth (morphs between shapes: w . ~ triangle smile)
    |          |
     '--------'
      .      .     <- Hands = 2 small dots (can animate: wave, point, cover mouth)
       (blob)      <- Soft rounded body, slight wobble
```

### Visual Elements

1. **Body**: Rounded blob shape (NOT a perfect circle — slight organic noise/wobble)
   - Fill: `#f97316` (Wiii orange) — changes with state
   - Subtle breathing animation (scale oscillation)
   - Slight body sway on idle

2. **Eyes** (2x): Large, round, expressive
   - White sclera (ellipse)
   - Colored iris with radial gradient (gold: `#fbbf24` -> `#92400e`)
   - Dark pupil (circle, scales with `pupil_size`)
   - 2 white highlight dots (top-right large, bottom-left small)
   - Eye shape deforms: normal ellipse <-> happy ^_^ arc (driven by `eye_shape`)
   - Eyes follow pointer (built-in Rive pointer tracking)

3. **Eyebrows** (2x): Simple short lines above eyes
   - Move up/down with `brow_raise`
   - Tilt with `brow_tilt` (inner furrow for worry, outer raise for surprise)

4. **Mouth**: Center of face, below nose
   - Morphs between shapes based on `mouth_shape`:
     - 0-25: Default bezier (smile/frown driven by `mouth_curve`)
     - 25-50: Cat omega w (kawaii idle)
     - 50-75: Small dot . (contemplative)
     - 75-100: Wavy ~ (nervous)
   - Opens with `mouth_openness` (jaw drop)
   - Width scales with `mouth_width`

5. **Nose**: Tiny dot (barely visible, just a hint)

6. **Blush**: 2 ellipses below eyes + 3 diagonal hash lines per cheek
   - Opacity driven by `blush` (0=invisible, 100=full pink)
   - Color: `#ff6b9d`

7. **Hands**: 2 small circles at body sides
   - Position/gesture driven by `hand_gesture`:
     - 0 (rest): Sides, slightly down
     - 20 (wave): One hand up, waving animation
     - 40 (point): One hand forward/up (chin rest for thinking)
     - 60 (cover_mouth): Both hands cover mouth (shy/error)
     - 80 (raised): Both hands up (celebration)
     - 100 (clap): Hands together, clapping

8. **Manga Indicators** (overlays, appear/disappear):
   - Sparkles (3 stars around head) — for complete/excited state
   - Heart — for warm mood
   - Sweat drop — for error/worried state
   - Thought bubble — for thinking state
   - Music note — for idle (relaxed)
   - Anger vein mark — for frustration
   - ZZZ — for sleepy state

## State Machine: `main`

### Number Inputs (all 0-100 range)

| Input Name | Default | Description |
|-----------|---------|-------------|
| `eye_openness` | 58 | 0=closed, 50=normal, 100=wide open |
| `pupil_size` | 50 | 0=tiny pinpoint, 50=normal, 100=dilated |
| `gaze_x` | 50 | 0=far left, 50=center, 100=far right |
| `gaze_y` | 50 | 0=far up, 50=center, 100=far down |
| `eye_shape` | 0 | 0=normal ellipse, 100=happy ^_^ arc |
| `mouth_curve` | 58 | 0=deep frown, 50=neutral, 100=big smile |
| `mouth_openness` | 0 | 0=closed, 100=wide open (jaw drop) |
| `mouth_width` | 50 | 0=narrow, 50=normal, 100=wide |
| `mouth_shape` | 0 | 0=default, 25=cat-omega, 50=dot, 75=wavy |
| `brow_raise` | 50 | 0=deeply lowered, 50=neutral, 100=raised high |
| `brow_tilt` | 50 | 0=inner furrow (worry), 50=flat, 100=outer raise |
| `blush` | 0 | 0=invisible, 100=full pink cheeks |
| `energy` | 30 | 0=sleepy/calm, 100=bouncy/fast animations |
| `hand_gesture` | 0 | 0=rest, 20=wave, 40=point, 60=cover, 80=raised, 100=clap |

### Boolean Inputs

| Input Name | Default | Description |
|-----------|---------|-------------|
| `is_speaking` | false | When true, mouth oscillates open/closed automatically |
| `is_blinking` | false | When true, eyes are in blink state |

### Trigger Inputs

| Input Name | Description |
|-----------|-------------|
| `trig_surprise` | Play startle reaction (eyes wide, body jump) |
| `trig_nod` | Play agreement nod (head bobs down then up) |
| `trig_shake` | Play disagreement shake (head shakes side to side) |
| `trig_bounce` | Play happy bounce (body jumps up, squash-stretch) |
| `trig_wave` | Play hand wave greeting animation |
| `trig_blink` | Force a single blink |

### Pointer Tracking

Set up a **Pointer Move** listener on the full artboard with:
- **Action**: Align Target -> control bone for eye gaze
- This makes eyes follow the mouse cursor automatically
- The code also sends `gaze_x`/`gaze_y` as fallback for non-mouse contexts

### Idle Animations (auto-playing loops)

These should run continuously in the background state:
1. **Breathing**: Subtle body scale oscillation (3-4 second cycle)
2. **Blinking**: Natural blink every 3-6 seconds (random interval)
3. **Micro-sway**: Very subtle body rotation (< 2 degrees)

## Blend States

The state machine should use **Blend States** for smooth transitions:

1. **Eye blend**: Blend between normal eyes and ^_^ happy eyes based on `eye_shape`
2. **Mouth blend**: Blend between mouth shapes based on `mouth_shape`
3. **Expression blend**: Blend brow/eye/mouth simultaneously for coherent expressions
4. **Energy blend**: Speed up all idle animations proportional to `energy`

## Color Variants (Optional Phase 2)

For state-specific body colors, use a `body_color` number input (0-100):
- 0-20: Orange (#f97316) — idle/listening/speaking
- 20-40: Green (#22c55e) — complete
- 40-60: Amber (#f59e0b) — error
- 60-80: Gold (#fbbf24) — excited
- 80-100: Purple (#c084fc) — gentle

## Testing Checklist

After creating the .riv file, verify in the Avatar Preview page:

1. [ ] Open http://localhost:1420/?preview=avatar
2. [ ] Switch to "Rive" mode (top-right toggle)
3. [ ] Click each lifecycle state — expression changes visibly
4. [ ] Click each mood — overlay modifies expression
5. [ ] Move mouse over avatar — eyes follow cursor
6. [ ] Click soul presets — face parameters update smoothly
7. [ ] Adjust face sliders — changes reflect in real-time
8. [ ] Auto Demo — cycles through all states/presets smoothly
9. [ ] Verify Rive inputs panel shows correct values

## Resources

- Rive Editor: https://rive.app (free for personal use)
- Community character examples to reference:
  - Interactive Avatar: https://rive.app/community/files/9294-17679-interactive-avatar/
  - Eyes following cursor: https://rive.app/community/files/4786-9652-eyes-following-cursor/
  - Animated emojis: https://rive.app/community/files/1714-4322-rives-animated-emojis/
