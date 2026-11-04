import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '');
  return {
    plugins: [react()],
    server: {
      port: 5173,
      strictPort: true,
      proxy: {
        '/api': { target: env.API_PROXY_TARGET || 'http://127.0.0.1:8000', changeOrigin: false },
      },
    },
    build: {
      sourcemap: true,
      rolldownOptions: {
        output: {
          codeSplitting: {
            groups: [
              { name: 'react', test: /node_modules[\\/](?:react|react-dom|scheduler)[\\/]/ },
              { name: 'router', test: /node_modules[\\/]react-router[\\/]/ },
              { name: 'validation', test: /node_modules[\\/]zod[\\/]/ },
            ],
          },
        },
      },
    },
  };
});
