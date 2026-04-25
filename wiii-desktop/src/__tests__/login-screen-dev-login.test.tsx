/**
 * Issue #88: Local dev-login button on LoginScreen.
 *
 * Verifies:
 *   - The button renders only when running on localhost AND backend reports
 *     enable_dev_login=true.
 *   - The button is hidden when the backend probe returns enabled=false.
 *   - Clicking the button POSTs to /auth/dev-login and pipes the response
 *     through loginWithTokens() — same flow Google OAuth uses.
 */
import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { render, screen, waitFor, fireEvent, act } from "@testing-library/react";


// jsdom does not implement matchMedia; the avatar hook reads it on mount.
if (typeof window !== "undefined" && !window.matchMedia) {
  Object.defineProperty(window, "matchMedia", {
    writable: true,
    value: (query: string) => ({
      matches: false,
      media: query,
      onchange: null,
      addListener: () => {},
      removeListener: () => {},
      addEventListener: () => {},
      removeEventListener: () => {},
      dispatchEvent: () => false,
    }),
  });
}

// Stub the avatar before LoginScreen imports it — its real implementation
// pulls in IntersectionObserver / animation hooks that are out of scope
// for this dev-login flow test.
vi.mock("@/components/common/WiiiAvatar", () => ({
  WiiiAvatar: () => null,
}));

import { LoginScreen } from "@/components/auth/LoginScreen";
import { useSettingsStore } from "@/stores/settings-store";
import { useAuthStore } from "@/stores/auth-store";


function _setLocalhostHost() {
  Object.defineProperty(window, "location", {
    configurable: true,
    value: {
      ...window.location,
      hostname: "localhost",
      origin: "http://localhost:1420",
      search: "",
      hash: "",
    },
  });
}


function _resetSettings() {
  useSettingsStore.setState({
    settings: {
      ...useSettingsStore.getState().settings,
      server_url: "http://localhost:8080",
      api_key: "",
      user_id: "",
      user_role: "student",
    },
    isLoaded: true,
  });
}


describe("LoginScreen — dev-login button (Issue #88)", () => {
  beforeEach(() => {
    _setLocalhostHost();
    _resetSettings();
    // Reset auth-store's loginWithTokens spy if previously stubbed.
    useAuthStore.setState({
      isAuthenticated: false,
      user: null,
      tokens: null,
      authMode: "legacy",
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("does not render the dev button when backend reports enabled=false", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string) => {
        if (url.includes("/auth/dev-login/status")) {
          return new Response(JSON.stringify({ enabled: false }), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          });
        }
        return new Response("{}", { status: 200 });
      }),
    );

    await act(async () => {
      render(<LoginScreen />);
    });

    // After the probe resolves, the button must not be in the DOM.
    await waitFor(() => {
      expect(screen.queryByTestId("dev-login-button")).toBeNull();
    });
  });

  it("renders the dev button when backend reports enabled=true", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string) => {
        if (url.includes("/auth/dev-login/status")) {
          return new Response(JSON.stringify({ enabled: true }), {
            status: 200,
          });
        }
        return new Response("{}", { status: 200 });
      }),
    );

    await act(async () => {
      render(<LoginScreen />);
    });

    await waitFor(() => {
      expect(screen.getByTestId("dev-login-button")).toBeTruthy();
    });
    // Sanity: the badge + Vietnamese label are present
    expect(screen.getByText("DEV")).toBeTruthy();
    expect(screen.getByText(/Đăng nhập nhanh/)).toBeTruthy();
  });

  it("clicking the button POSTs to /auth/dev-login and stores tokens", async () => {
    const tokenPayload = {
      access_token: "ACCESS",
      refresh_token: "REFRESH",
      expires_in: 1800,
      organization_id: "default",
      user: {
        id: "dev-user-1",
        email: "dev@localhost",
        name: "Dev User",
        avatar_url: null,
        role: "admin",
        legacy_role: "admin",
        platform_role: "platform_admin",
        role_source: "platform",
        active_organization_id: "default",
      },
    };

    let postCalled = false;
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string, init?: RequestInit) => {
        if (url.includes("/auth/dev-login/status")) {
          return new Response(JSON.stringify({ enabled: true }), {
            status: 200,
          });
        }
        if (
          url.endsWith("/api/v1/auth/dev-login") &&
          init?.method === "POST"
        ) {
          postCalled = true;
          return new Response(JSON.stringify(tokenPayload), { status: 200 });
        }
        return new Response("{}", { status: 200 });
      }),
    );

    const loginSpy = vi.fn(async () => {});
    useAuthStore.setState({ loginWithTokens: loginSpy } as any);

    await act(async () => {
      render(<LoginScreen />);
    });

    await waitFor(() => {
      expect(screen.getByTestId("dev-login-button")).toBeTruthy();
    });

    await act(async () => {
      fireEvent.click(screen.getByTestId("dev-login-button"));
    });

    await waitFor(() => {
      expect(postCalled).toBe(true);
      expect(loginSpy).toHaveBeenCalledTimes(1);
      const [accessTok, refreshTok, expiresIn, user] = loginSpy.mock.calls[0];
      expect(accessTok).toBe("ACCESS");
      expect(refreshTok).toBe("REFRESH");
      expect(expiresIn).toBe(1800);
      // buildAuthUserFromPayload normalises user_id→id; the AuthUser carries
      // the canonical id field plus the legacy user_id field.
      expect(user.id).toBe("dev-user-1");
    });
  });
});
