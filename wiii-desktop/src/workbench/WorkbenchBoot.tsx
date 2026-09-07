import { WiiiMark } from "@/components/common/WiiiMark";

export function BootSplash({ label }: { label: string }) {
  return (
    <div className="flex h-screen flex-col items-center justify-center bg-surface">
      <div className="flex flex-col items-center gap-4">
        <WiiiMark size={48} alt="Wiii" className="animate-pulse" />
        <span className="text-sm text-text-tertiary">{label}</span>
      </div>
    </div>
  );
}

export function BootFailure({
  error,
  onRetry,
}: {
  error: string;
  onRetry: () => void;
}) {
  return (
    <div className="grid h-screen place-items-center bg-surface px-6">
      <section className="w-full max-w-md rounded-2xl border border-border bg-surface-secondary p-6 text-center">
        <WiiiMark size={44} alt="Wiii" />
        <h1 className="mt-4 text-base font-semibold text-text">
          Wiii chưa khởi động xong
        </h1>
        <p className="mt-2 break-words text-sm leading-6 text-text-tertiary">
          {error}
        </p>
        <button
          type="button"
          className="mt-5 h-9 rounded-lg bg-text px-4 text-sm font-medium text-surface transition-opacity hover:opacity-85 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent)]/30"
          onClick={onRetry}
        >
          Thử khởi động lại
        </button>
      </section>
    </div>
  );
}
