import type { Config } from "tailwindcss";

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  darkMode: ["class", '[data-theme="dark"]'],
  theme: {
    extend: {
      fontFamily: {
        sans: ["Geist", "system-ui", "-apple-system", "sans-serif"],
        mono: ["Geist Mono", "ui-monospace", "monospace"],
      },
      // The design's one breakpoint (frontend/README.md Section 9.5):
      // side panel + sticky map at >= 960px, bottom sheet below it.
      screens: {
        desktop: "960px",
      },
    },
  },
  plugins: [],
} satisfies Config;
