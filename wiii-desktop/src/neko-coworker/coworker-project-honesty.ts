import type { NekoProject } from "@/workbench/contracts";

export type CoworkerSummaryCardCopy = {
  value: string;
  detail: string;
  /** True when Wiii has projects but coworker machine has no grant/active mount yet. */
  needsCoworkerGrant: boolean;
};

function primaryWiiiRoot(projects: NekoProject[]): { name: string; path: string } | null {
  const project = projects[0];
  if (!project) return null;
  const root = project.roots[0];
  if (!root) return { name: project.name, path: "" };
  return { name: project.name, path: root.path };
}

/**
 * Honest summary for "Project đang mở" — never claim "Không có" when Wiii
 * already has an open workspace/session folder. Coworker grants stay separate
 * from Chill (no auto-grant).
 */
export function coworkerOpenProjectCard(args: {
  environmentProjectName?: string | null;
  environmentProjectPath?: string | null;
  wiiiProjects: NekoProject[];
}): CoworkerSummaryCardCopy {
  const mountedName = args.environmentProjectName?.trim() || null;
  const mountedPath = args.environmentProjectPath?.trim() || null;
  if (mountedName || mountedPath) {
    return {
      value: mountedName ?? mountedPath ?? "Đang mở",
      detail: mountedPath ?? "Đã gắn vào máy Neko",
      needsCoworkerGrant: false,
    };
  }

  const primary = primaryWiiiRoot(args.wiiiProjects);
  if (primary) {
    return {
      value: primary.name,
      detail: primary.path
        ? `${primary.path} · chưa gắn vào máy Neko`
        : "Project Wiii · chưa gắn vào máy Neko",
      needsCoworkerGrant: true,
    };
  }

  return {
    value: "Không có",
    detail: "Neko chưa nhận thư mục nào",
    needsCoworkerGrant: false,
  };
}

/**
 * Honest summary for "Quyền Project" — distinguish Chill workspace presence
 * from coworker workstation grants.
 */
export function coworkerGrantsCard(args: {
  grantCount: number;
  wiiiProjectCount: number;
}): CoworkerSummaryCardCopy {
  const grants = Math.max(0, args.grantCount);
  if (grants > 0) {
    return {
      value: `${grants} Project`,
      detail: "Chỉ thư mục được cấp quyền mới được gắn vào",
      needsCoworkerGrant: false,
    };
  }

  if (args.wiiiProjectCount > 0) {
    return {
      value: "0 quyền máy Neko",
      detail: `Có ${args.wiiiProjectCount} Project Wiii — cấp quyền bên dưới để gắn (khác phiên Chill)`,
      needsCoworkerGrant: true,
    };
  }

  return {
    value: "0 Project",
    detail: "Chỉ thư mục được cấp quyền mới được gắn vào",
    needsCoworkerGrant: false,
  };
}

export const COWORKER_CHILL_SEPARATION_VI =
  "Phiên Chill và máy Đồng nghiệp là hai bề mặt khác nhau. Project đang mở trong Wiii chưa đồng nghĩa Neko đã được cấp quyền trên máy làm việc — hãy Cấp quyền bên dưới nếu muốn gắn cùng thư mục. Wiii không tự cấp quyền.";
