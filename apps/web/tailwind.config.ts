import type { Config } from "tailwindcss";

export default {
  content: ["./index.html", "./src/**/*.{vue,ts}"],
  theme: {
    extend: {
      colors: {
        terminal: {
          bg: "#020617",
          panel: "#0F172A",
          panelAlt: "#1E293B",
          signal: "#22C55E",
          text: "#F8FAFC",
          muted: "#94A3B8",
          danger: "#F97316",
          warning: "#FBBF24",
          info: "#38BDF8",
        },
      },
      boxShadow: {
        glow: "0 0 0 1px rgba(148, 163, 184, 0.12), 0 18px 45px rgba(2, 6, 23, 0.38)",
      },
      fontFamily: {
        mono: ["Fira Code", "ui-monospace", "SFMono-Regular", "monospace"],
        sans: ["Fira Sans", "system-ui", "sans-serif"],
      },
    },
  },
  plugins: [],
} satisfies Config;
