import {useEffect, useRef} from 'react';
import L from 'leaflet';
// O Leaflet precisa do próprio CSS para posicionar blocos do mapa e controles.
import 'leaflet/dist/leaflet.css';

export interface PontoMapa {
  id: string;
  nome: string;
  lat: number;
  lon: number;
  cor: string; // hex: o Leaflet escreve a cor como atributo SVG, que não lê var() do tema
  texto: string;
  alerta?: boolean; // ocorrência em andamento: contorno amarelo, a cor de dentro segue a situação
}

const AMARELO_ALERTA = '#f5b400';

const escapar = (s: string) =>
  s.replace(/[&<>"']/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'})[c]!);

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
}: {
  pontos: PontoMapa[];
  areas?: AreaMapa[];
  descricao: string;
  foco?: FocoMapa | null;
  id?: string; // âncora para a página rolar até o mapa
}) {
  const ref = useRef<HTMLDivElement>(null);
  const mapaRef = useRef<L.Map | null>(null);
  const marcasRef = useRef<Record<string, L.CircleMarker>>({});
  const camerasRef = useRef<L.LayerGroup | null>(null);
  const chave = JSON.stringify([pontos, areas]); // recria o mapa só se os dados mudarem
  useEffect(() => {
    if (!ref.current || (!pontos.length && !areas.length)) {
      return;
    }
    const mapa = L.map(ref.current, {
      scrollWheelZoom: false, // rolar a página não deve virar zoom no mapa
      dragging: !L.Browser.mobile, // no celular, um dedo rola a página; zoom pelos botões
    });
    // Imagens do OpenStreetMap (gratuitas com atribuição). O CARTO passou a exigir chave.
    // Coloridas de propósito: Ponte, BR-101, Santana e Fonseca ajudam a se localizar.
    L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution:
        '&copy; <a href="https://www.openstreetmap.org/copyright">colaboradores do OpenStreetMap</a>',
      maxZoom: 19,
    }).addTo(mapa);
    // Sinistros primeiro: ficam por baixo das câmeras. Cada grupo é uma camada que a pessoa
    // liga e desliga pelo controle nativo do Leaflet, no canto do mapa.
    const todas: L.CircleMarker[] = [];
    const sinistros = L.layerGroup().addTo(mapa);
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
      todas.push(m);
    }
    const cameras = L.layerGroup().addTo(mapa);
    marcasRef.current = {};
    for (const p of pontos) {
      const m = L.circleMarker([p.lat, p.lon], {
        radius: p.alerta ? 12 : 11,
        color: p.alerta ? AMARELO_ALERTA : '#ffffff',
        weight: p.alerta ? 6 : 3,
        fillColor: p.cor,
        fillOpacity: 1,
      })
        .bindTooltip(p.nome, {direction: 'top', offset: [0, -10]})
        .bindPopup(
          `<strong>${escapar(p.nome)}</strong><br>${escapar(p.texto)}<br><small>Posição aproximada</small>`,
        )
        .addTo(cameras);
      marcasRef.current[p.id] = m;
      todas.push(m);
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
    mapa.fitBounds(L.featureGroup(todas).getBounds(), {padding: [36, 36]});
    mapaRef.current = mapa;
    camerasRef.current = cameras;
    return () => {
      mapa.remove();
      mapaRef.current = null;
      camerasRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [chave]);
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
  }, [foco, chave]);
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
