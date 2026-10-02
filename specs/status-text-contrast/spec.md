# Small status text contrast

Current native audit: Work's 12px unknown-outcome label and other small semantic status labels use the Neko light semantic colors. Source token math finds success/warning/danger below 4.5:1 on one or more normal surfaces. Screenshot pixel-audit/03-status-contrast-before.jpg captures the affected Work detail.

Keep the approved character/brand unchanged. Adjust only light semantic status ink to retain green/amber/red meaning while meeting at least 4.5:1 against canvas/sidebar/raised/composer/inset. Dark palette already passes. Add regression calculations for text/secondary/tertiary/ghost/status foregrounds across both palettes, plus inverse buttons. This is a token-pair guarantee, not a blanket WCAG certification (opacity, overlays, third-party surfaces and actual computed states need separate review).
