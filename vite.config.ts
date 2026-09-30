import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';

export default defineConfig({
  plugins: [react(), tailwindcss()],
  css: { postcss: {} },
  server: { port: 5173, host: '127.0.0.1', proxy: { '/api': { target: 'http://127.0.0.1:8000', changeOrigin: true } } },
  preview: { port: 4173, host: '127.0.0.1', proxy: { '/api': { target: 'http://127.0.0.1:8000', changeOrigin: true } } },
  build: {
    chunkSizeWarningLimit: 700,
    rollupOptions: {
      output: {
        manualChunks: (id) => {
          if (id.includes('node_modules/recharts') || id.includes('node_modules/d3-') || id.includes('node_modules/victory-vendor')) return 'charts';
          if (id.includes('node_modules/leaflet') || id.includes('node_modules/react-leaflet') || id.includes('@react-leaflet')) return 'map';
          if (id.includes('node_modules/react') || id.includes('node_modules/scheduler')) return 'react';
        },
      },
    },
  },
});
