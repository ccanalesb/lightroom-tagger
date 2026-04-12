---
alwaysApply: false
globs:
  - "apps/visualizer/frontend/**/*.tsx"
  - "apps/visualizer/frontend/**/*.ts"
  - "apps/visualizer/frontend/**/*.css"
---

# Frontend Design Guidelines

When working on frontend files, always follow the design system defined in `apps/visualizer/frontend/DESIGN.md`.

**Before making any UI/styling decisions, read that file for:**
- Color palette (light + dark mode CSS variables)
- Typography scale (Inter font, specific sizes/weights/spacing)
- Component patterns (Button, Card, Badge, Input, Tabs)
- Shadow system (card, deep)
- Spacing (8px base grid)
- Tailwind semantic classes (`bg-bg`, `text-text`, `border-border`, `text-accent`, etc.)

**Rules:**
- Use semantic Tailwind classes from the design system, not raw color values
- Respect the single accent color (blue) for all interactive elements
- Follow the 8px spacing grid
- New components must support both light and dark mode via CSS variables
- Use the existing shadow presets (`shadow-card`, `shadow-deep`), don't invent new ones
- Badge, Button, Card patterns are already established — extend, don't reinvent
