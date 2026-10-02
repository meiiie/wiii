import { useId, type SVGProps } from "react";
import "./wiii-logo.css";

export type WiiiLogoProps = Omit<SVGProps<SVGSVGElement>, "children" | "width" | "height"> & {
  label?: string;
  title?: string;
  size?: number;
  variant?: "mark" | "mascot";
  state?: "ready" | "arriving" | "settling";
};

export function WiiiLogo({ label = "", size = 32, variant = "mark", state = "ready", title, className, style, ...props }: WiiiLogoProps) {
  const instanceId = useId();
  const prefix = `wiii-${instanceId.replace(/:/g, "")}`;
  const isMark = variant === "mark";
  const accessibleLabel = props["aria-label"] ?? (label || undefined);
  const named = Boolean(accessibleLabel || title || props["aria-labelledby"]);
  return (
    <svg {...props} {...{ draggable: false }} width={size} height={size} focusable="false" xmlns="http://www.w3.org/2000/svg"
      viewBox={isMark ? "0 0 1024 1024" : "0 0 1254 1254"}
      className={["wiii-logo", className].filter(Boolean).join(" ")}
      style={{ width: size, height: size, ...style }}
      role={props.role ?? (named ? "img" : undefined)} aria-hidden={props["aria-hidden"] ?? (named ? undefined : true)}
      aria-label={accessibleLabel}
      aria-labelledby={props["aria-labelledby"] ?? (!accessibleLabel && title ? `${prefix}-title` : undefined)} data-state={state}>
      {(title || label) && <title id={`${prefix}-title`}>{title || label}</title>}
      <defs>
    <linearGradient id={`${prefix}-wiii-body-shade`} x1="480" y1="250" x2="660" y2="730" gradientUnits="userSpaceOnUse">
      <stop stopColor="#F5F0E6"/><stop offset=".52" stopColor="#EFE9E0"/><stop offset="1" stopColor="#D9D0C2"/>
    </linearGradient>
    <linearGradient id={`${prefix}-wiii-tail-back-shade`} x1="320" y1="435" x2="950" y2="930" gradientUnits="userSpaceOnUse">
      <stop stopColor="#454241"/><stop offset=".55" stopColor="#363433"/><stop offset="1" stopColor="#2A2928"/>
    </linearGradient>
    <linearGradient id={`${prefix}-wiii-tail-front-shade`} x1="450" y1="635" x2="540" y2="1010" gradientUnits="userSpaceOnUse">
      <stop stopColor="#454241"/><stop offset=".5" stopColor="#393736"/><stop offset="1" stopColor="#2A2928"/>
    </linearGradient>
  <linearGradient id={`${prefix}-wiii-tile-shade`} x1="0" y1="32" x2="0" y2="992" gradientUnits="userSpaceOnUse"><stop stopColor="#EEEBE6"/><stop offset="1" stopColor="#AEABAB"/></linearGradient></defs>
      {isMark && <g id={`${prefix}-wiii-icon-tile`}><rect x="32" y="32" width="960" height="960" rx="226" fill={`url(#${prefix}-wiii-tile-shade)`} stroke="#2A2928" strokeOpacity=".14" strokeWidth="3"/></g>}
      <g transform={isMark ? "translate(-40.36 10.91) scale(.893054)" : undefined}>
        <g id={`${prefix}-wiii-neko-peek`} className="wiii-neko-peek">
    <g id={`${prefix}-wiii-tail-back`} className="wiii-tail-back"><path d="M325 422 C262 466 212 523 186 584 C168 630 163 677 167 720 C171 768 188 812 216 848 C244 882 281 912 328 941 C390 969 469 991 546 999 C600 1005 660 1009 704 1007 C751 1007 782 1002 806 998 C850 992 881 981 905 964 C922 954 933 940 943 925 C982 904 1017 883 1045 816 C1067 766 1075 700 1070 663 C1063 602 1042 531 1017 461 C996 426 969 403 934 381 C740 340 498 346 325 422 Z" fill={`url(#${prefix}-wiii-tail-back-shade)`}/></g>
    <g id={`${prefix}-wiii-head`} className="wiii-head">
      <path id={`${prefix}-wiii-body`} className="wiii-body" d="M326 601 C315 576 320 530 325 491 C329 454 320 399 324 363 C326 335 337 321 359 315 C390 304 417 320 451 331 C466 336 477 334 494 328 C554 306 616 288 677 286 C700 285 714 288 729 279 C751 263 773 237 795 222 C816 207 838 205 857 217 C879 231 890 261 901 294 C912 328 920 359 938 388 C957 422 974 451 973 487 C973 527 951 565 923 593 C890 627 844 652 797 670 C733 694 651 706 565 704 C496 701 436 684 390 663 C358 648 338 632 326 601 Z" fill={`url(#${prefix}-wiii-body-shade)`}/>
      <g id={`${prefix}-wiii-eyes`} className="wiii-eyes" fill="#2A2928">
        <g id={`${prefix}-wiii-eye-left`} className="wiii-eye-left"><path d="M555 524 C531 526 516 552 519 585 C521 619 536 642 558 641 C584 640 597 615 593 582 C590 548 576 522 555 524 Z"/></g>
        <g id={`${prefix}-wiii-eye-right`} className="wiii-eye-right"><path d="M779 493 C756 496 746 521 750 552 C754 586 769 608 791 607 C815 605 825 579 822 549 C818 516 802 490 779 493 Z"/></g>
      </g>
    </g>
    <g id={`${prefix}-wiii-tail-front`} className="wiii-tail-front"><path d="M175 630 C205 651 246 670 300 684 C369 702 454 701 553 705 C654 710 761 738 852 783 C916 814 952 847 954 883 C955 918 937 947 905 964 C881 981 850 992 806 998 C751 1007 704 1007 660 1008 C600 1007 570 1003 546 999 C469 991 390 969 328 941 C281 912 244 882 216 848 C188 812 171 768 167 720 C163 685 168 655 175 630 Z" fill={`url(#${prefix}-wiii-tail-front-shade)`}/></g>
  </g>
      </g>
    </svg>
  );
}
