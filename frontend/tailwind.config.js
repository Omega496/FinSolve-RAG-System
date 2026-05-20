/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        // Role-specific color palette from AGNNTS.md
        role: {
          engineering: '#8B5CF6',  // violet-500
          finance: '#10B981',      // emerald-500
          marketing: '#F97316',    // orange-500
          hr: '#F43F5E',          // rose-500
          c_suite: '#F59E0B',     // amber-500
          employee: '#64748B',    // slate-500
        },
      },
    },
  },
  plugins: [],
}
