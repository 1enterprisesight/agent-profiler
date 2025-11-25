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
          50: '#f0f9ff',
          100: '#e0f2fe',
          500: '#0ea5e9',
          600: '#0284c7',
          700: '#0369a1',
        },
        agent: {
          orchestrator: '#8b5cf6',
          data: '#10b981',
          sql: '#3b82f6',
          semantic: '#f59e0b',
          pattern: '#ec4899',
          segment: '#14b8a6',
          benchmark: '#f97316',
          recommendation: '#06b6d4',
        }
      },
    },
  },
  plugins: [],
}
