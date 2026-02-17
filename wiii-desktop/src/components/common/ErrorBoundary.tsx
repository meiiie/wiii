import { Component, type ErrorInfo, type ReactNode } from "react";
import { RefreshCw } from "lucide-react";
import { WiiiAvatar } from "@/components/common/WiiiAvatar";

interface Props {
  children: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error("[ErrorBoundary]", error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="flex flex-col items-center justify-center h-full gap-4 p-8">
          <WiiiAvatar state="error" size={48} />
          <h2 className="text-lg font-semibold">Ôi không!</h2>
          <p className="text-text-secondary text-sm text-center max-w-md">
            Mình gặp sự cố rồi. {this.state.error?.message ? `Chi tiết: ${this.state.error.message}` : "Bạn thử lại nhé!"}
          </p>
          <button
            onClick={() => this.setState({ hasError: false, error: null })}
            className="flex items-center gap-2 px-4 py-2 bg-[var(--accent)] text-white rounded-lg hover:bg-[var(--accent-hover)] transition-colors"
          >
            <RefreshCw size={16} />
            Thử lại nha
          </button>
        </div>
      );
    }

    return this.props.children;
  }
}
