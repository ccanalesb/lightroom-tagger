# Frontend UI Redesign - Notion-Inspired Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transform Lightroom Tagger frontend from basic Tailwind UI to a polished, warm minimalist design system with light-first interface and full dark mode support, optimized for photo galleries and data management. Consolidate navigation from 6 to 3 sections with tabbed interfaces.

**Architecture:** Component-driven redesign using Tailwind + CSS variables for theming, React Context for dark mode state, reusable design system components following warm minimalism aesthetic. New navigation structure: Dashboard | Images (3 tabs) | Processing (4 tabs). Frontend-only changes - backend untouched.

**Tech Stack:** React 18, TypeScript, Tailwind CSS 3, Vite, Inter font

**Design Philosophy (Notion-Inspired - documentation only, no "notion" in code):**
- Warm neutrals over cold grays (`#f6f5f4` warm white, `rgba(0,0,0,0.95)` near-black)
- Ultra-thin borders (`1px solid rgba(0,0,0,0.1)`)
- Multi-layer shadows with sub-0.05 opacity
- Blue accent (`#0075de`) as singular interactive color
- 8px base spacing, organic non-rigid scale
- Dual mode: Light-first (warm white) + Dark mode (warm dark `#31302e`)

**Navigation Structure:**
1. **Dashboard** - Overview with stats cards and quick actions
2. **Images** - Tabbed interface:
   - Instagram tab: Browse Instagram dump images
   - Catalog tab: Browse Lightroom catalog images  
   - Matches tab: Review side-by-side matched pairs
3. **Processing** - Tabbed interface:
   - Vision Matching tab: Start vision matching jobs
   - Descriptions tab: Generate image descriptions
   - Job Queue tab: Monitor all background jobs
   - Providers tab: Configure AI model providers

---

## File Structure Overview

### New Files (Create)
- `apps/visualizer/frontend/src/theme/colors.ts` - Color tokens for light/dark modes
- `apps/visualizer/frontend/src/theme/typography.ts` - Typography scale
- `apps/visualizer/frontend/src/theme/shadows.ts` - Multi-layer shadow system
- `apps/visualizer/frontend/src/contexts/ThemeContext.tsx` - Dark mode state management
- `apps/visualizer/frontend/src/components/ui/ThemeToggle.tsx` - Dark mode toggle button
- `apps/visualizer/frontend/src/components/ui/Button/Button.tsx` - Button component
- `apps/visualizer/frontend/src/components/ui/Button/index.ts` - Button export
- `apps/visualizer/frontend/src/components/ui/Card/Card.tsx` - Card component
- `apps/visualizer/frontend/src/components/ui/Card/CardHeader.tsx` - Card header
- `apps/visualizer/frontend/src/components/ui/Card/CardTitle.tsx` - Card title
- `apps/visualizer/frontend/src/components/ui/Card/CardContent.tsx` - Card content
- `apps/visualizer/frontend/src/components/ui/Card/index.ts` - Card exports
- `apps/visualizer/frontend/src/components/ui/Badge/Badge.tsx` - Status badge component
- `apps/visualizer/frontend/src/components/ui/Badge/index.ts` - Badge export
- `apps/visualizer/frontend/src/components/ui/Input/Input.tsx` - Input component
- `apps/visualizer/frontend/src/components/ui/Input/index.ts` - Input export
- `apps/visualizer/frontend/src/components/ui/Tabs/Tabs.tsx` - Tab navigation component
- `apps/visualizer/frontend/src/components/ui/Tabs/index.ts` - Tabs export
- `apps/visualizer/frontend/src/pages/ImagesPage.tsx` - New unified images page with tabs
- `apps/visualizer/frontend/src/pages/ProcessingPage.tsx` - New unified processing page with tabs
- `apps/visualizer/frontend/src/components/images/InstagramTab.tsx` - Instagram gallery tab content
- `apps/visualizer/frontend/src/components/images/CatalogTab.tsx` - Catalog gallery tab content
- `apps/visualizer/frontend/src/components/images/MatchesTab.tsx` - Match review tab content
- `apps/visualizer/frontend/src/components/processing/MatchingTab.tsx` - Vision matching tab content
- `apps/visualizer/frontend/src/components/processing/DescriptionsTab.tsx` - Descriptions tab content
- `apps/visualizer/frontend/src/components/processing/JobQueueTab.tsx` - Jobs queue tab content
- `apps/visualizer/frontend/src/components/processing/ProvidersTab.tsx` - Providers config tab content
- `apps/visualizer/frontend/DESIGN.md` - Complete design system documentation

### Modified Files
- `apps/visualizer/frontend/tailwind.config.js` - Add color palette + custom utilities (remove "notion" prefix)
- `apps/visualizer/frontend/src/index.css` - Import Inter font, CSS variables for theming (semantic names)
- `apps/visualizer/frontend/src/App.tsx` - Wrap with ThemeProvider, update routes
- `apps/visualizer/frontend/src/components/Layout.tsx` - Complete redesign with 3-item nav
- `apps/visualizer/frontend/src/components/instagram/InstagramImageCard.tsx` - Card styling (no "notion" in classes)
- `apps/visualizer/frontend/src/components/instagram/ImageDetailsModal.tsx` - Modal styling
- `apps/visualizer/frontend/src/components/ui/Pagination.tsx` - Pagination styling

### Removed Files (Old Pages - Replaced by Tabs)
- `apps/visualizer/frontend/src/pages/InstagramPage.tsx` - Moved to InstagramTab
- `apps/visualizer/frontend/src/pages/MatchingPage.tsx` - Moved to MatchingTab
- `apps/visualizer/frontend/src/pages/DescriptionsPage.tsx` - Moved to DescriptionsTab
- `apps/visualizer/frontend/src/pages/JobsPage.tsx` - Moved to JobQueueTab
- `apps/visualizer/frontend/src/pages/ProvidersPage.tsx` - Moved to ProvidersTab

---

## Task 1: Foundation - Theme Configuration

**Files:**
- Modify: `apps/visualizer/frontend/tailwind.config.js`
- Modify: `apps/visualizer/frontend/src/index.css`
- Create: `apps/visualizer/frontend/src/theme/colors.ts`

### Step 1: Create color token system

Create `apps/visualizer/frontend/src/theme/colors.ts`:

```typescript
// Notion-inspired color system with light + dark mode support
export const colors = {
  light: {
    // Primary surfaces
    background: '#ffffff',           // Pure white page canvas
    surface: '#f6f5f4',             // Warm white surface tint
    surfaceHover: '#f1f0ed',        // Hover state for surfaces
    
    // Text hierarchy
    textPrimary: 'rgba(0,0,0,0.95)', // Near-black with micro-warmth
    textSecondary: '#615d59',        // Warm gray 500
    textTertiary: '#a39e98',         // Warm gray 300
    
    // Borders & dividers
    border: 'rgba(0,0,0,0.1)',       // Ultra-thin whisper border
    borderStrong: 'rgba(0,0,0,0.15)', // Slightly more visible
    
    // Interactive
    accent: '#0075de',               // Notion Blue
    accentHover: '#005bab',          // Darker blue on hover
    accentLight: '#f2f9ff',          // Light blue tint
    
    // Semantic
    success: '#1aae39',
    warning: '#dd5b00',
    error: '#e03e3e',
  },
  dark: {
    // Primary surfaces
    background: '#191919',           // Deep warm dark
    surface: '#31302e',              // Warm dark surface
    surfaceHover: '#3d3b38',         // Hover state
    
    // Text hierarchy
    textPrimary: '#f7f6f5',          // Near-white
    textSecondary: '#9b9a97',        // Muted warm gray
    textTertiary: '#6f6e69',         // De-emphasized
    
    // Borders & dividers
    border: 'rgba(255,255,255,0.1)', // Ultra-thin light border
    borderStrong: 'rgba(255,255,255,0.15)',
    
    // Interactive
    accent: '#62aef0',               // Light blue for dark bg
    accentHover: '#97c9ff',          // Lighter on hover
    accentLight: 'rgba(98,174,240,0.1)',
    
    // Semantic
    success: '#2a9d99',
    warning: '#ff8c42',
    error: '#ff6b6b',
  }
} as const;

export type ThemeColors = typeof colors.light;
export type ThemeMode = 'light' | 'dark';
```

### Step 2: Update Tailwind config with semantic color names

Modify `apps/visualizer/frontend/tailwind.config.js`:

```javascript
/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: 'class', // Enable class-based dark mode
  theme: {
    extend: {
      colors: {
        // Semantic color tokens (no "notion" prefix)
        'bg': 'var(--color-background)',
        'surface': 'var(--color-surface)',
        'surface-hover': 'var(--color-surface-hover)',
        'text': 'var(--color-text-primary)',
        'text-secondary': 'var(--color-text-secondary)',
        'text-tertiary': 'var(--color-text-tertiary)',
        'border': 'var(--color-border)',
        'border-strong': 'var(--color-border-strong)',
        'accent': 'var(--color-accent)',
        'accent-hover': 'var(--color-accent-hover)',
        'accent-light': 'var(--color-accent-light)',
        'success': 'var(--color-success)',
        'warning': 'var(--color-warning)',
        'error': 'var(--color-error)',
      },
      fontFamily: {
        sans: ['Inter', '-apple-system', 'system-ui', 'Segoe UI', 'Helvetica', 'Arial', 'sans-serif'],
      },
      fontSize: {
        'hero': ['64px', { lineHeight: '1.0', letterSpacing: '-2.125px', fontWeight: '700' }],
        'section': ['48px', { lineHeight: '1.0', letterSpacing: '-1.5px', fontWeight: '700' }],
        'subsection': ['26px', { lineHeight: '1.23', letterSpacing: '-0.625px', fontWeight: '700' }],
        'card-title': ['22px', { lineHeight: '1.27', letterSpacing: '-0.25px', fontWeight: '700' }],
        'body-lg': ['20px', { lineHeight: '1.40', letterSpacing: '-0.125px', fontWeight: '600' }],
      },
      boxShadow: {
        'card': 'rgba(0,0,0,0.04) 0px 4px 18px, rgba(0,0,0,0.027) 0px 2.025px 7.84688px, rgba(0,0,0,0.02) 0px 0.8px 2.925px, rgba(0,0,0,0.01) 0px 0.175px 1.04062px',
        'deep': 'rgba(0,0,0,0.01) 0px 1px 3px, rgba(0,0,0,0.02) 0px 3px 7px, rgba(0,0,0,0.02) 0px 7px 15px, rgba(0,0,0,0.04) 0px 14px 28px, rgba(0,0,0,0.05) 0px 23px 52px',
      },
      borderRadius: {
        'base': '8px',
        'card': '12px',
      },
    },
  },
  plugins: [],
}
```

### Step 3: Add CSS variables for runtime theme switching

Modify `apps/visualizer/frontend/src/index.css`:

```css
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

@tailwind base;
@tailwind components;
@tailwind utilities;

:root {
  /* Light mode (default) */
  --color-background: #ffffff;
  --color-surface: #f6f5f4;
  --color-surface-hover: #f1f0ed;
  --color-text-primary: rgba(0,0,0,0.95);
  --color-text-secondary: #615d59;
  --color-text-tertiary: #a39e98;
  --color-border: rgba(0,0,0,0.1);
  --color-border-strong: rgba(0,0,0,0.15);
  --color-accent: #0075de;
  --color-accent-hover: #005bab;
  --color-accent-light: #f2f9ff;
  --color-success: #1aae39;
  --color-warning: #dd5b00;
  --color-error: #e03e3e;
}

.dark {
  /* Dark mode */
  --color-background: #191919;
  --color-surface: #31302e;
  --color-surface-hover: #3d3b38;
  --color-text-primary: #f7f6f5;
  --color-text-secondary: #9b9a97;
  --color-text-tertiary: #6f6e69;
  --color-border: rgba(255,255,255,0.1);
  --color-border-strong: rgba(255,255,255,0.15);
  --color-accent: #62aef0;
  --color-accent-hover: #97c9ff;
  --color-accent-light: rgba(98,174,240,0.1);
  --color-success: #2a9d99;
  --color-warning: #ff8c42;
  --color-error: #ff6b6b;
}

body {
  margin: 0;
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', 'Oxygen',
    'Ubuntu', 'Cantarell', 'Fira Sans', 'Droid Sans', 'Helvetica Neue',
    sans-serif;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  background-color: var(--color-background);
  color: var(--color-text-primary);
  transition: background-color 0.2s ease, color 0.2s ease;
}
```

### Step 4: Verify Tailwind build

```bash
cd apps/visualizer/frontend
npm run build
```

Expected: No errors, CSS variables compiled

### Step 5: Commit foundation

```bash
git add apps/visualizer/frontend/tailwind.config.js apps/visualizer/frontend/src/index.css apps/visualizer/frontend/src/theme/colors.ts
git commit -m "feat(frontend): add Notion-inspired theme foundation with dark mode support"
```

---

## Task 2: Dark Mode Context & Toggle

**Files:**
- Create: `apps/visualizer/frontend/src/contexts/ThemeContext.tsx`
- Create: `apps/visualizer/frontend/src/components/ui/ThemeToggle.tsx`
- Modify: `apps/visualizer/frontend/src/App.tsx`

### Step 1: Create theme context for dark mode state

Create `apps/visualizer/frontend/src/contexts/ThemeContext.tsx`:

```typescript
import { createContext, useContext, useEffect, useState, ReactNode } from 'react';

type ThemeMode = 'light' | 'dark';

interface ThemeContextType {
  mode: ThemeMode;
  toggleMode: () => void;
  setMode: (mode: ThemeMode) => void;
}

const ThemeContext = createContext<ThemeContextType | undefined>(undefined);

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [mode, setModeState] = useState<ThemeMode>(() => {
    // Check localStorage first, then system preference
    const stored = localStorage.getItem('theme-mode');
    if (stored === 'light' || stored === 'dark') {
      return stored;
    }
    
    // System preference
    if (window.matchMedia('(prefers-color-scheme: dark)').matches) {
      return 'dark';
    }
    
    return 'light';
  });

  useEffect(() => {
    // Apply dark class to html element
    const root = document.documentElement;
    if (mode === 'dark') {
      root.classList.add('dark');
    } else {
      root.classList.remove('dark');
    }
    
    // Persist to localStorage
    localStorage.setItem('theme-mode', mode);
  }, [mode]);

  const toggleMode = () => {
    setModeState(prev => prev === 'light' ? 'dark' : 'light');
  };

  const setMode = (newMode: ThemeMode) => {
    setModeState(newMode);
  };

  return (
    <ThemeContext.Provider value={{ mode, toggleMode, setMode }}>
      {children}
    </ThemeContext.Provider>
  );
}

export function useTheme() {
  const context = useContext(ThemeContext);
  if (!context) {
    throw new Error('useTheme must be used within ThemeProvider');
  }
  return context;
}
```

### Step 2: Create theme toggle button component

Create `apps/visualizer/frontend/src/components/ui/ThemeToggle.tsx`:

```typescript
import { useTheme } from '../../contexts/ThemeContext';

export function ThemeToggle() {
  const { mode, toggleMode } = useTheme();
  
  return (
    <button
      onClick={toggleMode}
      className="p-2 rounded-base border border-border hover:bg-surface transition-colors"
      aria-label={`Switch to ${mode === 'light' ? 'dark' : 'light'} mode`}
      title={`Current: ${mode} mode`}
    >
      {mode === 'light' ? (
        <svg
          className="w-5 h-5 text-text-secondary"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z"
          />
        </svg>
      ) : (
        <svg
          className="w-5 h-5 text-text-secondary"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z"
          />
        </svg>
      )}
    </button>
  );
}
```

### Step 3: Wrap App with ThemeProvider

Modify `apps/visualizer/frontend/src/App.tsx`:

```typescript
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom'
import { Layout } from './components/Layout'
import { ErrorBoundary } from './components/ui/ErrorBoundary'
import { DashboardPage } from './pages/DashboardPage'
import { DescriptionsPage } from './pages/DescriptionsPage'
import { InstagramPage } from './pages/InstagramPage'
import { MatchingPage } from './pages/MatchingPage'
import { JobsPage } from './pages/JobsPage'
import { ProvidersPage } from './pages/ProvidersPage'
import { MatchOptionsProvider } from './stores/matchOptionsContext'
import { ThemeProvider } from './contexts/ThemeContext'

function App() {
  return (
    <ThemeProvider>
      <MatchOptionsProvider>
        <Router>
          <Routes>
            <Route path="/" element={<Layout />}>
              <Route index element={<ErrorBoundary><DashboardPage /></ErrorBoundary>} />
              <Route path="instagram" element={<ErrorBoundary><InstagramPage /></ErrorBoundary>} />
              <Route path="matching" element={<ErrorBoundary><MatchingPage /></ErrorBoundary>} />
              <Route path="descriptions" element={<ErrorBoundary><DescriptionsPage /></ErrorBoundary>} />
              <Route path="jobs" element={<ErrorBoundary><JobsPage /></ErrorBoundary>} />
              <Route path="providers" element={<ErrorBoundary><ProvidersPage /></ErrorBoundary>} />
            </Route>
          </Routes>
        </Router>
      </MatchOptionsProvider>
    </ThemeProvider>
  )
}

export default App
```

### Step 4: Test theme toggle in browser

```bash
# Frontend should still be running, refresh browser
# Click theme toggle button (will add to nav in next task)
# Expected: Background and text colors switch between light and dark
```

### Step 5: Commit dark mode system

```bash
git add apps/visualizer/frontend/src/contexts/ThemeContext.tsx apps/visualizer/frontend/src/components/ui/ThemeToggle.tsx apps/visualizer/frontend/src/App.tsx
git commit -m "feat(frontend): add dark mode context and toggle component"
```

---

## Task 3: Core UI Components (Button, Card, Badge, Input)

**Files:**
- Create: `apps/visualizer/frontend/src/components/ui/Button/Button.tsx`
- Create: `apps/visualizer/frontend/src/components/ui/Button/index.ts`
- Create: `apps/visualizer/frontend/src/components/ui/Card/Card.tsx`
- Create: `apps/visualizer/frontend/src/components/ui/Card/CardHeader.tsx`
- Create: `apps/visualizer/frontend/src/components/ui/Card/CardTitle.tsx`
- Create: `apps/visualizer/frontend/src/components/ui/Card/CardContent.tsx`
- Create: `apps/visualizer/frontend/src/components/ui/Card/index.ts`
- Create: `apps/visualizer/frontend/src/components/ui/Badge/Badge.tsx`
- Create: `apps/visualizer/frontend/src/components/ui/Badge/index.ts`
- Create: `apps/visualizer/frontend/src/components/ui/Input/Input.tsx`
- Create: `apps/visualizer/frontend/src/components/ui/Input/index.ts`

### Step 1: Create Button component structure

Create `apps/visualizer/frontend/src/components/ui/Button/Button.tsx`:

```typescript
import { ButtonHTMLAttributes, ReactNode } from 'react';

type ButtonVariant = 'primary' | 'secondary' | 'ghost' | 'danger';
type ButtonSize = 'sm' | 'md' | 'lg';

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  fullWidth?: boolean;
  children: ReactNode;
}

const variantClasses: Record<ButtonVariant, string> = {
  primary: 'bg-accent text-white hover:bg-accent-hover border border-accent',
  secondary: 'bg-surface text-text hover:bg-surface-hover border border-border',
  ghost: 'bg-transparent text-text-secondary hover:bg-surface border border-transparent',
  danger: 'bg-error text-white hover:opacity-90 border border-error',
};

const sizeClasses: Record<ButtonSize, string> = {
  sm: 'px-3 py-1.5 text-sm',
  md: 'px-4 py-2 text-base',
  lg: 'px-6 py-3 text-lg',
};

export function Button({
  variant = 'secondary',
  size = 'md',
  fullWidth = false,
  className = '',
  disabled,
  children,
  ...props
}: ButtonProps) {
  return (
    <button
      className={`
        ${variantClasses[variant]}
        ${sizeClasses[size]}
        ${fullWidth ? 'w-full' : ''}
        ${disabled ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}
        font-medium rounded-base transition-all duration-150
        disabled:opacity-50 disabled:cursor-not-allowed
        focus:outline-none focus:ring-2 focus:ring-accent focus:ring-offset-2
        ${className}
      `.trim()}
      disabled={disabled}
      {...props}
    >
      {children}
    </button>
  );
}
```

Create `apps/visualizer/frontend/src/components/ui/Button/index.ts`:

```typescript
export { Button } from './Button';
```

### Step 2: Create Card component structure (multiple files)

Create `apps/visualizer/frontend/src/components/ui/Card/Card.tsx`:

```typescript
import { ReactNode } from 'react';

interface CardProps {
  children: ReactNode;
  className?: string;
  onClick?: () => void;
  hoverable?: boolean;
  padding?: 'none' | 'sm' | 'md' | 'lg';
}

const paddingClasses = {
  none: '',
  sm: 'p-3',
  md: 'p-4',
  lg: 'p-6',
};

export function Card({
  children,
  className = '',
  onClick,
  hoverable = false,
  padding = 'md',
}: CardProps) {
  return (
    <div
      className={`
        bg-bg border border-border rounded-card
        shadow-card transition-all duration-150
        ${paddingClasses[padding]}
        ${hoverable || onClick ? 'hover:shadow-deep hover:border-border-strong cursor-pointer' : ''}
        ${className}
      `.trim()}
      onClick={onClick}
    >
      {children}
    </div>
  );
}
```

Create `apps/visualizer/frontend/src/components/ui/Card/CardHeader.tsx`:

```typescript
import { ReactNode } from 'react';

interface CardHeaderProps {
  children: ReactNode;
  className?: string;
}

export function CardHeader({ children, className = '' }: CardHeaderProps) {
  return (
    <div className={`mb-3 ${className}`}>
      {children}
    </div>
  );
}
```

Create `apps/visualizer/frontend/src/components/ui/Card/CardTitle.tsx`:

```typescript
import { ReactNode } from 'react';

interface CardTitleProps {
  children: ReactNode;
  className?: string;
}

export function CardTitle({ children, className = '' }: CardTitleProps) {
  return (
    <h3 className={`text-card-title text-text font-bold ${className}`}>
      {children}
    </h3>
  );
}
```

Create `apps/visualizer/frontend/src/components/ui/Card/CardContent.tsx`:

```typescript
import { ReactNode } from 'react';

interface CardContentProps {
  children: ReactNode;
  className?: string;
}

export function CardContent({ children, className = '' }: CardContentProps) {
  return (
    <div className={`text-text-secondary ${className}`}>
      {children}
    </div>
  );
}
```

Create `apps/visualizer/frontend/src/components/ui/Card/index.ts`:

```typescript
export { Card } from './Card';
export { CardHeader } from './CardHeader';
export { CardTitle } from './CardTitle';
export { CardContent } from './CardContent';
```

### Step 3: Create Badge component structure

Create `apps/visualizer/frontend/src/components/ui/Badge/Badge.tsx`:

```typescript
import { ReactNode } from 'react';

type BadgeVariant = 'default' | 'success' | 'warning' | 'error' | 'accent';

interface BadgeProps {
  children: ReactNode;
  variant?: BadgeVariant;
  className?: string;
}

const variantClasses: Record<BadgeVariant, string> = {
  default: 'bg-surface text-text-secondary border-border',
  success: 'bg-green-50 dark:bg-green-900/20 text-success border-green-200 dark:border-green-800',
  warning: 'bg-orange-50 dark:bg-orange-900/20 text-warning border-orange-200 dark:border-orange-800',
  error: 'bg-red-50 dark:bg-red-900/20 text-error border-red-200 dark:border-red-800',
  accent: 'bg-accent-light text-accent border-blue-200 dark:border-blue-800',
};

export function Badge({ children, variant = 'default', className = '' }: BadgeProps) {
  return (
    <span
      className={`
        inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium
        border ${variantClasses[variant]} ${className}
      `.trim()}
    >
      {children}
    </span>
  );
}
```

Create `apps/visualizer/frontend/src/components/ui/Badge/index.ts`:

```typescript
export { Badge } from './Badge';
```

### Step 4: Create Input component structure

Create `apps/visualizer/frontend/src/components/ui/Input/Input.tsx`:

```typescript
import { InputHTMLAttributes, forwardRef } from 'react';

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
  fullWidth?: boolean;
}

export const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ label, error, fullWidth = false, className = '', ...props }, ref) => {
    return (
      <div className={fullWidth ? 'w-full' : ''}>
        {label && (
          <label className="block text-sm font-medium text-text-secondary mb-1.5">
            {label}
          </label>
        )}
        <input
          ref={ref}
          className={`
            px-3 py-2 rounded-base border border-border
            bg-bg text-text placeholder-text-tertiary
            focus:outline-none focus:ring-2 focus:ring-accent focus:border-transparent
            hover:border-border-strong
            disabled:opacity-50 disabled:cursor-not-allowed
            transition-all duration-150
            ${fullWidth ? 'w-full' : ''}
            ${error ? 'border-error focus:ring-error' : ''}
            ${className}
          `.trim()}
          {...props}
        />
        {error && (
          <p className="mt-1 text-sm text-error">{error}</p>
        )}
      </div>
    );
  }
);

Input.displayName = 'Input';
```

Create `apps/visualizer/frontend/src/components/ui/Input/index.ts`:

```typescript
export { Input } from './Input';
```

### Step 5: Commit core components

```bash
git add apps/visualizer/frontend/src/components/ui/Button/ apps/visualizer/frontend/src/components/ui/Card/ apps/visualizer/frontend/src/components/ui/Badge/ apps/visualizer/frontend/src/components/ui/Input/
git commit -m "feat(frontend): add Notion-styled core UI components with proper file structure"
```

---

## Task 4: Redesign Layout with 3-Section Navigation

**Files:**
- Modify: `apps/visualizer/frontend/src/components/Layout.tsx`

### Step 1: Completely redesign Layout with consolidated navigation

Replace entire content of `apps/visualizer/frontend/src/components/Layout.tsx`:

```typescript
import { Outlet, NavLink } from 'react-router-dom';
import { ThemeToggle } from './ui/ThemeToggle';
import { APP_TITLE } from '../constants/strings';

export function Layout() {
  const navItems = [
    { to: '/', label: 'Dashboard', exact: true },
    { to: '/images', label: 'Images' },
    { to: '/processing', label: 'Processing' },
  ];

  return (
    <div className="min-h-screen bg-bg transition-colors duration-200">
      {/* Header with subtle bottom border */}
      <header className="sticky top-0 z-50 bg-bg/95 backdrop-blur-sm border-b border-border">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            {/* Logo/Title */}
            <div className="flex items-center space-x-8">
              <h1 className="text-lg font-semibold text-text">
                {APP_TITLE}
              </h1>

              {/* Horizontal navigation */}
              <nav className="hidden md:flex items-center space-x-1">
                {navItems.map((item) => (
                  <NavLink
                    key={item.to}
                    to={item.to}
                    end={item.exact}
                    className={({ isActive }) =>
                      `px-3 py-1.5 rounded-base text-sm font-medium transition-all duration-150
                      ${
                        isActive
                          ? 'bg-accent-light text-accent'
                          : 'text-text-secondary hover:bg-surface hover:text-text'
                      }`
                    }
                  >
                    {item.label}
                  </NavLink>
                ))}
              </nav>
            </div>

            {/* Right side actions */}
            <div className="flex items-center space-x-3">
              <ThemeToggle />
            </div>
          </div>
        </div>

        {/* Mobile navigation */}
        <div className="md:hidden border-t border-border">
          <nav className="px-4 py-2 flex overflow-x-auto space-x-1">
            {navItems.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.exact}
                className={({ isActive }) =>
                  `px-3 py-1.5 rounded-base text-sm font-medium whitespace-nowrap transition-all duration-150
                  ${
                    isActive
                      ? 'bg-accent-light text-accent'
                      : 'text-text-secondary hover:bg-surface'
                  }`
                }
              >
                {item.label}
              </NavLink>
            ))}
          </nav>
        </div>
      </header>

      {/* Main content area */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <Outlet />
      </main>
    </div>
  );
}
```
```

### Step 2: Test navigation in browser

Refresh browser and verify:
- Only 3 nav items: Dashboard, Images, Processing
- Light theme: white background, dark text, blue accent on active nav
- Dark theme: dark background, light text, light blue accent
- Theme toggle works in header
- Navigation items highlighted on active route
- Mobile responsive navigation appears on narrow screens

Expected: Clean 3-section navigation with smooth theme transitions

### Step 3: Commit layout redesign

```bash
git add apps/visualizer/frontend/src/components/Layout.tsx
git commit -m "feat(frontend): redesign Layout with consolidated 3-section navigation"
```

---

## Task 5: Redesign Dashboard Page

**Files:**
- Modify: `apps/visualizer/frontend/src/pages/DashboardPage.tsx`

### Step 1: Redesign Dashboard with Notion card grid

Replace content of `apps/visualizer/frontend/src/pages/DashboardPage.tsx`:

```typescript
import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Card, CardHeader, CardTitle, CardContent } from '../components/ui/Card';
import { Badge } from '../components/ui/Badge';
import { ImagesAPI, JobsAPI } from '../services/api';

export function DashboardPage() {
  const [stats, setStats] = useState({
    instagramImages: 0,
    catalogImages: 0,
    matches: 0,
    pendingJobs: 0,
  });
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function loadStats() {
      try {
        const [instagramData, jobsData] = await Promise.all([
          ImagesAPI.listInstagram({ limit: 1, offset: 0 }),
          JobsAPI.list(),
        ]);

        const pendingCount = jobsData.jobs.filter(
          (job) => job.status === 'pending' || job.status === 'running'
        ).length;

        setStats({
          instagramImages: instagramData.total,
          catalogImages: 0, // TODO: Add catalog count API
          matches: 0, // TODO: Add matches count API
          pendingJobs: pendingCount,
        });
      } catch (error) {
        console.error('Failed to load dashboard stats:', error);
      } finally {
        setLoading(false);
      }
    }

    loadStats();
  }, []);

  const statCards = [
    {
      title: 'Instagram Images',
      value: stats.instagramImages.toLocaleString(),
      description: 'Downloaded from Instagram dump',
      link: '/instagram',
      badge: stats.instagramImages > 0 ? 'success' : 'default',
    },
    {
      title: 'Catalog Images',
      value: stats.catalogImages.toLocaleString(),
      description: 'Indexed from Lightroom catalog',
      link: '/matching',
      badge: 'default',
    },
    {
      title: 'Matched Images',
      value: stats.matches.toLocaleString(),
      description: 'Successfully matched pairs',
      link: '/jobs',
      badge: stats.matches > 0 ? 'success' : 'default',
    },
    {
      title: 'Active Jobs',
      value: stats.pendingJobs.toLocaleString(),
      description: 'Currently running or queued',
      link: '/jobs',
      badge: stats.pendingJobs > 0 ? 'accent' : 'default',
    },
  ];

  return (
    <div className="space-y-8">
      {/* Page header */}
      <div>
        <h1 className="text-section text-text mb-2">
          Lightroom Tagger
        </h1>
        <p className="text-text-secondary">
          Match Instagram photos with your Lightroom catalog using AI vision models
        </p>
      </div>

      {/* Stats grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {statCards.map((stat) => (
          <Link key={stat.title} to={stat.link} className="block">
            <Card hoverable padding="md">
              <CardHeader>
                <div className="flex items-start justify-between">
                  <CardTitle>{stat.title}</CardTitle>
                  <Badge variant={stat.badge as any}>{stat.value}</Badge>
                </div>
              </CardHeader>
              <CardContent>
                <p className="text-sm">{stat.description}</p>
              </CardContent>
            </Card>
          </Link>
        ))}
      </div>

      {/* Quick actions */}
      <div>
        <h2 className="text-card-title text-text mb-4">Quick Actions</h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <Link to="/instagram">
            <Card hoverable padding="md">
              <CardHeader>
                <CardTitle>View Instagram Images</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-sm">Browse your downloaded Instagram photos and check import status</p>
              </CardContent>
            </Card>
          </Link>

          <Link to="/matching">
            <Card hoverable padding="md">
              <CardHeader>
                <CardTitle>Start Vision Matching</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-sm">Use AI vision models to match Instagram photos with catalog images</p>
              </CardContent>
            </Card>
          </Link>

          <Link to="/descriptions">
            <Card hoverable padding="md">
              <CardHeader>
                <CardTitle>Generate Descriptions</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-sm">Create AI-generated descriptions for better matching accuracy</p>
              </CardContent>
            </Card>
          </Link>
        </div>
      </div>

      {/* Loading state */}
      {loading && (
        <div className="flex items-center justify-center py-12">
          <div className="text-text-secondary">Loading stats...</div>
        </div>
      )}
    </div>
  );
}
```

### Step 2: Test Dashboard in browser

Navigate to `/` and verify:
- Stats cards display with Notion styling
- Hover effects on cards work
- Badges show appropriate colors
- Quick action cards are clickable
- Layout responsive on mobile

Expected: Clean, card-based dashboard with Notion aesthetic

### Step 3: Commit Dashboard redesign

```bash
git add apps/visualizer/frontend/src/pages/DashboardPage.tsx
git commit -m "feat(frontend): redesign Dashboard with Notion-style card grid"
```

---

## Task 6: Redesign Instagram Gallery Page

**Files:**
- Modify: `apps/visualizer/frontend/src/pages/InstagramPage.tsx`
- Modify: `apps/visualizer/frontend/src/components/instagram/InstagramImageCard.tsx`

### Step 1: Update Instagram page with Notion filters

Modify `apps/visualizer/frontend/src/pages/InstagramPage.tsx` - replace the render section starting at line 80:

```typescript
  // ... (keep existing state and fetchImages logic)

  return (
    <div className="space-y-6">
      {/* Page header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-section text-text mb-2">
            {INSTAGRAM_DOWNLOADED}
          </h1>
          <p className="text-text-secondary">
            {total} images from Instagram dump
          </p>
        </div>

        {/* Date filter */}
        {availableMonths.length > 0 && (
          <div className="flex items-center space-x-2">
            <select
              value={dateFilter}
              onChange={(e) => handleFilterChange(e.target.value)}
              className="px-3 py-2 rounded-base border border-border bg-bg text-text text-sm focus:outline-none focus:ring-2 focus:ring-accent hover:border-border-strong transition-all"
            >
              <option value="">{FILTER_ALL_DATES}</option>
              {availableMonths.map((month) => (
                <option key={month} value={month}>
                  {formatMonth(month)}
                </option>
              ))}
            </select>
            {dateFilter && (
              <button
                onClick={clearFilter}
                className="px-3 py-2 text-sm rounded-base border border-border bg-bg text-text-secondary hover:bg-surface hover:text-text transition-all"
              >
                {FILTER_CLEAR}
              </button>
            )}
          </div>
        )}
      </div>

      {/* Error state */}
      {error && <PageError message={error} />}

      {/* Loading state */}
      {isLoading && <SkeletonGrid count={ITEMS_PER_PAGE} />}

      {/* Image grid */}
      {!isLoading && !error && (
        <>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
            {images.map((image) => (
              <InstagramImageCard
                key={image.key}
                image={image}
                onClick={() => openModal(image)}
              />
            ))}
          </div>

          {/* Pagination */}
          {pagination.total_pages > 1 && (
            <div className="flex justify-center pt-4">
              <Pagination
                currentPage={pagination.current_page}
                totalPages={pagination.total_pages}
                onPageChange={handlePageChange}
              />
            </div>
          )}
        </>
      )}

      {/* Image details modal */}
      {isModalOpen && selectedImage && (
        <ImageDetailsModal image={selectedImage} onClose={closeModal} />
      )}
    </div>
  );
}
```

### Step 2: Redesign Instagram image cards

Replace content of `apps/visualizer/frontend/src/components/instagram/InstagramImageCard.tsx`:

```typescript
import type { InstagramImage } from '../../services/api';
import { Badge } from '../ui/Badge';

interface InstagramImageCardProps {
  image: InstagramImage;
  onClick: () => void;
}

export function InstagramImageCard({ image, onClick }: InstagramImageCardProps) {
  const dateDisplay = image.created_at
    ? new Date(image.created_at).toLocaleDateString()
    : image.date_folder
      ? `${image.date_folder.slice(0, 4)}/${image.date_folder.slice(4, 6)} (est.)`
      : 'No date';

  return (
    <div
      onClick={onClick}
      className="group cursor-pointer bg-bg rounded-card border border-border overflow-hidden shadow-card hover:shadow-deep hover:border-border-strong transition-all duration-200"
    >
      {/* Image container with aspect ratio */}
      <div className="relative aspect-square bg-surface">
        <img
          src={`/api/images/instagram/${encodeURIComponent(image.key)}/thumbnail`}
          alt={image.filename}
          className="absolute inset-0 w-full h-full object-cover"
          loading="lazy"
        />
        
        {/* Overlay on hover */}
        <div className="absolute inset-0 bg-black/0 group-hover:bg-black/10 transition-colors duration-200" />
        
        {/* Status badges */}
        <div className="absolute top-2 right-2 flex flex-col gap-1">
          {image.matched_catalog_key && (
            <Badge variant="success">Matched</Badge>
          )}
          {image.description && (
            <Badge variant="accent">Described</Badge>
          )}
        </div>
      </div>

      {/* Card footer with metadata */}
      <div className="p-3 space-y-1">
        <p className="text-sm font-medium text-text truncate">
          {image.instagram_folder}
        </p>
        <p className="text-xs text-text-tertiary">
          {image.source_folder}
        </p>
        <p className="text-xs text-text-secondary">
          {dateDisplay}
        </p>
      </div>
    </div>
  );
}
```

### Step 3: Test Instagram gallery in browser

Navigate to `/instagram` and verify:
- Image cards display with Notion styling
- Hover effects on cards work smoothly
- Status badges show for matched/described images
- Date filter dropdown styled correctly
- Grid layout responsive on mobile
- Images load correctly

Expected: Clean photo gallery with Notion card aesthetic

### Step 4: Commit Instagram redesign

```bash
git add apps/visualizer/frontend/src/pages/InstagramPage.tsx apps/visualizer/frontend/src/components/instagram/InstagramImageCard.tsx
git commit -m "feat(frontend): redesign Instagram gallery with Notion-style cards and filters"
```

---

## Task 7: Redesign Matching Page

**Files:**
- Modify: `apps/visualizer/frontend/src/pages/MatchingPage.tsx`
- Modify: `apps/visualizer/frontend/src/components/matching/AdvancedOptions.tsx`

### Step 1: Update Matching page header and controls

Modify `apps/visualizer/frontend/src/pages/MatchingPage.tsx` - update the render section to use new components:

```typescript
  // ... (keep existing imports and logic)
  import { Button } from '../components/ui/Button';
  import { Card, CardHeader, CardTitle, CardContent } from '../components/ui/Card';
  import { Badge } from '../components/ui/Badge';

  // ... (keep existing state and functions)

  return (
    <div className="space-y-6">
      {/* Page header */}
      <div>
        <h1 className="text-section text-text mb-2">
          Vision Matching
        </h1>
        <p className="text-text-secondary">
          Match Instagram photos with catalog images using AI vision models
        </p>
      </div>

      {/* Main matching card */}
      <Card padding="lg">
        <CardHeader>
          <CardTitle>Start Vision Matching Job</CardTitle>
        </CardHeader>
        
        <CardContent>
          <div className="space-y-6">
            {/* Date filter */}
            <div>
              <label className="block text-sm font-medium text-text mb-2">
                Date Filter
              </label>
              <select
                value={dateFilter}
                onChange={(e) => setDateFilter(e.target.value)}
                className="w-full px-3 py-2 rounded-base border border-border bg-bg text-text focus:outline-none focus:ring-2 focus:ring-accent hover:border-border-strong transition-all"
              >
                {DATE_FILTERS.map((filter) => (
                  <option key={filter.value} value={filter.value}>
                    {filter.label}
                  </option>
                ))}
              </select>
            </div>

            {/* Advanced options toggle */}
            <div>
              <button
                onClick={() => setShowAdvanced(!showAdvanced)}
                className="flex items-center space-x-2 text-sm font-medium text-accent hover:text-accent-hover transition-colors"
              >
                <svg
                  className={`w-4 h-4 transition-transform ${showAdvanced ? 'rotate-90' : ''}`}
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                </svg>
                <span>{ADVANCED_OPTIONS_TITLE}</span>
              </button>
            </div>

            {/* Advanced options panel */}
            {showAdvanced && (
              <div className="pt-4 border-t border-border">
                <AdvancedOptions
                  useVisionComparison={matchOptions.useVisionComparison}
                  onUseVisionComparisonChange={(value) => 
                    updateMatchOptions({ useVisionComparison: value })
                  }
                  maxWorkers={matchOptions.maxWorkers}
                  onMaxWorkersChange={(value) =>
                    updateMatchOptions({ maxWorkers: value })
                  }
                />
              </div>
            )}

            {/* Start button */}
            <div className="pt-4">
              <Button
                variant="primary"
                size="lg"
                fullWidth
                onClick={startMatching}
                disabled={isStarting}
              >
                {isStarting ? 'Starting Job...' : 'Start Vision Matching'}
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Recent jobs */}
      <div>
        <h2 className="text-card-title text-text mb-4">Recent Matching Jobs</h2>
        <div className="space-y-3">
          {recentJobs.map((job) => (
            <Card key={job.id} padding="md">
              <div className="flex items-center justify-between">
                <div className="flex-1">
                  <div className="flex items-center space-x-3 mb-1">
                    <span className="text-sm font-medium text-text">
                      {job.job_type}
                    </span>
                    <Badge variant={
                      job.status === 'completed' ? 'success' :
                      job.status === 'failed' ? 'error' :
                      job.status === 'running' ? 'accent' : 'default'
                    }>
                      {job.status}
                    </Badge>
                  </div>
                  <p className="text-xs text-text-tertiary">
                    {new Date(job.created_at).toLocaleString()}
                  </p>
                </div>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => window.location.href = '/jobs'}
                >
                  View Details
                </Button>
              </div>
            </Card>
          ))}
        </div>
      </div>
    </div>
  );
}
```

### Step 2: Update AdvancedOptions with Notion styling

Modify `apps/visualizer/frontend/src/components/matching/AdvancedOptions.tsx`:

```typescript
import { WorkerSlider } from './WorkerSlider';
import {
  ADVANCED_VISION_LABEL,
  ADVANCED_VISION_DESCRIPTION,
} from '../../constants/strings';

interface AdvancedOptionsProps {
  useVisionComparison: boolean;
  onUseVisionComparisonChange: (value: boolean) => void;
  maxWorkers: number;
  onMaxWorkersChange: (value: number) => void;
}

export function AdvancedOptions({
  useVisionComparison,
  onUseVisionComparisonChange,
  maxWorkers,
  onMaxWorkersChange,
}: AdvancedOptionsProps) {
  return (
    <div className="space-y-6">
      {/* Vision comparison toggle */}
      <div className="flex items-start space-x-3">
        <input
          type="checkbox"
          id="vision-comparison"
          checked={useVisionComparison}
          onChange={(e) => onUseVisionComparisonChange(e.target.checked)}
          className="mt-1 h-4 w-4 rounded border-border text-accent focus:ring-accent focus:ring-offset-0 cursor-pointer"
        />
        <div className="flex-1">
          <label
            htmlFor="vision-comparison"
            className="text-sm font-medium text-text cursor-pointer"
          >
            {ADVANCED_VISION_LABEL}
          </label>
          <p className="text-xs text-text-secondary mt-0.5">
            {ADVANCED_VISION_DESCRIPTION}
          </p>
        </div>
      </div>

      {/* Worker count slider */}
      <WorkerSlider value={maxWorkers} onChange={onMaxWorkersChange} />
    </div>
  );
}
```

### Step 3: Test Matching page in browser

Navigate to `/matching` and verify:
- Card-based layout with Notion styling
- Date filter dropdown works
- Advanced options accordion expands/collapses
- Start button styled correctly
- Recent jobs list displays with badges
- All interactive elements have proper hover states

Expected: Clean, card-based matching interface

### Step 4: Commit Matching redesign

```bash
git add apps/visualizer/frontend/src/pages/MatchingPage.tsx apps/visualizer/frontend/src/components/matching/AdvancedOptions.tsx
git commit -m "feat(frontend): redesign Matching page with Notion-style cards and controls"
```

---

## Task 8: Redesign Descriptions Page

**Files:**
- Modify: `apps/visualizer/frontend/src/pages/DescriptionsPage.tsx`

### Step 1: Update Descriptions page with Notion components

Modify the render section of `apps/visualizer/frontend/src/pages/DescriptionsPage.tsx`:

```typescript
  // ... (add imports)
  import { Button } from '../components/ui/Button';
  import { Card, CardHeader, CardTitle, CardContent } from '../components/ui/Card';
  import { Badge } from '../components/ui/Badge';

  // ... (keep existing logic)

  return (
    <div className="space-y-6">
      {/* Page header */}
      <div>
        <h1 className="text-section text-text mb-2">
          Image Descriptions
        </h1>
        <p className="text-text-secondary">
          Generate AI descriptions for Instagram images to improve matching accuracy
        </p>
      </div>

      {/* Main description generation card */}
      <Card padding="lg">
        <CardHeader>
          <CardTitle>Generate Descriptions Job</CardTitle>
        </CardHeader>
        
        <CardContent>
          <div className="space-y-6">
            {/* Stats */}
            <div className="grid grid-cols-3 gap-4">
              <div className="text-center p-4 bg-surface rounded-base">
                <div className="text-2xl font-bold text-text">
                  {stats.total.toLocaleString()}
                </div>
                <div className="text-sm text-text-secondary">Total Images</div>
              </div>
              <div className="text-center p-4 bg-surface rounded-base">
                <div className="text-2xl font-bold text-success">
                  {stats.described.toLocaleString()}
                </div>
                <div className="text-sm text-text-secondary">Described</div>
              </div>
              <div className="text-center p-4 bg-surface rounded-base">
                <div className="text-2xl font-bold text-text-tertiary">
                  {stats.pending.toLocaleString()}
                </div>
                <div className="text-sm text-text-secondary">Pending</div>
              </div>
            </div>

            {/* Advanced options */}
            <div>
              <button
                onClick={() => setShowAdvanced(!showAdvanced)}
                className="flex items-center space-x-2 text-sm font-medium text-accent hover:text-accent-hover transition-colors"
              >
                <svg
                  className={`w-4 h-4 transition-transform ${showAdvanced ? 'rotate-90' : ''}`}
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                </svg>
                <span>{ADVANCED_OPTIONS_TITLE}</span>
              </button>
            </div>

            {showAdvanced && (
              <div className="pt-4 border-t border-border">
                <WorkerSlider
                  value={maxWorkers}
                  onChange={setMaxWorkers}
                />
              </div>
            )}

            {/* Start button */}
            <div className="pt-4">
              <Button
                variant="primary"
                size="lg"
                fullWidth
                onClick={startDescriptions}
                disabled={isStarting || stats.pending === 0}
              >
                {isStarting
                  ? 'Starting Job...'
                  : stats.pending === 0
                    ? 'All Images Described'
                    : `Generate ${stats.pending} Descriptions`}
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Recent jobs */}
      <div>
        <h2 className="text-card-title text-text mb-4">Recent Description Jobs</h2>
        <div className="space-y-3">
          {recentJobs.map((job) => (
            <Card key={job.id} padding="md">
              <div className="flex items-center justify-between">
                <div className="flex-1">
                  <div className="flex items-center space-x-3 mb-1">
                    <span className="text-sm font-medium text-text">
                      {job.job_type}
                    </span>
                    <Badge variant={
                      job.status === 'completed' ? 'success' :
                      job.status === 'failed' ? 'error' :
                      job.status === 'running' ? 'accent' : 'default'
                    }>
                      {job.status}
                    </Badge>
                  </div>
                  <p className="text-xs text-text-tertiary">
                    {new Date(job.created_at).toLocaleString()}
                  </p>
                </div>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => window.location.href = '/jobs'}
                >
                  View Details
                </Button>
              </div>
            </Card>
          ))}
        </div>
      </div>
    </div>
  );
}
```

### Step 2: Test Descriptions page

Navigate to `/descriptions` and verify:
- Stats cards display correctly
- Advanced options toggle works
- Button states (enabled/disabled) work correctly
- Recent jobs list styled properly

Expected: Clean card-based descriptions interface

### Step 3: Commit Descriptions redesign

```bash
git add apps/visualizer/frontend/src/pages/DescriptionsPage.tsx
git commit -m "feat(frontend): redesign Descriptions page with Notion-style layout"
```

---

## Task 9: Redesign Jobs Page

**Files:**
- Modify: `apps/visualizer/frontend/src/pages/JobsPage.tsx`

### Step 1: Update Jobs page with Notion table styling

Modify the render section of `apps/visualizer/frontend/src/pages/JobsPage.tsx`:

```typescript
  // ... (add imports)
  import { Card } from '../components/ui/Card';
  import { Badge } from '../components/ui/Badge';
  import { Button } from '../components/ui/Button';

  // ... (keep existing logic)

  return (
    <div className="space-y-6">
      {/* Page header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-section text-text mb-2">
            Job Queue
          </h1>
          <p className="text-text-secondary">
            Monitor and manage background processing jobs
          </p>
        </div>
        
        <Button variant="secondary" onClick={loadJobs}>
          <svg className="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
          </svg>
          Refresh
        </Button>
      </div>

      {/* Jobs table card */}
      <Card padding="none">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead className="border-b border-border">
              <tr className="bg-surface">
                <th className="px-6 py-3 text-left text-xs font-medium text-text-secondary uppercase tracking-wider">
                  Type
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-text-secondary uppercase tracking-wider">
                  Status
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-text-secondary uppercase tracking-wider">
                  Created
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-text-secondary uppercase tracking-wider">
                  Progress
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-text-secondary uppercase tracking-wider">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {jobs.map((job) => (
                <tr
                  key={job.id}
                  className="hover:bg-surface transition-colors"
                >
                  <td className="px-6 py-4 whitespace-nowrap">
                    <div className="text-sm font-medium text-text">
                      {job.job_type}
                    </div>
                    <div className="text-xs text-text-tertiary">
                      {job.id.substring(0, 8)}
                    </div>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <Badge variant={
                      job.status === 'completed' ? 'success' :
                      job.status === 'failed' ? 'error' :
                      job.status === 'running' ? 'accent' : 'default'
                    }>
                      {job.status}
                    </Badge>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-text-secondary">
                    {new Date(job.created_at).toLocaleString()}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    {job.status === 'running' && (
                      <div className="w-full bg-surface rounded-full h-2">
                        <div
                          className="bg-accent h-2 rounded-full transition-all duration-300"
                          style={{ width: `${(job.progress || 0) * 100}%` }}
                        />
                      </div>
                    )}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-right text-sm">
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => window.alert(`View job ${job.id}`)}
                    >
                      Details
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      {/* Empty state */}
      {jobs.length === 0 && !loading && (
        <Card padding="lg">
          <div className="text-center py-12">
            <svg
              className="mx-auto h-12 w-12 text-text-tertiary"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2"
              />
            </svg>
            <h3 className="mt-2 text-sm font-medium text-text">No jobs</h3>
            <p className="mt-1 text-sm text-text-secondary">
              Start a matching or description job to see it here
            </p>
          </div>
        </Card>
      )}
    </div>
  );
}
```

### Step 2: Test Jobs page

Navigate to `/jobs` and verify:
- Table displays with Notion styling
- Badge colors match job status
- Hover effects on table rows
- Progress bars display for running jobs
- Empty state displays when no jobs

Expected: Clean table with Notion aesthetic

### Step 3: Commit Jobs redesign

```bash
git add apps/visualizer/frontend/src/pages/JobsPage.tsx
git commit -m "feat(frontend): redesign Jobs page with Notion-style table and badges"
```

---

## Task 10: Redesign Providers Page

**Files:**
- Modify: `apps/visualizer/frontend/src/pages/ProvidersPage.tsx`

### Step 1: Update Providers page with card grid

Modify the render section of `apps/visualizer/frontend/src/pages/ProvidersPage.tsx`:

```typescript
  // ... (add imports)
  import { Card, CardHeader, CardTitle, CardContent } from '../components/ui/Card';
  import { Badge } from '../components/ui/Badge';
  import { Button } from '../components/ui/Button';

  // ... (keep existing logic)

  return (
    <div className="space-y-6">
      {/* Page header */}
      <div>
        <h1 className="text-section text-text mb-2">
          AI Providers
        </h1>
        <p className="text-text-secondary">
          Configure AI model providers for vision matching and descriptions
        </p>
      </div>

      {/* Providers grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {providers.map((provider) => (
          <Card key={provider.id} padding="lg">
            <CardHeader>
              <div className="flex items-start justify-between">
                <CardTitle>{provider.name}</CardTitle>
                <Badge variant={provider.available ? 'success' : 'default'}>
                  {provider.available ? 'Available' : 'Unavailable'}
                </Badge>
              </div>
            </CardHeader>
            
            <CardContent>
              <div className="space-y-4">
                {/* Provider info */}
                <div>
                  <p className="text-sm text-text-secondary mb-2">
                    {provider.description || 'AI model provider'}
                  </p>
                  
                  {provider.base_url && (
                    <p className="text-xs text-text-tertiary font-mono">
                      {provider.base_url}
                    </p>
                  )}
                </div>

                {/* Models list */}
                {provider.models && provider.models.length > 0 && (
                  <div>
                    <h4 className="text-sm font-medium text-text mb-2">
                      Available Models ({provider.models.length})
                    </h4>
                    <div className="space-y-2 max-h-40 overflow-y-auto">
                      {provider.models.map((model: any) => (
                        <div
                          key={model.id}
                          className="flex items-center justify-between p-2 bg-surface rounded-base text-sm"
                        >
                          <span className="text-text font-mono text-xs truncate">
                            {model.id}
                          </span>
                          {model.vision && (
                            <Badge variant="accent">Vision</Badge>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Actions */}
                <div className="pt-4 border-t border-border">
                  <Button
                    variant="secondary"
                    size="sm"
                    fullWidth
                    onClick={() => window.alert(`Configure ${provider.name}`)}
                  >
                    Configure
                  </Button>
                </div>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Loading state */}
      {loading && (
        <div className="flex items-center justify-center py-12">
          <div className="text-text-secondary">Loading providers...</div>
        </div>
      )}
    </div>
  );
}
```

### Step 2: Test Providers page

Navigate to `/providers` and verify:
- Provider cards display in grid
- Available/Unavailable badges show correctly
- Models list is scrollable
- Vision badges appear on vision models
- Card hover effects work

Expected: Clean provider configuration interface

### Step 3: Commit Providers redesign

```bash
git add apps/visualizer/frontend/src/pages/ProvidersPage.tsx
git commit -m "feat(frontend): redesign Providers page with Notion-style card grid"
```

---

## Task 11: Update Pagination Component

**Files:**
- Modify: `apps/visualizer/frontend/src/components/ui/Pagination.tsx`

### Step 1: Redesign Pagination with Notion styling

Replace content of `apps/visualizer/frontend/src/components/ui/Pagination.tsx`:

```typescript
interface PaginationProps {
  currentPage: number;
  totalPages: number;
  onPageChange: (page: number) => void;
}

export function Pagination({ currentPage, totalPages, onPageChange }: PaginationProps) {
  const pages = Array.from({ length: totalPages }, (_, i) => i + 1);
  
  // Show max 7 pages: [1] ... [n-1] [n] [n+1] ... [total]
  let visiblePages = pages;
  if (totalPages > 7) {
    if (currentPage <= 3) {
      visiblePages = [...pages.slice(0, 5), -1, totalPages];
    } else if (currentPage >= totalPages - 2) {
      visiblePages = [1, -1, ...pages.slice(totalPages - 5)];
    } else {
      visiblePages = [
        1,
        -1,
        currentPage - 1,
        currentPage,
        currentPage + 1,
        -1,
        totalPages,
      ];
    }
  }

  return (
    <div className="flex items-center space-x-2">
      {/* Previous button */}
      <button
        onClick={() => onPageChange(currentPage - 1)}
        disabled={currentPage === 1}
        className="px-3 py-2 rounded-base border border-border bg-bg text-text-secondary hover:bg-surface hover:text-text disabled:opacity-50 disabled:cursor-not-allowed transition-all"
        aria-label="Previous page"
      >
        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
        </svg>
      </button>

      {/* Page numbers */}
      {visiblePages.map((page, index) =>
        page === -1 ? (
          <span
            key={`ellipsis-${index}`}
            className="px-3 py-2 text-text-tertiary"
          >
            ...
          </span>
        ) : (
          <button
            key={page}
            onClick={() => onPageChange(page)}
            className={`px-3 py-2 rounded-base border transition-all
              ${
                page === currentPage
                  ? 'bg-accent-light text-accent border-accent font-medium'
                  : 'border-border bg-bg text-text-secondary hover:bg-surface hover:text-text'
              }
            `}
          >
            {page}
          </button>
        )
      )}

      {/* Next button */}
      <button
        onClick={() => onPageChange(currentPage + 1)}
        disabled={currentPage === totalPages}
        className="px-3 py-2 rounded-base border border-border bg-bg text-text-secondary hover:bg-surface hover:text-text disabled:opacity-50 disabled:cursor-not-allowed transition-all"
        aria-label="Next page"
      >
        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
        </svg>
      </button>
    </div>
  );
}
```

### Step 2: Test pagination on Instagram page

Navigate to `/instagram` and verify:
- Pagination displays at bottom of page
- Previous/Next buttons work
- Page numbers highlight current page
- Ellipsis shows for large page counts
- Hover states work correctly

Expected: Clean Notion-style pagination

### Step 3: Commit pagination redesign

```bash
git add apps/visualizer/frontend/src/components/ui/Pagination.tsx
git commit -m "feat(frontend): redesign Pagination with Notion-style controls"
```

---

## Task 12: Update Modal Component

**Files:**
- Modify: `apps/visualizer/frontend/src/components/instagram/ImageDetailsModal.tsx`

### Step 1: Redesign modal with Notion styling

Replace content of `apps/visualizer/frontend/src/components/instagram/ImageDetailsModal.tsx`:

```typescript
import { useEffect } from 'react';
import type { InstagramImage } from '../../services/api';
import { Badge } from '../ui/Badge';

interface ImageDetailsModalProps {
  image: InstagramImage;
  onClose: () => void;
}

export function ImageDetailsModal({ image, onClose }: ImageDetailsModalProps) {
  // Close on Escape key
  useEffect(() => {
    const handleEsc = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', handleEsc);
    return () => window.removeEventListener('keydown', handleEsc);
  }, [onClose]);

  const dateDisplay = image.created_at
    ? new Date(image.created_at).toLocaleString()
    : image.date_folder
      ? `${image.date_folder.slice(0, 4)}/${image.date_folder.slice(4, 6)} (estimated)`
      : 'No date';

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm"
      onClick={onClose}
    >
      <div
        className="relative w-full max-w-4xl max-h-[90vh] bg-bg rounded-card shadow-deep overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Close button */}
        <button
          onClick={onClose}
          className="absolute top-4 right-4 z-10 p-2 rounded-base bg-surface/80 backdrop-blur-sm border border-border hover:bg-surface-hover transition-all"
          aria-label="Close modal"
        >
          <svg className="w-5 h-5 text-text" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>

        <div className="grid md:grid-cols-2 gap-6 p-6 overflow-y-auto max-h-[90vh]">
          {/* Image */}
          <div className="aspect-square bg-surface rounded-base overflow-hidden">
            <img
              src={`/api/images/instagram/${encodeURIComponent(image.key)}/thumbnail`}
              alt={image.filename}
              className="w-full h-full object-contain"
            />
          </div>

          {/* Details */}
          <div className="space-y-6">
            <div>
              <h2 className="text-card-title text-text mb-2">
                Image Details
              </h2>
              <div className="flex flex-wrap gap-2">
                {image.matched_catalog_key && (
                  <Badge variant="success">Matched</Badge>
                )}
                {image.description && (
                  <Badge variant="accent">Described</Badge>
                )}
                {image.processed && (
                  <Badge variant="default">Processed</Badge>
                )}
              </div>
            </div>

            {/* Metadata grid */}
            <div className="space-y-3">
              <MetadataRow label="Filename" value={image.filename} />
              <MetadataRow label="Folder" value={image.instagram_folder} />
              <MetadataRow label="Source" value={image.source_folder} />
              <MetadataRow label="Date" value={dateDisplay} />
              {image.image_hash && (
                <MetadataRow
                  label="Image Hash"
                  value={image.image_hash}
                  mono
                />
              )}
              {image.matched_catalog_key && (
                <MetadataRow
                  label="Catalog Match"
                  value={image.matched_catalog_key}
                  mono
                />
              )}
            </div>

            {/* Description */}
            {image.description && (
              <div className="p-4 bg-surface rounded-base border border-border">
                <h3 className="text-sm font-medium text-text mb-2">
                  AI Description
                </h3>
                <p className="text-sm text-text-secondary">
                  {image.description}
                </p>
              </div>
            )}

            {/* EXIF data */}
            {image.exif_data && (
              <div>
                <h3 className="text-sm font-medium text-text mb-2">
                  EXIF Data
                </h3>
                <div className="space-y-2">
                  {image.exif_data.device_id && (
                    <MetadataRow label="Device" value={image.exif_data.device_id} />
                  )}
                  {image.exif_data.lens_model && (
                    <MetadataRow label="Lens" value={image.exif_data.lens_model} />
                  )}
                  {image.exif_data.latitude && image.exif_data.longitude && (
                    <MetadataRow
                      label="Location"
                      value={`${image.exif_data.latitude.toFixed(6)}, ${image.exif_data.longitude.toFixed(6)}`}
                    />
                  )}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

function MetadataRow({
  label,
  value,
  mono = false,
}: {
  label: string;
  value: string;
  mono?: boolean;
}) {
  return (
    <div className="flex justify-between items-start py-2 border-b border-border last:border-0">
      <span className="text-sm text-text-secondary">{label}</span>
      <span className={`text-sm text-text text-right ${mono ? 'font-mono' : ''}`}>
        {value}
      </span>
    </div>
  );
}
```

### Step 2: Test modal on Instagram page

Navigate to `/instagram`, click any image, and verify:
- Modal opens with Notion styling
- Image displays correctly
- Metadata grid displays
- Status badges show
- Close button and ESC key work
- Backdrop blur effect visible
- Modal scrolls if content overflows

Expected: Clean, professional modal

### Step 3: Commit modal redesign

```bash
git add apps/visualizer/frontend/src/components/instagram/ImageDetailsModal.tsx
git commit -m "feat(frontend): redesign ImageDetailsModal with Notion-style layout"
```

---

## Task 13: Create DESIGN.md Documentation

**Files:**
- Create: `apps/visualizer/frontend/DESIGN.md`

### Step 1: Write comprehensive design system documentation

Create `apps/visualizer/frontend/DESIGN.md`:

```markdown
# Design System Inspiration of Lightroom Tagger

## 1. Visual Theme & Atmosphere

Lightroom Tagger's UI is built on Notion's warm minimalism philosophy — a clean canvas that prioritizes content while maintaining approachable sophistication. The design system uses warm neutrals (`#f6f5f4` warm white, `rgba(0,0,0,0.95)` near-black) instead of cold grays, creating a tactile, paper-like quality that feels premium yet accessible.

The interface supports dual modes: light-first for general use, dark mode for photo editing contexts. Both modes maintain the same warm undertones, creating visual continuity across theme switches. Ultra-thin borders (`1px solid rgba(0,0,0,0.1)` in light, `rgba(255,255,255,0.1)` in dark) provide structure without weight, following Notion's "whisper-border" philosophy.

**Key Characteristics:**
- Inter font family (same as Notion) with standard weights (400, 500, 600, 700)
- Warm neutral palette with yellow-brown undertones
- Single accent color: Notion Blue (`#0075de` light, `#62aef0` dark)
- Ultra-thin borders throughout — structure without visual noise
- Multi-layer shadow system with sub-0.05 opacity for barely-there depth
- 8px base spacing with organic, non-rigid scale
- Dual mode: Light-first (warm white) + Dark mode (warm dark)

## 2. Color Palette & Roles

### Light Mode (Default)

**Primary Surfaces:**
- **Background** (`#ffffff`): Pure white page canvas
- **Surface** (`#f6f5f4`): Warm white surface tint — yellow undertone
- **Surface Hover** (`#f1f0ed`): Hover state for interactive surfaces

**Text Hierarchy:**
- **Text Primary** (`rgba(0,0,0,0.95)`): Near-black with micro-warmth — not pure black
- **Text Secondary** (`#615d59`): Warm gray 500 for descriptions
- **Text Tertiary** (`#a39e98`): Warm gray 300 for de-emphasized content

**Borders & Dividers:**
- **Border** (`rgba(0,0,0,0.1)`): Ultra-thin whisper border
- **Border Strong** (`rgba(0,0,0,0.15)`): Slightly more visible

**Interactive:**
- **Accent** (`#0075de`): Notion Blue — primary CTA, links, active states
- **Accent Hover** (`#005bab`): Darker blue on hover
- **Accent Light** (`#f2f9ff`): Light blue tint for backgrounds

**Semantic:**
- **Success** (`#1aae39`): Completion states, positive indicators
- **Warning** (`#dd5b00`): Attention needed, caution
- **Error** (`#e03e3e`): Failure states, destructive actions

### Dark Mode

**Primary Surfaces:**
- **Background** (`#191919`): Deep warm dark
- **Surface** (`#31302e`): Warm dark surface — Notion's signature warm dark
- **Surface Hover** (`#3d3b38`): Hover state

**Text Hierarchy:**
- **Text Primary** (`#f7f6f5`): Near-white — not pure white
- **Text Secondary** (`#9b9a97`): Muted warm gray
- **Text Tertiary** (`#6f6e69`): De-emphasized

**Borders & Dividers:**
- **Border** (`rgba(255,255,255,0.1)`): Ultra-thin light border
- **Border Strong** (`rgba(255,255,255,0.15)`): Slightly more visible

**Interactive:**
- **Accent** (`#62aef0`): Light blue for dark backgrounds
- **Accent Hover** (`#97c9ff`): Lighter on hover
- **Accent Light** (`rgba(98,174,240,0.1)`): Light blue tint

**Semantic:**
- **Success** (`#2a9d99`): Teal-shifted success
- **Warning** (`#ff8c42`): Warm orange warning
- **Error** (`#ff6b6b`): Warm red error

## 3. Typography Rules

### Font Family
- **Primary**: `Inter`, with fallbacks: `-apple-system, system-ui, Segoe UI, Helvetica, Arial, sans-serif`
- Inter is loaded via Google Fonts CDN with weights 400, 500, 600, 700

### Hierarchy

| Role | Size | Weight | Line Height | Letter Spacing | Usage |
|------|------|--------|-------------|----------------|-------|
| Hero Display | 64px (4rem) | 700 | 1.0 | -2.125px | Maximum impact headlines |
| Section | 48px (3rem) | 700 | 1.0 | -1.5px | Page section titles |
| Subsection | 26px (1.63rem) | 700 | 1.23 | -0.625px | Section sub-titles |
| Card Title | 22px (1.38rem) | 700 | 1.27 | -0.25px | Card headings |
| Body Large | 20px (1.25rem) | 600 | 1.40 | -0.125px | Introductions, feature descriptions |
| Body | 16px (1rem) | 400 | 1.50 | normal | Standard reading text |
| Body Medium | 16px (1rem) | 500 | 1.50 | normal | Navigation, emphasized UI text |
| Body Semibold | 16px (1rem) | 600 | 1.50 | normal | Strong labels |
| Small | 14px (0.88rem) | 400-500 | 1.43 | -0.224px | Secondary text, captions |
| Tiny | 12px (0.75rem) | 400 | 1.33 | -0.12px | Fine print, footnotes |

### Principles
- Negative letter-spacing at display sizes (64px, 48px, 26px) creates compressed, authoritative headlines
- Standard tracking at body sizes for comfortable reading
- Three-tier weight system: 400 (reading), 500 (emphasis), 600-700 (strong emphasis)

## 4. Component Stylings

### Buttons

**Primary (Brand)**
- Background: `var(--color-accent)`
- Text: `#ffffff`
- Border: `1px solid var(--color-accent)`
- Radius: `8px` (Notion standard)
- Hover: Background shifts to `var(--color-accent-hover)`
- Focus: Ring `2px solid var(--color-accent)` with `2px` offset
- Padding: `8px 16px` (md), `6px 12px` (sm), `12px 24px` (lg)

**Secondary**
- Background: `var(--color-surface)`
- Text: `var(--color-text-primary)`
- Border: `1px solid var(--color-border)`
- Hover: Background to `var(--color-surface-hover)`

**Ghost**
- Background: `transparent`
- Text: `var(--color-text-secondary)`
- Border: `1px solid transparent`
- Hover: Background to `var(--color-surface)`

**Danger**
- Background: `var(--color-error)`
- Text: `#ffffff`
- Border: `1px solid var(--color-error)`
- Hover: Opacity `0.9`

### Cards & Containers
- Background: `var(--color-background)`
- Border: `1px solid var(--color-border)`
- Radius: `12px` (cards), `8px` (small components)
- Shadow: `rgba(0,0,0,0.04) 0px 4px 18px, rgba(0,0,0,0.027) 0px 2.025px 7.84688px, rgba(0,0,0,0.02) 0px 0.8px 2.925px, rgba(0,0,0,0.01) 0px 0.175px 1.04062px`
- Hover: Shadow intensifies to deep shadow, border to `var(--color-border-strong)`
- Padding: `16px` (md), `12px` (sm), `24px` (lg)

### Inputs & Forms

**Text Input**
- Background: `var(--color-background)`
- Text: `var(--color-text-primary)`
- Placeholder: `var(--color-text-tertiary)`
- Border: `1px solid var(--color-border)`
- Padding: `8px 12px`
- Radius: `8px`
- Focus: Ring `2px solid var(--color-accent)`, border `transparent`
- Hover: Border to `var(--color-border-strong)`

**Select Dropdown**
- Same styling as text input
- Arrow icon in `var(--color-text-secondary)`

**Checkbox**
- Size: `16px x 16px`
- Border: `1px solid var(--color-border)`
- Radius: `4px`
- Checked: Background `var(--color-accent)`, checkmark white

### Badges & Pills

**Default**
- Background: `var(--color-surface)`
- Text: `var(--color-text-secondary)`
- Border: `1px solid var(--color-border)`
- Radius: `9999px` (full pill)
- Padding: `2px 10px`
- Font: `12px`, weight `500`

**Success**
- Background: `rgba(26,174,57,0.1)` (light) / `rgba(42,157,153,0.2)` (dark)
- Text: `var(--color-success)`
- Border: Success-tinted

**Warning**
- Background: `rgba(221,91,0,0.1)` (light) / `rgba(255,140,66,0.2)` (dark)
- Text: `var(--color-warning)`

**Error**
- Background: `rgba(224,62,62,0.1)` (light) / `rgba(255,107,107,0.2)` (dark)
- Text: `var(--color-error)`

**Accent**
- Background: `var(--color-accent-light)`
- Text: `var(--color-accent)`
- Border: Accent-tinted

## 5. Layout Principles

### Spacing Scale (8px base)
- **4px** (`0.5`): Tight spacing, inline elements
- **8px** (`1`): Standard small gap
- **12px** (`1.5`): Comfortable small gap
- **16px** (`2`): Standard medium gap
- **24px** (`3`): Comfortable medium gap
- **32px** (`4`): Large section gap
- **48px** (`6`): Extra large section gap

### Grid & Containers
- Max width: `1280px` (`7xl`) for main content
- Responsive padding: `16px` (mobile), `24px` (tablet), `32px` (desktop)
- Card grids: 1 column (mobile), 2 columns (tablet), 3-4 columns (desktop)

### Whitespace Philosophy
- Let content breathe — generous space between major sections (32px-48px)
- Tight spacing within related groups (8px-12px)
- Never flush content to edges — always maintain container padding

## 6. Depth & Elevation

### Shadow System

**Card Shadow (default elevation)**
```
rgba(0,0,0,0.04) 0px 4px 18px,
rgba(0,0,0,0.027) 0px 2.025px 7.84688px,
rgba(0,0,0,0.02) 0px 0.8px 2.925px,
rgba(0,0,0,0.01) 0px 0.175px 1.04062px
```
Multi-layer stack with cumulative opacity < 0.05 — barely-there depth

**Deep Shadow (modal, featured content)**
```
rgba(0,0,0,0.01) 0px 1px 3px,
rgba(0,0,0,0.02) 0px 3px 7px,
rgba(0,0,0,0.02) 0px 7px 15px,
rgba(0,0,0,0.04) 0px 14px 28px,
rgba(0,0,0,0.05) 0px 23px 52px
```
Five-layer elevation for maximum depth without harshness

### Border Hierarchy
- Ultra-thin (`rgba(0,0,0,0.1)` / `rgba(255,255,255,0.1)`): Default division
- Strong (`rgba(0,0,0,0.15)` / `rgba(255,255,255,0.15)`): Emphasis, hover states
- Solid (`var(--color-text-primary)`): Maximum contrast (rarely used)

## 7. Do's and Don'ts

### Do
- Use warm neutrals consistently — never cold grays
- Apply ultra-thin borders for subtle structure
- Maintain 8px spacing rhythm throughout
- Use single accent color (Notion Blue) for all interactive elements
- Test both light and dark modes for visual consistency
- Let content breathe with generous whitespace
- Use multi-layer shadows for depth without harshness

### Don't
- Don't use pure black or pure white for text (use near-black/near-white)
- Don't mix accent colors — stick to Notion Blue
- Don't use heavy borders or drop shadows
- Don't create custom spacing values outside the 8px scale
- Don't override theme colors manually — use CSS variables
- Don't forget hover and focus states on interactive elements
- Don't use solid backgrounds without borders (cards need subtle borders)

## 8. Responsive Behavior

### Breakpoints (Tailwind defaults)
- `sm`: 640px (mobile landscape, small tablets)
- `md`: 768px (tablets)
- `lg`: 1024px (desktop)
- `xl`: 1280px (large desktop)

### Responsive Patterns

**Navigation**
- Desktop: Horizontal nav in header
- Mobile: Scrollable horizontal nav below header

**Card Grids**
- Mobile: 1 column
- Tablet (md): 2 columns
- Desktop (lg): 3 columns
- Large (xl): 4 columns (where appropriate)

**Typography**
- Display sizes scale down 10-15% on mobile
- Maintain readable line lengths (max 70-80 characters)
- Increase line-height slightly on small screens for readability

**Touch Targets**
- Minimum `44px x 44px` for interactive elements on mobile
- Add padding to compensate for smaller visual sizes

## 9. Agent Prompt Guide

### Quick Color Reference

**Light Mode**
- Background: `#ffffff`
- Surface: `#f6f5f4`
- Text: `rgba(0,0,0,0.95)`
- Accent: `#0075de`
- Border: `rgba(0,0,0,0.1)`

**Dark Mode**
- Background: `#191919`
- Surface: `#31302e`
- Text: `#f7f6f5`
- Accent: `#62aef0`
- Border: `rgba(255,255,255,0.1)`

### Ready-to-Use Prompts

**"Build a page using Lightroom Tagger's design system"**
→ Use warm neutrals, Inter font, Notion Blue accent, ultra-thin borders, 8px spacing

**"Create a card component"**
→ `bg-bg border border-border rounded-card shadow-card p-4`

**"Style a primary button"**
→ `bg-accent text-white hover:bg-accent-hover rounded-base px-4 py-2 font-medium`

**"Add a status badge"**
→ Use `<Badge variant="success|warning|error|accent">` component

**"Create a data table"**
→ Card wrapper, ultra-thin borders between rows, hover states on `tr` with `bg-surface`

### Component Class Patterns

```tsx
// Button
className="bg-accent text-white hover:bg-accent-hover rounded-base px-4 py-2 font-medium transition-all focus:ring-2 focus:ring-accent"

// Card
className="bg-bg border border-border rounded-card shadow-card p-4 hover:shadow-deep hover:border-border-strong transition-all"

// Input
className="px-3 py-2 rounded-base border border-border bg-bg text-text focus:ring-2 focus:ring-accent hover:border-border-strong transition-all"

// Badge
className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium border bg-accent-light text-accent border-blue-200"
```

---

## Implementation Notes

This design system is implemented using:
- **React** + **TypeScript** for components
- **Tailwind CSS** for styling with custom theme configuration
- **CSS Variables** (`--color-*`) for runtime theme switching
- **ThemeContext** for dark mode state management
- **Inter font** from Google Fonts CDN

All components follow DRY principles with reusable base components:
- `Button`, `Card`, `Badge`, `Input`, `ThemeToggle`
- Consistent props API across components
- TypeScript interfaces for type safety
