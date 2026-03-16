/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './pages/**/*.{js,ts,jsx,tsx,mdx}',
    './components/**/*.{js,ts,jsx,tsx,mdx}',
    './app/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        'risk-high': '#ef4444',
        'risk-medium': '#f97316',
        'risk-low': '#22c55e',
        'primary': '#3b82f6',
        'secondary': '#64748b',
      },
    },
  },
  plugins: [],
}
