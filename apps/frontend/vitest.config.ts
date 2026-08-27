import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'
import { vanillaExtractPlugin } from '@vanilla-extract/vite-plugin'
import { fileURLToPath } from 'url'
import path from 'path'

const __dirname = path.dirname(fileURLToPath(import.meta.url))

export default defineConfig({
  plugins: [react(), vanillaExtractPlugin()],
  test: {
    environment: 'jsdom',
    /**
     * O teste roda contra a MESMA base que o CI: relativa.
     *
     * O Vitest carrega os `.env*` do Vite, então um `.env.local` apontando o
     * dev server para a API do DEV — coisa que todo mundo tem — fazia
     * `API_BASE` virar URL absoluta e derrubava 8 testes da família do live
     * view, que afirmam caminho relativo. Vermelho no laptop, verde no CI: o
     * pior tipo de falha, porque manda caçar regressão que não existe.
     *
     * Fixar aqui torna a suíte independente do ambiente de quem roda.
     */
    env: { VITE_API_URL: '', VITE_WS_URL: '' },
    setupFiles: ['./src/test/setup.ts'],
    exclude: ['**/node_modules/**', '**/src/test/e2e/**'],
    server: {
      deps: {
        inline: [/^@vanilla-extract\//],
      },
    },
  },
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
})
