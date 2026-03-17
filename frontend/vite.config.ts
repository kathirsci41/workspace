import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';
import path from 'path';

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  test: {
    environment: 'node',
    include: ['../tests/frontend/**/*.test.ts'],
    alias: {
      '@': '/src',
    },
  },
  server: {
    port: 5174,
    proxy: {
      '/api': {
        target: process.env.API_TARGET || 'http://127.0.0.1:8002',
        changeOrigin: true,
      },
    },
  },
});
