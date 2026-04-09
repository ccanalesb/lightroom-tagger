# Lightroom Tagger Design System

Warm minimalist design system with light-first interface and full dark mode support.

## 1. Visual Theme & Atmosphere

Light-first interface with warm neutrals — soft cream whites (`#f6f5f4`) and warm near-blacks (`rgba(0,0,0,0.95)`) create a paper-like quality that feels premium yet approachable. Dark mode maintains the same warm undertones with deep warm darks (`#31302e`) instead of cold blacks.

Ultra-thin borders (`1px solid rgba(0,0,0,0.1)`) provide structure without visual noise. Multi-layer shadows with cumulative opacity below 0.05 create barely-there depth. Single blue accent color (`#0075de` light, `#62aef0` dark) for all interactive elements maintains visual simplicity.

**Key Characteristics:**
- Inter font family with standard weights (400, 500, 600, 700)
- Warm neutral palette with yellow-brown undertones
- Ultra-thin borders for whisper-weight divisions
- Multi-layer shadow system with sub-0.05 opacity
- Single accent color (blue) for all interactive elements
- 8px base spacing with organic scale
- Dual mode: Light-first + Dark mode

## 2. Color Palette

### Light Mode (Default)

**Surfaces:**
- Background: `#ffffff` (pure white canvas)
- Surface: `#f6f5f4` (warm white tint)
- Surface Hover: `#f1f0ed` (hover state)

**Text:**
- Primary: `rgba(0,0,0,0.95)` (near-black with micro-warmth)
- Secondary: `#615d59` (warm gray)
- Tertiary: `#a39e98` (muted warm gray)

**Interactive:**
- Accent: `#0075de` (blue)
- Accent Hover: `#005bab` (darker blue)
- Accent Light: `#f2f9ff` (light blue tint)

**Borders:**
- Border: `rgba(0,0,0,0.1)` (ultra-thin)
- Border Strong: `rgba(0,0,0,0.15)` (emphasized)

**Semantic:**
- Success: `#1aae39` (green)
- Warning: `#dd5b00` (orange)
- Error: `#e03e3e` (red)

### Dark Mode

**Surfaces:**
- Background: `#191919` (deep warm dark)
- Surface: `#31302e` (warm dark surface)
- Surface Hover: `#3d3b38` (hover state)

**Text:**
- Primary: `#f7f6f5` (near-white)
- Secondary: `#9b9a97` (muted warm gray)
- Tertiary: `#6f6e69` (de-emphasized)

**Interactive:**
- Accent: `#62aef0` (light blue)
- Accent Hover: `#97c9ff` (lighter blue)
- Accent Light: `rgba(98,174,240,0.1)` (blue tint)

**Borders:**
- Border: `rgba(255,255,255,0.1)` (ultra-thin light)
- Border Strong: `rgba(255,255,255,0.15)` (emphasized)

**Semantic:**
- Success: `#2a9d99` (teal)
- Warning: `#ff8c42` (warm orange)
- Error: `#ff6b6b` (warm red)

## 3. Typography

### Font Family
- Primary: `Inter` via Google Fonts CDN
- Fallbacks: `-apple-system, system-ui, Segoe UI, Helvetica, Arial, sans-serif`
- Weights: 400 (regular), 500 (medium), 600 (semibold), 700 (bold)

### Scale

| Role | Size | Weight | Line Height | Letter Spacing |
|------|------|--------|-------------|----------------|
| Hero | 64px | 700 | 1.0 | -2.125px |
| Section | 48px | 700 | 1.0 | -1.5px |
| Subsection | 26px | 700 | 1.23 | -0.625px |
| Card Title | 22px | 700 | 1.27 | -0.25px |
| Body Large | 20px | 600 | 1.40 | -0.125px |
| Body | 16px | 400 | 1.50 | normal |
| Body Medium | 16px | 500 | 1.50 | normal |
| Small | 14px | 400-500 | 1.43 | -0.224px |
| Tiny | 12px | 400 | 1.33 | -0.12px |

## 4. Components

### Button
- Variants: primary, secondary, ghost, danger
- Sizes: sm, md, lg
- Border radius: 8px
- Focus: 2px ring with accent color
- Transition: all 150ms

### Card
- Background: `bg-bg`
- Border: 1px `border-border`
- Radius: 12px
- Shadow: Multi-layer card shadow
- Hover: Deep shadow + strong border
- Padding: none, sm (12px), md (16px), lg (24px)

### Badge
- Variants: default, success, warning, error, accent
- Radius: 9999px (full pill)
- Font: 12px weight 500
- Padding: 2px 10px

### Input
- Border: 1px `border-border`
- Radius: 8px
- Focus: 2px ring with accent color
- Hover: Border strong
- Padding: 8px 12px

### Tabs
- Border bottom: 2px on active
- Active color: accent
- Inactive: text-secondary
- Hover: text + border hint

## 5. Shadows

**Card (default):**
```
rgba(0,0,0,0.04) 0px 4px 18px,
rgba(0,0,0,0.027) 0px 2.025px 7.84688px,
rgba(0,0,0,0.02) 0px 0.8px 2.925px,
rgba(0,0,0,0.01) 0px 0.175px 1.04062px
```

**Deep (modal/featured):**
```
rgba(0,0,0,0.01) 0px 1px 3px,
rgba(0,0,0,0.02) 0px 3px 7px,
rgba(0,0,0,0.02) 0px 7px 15px,
rgba(0,0,0,0.04) 0px 14px 28px,
rgba(0,0,0,0.05) 0px 23px 52px
```

## 6. Spacing (8px base)

- 0.5 = 4px
- 1 = 8px
- 1.5 = 12px
- 2 = 16px
- 3 = 24px
- 4 = 32px
- 6 = 48px
- 8 = 64px

## 7. Responsive Breakpoints

- sm: 640px (mobile landscape)
- md: 768px (tablet)
- lg: 1024px (desktop)
- xl: 1280px (large desktop)

## 8. Implementation

Built with:
- React 18 + TypeScript
- Tailwind CSS 3 (custom theme)
- CSS Variables for theme switching
- ThemeContext for dark mode
- Component folder structure with index exports

CSS Variables:
```css
:root {
  --color-background: #ffffff;
  --color-surface: #f6f5f4;
  /* ... all theme colors */
}

.dark {
  --color-background: #191919;
  --color-surface: #31302e;
  /* ... dark mode overrides */
}
```

Tailwind Classes (semantic):
- `bg-bg`, `bg-surface`, `bg-surface-hover`
- `text-text`, `text-text-secondary`, `text-text-tertiary`
- `border-border`, `border-border-strong`
- `text-accent`, `bg-accent`, `hover:bg-accent-hover`
- `rounded-base` (8px), `rounded-card` (12px)
- `shadow-card`, `shadow-deep`
