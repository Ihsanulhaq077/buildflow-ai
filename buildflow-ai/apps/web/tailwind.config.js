/** @type {import('tailwindcss').Config} */
export default {
  content: [
    './index.html',
    './src/**/*.{js,jsx}',
  ],
  theme: {
    extend: {
      colors: {
        ink: {
          50: '#f6f7f9',
          100: '#eef1f5',
          200: '#dde3ec',
          300: '#c4ccda',
          400: '#9aa6b8',
          500: '#6b7689',
          600: '#4a5468',
          700: '#2c3340',
          800: '#1a1f2b',
          900: '#0d1117',
        },
        brand: {
          50: '#eef4ff',
          100: '#d9e6ff',
          200: '#b3ccff',
          300: '#7eb0ff',
          400: '#4a8cff',
          500: '#2f6bf0',
          600: '#1e4fd0',
          700: '#1a3fa8',
          800: '#1c3573',
          900: '#1e2f55',
        },
        accent: {
          50: '#fef7f0',
          100: '#fdf0e3',
          200: '#fbdcc7',
          300: '#f8b58e',
          400: '#f48e5e',
          500: '#e86a34',
          600: '#c85428',
          700: '#a44222',
          800: '#83351d',
          900: '#532113',
        },
        surface: {
          0: '#ffffff',
          1: '#f8fafc',
          2: '#f1f5f9',
          3: '#e2e8f0',
        },
        line: {
          0: '#e5e7eb',
          1: '#d1d5db',
          2: '#9ca3af',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        serif: ['"Instrument Serif"', 'Georgia', 'serif'],
        mono: ['"JetBrains Mono"', 'monospace'],
      },
      fontSize: {
        'display-2xl': ['3.5rem', { lineHeight: '1.1', fontWeight: '700' }],
        'display-xl': ['2.75rem', { lineHeight: '1.15', fontWeight: '700' }],
      },
      spacing: {
        '18': '4.5rem',
        '22': '5.5rem',
        '26': '6.5rem',
        '30': '7.5rem',
      },
      boxShadow: {
        soft: '0 1px 2px 0 rgba(13,17,23,0.04), 0 1px 3px 0 rgba(13,17,23,0.06)',
        card: '0 1px 3px 0 rgba(13,17,23,0.06), 0 8px 24px -6px rgba(13,17,23,0.08)',
        elevated: '0 4px 6px -1px rgba(13,17,23,0.06), 0 24px 48px -12px rgba(13,17,23,0.12)',
        glow: '0 0 0 1px rgba(47,107,240,0.15), 0 8px 32px -8px rgba(47,107,240,0.25)',
      },
      borderRadius: {
        xl: '1rem',
        '2xl': '1.5rem',
      },
      animation: {
        'fade-in': 'fade-in 0.4s cubic-bezier(0.16,1,0.3,1)',
        'slide-up': 'slide-up 0.5s cubic-bezier(0.16,1,0.3,1)',
        'pulse-slow': 'pulse 3s cubic-bezier(0.4,0,0.6,1) infinite',
      },
      keyframes: {
        'fade-in': { '0%': { opacity: '0' }, '100%': { opacity: '1' } },
        'slide-up': { '0%': { opacity: '0', transform: 'translateY(12px)' }, '100%': { opacity: '1', transform: 'translateY(0)' } },
      },
    },
  },
  plugins: [],
}