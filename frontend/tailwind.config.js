/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Manrope', 'sans-serif'],
      },
      colors: {
        blood: {
          50: '#fef2f2',
          100: '#ffe1e1',
          500: '#e50914',
          600: '#b80710',
          700: '#99060c',
          800: '#660408',
          900: '#330204',
          950: '#1a0102',
        },
        slate: {
          800: '#1c1c1e',
          850: '#161618',
          900: '#111111',
          950: '#0a0a0c',
        }
      },
      animation: {
        'pulse-fast': 'pulse 1s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'glow-red': 'glowRed 2s ease-in-out infinite alternate',
        'float': 'float 6s ease-in-out infinite',
      },
      keyframes: {
        glowRed: {
          '0%': { boxShadow: '0 0 10px rgba(229, 9, 20, 0.2)' },
          '100%': { boxShadow: '0 0 30px rgba(229, 9, 20, 0.6)' },
        },
        float: {
          '0%, 100%': { transform: 'translateY(0)' },
          '50%': { transform: 'translateY(-20px)' },
        }
      }
    },
  },
  plugins: [],
}
