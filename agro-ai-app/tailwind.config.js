/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        forest: { DEFAULT: "#1F4D2B", deep: "#153420" },
        saffron: { DEFAULT: "#E58A2D", pale: "#FBE6CC" },
        cream: "#FFF8EC",
        leaf: { DEFAULT: "#3F7A3F", pale: "#E4EFDE" },
        ink: { DEFAULT: "#1A1A1A", soft: "#6B6459" },
        line: "#EDE2CE"
      },
      fontFamily: {
        display: ["Fraunces", "serif"],
        body: ["Inter", "sans-serif"]
      },
      borderRadius: {
        "3xl": "24px",
        "4xl": "28px"
      },
      boxShadow: {
        soft: "0 6px 18px rgba(31,77,43,0.08)"
      }
    }
  },
  plugins: []
};
