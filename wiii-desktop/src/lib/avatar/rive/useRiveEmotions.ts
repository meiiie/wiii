/**
 * useRiveEmotions — Sprint 141: React hook connecting emotion engine to Rive.
 *
 * Manages the bridge between WiiiAvatarProps (state, mood, soulEmotion)
 * and the Rive state machine inputs. Handles:
 * - Smooth interpolation between expression states (60fps)
 * - Speaking mouth oscillation
 * - Idle micro-expressions (random gaze shifts, blinks)
 * - Pointer tracking normalization
 */
import { useRef, useEffect, useCallback } from "react";
import type { Rive, StateMachineInput } from "@rive-app/react-webgl2";
import type { AvatarState } from "../types";
import type { MoodType } from "../mood-theme";
import type { SoulEmotionData } from "../types";
import { resolveAvatarState, lerpRiveInputs } from "./rive-adapter";
import { RIVE_INPUTS, RIVE_TRIGGERS, RIVE_BOOLEANS, MAIN_STATE_MACHINE } from "./rive-config";

/** Interpolation speed per frame (higher = snappier transitions) */
const LERP_SPEED = 0.1;

/** Speaking mouth oscillation amplitude (Rive 0-100 scale) */
const SPEAK_AMPLITUDE = 25;
/** Speaking mouth oscillation frequency (Hz) */
const SPEAK_FREQ = 4.5;

/** Idle gaze drift interval (ms) */
const IDLE_GAZE_INTERVAL = 3000;
/** Idle gaze drift range (Rive 0-100, centered at 50) */
const IDLE_GAZE_RANGE = 12;

interface UseRiveEmotionsOptions {
  state: AvatarState;
  mood: MoodType;
  soulEmotion: SoulEmotionData | null;
  rive: Rive | null;
}

/**
 * Drives Rive state machine inputs from the Wiii emotion engine.
 * Call this hook with the current avatar state — it handles all animation.
 */
export function useRiveEmotions({
  state,
  mood,
  soulEmotion,
  rive,
}: UseRiveEmotionsOptions): void {
  // Refs for animation loop state
  const currentInputsRef = useRef<Record<string, number>>({});
  const targetInputsRef = useRef<Record<string, number>>({});
  const rafIdRef = useRef<number>(0);
  const prevStateRef = useRef<AvatarState>(state);
  const startTimeRef = useRef<number>(performance.now());
  const idleGazeTimerRef = useRef<number>(0);
  const idleGazeTargetRef = useRef({ x: 50, y: 50 });

  // Cache input accessors for performance
  const inputCacheRef = useRef<Map<string, StateMachineInput>>(new Map());

  /** Get or cache a state machine input by name */
  const getInput = useCallback(
    (name: string): StateMachineInput | undefined => {
      if (!rive) return undefined;
      const cached = inputCacheRef.current.get(name);
      if (cached) return cached;

      const inputs = rive.stateMachineInputs(MAIN_STATE_MACHINE);
      if (!inputs) return undefined;

      const input = inputs.find((i) => i.name === name);
      if (input) {
        inputCacheRef.current.set(name, input);
      }
      return input;
    },
    [rive],
  );

  /** Set a number input value */
  const setNumber = useCallback(
    (name: string, value: number) => {
      const input = getInput(name);
      if (input && "value" in input) {
        input.value = value;
      }
    },
    [getInput],
  );

  /** Fire a trigger input */
  const fireTrigger = useCallback(
    (name: string) => {
      const input = getInput(name);
      if (input && "fire" in input) {
        (input as { fire: () => void }).fire();
      }
    },
    [getInput],
  );

  /** Set a boolean input */
  const setBoolean = useCallback(
    (name: string, value: boolean) => {
      const input = getInput(name);
      if (input && "value" in input) {
        input.value = value;
      }
    },
    [getInput],
  );

  // ── Update target whenever state/mood/soul changes ────────────────

  useEffect(() => {
    const resolved = resolveAvatarState(state, mood, soulEmotion);
    targetInputsRef.current = resolved.inputs;

    // Set boolean states
    if (rive) {
      setBoolean(RIVE_BOOLEANS.isSpeaking, resolved.isSpeaking);
    }

    // Fire trigger on state transitions
    if (state !== prevStateRef.current && rive) {
      if (state === "complete") fireTrigger(RIVE_TRIGGERS.bounce);
      if (state === "error") fireTrigger(RIVE_TRIGGERS.shake);
      if (state === "listening") fireTrigger(RIVE_TRIGGERS.nod);
      prevStateRef.current = state;
    }
  }, [state, mood, soulEmotion, rive, setBoolean, fireTrigger]);

  // ── Animation loop ────────────────────────────────────────────────

  useEffect(() => {
    if (!rive) return;

    // Initialize current inputs to target on first frame
    if (Object.keys(currentInputsRef.current).length === 0) {
      const resolved = resolveAvatarState(state, mood, soulEmotion);
      currentInputsRef.current = { ...resolved.inputs };
      targetInputsRef.current = resolved.inputs;

      // Apply immediately (no lerp on init)
      for (const [name, value] of Object.entries(resolved.inputs)) {
        setNumber(name, value);
      }
    }

    startTimeRef.current = performance.now();

    const animate = (now: number) => {
      const elapsed = (now - startTimeRef.current) / 1000;
      const target = targetInputsRef.current;
      const current = currentInputsRef.current;

      // ── Idle micro-expressions: random gaze drift ──
      if (state === "idle" || state === "listening") {
        idleGazeTimerRef.current += 16; // ~60fps
        if (idleGazeTimerRef.current > IDLE_GAZE_INTERVAL) {
          idleGazeTimerRef.current = 0;
          idleGazeTargetRef.current = {
            x: 50 + (Math.random() - 0.5) * IDLE_GAZE_RANGE * 2,
            y: 50 + (Math.random() - 0.5) * IDLE_GAZE_RANGE * 2,
          };
        }
        target[RIVE_INPUTS.gazeX] = idleGazeTargetRef.current.x;
        target[RIVE_INPUTS.gazeY] = idleGazeTargetRef.current.y;
      }

      // ── Speaking mouth oscillation ──
      if (state === "speaking") {
        const baseOpen = target[RIVE_INPUTS.mouthOpenness] ?? 30;
        const oscillation = Math.abs(Math.sin(elapsed * Math.PI * SPEAK_FREQ)) * SPEAK_AMPLITUDE;
        target[RIVE_INPUTS.mouthOpenness] = Math.min(100, baseOpen + oscillation);
      }

      // ── Smooth interpolation ──
      const interpolated = lerpRiveInputs(current, target, LERP_SPEED);
      currentInputsRef.current = interpolated;

      // ── Apply to Rive ──
      for (const [name, value] of Object.entries(interpolated)) {
        setNumber(name, value);
      }

      rafIdRef.current = requestAnimationFrame(animate);
    };

    rafIdRef.current = requestAnimationFrame(animate);

    return () => {
      if (rafIdRef.current) {
        cancelAnimationFrame(rafIdRef.current);
      }
    };
  }, [rive, state, mood, soulEmotion, setNumber]);

  // ── Clear cache on rive change ────────────────────────────────────

  useEffect(() => {
    inputCacheRef.current.clear();
  }, [rive]);
}
