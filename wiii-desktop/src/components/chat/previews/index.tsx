/**
 * Preview card registry and router.
 * Sprint 166: Dispatches rendering to specialized preview cards based on preview_type.
 */
import type { PreviewItemData } from "@/api/types";
import { DocumentPreviewCard } from "./DocumentPreviewCard";
import { ProductPreviewCard } from "./ProductPreviewCard";
import { WebPreviewCard } from "./WebPreviewCard";
import { LinkPreviewCard } from "./LinkPreviewCard";
import { CodePreviewCard } from "./CodePreviewCard";
import { HostActionPreviewCard } from "./HostActionPreviewCard";

type PreviewCardComponent = React.ComponentType<{
  item: PreviewItemData;
  onClick?: () => void;
}>;

/** Registry mapping preview_type → specialized card component. */
const PREVIEW_REGISTRY: Record<string, PreviewCardComponent> = {
  document: DocumentPreviewCard,
  product: ProductPreviewCard,
  web: WebPreviewCard,
  link: LinkPreviewCard,
  code: CodePreviewCard,
  host_action: HostActionPreviewCard,
};

interface PreviewCardRendererProps {
  item: PreviewItemData;
  onClick?: () => void;
}

/**
 * PreviewCardRenderer — Routes to the correct specialized preview card.
 * Falls back to DocumentPreviewCard for unknown types.
 */
export function PreviewCardRenderer({ item, onClick }: PreviewCardRendererProps) {
  const Card = PREVIEW_REGISTRY[item.preview_type] ?? DocumentPreviewCard;
  return <Card item={item} onClick={onClick} />;
}

/** Re-export individual cards for direct use. */
export { DocumentPreviewCard } from "./DocumentPreviewCard";
export { ProductPreviewCard } from "./ProductPreviewCard";
export { WebPreviewCard } from "./WebPreviewCard";
export { LinkPreviewCard } from "./LinkPreviewCard";
export { CodePreviewCard } from "./CodePreviewCard";
export { HostActionPreviewCard } from "./HostActionPreviewCard";
