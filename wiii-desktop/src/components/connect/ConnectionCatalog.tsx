import { useEffect, useMemo, useRef, useState } from "react";
import { PlugZap, Search } from "lucide-react";
import type {
  WiiiConnectActivationReadinessResponse,
  WiiiConnectAuthorizationUrlDecision,
  WiiiConnectEffectiveActionInventoryResponse,
  WiiiConnectProviderConnectionListResponse,
  WiiiConnectProviderConnectionRecord,
  WiiiConnectProviderRegistryEntry,
  WiiiConnectSessionStartDecision,
} from "@/api/types/wiii-connect";
import type { WiiiConnectRuntimeSnapshot } from "@/api/types/runtime-diagnostics";
import {
  buildWiiiConnectProviderCallbackUrl,
  createWiiiConnectProviderAuthorizationUrl,
  disconnectWiiiConnectProviderConnection,
  fetchWiiiConnectProviderActivationReadiness,
  fetchWiiiConnectProviderConnections,
  fetchWiiiConnectProviderEffectiveActions,
  startWiiiConnectProviderSession,
} from "@/api/wiii-connect";
import type { CapabilityStatusViewModel } from "@/lib/capability-status";
import { categoryFilters, providerFilters } from "./catalog-data";
import { buildConnectionCatalogCards } from "./catalog-model";
import type {
  CatalogCard,
  CatalogCategory,
  ProviderActionInventoryState,
  ProviderActivationReadinessState,
  ProviderConnectionListState,
  ProviderDisconnectState,
  ProviderFilter,
} from "./connect-types";
import { ConnectionDetailPanel } from "./ConnectionDetailPanel";
import { StatusPill } from "./ConnectStatus";
import {
  defaultActivationActionSlug,
  externalControlLabel,
  locallyDisabledConnection,
  primaryProviderConnection,
  providerConnectionRef,
  responseWithLocallyDisabledConnection,
} from "./provider-readiness";

async function openExternalUrl(url: string): Promise<void> {
  const parsed = new URL(url);
  if (!["http:", "https:"].includes(parsed.protocol)) {
    throw new Error("unsupported_authorization_url");
  }
  try {
    const { open } = await import("@tauri-apps/plugin-shell");
    await open(parsed.toString());
    return;
  } catch {
    window.open(parsed.toString(), "_blank", "noopener,noreferrer");
  }
}

export function ConnectionCatalog({
  snapshot,
  fallbackModel,
  providerRegistry,
  providerRegistryLoaded,
  initialProviderSlug,
  onRuntimeRefresh,
}: {
  snapshot: WiiiConnectRuntimeSnapshot | null;
  fallbackModel: CapabilityStatusViewModel;
  providerRegistry: WiiiConnectProviderRegistryEntry[] | null;
  providerRegistryLoaded: boolean;
  initialProviderSlug?: string | null;
  onRuntimeRefresh?: () => Promise<unknown>;
}) {
  const [provider, setProvider] = useState<ProviderFilter>(
    initialProviderSlug ? "composio" : "wiii_native",
  );
  const [category, setCategory] = useState<CatalogCategory>("all");
  const [query, setQuery] = useState("");
  const [selectedCardId, setSelectedCardId] = useState<string | null>(null);
  const [sessionDecisions, setSessionDecisions] = useState<
    Record<string, WiiiConnectSessionStartDecision>
  >({});
  const [authorizationDecisions, setAuthorizationDecisions] = useState<
    Record<string, WiiiConnectAuthorizationUrlDecision>
  >({});
  const [sessionErrors, setSessionErrors] = useState<Record<string, string>>({});
  const [authorizationErrors, setAuthorizationErrors] = useState<Record<string, string>>({});
  const [sessionLoadingSlug, setSessionLoadingSlug] = useState<string | null>(null);
  const [authorizationLoadingSlug, setAuthorizationLoadingSlug] = useState<string | null>(null);
  const [providerReadinessStates, setProviderReadinessStates] = useState<
    Record<string, ProviderActivationReadinessState>
  >({});
  const [providerActionInventories, setProviderActionInventories] = useState<
    Record<string, ProviderActionInventoryState>
  >({});
  const [providerConnectionLists, setProviderConnectionLists] = useState<
    Record<string, ProviderConnectionListState>
  >({});
  const [disconnectStates, setDisconnectStates] = useState<
    Record<string, ProviderDisconnectState>
  >({});
  const connectionPollTokenRef = useRef(0);
  const appliedFocusRef = useRef<string | null>(null);

  useEffect(() => {
    return () => {
      connectionPollTokenRef.current += 1;
    };
  }, []);

  const cards = useMemo(
    () =>
      buildConnectionCatalogCards(
        snapshot,
        fallbackModel,
        providerRegistry,
        providerConnectionLists,
        providerReadinessStates,
      ),
    [snapshot, fallbackModel, providerRegistry, providerConnectionLists, providerReadinessStates],
  );

  useEffect(() => {
    const target = initialProviderSlug?.trim().toLowerCase();
    if (!target || appliedFocusRef.current === target) return;
    const card = cards.find((candidate) => candidate.providerSlug.toLowerCase() === target);
    if (!card) return;
    appliedFocusRef.current = target;
    setProvider(card.provider);
    setCategory("all");
    setQuery("");
    setSelectedCardId(card.id);
  }, [cards, initialProviderSlug]);

  const normalizedQuery = query.trim().toLowerCase();
  const filteredCards = cards.filter((card) => {
    if (card.provider !== provider) return false;
    if (category !== "all" && card.category !== category) return false;
    if (!normalizedQuery) return true;
    return [card.label, card.description, card.categoryLabel, card.providerLabel]
      .join(" ")
      .toLowerCase()
      .includes(normalizedQuery);
  });

  const selectedCard =
    filteredCards.find((card) => card.id === selectedCardId) ?? filteredCards[0] ?? null;

  const refreshActivationReadiness = async (
    card: CatalogCard,
    connection?: WiiiConnectProviderConnectionRecord | null,
  ): Promise<WiiiConnectActivationReadinessResponse | null> => {
    if (card.provider === "wiii_native" || card.registrySource !== "backend") return null;
    const slug = card.providerSlug;
    const selectedConnection =
      connection ?? primaryProviderConnection(providerConnectionLists[slug]?.response);
    setProviderReadinessStates((current) => ({
      ...current,
      [slug]: {
        ...current[slug],
        loading: true,
        error: undefined,
      },
    }));
    try {
      const response = await fetchWiiiConnectProviderActivationReadiness(slug, {
        actionSlug: defaultActivationActionSlug(card),
        connectionRef: providerConnectionRef(selectedConnection),
        probeDatabase: true,
      });
      setProviderReadinessStates((current) => ({
        ...current,
        [slug]: {
          response,
          loading: false,
          lastFetchedAt: new Date().toISOString(),
        },
      }));
      return response;
    } catch {
      setProviderReadinessStates((current) => ({
        ...current,
        [slug]: {
          ...current[slug],
          loading: false,
          error: "Không thể đọc activation readiness từ backend.",
          lastFetchedAt: new Date().toISOString(),
        },
      }));
      return null;
    }
  };

  const refreshActionInventory = async (
    card: CatalogCard,
    connection?: WiiiConnectProviderConnectionRecord | null,
  ): Promise<WiiiConnectEffectiveActionInventoryResponse | null> => {
    if (card.provider === "wiii_native" || card.registrySource !== "backend") return null;
    const slug = card.providerSlug;
    const selectedConnection =
      connection ?? primaryProviderConnection(providerConnectionLists[slug]?.response);
    setProviderActionInventories((current) => ({
      ...current,
      [slug]: {
        ...current[slug],
        loading: true,
        error: undefined,
      },
    }));
    try {
      const response = await fetchWiiiConnectProviderEffectiveActions(slug, {
        connectionRef: providerConnectionRef(selectedConnection),
        probeDatabase: true,
      });
      setProviderActionInventories((current) => ({
        ...current,
        [slug]: {
          response,
          loading: false,
          lastFetchedAt: new Date().toISOString(),
        },
      }));
      return response;
    } catch {
      setProviderActionInventories((current) => ({
        ...current,
        [slug]: {
          ...current[slug],
          loading: false,
          error: "Không thể đọc effective action inventory từ backend.",
          lastFetchedAt: new Date().toISOString(),
        },
      }));
      return null;
    }
  };

  useEffect(() => {
    if (
      !selectedCard ||
      selectedCard.provider === "wiii_native" ||
      selectedCard.registrySource !== "backend"
    ) {
      return;
    }
    const slug = selectedCard.providerSlug;
    const connectionState = providerConnectionLists[slug];
    if (connectionState?.loading) return;
    if (!connectionState?.response && !connectionState?.error) {
      void refreshProviderConnections(selectedCard).then((response) => {
        if (!response) void refreshActivationReadiness(selectedCard);
      });
      return;
    }
    const readinessState = providerReadinessStates[slug];
    if (!readinessState?.loading && !readinessState?.response && !readinessState?.error) {
      void refreshActivationReadiness(selectedCard);
    }
    const inventoryState = providerActionInventories[slug];
    if (!inventoryState?.loading && !inventoryState?.response && !inventoryState?.error) {
      void refreshActionInventory(selectedCard);
    }
  }, [
    selectedCard?.id,
    selectedCard?.provider,
    selectedCard?.providerSlug,
    selectedCard?.registrySource,
    providerConnectionLists[selectedCard?.providerSlug ?? ""]?.loading,
    providerConnectionLists[selectedCard?.providerSlug ?? ""]?.response,
    providerConnectionLists[selectedCard?.providerSlug ?? ""]?.error,
    providerReadinessStates[selectedCard?.providerSlug ?? ""]?.loading,
    providerReadinessStates[selectedCard?.providerSlug ?? ""]?.response,
    providerReadinessStates[selectedCard?.providerSlug ?? ""]?.error,
    providerActionInventories[selectedCard?.providerSlug ?? ""]?.loading,
    providerActionInventories[selectedCard?.providerSlug ?? ""]?.response,
    providerActionInventories[selectedCard?.providerSlug ?? ""]?.error,
  ]);

  const requestSessionDecision = async (card: CatalogCard) => {
    if (card.provider === "wiii_native" || card.registrySource !== "backend") return;
    const slug = card.providerSlug;
    setSessionLoadingSlug(slug);
    setSessionErrors((current) => {
      const next = { ...current };
      delete next[slug];
      return next;
    });
    try {
      const decision = await startWiiiConnectProviderSession(slug, {
        surface: "desktop",
        requested_scopes: { read: true },
        request_metadata: {
          source: "wiii_connect_page",
          provider: card.provider,
        },
      });
      setSessionDecisions((current) => ({ ...current, [slug]: decision }));
    } catch {
      setSessionErrors((current) => ({
        ...current,
        [slug]: "Không thể kiểm tra kết nối từ backend.",
      }));
    } finally {
      setSessionLoadingSlug((current) => (current === slug ? null : current));
    }
  };

  const refreshProviderConnections = async (
    card: CatalogCard,
  ): Promise<WiiiConnectProviderConnectionListResponse | null> => {
    if (card.provider === "wiii_native" || card.registrySource !== "backend") return null;
    const slug = card.providerSlug;
    setProviderConnectionLists((current) => ({
      ...current,
      [slug]: {
        ...current[slug],
        loading: true,
        error: undefined,
      },
    }));
    try {
      const response = await fetchWiiiConnectProviderConnections(slug, {
        probeDatabase: true,
      });
      setProviderConnectionLists((current) => ({
        ...current,
        [slug]: {
          response,
          loading: false,
          lastFetchedAt: new Date().toISOString(),
        },
      }));
      void refreshActivationReadiness(card, primaryProviderConnection(response));
      void refreshActionInventory(card, primaryProviderConnection(response));
      void onRuntimeRefresh?.();
      return response;
    } catch {
      setProviderConnectionLists((current) => ({
        ...current,
        [slug]: {
          ...current[slug],
          loading: false,
          error: "Không thể đọc trạng thái connection từ backend.",
          lastFetchedAt: new Date().toISOString(),
        },
      }));
      return null;
    }
  };

  const disconnectProviderConnection = async (
    card: CatalogCard,
    connection: WiiiConnectProviderConnectionRecord,
  ) => {
    if (card.provider === "wiii_native" || card.registrySource !== "backend") return;
    const slug = card.providerSlug;
    connectionPollTokenRef.current += 1;
    setDisconnectStates((current) => ({
      ...current,
      [slug]: {
        ...current[slug],
        loading: true,
        error: undefined,
      },
    }));
    try {
      const response = await disconnectWiiiConnectProviderConnection(
        slug,
        providerConnectionRef(connection),
      );
      setDisconnectStates((current) => ({
        ...current,
        [slug]: {
          response,
          loading: false,
          lastUpdatedAt: new Date().toISOString(),
        },
      }));
      if (response.local_disabled) {
        const disabledConnection = locallyDisabledConnection(
          connection,
          "user_disconnect_requested",
        );
        setProviderConnectionLists((current) => ({
          ...current,
          [slug]: {
            ...current[slug],
            response: responseWithLocallyDisabledConnection(
              current[slug]?.response,
              connection,
              "user_disconnect_requested",
            ),
            loading: false,
            lastFetchedAt: new Date().toISOString(),
          },
        }));
        void refreshActivationReadiness(card, disabledConnection);
        void refreshActionInventory(card, disabledConnection);
        void onRuntimeRefresh?.();
      }
    } catch {
      setDisconnectStates((current) => ({
        ...current,
        [slug]: {
          ...current[slug],
          loading: false,
          error: "Không thể ngắt kết nối từ backend.",
          lastUpdatedAt: new Date().toISOString(),
        },
      }));
    }
  };

  const pollProviderConnectionsAfterAuthorization = async (card: CatalogCard) => {
    const pollToken = connectionPollTokenRef.current + 1;
    connectionPollTokenRef.current = pollToken;
    for (let attempt = 0; attempt < 8; attempt += 1) {
      if (attempt > 0) {
        await new Promise((resolve) => window.setTimeout(resolve, 3000));
      }
      if (connectionPollTokenRef.current !== pollToken) return;
      const response = await refreshProviderConnections(card);
      if (connectionPollTokenRef.current !== pollToken) return;
      if (response?.connections.some((connection) => connection.state === "connected" || connection.active)) {
        return;
      }
    }
  };

  const requestAuthorizationUrl = async (card: CatalogCard) => {
    if (card.provider === "wiii_native" || card.registrySource !== "backend") return;
    const slug = card.providerSlug;
    setAuthorizationLoadingSlug(slug);
    setAuthorizationErrors((current) => {
      const next = { ...current };
      delete next[slug];
      return next;
    });
    try {
      const decision = await createWiiiConnectProviderAuthorizationUrl(slug, {
        surface: "desktop",
        redirect_uri: buildWiiiConnectProviderCallbackUrl(slug),
        probe_database: true,
        requested_scopes: { read: true },
        request_metadata: {
          source: "wiii_connect_page",
          provider: card.provider,
        },
      });
      setAuthorizationDecisions((current) => ({ ...current, [slug]: decision }));
      if (decision.status === "ready" && decision.authorization_url) {
        await openExternalUrl(decision.authorization_url);
        void pollProviderConnectionsAfterAuthorization(card);
      }
    } catch {
      setAuthorizationErrors((current) => ({
        ...current,
        [slug]: "Không thể bắt đầu Connect Link từ backend.",
      }));
    } finally {
      setAuthorizationLoadingSlug((current) => (current === slug ? null : current));
    }
  };

  return (
    <section className="v3-space-y-4">
      <div className="rounded-lg border border-[var(--border)] bg-surface p-4">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <div className="flex items-center gap-2">
              <PlugZap size={16} className="text-text-secondary" aria-hidden="true" />
              <h2 className="text-sm font-semibold text-text">Ứng dụng và tài khoản</h2>
            </div>
          </div>
          <StatusPill tone={providerRegistryLoaded || snapshot ? "ok" : "pending"}>
            {providerRegistryLoaded
              ? "Danh mục đã đồng bộ"
              : snapshot
                ? "Dữ liệu từ phiên làm việc"
                : "Chế độ ngoại tuyến"}
          </StatusPill>
        </div>

        <div className="mt-4 flex flex-wrap gap-2">
          {providerFilters.map((item) => (
            <button
              key={item.id}
              type="button"
              aria-label={`${item.label}${item.id === "composio" ? " (Composio)" : ""}`}
              onClick={() => {
                setProvider(item.id);
                setSelectedCardId(null);
              }}
              className={`inline-flex min-h-9 items-center gap-2 rounded-md border px-3 py-1.5 text-sm font-medium transition-colors ${
                provider === item.id
                  ? "border-primary/40 bg-primary/10 text-primary"
                  : "border-[var(--border)] bg-surface-secondary text-text-secondary hover:text-text"
              }`}
              aria-pressed={provider === item.id}
            >
              <span>{item.label}</span>
            </button>
          ))}
        </div>

        <div className="mt-4 grid items-start gap-3 lg:grid-cols-[minmax(240px,420px)_1fr]">
          <label className="relative block">
            <span className="sr-only">Tìm kết nối</span>
            <Search
              size={16}
              className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-text-tertiary"
              aria-hidden="true"
            />
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              className="h-10 w-full rounded-md border border-[var(--border)] bg-surface-secondary pl-9 pr-3 text-sm text-text v3-outline-none focus:border-primary"
              placeholder="Tìm kết nối..."
            />
          </label>

          <div className="flex flex-wrap gap-2">
            {categoryFilters.map((item) => (
              <button
                key={item.id}
                type="button"
                onClick={() => {
                  setCategory(item.id);
                  setSelectedCardId(null);
                }}
                className={`inline-flex min-h-9 items-center rounded-md border px-3 py-1.5 text-sm ${
                  category === item.id
                    ? "border-primary/40 bg-primary/10 text-primary"
                    : "border-[var(--border)] bg-surface-secondary text-text-secondary hover:text-text"
                }`}
                aria-pressed={category === item.id}
              >
                {item.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      <div className="grid items-start gap-4 xl:grid-cols-[minmax(0,1fr)_minmax(320px,420px)]">
        <div className="grid gap-3 sm:grid-cols-2 2xl:grid-cols-3">
          {filteredCards.map((card) => {
            const Icon = card.icon;
            const selected = selectedCard?.id === card.id;
            return (
              <button
                key={card.id}
                type="button"
                onClick={() => setSelectedCardId(card.id)}
                className={`min-h-[168px] rounded-lg border bg-surface p-4 text-left transition-colors ${
                  selected
                    ? "border-primary/50 ring-2 ring-primary/10"
                    : "border-[var(--border)] hover:border-primary/30"
                }`}
                aria-pressed={selected}
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="flex min-w-0 items-start gap-3">
                    <span className="grid h-10 w-10 shrink-0 place-items-center rounded-lg bg-surface-secondary text-text-secondary">
                      <Icon size={19} aria-hidden="true" />
                    </span>
                    <div className="min-w-0">
                      <h3 className="truncate text-sm font-semibold text-text">{card.label}</h3>
                      <p className="mt-0.5 truncate text-xs text-text-tertiary">
                        {card.providerLabel} · {card.categoryLabel}
                      </p>
                    </div>
                  </div>
                  <StatusPill tone={card.tone}>{card.status}</StatusPill>
                </div>
                <p className="mt-3 line-clamp-2 text-sm text-text-secondary">
                  {card.description}
                </p>
                <div className="mt-4 grid grid-cols-2 gap-2 text-xs">
                  <div className="min-w-0 rounded-md bg-surface-secondary px-2 py-2">
                    <div className="text-text-tertiary">Neko dùng được</div>
                    <div className="mt-0.5 truncate font-medium text-text">
                      {card.agentReady ? "Có" : "Chưa"}
                    </div>
                  </div>
                  <div className="min-w-0 rounded-md bg-surface-secondary px-2 py-2">
                    <div className="text-text-tertiary">Trạng thái</div>
                    <div className="mt-0.5 truncate font-medium text-text">
                      {externalControlLabel(card)}
                    </div>
                  </div>
                </div>
              </button>
            );
          })}

          {filteredCards.length === 0 && (
            <div className="rounded-lg border border-dashed border-[var(--border)] bg-surface-secondary px-4 py-8 text-sm text-text-secondary sm:col-span-2 2xl:col-span-3">
              Không tìm thấy kết nối phù hợp với bộ lọc hiện tại.
            </div>
          )}
        </div>

        <ConnectionDetailPanel
          card={selectedCard}
          readinessState={
            selectedCard ? providerReadinessStates[selectedCard.providerSlug] : undefined
          }
          sessionDecision={selectedCard ? sessionDecisions[selectedCard.providerSlug] : undefined}
          authorizationDecision={selectedCard ? authorizationDecisions[selectedCard.providerSlug] : undefined}
          sessionLoading={selectedCard ? sessionLoadingSlug === selectedCard.providerSlug : false}
          readinessLoading={
            selectedCard
              ? Boolean(providerReadinessStates[selectedCard.providerSlug]?.loading)
              : false
          }
          authorizationLoading={selectedCard ? authorizationLoadingSlug === selectedCard.providerSlug : false}
          disconnectState={selectedCard ? disconnectStates[selectedCard.providerSlug] : undefined}
          actionInventoryState={selectedCard ? providerActionInventories[selectedCard.providerSlug] : undefined}
          readinessError={
            selectedCard ? providerReadinessStates[selectedCard.providerSlug]?.error : undefined
          }
          actionInventoryError={
            selectedCard ? providerActionInventories[selectedCard.providerSlug]?.error : undefined
          }
          sessionError={selectedCard ? sessionErrors[selectedCard.providerSlug] : undefined}
          authorizationError={selectedCard ? authorizationErrors[selectedCard.providerSlug] : undefined}
          connectionList={selectedCard ? providerConnectionLists[selectedCard.providerSlug] : undefined}
          onRefreshReadiness={refreshActivationReadiness}
          onRequestSession={requestSessionDecision}
          onRequestAuthorization={requestAuthorizationUrl}
          onRefreshConnections={refreshProviderConnections}
          onRefreshActionInventory={refreshActionInventory}
          onDisconnectConnection={disconnectProviderConnection}
        />
      </div>
    </section>
  );
}
