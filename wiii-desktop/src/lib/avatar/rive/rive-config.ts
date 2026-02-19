/**
 * Rive Avatar Configuration — Sprint 141: Rive Integration.
 *
 * Defines the contract between the React emotion engine and the Rive state machine.
 * All state machine input names and value ranges are defined here.
 *
 * The .riv file MUST define a state machine named MAIN_STATE_MACHINE
 * with inputs matching the names and ranges below.
 */

// ── Rive file path ──────────────────────────────────────────────────
export const RIVE_FILE_PATH = "/animations/wiii-avatar.riv";

// ── State machine name ──────────────────────────────────────────────
export const MAIN_STATE_MACHINE = "main";

// ── Number inputs (continuous 0–100 unless noted) ───────────────────

/** Facial expression number inputs — mapped from FaceExpression */
export const RIVE_INPUTS = {
  // Eyes
  eyeOpenness: "eye_openness",       // 0=closed, 50=normal, 100=wide
  pupilSize: "pupil_size",           // 0=tiny, 50=normal, 100=dilated
  gazeX: "gaze_x",                   // 0=far left, 50=center, 100=far right
  gazeY: "gaze_y",                   // 0=far up, 50=center, 100=far down
  eyeShape: "eye_shape",             // 0=normal ellipse, 100=happy ^_^ arc

  // Mouth
  mouthCurve: "mouth_curve",         // 0=frown, 50=neutral, 100=smile
  mouthOpenness: "mouth_openness",   // 0=closed, 100=wide open
  mouthWidth: "mouth_width",         // 0=narrow, 50=normal, 100=wide
  mouthShape: "mouth_shape",         // 0=default, 25=cat-omega, 50=dot, 75=wavy

  // Brows
  browRaise: "brow_raise",           // 0=lowered, 50=neutral, 100=raised
  browTilt: "brow_tilt",             // 0=inner furrow, 50=flat, 100=outer raise

  // Cheeks & body
  blush: "blush",                    // 0=none, 100=full red
  energy: "energy",                  // 0=sleepy/calm, 100=bouncy/energetic

  // Hands
  handGesture: "hand_gesture",       // 0=rest, 20=wave, 40=point, 60=cover_mouth, 80=raised, 100=clap
} as const;

/** Trigger inputs — one-shot animations */
export const RIVE_TRIGGERS = {
  surprise: "trig_surprise",         // Startle reaction
  nod: "trig_nod",                   // Agreement nod
  shake: "trig_shake",               // Disagreement head shake
  bounce: "trig_bounce",             // Happy bounce
  wave: "trig_wave",                 // Hand wave greeting
  blink: "trig_blink",              // Force a blink
} as const;

/** Boolean inputs — toggle states */
export const RIVE_BOOLEANS = {
  isSpeaking: "is_speaking",         // Enable mouth oscillation
  isBlinking: "is_blinking",         // Currently in blink
} as const;

// ── Mapping ranges ──────────────────────────────────────────────────

/**
 * Maps FaceExpression param ranges to Rive 0–100 range.
 * Formula: riveValue = (faceValue - srcMin) / (srcMax - srcMin) * 100
 */
export interface RangeMapping {
  srcMin: number;
  srcMax: number;
  riveMin: number;
  riveMax: number;
}

export const PARAM_RANGES: Record<string, RangeMapping> = {
  eyeOpenness:  { srcMin: 0.3,  srcMax: 1.5,  riveMin: 0, riveMax: 100 },
  pupilSize:    { srcMin: 0.5,  srcMax: 1.5,  riveMin: 0, riveMax: 100 },
  gazeX:        { srcMin: -1,   srcMax: 1,    riveMin: 0, riveMax: 100 },
  gazeY:        { srcMin: -1,   srcMax: 1,    riveMin: 0, riveMax: 100 },
  eyeShape:     { srcMin: 0,    srcMax: 1,    riveMin: 0, riveMax: 100 },
  mouthCurve:   { srcMin: -1,   srcMax: 1,    riveMin: 0, riveMax: 100 },
  mouthOpenness:{ srcMin: 0,    srcMax: 1,    riveMin: 0, riveMax: 100 },
  mouthWidth:   { srcMin: 0.5,  srcMax: 1.5,  riveMin: 0, riveMax: 100 },
  mouthShape:   { srcMin: 0,    srcMax: 3,    riveMin: 0, riveMax: 100 },
  browRaise:    { srcMin: -1,   srcMax: 1,    riveMin: 0, riveMax: 100 },
  browTilt:     { srcMin: -1,   srcMax: 1,    riveMin: 0, riveMax: 100 },
  blush:        { srcMin: 0,    srcMax: 1,    riveMin: 0, riveMax: 100 },
};

// ── Lifecycle state → energy + expression mapping ───────────────────

/**
 * Default energy levels for each avatar lifecycle state.
 * Energy drives body bounce speed, breathing depth, and particle activity.
 */
export const STATE_ENERGY: Record<string, number> = {
  idle: 30,
  listening: 40,
  thinking: 60,
  speaking: 55,
  complete: 25,
  error: 45,
};

// ── Hand gesture constants ──────────────────────────────────────────

export const HAND_GESTURES = {
  rest: 0,
  wave: 20,
  point: 40,
  coverMouth: 60,
  raised: 80,
  clap: 100,
} as const;
