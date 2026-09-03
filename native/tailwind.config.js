/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        theme: {
          bg: "var(--theme-bg)",
          card: "var(--theme-card)",
          text: "var(--theme-text)",
          muted: "var(--theme-muted)",
          border: "var(--theme-border)",
          accent: "var(--theme-accent)",
          hover: "var(--theme-hover)",
        },
      },
    },
  },
  plugins: [],
};
