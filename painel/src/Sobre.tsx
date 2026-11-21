import {useCallback, useState, type CSSProperties, type ReactNode} from 'react';
import {Heading, Text} from '@astryxdesign/core/Text';
import {Card} from '@astryxdesign/core/Card';
import {Banner} from '@astryxdesign/core/Banner';
import {Link} from '@astryxdesign/core/Link';
import {List, ListItem} from '@astryxdesign/core/List';
import {Selector} from '@astryxdesign/core/Selector';
import {VStack} from '@astryxdesign/core/Stack';
import {Layout, LayoutContent, LayoutPanel} from '@astryxdesign/core/Layout';
import {Divider} from '@astryxdesign/core/Divider';
import {CodeBlock} from '@astryxdesign/core/CodeBlock';
import {Outline, type OutlineItem} from '@astryxdesign/core/Outline';
import {useMediaQuery} from '@astryxdesign/core/hooks';
import {
  LineChart,
  Line,
  ReferenceArea,
  XAxis,
  YAxis,
  ResponsiveContainer,
} from 'recharts';
import {Topo} from './Topo';
import {FAQ} from './faq';

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

const OUTLINE_ITEMS: OutlineItem[] = [
  {id: 'o-que-e', label: 'O que é', level: 2},
  {id: 'como-funciona', label: 'Como funciona', level: 2},
  {id: 'guia', label: 'Guia dos gráficos', level: 2},
  {id: 'metodo', label: 'Método e validação', level: 2},
  {id: 'limites', label: 'Limites e privacidade', level: 2},
  {id: 'incorporar', label: 'Usar em outro site', level: 2},
  {id: 'perguntas', label: 'Perguntas frequentes', level: 2},
];

const IFRAME = `<iframe
  src="https://transito.fanara.com.br/texto.html"
  title="Trânsito na saída da Ponte Rio–Niterói"
  width="100%" height="420" loading="lazy"></iframe>`;

const OUTLINE_OPTIONS = OUTLINE_ITEMS.map(item => ({
  value: item.id,
  label: item.label,
}));

const outlinePanel: CSSProperties = {
  position: 'sticky',
  top: 24,
  alignSelf: 'start',
  paddingBlockStart: 120,
};

const TINTA = 'var(--color-text-secondary, #4E606F)';
const EIXO = {fontSize: 'var(--font-size-sm, 12px)', fill: TINTA};

// Forma clássica do diagrama fluxo × ocupação. Esquema, não medição: sem números nos eixos.
const ESQUEMA = [
  {o: 0, f: 0},
  {o: 3, f: 10},
  {o: 10, f: 0},
];

function EsquemaFundamental() {
  return (
    <VStack gap={2}>
      <ResponsiveContainer width="100%" height={200}>
        <LineChart
          data={ESQUEMA}
          margin={{top: 8, right: 16, bottom: 24, left: 8}}
          role="img"
          aria-label="Esquema: o fluxo sobe com a ocupação até um máximo e depois cai. À esquerda do máximo, trânsito livre; à direita, congestionado.">
          <ReferenceArea
            x1={0}
            x2={3}
            fill="var(--color-data-categorical-green, #0B991F)"
            fillOpacity={0.08}
            label={{value: 'trânsito livre', position: 'insideTop', ...EIXO}}
          />
          <ReferenceArea
            x1={3}
            x2={10}
            fill="var(--color-data-categorical-red, #F5394F)"
            fillOpacity={0.08}
            label={{value: 'congestionado', position: 'insideTop', ...EIXO}}
          />
          <XAxis
            dataKey="o"
            type="number"
            domain={[0, 10]}
            tick={false}
            axisLine={{stroke: TINTA}}
            label={{value: 'ocupação →', position: 'insideBottom', offset: -8, ...EIXO}}
          />
          <YAxis
            type="number"
            domain={[0, 12]}
            tick={false}
            axisLine={{stroke: TINTA}}
            width={24}
            label={{value: 'fluxo →', angle: -90, position: 'insideLeft', ...EIXO}}
          />
          <Line
            type="linear"
            dataKey="f"
            stroke="var(--color-data-categorical-blue, #0171E3)"
            strokeWidth={2}
            dot={false}
            isAnimationActive={false}
          />
        </LineChart>
      </ResponsiveContainer>
      <Text type="supporting" color="secondary">
        Esquema ilustrativo, não são dados medidos.
      </Text>
    </VStack>
  );
}

function Grafico({
  titulo,
  mostra,
  ler,
  cuidado,
  children,
}: {
  titulo: string;
  mostra: string;
  ler: string;
  cuidado: string;
  children?: ReactNode;
}) {
  return (
    <Card>
      <VStack gap={3}>
        <Heading level={3}>{titulo}</Heading>
        <Text type="body">
          <Text type="body" weight="semibold">
            O que mostra.{' '}
          </Text>
          {mostra}
        </Text>
        <Text type="body">
          <Text type="body" weight="semibold">
            Como ler.{' '}
          </Text>
          {ler}
        </Text>
        {children}
        <Text type="body" color="secondary">
          <Text type="body" weight="semibold" color="secondary">
            Cuidado.{' '}
          </Text>
          {cuidado}
        </Text>
      </VStack>
    </Card>
  );
}

export default function Sobre() {
  const [activeId, setActiveId] = useState<string | undefined>(
    OUTLINE_ITEMS[0]?.id,
  );
  const isMobile = useMediaQuery('(max-width: 768px)');

  const scrollToId = useCallback((id: string) => {
    setActiveId(id);
    const target = document.getElementById(id);
    if (target != null) {
      target.scrollIntoView({behavior: 'smooth', block: 'start'});
      window.history.pushState(null, '', `#${id}`);
    }
  }, []);

  return (
    <Layout
      height="auto"
      contentWidth={960}
      end={
        isMobile ? undefined : (
          <LayoutPanel
            isScrollable={false}
            label="Nesta página"
            role="complementary"
            style={outlinePanel}>
            <Outline items={OUTLINE_ITEMS} onActiveIdChange={setActiveId} />
          </LayoutPanel>
        )
      }
      content={
        <LayoutContent isScrollable={false} padding={8}>
          <VStack gap={8}>
            <Topo atual="sobre" />

            <VStack gap={2}>
              <Heading level={1} type="display-2">
                Sobre o Fluxo Niterói
              </Heading>
              <Text type="supporting" color="secondary">
                Atualizado em 12 de novembro de 2026
              </Text>
              {isMobile && (
                <Selector
                  label="Nesta página"
                  isLabelHidden
                  options={OUTLINE_OPTIONS}
                  value={activeId}
                  onChange={scrollToId}
                  width="100%"
                />
              )}
            </VStack>

            <Banner
              status="warning"
              title="Aviso: os números do painel ainda são preliminares"
              description="A contagem automática ainda não foi conferida contra contagem manual. Use o painel para acompanhar o estudo, não como resultado."
            />

            <VStack gap={4}>
              <Heading id="o-que-e" level={2}>
                O que é
              </Heading>
              <Text type="body">
                O Fluxo Niterói é um estudo cívico que conta, minuto a minuto, os
                veículos que passam pela Av. Jansen de Melo, na saída da Ponte
                Rio–Niterói sentido Icaraí. A contagem é feita por visão
                computacional sobre os vídeos que as câmeras públicas da NitTrans
                já publicam na internet.
              </Text>
              <Text type="body">
                O trecho tem fila recorrente na descida da ponte enquanto as vias
                vizinhas andam livres, um sinal de gargalo pontual. Os aplicativos
                de mapa mostram a velocidade, mas não quantos veículos passam. Sem
                essa contagem não dá para saber onde a capacidade se perde nem
                testar o que a recuperaria.
              </Text>
              <Text type="body">
                O objetivo é localizar o gargalo com dados, testar correções em
                simulação e levar à prefeitura propostas com o ganho estimado.
              </Text>
            </VStack>

            <Divider />

            <VStack gap={4}>
              <Heading id="como-funciona" level={2}>
                Como funciona
              </Heading>
              <List density="compact" listStyle="decimal">
                <ListItem label={<Text type="body">A cada minuto, um programa baixa o último clipe de cerca de 60 segundos de cada câmera, no endereço público da NitTrans.</Text>} />
                <ListItem label={<Text type="body">Um modelo de visão computacional (YOLO) encontra carros, motos, ônibus e caminhões em cada quadro do vídeo.</Text>} />
                <ListItem label={<Text type="body">Um rastreador liga as detecções do mesmo veículo ao longo do clipe, formando a trajetória dele.</Text>} />
                <ListItem label={<Text type="body">Cada câmera tem uma linha fixa que corta as faixas. O veículo é contado uma vez quando a trajetória cruza essa linha, com o sentido registrado.</Text>} />
                <ListItem label={<Text type="body">O vídeo é apagado. Só os números vão para o banco, que alimenta este site a cada 5 minutos.</Text>} />
              </List>
              <Text type="body" color="secondary">
                Hoje são quatro câmeras: duas na Jansen de Melo (sentido Ponte e o
                cruzamento com a Rua Marechal Deodoro), que enxergam os dois sentidos,
                o que vai para Icaraí e o que vai para a ponte, e duas na Alameda São
                Boaventura (acesso à Ponte e cruzamento com a João Brasil), que contam
                pistas de mão única vindas do Fonseca. Todo o processamento roda em um notebook comum, sem custo de
                serviço.
              </Text>
            </VStack>

            <Divider />

            <VStack gap={4}>
              <Heading id="guia" level={2}>
                Guia dos gráficos
              </Heading>
              <Text type="body">
                O <Link href="/">painel</Link> mostra as últimas 24 horas de
                coleta. Em todos os gráficos, cada câmera tem sempre a mesma cor:
                azul para a Jansen de Melo sentido Ponte e marrom para o cruzamento
                com a Marechal Deodoro. Passe o mouse (ou toque) em qualquer ponto
                para ver o valor exato.
              </Text>

              <Grafico
                titulo="Indicador de coleta"
                mostra="Se o sistema está coletando agora. A bolinha verde pulsando significa que o último clipe tem menos de 10 minutos; a cinza, que a coleta está pausada."
                ler="Ao lado aparece a hora do último clipe analisado. Com a coleta pausada, todos os números da página param naquele horário."
                cuidado="A coleta roda em um notebook pessoal. Pausas são normais e aparecem como buracos nos gráficos."
              />

              <Grafico
                titulo="Cobertura da coleta"
                mostra="Uma grade com os últimos 14 dias (linhas) e as 24 horas do dia (colunas). Quanto mais escuro o quadrado, mais minutos de vídeo foram analisados naquela hora."
                ler="Até 19/11/2026 a coleta rodou só em janelas de pico; desde então roda o dia todo, todos os dias, para formar a história que permite comparar e prever. Qualquer conclusão vale só para as horas preenchidas. Quadrados claros indicam hora com pouca amostra."
                cuidado="Uma hora com poucos minutos analisados (por exemplo, quando a coleta começou no meio dela) pesa pouco. Comparações entre dias só fazem sentido entre horas com coleta nos dois dias."
              />

              <Grafico
                titulo="Cartões de destaque"
                mostra="Um cartão por câmera e por sentido (por exemplo, para Icaraí e para a ponte), com o fluxo médio da última hora coletada em veículos por hora. A curva sob o número é o fluxo das últimas 24 horas. Dois cartões somam os veículos e os clipes do período."
                ler="O cartão “para Icaraí” é o que mede a descida, que é o foco do estudo. A curva mostra se o momento atual está acima ou abaixo do resto do dia."
                cuidado="Uma hora com poucos clipes (por exemplo, logo após a coleta recomeçar) gera uma média instável. Um sentido só ganha cartão quando a câmera contou pelo menos 10 veículos nele, para que contagens isoladas não pareçam fluxo. A soma de veículos conta duas vezes quem passa pelas duas câmeras."
              />

              <Grafico
                titulo="Fluxo por sentido"
                mostra="Um gráfico para cada sentido real: para Icaraí, para a ponte, vindo do Fonseca e para o Centro, Santana e BR. Cada um mostra quantos veículos por hora cruzam a linha de contagem de cada câmera, em médias de 5 minutos."
                ler="É a medida de capacidade da via. Uma queda brusca no horário de pico, com a ocupação subindo ao mesmo tempo, é o sinal de que a fila chegou à câmera. Os trechos sem linha são períodos sem coleta. Os sentidos ficam separados porque somar fluxos opostos esconderia o que acontece na descida."
                cuidado="O sentido de cada câmera foi confirmado pelo autor com uma foto das trajetórias e o Street View. Câmeras de vias diferentes só dividem um gráfico quando vão para o mesmo lugar. O fluxo de 5 minutos é extrapolado para uma hora: variações rápidas são normais perto de semáforos, que soltam os carros em pelotões."
              />

              <Grafico
                titulo="Ocupação"
                mostra="A média de veículos visíveis na imagem da câmera em cada quadro do vídeo."
                ler="Ocupação alta significa muitos veículos na tela ao mesmo tempo, seja porque o trânsito está intenso, seja porque está parado. É o fluxo que separa os dois casos."
                cuidado="Árvores, ônibus e a perspectiva da câmera escondem veículos. Compare a ocupação de uma câmera com ela mesma ao longo do dia, não entre câmeras."
              />

              <Grafico
                titulo="Fluxo × ocupação"
                mostra="Cada ponto é um clipe de um minuto, posicionado pela ocupação (eixo horizontal) e pelo fluxo (eixo vertical). Os pontos da Jansen sentido Ponte são círculos; os do cruzamento, triângulos."
                ler="É a versão medida do diagrama fundamental do tráfego. Com trânsito livre, mais veículos na via significam mais veículos passando, e os pontos sobem para a direita. Depois do ponto de capacidade, mais veículos na via significam fila, e o fluxo cai. Pontos na parte de baixo à direita são minutos de congestionamento."
                cuidado="O desenho só aparece com pontos dos dois regimes. Uma noite de trânsito livre preenche apenas o lado esquerdo; o lado congestionado depende de coletar nos horários de pico.">
                <EsquemaFundamental />
              </Grafico>

              <Grafico
                titulo="Tipos de veículo"
                mostra="Quantos carros, motos, ônibus e caminhões cada câmera contou nas últimas 24 horas, com a participação de cada tipo no total."
                ler="Ônibus e caminhões ocupam mais espaço e arrancam mais devagar. Uma participação alta deles ajuda a explicar a fila mesmo com poucos veículos."
                cuidado="Até agora o modelo quase não identificou motos, o que é improvável na prática. A conferência manual vai dizer se ele está falhando nessa classe."
              />

              <Grafico
                titulo="Últimos clipes analisados"
                mostra="Os 20 clipes mais recentes, com horário, câmera, veículos que vão para Icaraí e para a ponte, fluxo equivalente por hora (dos dois sentidos juntos) e ocupação."
                ler="É a tabela com os números exatos que alimentam os gráficos, útil para conferir um ponto específico."
                cuidado="A coluna de fluxo por hora soma os dois sentidos do clipe; para o fluxo por sentido, use os gráficos."
              />
            </VStack>

            <Divider />

            <VStack gap={4}>
              <Heading id="metodo" level={2}>
                Método e validação
              </Heading>
              <Text type="body">
                Nenhuma conclusão sai de dado não validado. Antes de qualquer
                análise, a contagem automática é comparada com contagem humana às
                cegas: uma pessoa assiste a uma amostra de clipes vendo só a linha
                de contagem, sem ver o resultado do programa, e anota quantos
                veículos cruzaram. Só depois as duas contagens são comparadas.
              </Text>
              <List density="compact" listStyle="disc">
                <ListItem label={<Text type="body">A amostra cobre dia, noite, pico e chuva, com cerca de 20 clipes por câmera.</Text>} />
                <ListItem label={<Text type="body">O erro é medido por câmera, condição e sentido, com sinal (mostra se o programa conta a mais ou a menos) e por clipe (mostra a dispersão).</Text>} />
                <ListItem label={<Text type="body">O limite proposto é de 10% de erro. Câmera ou condição acima disso fica fora da análise até a causa ser corrigida.</Text>} />
                <ListItem label={<Text type="body">Cada número no banco guarda o modelo, a versão e a linha de contagem usados, para que qualquer resultado possa ser reproduzido.</Text>} />
              </List>
              <Text type="body">
                Com os dados validados, as etapas seguintes são reproduzir o
                trecho em um simulador de tráfego de código aberto (SUMO), ajustado
                até que as filas simuladas coincidam com as medidas, e testar nele
                intervenções como novos tempos de semáforo ou mudanças de
                conversão. Só as que mostrarem ganho no modelo conferido viram
                proposta.
              </Text>
            </VStack>

            <Divider />

            <VStack gap={4}>
              <Heading id="limites" level={2}>
                Limites e privacidade
              </Heading>
              <List density="compact" listStyle="disc">
                <ListItem label={<Text type="body">Só números são guardados. O vídeo é apagado logo após a contagem; não há leitura de placas nem identificação de pessoas.</Text>} />
                <ListItem label={<Text type="body">A coleta acessa cada câmera no máximo uma vez por minuto e não insiste quando o servidor público falha.</Text>} />
                <ListItem label={<Text type="body">A câmera vê só uma seção da via. Sabemos quantos veículos passam, não de onde vêm nem para onde vão.</Text>} />
                <ListItem label={<Text type="body">Ajustes de semáforo e de geometria reduzem atraso em gargalos pontuais, mas não resolvem excesso de veículos.</Text>} />
              </List>
            </VStack>

            <Divider />

            <VStack gap={4}>
              <Heading id="incorporar" level={2}>
                Usar em outro site
              </Heading>
              <Text type="body">
                A versão só texto cabe numa moldura (iframe) de qualquer site: não usa
                JavaScript, atualiza a cada coleta e o link “Painel completo” abre o painel
                na janela inteira. Cole o código onde quiser mostrar o trânsito:
              </Text>
              <CodeBlock code={IFRAME} language="html" />
              <Text type="body" color="secondary">
                É uma indicação feita por inteligência artificial, ainda sem conferência por
                amostragem: mantenha o aviso e o link da moldura. Para dados em planilha, há o{' '}
                <Link href="dados-por-hora.csv">CSV por hora</Link> e o{' '}
                <Link href="feed.xml">feed RSS</Link>.
              </Text>
            </VStack>

            <Divider />

            <VStack gap={6}>
              <Heading id="perguntas" level={2}>
                Perguntas frequentes
              </Heading>
              {FAQ.map(q => (
                <VStack key={q.pergunta} gap={2}>
                  <Heading level={3}>{q.pergunta}</Heading>
                  <Text type="body">{q.resposta}</Text>
                </VStack>
              ))}
            </VStack>

            <Divider />

            <Text type="supporting" color="secondary">
              Estudo cívico independente do Labs.fanara.com.br, sem vínculo com a
              Prefeitura de Niterói nem com a NitTrans. As imagens de origem são
              as publicadas pela NitTrans em seu serviço de videomonitoramento.
              Código aberto sob a licença AGPL-3.0:{' '}
              <Link href="https://github.com/estudio-max/transito-niteroi">repositório no GitHub</Link>.
            </Text>
          </VStack>
        </LayoutContent>
      }
    />
  );
}
