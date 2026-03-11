import { defineConfig } from 'vite';
import { loadEnv } from 'vite';

// https://vitejs.dev/config
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '');
  const APP_URL =
    env.ELECTRON_APP_URL ?? 'http://localhost:3000/dashboard/client';

  return {
    define: {
      'process.env.ELECTRON_APP_URL': JSON.stringify(APP_URL),
    },
  };
});
