import type { VisualRuntimeManifest, VisualShellVariant } from "@/api/types";
import { InlineVisualFrame } from "./InlineVisualFrame";

interface EmbeddedAppFrameProps {
  html: string;
  className?: string;
  title?: string;
  summary?: string;
  sessionId?: string;
  shellVariant?: VisualShellVariant;
  runtimeManifest?: VisualRuntimeManifest | null;
}

export function EmbeddedAppFrame(props: EmbeddedAppFrameProps) {
  return (
    <InlineVisualFrame
      {...props}
      frameKind="app"
      shellVariant={props.shellVariant || "immersive"}
      showFrameIntro={false}
      hostShellMode="force"
    />
  );
}
