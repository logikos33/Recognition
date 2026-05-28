import { defineConfig } from 'astro/config'
import react from '@astrojs/react'
import tailwind from '@astrojs/tailwind'

export default defineConfig({
  integrations: [react(), tailwind()],
  output: 'static',
  vite: {
    plugins: [
      {
        name: 'cross-origin-isolation',
        configureServer(server) {
          server.middlewares.use((_req, res, next) => {
            res.setHeader('Cross-Origin-Opener-Policy', 'same-origin')
            res.setHeader('Cross-Origin-Embedder-Policy', 'require-corp')
            next()
          })
        },
        configurePreviewServer(server) {
          server.middlewares.use((_req, res, next) => {
            res.setHeader('Cross-Origin-Opener-Policy', 'same-origin')
            res.setHeader('Cross-Origin-Embedder-Policy', 'require-corp')
            next()
          })
        },
      },
    ],
  },
})
