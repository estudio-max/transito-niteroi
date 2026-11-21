import {useEffect, useState} from 'react';

// Sinistros de trânsito (sinistros.py → sinistros.json): tipos, filtro e carregamento,
// usados pela página Sinistros e pela camada de sinistros do mapa do painel.

// Pontos críticos de sinistros (sinistros.py): PRF nas rodovias federais e o ranking
// de vias da NitTrans, transcrito da tabela publicada em imagem.
export interface Sinistros {
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
      grupos?: Record<string, GrupoSinistro>; // por categoria (sinistros.categoria)
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

export interface GrupoSinistro {
  n: number;
  vitimas: number; // sinistros com ferido ou morto
  fatais: number; // sinistros com morto
  mortos: number;
  feridos_graves: number;
}

// Filtro dos sinistros da PRF (mapa e ranking). A tabela da NitTrans não tem tipo nem gravidade.
export type Gravidade = 'todos' | 'vitimas' | 'fatais';
export interface FiltroSinistros {
  gravidade: Gravidade;
  tipo: string; // 'todos' ou uma chave de CATEGORIAS
}
// Rótulos curtos: os três cabem no celular sem cortar ("Vítimas" = feridos ou mortos).
export const GRAVIDADES: Array<[Gravidade, string]> = [
  ['todos', 'Todos'],
  ['vitimas', 'Vítimas'],
  ['fatais', 'Mortes'],
];
export const CATEGORIAS: Array<[string, string]> = [
  ['colisao', 'Colisões'],
  ['queda', 'Quedas de moto e de ocupantes'],
  ['atropelamento', 'Atropelamentos'],
  ['tombamento', 'Tombamentos e saídas de pista'],
  ['outros', 'Outros (incêndio, carga, etc.)'],
];
export const ROTULO_GRAVIDADE: Record<Gravidade, [string, string]> = {
  todos: ['sinistro', 'sinistros'],
  vitimas: ['sinistro com vítimas', 'sinistros com vítimas'],
  fatais: ['sinistro com morte', 'sinistros com mortes'],
};

// Trechos da PRF com o que o filtro escolhe: quantos sinistros, mortos e feridos graves.
// Sem `grupos` (sinistros.json antigo), só o filtro "todos/todos" tem dado.
export function trechosFiltrados(s: Sinistros, f: FiltroSinistros) {
  return s.prf.trechos
    .map(t => {
      const grupos = Object.entries(t.grupos ?? {}).filter(([k]) => f.tipo === 'todos' || k === f.tipo);
      const soma = (campo: keyof GrupoSinistro) => grupos.reduce((a, [, g]) => a + g[campo], 0);
      const valor = f.gravidade === 'todos' ? soma('n') : soma(f.gravidade);
      // Os feridos graves por categoria incluem sinistros sem morte: no filtro "com mortes"
      // ficam de fora, para não parecerem vítimas dos sinistros fatais.
      const feridos_graves: number | null = f.gravidade === 'fatais' ? null : soma('feridos_graves');
      return t.grupos
        ? {...t, valor, mortos: soma('mortos'), feridos_graves}
        : {...t, valor: f.gravidade === 'todos' && f.tipo === 'todos' ? t.sinistros : 0};
    })
    .filter(t => t.valor > 0)
    .sort(
      (a, b) =>
        b.mortos + (b.feridos_graves ?? 0) - (a.mortos + (a.feridos_graves ?? 0)) || b.valor - a.valor,
    );
}

export const vitimasTexto = (t: {mortos: number; feridos_graves: number | null}) =>
  `${t.mortos} ${t.mortos === 1 ? 'morto' : 'mortos'}${t.feridos_graves == null ? '' : ` e ${t.feridos_graves} feridos graves`}`;

export const descricaoFiltro = (f: FiltroSinistros, n = 2) =>
  `${ROTULO_GRAVIDADE[f.gravidade][n === 1 ? 0 : 1]}${f.tipo === 'todos' ? '' : ` · ${CATEGORIAS.find(([k]) => k === f.tipo)?.[1].toLowerCase()}`}`;

// caminho relativo à página: o painel está na raiz, a página Sinistros em /sinistros/
export function useSinistros(caminho = 'sinistros.json') {
  const [s, setS] = useState<Sinistros | null>(null);
  useEffect(() => {
    fetch(caminho)
      .then(r => (r.ok ? r.json() : null))
      .then(setS)
      .catch(() => setS(null));
  }, [caminho]);
  return s;
}

// Vias da tabela da NitTrans que têm câmera pública da região (coletor.REGIAO), separando
// as que este projeto conta das que só têm câmera.
export const VIAS_COM_CAMERA: Record<string, {cameras: number; contando: boolean}> = {
  'Alameda São Boaventura': {cameras: 2, contando: false},
  'Av. Professor João Brasil': {cameras: 1, contando: false},
  'Av. Feliciano Sodré': {cameras: 2, contando: false},
  'Av. Jansen de Melo': {cameras: 2, contando: true},
};


// Período da tabela da NitTrans: 1º/1/2024 a 31/10/2026.
export const DIAS_NITTRANS = 1035;
export const frequencia = (total: number) => {
  const dias = DIAS_NITTRANS / total;
  return dias < 1.5 ? `cerca de ${Math.round(total / DIAS_NITTRANS)} por dia` : `cerca de 1 a cada ${Math.round(dias)} dias`;
};


export const SEM_FILTRO: FiltroSinistros = {gravidade: 'todos', tipo: 'todos'};
