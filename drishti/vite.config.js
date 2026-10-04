import { copyFileSync, createReadStream, existsSync } from 'node:fs';
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// Files the browser asks for by name (service worker, manifest, icon, the hologram's head).
// They sit next to the source in this one flat folder, so there is no public/ folder.
const STATIC = ['favicon.svg', 'hologram-head.bin', 'manifest.webmanifest', 'sw.js'];
const TYPES = { svg: 'image/svg+xml', bin: 'application/octet-stream', webmanifest: 'application/manifest+json', js: 'text/javascript' };

const staticFiles = {
  name: 'atulya-static-files',
  configureServer(server) {
    server.middlewares.use((req, res, next) => {
      const name = (req.url || '').split('?')[0].slice(1);
      if (!STATIC.includes(name)) return next();
      res.setHeader('Content-Type', TYPES[name.split('.').pop()] || 'application/octet-stream');
      createReadStream(name).pipe(res);
    });
  },
  closeBundle() {
    for (const name of STATIC) if (existsSync(name)) copyFileSync(name, `dist/${name}`);
  },
};

export default defineConfig({
  publicDir: false,
  plugins: [react(), staticFiles],
  build: {
    outDir: 'dist',
    emptyOutDir: true,
    chunkSizeWarningLimit: 600, // the hologram (three.js) is one lazy-loaded chunk
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
