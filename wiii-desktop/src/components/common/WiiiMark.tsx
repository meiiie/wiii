import type { SVGProps } from "react";
import { WiiiLogo } from "./WiiiLogo";

interface WiiiMarkProps
  extends Omit<SVGProps<SVGSVGElement>, "width" | "height" | "children"> {
  size?: number;
  title?: string;
  alt?: string;
}

/** Compact product identity. WiiiAvatar remains the conversation character. */
export function WiiiMark({
  size = 20,
  title,
  alt,
  ...props
}: WiiiMarkProps) {
  return <WiiiLogo {...props} variant="mark" size={size} label={alt} title={title} />;
}
