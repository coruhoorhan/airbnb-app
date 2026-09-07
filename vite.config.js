import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  build: {
    rollupOptions: {
      input: {
        main: 'index.html',
        'service-worker': 'src/service-worker.js'
      },
      output: {
        entryFileNames: assetInfo => {
          return assetInfo.name === 'service-worker'
            ? '[name].js'
            : 'assets/[name]-[hash].js';
        }
      }
    }
  },
  server: {
    host: "0.0.0.0",
    port: 5173,
    proxy: {
      "/api": {
        target: "http://127.0.0.1:4000",
        changeOrigin: true
      },
      "/uploads": {
        target: "http://127.0.0.1:4000",
        changeOrigin: true
      }
    }
  }
});
