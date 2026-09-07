import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { NekoProviderSessionRecord } from "@/neko/contracts";
import type { NekoSession } from "@/neko-chill/stores/neko-session-store";
import { ProviderSessionCatalogPanel } from "@/neko-chill/components/ProviderSessionCatalogPanel";

function providers(count: number): NekoProviderSessionRecord[] {
  return Array.from({ length: count }, (_, index) => ({
    providerId: index % 2 === 0 ? "codex" : "claude",
    nativeSessionId: `session-${index}`,
    title: `Session ${index}`,
    workspacePath: "E:\\Projects\\Wiii",
    createdAt: null,
    updatedAt: new Date(Date.UTC(2026, 7, 24, 0, 0, index)).toISOString(),
    model: null,
    state: "saved",
    canResume: index % 2 === 0,
  }));
}

function managed(): NekoSession {
  return {
    id: "managed-1",
    agentId: "codex",
    agentName: "Codex",
    title: "Managed auth work",
    createdAt: 1,
    updatedAt: Date.UTC(2026, 7, 25),
    workspace: { path: "e:\\projects\\wiii\\", name: "Wiii" },
    launchProfile: null,
    backendSessionId: null,
    controls: [],
    commands: [],
    pendingControlId: null,
    lastActivityAt: 1,
    status: "idle",
    messages: [{ id: "user-1", role: "user", text: "fix authentication" }],
    events: [],
    eventHighWaterMark: 0,
    runtime: null,
    pendingPermission: null,
    resolvingPermissionId: null,
    cancelPending: false,
    closePending: false,
    deletePending: false,
  };
}

function panel(overrides: Partial<React.ComponentProps<typeof ProviderSessionCatalogPanel>> = {}) {
  const props: React.ComponentProps<typeof ProviderSessionCatalogPanel> = {
    managedSessions: [],
    providerSessions: [],
    providerCatalogs: [],
    providerNames: new Map([["codex", "Codex"], ["claude", "Claude Code"]]),
    discoveryLoading: false,
    onRefresh: vi.fn(),
    onOpenManaged: vi.fn(),
    onImportProvider: vi.fn(),
    ...overrides,
  };
  return { ...render(<ProviderSessionCatalogPanel {...props} />), props };
}

describe("unified session catalog panel", () => {
  it("previews six deterministic rows instead of rendering a 300-session wall", () => {
    panel({ providerSessions: providers(300) });

    expect(screen.getByText("Session 299")).toBeTruthy();
    expect(screen.getByText("Session 294")).toBeTruthy();
    expect(screen.queryByText("Session 293")).toBeNull();
    expect(screen.getByRole("button", { name: "Xem tất cả 300 phiên" })).toBeTruthy();
    expect(screen.getByText("300 phiên · 0 do Wiii quản lý")).toBeTruthy();
  });

  it("flattens hierarchy while searching across provider and Wiii metadata", () => {
    panel({ managedSessions: [managed()], providerSessions: providers(300) });

    fireEvent.change(screen.getByRole("searchbox", { name: "Tìm mọi phiên" }), {
      target: { value: "fix authentication" },
    });

    expect(screen.getByTestId("flat-session-search")).toBeTruthy();
    expect(screen.getByText("Managed auth work")).toBeTruthy();
    expect(screen.queryByText("Session 299")).toBeNull();
  });

  it("uses harness counts as project-local filters and keeps harness as an alternate projection", () => {
    panel({ managedSessions: [managed()], providerSessions: [providers(2)[1]!] });

    expect(screen.getByRole("button", { name: "Tất cả 2" })).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Claude Code 1" }));
    expect(screen.getByText("Session 1")).toBeTruthy();
    expect(screen.queryByText("Managed auth work")).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: "Harness" }));
    expect(screen.getAllByText("Codex").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Claude Code").length).toBeGreaterThan(0);
  });

  it("opens Wiii-managed sessions without pretending read-only external sessions can resume", () => {
    const onOpenManaged = vi.fn();
    panel({
      managedSessions: [managed()],
      providerSessions: [providers(2)[1]!],
      onOpenManaged,
    });

    fireEvent.click(screen.getByRole("button", { name: "Mở phiên Managed auth work" }));
    expect(onOpenManaged).toHaveBeenCalledWith("managed-1");
    expect(screen.getByText("Ngoài Wiii")).toBeTruthy();
  });
});
