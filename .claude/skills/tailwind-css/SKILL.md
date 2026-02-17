# TailwindCSS 3 Skill

## Description
TailwindCSS utility-first CSS framework patterns for rapid UI development.

## Configuration
```javascript
// tailwind.config.js
/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        primary: {
          50: '#eff6ff',
          500: '#3b82f6',
          600: '#2563eb',
          700: '#1d4ed8',
        },
      },
      fontFamily: {
        sans: ['Inter', 'sans-serif'],
      },
    },
  },
  plugins: [],
}
```

## Common Patterns

### Layout
```tsx
// Flexbox
<div className="flex items-center justify-between gap-4">

// Grid
<div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">

// Container
<div className="container mx-auto px-4 max-w-7xl">
```

### Spacing
```tsx
// Padding
<div className="p-4 px-6 py-2 pt-4 pb-8">

// Margin
<div className="m-4 mx-auto my-8 mt-4 mb-6">

// Gap (for flex/grid)
<div className="flex gap-4">
```

### Typography
```tsx
// Text size
<p className="text-sm text-base text-lg text-xl text-2xl">

// Font weight
<p className="font-normal font-medium font-semibold font-bold">

// Text color
<p className="text-gray-900 text-gray-600 text-blue-500">

// Line height
<p className="leading-tight leading-normal leading-relaxed">
```

### Backgrounds & Borders
```tsx
// Background
<div className="bg-white bg-gray-100 bg-blue-500">

// Border
<div className="border border-gray-200 border-2 border-blue-500">

// Border radius
<div className="rounded rounded-lg rounded-full rounded-none">

// Shadow
<div className="shadow shadow-md shadow-lg shadow-xl">
```

### Interactive States
```tsx
// Hover
<button className="bg-blue-500 hover:bg-blue-600">

// Focus
<input className="focus:outline-none focus:ring-2 focus:ring-blue-500">

// Active
<button className="active:bg-blue-700">

// Disabled
<button className="disabled:opacity-50 disabled:cursor-not-allowed">
```

### Responsive Design
```tsx
// Mobile-first breakpoints
<div className="
  text-sm          /* default (mobile) */
  md:text-base     /* >= 768px */
  lg:text-lg       /* >= 1024px */
  xl:text-xl       /* >= 1280px */
">

// Hide/show
<div className="hidden md:block">  {/* Hidden on mobile, visible on md+ */}
<div className="md:hidden">        {/* Visible on mobile, hidden on md+ */}
```

### Dark Mode
```tsx
// With dark: prefix
<div className="bg-white dark:bg-gray-900 text-gray-900 dark:text-white">
```

## Component Examples

### Card
```tsx
<div className="bg-white rounded-lg shadow-md p-6 hover:shadow-lg transition-shadow">
  <h3 className="text-lg font-semibold text-gray-900">Title</h3>
  <p className="mt-2 text-gray-600">Description</p>
</div>
```

### Button
```tsx
<button className="
  px-4 py-2
  bg-blue-500 hover:bg-blue-600
  text-white font-medium
  rounded-lg
  transition-colors
  focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2
  disabled:opacity-50 disabled:cursor-not-allowed
">
  Click me
</button>
```

### Input
```tsx
<input
  type="text"
  className="
    w-full px-4 py-2
    border border-gray-300 rounded-lg
    focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent
    placeholder-gray-400
  "
  placeholder="Enter text..."
/>
```

### Chat Bubble
```tsx
// User message
<div className="flex justify-end">
  <div className="max-w-[80%] bg-blue-500 text-white rounded-lg rounded-br-none px-4 py-2">
    {message}
  </div>
</div>

// Assistant message
<div className="flex justify-start">
  <div className="max-w-[80%] bg-gray-100 text-gray-900 rounded-lg rounded-bl-none px-4 py-2">
    {message}
  </div>
</div>
```

## Utility: cn() for Conditional Classes
```typescript
import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

// Usage
<div className={cn(
  "p-4 rounded-lg",
  isActive && "bg-blue-500",
  isDisabled && "opacity-50"
)}>
```

## Best Practices

1. **Mobile-first** - Start with mobile styles, add breakpoints for larger screens
2. **Extract components** - Don't repeat long class strings, create components
3. **Use @apply sparingly** - Prefer component extraction over @apply
4. **Consistent spacing** - Stick to the spacing scale (4, 8, 12, 16, etc.)
5. **Semantic colors** - Use primary, secondary, etc. instead of raw colors
