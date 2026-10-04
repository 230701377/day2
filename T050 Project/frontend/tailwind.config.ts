import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        brand: {
          50: "#f0f6ff",
          100: "#dbe9ff",
          200: "#bcd5ff",
          300: "#8eb6ff",
          400: "#598fff",
          500: "#3568ff",
          600: "#1d44f5",
          700: "#1734d4",
          800: "#182eab",
          900: "#1a2d86",
        },
      },
      fontFamily: {
        sans: ["Inter", "ui-sans-serif", "system-ui"],
      },
    },
  },
  plugins: [],
};

export default config;
