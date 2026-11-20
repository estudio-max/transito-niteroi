import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  base: './',
  build: {
    // duas páginas: o painel (/) e a apresentação do projeto (/sobre/)
    rolldownOptions: {
      input: { main: 'index.html', sobre: 'sobre/index.html' },
    },
  },
})
