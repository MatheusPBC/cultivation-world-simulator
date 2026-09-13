import { defineConfig, loadEnv } from 'vite'
import vue from '@vitejs/plugin-vue'
import path from 'path'
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd())
  return {
    publicDir: false,
    plugins: [vue()],
    resolve: { alias: { '@': path.resolve(__dirname, './src') } },
    build: { outDir: 'dist-medieval', assetsDir: 'web_static', assetsInlineLimit: 0 },
    server: { host: '127.0.0.1', proxy: { '/api': { target: env.VITE_API_TARGET || 'http://127.0.0.1:8002', changeOrigin: true } } },
  }
})
