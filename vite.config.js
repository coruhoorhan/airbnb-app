import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': 'http://localhost:3000'
    }
  },
  build: {
    rollupOptions: {
      input: {
        main: './index.html',
        'service-worker': './src/service-worker.js'
      },
      output: {
        entryFileNames: (assetInfo) => {
          return assetInfo.name === 'service-worker' ? '[name].js' : 'assets/[name]-[hash].js'
        }
      }
    }
  }
})
