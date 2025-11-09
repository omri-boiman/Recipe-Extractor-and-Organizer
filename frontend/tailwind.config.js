/** @type {import('tailwindcss').Config} */
export default {
  darkMode: 'class',
  content: [
    './index.html',
    './src/**/*.{ts,tsx}',
  ],
  theme: {
    extend: {
      colors: {
        brand: {
          50: '#ecfdf5',
          100: '#d1fae5',
          200: '#a7f3d0',
          300: '#6ee7b7',
          400: '#34d399',
          500: '#10b981',
          600: '#059669',
          700: '#047857',
          800: '#065f46',
          900: '#064e3b',
        }
      },
      boxShadow: {
        'soft': '0 1px 2px rgba(0,0,0,0.06), 0 4px 12px rgba(0,0,0,0.06)',
      },
      backdropBlur: {
        xs: '2px',
      },
      keyframes: {
        'fade-in': {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' }
        },
        'scale-in': {
          '0%': { transform: 'scale(0.98)', opacity: '0' },
          '100%': { transform: 'scale(1)', opacity: '1' }
        },
        'typing': {
          '0%, 20%': { transform: 'translateY(0)', opacity: '0.4' },
          '50%': { transform: 'translateY(-2px)', opacity: '1' },
          '80%, 100%': { transform: 'translateY(0)', opacity: '0.4' }
        }
      },
      animation: {
        'fade-in': 'fade-in 200ms ease-out',
        'scale-in': 'scale-in 200ms ease-out',
        'typing': 'typing 1s ease-in-out infinite',
      }
    },
  },
  plugins: [],
}
