/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        bg: '#f8fafc',
        ink: {
          900: '#1e293b',
          500: '#64748b',
          300: '#cbd5e1',
        },
        border: '#e2e8f0',
        brand: {
          DEFAULT: '#4a90d9',
          50: '#eff6fc',
          100: '#dbeaf6',
          600: '#3f7ec0',
        },
        leaf: {
          DEFAULT: '#52a882',
          50: '#eef7f2',
          100: '#d8ecdf',
          600: '#41936e',
        },
        sand: {
          DEFAULT: '#e8b84b',
          50: '#fbf5e6',
          100: '#f6e8c0',
          600: '#cea035',
        },
      },
      fontFamily: {
        sans: ['Inter', 'Noto Sans SC', 'system-ui', 'sans-serif'],
      },
      boxShadow: {
        card: '0 1px 2px 0 rgb(15 23 42 / 0.04), 0 1px 3px 0 rgb(15 23 42 / 0.06)',
        cardHover: '0 6px 18px -6px rgb(15 23 42 / 0.18), 0 2px 6px -2px rgb(15 23 42 / 0.06)',
      },
    },
  },
  plugins: [],
}
