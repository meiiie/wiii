/**
 * ModelSelector — inline LLM provider picker dropdown.
 * Cloned from DomainSelector pattern. Pill button + upward dropdown.
 */
import { useState, useRef, useEffect, useCallback } from "react";
import { AnimatePresence, motion } from "motion/react";
import { Sparkles, Cpu, ChevronUp } from "lucide-react";
import { useModelStore } from "@/stores/model-store";

const PROVIDER_ICONS: Record<string, typeof Cpu> = {
  auto: Sparkles,
  google: Cpu,
  zhipu: Cpu,
};

const PROVIDER_LABELS: Record<string, string> = {
  auto: "Tự động",
  google: "Gemini",
  zhipu: "GLM-5",
};

interface ModelSelectorProps {
  compact?: boolean;
}

export function ModelSelector({ compact: _compact }: ModelSelectorProps = {}) {
  const { activeProvider, setActiveProvider, providers, fetchProviders } =
    useModelStore();
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const fetchedRef = useRef(false);

  // Fetch providers once on mount
  useEffect(() => {
    if (!fetchedRef.current) {
      fetchedRef.current = true;
      fetchProviders();
    }
  }, [fetchProviders]);

  // Outside-click close
  const handleClickOutside = useCallback(
    (e: MouseEvent) => {
      if (
        open &&
        containerRef.current &&
        !containerRef.current.contains(e.target as Node)
      ) {
        setOpen(false);
      }
    },
    [open],
  );

  useEffect(() => {
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [handleClickOutside]);

  // Escape key close
  useEffect(() => {
    if (!open) return;
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    document.addEventListener("keydown", handleKey);
    return () => document.removeEventListener("keydown", handleKey);
  }, [open]);

  // Hide if only 1 provider (or none)
  if (providers.length <= 1) return null;

  const ActiveIcon = PROVIDER_ICONS[activeProvider] || Sparkles;
  const activeLabel = PROVIDER_LABELS[activeProvider] || activeProvider;

  // Build options: "auto" first, then real providers
  const options: Array<{
    id: string;
    label: string;
    Icon: typeof Cpu;
    available?: boolean;
  }> = [
    { id: "auto", label: PROVIDER_LABELS.auto, Icon: PROVIDER_ICONS.auto },
    ...providers.map((p) => ({
      id: p.id,
      label: PROVIDER_LABELS[p.id] || p.displayName,
      Icon: PROVIDER_ICONS[p.id] || Cpu,
      available: p.available,
    })),
  ];

  const handleSelect = (id: string) => {
    setActiveProvider(id);
    setOpen(false);
  };

  return (
    <div ref={containerRef} className="relative">
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs text-text-secondary hover:text-text hover:bg-surface-tertiary transition-colors"
        aria-label="Chọn model"
        aria-expanded={open}
        data-testid="model-selector-trigger"
      >
        <ActiveIcon size={13} />
        <span>{activeLabel}</span>
        <motion.span
          animate={{ rotate: open ? 0 : 180 }}
          transition={{ type: "spring", stiffness: 300, damping: 20 }}
          className="inline-flex"
        >
          <ChevronUp size={12} />
        </motion.span>
      </button>

      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0, scale: 0.95, y: 4 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95, y: 4 }}
            transition={{ duration: 0.15, ease: "easeOut" }}
            className="absolute bottom-full left-0 mb-1 min-w-[180px] rounded-xl border border-border bg-surface shadow-lg"
            style={{ zIndex: 50 }}
            role="listbox"
            aria-label="Danh sách model"
            data-testid="model-selector-dropdown"
          >
            <div className="py-1">
              {options.map(({ id, label, Icon, available }) => {
                const isActive = id === activeProvider;
                const isUnavailable = available === false;
                return (
                  <button
                    key={id}
                    onClick={() => handleSelect(id)}
                    role="option"
                    aria-selected={isActive}
                    className={`w-full flex items-center gap-2.5 px-3 py-2 text-sm transition-colors ${
                      isActive
                        ? "text-[var(--accent)] bg-[var(--accent-light)]"
                        : isUnavailable
                          ? "text-text-tertiary hover:bg-surface-secondary"
                          : "text-text hover:bg-surface-secondary"
                    }`}
                  >
                    <Icon size={15} />
                    <span>{label}</span>
                    {/* Availability dot */}
                    {id !== "auto" && (
                      <span
                        className={`ml-auto w-2 h-2 rounded-full ${
                          isUnavailable ? "bg-yellow-400" : "bg-green-500"
                        }`}
                        title={isUnavailable ? "Đang bận" : "Sẵn sàng"}
                      />
                    )}
                    {isActive && id === "auto" && (
                      <span className="ml-auto text-[var(--accent)] text-xs">
                        ✓
                      </span>
                    )}
                  </button>
                );
              })}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
