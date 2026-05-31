import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  build: {
    outDir: 'dist',
    emptyOutDir: true,
  },
  server: {
    proxy: {
      '/v1': 'http://127.0.0.1:8501',
      '/api': 'http://127.0.0.1:8501',
      '/ws': {
        target: 'ws://127.0.0.1:8501',
        ws: true,
      },
    },
  },
});
