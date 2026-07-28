/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ['./src/renderer/index.html', './src/renderer/src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        background: 'hsl(var(--background) / <alpha-value>)',
        foreground: 'hsl(var(--foreground) / <alpha-value>)',
        surface: {
          DEFAULT: 'hsl(var(--surface) / <alpha-value>)',
          hover: 'hsl(var(--surface-hover) / <alpha-value>)',
          elevated: 'hsl(var(--surface-elevated) / <alpha-value>)'
        },
        muted: { DEFAULT: 'hsl(var(--muted) / <alpha-value>)', foreground: 'hsl(var(--muted-foreground) / <alpha-value>)' },
        primary: { DEFAULT: 'hsl(var(--primary) / <alpha-value>)', foreground: 'hsl(var(--primary-foreground) / <alpha-value>)' },
        border: 'hsl(var(--border) / <alpha-value>)',
        success: 'hsl(var(--success) / <alpha-value>)',
        destructive: 'hsl(var(--destructive) / <alpha-value>)'
      },
      borderRadius: { xl: '12px', '2xl': '16px', '3xl': '22px' },
      boxShadow: {
        soft: '0 1px 2px hsl(240 20% 2% / .16), 0 16px 40px -22px hsl(240 20% 2% / .8)',
        glow: '0 0 0 1px hsl(var(--primary) / .24), 0 12px 30px -14px hsl(var(--primary) / .85)'
      },
      fontFamily: { sans: ['Inter', 'system-ui', 'sans-serif'] }
    }
  },
  plugins: []
}
