import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  base: './',
  build: {
    // três páginas: o painel (/), os sinistros (/sinistros/) e a apresentação (/sobre/)
    rolldownOptions: {
      input: { main: 'index.html', sobre: 'sobre/index.html', sinistros: 'sinistros/index.html' },
    },
  },
})
