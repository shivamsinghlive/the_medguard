/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      fontFamily: { sans: ['Inter', 'ui-sans-serif', 'system-ui', 'Segoe UI', 'sans-serif'] },
      colors: {
        ink: { 900: '#0f172a', 700: '#334155', 500: '#64748b', 300: '#cbd5e1', 100: '#f1f5f9' },
        brand: { 50: '#eef6ff', 100: '#d9eaff', 500: '#3b6cf6', 600: '#2f56d9', 700: '#2645b0' },
        review: { 50: '#fff7ed', 500: '#f97316', 700: '#c2410c' },
        okay: { 50: '#ecfdf5', 500: '#10b981', 700: '#047857' },
        unknown: { 50: '#f8fafc', 500: '#94a3b8' },
      },
      boxShadow: { card: '0 1px 2px rgba(15,23,42,.04), 0 8px 24px -12px rgba(15,23,42,.12)' },
    },
  },
  plugins: [],
}
