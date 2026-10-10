import type { Config } from "tailwindcss";

/**
 * Colours are CSS variables (see globals.css) so light/dark themes swap in one place.
 * Each token is stored as "R G B" so Tailwind opacity modifiers (bg-lens/10) work.
 */
const token = (name: string) => `rgb(var(--${name}) / <alpha-value>)`;

const config: Config = {
  darkMode: "class",
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        paper: token("paper"),
        surface: token("surface"),
        ink: token("ink"),
        graphite: token("graphite"),
        rule: token("rule"),
        lens: token("lens"),
        "lens-ink": token("lens-ink"),
        highlight: token("highlight"),
        "highlight-ink": token("highlight-ink"),
        redpen: token("redpen"),
        amber: token("amber"),
        moss: token("moss"),
      },
      fontFamily: {
        sans: [
          '"IBM Plex Sans"',
          "ui-sans-serif",
          "system-ui",
          "-apple-system",
          "Segoe UI",
          "Roboto",
          "sans-serif",
        ],
        serif: ['"IBM Plex Serif"', "ui-serif", "Georgia", "Cambria", '"Times New Roman"', "serif"],
      },
      maxWidth: {
        prose: "68ch",
      },
      keyframes: {
        "gauge-fill": {
          from: { strokeDashoffset: "var(--gauge-circumference)" },
          to: { strokeDashoffset: "var(--gauge-offset)" },
        },
        shimmer: {
          "0%, 100%": { opacity: "0.55" },
          "50%": { opacity: "1" },
        },
      },
      animation: {
        "gauge-fill": "gauge-fill 1.1s cubic-bezier(0.22, 1, 0.36, 1) both",
        shimmer: "shimmer 1.6s ease-in-out infinite",
      },
    },
  },
  plugins: [],
};

export default config;
