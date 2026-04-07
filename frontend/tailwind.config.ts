/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ['./src/**/*.{js,ts,jsx,tsx,mdx}'],
  theme: {
    extend: {
      colors: {
        bg:      '#080c10',
        surface: '#0e1419',
        panel:   '#141b24',
        border:  '#1e2a36',
        border2: '#2a3a4a',
        accent:  '#00d4ff',
        accent2: '#0099cc',
        muted:   '#6b7c8f',
      },
      fontFamily: {
        sans: ['Space Grotesk', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'monospace'],
      },
      animation: {
        'pulse-dot': 'pulse-dot 2s ease-in-out infinite',
        'spin-ring': 'spin-ring 1.2s ease-in-out infinite',
        'fade-in':   'fade-in 0.3s ease-out',
        'slide-up':  'slide-up 0.4s ease-out',
      },
      keyframes: {
        'pulse-dot': {
          '0%,100%': { opacity: '1', transform: 'scale(1)' },
          '50%':     { opacity: '0.4', transform: 'scale(0.7)' },
        },
        'spin-ring': {
          '0%':   { boxShadow: '0 0 0 2px rgba(0,212,255,0.4)' },
          '50%':  { boxShadow: '0 0 0 5px rgba(0,212,255,0.1)' },
          '100%': { boxShadow: '0 0 0 2px rgba(0,212,255,0.4)' },
        },
        'fade-in':  { from: { opacity: '0' }, to: { opacity: '1' } },
        'slide-up': { from: { opacity: '0', transform: 'translateY(12px)' }, to: { opacity: '1', transform: 'translateY(0)' } },
      },
    },
  },
  plugins: [],
}