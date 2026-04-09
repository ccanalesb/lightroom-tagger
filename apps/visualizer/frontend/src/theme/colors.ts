export const colors = {
  light: {
    background: '#ffffff',
    surface: '#f6f5f4',
    surfaceHover: '#f1f0ed',
    textPrimary: 'rgba(0,0,0,0.95)',
    textSecondary: '#615d59',
    textTertiary: '#a39e98',
    border: 'rgba(0,0,0,0.1)',
    borderStrong: 'rgba(0,0,0,0.15)',
    accent: '#0075de',
    accentHover: '#005bab',
    accentLight: '#f2f9ff',
    success: '#1aae39',
    warning: '#dd5b00',
    error: '#e03e3e',
  },
  dark: {
    background: '#191919',
    surface: '#31302e',
    surfaceHover: '#3d3b38',
    textPrimary: '#f7f6f5',
    textSecondary: '#9b9a97',
    textTertiary: '#6f6e69',
    border: 'rgba(255,255,255,0.1)',
    borderStrong: 'rgba(255,255,255,0.15)',
    accent: '#62aef0',
    accentHover: '#97c9ff',
    accentLight: 'rgba(98,174,240,0.1)',
    success: '#2a9d99',
    warning: '#ff8c42',
    error: '#ff6b6b',
  },
} as const;

export type ThemeColors = typeof colors.light;
export type ThemeMode = 'light' | 'dark';
