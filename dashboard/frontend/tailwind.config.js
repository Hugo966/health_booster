/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: "#0a0e1a",
        panel: "#0e1424",
        accent: "#00d4ff",
        alert: "#ff4757",
        amber: "#ffa502",
        good: "#2ed573",
        muted: "#7a8699",
      },
      fontFamily: {
        display: ["Orbitron", "ui-sans-serif", "system-ui"],
        body: ["Inter", "ui-sans-serif", "system-ui"],
      },
    },
  },
  plugins: [],
};
