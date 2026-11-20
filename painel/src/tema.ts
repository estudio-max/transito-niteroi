import {defineTheme} from '@astryxdesign/core/theme';
import {themes, defaultThemeSlug} from './astryx-themes';

// Tema neutro com fonte de leitura fácil (Atkinson Hyperlegible Next, feita para baixa visão;
// a versão Next tem todos os pesos, então títulos em 500/600 não caem para o regular).
// A fonte vem do Google Fonts, carregada no <head> das duas páginas.
// Vai no eixo de tipografia, não em tokens soltos: a regra do tema neutro para telas de
// toque recalcula a tipografia e regravava a fonte padrão (Figtree) por cima dos tokens.
const FAMILIA = 'Atkinson Hyperlegible Next';
const RESERVA = "'Atkinson Hyperlegible', system-ui, sans-serif";

export const tema = defineTheme({
  name: 'fluxo-niteroi',
  extends: themes[defaultThemeSlug],
  typography: {
    body: {family: FAMILIA, fallbacks: RESERVA},
    heading: {family: FAMILIA, fallbacks: RESERVA},
  },
  // A página pinta o próprio fundo: sem isso, com o sistema em modo escuro, o navegador
  // pinta o fundo de preto e os títulos fora dos cartões somem.
  components: {
    layout: {base: {backgroundColor: 'var(--color-background-body)', minHeight: '100dvh'}},
  },
});
