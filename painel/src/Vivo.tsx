import {useContagem, useMovimentoReduzido} from './useVivo';

// Elementos de "sistema funcionando" (pedido do autor em 21/11/2026): ilustrações dos
// veículos, números que contam até o valor novo e um radar de varredura. Tudo em SVG com
// animação do próprio SVG ou requestAnimationFrame: nada de CSS importado. Quem pede ao
// sistema para reduzir movimento vê tudo parado.

// ---------- veículos ----------

export type TipoVeiculo = 'carro' | 'moto' | 'onibus' | 'caminhao';

function Roda({cx, cy, r, cor, gira}: {cx: number; cy: number; r: number; cor: string; gira: boolean}) {
  return (
    <g>
      <circle cx={cx} cy={cy} r={r} fill="#040b09" stroke={cor} strokeWidth={1.6} />
      <g>
        <line x1={cx - r + 1.5} y1={cy} x2={cx + r - 1.5} y2={cy} stroke={cor} strokeWidth={1} />
        <line x1={cx} y1={cy - r + 1.5} x2={cx} y2={cy + r - 1.5} stroke={cor} strokeWidth={1} />
        {gira && (
          <animateTransform
            attributeName="transform"
            type="rotate"
            from={`0 ${cx} ${cy}`}
            to={`360 ${cx} ${cy}`}
            dur="0.9s"
            repeatCount="indefinite"
          />
        )}
      </g>
    </g>
  );
}

// Silhueta lateral de cada tipo, num quadro 64x32, contorno na cor e vidro translúcido.
export function Veiculo({tipo, cor, tamanho = 40, gira = false}: {tipo: TipoVeiculo; cor: string; tamanho?: number; gira?: boolean}) {
  const corpo = {fill: cor, fillOpacity: 0.16, stroke: cor, strokeWidth: 1.6, strokeLinejoin: 'round' as const};
  const vidro = {fill: cor, fillOpacity: 0.35};
  const farol = <rect x={58} y={15} width={4} height={3} rx={1} fill="#f5b942" />;
  return (
    <svg
      width={tamanho}
      height={tamanho / 2}
      viewBox="0 0 64 32"
      aria-hidden="true"
      style={{filter: `drop-shadow(0 0 3px ${cor})`, overflow: 'visible'}}>
      {tipo === 'carro' && (
        <>
          <path d="M17 13 L24 5 H40 L48 13 Z" {...corpo} />
          <path d="M22 12 L26 7 H32 V12 Z M34 12 V7 H39 L45 12 Z" {...vidro} />
          <rect x={4} y={13} width={56} height={10} rx={4} {...corpo} />
          {farol}
          <Roda cx={17} cy={24} r={5} cor={cor} gira={gira} />
          <Roda cx={47} cy={24} r={5} cor={cor} gira={gira} />
        </>
      )}
      {tipo === 'moto' && (
        <>
          <path d="M14 22 L26 13 H38 L50 22" fill="none" stroke={cor} strokeWidth={2} strokeLinecap="round" />
          <path d="M24 11 H37" stroke={cor} strokeWidth={3.5} strokeLinecap="round" />
          <path d="M42 7 L47 14" stroke={cor} strokeWidth={2} strokeLinecap="round" />
          <rect x={47} y={13} width={4} height={3} rx={1} fill="#f5b942" />
          <Roda cx={14} cy={22} r={7.5} cor={cor} gira={gira} />
          <Roda cx={50} cy={22} r={7.5} cor={cor} gira={gira} />
        </>
      )}
      {tipo === 'onibus' && (
        <>
          <rect x={2} y={3} width={60} height={20} rx={3} {...corpo} />
          {[7, 18, 29, 40].map(x => (
            <rect key={x} x={x} y={7} width={8} height={7} rx={1} {...vidro} />
          ))}
          <rect x={51} y={7} width={8} height={12} rx={1} {...vidro} />
          {farol}
          <Roda cx={14} cy={24} r={4.5} cor={cor} gira={gira} />
          <Roda cx={50} cy={24} r={4.5} cor={cor} gira={gira} />
        </>
      )}
      {tipo === 'caminhao' && (
        <>
          <rect x={2} y={4} width={38} height={18} rx={2} {...corpo} />
          <path d="M42 9 H51 L60 15 V22 H42 Z" {...corpo} />
          <path d="M45 11 H50 L56 15 H45 Z" {...vidro} />
          {farol}
          <Roda cx={11} cy={24} r={4.5} cor={cor} gira={gira} />
          <Roda cx={28} cy={24} r={4.5} cor={cor} gira={gira} />
          <Roda cx={51} cy={24} r={4.5} cor={cor} gira={gira} />
        </>
      )}
    </svg>
  );
}

// ---------- números que contam ----------

const numero = new Intl.NumberFormat('pt-BR');

export function Contador({valor}: {valor: number}) {
  return <>{numero.format(useContagem(valor))}</>;
}

// ---------- radar ----------

// Pequeno radar com varredura girando: marca que a coleta está ao vivo.
export function Radar({tamanho = 22, ativo = true}: {tamanho?: number; ativo?: boolean}) {
  const reduzir = useMovimentoReduzido();
  const cor = ativo ? '#2ee6b6' : '#5c7a71';
  return (
    <svg width={tamanho} height={tamanho} viewBox="0 0 40 40" aria-hidden="true">
      <defs>
        <linearGradient id="varredura" x1="0" y1="0" x2="1" y2="0">
          <stop offset="0%" stopColor={cor} stopOpacity={0} />
          <stop offset="100%" stopColor={cor} stopOpacity={0.7} />
        </linearGradient>
      </defs>
      <circle cx={20} cy={20} r={18} fill="none" stroke={cor} strokeOpacity={0.5} />
      <circle cx={20} cy={20} r={11} fill="none" stroke={cor} strokeOpacity={0.3} />
      <circle cx={20} cy={20} r={2} fill={cor} />
      {ativo && (
        <path d="M20 20 L20 2 A18 18 0 0 1 35.6 11 Z" fill="url(#varredura)">
          {!reduzir && (
            <animateTransform
              attributeName="transform"
              type="rotate"
              from="0 20 20"
              to="360 20 20"
              dur="2.4s"
              repeatCount="indefinite"
            />
          )}
        </path>
      )}
    </svg>
  );
}
