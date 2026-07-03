import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';
import path from 'path';

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@garden/shared': path.resolve(__dirname, '../../packages/shared/src'),
    },
  },
  server: {
    proxy: {
      // All API calls and static files (images, CSS) go through FastAPI on port 8000
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
      '/static': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
  test: {
    environment: 'jsdom',
    setupFiles: './src/test/setup.ts',
    include: [
      'src/**/*.test.{ts,tsx}',
      '../../packages/shared/src/**/*.test.ts',
    ],
  },
});
