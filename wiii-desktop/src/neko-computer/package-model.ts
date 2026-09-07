import type {
  ComputerDoctor,
  ComputerEnvironment,
  ComputerPackageStatus,
} from "./contracts";

export const COMPUTER_CORE_PACKAGE_ID = "web-computer-core";

export function coreComputerPackage(
  doctor: ComputerDoctor | null | undefined,
): ComputerPackageStatus | null {
  return doctor?.packages?.find((item) => item.packageId === COMPUTER_CORE_PACKAGE_ID) ?? null;
}

export interface ComputerPackUpdateSummary {
  activeVersion: string;
  targetVersion: string;
}

export function computerPackUpdateSummary(
  environment: ComputerEnvironment | null | undefined,
  corePackage: ComputerPackageStatus | null | undefined,
): ComputerPackUpdateSummary | null {
  if (!environment?.packUpdateAvailable) return null;
  return {
    activeVersion: environment.activePackVersion ?? "gói cũ",
    targetVersion: corePackage?.manifest.version ?? "bản mới",
  };
}

export function formatComputerBytes(bytes: number | null | undefined): string {
  if (bytes == null || !Number.isFinite(bytes) || bytes < 0) return "Đang tính dung lượng";
  const units = ["B", "KB", "MB", "GB", "TB"] as const;
  let value = bytes;
  let unit = 0;
  while (value >= 1024 && unit < units.length - 1) {
    value /= 1024;
    unit += 1;
  }
  const maximumFractionDigits = unit >= 3 ? 1 : 0;
  return `${new Intl.NumberFormat("vi-VN", { maximumFractionDigits }).format(value)} ${units[unit]}`;
}
