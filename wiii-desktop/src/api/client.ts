/**
 * HTTP client for Wiii backend API.
 *
 * Uses @tauri-apps/plugin-http to bypass CORS when running in Tauri.
 * Falls back to native browser fetch when running in a regular browser.
 */

const isTauri =
  typeof window !== "undefined" && "__TAURI_INTERNALS__" in window;

/** Default request timeout in milliseconds (60 seconds) */
const DEFAULT_TIMEOUT_MS = 60_000;

/**
 * Adaptive fetch — uses Tauri plugin-http in Tauri, native fetch in browser.
 * Sprint 85: Adds configurable timeout via AbortController.
 */
async function adaptiveFetch(
  url: string,
  init?: RequestInit,
  timeoutMs: number = DEFAULT_TIMEOUT_MS
): Promise<Response> {
  // Sprint 85: Timeout via AbortController — prevents hung requests
  const controller = new AbortController();
  const existingSignal = init?.signal;

  // Merge with any existing abort signal
  if (existingSignal) {
    existingSignal.addEventListener("abort", () => controller.abort(existingSignal.reason));
  }
  const timeoutId = setTimeout(() => controller.abort("Request timeout"), timeoutMs);

  try {
    const fetchInit: RequestInit = { ...init, signal: controller.signal };
    if (isTauri) {
      try {
        const { fetch: tauriFetch } = await import("@tauri-apps/plugin-http");
        return await tauriFetch(url, fetchInit);
      } catch {
        // Fallback if plugin fails to load
        return await fetch(url, fetchInit);
      }
    }
    return await fetch(url, fetchInit);
  } finally {
    clearTimeout(timeoutId);
  }
}

export class WiiiClient {
  private baseUrl: string;
  private headers: Record<string, string>;

  constructor(baseUrl: string, headers: Record<string, string> = {}) {
    this.baseUrl = baseUrl.replace(/\/+$/, ""); // Remove trailing slash
    this.headers = headers;
  }

  /** Update authentication headers */
  setHeaders(headers: Record<string, string>) {
    this.headers = headers;
  }

  /** Update base URL */
  setBaseUrl(url: string) {
    this.baseUrl = url.replace(/\/+$/, "");
  }

  /** GET request */
  async get<T>(
    path: string,
    params?: Record<string, string>
  ): Promise<T> {
    const url = new URL(path, this.baseUrl);
    if (params) {
      Object.entries(params).forEach(([k, v]) =>
        url.searchParams.set(k, v)
      );
    }

    const response = await adaptiveFetch(url.toString(), {
      method: "GET",
      headers: this.headers,
    });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }

    return (await response.json()) as T;
  }

  /** POST request (JSON) */
  async post<T>(path: string, body: unknown): Promise<T> {
    const url = new URL(path, this.baseUrl).toString();

    const response = await adaptiveFetch(url, {
      method: "POST",
      headers: {
        ...this.headers,
        "Content-Type": "application/json",
      },
      body: JSON.stringify(body),
    });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }

    return (await response.json()) as T;
  }

  /** GET request with extra headers (e.g. X-Session-ID) */
  async getWithHeaders<T>(
    path: string,
    extraHeaders: Record<string, string>,
    params?: Record<string, string>
  ): Promise<T> {
    const url = new URL(path, this.baseUrl);
    if (params) {
      Object.entries(params).forEach(([k, v]) =>
        url.searchParams.set(k, v)
      );
    }

    const response = await adaptiveFetch(url.toString(), {
      method: "GET",
      headers: { ...this.headers, ...extraHeaders },
    });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }

    return (await response.json()) as T;
  }

  /** POST request with extra headers (e.g. X-Session-ID) */
  async postWithHeaders<T>(
    path: string,
    body: unknown,
    extraHeaders: Record<string, string>
  ): Promise<T> {
    const url = new URL(path, this.baseUrl).toString();

    const response = await adaptiveFetch(url, {
      method: "POST",
      headers: {
        ...this.headers,
        "Content-Type": "application/json",
        ...extraHeaders,
      },
      body: JSON.stringify(body),
    });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }

    return (await response.json()) as T;
  }

  /** DELETE request */
  async delete<T>(path: string): Promise<T> {
    const url = new URL(path, this.baseUrl).toString();

    const response = await adaptiveFetch(url, {
      method: "DELETE",
      headers: this.headers,
    });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }

    return (await response.json()) as T;
  }

  /** PUT request (JSON) */
  async put<T>(path: string, body: unknown): Promise<T> {
    const url = new URL(path, this.baseUrl).toString();

    const response = await adaptiveFetch(url, {
      method: "PUT",
      headers: {
        ...this.headers,
        "Content-Type": "application/json",
      },
      body: JSON.stringify(body),
    });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }

    return (await response.json()) as T;
  }

  /** PATCH request (JSON) */
  async patch<T>(path: string, body: unknown): Promise<T> {
    const url = new URL(path, this.baseUrl).toString();

    const response = await adaptiveFetch(url, {
      method: "PATCH",
      headers: {
        ...this.headers,
        "Content-Type": "application/json",
      },
      body: JSON.stringify(body),
    });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }

    return (await response.json()) as T;
  }

  /**
   * POST request that returns a ReadableStream for SSE streaming.
   * Used for /chat/stream/v3 endpoint.
   */
  async postStream(
    path: string,
    body: unknown,
    extraHeaders?: Record<string, string>,
  ): Promise<ReadableStream<Uint8Array>> {
    const url = new URL(path, this.baseUrl).toString();

    const response = await adaptiveFetch(url, {
      method: "POST",
      headers: {
        ...this.headers,
        "Content-Type": "application/json",
        ...extraHeaders,
      },
      body: JSON.stringify(body),
    });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }

    if (!response.body) {
      throw new Error("No response body for streaming");
    }

    return response.body;
  }

  /** Get the full URL for a path */
  getUrl(path: string): string {
    return new URL(path, this.baseUrl).toString();
  }
}

/** Singleton client instance */
let _client: WiiiClient | null = null;

export function getClient(): WiiiClient {
  if (!_client) {
    _client = new WiiiClient("http://localhost:8000");
  }
  return _client;
}

export function initClient(baseUrl: string, headers: Record<string, string>) {
  _client = new WiiiClient(baseUrl, headers);
  return _client;
}
