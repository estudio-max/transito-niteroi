import {useState} from 'react';
import {Layout, LayoutContent, VStack, HStack} from '@astryxdesign/core/Layout';
import {Text, Heading} from '@astryxdesign/core/Text';
import {Badge} from '@astryxdesign/core/Badge';
import {Grid} from '@astryxdesign/core/Grid';
import {Link} from '@astryxdesign/core/Link';
import {Spinner} from '@astryxdesign/core/Spinner';
import {SegmentedControl, SegmentedControlItem} from '@astryxdesign/core/SegmentedControl';
import {Selector} from '@astryxdesign/core/Selector';
import {Topo} from './Topo';
import {ChartCard} from './ChartCard';
import Mapa from './Mapa';
import {
  CATEGORIAS,
  GRAVIDADES,
  VIAS_COM_CAMERA,
  descricaoFiltro,
  frequencia,
  trechosFiltrados,
  useSinistros,
  vitimasTexto,
} from './sinistros';
import type {FiltroSinistros, Gravidade, Sinistros} from './sinistros';

// Página "Sinistros" (21/11/2026): dados de vários anos (PRF e NitTrans) saíram do painel ao
// vivo, onde quem volta várias vezes ao dia via sempre a mesma coisa.

const numero = new Intl.NumberFormat('pt-BR');

export function FiltroDeSinistros({filtro, aoMudar}: {filtro: FiltroSinistros; aoMudar: (f: FiltroSinistros) => void}) {
  return (
    <Grid columns={{minWidth: 260, repeat: 'fit'}} gap={3}>
      <SegmentedControl
        value={filtro.gravidade}
        onChange={v => aoMudar({...filtro, gravidade: v as Gravidade})}
        label="Gravidade dos sinistros"
        layout="fill">
        {GRAVIDADES.map(([v, nome]) => (
          <SegmentedControlItem key={v} value={v} label={nome} />
        ))}
      </SegmentedControl>
      <Selector
        label="Tipo de sinistro"
        value={filtro.tipo}
        onChange={v => aoMudar({...filtro, tipo: v ?? 'todos'})}
        options={[{value: 'todos', label: 'Todos os tipos'}, ...CATEGORIAS.map(([value, label]) => ({value, label}))]}
      />
    </Grid>
  );
}


function PontosCriticos({s, filtro}: {s: Sinistros; filtro: FiltroSinistros}) {
  const graves = trechosFiltrados(s, filtro).slice(0, 5);
  const filtrado = filtro.gravidade !== 'todos' || filtro.tipo !== 'todos';
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
            {filtrado && (
              <Badge label={`Filtro do mapa: ${descricaoFiltro(filtro)}`} variant="neutral" />
            )}
            {graves.map((t, i) => (
              <VStack key={t.nome} gap={0}>
                <Text type="body" weight="semibold">{`${i + 1}. ${t.nome}`}</Text>
                <Text type="body" color="secondary">
                  {`${vitimasTexto(t)} em ${t.valor} ${descricaoFiltro(filtro, t.valor)}, em ${anosPrf} anos`}
                </Text>
              </VStack>
            ))}
            {!graves.length && (
              <Text type="body" color="secondary">
                Nenhum sinistro com esse filtro no período.
              </Text>
            )}
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


export default function PaginaSinistros() {
  const s = useSinistros('../sinistros.json');
  const [filtro, setFiltro] = useState<FiltroSinistros>({gravidade: 'todos', tipo: 'todos'});
  const areas = s
    ? trechosFiltrados(s, filtro)
        .filter(t => t.lat != null && t.lon != null)
        .map(t => ({
          nome: t.nome,
          lat: t.lat!,
          lon: t.lon!,
          sinistros: t.valor,
          texto: `${t.valor} ${descricaoFiltro(filtro, t.valor)}, com ${vitimasTexto(t)}, de ${s.prf.anos.join(' a ')} (PRF).`,
        }))
    : [];
  return (
    <Layout
      height="fill"
      content={
        <LayoutContent padding={6}>
          <VStack gap={6}>
            <Topo atual="sinistros" />
            <VStack gap={1}>
              <Heading level={1} type="display-3">
                Sinistros de trânsito
              </Heading>
              <Text type="body" color="secondary">
                Onde os acidentes se concentram em Niterói, somando vários anos de dados oficiais da
                PRF e da NitTrans. Não muda de um dia para o outro: o trânsito de agora está no{' '}
                <Link href="../">painel</Link>.
              </Text>
            </VStack>
            {s ? (
              <>
                <FiltroDeSinistros filtro={filtro} aoMudar={setFiltro} />
                <Mapa
                  id="mapa-sinistros"
                  pontos={[]}
                  areas={areas}
                  descricao={`Mapa dos trechos da BR-101 e da Ponte em Niterói com ${descricaoFiltro(filtro)}, de ${s.prf.anos.join(' a ')}.`}
                />
                <Text type="body" color="secondary">
                  {`Manchas maiores, mais ${descricaoFiltro(filtro)}. Toque numa mancha para ver os números do trecho.`}
                </Text>
                <PontosCriticos s={s} filtro={filtro} />
              </>
            ) : (
              <Spinner label="Carregando os sinistros" />
            )}
          </VStack>
        </LayoutContent>
      }
    />
  );
}
