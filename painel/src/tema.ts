import {defineTheme} from '@astryxdesign/core/theme';
import {themes, defaultThemeSlug} from './astryx-themes';

// Visual "sala de controle" (pedido do autor em 21/11/2026, referências: painel escuro com
// acento ciano-neon e cantos marcados; cartões de vidro com brilho dourado). Tudo pelo tema:
// tokens de cor, fontes, raio e overrides de componente; nenhum componente foi copiado.
//
// Leitura continua na Atkinson Hyperlegible Next (feita para baixa visão; a versão Next tem
// todos os pesos). Títulos e números usam Chakra Petch, de cara técnica. As duas vêm do Google
// Fonts no <head> das duas páginas. Vão no eixo de tipografia, não em tokens soltos: a regra do
// tema neutro para telas de toque recalcula a tipografia e regravava a fonte padrão por cima.
const LEITURA = 'Atkinson Hyperlegible Next';
const RESERVA = "'Atkinson Hyperlegible', system-ui, sans-serif";
const TECNICA = 'Chakra Petch';

const NEON = '#2ee6b6';
const neon = (alfa: number) => `rgba(46, 230, 182, ${alfa})`;
const OURO = (alfa: number) => `rgba(245, 185, 66, ${alfa})`;

// Cantos de mira nos cartões: 8 traços de 14 px, dois por canto.
const TRACO = `linear-gradient(${neon(0.75)}, ${neon(0.75)})`;
const CANTOS = {
  backgroundImage: Array(8).fill(TRACO).join(', '),
  backgroundPosition:
    'top left, top left, top right, top right, bottom left, bottom left, bottom right, bottom right',
  backgroundSize: Array(4).fill('14px 2px, 2px 14px').join(', '),
  backgroundRepeat: 'no-repeat',
};

export const tema = defineTheme({
  name: 'fluxo-niteroi',
  extends: themes[defaultThemeSlug],
  typography: {
    body: {family: LEITURA, fallbacks: RESERVA},
    heading: {family: TECNICA, fallbacks: RESERVA},
  },
  radius: {base: 3, multiplier: 1},
  // A página roda sempre em modo escuro (main.tsx); os valores valem para ele.
  tokens: {
    '--color-background-body': '#040b09',
    '--color-background-surface': 'rgba(8, 24, 20, 0.82)',
    '--color-background-card': 'rgba(8, 24, 20, 0.74)',
    '--color-background-muted': neon(0.07),
    '--color-background-popover': '#0b1d18',
    '--color-border': neon(0.2),
    '--color-border-emphasized': neon(0.45),
    '--color-accent': NEON,
    '--color-accent-muted': neon(0.14),
    '--color-text-accent': '#5ff0c8',
    '--color-icon-accent': NEON,
    '--color-on-accent': '#02140f',
    '--color-text-primary': '#e6fff6',
    '--color-text-secondary': '#9fc4b8',
    '--color-icon-primary': '#e6fff6',
    '--color-icon-secondary': '#9fc4b8',
  },
  components: {
    // A página pinta o próprio fundo: grade fina e um halo ciano no topo.
    layout: {
      base: {
        backgroundColor: 'var(--color-background-body)',
        backgroundImage: [
          `radial-gradient(ellipse 90% 55% at 50% -12%, ${neon(0.16)}, transparent 62%)`,
          `linear-gradient(${neon(0.045)} 1px, transparent 1px)`,
          `linear-gradient(90deg, ${neon(0.045)} 1px, transparent 1px)`,
        ].join(', '),
        backgroundSize: '100% 100%, 40px 40px, 40px 40px',
        backgroundAttachment: 'fixed',
        minHeight: '100dvh',
      },
    },
    // Cartão de vidro: translúcido, desfocando o fundo, borda fina e cantos de mira.
    card: {
      base: {
        ...CANTOS,
        borderColor: neon(0.22),
        backdropFilter: 'blur(10px)',
        boxShadow: `0 0 0 1px ${neon(0.04)}, 0 10px 36px rgba(0, 0, 0, 0.5), inset 0 1px 0 rgba(255, 255, 255, 0.04)`,
      },
      // Alertas com o brilho quente da referência de vidro; ok com o brilho ciano.
      'variant:yellow': {borderColor: OURO(0.55), boxShadow: `0 0 28px ${OURO(0.22)}`},
      'variant:red': {borderColor: 'rgba(255, 99, 99, 0.55)', boxShadow: '0 0 28px rgba(255, 99, 99, 0.22)'},
      'variant:green': {borderColor: neon(0.5), boxShadow: `0 0 28px ${neon(0.18)}`},
      // Sem base / coleta parada: vidro neutro em vez do cinza opaco do tema escuro.
      'variant:gray': {backgroundColor: 'rgba(14, 32, 28, 0.78)', borderColor: neon(0.25)},
    },
    // Números e títulos grandes acendem de leve.
    heading: {
      'type:display-3': {textShadow: `0 0 22px ${neon(0.35)}`},
    },
    'segmented-control-item': {
      selected: {boxShadow: `0 0 0 1px ${neon(0.6)}, 0 0 14px ${neon(0.35)}`},
    },
  },
});
