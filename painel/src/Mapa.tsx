import {useEffect, useRef} from 'react';
import L from 'leaflet';
// O Leaflet precisa do próprio CSS para posicionar blocos do mapa e controles.
import 'leaflet/dist/leaflet.css';
import {useMovimentoReduzido} from './useVivo';

export interface PontoMapa {
  id: string;
  nome: string;
  lat: number;
  lon: number;
  cor: string; // hex: o Leaflet escreve a cor como atributo SVG, que não lê var() do tema
  texto: string;
  alerta?: boolean; // ocorrência em andamento: contorno amarelo, a cor de dentro segue a situação
  pulso?: boolean; // câmera contando ao vivo: um anel que se expande e some, como um sonar
}

// Etiqueta ao vivo de uma câmera contada: veículos por hora agora e a tendência.
export interface EtiquetaMapa {
  valor: number;
  tendencia?: 'subindo' | 'estavel' | 'descendo' | null;
}

// Um instante do replay das últimas 24 horas: veículos por hora de cada câmera naquele
// balde de 5 minutos e o maior valor do dia de cada uma (para o tamanho e a cor do ponto).
export interface MomentoMapa {
  valores: Record<string, number | null>;
  maximos: Record<string, number>;
}

const AMARELO_ALERTA = '#f5b400';
const SETA = {subindo: '▲', descendo: '▼', estavel: '▬'} as const;
const numero = new Intl.NumberFormat('pt-BR');

const escapar = (s: string) =>
  s.replace(/[&<>"']/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'})[c]!);

// Escala do replay: um tom só (ciano), do apagado ao aceso, como manda o guia de
// visualização para intensidade.
function corReplay(k: number) {
  const de = [20, 88, 74];
  const ate = [95, 240, 200];
  const c = de.map((v, i) => Math.round(v + (ate[i] - v) * Math.max(0, Math.min(1, k))));
  return `rgb(${c.join(',')})`;
}

function htmlEtiqueta(valor: string, seta: string, lado: 'direita' | 'esquerda') {
  const caixa =
    'display:inline-flex;align-items:baseline;gap:4px;white-space:nowrap;padding:3px 8px;' +
    'border-radius:3px;background:rgba(8,24,20,0.9);border:1px solid rgba(46,230,182,0.55);' +
    'box-shadow:0 0 12px rgba(46,230,182,0.25);color:#e6fff6;' +
    `transform:translate(${lado === 'direita' ? '16px' : 'calc(-100% - 16px)'},-50%);`;
  return (
    `<span style="${caixa}"><b data-valor style="font:600 14px 'Chakra Petch',sans-serif">${valor}</b>` +
    `<span style="font:12px 'Atkinson Hyperlegible Next',sans-serif;color:#9fc4b8">veíc/h</span>` +
    `<span style="font-size:11px;color:#2ee6b6">${seta}</span></span>`
  );
}

// Número da etiqueta indo do valor anterior ao novo (~0,9 s), no próprio elemento.
function animarNumero(el: HTMLElement, de: number, para: number, reduzir: boolean) {
  if (reduzir || de === para) {
    el.textContent = numero.format(Math.round(para));
    return;
  }
  const inicio = performance.now();
  const passo = (t: number) => {
    const k = Math.min(1, (t - inicio) / 900);
    el.textContent = numero.format(Math.round(de + (para - de) * (1 - Math.pow(1 - k, 3))));
    if (k < 1) {
      requestAnimationFrame(passo);
    }
  };
  requestAnimationFrame(passo);
}

// Mapa da região com um ponto por câmera. O mesmo conteúdo existe em texto na página
// (situação e histórico), então o mapa é um apoio visual, não a única fonte.
// Área com sinistros (PRF): círculo translúcido, maior onde há mais sinistros.
export interface AreaMapa {
  nome: string;
  lat: number;
  lon: number;
  sinistros: number;
  texto: string;
}

// foco: câmera a centralizar e abrir (vem de "ver no mapa" numa ocorrência); `vez` muda a
// cada clique, para repetir o foco na mesma câmera.
export interface FocoMapa {
  id: string;
  vez: number;
}

export default function Mapa({
  pontos,
  areas = [],
  descricao,
  foco = null,
  id,
  sinistrosLigados = true,
  etiquetas = {},
  momento = null,
}: {
  pontos: PontoMapa[];
  areas?: AreaMapa[];
  descricao: string;
  foco?: FocoMapa | null;
  id?: string; // âncora para a página rolar até o mapa
  sinistrosLigados?: boolean; // camada de sinistros começa ligada? (no painel ao vivo, não)
  etiquetas?: Record<string, EtiquetaMapa>;
  momento?: MomentoMapa | null; // replay: substitui cor, tamanho e etiqueta ao vivo
}) {
  const ref = useRef<HTMLDivElement>(null);
  const reduzirMovimento = useMovimentoReduzido();
  const mapaRef = useRef<L.Map | null>(null);
  const marcasRef = useRef<Record<string, L.CircleMarker>>({});
  const camerasRef = useRef<L.LayerGroup | null>(null);
  const etiquetasRef = useRef<Record<string, {marca: L.Marker; valor: number}>>({});
  // O mapa só é recriado quando muda a estrutura (quais pontos e onde, as áreas). Cor, texto,
  // alerta e números mudam a cada leitura e são atualizados no lugar: antes o mapa inteiro
  // era refeito a cada minuto e perdia o zoom de quem estava olhando.
  const estrutura = JSON.stringify([
    pontos.map(p => [p.id, p.lat, p.lon, p.pulso]),
    areas,
    sinistrosLigados,
  ]);
  useEffect(() => {
    if (!ref.current || (!pontos.length && !areas.length)) {
      return;
    }
    const mapa = L.map(ref.current, {
      scrollWheelZoom: false, // rolar a página não deve virar zoom no mapa
      dragging: !L.Browser.mobile, // no celular, um dedo rola a página; zoom pelos botões
    });
    // Imagens do OpenStreetMap (gratuitas com atribuição). O CARTO passou a exigir chave.
    L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution:
        '&copy; <a href="https://www.openstreetmap.org/copyright">colaboradores do OpenStreetMap</a>',
      maxZoom: 19,
    }).addTo(mapa);
    // Visual escuro do painel: inverte só as imagens do mapa (pontos e manchas, em outra
    // camada, mantêm as cores reais). Sem chave de API, ao contrário de mapas escuros prontos.
    mapa.getPane('tilePane')!.style.filter =
      'invert(1) hue-rotate(180deg) brightness(0.78) contrast(0.92) saturate(0.55)';
    // Sinistros primeiro: ficam por baixo das câmeras. Cada grupo é uma camada que a pessoa
    // liga e desliga pelo controle nativo do Leaflet, no canto do mapa.
    const todas: L.CircleMarker[] = [];
    const sinistros = L.layerGroup();
    if (sinistrosLigados) {
      sinistros.addTo(mapa);
    }
    for (const a of areas) {
      const m = L.circleMarker([a.lat, a.lon], {
        radius: 6 + 2.2 * Math.sqrt(a.sinistros),
        stroke: false,
        fillColor: '#b42318',
        fillOpacity: 0.35,
      })
        .bindTooltip(a.nome, {direction: 'top'})
        .bindPopup(`<strong>${escapar(a.nome)}</strong><br>${escapar(a.texto)}`)
        .addTo(sinistros);
      // enquadramento inicial só com o que aparece (camada desligada não puxa o zoom)
      if (sinistrosLigados || !pontos.length) {
        todas.push(m);
      }
    }
    const cameras = L.layerGroup().addTo(mapa);
    marcasRef.current = {};
    etiquetasRef.current = {};
    for (const p of pontos) {
      const m = L.circleMarker([p.lat, p.lon], {radius: 11, color: '#ffffff', weight: 3, fillOpacity: 1})
        .bindTooltip(p.nome, {direction: 'top', offset: [0, -10]})
        .bindPopup('')
        .addTo(cameras);
      marcasRef.current[p.id] = m;
      todas.push(m);
      if (p.pulso && !reduzirMovimento) {
        // SVG com animação própria (nada de CSS): o anel cresce e desaparece a cada 2 s.
        L.marker([p.lat, p.lon], {
          interactive: false,
          keyboard: false,
          icon: L.divIcon({
            className: '',
            iconSize: [56, 56],
            html: `<svg width="56" height="56" viewBox="0 0 56 56" aria-hidden="true"><circle cx="28" cy="28" r="10" fill="none" stroke="#2ee6b6" stroke-width="2"><animate attributeName="r" values="10;26" dur="2s" repeatCount="indefinite"/><animate attributeName="opacity" values="0.9;0" dur="2s" repeatCount="indefinite"/></circle></svg>`,
          }),
        }).addTo(cameras);
      }
    }
    const camadas: Record<string, L.Layer> = {};
    if (pontos.length) {
      camadas['Câmeras'] = cameras;
    }
    if (areas.length) {
      camadas['Sinistros (PRF)'] = sinistros;
    }
    if (Object.keys(camadas).length > 1) {
      // aberto no computador; no celular vira um ícone que abre ao tocar, para não cobrir o mapa
      L.control.layers(undefined, camadas, {collapsed: mapa.getSize().x < 500}).addTo(mapa);
    }
    // Controles do Leaflet no mesmo vidro escuro dos cartões (o CSS dele é claro).
    ref.current.querySelectorAll<HTMLElement>('.leaflet-bar a, .leaflet-control-layers').forEach(el => {
      Object.assign(el.style, {
        background: 'rgba(8, 24, 20, 0.88)',
        color: '#e6fff6',
        borderColor: 'rgba(46, 230, 182, 0.35)',
      });
    });
    // Com etiquetas (que saem à direita dos pontos), mais margem à direita: senão a da câmera
    // mais a leste fica cortada pela borda, sobretudo no celular.
    mapa.fitBounds(
      L.featureGroup(todas).getBounds(),
      Object.keys(etiquetas).length
        ? {paddingTopLeft: [36, 36], paddingBottomRight: [130, 36]}
        : {padding: [36, 36]},
    );
    mapaRef.current = mapa;
    camerasRef.current = cameras;
    return () => {
      mapa.remove();
      mapaRef.current = null;
      camerasRef.current = null;
      etiquetasRef.current = {};
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [estrutura, reduzirMovimento]);

  // A cada leitura (ou a cada quadro do replay): cor, tamanho, contorno, texto e etiqueta.
  useEffect(() => {
    const cameras = camerasRef.current;
    if (!cameras) {
      return;
    }
    for (const p of pontos) {
      const m = marcasRef.current[p.id];
      if (!m) {
        continue;
      }
      const noReplay = momento && p.id in momento.valores;
      if (noReplay) {
        const v = momento.valores[p.id];
        const k = v == null ? 0 : v / Math.max(momento.maximos[p.id] ?? 1, 1);
        m.setStyle({fillColor: v == null ? '#3a4a46' : corReplay(k), color: '#ffffff', weight: 2});
        m.setRadius(v == null ? 5 : 6 + 16 * Math.sqrt(k));
      } else {
        m.setStyle({
          fillColor: p.cor,
          color: p.alerta ? AMARELO_ALERTA : '#ffffff',
          weight: p.alerta ? 6 : 3,
        });
        m.setRadius(p.alerta ? 12 : 11);
      }
      m.setPopupContent(
        `<strong>${escapar(p.nome)}</strong><br>${escapar(p.texto)}<br><small>Posição aproximada</small>`,
      );
      // etiqueta: no replay, o valor daquele instante; ao vivo, o dos últimos 15 min
      const e = etiquetas[p.id];
      const valor = noReplay ? momento.valores[p.id] : (e?.valor ?? null);
      const atual = etiquetasRef.current[p.id];
      if (valor == null) {
        if (atual) {
          atual.marca.remove();
          delete etiquetasRef.current[p.id];
        }
        continue;
      }
      // Câmera com outra contada logo a leste (menos de ~700 m): etiqueta do lado esquerdo.
      const vizinhaLeste = pontos.some(
        q => q.id !== p.id && q.id in etiquetas && q.lon > p.lon && q.lon - p.lon < 0.007 && Math.abs(q.lat - p.lat) < 0.003,
      );
      const seta = noReplay ? '' : e?.tendencia ? SETA[e.tendencia] : '';
      if (!atual) {
        const marca = L.marker([p.lat, p.lon], {
          interactive: false,
          keyboard: false,
          icon: L.divIcon({
            className: '',
            iconSize: [0, 0],
            html: htmlEtiqueta(numero.format(Math.round(valor)), seta, vizinhaLeste ? 'esquerda' : 'direita'),
          }),
        }).addTo(cameras);
        etiquetasRef.current[p.id] = {marca, valor};
        continue;
      }
      const el = atual.marca.getElement();
      const num = el?.querySelector<HTMLElement>('[data-valor]');
      const setaEl = num?.parentElement?.lastElementChild as HTMLElement | null | undefined;
      if (setaEl) {
        setaEl.textContent = seta;
      }
      if (num) {
        animarNumero(num, atual.valor, valor, reduzirMovimento || !!noReplay);
      }
      atual.valor = valor;
    }
  }, [pontos, etiquetas, momento, estrutura, reduzirMovimento]);

  useEffect(() => {
    const m = foco && marcasRef.current[foco.id];
    const mapa = mapaRef.current;
    if (m && mapa) {
      // pediu para ver a câmera: religa a camada se a pessoa tinha desligado
      if (camerasRef.current && !mapa.hasLayer(camerasRef.current)) {
        camerasRef.current.addTo(mapa);
      }
      mapa.setView(m.getLatLng(), 16);
      m.openPopup();
    }
  }, [foco, estrutura]);
  // O Leaflet precisa de um elemento DOM próprio para desenhar; não há componente
  // equivalente no Astryx.
  return (
    <div
      ref={ref}
      id={id}
      role="region"
      aria-label={descricao}
      style={{height: 380, width: '100%', borderRadius: 12, overflow: 'hidden', position: 'relative', zIndex: 0}}
    />
  );
}
