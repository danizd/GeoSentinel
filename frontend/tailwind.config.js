/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        'bg-base': '#0a0e1a',
        'bg-panel': '#0f1525',
        'bg-glass': 'rgba(15,21,37,0.75)',
        'border-glow': 'rgba(56,189,248,0.3)',
        'accent-blue': '#38bdf8',
        'accent-amber': '#fbbf24',
        'accent-red': '#ef4444',
        'accent-green': '#22c55e',
        'text-primary': '#e2e8f0',
        'text-secondary': '#64748b',
      },
      fontFamily: {
        mono: ['JetBrains Mono', 'monospace'],
        sans: ['Inter', 'system-ui', 'sans-serif'],
      },
    },
  },
  plugins: [],
}