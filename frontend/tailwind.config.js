/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        canvas: "#060708",
        panel: "#101214",
        muted: "#8f989f",
        line: "#252a2f",
        accent: "#63e6be",
        cobalt: "#7aa2ff",
        amber: "#f0b95e",
      },
      fontFamily: {
        sans: ["Inter", "ui-sans-serif", "system-ui", "sans-serif"],
      },
    },
  },
  plugins: [],
};
