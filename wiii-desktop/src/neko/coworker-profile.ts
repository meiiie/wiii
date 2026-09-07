import type { ComputerSeatState } from "./seat-contract";

export interface CoworkerProfile {
  id: string;
  displayName: string;
  disclosure: "ai";
  roleLabel: string;
  workstationLabel: string;
  avatar: "neko_peek";
}

export const DEFAULT_NEKO_COWORKER: Readonly<CoworkerProfile> = Object.freeze({
  id: "wiii-coworker-neko",
  displayName: "Neko",
  disclosure: "ai",
  roleLabel: "Đồng nghiệp AI",
  workstationLabel: "Máy tính công việc",
  avatar: "neko_peek",
});

export const LOCAL_WIII_OPERATOR_ID = "user:wiii-desktop";

export function coworkerWorkstationTitle(profile: CoworkerProfile): string {
  return `${profile.workstationLabel} của ${profile.displayName}`;
}

export function localUserControlsSeat(seatState: ComputerSeatState): boolean {
  return seatState === "user_controlled";
}

export function describeCoworkerSeat(
  profile: CoworkerProfile,
  seatState: ComputerSeatState,
  userOwnsSeat: boolean,
): string {
  if (userOwnsSeat) return `Bạn đang điều khiển máy của ${profile.displayName}`;
  if (seatState === "agent_controlled") {
    return `${profile.displayName} đang làm việc · Bạn đang quan sát`;
  }
  if (seatState === "user_controlled") {
    return "Một phiên người dùng khác đang điều khiển";
  }
  return "Đang quan sát · Chưa có ai điều khiển";
}
