/**
 * Rive avatar module barrel export — Sprint 141.
 */
export { RiveWiiiAvatar } from "./RiveWiiiAvatar";
export type { RiveWiiiAvatarProps } from "./RiveWiiiAvatar";
export { useRiveEmotions } from "./useRiveEmotions";
export {
  RIVE_FILE_PATH,
  MAIN_STATE_MACHINE,
  RIVE_INPUTS,
  RIVE_TRIGGERS,
  RIVE_BOOLEANS,
  PARAM_RANGES,
  STATE_ENERGY,
  HAND_GESTURES,
} from "./rive-config";
export {
  mapToRive,
  mapFromRive,
  faceExpressionToRive,
  resolveAvatarState,
  lerpRiveInputs,
} from "./rive-adapter";
