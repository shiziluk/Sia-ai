import { fileURLToPath, URL } from 'node:url'

import vue from '@vitejs/plugin-vue'
import { defineConfig } from 'vite'
import { VitePWA } from 'vite-plugin-pwa'

// Vite 配置：开发代理 + PWA
export default defineConfig({
  plugins: [
    vue(),
    VitePWA({
      // 自动更新 Service Worker
      registerType: 'autoUpdate',
      includeAssets: ['icon-192.png', 'icon-512.png'],
      manifest: {
        name: '希亚 - 我的AI女友',
        short_name: '希亚',
        description: '和希亚聊聊天，她会记住你说的每一句话。',
        lang: 'zh-CN',
        theme_color: '#e91e63',
        background_color: '#fff5f8',
        display: 'standalone',
        start_url: '/',
        icons: [
          { src: 'icon-192.png', sizes: '192x192', type: 'image/png' },
          { src: 'icon-512.png', sizes: '512x512', type: 'image/png' }
        ]
      },
      workbox: {
        // 立绘图片较大，不进预缓存，改为运行时缓存
        globPatterns: ['**/*.{js,css,html,webmanifest}'],
        runtimeCaching: [
          {
            urlPattern: ({ url }) => url.pathname.startsWith('/avatars/'),
            handler: 'CacheFirst',
            options: {
              cacheName: 'xia-avatars',
              expiration: { maxEntries: 20, maxAgeSeconds: 60 * 60 * 24 * 30 }
            }
          }
        ]
      }
    })
  ],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url))
    }
  },
  server: {
    port: 5173,
    // 把 /api 转发到本地 FastAPI 后端，免 CORS
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8900',
        changeOrigin: true
      }
    }
  }
})
