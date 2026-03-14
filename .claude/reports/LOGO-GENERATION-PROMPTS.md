# Wiii AI Logo Generation Prompts
**For:** Gemini Banana 2 / Imagen 3 / Midjourney
**Date:** 2026-03-14

---

## Context

- **Brand:** Wiii AI (by The Wiii Lab)
- **Parent logo:** Chữ "W" dạng sóng (wave), minimalist, dark gray (#3F3F46)
- **Color scheme:** Orange (#F97316) primary, warm neutrals
- **Style:** Modern, clean, approachable, educational
- **Usage:** Favicon, app icon, OG image, marketing

---

## Prompt 1: App Icon (Square, for favicon/app icon)

```json
{
  "prompt": "Minimalist app icon design for an AI education assistant called 'Wiii'. The icon features a stylized letter W made of smooth flowing wave curves, rendered in white on a warm orange (#F97316) rounded rectangle background. The wave has 3 peaks representing knowledge, intelligence, and interaction. Clean modern design, no text, flat design with subtle gradient from orange to deep orange. Suitable for app store icon at 512x512px. Professional, friendly, educational feel.",
  "negative_prompt": "text, words, letters, complex details, realistic, 3D, photographic, busy background, multiple colors, dark, scary",
  "aspect_ratio": "1:1",
  "style": "flat design, minimalist icon"
}
```

## Prompt 2: Wordmark Logo (Horizontal, for headers/marketing)

```json
{
  "prompt": "Clean modern wordmark logo 'Wiii' for an AI education platform. The first letter W is stylized as a flowing wave curve (like a sound wave or ocean wave). The 'iii' letters have dots that subtly resemble neural network nodes connected by thin lines. Color: warm orange (#F97316) for the wave W, dark charcoal (#1E293B) for 'iii'. White background, minimalist, professional, suitable for web header and marketing materials. Inspired by brands like Notion, Linear, Anthropic.",
  "negative_prompt": "complex, ornate, 3D, realistic, photographic, multiple colors, gradients, shadows, busy",
  "aspect_ratio": "3:1",
  "style": "minimalist wordmark, flat design"
}
```

## Prompt 3: OG Image / Social Card (1200x630)

```json
{
  "prompt": "Social media card design for Wiii AI, an intelligent learning assistant. Clean warm background with subtle gradient from cream to light orange. Center: stylized W wave logo in orange, below it 'Wiii AI' in bold modern font, tagline 'Trợ lý AI thông minh cho học tập' in gray. Three small icons at bottom: chart icon, brain icon, lightning bolt icon representing visual analytics, long-term memory, and multi-agent intelligence. Bottom right corner: 'by The Wiii Lab' in small gray text. Professional, educational, modern design.",
  "negative_prompt": "photographic, realistic people, complex scenes, dark, scary, multiple screenshots",
  "aspect_ratio": "1200:630",
  "style": "social media card, flat design, modern"
}
```

## Prompt 4: Mascot/Avatar (for chat UI)

```json
{
  "prompt": "Cute friendly mascot for an AI education assistant. A small round orange character with a warm smile, resembling a happy wave or blob. Has two small dots for eyes and a gentle curved smile. Simple, kawaii-inspired, minimal details. Orange (#F97316) body with slightly darker orange cheeks. White background. Suitable as chat avatar at 48x48px. Friendly, approachable, not intimidating.",
  "negative_prompt": "scary, complex, realistic, robotic, mechanical, angular, dark colors",
  "aspect_ratio": "1:1",
  "style": "kawaii, minimal mascot, flat design"
}
```

---

## Manual SVG Logo (Ready to Use)

If AI generation is not available, use this SVG:

### App Icon (Orange square + white wave W)
```svg
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" fill="none">
  <rect width="512" height="512" rx="96" fill="#F97316"/>
  <path d="M96 280 C 120 180, 160 180, 180 256 S 220 340, 256 256 S 296 170, 320 256 S 356 340, 416 230"
    stroke="white" stroke-width="40" stroke-linecap="round" stroke-linejoin="round" fill="none"/>
</svg>
```

### Monochrome Logo (Dark wave W, for light backgrounds)
```svg
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 480 240" fill="none">
  <path d="M32 160 C 60 60, 100 60, 130 120 S 180 200, 220 120 S 264 40, 300 120 S 340 200, 448 80"
    stroke="#3F3F46" stroke-width="32" stroke-linecap="round" stroke-linejoin="round"/>
</svg>
```

---

## Color Palette

| Name | Hex | Usage |
|------|-----|-------|
| Primary Orange | `#F97316` | Logo, accent, CTA buttons |
| Deep Orange | `#EA580C` | Hover states, gradients |
| Warm Cream | `#FAF5EE` | Background (light mode) |
| Dark Charcoal | `#1E293B` | Text, dark mode accent |
| Slate Gray | `#64748B` | Secondary text |
| Light Border | `#E2E8F0` | Borders, dividers |
