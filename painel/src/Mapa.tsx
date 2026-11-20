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
}

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

export default function Mapa({
  pontos,
  areas = [],
  descricao,
}: {
  pontos: PontoMapa[];
  areas?: AreaMapa[];
  descricao: string;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const chave = JSON.stringify([pontos, areas]); // recria o mapa só se os dados mudarem
  useEffect(() => {
    if (!ref.current || !pontos.length) {
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
    // Sinistros primeiro: ficam por baixo das câmeras.
    for (const a of areas) {
      L.circleMarker([a.lat, a.lon], {
        radius: 6 + 2.2 * Math.sqrt(a.sinistros),
        stroke: false,
        fillColor: '#b42318',
        fillOpacity: 0.35,
      })
        .bindTooltip(a.nome, {direction: 'top'})
        .bindPopup(`<strong>${escapar(a.nome)}</strong><br>${escapar(a.texto)}`)
        .addTo(mapa);
    }
    const marcas = pontos.map(p =>
      L.circleMarker([p.lat, p.lon], {
        radius: 11,
        color: '#ffffff',
        weight: 3,
        fillColor: p.cor,
        fillOpacity: 1,
      })
        .bindTooltip(p.nome, {direction: 'top', offset: [0, -10]})
        .bindPopup(
          `<strong>${escapar(p.nome)}</strong><br>${escapar(p.texto)}<br><small>Posição aproximada</small>`,
        )
        .addTo(mapa),
    );
    mapa.fitBounds(L.featureGroup(marcas).getBounds(), {padding: [36, 36]});
    return () => {
      mapa.remove();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [chave]);
  // O Leaflet precisa de um elemento DOM próprio para desenhar; não há componente
  // equivalente no Astryx.
  return (
    <div
      ref={ref}
      role="region"
      aria-label={descricao}
      style={{height: 380, width: '100%', borderRadius: 12, overflow: 'hidden', position: 'relative', zIndex: 0}}
    />
  );
}
