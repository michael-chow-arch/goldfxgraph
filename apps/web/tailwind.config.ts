import type { Config } from "tailwindcss";

export default {
  content: ["./index.html", "./src/**/*.{vue,ts}"],
  theme: {
    extend: {
      colors: {
        research: {
          canvas: "#020617",
          surface1: "#0B1220",
          surface2: "#111A2B",
          surface3: "#162033",
          surface4: "#1E293B",
          text: "#F8FAFC",
          muted: "#94A3B8",
          gold: "#D4A72C",
          amber: "#F59E0B",
          blue: "#38BDF8",
          green: "#22C55E",
          red: "#EF4444",
          orange: "#F97316",
        },
      },
      boxShadow: {
        glow: "0 0 0 1px rgba(148, 163, 184, 0.14), 0 18px 45px rgba(2, 6, 23, 0.42)",
        cockpit: "0 1px 0 rgba(255,255,255,0.02), 0 28px 80px -48px rgba(15, 23, 42, 0.8)",
      },
      fontFamily: {
        display: ["Plus Jakarta Sans", "PingFang SC", "Hiragino Sans GB", "SF Pro Text", "SF Pro Display", "Noto Sans SC", "system-ui", "sans-serif"],
        mono: ["Fira Code", "ui-monospace", "SFMono-Regular", "monospace"],
        sans: ["PingFang SC", "Hiragino Sans GB", "SF Pro Text", "SF Pro Display", "Noto Sans SC", "system-ui", "sans-serif"],
      },
      borderRadius: {
        xl2: "1.125rem",
        xl3: "1.5rem",
      },
    },
  },
  plugins: [],
} satisfies Config;
