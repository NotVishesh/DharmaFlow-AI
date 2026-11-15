import path from 'path';

/** @type {import('tailwindcss').Config} */
export default {
  content: [
    path.join(__dirname, 'index.html'),
    path.join(__dirname, 'src/**/*.{js,ts,jsx,tsx}'),
  ],
  theme: {
    extend: {
      colors: {
        dharma: {
          gold: '#f59e0b',
          crimson: '#e11d48',
          dark: '#090d16',
          card: '#111827',
          border: '#1f2937',
        }
      }
    },
  },
  plugins: [],
}
