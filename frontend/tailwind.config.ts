import type { Config } from "tailwindcss";

const hsl = (v: string) => `hsl(var(--${v}) / <alpha-value>)`;

const config: Config = {
  darkMode: "class",
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}", "./hooks/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: hsl("bg"), surface: hsl("surface"), sunken: hsl("sunken"), fg: hsl("fg"), muted: hsl("muted"),
        border: hsl("border"), accent: hsl("accent"), "accent-fg": hsl("accent-fg"), "accent-soft": hsl("accent-soft"),
        ok: hsl("ok"), "ok-soft": hsl("ok-soft"), bad: hsl("bad"), "bad-soft": hsl("bad-soft"),
        warn: hsl("warn"), "warn-soft": hsl("warn-soft"),
      },
      fontFamily: {
        sans: ['"Segoe UI"', "ui-sans-serif", "system-ui", '"Nirmala UI"', '"Noto Sans Devanagari"', "sans-serif"],
        serif: ['"Iowan Old Style"', '"Palatino Linotype"', "Georgia", "ui-serif", '"Nirmala UI"', '"Noto Serif Devanagari"', "serif"],
        mono: ["ui-monospace", "Consolas", "monospace"],
      },
      borderRadius: { xl: "0.875rem", "2xl": "1.125rem" },
      boxShadow: {
        soft: "0 1px 2px hsl(var(--shadow) / 0.05), 0 4px 16px hsl(var(--shadow) / 0.05)",
        pop: "0 8px 32px hsl(var(--shadow) / 0.14)",
      },
      keyframes: {
        shimmer: { "100%": { transform: "translateX(100%)" } },
        fadeIn: { from: { opacity: "0", transform: "translateY(4px)" }, to: { opacity: "1", transform: "none" } },
      },
      animation: { fadeIn: "fadeIn 0.25s ease-out both" },
    },
  },
  plugins: [],
};
export default config;
