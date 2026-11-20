import {Suspense, lazy, useEffect, useState} from 'react';
import type {ReactNode} from 'react';
import {VStack, HStack, Layout, LayoutContent} from '@astryxdesign/core/Layout';
import {Text, Heading} from '@astryxdesign/core/Text';
import {Card} from '@astryxdesign/core/Card';
import {Banner} from '@astryxdesign/core/Banner';
import {Badge} from '@astryxdesign/core/Badge';
import {Collapsible} from '@astryxdesign/core/Collapsible';
import {SegmentedControl, SegmentedControlItem} from '@astryxdesign/core/SegmentedControl';
import {EmptyState} from '@astryxdesign/core/EmptyState';
import {Spinner} from '@astryxdesign/core/Spinner';
import {StatusDot} from '@astryxdesign/core/StatusDot';
import {
  AreaChart,
  Area,
  BarChart,
  Bar,
  LabelList,
  LineChart,
  Line,
  ScatterChart,
  Scatter,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts';
import {Grid} from '@astryxdesign/core/Grid';
import {Table, proportional, pixel} from '@astryxdesign/core/Table';
import type {TableColumn} from '@astryxdesign/core/Table';
import {Divider} from '@astryxdesign/core/Divider';
import {Icon} from '@astryxdesign/core/Icon';
import {StopIcon} from '@heroicons/react/24/solid';
import {Link} from '@astryxdesign/core/Link';
import {Button} from '@astryxdesign/core/Button';
import {Topo} from './Topo';
import type {FocoMapa} from './Mapa';

// ============= DATA =============

type Ponto = {t: number} & Record<string, number | null>;

interface Camera {
  id: string;
  nome: string;
  sentido_confirmado?: boolean;
}

interface PorSentido {
  fluxo_h: number | null; // última hora coletada
  total: number; // veículos em toda a janela exportada
}

interface Resumo extends Camera {
  ocupacao: number | null;
  clipes: number;
  tipos: Record<string, number>;
  por_sentido?: Record<string, PorSentido>;
}

interface Clipe extends Record<string, unknown> {
  camera: string;
  utc: string;
  desce: number;
  sobe: number;
  fluxo_h: number | null;
  ocupacao: number;
}

interface Dados {
  gerado_utc: string;
  ultimo_clipe_utc: string | null;
  validado: boolean;
  balde_min: number;
  cameras: Camera[];
  sentidos?: Record<string, string>;
  resumo: Resumo[];
  total_veiculos: number;
  total_clipes: number;
  serie: Ponto[];
  cobertura?: {dias: string[]; minutos: number[][]};
  dispersao: Array<{c: string; f: number | null; o: number}>;
  ultimos: Clipe[];
  ocorrencias?: Ocorrencia[];
  veredito?: {
    nivel: 'ok' | 'atencao' | 'alerta' | 'pausado' | 'sem_base';
    texto: string;
    detalhe?: string;
  };
  situacao?: Record<string, Situacao>;
  onibus?: Record<string, {por_hora: number; intervalo_min: number | null; minutos_video: number}>;
  tendencia?: Record<string, Tendencia>;
  regiao?: PontoRegiao[];
  periodos?: Periodo[];
  antes_depois?: AntesDepois[];
  resumos?: Record<Janela, ResumoJanela>;
}

type Janela = '7d' | '30d' | 'total';
type Vista = 'agora' | Janela;

// Resumo por janela (exportar.resumos).
interface ResumoJanela {
  desde_utc: string | null;
  dias_com_dados: number;
  ocorrencias: number;
  cameras: Array<{
    id: string;
    nome: string;
    horas_video: number;
    pct_pesado: number | null;
    minutos_pesado: number;
    pior_hora: number;
    perfil: Array<Nivel | null>;
    fluxo_h: Record<string, number | null>;
    onibus_h: number | null;
  }>;
}

// Uma intervenção registrada em intervencoes.csv e a comparação feita por antes_depois.py.
interface AntesDepois {
  data: string;
  camera: string;
  nome: string;
  tipo: string;
  descricao: string;
  fonte: string;
  situacao: 'aguardando' | 'pronto';
  dias_depois: number;
  horas_comparaveis: number;
  frase: string;
  ocupacao?: {antes: number; depois: number; variacao_pct: number | null};
}

type Nivel = 'livre' | 'moderado' | 'pesado';

// Veículos por hora (os dois sentidos) nos últimos 15, 30 e 60 min e a direção, que compara
// os últimos 15 com os 45 anteriores (exportar.tendencia). Não depende do habitual.
interface Tendencia {
  m15: number | null;
  m30: number | null;
  m60: number | null;
  direcao: 'subindo' | 'estavel' | 'descendo' | null;
}
const DIRECAO = {subindo: 'subindo', estavel: 'estável', descendo: 'descendo'} as const;

// Pontos críticos de sinistros (sinistros.py): PRF nas rodovias federais e o ranking
// de vias da NitTrans, transcrito da tabela publicada em imagem.
interface Sinistros {
  prf: {
    fonte: string;
    anos: number[];
    total_sinistros: number;
    total_mortos: number;
    total_feridos_graves: number;
    fora_do_mapa: number;
    trechos: Array<{
      nome: string;
      sinistros: number;
      mortos: number;
      feridos_graves: number;
      graves: number;
      lat: number | null;
      lon: number | null;
    }>;
  };
  nittrans: {
    fonte: string;
    url: string;
    vias: Array<{via: string; '2024': number; '2025': number; '2026': number; total: number}>;
  };
}

function useSinistros() {
  const [s, setS] = useState<Sinistros | null>(null);
  useEffect(() => {
    fetch('sinistros.json')
      .then(r => (r.ok ? r.json() : null))
      .then(setS)
      .catch(() => setS(null));
  }, []);
  return s;
}

// Vias da tabela da NitTrans que têm câmera pública da região (coletor.REGIAO), separando
// as que este projeto conta das que só têm câmera.
const VIAS_COM_CAMERA: Record<string, {cameras: number; contando: boolean}> = {
  'Alameda São Boaventura': {cameras: 2, contando: false},
  'Av. Professor João Brasil': {cameras: 1, contando: false},
  'Av. Feliciano Sodré': {cameras: 2, contando: false},
  'Av. Jansen de Melo': {cameras: 2, contando: true},
};

// Um período contínuo de coleta (exportar.periodos), mais recente primeiro.
interface Periodo {
  inicio_utc: string;
  fim_utc: string;
  dia: string; // "hoje", "ontem" ou "dd/mm"
  inicio_t: string; // início do primeiro balde de 5 min
  balde_min: number;
  ocorrencias: number;
  frase: string;
  cameras: Array<{
    id: string;
    nome: string;
    faixa: Array<Nivel | null>;
    minutos_pesado: number;
    pior_utc: string;
    fluxo_h: Record<string, number | null>;
    onibus_h: number | null;
    com_base: boolean;
  }>;
}

// Ocupação de agora comparada com tudo o que a própria câmera já registrou (exportar.py).
interface Situacao {
  nivel: 'livre' | 'moderado' | 'pesado' | 'sem_historico' | 'sem_dado_recente';
  ocupacao?: number;
  percentil?: number;
}

interface PontoRegiao {
  id: string;
  nome: string;
  eixo: string;
  estado: 'no_ar' | 'parada' | 'fora' | 'sem_verificacao';
  ultimo_video_utc: string | null;
  contada: boolean;
  lat?: number;
  lon?: number;
}

// Veículo parado em dois clipes seguidos, classificado por um modelo de visão local (incidentes.py).
interface Ocorrencia extends Record<string, unknown> {
  camera: string;
  inicio_utc: string;
  fim_utc: string;
  clipes: number;
  classe: string;
  tipo: 'acidente' | 'enguico' | 'bloqueio';
  confianca: 'baixa' | 'media' | 'alta';
  descricao: string;
}

const TIPO_OCORRENCIA = {
  acidente: {rotulo: 'Acidente', variante: 'red'},
  enguico: {rotulo: 'Enguiço', variante: 'orange'},
  bloqueio: {rotulo: 'Bloqueio', variante: 'purple'},
} as const;
const CONFIANCA = {baixa: 'baixa', media: 'média', alta: 'alta'} as const;

const FUSO = 'America/Sao_Paulo';
const hora = new Intl.DateTimeFormat('pt-BR', {
  timeZone: FUSO,
  hour: '2-digit',
  minute: '2-digit',
});
const diaHora = new Intl.DateTimeFormat('pt-BR', {
  timeZone: FUSO,
  day: '2-digit',
  month: '2-digit',
  hour: '2-digit',
  minute: '2-digit',
});
const numero = new Intl.NumberFormat('pt-BR');
const decimal = new Intl.NumberFormat('pt-BR', {
  minimumFractionDigits: 1,
  maximumFractionDigits: 1,
});
const porcento = new Intl.NumberFormat('pt-BR', {style: 'percent', maximumFractionDigits: 0});

// Cor segue a câmera (ordem fixa da lista) em todos os gráficos, nunca a posição.
// Par validado nos fundos claro e escuro (o laranja do tema reprova no escuro).
// Com mais de duas câmeras: um gráfico pequeno por câmera, não mais cores.
const CORES = [
  'var(--color-data-categorical-blue, #0171E3)',
  'var(--color-data-categorical-brown, #965E03)',
];
const FORMAS = ['circle', 'triangle'] as const;
const TINTA = 'var(--color-text-secondary, #4E606F)';
const GRADE = 'var(--color-border, rgba(5, 54, 89, 0.1))';
const EIXO = {fontSize: 'var(--font-size-sm, 12px)', fill: TINTA};
const TIPOS: Array<[string, string]> = [
  ['carro', 'Carros'],
  ['moto', 'Motos'],
  ['onibus', 'Ônibus'],
  ['caminhao', 'Caminhões'],
];
const AO_VIVO_MIN = 10; // coleta conta como ativa se o último clipe tem menos que isso

// Sentido da imagem ("desce" = vem na direção da câmera) → sentido real na avenida.
// O texto vem de dados.sentidos (coletor.py), para ter uma única fonte.
const SENTIDOS = ['desce', 'sobe'] as const;
const MIN_TOTAL = 10; // um sentido só aparece se a câmera contou ao menos isso (some o ruído)

const rotulo = (dados: Dados, s: string) => {
  const t = dados.sentidos?.[s] ?? s;
  return t.charAt(0).toUpperCase() + t.slice(1);
};
const visivel = (dados: Dados, camera: string, s: string) =>
  (dados.resumo.find(r => r.id === camera)?.por_sentido?.[s]?.total ?? 0) >= MIN_TOTAL;
const rotuloMin = (dados: Dados, s: string) => dados.sentidos?.[s] ?? s; // mantém "Icaraí"
// Só avisa das câmeras que aparecem no gráfico daquele sentido.
const notaSentido = (dados: Dados, s: string) => {
  const pendentes = dados.cameras.filter(
    c => c.sentido_confirmado === false && visivel(dados, c.id, s),
  );
  return pendentes.length
    ? `Sentido a confirmar em: ${pendentes.map(c => c.nome).join(', ')} (inferido do nome da câmera).`
    : '';
};

function useDados() {
  const [dados, setDados] = useState<Dados | null>(null);
  const [erro, setErro] = useState(false);
  const [agora, setAgora] = useState(() => Date.now());
  useEffect(() => {
    const buscar = () => {
      setAgora(Date.now());
      fetch(`dados.json?t=${Date.now()}`)
        .then(r => (r.ok ? r.json() : Promise.reject(new Error(String(r.status)))))
        .then((d: Dados) => {
          setDados(d);
          setErro(false);
        })
        .catch(() => setErro(true));
    };
    buscar();
    const id = setInterval(buscar, 60_000);
    return () => clearInterval(id);
  }, []);
  return {dados, erro, agora};
}

// ============= CHART COMPONENTS =============

function ChartLegendItem({color, label}: {color: string; label: string}) {
  return (
    <HStack gap={2} vAlign="center">
      <Icon icon={StopIcon} size="xsm" style={{color}} />
      <Text type="supporting" color="secondary">
        {label}
      </Text>
    </HStack>
  );
}

function Legenda({cameras, cores = CORES}: {cameras: Camera[]; cores?: string[]}) {
  return (
    <HStack gap={6} vAlign="center" wrap="wrap">
      {cameras.map((c, i) => (
        <ChartLegendItem key={c.id} color={cores[i]} label={c.nome} />
      ))}
    </HStack>
  );
}

function Dica({titulo, linhas}: {titulo: string; linhas: Array<{cor?: string; texto: string}>}) {
  return (
    <Card padding={3}>
      <VStack gap={1}>
        <Text type="supporting" color="secondary">
          {titulo}
        </Text>
        {linhas.map(l => (
          <HStack key={l.texto} gap={2} vAlign="center">
            {l.cor && <Icon icon={StopIcon} size="xsm" style={{color: l.cor}} />}
            <Text type="supporting">{l.texto}</Text>
          </HStack>
        ))}
      </VStack>
    </Card>
  );
}

function SerieTooltip({
  active,
  payload,
  label,
  unidade,
  formato,
}: {
  active?: boolean;
  payload?: Array<{name: string; value: number; color: string}>;
  label?: number;
  unidade: string;
  formato: Intl.NumberFormat;
}) {
  if (!active || !payload?.length || label == null) {
    return null;
  }
  return (
    <Dica
      titulo={diaHora.format(label)}
      linhas={payload.map(e => ({
        cor: e.color,
        texto: `${e.name}: ${formato.format(e.value)} ${unidade}`,
      }))}
    />
  );
}

function SerieChart({
  dados,
  sentido,
  unidade,
  formato,
  descricao,
}: {
  dados: Dados;
  sentido?: (typeof SENTIDOS)[number]; // com sentido: fluxo; sem: ocupação (vale para os dois)
  unidade: string;
  formato: Intl.NumberFormat;
  descricao: string;
}) {
  const chaveDe = (id: string) => (sentido ? `${id}_${sentido}_fluxo` : `${id}_ocup`);
  // índice no array original mantém a cor da câmera igual em todos os gráficos
  const cams = dados.cameras
    .map((c, i) => ({c, i}))
    .filter(({c}) => !sentido || visivel(dados, c.id, sentido));
  if (!cams.length) {
    return (
      <Text type="supporting" color="secondary">
        Nenhuma câmera contou veículos suficientes neste sentido no período.
      </Text>
    );
  }
  // Rótulo direto no último ponto de cada linha: identidade não depende só da cor.
  // Em tela estreita o rótulo espremeria o gráfico; lá fica só a legenda.
  const estreito = window.matchMedia('(max-width: 640px)').matches;
  const ultimoIndice = (chave: string) =>
    estreito ? -1 : dados.serie.reduce((ult, p, i) => (p[chave] != null ? i : ult), -1);
  return (
    <VStack gap={3}>
      <ResponsiveContainer width="100%" height={280}>
        <LineChart
          data={dados.serie}
          margin={{top: 16, right: estreito ? 16 : 150, left: 0, bottom: 5}}
          accessibilityLayer
          role="img"
          aria-label={descricao}>
          <CartesianGrid horizontal vertical={false} stroke={GRADE} />
          <XAxis
            dataKey="t"
            type="number"
            scale="time"
            domain={['dataMin', 'dataMax']}
            tickFormatter={(v: number) => hora.format(v)}
            tick={EIXO}
            axisLine={false}
            tickLine={false}
            minTickGap={48}
          />
          <YAxis
            domain={[0, 'auto']}
            tickFormatter={(v: number) => numero.format(v)}
            tick={EIXO}
            axisLine={false}
            tickLine={false}
            width={48}
          />
          <Tooltip
            content={<SerieTooltip unidade={unidade} formato={formato} />}
            cursor={{stroke: GRADE}}
          />
          {cams.map(({c, i}) => {
            const chave = chaveDe(c.id);
            const ultimo = ultimoIndice(chave);
            return (
              <Line
                key={c.id}
                type="monotone"
                dataKey={chave}
                name={c.nome}
                stroke={CORES[i]}
                strokeWidth={2}
                dot={{r: 2.5, strokeWidth: 0, fill: CORES[i]}}
                activeDot={{r: 5}}
                connectNulls={false}
                animationDuration={600}
                label={(p: {index?: number; x?: number | string; y?: number | string}) =>
                  p.index === ultimo ? (
                    <text
                      x={Number(p.x ?? 0) + 8}
                      y={Number(p.y ?? 0) + 4}
                      fontSize="var(--font-size-sm, 12px)"
                      fill={TINTA}>
                      {c.nome}
                    </text>
                  ) : (
                    <g />
                  )
                }
              />
            );
          })}
        </LineChart>
      </ResponsiveContainer>
      <Legenda cameras={cams.map(({c}) => c)} cores={cams.map(({i}) => CORES[i])} />
    </VStack>
  );
}

function Sparkline({valores, cor, id}: {valores: number[]; cor: string; id: string}) {
  const data = valores.map((v, i) => ({i, v}));
  return (
    <ResponsiveContainer width="100%" height={48}>
      <AreaChart data={data} margin={{top: 4, right: 0, bottom: 0, left: 0}}>
        <defs>
          <linearGradient id={`grad-${id}`} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={cor} stopOpacity={0.35} />
            <stop offset="100%" stopColor={cor} stopOpacity={0} />
          </linearGradient>
        </defs>
        <Area
          type="monotone"
          dataKey="v"
          stroke={cor}
          strokeWidth={2}
          fill={`url(#grad-${id})`}
          animationDuration={600}
        />
      </AreaChart>
    </ResponsiveContainer>
  );
}

function DispersaoChart({dados}: {dados: Dados}) {
  return (
    <VStack gap={3}>
      <ResponsiveContainer width="100%" height={280}>
        <ScatterChart
          margin={{top: 16, right: 16, left: 0, bottom: 24}}
          role="img"
          aria-label="Gráfico de dispersão: cada ponto é um clipe, com a ocupação no eixo horizontal e o fluxo em veículos por hora no eixo vertical, por câmera.">
          <CartesianGrid stroke={GRADE} />
          <XAxis
            dataKey="o"
            type="number"
            name="Ocupação"
            domain={[0, 'auto']}
            tickFormatter={(v: number) => decimal.format(v)}
            tick={EIXO}
            axisLine={false}
            tickLine={false}
            label={{
              value: 'veículos visíveis por quadro',
              position: 'insideBottom',
              offset: -12,
              ...EIXO,
            }}
          />
          <YAxis
            dataKey="f"
            type="number"
            name="Fluxo"
            domain={[0, 'auto']}
            tickFormatter={(v: number) => numero.format(v)}
            tick={EIXO}
            axisLine={false}
            tickLine={false}
            width={48}
          />
          <Tooltip
            cursor={{stroke: GRADE}}
            content={({active, payload}) => {
              const p = payload?.[0]?.payload as {c: string; f: number; o: number} | undefined;
              if (!active || !p) {
                return null;
              }
              const i = dados.cameras.findIndex(c => c.id === p.c);
              return (
                <Dica
                  titulo={dados.cameras[i]?.nome ?? p.c}
                  linhas={[
                    {cor: CORES[i], texto: `${numero.format(p.f)} veículos/h`},
                    {texto: `${decimal.format(p.o)} veículos por quadro`},
                  ]}
                />
              );
            }}
          />
          {dados.cameras.map((c, i) => (
            <Scatter
              key={c.id}
              name={c.nome}
              data={dados.dispersao.filter(p => p.c === c.id && p.f != null)}
              fill={CORES[i]}
              fillOpacity={0.75}
              shape={FORMAS[i]}
              animationDuration={600}
            />
          ))}
        </ScatterChart>
      </ResponsiveContainer>
      <Legenda cameras={dados.cameras} />
    </VStack>
  );
}

function TiposChart({resumo, cor}: {resumo: Resumo; cor: string}) {
  const total = TIPOS.reduce((s, [k]) => s + (resumo.tipos[k] ?? 0), 0);
  const data = TIPOS.map(([k, nome]) => ({nome, n: resumo.tipos[k] ?? 0}));
  return (
    <ResponsiveContainer width="100%" height={168}>
      <BarChart
        data={data}
        layout="vertical"
        margin={{top: 0, right: 96, bottom: 0, left: 0}}
        role="img"
        aria-label={`Veículos por tipo em ${resumo.nome}: ${data.map(d => `${d.nome} ${d.n}`).join(', ')}.`}>
        <XAxis type="number" hide domain={[0, 'dataMax']} />
        <YAxis
          type="category"
          dataKey="nome"
          tick={EIXO}
          axisLine={false}
          tickLine={false}
          width={84}
        />
        <Tooltip
          cursor={{fill: GRADE}}
          content={({active, payload}) => {
            const p = payload?.[0]?.payload as {nome: string; n: number} | undefined;
            return active && p ? (
              <Dica
                titulo={resumo.nome}
                linhas={[
                  {
                    cor,
                    texto: `${p.nome}: ${numero.format(p.n)} (${porcento.format(total ? p.n / total : 0)})`,
                  },
                ]}
              />
            ) : null;
          }}
        />
        <Bar dataKey="n" fill={cor} barSize={14} radius={[0, 4, 4, 0]} animationDuration={600}>
          <LabelList
            dataKey="n"
            position="right"
            formatter={(v: unknown) =>
              `${numero.format(Number(v))} · ${porcento.format(total ? Number(v) / total : 0)}`
            }
            style={EIXO}
          />
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

const diaSemana = new Intl.DateTimeFormat('pt-BR', {
  timeZone: 'UTC',
  weekday: 'short',
  day: '2-digit',
  month: '2-digit',
});
const ROTULO_DIA = 88;
const CELULA = 24;
const TOPO_MAPA = 20;

// Mapa de cobertura: uma linha por dia, uma coluna por hora; quanto mais escuro,
// mais minutos de vídeo analisados. Sequencial de um tom só, 0 = célula vazia.
function CoberturaMapa({cobertura}: {cobertura: NonNullable<Dados['cobertura']>}) {
  const {dias, minutos} = cobertura;
  const largura = ROTULO_DIA + 24 * CELULA;
  const altura = TOPO_MAPA + dias.length * CELULA;
  const azul = CORES[0];
  const horasBoas = minutos.flat().filter(m => m >= 30).length;
  const diasComDado = minutos.filter(l => l.some(m => m > 0)).length;
  return (
    <VStack gap={3}>
      <svg
        viewBox={`0 0 ${largura} ${altura}`}
        width="100%"
        role="img"
        aria-label={`Mapa de cobertura dos últimos ${dias.length} dias: ${diasComDado} dias com coleta e ${horasBoas} horas com pelo menos 30 minutos de vídeo analisado.`}>
        {[0, 3, 6, 9, 12, 15, 18, 21].map(h => (
          <text
            key={h}
            x={ROTULO_DIA + h * CELULA + CELULA / 2}
            y={13}
            textAnchor="middle"
            fontSize={11}
            fill={TINTA}>
            {`${h}h`}
          </text>
        ))}
        {dias.map((d, i) => (
          <g key={d}>
            <text
              x={ROTULO_DIA - 8}
              y={TOPO_MAPA + i * CELULA + CELULA / 2 + 4}
              textAnchor="end"
              fontSize={11}
              fill={TINTA}>
              {diaSemana.format(new Date(`${d}T12:00:00Z`))}
            </text>
            {minutos[i].map((m, h) => (
              <rect
                key={h}
                x={ROTULO_DIA + h * CELULA + 1}
                y={TOPO_MAPA + i * CELULA + 1}
                width={CELULA - 2}
                height={CELULA - 2}
                rx={3}
                fill={m > 0 ? azul : 'none'}
                fillOpacity={m > 0 ? 0.15 + (0.85 * m) / 60 : 1}
                stroke={m > 0 ? 'none' : GRADE}>
                <title>{`${diaSemana.format(new Date(`${d}T12:00:00Z`))}, ${h}h: ${m} min de vídeo por câmera`}</title>
              </rect>
            ))}
          </g>
        ))}
      </svg>
      <HStack gap={4} vAlign="center" wrap="wrap">
        <Text type="supporting" color="secondary">
          Minutos analisados por hora:
        </Text>
        {[
          [0, 'nenhum'],
          [15, '15'],
          [30, '30'],
          [60, '60'],
        ].map(([m, rotulo]) => (
          <HStack key={rotulo} gap={2} vAlign="center">
            <svg width="14" height="14" aria-hidden="true">
              <rect
                x={1}
                y={1}
                width={12}
                height={12}
                rx={3}
                fill={Number(m) > 0 ? azul : 'none'}
                fillOpacity={Number(m) > 0 ? 0.15 + (0.85 * Number(m)) / 60 : 1}
                stroke={Number(m) > 0 ? 'none' : GRADE}
              />
            </svg>
            <Text type="supporting" color="secondary">
              {rotulo}
            </Text>
          </HStack>
        ))}
      </HStack>
      <Text type="supporting" color="secondary">
        {`${diasComDado} de ${dias.length} dias com coleta · ${horasBoas} horas com pelo menos 30 minutos analisados.`}
      </Text>
    </VStack>
  );
}

// ============= CARD COMPONENTS =============

function MetricCard({
  label,
  value,
  unidade,
  apoio,
  children,
}: {
  label: string;
  value: string;
  unidade: string;
  apoio: string;
  children?: ReactNode;
}) {
  return (
    <Card>
      <VStack gap={2}>
        <Heading level={4} accessibilityLevel={3}>
          {label}
        </Heading>
        <HStack gap={2} vAlign="end">
          <Heading level={2} type="display-3" accessibilityLevel={3}>
            {value}
          </Heading>
          <Text type="body" color="secondary">
            {unidade}
          </Text>
        </HStack>
        <Text type="supporting" color="secondary">
          {apoio}
        </Text>
        {children}
      </VStack>
    </Card>
  );
}

function ChartCard({
  titulo,
  apoio,
  children,
}: {
  titulo: string;
  apoio: string;
  children: ReactNode;
}) {
  return (
    <Card>
      <VStack gap={4}>
        <VStack gap={1}>
          <Heading level={4} accessibilityLevel={3}>
            {titulo}
          </Heading>
          <Text type="body" color="secondary">
            {apoio}
          </Text>
        </VStack>
        {children}
      </VStack>
    </Card>
  );
}

// ============= TABLE COMPONENTS =============

const colunas: TableColumn<Clipe>[] = [
  {
    key: 'utc',
    header: 'Horário',
    width: pixel(120),
    renderCell: (c: Clipe) => diaHora.format(new Date(c.utc)),
  },
  {key: 'camera', header: 'Câmera', width: proportional(1)},
  {key: 'desce', header: 'Para Icaraí', width: pixel(110)},
  {key: 'sobe', header: 'Para a ponte', width: pixel(120)},
  {
    key: 'fluxo_h',
    header: 'Veículos/h',
    width: pixel(110),
    renderCell: (c: Clipe) => (c.fluxo_h == null ? '' : numero.format(c.fluxo_h)),
  },
  {
    key: 'ocupacao',
    header: 'Ocupação',
    width: pixel(100),
    renderCell: (c: Clipe) => decimal.format(c.ocupacao),
  },
];

const minutos = (o: Ocorrencia) =>
  Math.round((new Date(o.fim_utc).getTime() - new Date(o.inicio_utc).getTime()) / 60_000) + 1;

// Ocorrência ainda em andamento: o último clipe dela é recente em relação à coleta.
const emAndamento = (o: Ocorrencia, dados: Dados) =>
  dados.veredito?.nivel !== 'pausado' &&
  dados.ultimo_clipe_utc != null &&
  new Date(dados.ultimo_clipe_utc).getTime() - new Date(o.fim_utc).getTime() <
    AO_VIVO_MIN * 60_000;

function Ocorrencias({
  lista,
  noMapa,
  aoVerNoMapa,
}: {
  lista: Ocorrencia[];
  noMapa: Record<string, string>; // nome da câmera → id, só as que têm posição no mapa
  aoVerNoMapa: (id: string) => void;
}) {
  return (
    <ChartCard
      titulo="Ocorrências nas últimas 24 horas"
      apoio="Quando um veículo fica parado no mesmo ponto por cerca de 3 minutos (3 clipes seguidos), quatro imagens vão para um modelo de IA local que diz se parece acidente, enguiço ou bloqueio. Classificação automática, não confirmada por pessoa: pode errar.">
      {lista.length ? (
        <VStack gap={4}>
          {lista.map(o => (
            <VStack key={`${o.camera}-${o.inicio_utc}`} gap={1}>
              <HStack gap={2} vAlign="center" wrap="wrap">
                <Badge
                  label={TIPO_OCORRENCIA[o.tipo].rotulo}
                  variant={TIPO_OCORRENCIA[o.tipo].variante}
                />
                <Text type="supporting" color="secondary">
                  {o.camera} · desde {diaHora.format(new Date(o.inicio_utc))} · parado
                  por ~{minutos(o)} min · confiança {CONFIANCA[o.confianca]}
                </Text>
              </HStack>
              <Text type="body">{o.descricao}</Text>
              {noMapa[o.camera] && (
                <HStack>
                  <Button
                    label="Ver no mapa"
                    variant="ghost"
                    size="sm"
                    onClick={() => aoVerNoMapa(noMapa[o.camera])}
                  />
                </HStack>
              )}
            </VStack>
          ))}
        </VStack>
      ) : (
        <Text type="body" color="secondary">
          Nenhum acidente, enguiço ou bloqueio detectado nas horas coletadas.
        </Text>
      )}
    </ChartCard>
  );
}

// ============= LEITURA RÁPIDA (topo da página) =============

const COR_VEREDITO = {
  ok: 'green',
  atencao: 'yellow',
  alerta: 'red',
  pausado: 'gray',
  sem_base: 'gray',
} as const;

function Veredito({dados}: {dados: Dados}) {
  const v = dados.veredito ?? {nivel: 'pausado' as const, texto: 'Sem dados no momento.'};
  const rotuloTopo =
    v.nivel === 'pausado'
      ? 'Coleta parada agora: o computador que mede está desligado ou sem conexão'
      : `Agora na saída da Ponte · atualizado às ${hora.format(new Date(dados.gerado_utc))}`;
  return (
    <Card variant={COR_VEREDITO[v.nivel]} padding={6}>
      <VStack gap={3}>
        <HStack gap={2} vAlign="center" wrap="wrap">
          <Badge label="Agora" variant="blue" />
          <Text type="body" color="secondary">
            {rotuloTopo}
          </Text>
        </HStack>
        <Heading level={2} type="display-3">
          {v.texto}
        </Heading>
        {v.detalhe && <Text type="large">{v.detalhe}</Text>}
        <Text type="body" color="secondary">
          Medido por inteligência artificial nas câmeras públicas da NitTrans, ainda sem
          conferência por amostragem: é uma indicação, não estatística oficial.
        </Text>
      </VStack>
    </Card>
  );
}

// ============= PONTOS CRÍTICOS DE SINISTROS =============

// Período da tabela da NitTrans: 1º/1/2024 a 31/10/2026.
const DIAS_NITTRANS = 1035;
const frequencia = (total: number) => {
  const dias = DIAS_NITTRANS / total;
  return dias < 1.5 ? `cerca de ${Math.round(total / DIAS_NITTRANS)} por dia` : `cerca de 1 a cada ${Math.round(dias)} dias`;
};

function PontosCriticos({s}: {s: Sinistros}) {
  const graves = s.prf.trechos.slice(0, 5);
  const anosPrf = s.prf.anos.length === 2 ? s.prf.anos[1] - s.prf.anos[0] + 1 : 1;
  const vias = s.nittrans.vias.slice(0, 10);
  return (
    <VStack gap={4}>
      <VStack gap={1}>
        <HStack gap={2} vAlign="center" wrap="wrap">
          <Heading level={3} accessibilityLevel={2}>
            Onde acontecem os sinistros
          </Heading>
          <Badge label={`Soma de ${s.prf.anos.join(' a ')}, não é o trânsito de hoje`} variant="orange" />
        </HStack>
        <Text type="body" color="secondary">
          Números acumulados em vários anos, de fontes oficiais (PRF e NitTrans), não das
          câmeras deste painel. Poucos trechos concentram a maior parte dos sinistros graves:
          é onde fiscalização, sinalização e obras rendem mais.
        </Text>
      </VStack>
      <Grid columns={{minWidth: 320, repeat: 'fit'}} gap={4}>
        <ChartCard
          titulo={`BR-101 e Ponte: trechos mais graves em ${anosPrf} anos`}
          apoio={`Soma de ${s.prf.anos.join(' a ')} (${s.prf.anos[1]} até agora), por quilômetro, ordenada por mortos mais feridos graves. Em Niterói, no período: ${numero.format(s.prf.total_sinistros)} sinistros, ${s.prf.total_mortos} mortos e ${s.prf.total_feridos_graves} feridos graves, cerca de ${Math.round(s.prf.total_mortos / anosPrf)} mortes por ano. ${s.prf.fora_do_mapa} boletins com rodovia, km ou coordenada incoerente ficaram fora do ranking e do mapa. Fonte: PRF, dados abertos.`}>
          <VStack gap={3}>
            {graves.map((t, i) => (
              <VStack key={t.nome} gap={0}>
                <Text type="body" weight="semibold">{`${i + 1}. ${t.nome}`}</Text>
                <Text type="body" color="secondary">
                  {`${t.mortos} ${t.mortos === 1 ? 'morto' : 'mortos'} e ${t.feridos_graves} feridos graves em ${t.sinistros} sinistros, em ${anosPrf} anos`}
                </Text>
              </VStack>
            ))}
          </VStack>
        </ChartCard>
        <ChartCard
          titulo="Vias municipais com mais sinistros em quase 3 anos"
          apoio="Soma de janeiro de 2024 a outubro de 2026. Conta quantidade, não gravidade. “Câmera contando”: este painel mede o trânsito na via. “Câmera sem contagem”: há câmera pública, mas ainda sem números deste projeto. Fonte: NitTrans, tabela publicada como imagem e transcrita aqui.">
          <VStack gap={3}>
            {vias.map((v, i) => {
              const cam = VIAS_COM_CAMERA[v.via];
              const n = cam ? `${cam.cameras} ${cam.cameras === 1 ? 'câmera' : 'câmeras'}` : '';
              return (
                <VStack key={v.via} gap={0}>
                  <HStack gap={2} vAlign="center" wrap="wrap">
                    <Text type="body" weight="semibold">{`${i + 1}. ${v.via}`}</Text>
                    {cam && (
                      <Badge
                        label={cam.contando ? 'Câmera contando' : 'Câmera sem contagem'}
                        variant={cam.contando ? 'green' : 'neutral'}
                      />
                    )}
                  </HStack>
                  <Text type="body" color="secondary">
                    {`${numero.format(v.total)} sinistros em quase 3 anos (${frequencia(v.total)})${cam ? ` · ${n}${cam.contando ? ', contadas por este painel' : ', contagem ainda não ligada'}` : ''}`}
                  </Text>
                </VStack>
              );
            })}
            <Text type="body">
              <Link href={s.nittrans.url}>Ver a tabela original na NitTrans</Link>
            </Text>
          </VStack>
        </ChartCard>
      </Grid>
    </VStack>
  );
}

// ============= ANTES E DEPOIS =============

const dataCurta = new Intl.DateTimeFormat('pt-BR', {timeZone: 'UTC', day: '2-digit', month: '2-digit', year: 'numeric'});

function AntesEDepois({lista}: {lista: AntesDepois[]}) {
  return (
    <ChartCard
      titulo="Antes e depois de mudanças na via"
      apoio="Quando a prefeitura muda algo num trecho medido (semáforo, faixas, lombada, pintura, obra), o painel compara o mesmo tipo de dia e o mesmo horário nas 4 semanas antes e depois, sem as horas com chuva. É comparação simples: não controla feriados, eventos ou mudanças em outros trechos.">
      {lista.length ? (
        <VStack gap={4}>
          {lista.map(i => (
            <VStack key={`${i.camera}-${i.data}`} gap={1}>
              <HStack gap={2} vAlign="center" wrap="wrap">
                <Badge
                  label={i.situacao === 'pronto' ? 'Resultado' : 'Aguardando dados'}
                  variant={i.situacao === 'pronto' ? 'blue' : 'neutral'}
                />
                <Text type="body" weight="semibold">
                  {`${i.nome} · ${i.tipo} em ${dataCurta.format(new Date(`${i.data}T12:00:00Z`))}`}
                </Text>
              </HStack>
              <Text type="body">{i.descricao}</Text>
              <Text type="body" color="secondary">
                {i.frase}
                {i.fonte ? ` Fonte: ${i.fonte}.` : ''}
              </Text>
            </VStack>
          ))}
        </VStack>
      ) : (
        <Text type="body" color="secondary">
          Nenhuma mudança registrada ainda. Cada mudança anunciada pela prefeitura ou pela
          NitTrans num ponto medido entra aqui com data e fonte, e o resultado aparece quando
          houver dados suficientes dos dois lados.
        </Text>
      )}
    </ChartCard>
  );
}

// ============= MAPA DA REGIÃO =============

const Mapa = lazy(() => import('./Mapa'));

// Cores dos pontos do mapa em hex: o Leaflet as escreve como atributo SVG.
const COR_MAPA = {
  livre: '#2f7d33',
  moderado: '#b8860b',
  pesado: '#c0262c',
  medido: '#185fa5',
  sem_contagem: '#7a828c',
} as const;

const ID_MAPA = 'mapa-regiao';

function MapaRegiao({
  dados,
  sinistros,
  foco,
}: {
  dados: Dados;
  sinistros: Sinistros | null;
  foco: FocoMapa | null;
}) {
  const aoVivo = dados.veredito?.nivel !== 'pausado';
  const ultimo = dados.periodos?.[0];
  const agoraOcorrencias = (dados.ocorrencias ?? []).filter(o => emAndamento(o, dados));
  const pontos = (dados.regiao ?? [])
    .filter(p => p.lat != null && p.lon != null)
    .map(p => {
      const s = dados.situacao?.[p.id];
      const noPeriodo = ultimo?.cameras.find(c => c.id === p.id);
      let cor: string = COR_MAPA.sem_contagem;
      let texto =
        'Câmera pública da NitTrans funcionando. Este projeto ainda não conta veículos nela: não há números deste ponto.';
      if (p.contada && aoVivo && s && (s.nivel === 'livre' || s.nivel === 'moderado' || s.nivel === 'pesado')) {
        cor = COR_MAPA[s.nivel];
        texto = `Agora: ${NOME_NIVEL[s.nivel]}.`;
      } else if (p.contada) {
        cor = COR_MAPA.medido;
        texto =
          noPeriodo && ultimo
            ? `${tituloPeriodo(ultimo)}: ${noPeriodo.minutos_pesado ? `acima do habitual por ${noPeriodo.minutos_pesado} min` : 'sem trânsito acima do habitual'}.`
            : 'Ponto medido; sem período recente.';
      }
      const oc = agoraOcorrencias.find(o => o.camera === p.nome);
      if (oc) {
        texto += ` Ocorrência agora: ${TIPO_OCORRENCIA[oc.tipo].rotulo.toLowerCase()} desde ${hora.format(new Date(oc.inicio_utc))} (classificação automática).`;
      }
      return {id: p.id, nome: p.nome, lat: p.lat!, lon: p.lon!, cor, texto, alerta: !!oc};
    });
  if (!pontos.length) {
    return null;
  }
  const legenda: Array<[string, string]> = aoVivo
    ? [
        [COR_MAPA.livre, 'Abaixo do habitual'],
        [COR_MAPA.moderado, 'Dentro do habitual'],
        [COR_MAPA.pesado, 'Acima do habitual'],
        [COR_MAPA.sem_contagem, 'Câmera sem contagem (sem números)'],
      ]
    : [
        [COR_MAPA.medido, 'Ponto medido (contagem ainda não conferida)'],
        [COR_MAPA.sem_contagem, 'Câmera sem contagem (sem números)'],
      ];
  return (
    <VStack gap={3}>
      <VStack gap={1}>
        <Heading level={3} accessibilityLevel={2}>
          Câmeras e sinistros no mapa
        </Heading>
        <Text type="body" color="secondary">
          Pontos são as câmeras, com a cor da situação agora. Manchas vermelhas são sinistros na
          BR-101 e na Ponte somados de vários anos, maiores onde há mais. Toque para ver o
          resumo. No canto do mapa, mostre ou esconda câmeras e sinistros. Posições das
          câmeras aproximadas.
        </Text>
      </VStack>
      <Suspense fallback={<Spinner label="Carregando o mapa" />}>
        <Mapa
          id={ID_MAPA}
          foco={foco}
          pontos={pontos}
          areas={(sinistros?.prf.trechos ?? [])
            .filter(t => t.lat != null && t.lon != null)
            .map(t => ({
              nome: t.nome,
              lat: t.lat!,
              lon: t.lon!,
              sinistros: t.sinistros,
              texto: `${t.sinistros} sinistros, ${t.mortos} mortos e ${t.feridos_graves} feridos graves de ${sinistros!.prf.anos.join(' a ')} (PRF).`,
            }))}
          descricao={`Mapa da saída da Ponte com ${pontos.length} câmeras: ${pontos.map(p => p.nome).join(', ')}.`}
        />
      </Suspense>
      <HStack gap={4} vAlign="center" wrap="wrap">
        {sinistros && (
          <HStack gap={2} vAlign="center">
            <svg width="16" height="16" aria-hidden="true">
              <circle cx={8} cy={8} r={7} fill="#b42318" fillOpacity={0.35} />
            </svg>
            <Text type="body">Sinistros na BR-101 e na Ponte, soma de 2022 a 2026 (PRF)</Text>
          </HStack>
        )}
        {legenda.map(([cor, nome]) => (
          <HStack key={nome} gap={2} vAlign="center">
            <svg width="16" height="16" aria-hidden="true">
              <circle cx={8} cy={8} r={6} fill={cor} stroke="#ffffff" strokeWidth={2} />
            </svg>
            <Text type="body">{nome}</Text>
          </HStack>
        ))}
        {aoVivo && (
          <HStack gap={2} vAlign="center">
            <svg width="16" height="16" aria-hidden="true">
              <circle cx={8} cy={8} r={5} fill="#7a828c" stroke="#f5b400" strokeWidth={3} />
            </svg>
            <Text type="body">Contorno amarelo: ocorrência agora (acidente, enguiço ou bloqueio)</Text>
          </HStack>
        )}
      </HStack>
      <Text type="body" color="secondary">
        Só as 2 câmeras da Jansen de Melo são contadas, e essa contagem ainda não foi conferida
        por amostragem: use como indicação.
      </Text>
    </VStack>
  );
}

// ============= RESUMO POR PERÍODO (7 dias, 30 dias, total) =============

const NOME_JANELA: Record<Janela, string> = {
  '7d': 'Últimos 7 dias',
  '30d': 'Últimos 30 dias',
  total: 'Histórico total',
};

// 24 células, uma por hora do dia, da cor do nível típico daquela hora.
function PerfilDia({perfil, nome}: {perfil: Array<Nivel | null>; nome: string}) {
  const largura = 24 * CELULA_FAIXA;
  return (
    <svg
      viewBox={`-16 0 ${largura + 32} ${ALTURA_FAIXA + 18}`}
      width="100%"
      style={{maxWidth: largura + 32}}
      role="img"
      aria-label={`${nome}, nível típico de cada hora do dia.`}>
      {perfil.map((nivel, h) => (
        <rect
          key={h}
          x={h * CELULA_FAIXA + 1}
          y={0}
          width={CELULA_FAIXA - 2}
          height={ALTURA_FAIXA}
          rx={3}
          fill={nivel ? COR_NIVEL[nivel] : 'none'}
          stroke={nivel ? 'none' : GRADE}>
          <title>{`${h}h: ${nivel ? NOME_NIVEL[nivel] : 'sem medição'}`}</title>
        </rect>
      ))}
      {[0, 6, 12, 18, 23].map(h => (
        <text
          key={h}
          x={h * CELULA_FAIXA + CELULA_FAIXA / 2}
          y={ALTURA_FAIXA + 14}
          textAnchor="middle"
          fontSize={12}
          fill={TINTA}>
          {`${h}h`}
        </text>
      ))}
    </svg>
  );
}

function ResumoPeriodo({janela, dados}: {janela: Janela; dados: Dados}) {
  const r = dados.resumos?.[janela];
  if (!r || !r.cameras.length) {
    return (
      <Text type="body" color="secondary">
        Ainda não há medições neste período.
      </Text>
    );
  }
  const desde = r.desde_utc ? diaHora.format(new Date(r.desde_utc)) : '';
  return (
    <VStack gap={4}>
      <VStack gap={2}>
        <Heading level={2} type="display-3">
          {NOME_JANELA[janela]}
        </Heading>
        <Text type="body" color="secondary">
          {`${r.dias_com_dados} ${r.dias_com_dados === 1 ? 'dia' : 'dias'} com coleta desde ${desde} · ${r.ocorrencias} ${r.ocorrencias === 1 ? 'ocorrência publicada' : 'ocorrências publicadas'}. Cada quadradinho compara com o habitual do mesmo dia e hora (acima do habitual: mais carregado que 85% dos registros).`}
        </Text>
        <LegendaNiveis />
      </VStack>
      <Grid columns={{minWidth: 320, repeat: 'fit'}} gap={4}>
        {r.cameras.map(c => {
          const fluxos = SENTIDOS.filter(s => (c.fluxo_h[s] ?? 0) >= MIN_TOTAL).map(
            s => `${numero.format(c.fluxo_h[s] ?? 0)} veículos/h ${rotuloMin(dados, s)}`,
          );
          return (
            <Card key={c.id}>
              <VStack gap={3}>
                <Heading level={4} accessibilityLevel={3}>
                  {c.nome}
                </Heading>
                <Heading level={3} accessibilityLevel={4}>
                  {c.pct_pesado == null
                    ? 'Ainda sem base para comparar com este dia e hora'
                    : `Acima do habitual em ${c.pct_pesado}% do tempo medido`}
                </Heading>
                <Text type="body">{`Pior horário: por volta das ${c.pior_hora}h.`}</Text>
                <VStack gap={1}>
                  <Text type="body" color="secondary">
                    Formato do dia: quais horas são mais cheias que o resto do dia
                  </Text>
                  <PerfilDia perfil={c.perfil} nome={c.nome} />
                  <LegendaNiveis perfil />
                </VStack>
                <Text type="body" color="secondary">
                  {[
                    fluxos.length ? `Média: ${fluxos.join(', ')}` : '',
                    c.onibus_h ? `ônibus: ~${numero.format(c.onibus_h)} por hora (estimativa)` : '',
                    `${decimal.format(c.horas_video)} h de vídeo analisadas`,
                  ]
                    .filter(Boolean)
                    .join(' · ')}
                </Text>
              </VStack>
            </Card>
          );
        })}
      </Grid>
    </VStack>
  );
}

// ============= HISTÓRICO DA COLETA =============

// Pesado é bem mais escuro que os outros dois: dá para distinguir sem enxergar cor.
const COR_NIVEL: Record<Nivel, string> = {
  livre: 'var(--color-border-green, #aad4a9)',
  moderado: 'var(--color-border-yellow, #e3c36c)',
  pesado: 'var(--color-icon-error, #c0262c)',
};
const NOME_NIVEL: Record<Nivel, string> = {
  livre: 'abaixo do habitual',
  moderado: 'dentro do habitual',
  pesado: 'acima do habitual',
};
const NOME_PERFIL: Record<Nivel, string> = {
  livre: 'hora mais vazia do dia',
  moderado: 'hora média',
  pesado: 'hora mais cheia do dia',
};
const CELULA_FAIXA = 14;
const ALTURA_FAIXA = 22;

const horaCurta = new Intl.DateTimeFormat('pt-BR', {
  timeZone: FUSO,
  hour: '2-digit',
  minute: '2-digit',
});

// Uma célula por 5 minutos, da cor do nível; vazia onde não houve medição.
// Marca de hora a cada 30 minutos embaixo. O texto do período diz o mesmo em palavras.
function Faixa({cam, periodo}: {cam: Periodo['cameras'][number]; periodo: Periodo}) {
  const n = cam.faixa.length;
  const t0 = new Date(periodo.inicio_t).getTime();
  const passo = periodo.balde_min * 60_000;
  const largura = Math.max(n, 1) * CELULA_FAIXA;
  const marcas = cam.faixa
    .map((_, i) => i)
    .filter(i => new Date(t0 + i * passo).getMinutes() % 30 === 0);
  return (
    <svg
      viewBox={`-16 0 ${largura + 32} ${ALTURA_FAIXA + 18}`}
      width="100%"
      style={{maxWidth: largura + 32}}
      role="img"
      aria-label={`${cam.nome}, de 5 em 5 minutos: ${cam.minutos_pesado} minutos acima do habitual.`}>
      {cam.faixa.map((nivel, i) => (
        <rect
          key={i}
          x={i * CELULA_FAIXA + 1}
          y={0}
          width={CELULA_FAIXA - 2}
          height={ALTURA_FAIXA}
          rx={3}
          fill={nivel ? COR_NIVEL[nivel] : 'none'}
          stroke={nivel ? 'none' : GRADE}>
          <title>{`${horaCurta.format(t0 + i * passo)}: ${nivel ? NOME_NIVEL[nivel] : 'sem medição'}`}</title>
        </rect>
      ))}
      {marcas.map(i => (
        <text
          key={i}
          x={i * CELULA_FAIXA + CELULA_FAIXA / 2}
          y={ALTURA_FAIXA + 14}
          textAnchor="middle"
          fontSize={12}
          fill={TINTA}>
          {horaCurta.format(t0 + i * passo)}
        </text>
      ))}
    </svg>
  );
}

function LegendaNiveis({perfil = false}: {perfil?: boolean}) {
  const nomes = perfil ? NOME_PERFIL : NOME_NIVEL;
  return (
    <HStack gap={4} vAlign="center" wrap="wrap">
      {(['livre', 'moderado', 'pesado'] as const).map(n => (
        <HStack key={n} gap={2} vAlign="center">
          <svg width="16" height="16" aria-hidden="true">
            <rect x={1} y={1} width={14} height={14} rx={3} fill={COR_NIVEL[n]} />
          </svg>
          <Text type="body">{nomes[n].charAt(0).toUpperCase() + nomes[n].slice(1)}</Text>
        </HStack>
      ))}
      <HStack gap={2} vAlign="center">
        <svg width="16" height="16" aria-hidden="true">
          <rect x={1} y={1} width={14} height={14} rx={3} fill="none" stroke={GRADE} />
        </svg>
        <Text type="body">Sem medição</Text>
      </HStack>
    </HStack>
  );
}

const tituloPeriodo = (p: Periodo) => {
  const dia = p.dia === 'hoje' ? 'Hoje' : p.dia === 'ontem' ? 'Ontem' : p.dia;
  return `${dia}, das ${horaCurta.format(new Date(p.inicio_utc))} às ${horaCurta.format(new Date(p.fim_utc))}`;
};

function CartaoPeriodo({p, dados}: {p: Periodo; dados: Dados}) {
  return (
    <Card>
      <VStack gap={4}>
        <VStack gap={1}>
          <Heading level={4} accessibilityLevel={3}>
            {tituloPeriodo(p)}
          </Heading>
          <Text type="body">{p.frase}</Text>
        </VStack>
        {p.cameras.map(c => {
          const fluxos = SENTIDOS.filter(s => (c.fluxo_h[s] ?? 0) >= MIN_TOTAL).map(
            s => `${numero.format(c.fluxo_h[s] ?? 0)} veículos/h ${rotuloMin(dados, s)}`,
          );
          return (
            <VStack key={c.id} gap={2}>
              <Text type="body" weight="semibold">
                {c.nome}
              </Text>
              <Faixa cam={c} periodo={p} />
              <Text type="body" color="secondary">
                {[
                  fluxos.length ? `Média: ${fluxos.join(', ')}` : '',
                  c.onibus_h ? `ônibus: ~${numero.format(c.onibus_h)} por hora (estimativa)` : '',
                ]
                  .filter(Boolean)
                  .join(' · ')}
              </Text>
            </VStack>
          );
        })}
      </VStack>
    </Card>
  );
}

const PERIODOS_VISIVEIS = 3;

function Historico({dados}: {dados: Dados}) {
  const lista = dados.periodos ?? [];
  if (!lista.length) {
    return null;
  }
  return (
    <VStack gap={4}>
      <VStack gap={2}>
        <HStack gap={2} vAlign="center" wrap="wrap">
          <Heading level={3} accessibilityLevel={2}>
            Histórico da coleta
          </Heading>
          <Badge label="Últimos 7 dias, em blocos de 3 horas" variant="neutral" />
        </HStack>
        <Text type="body" color="secondary">
          Cada bloco é um período em que as câmeras foram medidas. Cada quadradinho são 5
          minutos, comparados com o habitual daquele dia e hora. Habitual é o que a mesma câmera registrou no mesmo tipo de dia (útil ou fim de semana) e na mesma hora, em pelo menos 3 dias diferentes. Acima do habitual é mais carregado que 85% desses registros. Sem base suficiente, o painel diz que ainda não dá para comparar.
        </Text>
        <LegendaNiveis />
        <Text type="body">
          Receba o resumo de cada período: <Link href="feed.xml">feed RSS</Link>, que também
          pode ser ligado a redes sociais. Dados abertos, uma linha por câmera e hora, com a
          chuva: <Link href="dados-por-hora.csv">baixar CSV</Link>.
        </Text>
      </VStack>
      {lista.slice(0, PERIODOS_VISIVEIS).map(p => (
        <CartaoPeriodo key={p.inicio_utc} p={p} dados={dados} />
      ))}
      {lista.length > PERIODOS_VISIVEIS && (
        <Collapsible
          defaultIsOpen={false}
          trigger={
            <Text type="body" weight="semibold">
              {`Ver ${lista.length - PERIODOS_VISIVEIS} períodos anteriores`}
            </Text>
          }>
          <VStack gap={4}>
            {lista.slice(PERIODOS_VISIVEIS).map(p => (
              <CartaoPeriodo key={p.inicio_utc} p={p} dados={dados} />
            ))}
          </VStack>
        </Collapsible>
      )}
    </VStack>
  );
}

type Dot = 'success' | 'warning' | 'error' | 'accent' | 'neutral';

// O texto sempre acompanha a cor: quem não distingue cores lê a mesma informação.
function statusDoPonto(p: PontoRegiao, s?: Situacao): {dot: Dot; texto: string} {
  if (p.estado === 'fora') {
    return {dot: 'error', texto: 'Câmera fora do ar'};
  }
  if (p.estado === 'parada') {
    const desde = p.ultimo_video_utc ? ` desde ${hora.format(new Date(p.ultimo_video_utc))}` : '';
    return {dot: 'warning', texto: `Imagem parada${desde}`};
  }
  if (!p.contada) {
    return p.estado === 'no_ar'
      ? {dot: 'neutral', texto: 'No ar · contagem ainda não ligada'}
      : {dot: 'neutral', texto: 'Sem verificação recente'};
  }
  switch (s?.nivel) {
    case 'livre':
      return {dot: 'success', texto: 'Abaixo do habitual para esta hora'};
    case 'moderado':
      return {dot: 'warning', texto: 'Dentro do habitual para esta hora'};
    case 'pesado':
      return {dot: 'error', texto: 'Acima do habitual para esta hora'};
    case 'sem_historico':
      return {dot: 'neutral', texto: 'Medindo · ainda sem base para comparar com este dia e hora'};
    default:
      return {dot: 'neutral', texto: 'Sem medição agora'};
  }
}

const intervalo = (min: number) =>
  min < 1 ? `um a cada ${Math.round(min * 60)} s` : `um a cada ${decimal.format(min)} min`;

function Ponto({p, dados}: {p: PontoRegiao; dados: Dados}) {
  const st = statusDoPonto(p, dados.situacao?.[p.id]);
  const bus = dados.onibus?.[p.id];
  const t = dados.tendencia?.[p.id];
  // 30 e 60 min só aparecem com vídeo suficiente na janela (exportar.tendencia)
  const janelas = t
    ? (
        [
          ['30 min', t.m30],
          ['60 min', t.m60],
        ] as const
      )
        .filter(([, v]) => v != null)
        .map(([rotulo, v]) => `${rotulo}: ${numero.format(v!)}`)
    : [];
  return (
    <VStack gap={1}>
      <HStack gap={2} vAlign="center">
        <StatusDot variant={st.dot} label={st.texto} />
        <Text type="body" weight="semibold">
          {p.nome}
        </Text>
      </HStack>
      <Heading level={4} accessibilityLevel={3}>
        {st.texto}
      </Heading>
      {t && t.m15 != null && (
        <VStack gap={0}>
          <Text type="body">
            {`Movimento: ${numero.format(t.m15)} veículos/h nos últimos 15 min${t.direcao ? `, ${DIRECAO[t.direcao]}` : ''}`}
          </Text>
          {janelas.length > 0 && (
            <Text type="body" color="secondary">
              {`Últimos ${janelas.join(' · ')}`}
            </Text>
          )}
        </VStack>
      )}
      {bus && bus.por_hora > 0 && bus.intervalo_min != null && (
        <Text type="body" color="secondary">
          {`Ônibus na última hora: ~${numero.format(bus.por_hora)} (${intervalo(bus.intervalo_min)}), estimativa`}
        </Text>
      )}
    </VStack>
  );
}

// Só os pontos que a coleta mede de fato; os outros viram uma linha "em breve".
function Regiao({dados}: {dados: Dados}) {
  const regiao = dados.regiao ?? [];
  const medidos = regiao.filter(p => p.contada);
  const emBreve = regiao.filter(p => !p.contada);
  if (!medidos.length) {
    return null;
  }
  return (
    <VStack gap={4}>
      <VStack gap={1}>
        <Heading level={3} accessibilityLevel={2}>
          Agora, ponto a ponto
        </Heading>
        <Text type="body" color="secondary">
          Últimos 15 minutos comparados com o habitual do mesmo tipo de dia e da mesma hora, na
          mesma câmera. O movimento soma os dois sentidos e diz se está subindo ou descendo em
          relação aos 45 minutos anteriores, sem depender do habitual.
        </Text>
      </VStack>
      <Grid columns={{minWidth: 260, repeat: 'fit'}} gap={4}>
        {medidos.map(p => (
          <Card key={p.id}>
            <Ponto p={p} dados={dados} />
          </Card>
        ))}
      </Grid>
      {emBreve.length > 0 && (
        <Text type="body" color="secondary">
          {`Outras câmeras públicas da região, funcionando mas ainda sem contagem por este projeto (não há números delas): ${emBreve.map(p => p.nome).join(', ')}.`}
        </Text>
      )}
    </VStack>
  );
}

function CamerasPublicas({regiao}: {regiao: PontoRegiao[]}) {
  if (!regiao.length) {
    return null;
  }
  const noAr = regiao.filter(p => p.estado === 'no_ar').length;
  const problemas = regiao.filter(p => p.estado === 'fora' || p.estado === 'parada');
  // Com a coleta parada não há verificação recente: o cartão sairia vazio.
  if (regiao.every(p => p.estado === 'sem_verificacao')) {
    return null;
  }
  return (
    <ChartCard
      titulo="Câmeras públicas da região"
      apoio="Verificado a cada 5 minutos enquanto a coleta roda: a câmera responde e a imagem foi renovada há menos de 10 minutos.">
      <VStack gap={3}>
          <HStack gap={2} vAlign="end">
            <Heading level={2} type="display-3" accessibilityLevel={3}>
              {`${noAr} de ${regiao.length}`}
            </Heading>
            <Text type="body" color="secondary">
              no ar
            </Text>
          </HStack>
          {problemas.map(p => (
            <HStack key={p.id} gap={2} vAlign="center">
              <StatusDot variant={p.estado === 'fora' ? 'error' : 'warning'} label={p.estado} />
              <Text type="body">{`${p.nome}: ${statusDoPonto(p).texto.toLowerCase()}`}</Text>
            </HStack>
          ))}
      </VStack>
    </ChartCard>
  );
}

// ============= MAIN COMPONENT =============

function Conteudo({dados}: {dados: Dados}) {
  if (!dados.ultimo_clipe_utc) {
    return (
      <EmptyState
        title="Ainda não há dados"
        description="Nenhum clipe foi coletado nas últimas 24 horas. O painel se atualiza sozinho quando a coleta recomeçar."
      />
    );
  }
  const fluxos = (id: string, s: string) =>
    dados.serie.map(p => p[`${id}_${s}_fluxo`]).filter((v): v is number => v != null);
  return (
    <>
      {/* Metric Cards: um por câmera e sentido, o sentido Icaraí primeiro */}
      <Grid columns={{minWidth: 320, repeat: 'fit'}} gap={4}>
        <Grid columns={{minWidth: 240, repeat: 'fit'}} gap={4}>
          {SENTIDOS.flatMap(s =>
            dados.resumo
              .map((r, i) => ({r, i}))
              .filter(({r}) => visivel(dados, r.id, s))
              .map(({r, i}) => {
                const f = r.por_sentido?.[s]?.fluxo_h ?? null;
                const serie = fluxos(r.id, s);
                return (
                  <MetricCard
                    key={`${r.id}-${s}`}
                    label={rotulo(dados, s)}
                    value={f == null ? 'sem dados' : numero.format(f)}
                    unidade={f == null ? '' : 'veículos/h'}
                    apoio={`${r.nome} · média da última hora coletada${r.sentido_confirmado === false ? ' · sentido a confirmar' : ''}`}>
                    {serie.length > 1 && (
                      <Sparkline valores={serie} cor={CORES[i]} id={`${r.id}-${s}`} />
                    )}
                  </MetricCard>
                );
              }),
          )}
        </Grid>
        <Grid columns={{minWidth: 240, repeat: 'fit'}} gap={4}>
          <MetricCard
            label="Veículos contados"
            value={numero.format(dados.total_veiculos)}
            unidade="nas últimas 24 h"
            apoio="Câmeras somadas; o mesmo veículo pode ser contado em duas câmeras"
          />
          <MetricCard
            label="Clipes analisados"
            value={numero.format(dados.total_clipes)}
            unidade="nas últimas 24 h"
            apoio="Cada clipe tem cerca de 60 segundos de vídeo"
          />
        </Grid>
      </Grid>

      {/* Cobertura */}
      <ChartCard
        titulo="Cobertura da coleta"
        apoio="Quais horas dos últimos 14 dias têm dado. Desde 19/11/2026 a coleta roda o dia todo; antes, só nos picos. Buracos são horas em que o computador que mede ficou parado.">
        {dados.cobertura ? (
          <CoberturaMapa cobertura={dados.cobertura} />
        ) : (
          <Text type="supporting" color="secondary">
            Mapa indisponível nesta atualização.
          </Text>
        )}
      </ChartCard>

      <Divider />

      {/* Ao longo do tempo */}
      <Heading level={3} accessibilityLevel={2}>
        Ao longo do tempo
      </Heading>
      <Grid columns={{minWidth: 420, repeat: 'fit'}} gap={4}>
        {SENTIDOS.map(s => (
          <ChartCard
            key={s}
            titulo={`Fluxo · ${rotuloMin(dados, s)}`}
            apoio={`Veículos por hora que cruzam a linha de contagem, em médias de ${dados.balde_min} minutos. Horário de Brasília. ${notaSentido(dados, s)}`}>
            <SerieChart
              dados={dados}
              sentido={s}
              unidade="veículos/h"
              formato={numero}
              descricao={`Gráfico de linhas do fluxo de veículos por hora ${rotuloMin(dados, s)}, por câmera, ao longo do tempo. Os mesmos dados estão na tabela de últimos clipes.`}
            />
          </ChartCard>
        ))}
        <ChartCard
          titulo="Ocupação"
          apoio="Média de veículos visíveis por quadro. Sobe quando há fila, mesmo que o fluxo caia.">
          <SerieChart
            dados={dados}
            unidade="veículos por quadro"
            formato={decimal}
            descricao="Gráfico de linhas da ocupação média de cada câmera ao longo do tempo. Os mesmos dados estão na tabela de últimos clipes."
          />
        </ChartCard>
      </Grid>

      <Divider />

      {/* Retrato do período */}
      <Heading level={3} accessibilityLevel={2}>
        Retrato das últimas 24 horas
      </Heading>
      <Grid columns={{minWidth: 420, repeat: 'fit'}} gap={4}>
        <ChartCard
          titulo="Fluxo × ocupação"
          apoio="Cada ponto é um clipe. Com trânsito livre, os dois sobem juntos; quando há fila, a ocupação sobe e o fluxo cai.">
          <DispersaoChart dados={dados} />
        </ChartCard>
        <VStack gap={4}>
          {dados.resumo.map((r, i) => (
            <ChartCard
              key={r.id}
              titulo={`Tipos de veículo · ${r.nome}`}
              apoio="Veículos contados por tipo e participação no total da câmera.">
              <TiposChart resumo={r} cor={CORES[i]} />
            </ChartCard>
          ))}
        </VStack>
      </Grid>

      <Divider />

      {/* Últimos clipes */}
      <VStack gap={4}>
        <Heading level={3} accessibilityLevel={2}>
          Últimos clipes analisados
        </Heading>
        <Table<Clipe>
          data={dados.ultimos}
          columns={colunas}
          idKey={(c: Clipe) => `${c.camera}-${c.utc}`}
          density="compact"
          dividers="rows"
          hasHover
        />
      </VStack>
    </>
  );
}

function Estado({dados, agora}: {dados: Dados; agora: number}) {
  if (!dados.ultimo_clipe_utc) {
    return null;
  }
  const ultimo = new Date(dados.ultimo_clipe_utc);
  const aoVivo = agora - ultimo.getTime() < AO_VIVO_MIN * 60_000;
  const texto = aoVivo
    ? `Coletando agora · último clipe às ${hora.format(ultimo)}`
    : `Coleta pausada · último clipe em ${diaHora.format(ultimo)}`;
  return (
    <HStack gap={2} vAlign="center">
      <StatusDot variant={aoVivo ? 'success' : 'neutral'} label={texto} isPulsing={aoVivo} />
      <Text type="supporting" color="secondary">
        {texto}
      </Text>
    </HStack>
  );
}

export default function Painel() {
  const {dados, erro, agora} = useDados();
  const sinistros = useSinistros();
  const [vista, setVista] = useState<Vista>('agora');
  const [foco, setFoco] = useState<FocoMapa | null>(null);
  const noMapa = Object.fromEntries(
    (dados?.regiao ?? []).filter(p => p.lat != null && p.lon != null).map(p => [p.nome, p.id]),
  );
  const verNoMapa = (id: string) => {
    setFoco({id, vez: Date.now()});
    document.getElementById(ID_MAPA)?.scrollIntoView({behavior: 'smooth', block: 'center'});
  };
  return (
    <Layout
      height="fill"
      content={
        <LayoutContent padding={6}>
          <VStack gap={6}>
            <Topo atual="painel" />
            <HStack hAlign="between" vAlign="end" wrap="wrap" gap={4}>
              <VStack gap={1}>
                <Heading level={1} type="display-3">
                  Trânsito na saída da Ponte
                </Heading>
                <Text type="body" color="secondary">
                  Ilha da Conceição, Fonseca, Jansen de Melo e Centro, medidos pelas câmeras
                  públicas da NitTrans.
                </Text>
                <Text type="body" color="secondary">
                  Internet fraca? <Link href="texto.html">Versão só texto</Link>, sem gráficos
                  nem mapa.
                </Text>
              </VStack>
              {dados && <Estado dados={dados} agora={agora} />}
            </HStack>

            {erro && (
              <Banner
                status="error"
                title="Não foi possível carregar os dados"
                description="O painel tenta de novo a cada minuto."
              />
            )}

            {dados ? (
              <>
                <VStack gap={2}>
                  <SegmentedControl
                    value={vista}
                    onChange={v => setVista(v as Vista)}
                    label="Período mostrado"
                    layout="fill">
                    <SegmentedControlItem value="agora" label="Agora" />
                    <SegmentedControlItem value="7d" label="7 dias" />
                    <SegmentedControlItem value="30d" label="30 dias" />
                    <SegmentedControlItem value="total" label="Tudo" />
                  </SegmentedControl>
                  <Text type="body" color="secondary">
                    Cada bloco da página diz de que período são os números.
                  </Text>
                </VStack>
                {vista === 'agora' ? (
                  <>
                    <Veredito dados={dados} />
                    {dados.veredito?.nivel !== 'pausado' && <Regiao dados={dados} />}
                    <Grid columns={{minWidth: 320, repeat: 'fit'}} gap={4}>
                      <Ocorrencias
                        lista={dados.ocorrencias ?? []}
                        noMapa={noMapa}
                        aoVerNoMapa={verNoMapa}
                      />
                      <CamerasPublicas regiao={dados.regiao ?? []} />
                    </Grid>
                  </>
                ) : (
                  <>
                    <ResumoPeriodo janela={vista} dados={dados} />
                    {vista === '7d' && <Historico dados={dados} />}
                  </>
                )}
                <MapaRegiao dados={dados} sinistros={sinistros} foco={foco} />
                {sinistros && <PontosCriticos s={sinistros} />}
                <AntesEDepois lista={dados.antes_depois ?? []} />
                <Divider />
                <Collapsible
                  defaultIsOpen={false}
                  trigger={
                    <Heading level={3} accessibilityLevel={2}>
                      Detalhes técnicos: fluxo por sentido, ocupação e cobertura
                    </Heading>
                  }>
                  <VStack gap={6}>
                    <Conteudo dados={dados} />
                  </VStack>
                </Collapsible>
              </>
            ) : erro ? null : (
              <Spinner label="Carregando dados" />
            )}

            <Divider />

            <VStack gap={2}>
              <Heading level={3} accessibilityLevel={2}>
                Como é medido
              </Heading>
              <Text type="body">
                Um programa baixa o clipe público de cerca de 60 segundos de cada
                câmera, detecta carros, motos, ônibus e caminhões e conta os que
                cruzam uma linha fixa na imagem. O vídeo é apagado logo após a
                contagem: só os números são guardados, sem placas nem imagens.
                Quando um veículo fica parado em dois clipes seguidos, quatro
                imagens são analisadas por um modelo de IA que roda no próprio
                computador do autor, sem enviar imagem a terceiros; as imagens
                não são guardadas, só o texto da resposta.
              </Text>
              <Text type="body">
                O fluxo é separado por sentido: na Jansen x Marechal Deodoro, o
                lado esquerdo da imagem é o que vem da ponte para Icaraí e o
                direito é o que vai para a ponte (sentido confirmado). A câmera
                Jansen sentido Ponte mostra os dois sentidos; qual lado é qual
                ainda está sendo confirmado. Os intervalos sem linha nos gráficos são períodos
                em que a coleta não rodou. Estudo cívico independente do
                Labs.fanara.com.br, sem vínculo com a Prefeitura de Niterói.
                Código aberto (AGPL-3.0):{' '}
                <Link href="https://github.com/estudio-max/transito-niteroi">repositório no GitHub</Link>.
              </Text>
              <Text type="body">
                O que cada gráfico mostra e como ler:{' '}
                <Link href="/sobre/#guia">guia dos gráficos</Link>.
              </Text>
            </VStack>
          </VStack>
        </LayoutContent>
      }
    />
  );
}
