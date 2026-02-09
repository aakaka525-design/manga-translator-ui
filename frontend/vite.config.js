import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import path from 'path'
import { VitePWA } from 'vite-plugin-pwa'
import viteCompression from 'vite-plugin-compression'
import { visualizer } from 'rollup-plugin-visualizer'

// https://vitejs.dev/config/
export default defineConfig({
    plugins: [
        vue(),
        VitePWA({
            registerType: 'autoUpdate',
            includeAssets: ['favicon.ico', 'apple-touch-icon.png', 'mask-icon.svg'],
            // Workbox's default SW bundling uses @rollup/plugin-terser in "production" mode.
            // On Node 22.x this can fail with "Unfinished hook action(s) on exit: (terser) renderChunk".
            // Disabling SW minification keeps the PWA build stable.
            workbox: {
                mode: 'development'
            },
            manifest: {
                name: 'Neo-Comic Reader',
                short_name: 'NeoComic',
                description: 'AI-powered Manhua Translator & Reader',
                theme_color: '#0F0F11',
                background_color: '#0F0F11',
                display: 'standalone',
                scope: '/',
                start_url: '/',
                orientation: 'portrait',
                icons: [
                    {
                        src: 'pwa-192x192.png',
                        sizes: '192x192',
                        type: 'image/png'
                    },
                    {
                        src: 'pwa-512x512.png',
                        sizes: '512x512',
                        type: 'image/png'
                    },
                    {
                        src: 'pwa-512x512.png',
                        sizes: '512x512',
                        type: 'image/png',
                        purpose: 'any maskable'
                    }
                ]
            }
        }),
        viteCompression(),
        visualizer({
            open: false,
            gzipSize: true,
            brotliSize: true
        })
    ],
    resolve: {
        alias: {
            '@': path.resolve(__dirname, './src'),
        },
    },
    server: {
        proxy: {
            '/api': {
                target: 'http://localhost:8000',
                changeOrigin: true
            },
            '/data': {
                target: 'http://localhost:8000',
                changeOrigin: true
            },
            '/output': {
                target: 'http://localhost:8000',
                changeOrigin: true
            }
        }
    },
    build: {
        outDir: '../manga_translator/server/static/dist',
        emptyOutDir: true,
        rollupOptions: {
            output: {
                manualChunks(id) {
                    if (id.includes('node_modules')) {
                        return 'vendor';
                    }
                }
            }
        }
    }
})
