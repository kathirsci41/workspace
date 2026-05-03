/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      fontFamily: {
        sans: ['"Inter Tight"', 'system-ui', 'sans-serif'],
        display: ['Fraunces', 'Georgia', 'serif'],
        mono: ['"JetBrains Mono"', 'ui-monospace', 'monospace'],
      },
      colors: {
        ink: '#1C1B1A',
        paper: '#FAF7F1',
        accent: '#3B4FA3',
        signal: '#C2410C',
        veil: '#E8E1D3',
      },
    },
  },
  plugins: [],
};
