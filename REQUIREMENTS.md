# REQUIREMENTS — Fluxo Niterói

## Objetivo

Medir o fluxo real de veículos na Av. Jansen de Melo (saída da Ponte Rio–Niterói, sentido Icaraí) a partir das câmeras públicas da NitTrans, para diagnosticar o gargalo e, nas fases seguintes, testar intervenções em simulação.

## Público

- Autor do projeto: estudo cívico, com possibilidade de virar trabalho acadêmico.
- NitTrans / Prefeitura de Niterói, como destinatários do relatório.
- Futuro: produto, se o método se provar.

## Requisitos funcionais

| # | Requisito | Prioridade | Status |
|---|---|---|---|
| RF1 | Baixar o último clipe (`last_video.mp4`) de cada câmera configurada | alta | implementado |
| RF2 | Contar veículos que cruzam uma linha por câmera, por classe (carro, moto, ônibus, caminhão) e sentido | alta | implementado |
| RF3 | Medir ocupação: média de veículos visíveis por quadro (indicador de fila/densidade) | alta | implementado |
| RF4 | Gravar os números em SQLite, uma linha por clipe, sem duplicar clipe já processado | alta | implementado |
| RF5 | Rodar em laço com intervalo configurável e sobreviver a falhas do servidor (503, timeout) | alta | implementado |
| RF11 | Painel público em https://transito.fanara.com.br/ com fluxo, ocupação, tipos de veículo e últimos clipes, sempre com aviso de dado não validado enquanto a fase 2 não fechar | alta | implementado |
| RF12 | O coletor publica os dados no painel a cada 5 minutos (`--publicar`) | alta | implementado |
| RF13 | Coleta restrita a janelas de horário em dias úteis (`--janelas`, `--fim-de-semana`) | alta | implementado |
| RF14 | Mapa de cobertura (dias × horas, últimos 14 dias) no painel | alta | implementado |
| RF15 | Detectar veículo parado na imagem por 20 s ou mais dentro do clipe (`incidentes.parados`) | alta | implementado (18/11/2026) |
| RF16 | Abrir incidente quando o **mesmo veículo** (classe, altura da caixa e descritor de cor) fica parado em dois clipes seguidos (até 5 min) e estendê-lo enquanto continuar parado, sem nova classificação | alta | implementado (18/11/2026); gate de identidade em 21/11/2026 (fase 2m) |
| RF17 | Classificar o incidente com um modelo de visão local (Ollama, `qwen3-vl:4b-instruct`) a partir de 4 imagens (3 quadros e uma ampliação do veículo): acidente, enguiço, estacionado, fila, bloqueio ou indeterminado, com confiança e descrição curta | alta | implementado e testado em clipe real (19/11/2026); precisão ainda não medida; `VIZINHOS_FILA` e `RECORRENTE_H` evitam classificar fila e o mesmo ponto (21/11/2026) |
| RF18 | Painel mostra acidentes, enguiços e bloqueios das últimas 24 h que duraram 3 clipes seguidos ou mais, com aviso de classificação automática não confirmada, início e fim | alta | implementado e publicado (19/11/2026); dedupe por evento e exibição de duração em 21/11/2026 |
| RF19 | Primeira tela legível por leigo (o prefeito, a população): frase de veredito do momento, situação de cada ponto em texto e cor, ocorrências e câmeras no ar; gráficos técnicos recolhidos | alta | implementado e publicado (19/11/2026) |
| RF20 | Situação de cada ponto contado (livre, moderado, pesado) comparando a ocupação dos últimos 15 min com todo o histórico da própria câmera (14 dias); sem 30 clipes de histórico, diz que ainda não há base | alta | implementado (19/11/2026) |
| RF21 | Ônibus por hora e intervalo médio entre ônibus na última hora, por câmera contada | alta | implementado (19/11/2026), contagem de ônibus não validada |
| RF23 | Histórico da coleta: cada período contínuo de coleta vira um bloco com uma frase (minutos pesados e pior momento por câmera, ocorrências) e uma faixa de 5 em 5 minutos colorida por nível; fora da coleta, o topo resume o último período em vez de só dizer "pausado" | alta | implementado e publicado (19/11/2026) |
| RF24 | Mapa da região (OpenStreetMap) com um ponto por câmera: cor pela situação quando a coleta roda, azul para ponto medido e cinza para câmera sem contagem quando parada; ao tocar, nome e resumo do último período; posições marcadas como aproximadas | alta | implementado e publicado (19/11/2026) |
| RF25 | Feed RSS (`feed.xml`) com um texto pronto para post por período encerrado e por ocorrência publicável (título de até 240 caracteres, identificador estável, aviso de medição automática), publicado junto com `dados.json` | alta | implementado e publicado (19/11/2026) |
| RF26 | Coleta contínua, 24 h e todos os dias, das 2 câmeras contadas (sem `--janelas`) | alta | ligado em 19/11/2026 às 15h29 por decisão do autor |
| RF27 | Gravar cada passagem (câmera, clipe, segundo, tipo, sentido) na tabela `passagens`, somando exatamente a contagem do clipe | alta | implementado (19/11/2026) |
| RF28 | Gravar chuva (mm) e temperatura por hora do Open-Meteo para o Centro de Niterói, uma vez por hora | alta | implementado (19/11/2026) |
| RF29 | Cópia diária e consistente do `fluxo.db` no servidor, fora da pasta pública (`~/backup-transito/fluxo-AAAA-MM-DD.db`) | alta | implementado (19/11/2026) |
| RF30 | Dados abertos: `dados-por-hora.csv` com toda a história, uma linha por câmera e hora de Niterói, tipos, sentidos, ocupação média e chuva | alta | implementado e publicado (19/11/2026) |
| RF22 | Verificar a cada 5 min se cada uma das 7 câmeras da região responde e renova a imagem (só cabeçalho HTTP, sem baixar vídeo) e mostrar "x de 7 no ar" | alta | implementado (19/11/2026) |
| RF6 | Contagem por movimento no cruzamento (reto, conversões) | média | pendente |
| RF7 | Ler tempos de semáforo do vídeo | média | pendente |
| RF8 | Velocidades por trecho via API (TomTom/HERE) para trechos sem câmera | média | pendente |
| RF9 | Gêmeo digital no SUMO calibrado com os dados | futuro | pendente |
| RF10 | Agente que propõe e testa intervenções no simulador | futuro | pendente |

## Requisitos de método

O projeto é um estudo cívico que pode virar acadêmico e, depois, produto. Nenhuma conclusão sai de dado não validado.

| # | Requisito | Prioridade | Status |
|---|---|---|---|
| RM1 | Validar a contagem automática contra contagem manual às cegas em amostra de clipes (dia, noite, pico, chuva), reportando erro por câmera | alta | parcial: ferramenta pronta, contagem manual pendente |
| RM5 | A validação separa o erro por tipo de veículo (carro, moto, ônibus, caminhão), além do total por sentido | alta | parcial: ferramenta pronta (15/11/2026), contagem manual pendente |
| RM6 | A contagem manual registra o instante de cada veículo, e a comparação aponta veículo a veículo o que o sistema perdeu, contou a mais ou classificou errado | alta | parcial: ferramenta pronta (15/11/2026), contagem manual pendente |
| RM7 | As configurações candidatas do detector (padrão, rastreador permissivo, permissivo a 960 px) são comparadas sobre os mesmos clipes num só relatório | alta | implementado (15/11/2026) |
| RM2 | Registrar versão do modelo, linha de contagem e parâmetros usados em cada clipe | alta | implementado |
| RM3 | Toda afirmação do relatório aponta para a consulta/dado que a sustenta (reprodutível) | alta | pendente |
| RM4 | Intervenções só são recomendadas após teste em simulação calibrada, com incerteza declarada | futuro | pendente |

## Requisitos não funcionais

- **Privacidade (LGPD):** nenhum vídeo, imagem ou placa é guardado. O clipe vive em pasta temporária e é apagado após a contagem. Exceção única: a amostra de validação fica em `validacao/` até a contagem manual e é apagada com `validar.py limpar`. Os 3 quadros de um incidente são analisados por um modelo que roda no próprio notebook (Ollama) e não saem dele; só o texto da resposta é guardado. A instrução ao modelo proíbe descrever pessoas e ler placas. O painel informa isso em "Como é medido".
- **Uso responsável do servidor público:** poucas câmeras, intervalo mínimo de 60 s, sem repetição agressiva em caso de erro.
- **Custo:** zero; roda localmente, inclusive a classificação de incidentes. Em 18/11/2026 o autor havia escolhido a API do Claude (Haiku 5.5), mas ficou sem créditos e passou para o modelo local em 19/11/2026.
- **Segredos:** não há chave nem credencial no projeto.

## Regras de negócio

- **Incidente:** veículo parado (pé da caixa a menos de 0,3 altura da caixa do ponto de parada) por 20 s ou mais no clipe, que é o **mesmo veículo** — classe, altura da caixa e descritor de cor parecidos — de um parado do clipe anterior da mesma câmera (até 40 px e 5 min antes). Carros diferentes no mesmo ponto (fila de semáforo) não abrem incidente; com 4 ou mais vizinhos parados, também é fila. Começa no primeiro clipe em que o veículo apareceu parado. Parado num clipe só não abre incidente: costuma ser semáforo.
- **Classificação:** feita uma vez, quando o incidente abre. Tipos `acidente`, `enguico`, `estacionado`, `fila`, `bloqueio`, `indeterminado`; o modelo é instruído a preferir `indeterminado` a adivinhar. Só `acidente`, `enguico` e `bloqueio` vão para o painel (`PUBLICAVEIS`).

- Um veículo (uma trajetória rastreada) conta no máximo uma vez por clipe.
- Sentido é definido em relação à linha de contagem A→B desenhada da esquerda para a direita: `desce` = move-se para baixo na imagem (vem na direção da câmera); `sobe` = para cima (afasta-se). Nas câmeras da Jansen de Melo a imagem olha para a ponte, então `desce` = da ponte para Icaraí e `sobe` = para a ponte (`ROTULO_SENTIDO` em `coletor.py`).
- Fluxos de sentidos opostos nunca são somados; câmeras diferentes na mesma avenida também não, porque o mesmo veículo passa por duas.
- Clipe é identificado por câmera + `Last-Modified` do servidor.
- Na contagem manual, conta o veículo motorizado cuja base cruza o trecho amarelo da linha (quem passa fora do trecho não conta), no instante do cruzamento. Tipos: `carro` inclui SUV, picape e van; `moto` inclui motoneta; `onibus` inclui micro-ônibus; `caminhao` inclui VUC e carreta. Bicicleta não conta. Regra confirmada pelo autor em 15/11/2026.
- Um veículo contado à mão e um cruzamento automático são o mesmo veículo se estão no mesmo sentido e a até 2 s um do outro (`TOLERANCIA_S` em `validar.py`).

## Critérios de aceitação (fase 1)

- Rodar `--uma-vez` grava uma linha por câmera com contagens plausíveis frente à inspeção visual do clipe.
- Rodar de novo sobre o mesmo clipe não grava linha nova.
- Falha de uma câmera não derruba a coleta das outras.

## Fora de escopo agora

Previsão, simulação, as outras 5 câmeras do recorte, coleta em servidor (o único recurso de processamento é o notebook do autor; o painel só recebe dados enquanto o coletor roda nele).

## Direção do produto (19/11/2026)

Pedido do autor: o painel precisa ser útil e entendido "de cara" pelo prefeito e pela população, com valor de gestão e de governança, cobrindo o efeito da fila da Jansen de Melo no Fonseca, em Santana e na BR. Ideias aceitas para as próximas fases: contagem de ônibus como serviço à população, as 7 câmeras da região coletando juntas, diagnóstico cruzando câmeras (onde a fila nasce e quanto tempo leva para chegar a outro ponto), tempo até a pista ser liberada em cada ocorrência, comparação com o habitual de cada dia e horário, antes e depois de intervenções, boletim semanal e dados abertos. O autor quer evitar contagem manual: a proposta é checagem automática por uma segunda IA, com revisão humana só onde as duas discordam.

## Dúvidas e decisões pendentes

- **Aviso à NitTrans sobre coleta contínua:** o autor decidiu ligar a coleta 24 h em 19/11/2026 ("ligar tudo"). O aviso à NitTrans, que este documento pedia antes da coleta contínua, é do autor (mensagem em nome dele); a carga no servidor público continua a mesma da coleta de pico (2 clipes por minuto).
- **Operação contínua no notebook:** o coletor roda como processo da sessão do Claude Code e para quando ela fecha; para durar dias, rodar o comando do README num terminal próprio e configurar o Windows para não suspender na tomada (configuração do autor). Alternativa durável: um computador dedicado.

- **Publicação automática em redes sociais:** o projeto gera o RSS; quem publica é um serviço que lê RSS (Buffer, IFTTT, Zapier, Make) ligado às contas do autor, para o projeto não guardar senha de rede social. Alternativa: robô próprio (canal de Telegram, Bluesky) com chave criada pelo autor. Falta o autor escolher as redes e criar as contas e ligações. Risco: post automático amplifica erro; por isso ocorrências saem como "possível ... (classificação automática, não confirmada)" e só depois de 3 clipes.
- **Mapa de calor:** adiado de propósito. Com 2 pontos medidos, um mapa de calor interpolaria trânsito onde não há medição (Fonseca, Santana). Proposta para quando as 7 câmeras contarem: colorir o trecho de rua de cada câmera e dimensionar cada ponto pelos minutos pesados das últimas semanas ("pontos críticos").

- **Qualidade do modelo local (RF17):** em 19/11/2026, no único caso de teste disponível (carro nas bombas de um posto de gasolina, câmera 000018, noite), a primeira versão do prompt deu "enguiço, confiança alta", um falso positivo. Com a ampliação do veículo e a instrução de checar antes se ele está sobre a pista, passou a dar "estacionado", correto, em duas rodadas. Em coleta real de manhã, 2 incidentes foram classificados "estacionado" e nenhum acidente ou enguiço apareceu. **Nenhum acidente ou enguiço verdadeiro foi visto ainda**, então não se sabe se o modelo acerta esses casos (só que não inventou nos que viu). Proteção na publicação: `MIN_CLIPES_PUBLICAR = 3`. Alternativas se errar: (a) subir para `qwen3-vl:8b` (6,2 GB, não cabe inteiro na GPU de 6 GB, fica mais lento); (b) voltar à API do Claude quando houver crédito, trocando só `classificar_vlm`. Decidir depois de medir a precisão nos primeiros ~20 incidentes.
- **Limiares do detector de parado** (`PARADO_S` 20 s, `TOLERANCIA` 0,3 altura da caixa, `MESMO_LUGAR_PX` 40, `EMENDA_MIN` 5): escolhidos a olho. Nos 13 clipes noturnos de `validacao/` houve 2 parados isolados e nenhum incidente (um deles é carro no posto da 000018, que o modelo deveria chamar de `estacionado`). Calibrar com os primeiros incidentes de dia e de pico.
- **Vagas e pontos fixos:** carro estacionado no mesmo lugar vira um incidente `estacionado` por episódio (custo de uma chamada, não publicado). Se repetir muito, alternativa: zona de exclusão por câmera em `CAMERAS`.
- **Publicação com aviso:** decidido pelo autor em 18/11/2026: acidente, enguiço e bloqueio aparecem no painel marcados como classificação automática, mesmo antes de validados. Risco aceito: mostrar um "acidente" que não houve. Falta medir a precisão (quantos incidentes classificados conferem com o vídeo) antes de usar em relatório.

- **Permissão da NitTrans** para coleta automatizada contínua. Alternativas: (a) avisar e pedir anuência antes de rodar 24 h; (b) rodar só em picos curtos enquanto isso. Adotado por ora: (b).
- **Câmera Alameda Acesso Ponte (000019, lado do Fonseca), "super importante" segundo o autor:** ainda não coletada. O autor descreveu um lado da imagem como "sobe a ponte e vai para o Centro" e o outro como "desce da ponte e vai sentido Fonseca", mas na mensagem os dois lados saíram como "direito"; **falta confirmar qual é o esquerdo e qual é o direito**. Importância: ela cobre o ramo da descida que vai ao Fonseca, enquanto a 000018 cobre o ramo que vai a Icaraí/Centro. Só entra em `CAMERAS` depois dessa confirmação e da calibração da linha de contagem.
- **Amostragem sem coleta 24 h:** decidido em 12/11/2026. Coleta em janelas fixas (`--janelas`, padrão recomendado 06:30–09:30 e 17:00–20:00 em dias úteis), repetidas por cerca de duas semanas; o painel mostra o mapa de cobertura dos últimos 14 dias e as conclusões valem só para as horas cobertas. Falta decidir se entra uma janela de vale (ex.: 11:00–12:00) como referência.
- **Detecção de motos:** em 600+ veículos o modelo não contou nenhuma moto, o que é incompatível com o trânsito de Niterói (observação do autor). Diagnóstico (12/11/2026, 3 clipes noturnos, 1 quadro em 5, detecções antes do rastreador): `yolo11n` a 640 px e confiança 0,25 achou 57 motos; a 960 px e confiança 0,10 achou 148; `yolo11s` a 960 px e 0,10 achou 233. Causa encontrada: o rastreador (ByteTrack) só abre trajetória com confiança ≥ 0,25 (`new_track_thresh`), então baixar `--conf` sozinho não muda nada. Nos 6 clipes noturnos guardados, rastreador padrão: 0 trajetórias de moto, 170 carros cruzam a linha. Com `rastreador_permissivo.yaml` (0,10): 14 trajetórias de moto (2 cruzam a linha), 264 carros cruzam (+55%), 23 s por clipe a 640 px e 39 s a 960 px. Não se sabe se o aumento de carros é veículo real que antes se perdia ou o mesmo veículo contado duas vezes: **só a contagem manual decide**. O coletor continua com a configuração padrão até lá; as três opções são comparadas de uma vez com `validar.py comparar --todas`, que mostra por tipo quantos veículos cada uma perdeu e quantos contou a mais. **Correção (19/11/2026):** o Ultralytics instalado (8.4.211, o mesmo desde 13/11) usa por padrão o rastreador TrackTrack, não o ByteTrack, e ele só abre trajetória com confiança ≥ 0,7 (`new_track_thresh`); é o que o coletor usa hoje. `rastreador_permissivo.yaml` continua sendo ByteTrack. Comparação com uma referência automática (`yolo11x` a 1280 px) na fase 2 do `STEPS.md`: a configuração atual do coletor conta de 37% a 73% menos que a referência à noite.
- **Limiar de erro aceitável** na validação (RM1): proposto ≤ 10% por câmera e período; confirmar com orientador/literatura se o estudo virar acadêmico. Por tipo de veículo o mesmo limiar é marcado no relatório, mas com poucas motos, ônibus e caminhões por clipe a porcentagem oscila muito: **falta decidir** se o critério por tipo é porcentagem ou número absoluto de veículos perdidos.
- **Regra de tipos na contagem manual:** decidida em 15/11/2026 (van e picape como carro, VUC como caminhão; ver regras de negócio). Em aberto só o efeito no relatório: o detector usa as classes do COCO, em que picape grande costuma sair como caminhão; se isso gerar muitos "trocados", alternativas: (a) manter os 4 tipos; (b) juntar ônibus e caminhão em "pesados" no relatório.
- **Tolerância de 2 s no pareamento:** escolhida sem medição. Se a fila andar devagar e a pessoa demorar a apertar, veículos certos aparecem como "perdido" + "a mais"; ajustar depois da primeira contagem real.
- **Desempenho:** em CPU, duas câmeras levam ~75 s por rodada e o clipe renova a cada ~62 s, então parte dos clipes é perdida. Alternativas: (a) `--passo 2`, **descartada** em 12/11/2026 porque a contagem desaba (ver `STEPS.md`); (b) instalar PyTorch com CUDA (a máquina tem RTX 3050); (c) aceitar amostragem, contando um clipe sim, um não. Não decidido entre (b) e (c).
- **Sentido real de cada câmera:** Jansen x Mal. Deodoro (000018) **confirmado pelo autor em 12/11/2026**: lado esquerdo da imagem = da ponte para Icaraí ("desce" na imagem), lado direito = para a ponte ("sobe"). Jansen sent. Ponte (000026): **a confirmar** (clicar no marcador no mapa do app e/ou conferir uma referência na rua). A câmera gira: até 13/11 mostrava só o fluxo que se afasta; de 16/11 em diante mostra as duas pistas, e a linha foi refeita em 20/11/2026 para atravessar as duas ("desce" = vem para a câmera, "sobe" = se afasta). Consequência: até confirmar, o estudo da descida para Icaraí usa o "desce" da 000018.
- **Oitava câmera** do recorte: não identificada na lista oficial.
