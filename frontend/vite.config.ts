import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    host: '127.0.0.1',
    port: 5180,
    proxy: {
      '/api': {
        target: process.env.VITE_PROXY_API_TARGET ?? 'http://127.0.0.1:8100',
        changeOrigin: true,
      },
    },
  },
  test: {
    environment: 'jsdom',
    setupFiles: './src/test/setup.ts',
    globals: true,
    exclude: ['node_modules/**', 'dist/**', 'e2e/**'],
  },
});
