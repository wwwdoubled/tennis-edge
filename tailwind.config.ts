import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#1a1815",
        paper: "#f5f1e8",
        cream: "#faf8f3",
        ash: "#9a978f",
        edge: "#d8ff3d",     // electric chartreuse — single accent
        clay:  "#c66b3d",
        grass: "#5a8c3a",
        hard:  "#3a6b9c",
      },
      fontFamily: {
        display: ["var(--font-display)", "Georgia", "serif"],
        sans:    ["var(--font-sans)", "ui-sans-serif", "system-ui"],
        mono:    ["var(--font-mono)", "ui-monospace", "monospace"],
      },
    },
  },
  plugins: [],
};
export default config;
