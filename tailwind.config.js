/** @type {import("tailwindcss").Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        // Fatsa Escapes — "Kinetic Coastal & Modernist" (design.md)
        // Birincil CTA: Kıyı Gün Batımı #FF5A36 | İkincil: Karadeniz Zümrütü #0F9D78
        airbnb: {
          DEFAULT: "#FF5A36", // Kıyı Gün Batımı (CTA)
          dark: "#E0491F",
          hover: "#D64316",
          light: "#FFF4EF"
        },
        charcoal: {
          DEFAULT: "#1F2937", // Kömür (metin)
          dark: "#0D0F12", // Derin Obsidyen (footer/koyu zemin)
          light: "#6B7280",
          muted: "#9CA3AF",
          border: "#E5E0D8", // Kıyı Kumu kenarlık
          bg: "#F7F4EE" // Kıyı Kumu zemin
        },
        // Karadeniz Zümrütü ailesi (custom override — Tailwind default değil)
        emerald: {
          50: "#EDFBF6",
          100: "#D3F5E8",
          200: "#A9EAD3",
          300: "#74D9B9",
          400: "#3DC49C",
          500: "#17AE87",
          600: "#0F9D78",
          700: "#0C7D60",
          800: "#0C634E",
          900: "#0A5041"
        },
        // Kehribar altın ailesi (yıldızlar, badge'ler) — custom override
        amber: {
          50: "#FDF8EC",
          100: "#F9EECC",
          200: "#F3DFA0",
          300: "#EDCC6E",
          400: "#F2B33D",
          500: "#E9A62B",
          600: "#D9942A",
          700: "#B87A22",
          800: "#96631E",
          900: "#7A501B"
        },
        // Kıyı deniz mavisi (bağlantı/ikon) — custom override
        blue: {
          50: "#EEF4F5",
          100: "#D6E4E6",
          200: "#C8DADD",
          300: "#9FBFC4",
          400: "#5F959D",
          500: "#3D7B84",
          600: "#2A6E77",
          700: "#23585F",
          800: "#1C464B",
          900: "#16383C"
        },
        // Kıyı sisi (hero zeminleri) — custom override
        sky: {
          50: "#F2F7F6",
          100: "#E4F0EE",
          200: "#C9E1DE",
          300: "#A3CCC7",
          400: "#6FB0AA",
          500: "#4B958F",
          600: "#3A7A75",
          700: "#31625E",
          800: "#2A504D",
          900: "#244240"
        },
        // Host paneli ikincil — custom override
        indigo: {
          50: "#EEF1F7",
          100: "#D9E0EC",
          200: "#B7C4DB",
          300: "#8FA2C3",
          400: "#6780A8",
          500: "#4D6690",
          600: "#3D5478",
          700: "#324561",
          800: "#2A394F",
          900: "#232E40"
        }
      },
      fontFamily: {
        display: ["Space Grotesk", "Plus Jakarta Sans", "sans-serif"],
        sans: ["Plus Jakarta Sans", "Inter", "sans-serif"]
      },
      boxShadow: {
        // korrodesign: "Shadows > borders" — kart kenarlığı olarak katmanlı gölge
        border: "0 0 0 1px rgba(0,0,0,0.06), 0 1px 2px -1px rgba(0,0,0,0.06), 0 2px 4px rgba(0,0,0,0.04)",
        "border-hover": "0 0 0 1px rgba(0,0,0,0.08), 0 1px 2px -1px rgba(0,0,0,0.08), 0 2px 4px rgba(0,0,0,0.06), 0 8px 24px -6px rgba(0,0,0,0.10)"
      }
    }
  },
  plugins: []
};
