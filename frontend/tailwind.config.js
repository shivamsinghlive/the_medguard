/** @type {import('tailwindcss').Config} */
// Daylight-lab palette. Every color reads a CSS variable (RGB channels, see index.css)
// so light and dark mode switch together without per-class dark: variants.
const v = (name) => `rgb(var(--${name}) / <alpha-value>)`
const scale = (prefix, steps) => Object.fromEntries(steps.map((s) => [s, v(`${prefix}-${s}`)]))

export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      fontFamily: {
        sans: ['"Instrument Sans"', 'ui-sans-serif', 'system-ui', '-apple-system', '"Segoe UI"', 'sans-serif'],
        display: ['"Bricolage Grotesque"', '"Instrument Sans"', 'ui-sans-serif', 'system-ui', 'sans-serif'],
      },
      colors: {
        paper: v('paper'),
        card: v('card'),
        line: v('slate-200'),
        ink: scale('ink', [100, 300, 500, 700, 900]),
        slate: scale('slate', [50, 100, 200, 300, 400, 500, 600, 700, 800]),
        brand: scale('brand', [50, 100, 200, 300, 500, 600, 700]),
        teal: scale('teal', [50, 500, 700]),
        review: scale('review', [50, 100, 200, 400, 500, 700]),
      },
      boxShadow: {
        card: '0 1px 2px rgb(var(--shadow) / .05), 0 10px 28px -14px rgb(var(--shadow) / .22)',
        lift: '0 18px 40px -18px rgb(var(--shadow) / .35)',
      },
      keyframes: {
        rise: { from: { opacity: '0', transform: 'translateY(6px)' }, to: { opacity: '1', transform: 'none' } },
        stamp: { from: { opacity: '0', transform: 'scale(1.6) rotate(-3deg)' }, to: { opacity: '1', transform: 'scale(1) rotate(-3deg)' } },
        shimmer: { from: { backgroundPosition: '-400px 0' }, to: { backgroundPosition: '400px 0' } },
      },
      animation: {
        rise: 'rise .35s ease-out both',
        stamp: 'stamp .45s cubic-bezier(.2,1.4,.4,1) both',
        shimmer: 'shimmer 1.2s linear infinite',
      },
    },
  },
  plugins: [],
}
