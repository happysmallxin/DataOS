/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        dataos: {
          50: '#f0f5ff',
          100: '#e0ebff',
          200: '#b8d4fe',
          300: '#85b8fd',
          400: '#4e94fa',
          500: '#2563eb',
          600: '#1d4ed8',
          700: '#1e40af',
          800: '#1e3a8a',
          900: '#1e3266',
        },
      },
    },
  },
  plugins: [],
}
