import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  esbuild: {
    loader: "jsx",
    include: /src\/.*\.jsx?|tests\/.*\.js$/,
    exclude: [],
  },
  test: {
    environment: "jsdom",
    setupFiles: "./vitest.setup.js"
  }
});
