# STEPS — Fluxo Niterói

Atualizado em 19/11/2026.

## Fase 1 — Coletor mínimo · **concluída**

- Objetivo: provar que dá para extrair contagem das câmeras públicas.
- Feito: `coletor.py` (download, rastreamento, contagem por linha, ocupação, SQLite, laço tolerante a falha), 7 testes unitários, lint.
- Prova: `ruff` limpo, 7/7 testes; execução real em 12/11/2026 gravou 3 clipes de 2 câmeras (ex.: 000026 com 21 e 27 carros em ~60 s).
- Não feito: teste automatizado da parte de vídeo/rede (débito).

## Fase 2 — Validação do método · **em andamento**

- Objetivo: saber o erro da contagem antes de usar qualquer número (RM1, RM2).
- Concluído:
  - `validar.py`: `amostrar` (guarda clipe + vídeo só com a linha), `comparar` (roda o contador, grava `resultado_*.csv`, mostra erro por câmera/condição/sentido; `--diag` grava vídeo com caixas e IDs), `limpar` (apaga vídeos já contados).
  - Parâmetros por clipe no banco (`modelo`, `passo`, `linha`), com migração de banco antigo (RM2).
  - Primeira amostra: 6 clipes noturnos (3 por câmera) em `validacao/`, aguardando contagem manual.
  - Validação por tipo de veículo e veículo a veículo (15/11/2026, RM5 a RM7):
    - `validar.py contar`: contador por teclado, uma tecla por veículo (tipo × sentido), com pausa, volta de 3 s, meia velocidade e desfazer; grava `eventos.csv` (instante de cada veículo) e os totais em `manual.csv`.
    - `comparar`: erro por tipo além do total; pareamento no tempo aponta perdidos, a mais e classe trocada em `divergencias_*.csv`; `--todas` compara padrão, permissivo e permissivo a 960 px numa tabela só.
    - `manual.csv` migrado para 8 colunas (tipo × sentido); `amostrar` deixou de gerar a cópia `_linha.mp4`.
    - Corrigido: o nome do arquivo de resultado truncava a confiança (`--conf 0.10` virava `conf0`), e duas confianças diferentes gravariam no mesmo arquivo.
    - Prova: `ruff` limpo, 39/39 testes, cobertura 57% (validar 52%). Execução real numa pasta temporária, com um clipe e contagem manual fabricada a partir do automático (um veículo removido, um com a classe trocada): as três configurações rodaram, e as divergências apontaram exatamente o veículo removido como "a mais" e o alterado como "classe trocada". A tela do contador foi conferida por imagem gerada, **não por sessão real com teclado**.
    - Amostra ampliada: mais 7 clipes noturnos em 15/11/2026 (domingo e feriado, ~22 h), total de 13 (7 da 000026, 6 da 000018). Nenhum de dia ou de pico ainda.
  - Referência automática, sem contagem manual (19/11/2026, pedido do autor: "o ideal era ter uma contagem automática"):
    - `validar.py referencia` conta os clipes guardados com `yolo11x` a 1280 px (pesos baixados em 19/11, 109 MB) e grava `referencia.csv` e `eventos_referencia.csv` no formato da contagem manual; `comparar --contra referencia` compara com ela. Grava a cada clipe e retoma de onde parou (2 a 4 min por clipe na GPU dividida com o coletor; 31 min nos 13).
    - **Não é erro real:** a referência também erra. Mede quanto a contagem muda com mais modelo e resolução; alguns clipes contados à mão dizem se ela está perto da realidade.
    - Resultado nos 13 clipes noturnos, total de veículos (tabela por tipo e sentido em `validacao/comparacao_referencia.txt`, por clipe em `resultado_*_contra_referencia.csv`):

      | Grupo | Referência `yolo11x` 1280 | Coletor hoje (`yolo11n` 640) | `yolo11n` permissivo 640 | `yolo11n` permissivo 960 | `yolo11s` 960 |
      |---|---|---|---|---|---|
      | 000018, 6 clipes | 329 | 207 (−37%) | 290 (−12%) | 304 (−8%) | 270 (−18%) |
      | 000026 de 16/11, 4 clipes | 111 | 30 (−73%) | 88 (−21%) | 81 (−27%) | 108 (−3%) |
      | 000026 13/11 00:42 | 19 | 23 | 33 | 30 | 22 |
      | 000026 13/11 00:43 e 00:44 | 7 | 31 | 64 | 59 | 23 |

    - Leitura: em todos os clipes, menos os três de 13/11 da 000026, a configuração do coletor é a que menos conta, abaixo de todas as outras. Pior caso: 000018 no sentido "da ponte para Icaraí", 79 contra 187 da referência (−58%). Se a referência estiver perto da realidade, **os números noturnos publicados estão bem abaixo do real**. Dia e pico não foram medidos (nenhum clipe).
    - Causa provável: o Ultralytics instalado (8.4.211, o mesmo em todos os clipes do banco desde 13/11) usa por padrão o rastreador **TrackTrack**, não o ByteTrack, e ele só abre trajetória com confiança ≥ 0,7 (`new_track_thresh`); à noite o `yolo11n` raramente chega a isso. O modelo maior e o ByteTrack permissivo (0,10) passam do limiar com mais frequência.
    - A conferir no vídeo: nos clipes 000026 de 13/11 00:43 e 00:44 a referência vê 1 e 6 veículos e as outras configurações de 9 a 32. Suspeita: fila parada sobre a linha, com caixa tremendo e troca de ID gerando cruzamentos falsos nos modelos menores. Rodar `comparar --contra referencia --diag` nesses clipes e assistir.
    - Atenção: `manual.csv` tem dois clipes (000026_20261113T004220 e 000018_20261113T004214) com as 8 colunas em zero e nenhum evento em `eventos.csv`. `comparar` os trata como contados com zero veículo. Parece teste do contador, não contagem: confirmar com o autor e apagar os zeros antes da comparação com a contagem manual.
    - Prova: `ruff` limpo, 80/80 testes, cobertura total 74% (um teste novo: a referência sai no formato da contagem manual, não toca `manual.csv` e retoma sem recontar clipe feito); execução real nos 13 clipes e as duas comparações acima.
    - Incidentes na mesma noite: (1) das 18h56 às 19h56 o envio ao site falhou (`scp` com 0xC0000142, processo sem console depois que a sessão que o iniciou fechou); a contagem continuou no banco. O coletor passou a rodar num console oculto próprio. (2) Por volta das 20h44 o `.venv` foi apagado em parte, por causa não identificada (sem `pyvenv.cfg`, pacotes do Ultralytics sumindo): 3 rodadas do coletor falharam e a primeira execução da referência caiu. O `.venv` foi recriado do `uv.lock` (mesmas versões, CUDA funcionando) e o coletor religado às 20h52.
- Pendente (depende de pessoa):
  - Contagem manual às cegas com `uv run validar.py contar`. Meta: ~20 clipes por câmera, cobrindo dia, noite, pico e chuva.
  - Guardar clipes de dia e de pico em dia útil (`amostrar --condicao dia`, `--condicao pico-manha`, `--condicao pico-tarde`), rodando o comando nesses horários.
  - Decidir o critério de erro por tipo (ver dúvidas em `REQUIREMENTS.md`). A regra de tipos da contagem manual foi confirmada pelo autor em 15/11/2026.
  - Recalibrar as linhas com quadros diurnos; confirmar o sentido real de cada câmera.
  - **`--passo 2` descartado.** Nos 6 clipes da amostra (yolo11n, 12/11/2026), passo 1 contra passo 2:

    | Clipe | Passo 1 (desce / sobe) | Passo 2 (desce / sobe) |
    |---|---|---|
    | 000018 00:42 | 21 / 9 | 16 / 1 |
    | 000018 00:43 | 21 / 26 | 19 / 7 |
    | 000018 00:44 | 22 / 18 | 18 / 6 |
    | 000026 00:42 | 0 / 23 | 0 / 14 |
    | 000026 00:43 | 0 / 15 | 0 / 0 |
    | 000026 00:44 | 0 / 16 | 0 / 0 |

    A 5 quadros por segundo o rastreador não liga as detecções do mesmo veículo e a trajetória nunca cruza a linha. Tempo por clipe em CPU: 31 a 44 s no passo 1 (incluindo gravar o vídeo de diagnóstico), 13 a 18 s no passo 2.
- Pendente (técnico):
  - Instalar PyTorch com CUDA (RTX 3050) e medir o tempo por clipe, para acompanhar mais de uma câmera em tempo real.
  - O resultado acima levanta a suspeita de que 10 quadros por segundo já percam veículos rápidos; a contagem manual vai confirmar ou afastar.
- Critério de conclusão: erro por câmera e período documentado; ≤ 10% ou causa identificada.
- Risco: noite/chuva/oclusão por ônibus podem exigir modelo maior.
- Pendência externa: avisar a NitTrans sobre a coleta.

## Fase 2b — Painel público · **concluída em 12/11/2026**

- Objetivo: mostrar os dados na internet enquanto o estudo anda.
- Feito: `exportar.py` (6 testes), painel React + Astryx em `painel/`, publicado em https://transito.fanara.com.br/ (HTTPS ativo), coletor com `--publicar`.
- Prova: `ruff` limpo, 20/20 testes Python; `tsc` e `oxlint` limpos; `astryx doctor --built` sem falhas; conferido no navegador em largura de computador e de celular, modo escuro; paleta validada em claro e escuro; site respondendo 200 com os dados reais.
- Página `/sobre/` (modelo `documentation-technical` do Astryx): o que é, como funciona, guia de cada gráfico (o que mostra, como ler, cuidado), método, limites e perguntas frequentes com JSON-LD `FAQPage`. O texto das perguntas existe em `src/faq.ts` e em `sobre/index.html`; precisam ser mudados juntos.
- Não feito: testes automatizados do painel; conferência visual no modo claro; relatório de SEO em documento.
- Sentidos (12/11/2026): o autor confirmou o sentido da 000018 pelo mapa do app; o painel e a página Sobre passaram a separar o fluxo por sentido (da ponte para Icaraí / para a ponte). Pendente: confirmar o sentido da 000026; a descida só é medida pela 000018.
- Cobertura: coletor com `--janelas` (4 testes) e mapa de cobertura no painel a partir de `exportar.cobertura` (2 testes); guia na página Sobre.
- Auditoria SEO/GEO/AEO (conferência manual da página publicada):
  - OK: título (58 caracteres), descrição, canonical, `lang="pt-BR"`, um único H1, Open Graph, dados estruturados `Dataset`, `robots.txt`, `sitemap.xml`, HTTPS, viewport.
  - Pendente: imagem de compartilhamento (`og:image`); conteúdo depende de JavaScript; sem página "sobre" com autoria e contato (E-E-A-T); sem perguntas e respostas (AEO); peso do JavaScript.

## Fase 2c — Incidentes (veículo parado + modelo de visão local) · **publicada em 19/11/2026**

- Objetivo: dar contexto ao painel dizendo quando há acidente, enguiço ou bloqueio, em vez de só números (pedido do autor em 18/11/2026, depois de pesquisar soluções prontas de código aberto: nenhuma separa acidente de enguiço).
- Decisões do autor: ocorrências no site público com aviso, antes de validar (18/11/2026). Modelo de visão: começou com a API do Claude (Haiku 5.5), mas a conta ficou sem crédito e passou para um modelo local no Ollama em 19/11/2026. A chamada ao Claude foi removida do código e a dependência `anthropic` saiu. No dia 19/11 o autor, longe do computador, autorizou ir até a publicação sem pedir aprovação.
- Feito:
  - `incidentes.py`: `observador`, `parados`, `imagens` (3 quadros + ampliação), `classificar_vlm` (Ollama, saída por esquema JSON), `registrar`, `criar_tabelas`.
  - `coletor.coletar` chama o detector depois de gravar a contagem; log `INCIDENTE <tipo> <confiança> <descrição>`.
  - `exportar.ler_ocorrencias` e campo `ocorrencias` em `dados.json`: só acidente, enguiço e bloqueio, últimas 24 h, com incidente de 3 clipes ou mais (`MIN_CLIPES_PUBLICAR`).
  - Painel: bloco "Ocorrências nas últimas 24 horas" com selo por tipo (`Badge` do Astryx), descrição, duração e confiança; aviso de classificação automática; "Como é medido" informa que a análise roda no computador do autor.
- Achados do teste real (19/11/2026):
  - A variante padrão `qwen3-vl:4b` é "thinking": estourou o limite de resposta raciocinando e devolveu conteúdo vazio. Trocada por `qwen3-vl:4b-instruct`.
  - Com 4 imagens, o contexto padrão do Ollama (4096) estourou (HTTP 400, 4673 tokens). `num_ctx` passou para 8192.
  - Primeira versão do prompt: carro nas bombas de um posto saiu "enguiço, confiança alta" (falso positivo). Com a ampliação do veículo e a instrução de checar se está sobre a pista, saiu "estacionado, alta", correto, nas duas rodadas. O 4B é confiante demais: a confiança do modelo não é medida de acerto.
  - Outro parado guardado (000026) saiu "fila, alta", plausível (semáforo com trânsito atrás).
- Prova:
  - `ruff` limpo, 51/51 testes, cobertura total 63% (`incidentes` 90%).
  - Coleta real de manhã (19/11, ~07h15 a 07h25), duas câmeras, com o modelo local: parados de fila de semáforo não abriram incidente; 2 incidentes classificados como "estacionado" (fora do painel); nenhum acidente ou enguiço. Latência da classificação ~5 a 15 s com o modelo carregado.
  - Painel: `oxlint`, `tsc` e build limpos; `astryx doctor --built` sem falhas (3 avisos); conferido no navegador em escuro, computador e celular. **Publicado** em https://transito.fanara.com.br/ (HTTP 200, bloco de ocorrências presente, sem erro no console, "Coletando agora"). Backup do site anterior em `backup-site/transito-antes-2026-11-19.tgz` (ignorado pelo Git).
  - Coletor deixado rodando: `uv run coletor.py --janelas 06:30-09:30,17:00-20:00 --publicar hostgator-fanara:transito.fanara.com.br` (log em `coletor.log`).
- Pendente:
  - **Ver um acidente ou enguiço verdadeiro passar pelo modelo.** Até lá, a precisão nesses casos é desconhecida e o painel só mostra o que durar 3 clipes.
  - Medir precisão: anotar, para os primeiros ~20 incidentes, se o tipo confere com o vídeo; decidir entre `qwen3-vl:8b` e voltar ao Claude (ver `REQUIREMENTS.md`).
  - Calibrar limiares com casos de dia e de pico; avaliar zona de exclusão para vagas fixas e pontos de ônibus.
  - O coletor depende do notebook ligado, com o Ollama aberto, e para quando a sessão do Claude Code fechar.
  - Observação sem causa investigada: de manhã a 000026 contou ~474 veículos/h "da ponte para Icaraí" e ~2.200 "para a ponte"; o `REQUIREMENTS.md` dizia que ela só vê o sentido que se afasta. O sentido dessa câmera continua "a confirmar".

## Fase 2d — Painel para leigos (veredito, pontos, ônibus, câmeras no ar) · **publicado em 19/11/2026**

- Pedido do autor (19/11/2026): painel útil para população e gestores, que o prefeito entenda de cara, com apelo visual; começar pelo painel e depois baixar o PyTorch com GPU.
- Direção visual (skill ui-ux-pro-max, estilo "Accessible & Ethical", indicado para governo e público amplo): tema claro de alto contraste, fonte Atkinson Hyperlegible, status sempre em texto além da cor, detalhes técnicos recolhidos.
- Feito: `REGIAO` e `checar_cameras` no coletor; `situacao`, `onibus`, `cameras_no_ar` e `veredito` no exportador; painel com veredito, situação por ponto (7 câmeras em 4 eixos), ocorrências, câmeras no ar e "Detalhes técnicos" recolhido; título e descrição da página falam da região, não só da Jansen; texto de "Como é medido" corrigido (a 000026 mostra os dois sentidos).
- Prova: `ruff` limpo, 58/58 testes (7 novos em `test_painel_dados.py`), cobertura total 67% (`exportar` 96%); `oxlint`, `tsc`, build e `astryx doctor --built` sem falhas; conferido no navegador com o sistema em modo escuro (achado e corrigido o fundo preto), detalhes abertos e celular de 375 px sem rolagem lateral; `dados.json` real com as 7 câmeras "no ar" e veredito "Trânsito livre ou moderado".
- GPU: PyTorch 2.14.1+cu126 instalado (o driver 577 suporta CUDA 12.9; a 2.15 não existe para CUDA 12.x antigo). `torch.cuda.is_available()` verdadeiro na RTX 3050. Clipe de 62 s: 16 s com `yolo11n` (era 31 a 44 s na CPU), 23 s com `yolo11s` a 960 px, que achou 1 moto e 2 carros a mais no mesmo clipe. O coletor foi reiniciado e já roda na GPU, ainda com `yolo11n`.
- Publicado em 19/11/2026 ~09h47 com autorização do autor: HTTP 200 em `/`, `/sobre/` e `dados.json`; conferido no navegador com o sistema em modo escuro (fundo claro, fonte carregada, sem erro no console), mostrando "Coleta pausada" fora da janela, como esperado. Backup do site anterior em `backup-site/transito-antes-painel-novo-2026-11-19.tgz`.
- Pendente: fase 1 (modelo maior, 7 câmeras, checagem automática por segunda IA).

## Fase 2e — Histórico da coleta e correções da análise crítica · **publicado em 19/11/2026**

- Origem: captura do autor no celular às 9h56 de 19/11 (coleta parada) e análise crítica com a skill ui-ux-pro-max. Achados: o topo gastava a tela com "Coleta pausada"; 7 cartões sem informação sobre a rua ("contagem ainda não ligada", "sem medição agora"); ônibus ao lado de "sem medição"; "7 de 7 no ar" com a coleta parada; método antes do conteúdo; texto de apoio de 11 a 12 px; títulos sem negrito no celular. Pedido do autor: "temos que ter um histórico da coleta e que seja útil e fácil".
- Feito: `exportar.periodos` e `_frase_periodo`; veredito pausado com o resumo do último período; painel com "Histórico da coleta" (faixa de 5 em 5 min e frase por período), "agora" só com coleta rodando e só pontos medidos, câmeras no ar só com verificação recente, textos maiores, fonte Atkinson Hyperlegible Next no eixo de tipografia.
- Achado e corrigido: no celular (tela de toque, abaixo de 1024 px) o tema neutro regravava a fonte Figtree por cima do token; era a causa dos títulos diferentes na captura do autor.
- Prova: `ruff` limpo, 60/60 testes (2 novos de períodos, veredito atualizado), cobertura total 69%; `oxlint`, `tsc`, build e `astryx doctor` sem falhas; conferido no navegador em computador e celular de 375 px (fonte carregada em peso 600 nos dois, sem rolagem lateral, sem erro no console), com os 3 períodos reais: hoje das 07h14 às 09h29 (Jansen x Mal. Deodoro pesada por 15 min, pior às 07h25), 15/11 e 12/11 à noite. Coletor reiniciado para usar o exportador novo.
- Publicado em 19/11/2026 ~10h40 (ver fase 2g).

## Fase 2f — Mapa das câmeras · **publicado em 19/11/2026**

- Pedido do autor (19/11/2026): mapa de Niterói com o ponto das câmeras, para facilitar a leitura do cidadão.
- Feito: coordenadas das 7 câmeras pelo OpenStreetMap; `Mapa.tsx` com Leaflet; seção "Onde ficam as câmeras" logo abaixo do veredito, com legenda em texto e balão por ponto.
- Prova: `tsc`, `oxlint`, build e `astryx doctor` sem falhas; 60/60 testes Python; conferido no navegador em computador e celular (375 px, sem rolagem lateral, atribuição do OpenStreetMap presente); o toque no ponto da Jansen x Mal. Deodoro abre "Hoje, das 07:14 às 09:29: pesado por 15 min. Posição aproximada". Coletor reiniciado para publicar as coordenadas.
- Publicado em 19/11/2026 ~10h40 (ver fase 2g).
- Pendente: o autor conferir as posições aproximadas (Ilha da Conceição, Alameda acesso à Ponte, Jansen sentido Ponte, Feliciano Sodré).

## Fase 2g — Feed de texto para redes sociais · **publicado em 19/11/2026**

- Pedido do autor (19/11/2026): transformar os dados em texto, num feed que possa ser publicado automaticamente em redes sociais; e mapa de calor das áreas críticas.
- Feito: `itens_feed` e `feed` (RSS 2.0), gravado e enviado com os dados; link no `<head>` e no histórico. Mapa de calor adiado com motivo (ver `REQUIREMENTS.md`).
- Prova: 62/62 testes (2 novos: só períodos encerrados viram item, título exato, limite de 240 caracteres, RSS válido com `guid` e `pubDate`); feed real com 3 itens (hoje de manhã, 15/11 e 12/11 à noite); build e `astryx doctor` sem falhas.
- Publicado em 19/11/2026 ~10h40 junto com as fases 2e e 2f, com autorização do autor ("pode publicar tudo"): `/`, `/sobre/`, `dados.json` e `feed.xml` respondendo 200; no navegador, mapa com 7 pontos e imagens carregadas, histórico, link do RSS e fonte certa. Backup do site anterior em `backup-site/transito-antes-historico-mapa-2026-11-19.tgz`.
- Pendente: o autor escolher as redes e ligar o RSS (Buffer, IFTTT, Zapier ou robô próprio).

## Fase 2h — Coleta contínua e história para prever · **ligada em 19/11/2026**

- Pedido do autor: "pra fazer predições é preciso guardar história"; aprovou ligar a coleta 24 h e os itens de guardar história ("Sim, ligar tudo").
- Feito: `passagens` (cada veículo com horário), `historia.py` (chuva por hora e cópia diária do banco), `csv_por_hora` (dados abertos), períodos em blocos de 3 h, textos do painel e da página Sobre sem as janelas de pico, link do CSV no histórico. Coletor religado sem `--janelas`.
- Prova: 67/67 testes (passagens = contar, clima só horas passadas, CSV com soma e chuva, cópia usando só o host, corte em blocos de 3 h); primeira volta real às 15h29: clipes das duas câmeras com passagens iguais à contagem (39 e 58), 67 horas de clima gravadas, cópia `fluxo-2026-11-19.db` em `~/backup-transito` (fora de `public_html` e da pasta do site), painel publicado; site no ar com "Coletando agora", veredito verde, mapa com os pontos medidos em verde, links do RSS e do CSV; CSV respondendo 200 (`text/csv`). Backup do site anterior em `backup-site/transito-antes-coleta-24h-2026-11-19.tgz`.
- Pendente (autor): avisar a NitTrans; deixar o coletor rodando fora da sessão do Claude Code e o Windows sem suspender na tomada.
- Próximo: com ~4 semanas contínuas, perfil típico por dia da semana e hora e o desvio de hoje; com 2 a 3 meses, previsão da próxima hora (perfil + desvio + chuva).

## Fase 2i — Antes e depois, pontos críticos de sinistros e piloto de velocidade · **publicado em 19/11/2026**

- Pedido do autor: sequência 1 (antes e depois), 2 (sinistros) e 3 (velocidade), a partir da reflexão sobre o que um gestor quer.
- Feito:
  - `antes_depois.py` e `intervencoes.csv` (registro editável; mesmo tipo de dia e hora, 4 semanas antes e depois, sem chuva, mínimo de 12 horas comparáveis); seção "Antes e depois de mudanças na via", hoje vazia com explicação.
  - `sinistros.py`: PRF 2022–2026 em Niterói (960 sinistros, 26 mortos, 104 feridos graves; mais grave: BR-101 km 321, 6 mortos e 14 feridos graves; mais sinistros: km 322, 228) e ranking municipal da NitTrans transcrito (`dados-externos/nittrans_vias_sinistros.csv`, conferido pela soma das 30 linhas). Manchas no mapa e seção "Onde acontecem os sinistros", com as vias que têm câmera pública marcadas (Alameda São Boaventura, 2ª da cidade, com 2 câmeras sem contagem).
  - Velocidade relativa (`coletor.velocidade_relativa`, coluna `passagens.vel_rel`): alturas da caixa por segundo no segundo em volta do cruzamento; comparável entre horários na mesma câmera. Para km/h falta uma referência de campo (carro passando a velocidade conhecida, ou distância medida na rua).
  - Corrigido: `exportar.py` quebrava na linha de comando (função definida depois do bloco principal); teste de regressão que roda o script.
- Prova: 76/76 testes; build e `astryx doctor` sem falhas; conferido na pré-visualização e no ar (mapa com 7 câmeras e 32 trechos da PRF, seções novas, sem erro no console); primeira volta do coletor com velocidade gravada (55 e 29 passagens, de 0,5 a 6,3). Backup do site anterior em `backup-site/transito-antes-sinistros-2026-11-19.tgz`.

## Fase 2j — Detector maior, autoria e GitHub aberto · **feito em 19–20/11/2026**

- **Detector:** o coletor passou a rodar `--modelo yolo11s.pt --imgsz 960 --conf 0.10 --tracker rastreador_permissivo.yaml` (antes: `yolo11n`, 640 px, rastreador padrão). Escolha pela comparação contra a referência (`yolo11x` a 1280 px, outro detector, não contagem humana; 13 clipes noturnos, `validar.py comparar --contra referencia`):

  | Configuração | 000018 desce | 000018 sobe | 000026 sobe |
  |---|---|---|---|
  | yolo11n padrão | -57,8% | -9,9% | -36,8% |
  | yolo11n permissivo 960 | -15,5% | +2,8% | +18,8% |
  | yolo11s 960, rastreador padrão | -26,2% | -7,0% | +13,5% |
  | **yolo11s 960 permissivo (adotada)** | **+2,7%** | **+6,3%** | +57,9% |

  Na câmera principal (000018) é a melhor. Na 000026 todas as configurações sensíveis contam mais que a referência (82 "a mais"): ou duplicam veículos ou a referência perde veículos; só uma contagem humana decide.
- **Tempo:** intervalo entre clipes ~60 s na maioria das rodadas; cerca de 1 rodada em 4 perde um clipe (114–125 s), com a GPU dividida com o Ollama.
- **Série histórica:** o habitual passou a usar só clipes do mesmo detector (`montar_base` filtra pela configuração do clipe mais recente da câmera), e o CSV ganhou a coluna `deteccao`; sem isso, o detector mais sensível pareceria "acima do habitual". Consequência: o habitual recomeça do zero a partir de 19/11/2026 23h10.
- **Autoria:** página Sobre, FAQ (as duas cópias) e rodapé do painel citam Labs.fanara.com.br, a licença AGPL-3.0 e o repositório.
- **GitHub:** <https://github.com/estudio-max/transito-niteroi>, público, AGPL-3.0, commits com e-mail `noreply` do GitHub. Fora do repositório: banco, vídeos, modelos, log, backups, dados da PRF e os arquivos gerados a cada coleta.
- Achado: o `node_modules` do painel foi esvaziado no reinício da sessão; reinstalado com `npm ci`.

## Fase 2k — Itens de baixo custo da lista de melhorias · **publicado em 19/11/2026**

- Pedido do autor: "Implemente agora os itens de baixo custo da lista" (grupo "Fazer logo" do radar).
- Feito:
  - **Tendência** (`exportar.tendencia`, campo `tendencia` em `dados.json`): veículos por hora, os dois sentidos somados, nos últimos 15, 30 e 60 min, e a direção (últimos 15 contra os 45 anteriores: acima de +15% "subindo", abaixo de −15% "descendo"). Exige 10 min de vídeo nos últimos 15 e 20 min nos 45 anteriores. Usa só clipes do mesmo detector do clipe mais recente: logo depois da troca de 23h10 a janela misturava os dois e a 000026 saía "subindo" (1.432 contra 784 veículos/h) só pela troca. No painel, linha "Movimento" em cada cartão de "Agora, ponto a ponto".
  - **Versão só texto** (`exportar.texto_simples` → `texto.html`, sem JavaScript, `noindex`): veredito, cada ponto com o movimento, ocorrências. Gerada e enviada a cada coleta; link "Versão só texto" no topo do painel.
  - **Camadas no mapa:** controle nativo do Leaflet (`L.control.layers`) para mostrar ou esconder câmeras e sinistros; aberto no computador, recolhido num ícone quando o mapa tem menos de 500 px de largura (no celular cobria o mapa e o balão).
  - **Ocorrência no mapa:** câmera com ocorrência em andamento (último clipe da ocorrência a menos de 10 min do último clipe da coleta) ganha contorno amarelo; o preenchimento continua sendo a situação, porque o amarelo-escuro já significa "dentro do habitual". Balão e legenda dizem o mesmo em texto.
  - **Ver no mapa:** botão em cada ocorrência rola a página até o mapa, centraliza a câmera e abre o balão (religa a camada de câmeras se estiver desligada).
  - **Ranking de sinistros:** "Câmera contando" (Jansen de Melo) separado de "Câmera sem contagem" (Alameda São Boaventura, Professor João Brasil, Feliciano Sodré), com o número de câmeras.
- Prova: `ruff` limpo, 83/83 testes (tendência com troca de detector e mínimo de vídeo; texto escapa HTML e traz o essencial), cobertura total 75%; `oxlint`, build e `astryx doctor --built` sem falhas (3 avisos, os mesmos de antes). No navegador (pré-visualização local, dados reais): movimento nos dois cartões; "Ver no mapa" com clique real centraliza e abre o balão; contorno amarelo conferido com uma ocorrência simulada só no `dados.json` local (depois regenerado); controle aberto a 1280 px e recolhido a ~430 px, sem rolagem lateral; sem erro no console; `texto.html` completo.
- Publicado em 19/11/2026 ~23h39 com autorização do autor ("Sim, publicar"): coletor reiniciado com os mesmos argumentos (`yolo11s`, 960 px, rastreador permissivo) para carregar o exportador novo; painel enviado com `scp -r dist/.`. No ar: `/`, `/texto.html`, `/sobre/`, `dados.json` e `feed.xml` respondendo 200; `dados.json` publicado pelo coletor com `tendencia`; no navegador, movimento nos dois cartões, 3 botões "Ver no mapa", camadas Câmeras e Sinistros (PRF), ranking separado, sem rolagem lateral e sem erro do site no console. O contorno amarelo apareceu com uma ocorrência real: enguiço na Jansen x Mal. Deodoro desde 23h32. Backup do site anterior em `backup-site/transito-antes-melhorias-2026-11-19.tgz`.

## Radar: ideias a amadurecer (19/11/2026)

### Lista de melhorias de visualização recebida em 20/11/2026 (avaliação)

- **Fazer logo (baixo custo, sem conflito com as regras do projeto)** · feito na fase 2k: tendência dos últimos 15/30/60 minutos por câmera (subindo, estável, descendo), que dá referência sem precisar do habitual; camadas liga/desliga no mapa (trânsito agora × sinistros históricos); ponto da câmera em amarelo quando há ocorrência aberta; clicar na ocorrência centraliza o mapa; versão só texto para internet ruim; marcar no ranking de sinistros "contando agora" (Jansen) separado de "câmera sem contagem".
- **A amadurecer:** contagem total por tipo no "agora" (o detector já conta carro, moto, ônibus e caminhão; a lista supôs que só ônibus, o que não procede); página para incorporar em outros sites (`<iframe>`); filtro de sinistros por gravidade e por tipo de acidente (a base da PRF tem `tipo_acidente` e vítimas por boletim; motos exigiria a tabela de veículos envolvidos).
- **Não recomendado agora:** limiar fixo de veículos por 15 minutos para "livre/retenção" (arbitrário, cada câmera enxerga um trecho diferente; é o "espaço" que falta calibrar); foto da ocorrência, mesmo desfocada (quebra a regra de não guardar imagens e exige desfoque confiável de rostos e placas); botões de confirmação pública (o site é estático, sem servidor para receber votos, e seria fácil de manipular; alternativa: link para abrir uma issue no GitHub); prévia do vídeo da NitTrans no mapa (republicar o vídeo dela no site exige autorização; um link para o app da NitTrans resolve).


### Contagem só faz sentido com tempo e espaço (pedido do autor, 19/11/2026)

- **Tempo:** hoje `situacao` e `periodos` comparam a ocupação com *toda* a história da câmera, sem separar hora do dia nem dia da semana. Consequência: o pico da manhã tende a sair "pesado" e a madrugada "livre" sempre; não diz se *aquele horário* está acima do habitual. A comparação certa é com o mesmo dia da semana e a mesma hora (já usada em `antes_depois.py`), e só com base suficiente (hoje há 3 dias de coleta: mostrar "sem base" até haver ~4 semanas).
- **Espaço:** veículos por hora não dizem se há excesso sem a capacidade do trecho. Falta densidade (veículos por faixa e por comprimento visível) e a capacidade da via (número de faixas, semáforo). A ocupação (veículos por quadro) já é uma densidade da área da imagem, mas a área visível difere entre câmeras; calibrar o comprimento do trecho por câmera com uma medida de campo, a mesma que serve para km/h.
- **Feito em 19/11/2026 (tempo):** o nível passou a comparar com o mesmo tipo de dia (útil ou fim de semana) e a mesma hora da mesma câmera (`exportar.montar_base`, `_nivel_habitual`), exigindo 30 clipes em pelo menos 3 dias diferentes (`MIN_BASE_HORA`, `MIN_DIAS_BASE`); a hora usada é a da medição, não a do relógio. Rótulos: abaixo (até o percentil 15), dentro, acima do habitual (além do 85). Os ids internos continuam `livre`/`moderado`/`pesado`. Sem base, o topo fica cinza (`sem_base`) e diz que ainda não dá para comparar; com 3 dias de coleta quase tudo cai aí até completar umas 4 semanas. O "formato do dia" (24 horas) segue comparando as horas entre si, com legenda própria.
- **Pendente (espaço):** densidade por faixa e por comprimento visível, e a capacidade da via; exige calibração por câmera.

Nada aqui foi descartado nem decidido. São direções registradas para amadurecer; cada uma vira fase quando houver dado, parceiro ou decisão do autor.

### Caminhos de relação com a prefeitura (avaliação de 19/11/2026)

- **A. Melhorar o que a prefeitura já tem:** a NitTrans publica sinistros (mapas, mapas de calor, ranking de vias, mortalidade) só como imagem, sem gravidade nem download; tem câmeras de contagem próprias sem números publicados. Proposta: versão aberta e por gravidade desses dados (no estilo do Infosiga-SP), via Lei de Acesso à Informação ou cooperação técnica.
- **B. Indicadores complementares:** o que ninguém publica: contagem contínua e independente, antes e depois de intervenções, regularidade dos ônibus, tempo até liberar a pista, câmeras fora do ar, velocidade fora do pico.
- **Leitura atual:** os dois, com papéis diferentes: B é o motor (só este projeto faz), A é a porta de entrada e o multiplicador. Ponto de encontro: comparar a nossa contagem com a das câmeras de contagem da NitTrans onde coincidirem, o que validaria a contagem sem contagem manual.
- Pedidos via Lei de Acesso à Informação a amadurecer: NitTrans (base de sinistros com local e gravidade 2020–2026; lista, posição e contagens das câmeras de contagem; lista das câmeras públicas com coordenadas); Defesa Civil (série dos 46 pluviômetros; dados do radar).
- Avisar a NitTrans, em particular, do valor de 2025 da tabela de mortalidade (46,7 por 100 mil, contra 10 a 17 nos outros anos).

### Plano Niterói Mais Resiliente 2021–2024 (Defesa Civil e Geotecnia), lacunas e oportunidades

- **Radar meteorológico com "interface para compartilhamento de dados com o público, demais municípios e órgãos" (meta de dez/2022, R$ 10,97 mi):** há imagens no site e no aplicativo AlertaDCNIT, mas não achamos dados abertos nem API. Oportunidade: ser o primeiro consumidor dessa interface (chuva por bairro no lugar do Open-Meteo) e pedir o acesso citando a própria meta do plano.
- **Projeto PDPA/UFF "Monitoramento remoto em tempo real de áreas alagadas em vias públicas com intervenção viária inteligente" (R$ 298 mil, dez/2023):** é o projeto mais próximo do nosso (vias, tempo real, trânsito). Não achamos resultado publicado. Oportunidade: acrescentar "via alagada" aos tipos que o modelo de visão reconhece nas câmeras, e procurar a equipe da UFF.
- **"Niterói Organizada e Segura: estudo do impacto das chuvas" (R$ 362 mil):** já guardamos chuva por hora e fluxo por hora; o impacto da chuva no trânsito da saída da Ponte é um indicador que podemos produzir e oferecer.
- **Centro de Estudos e Pesquisas em Prevenção de Desastres (UFF) e Pluv-Web (Instituto de Computação da UFF):** parceiros naturais; há artigo da UFF sobre monitoramento de chuva e impactos urbanos em tempo real (SIBGRAPI).
- **Rede de qualidade do ar (R$ 1,5 mi):** contagem por tipo de veículo é o dado que falta para estimar a contribuição do trânsito nas medições de ar.
- **Planos de contingência e simulados:** o plano não fala de mobilidade em emergência (rotas de saída, Ponte, interdições). A situação das vias em tempo real pode servir ao Centro de Monitoramento e Operações em dia de chuva forte.
- **2.500 voluntários dos NUDECs e o aplicativo AlertaDCNIT:** canal de alerta já existente para o feed (via alagada, ocorrência) e, a amadurecer, voluntários conferindo amostras da contagem e dos incidentes.
- **Lacunas do plano:** só entregas, prazos e valores, sem indicadores de resultado (tempo de resposta, vias alagadas por evento, população alertada); trânsito ausente do escopo, salvo o projeto das vias alagadas; vigência 2021–2024 encerrada, sem balanço público encontrado; nenhuma menção a integração com a NitTrans.

### Outras ideias já levantadas

Mapa de calor (quando as 7 câmeras contarem), trechos de rua coloridos e pontos críticos por minutos pesados; publicação automática em redes (ligar o RSS); velocidade em km/h (falta referência de campo); câmeras da Região Oceânica (TransOceânica, túnel Charitas–Cafubá); ônibus contra a programação (GTFS); boletim semanal; previsão da próxima hora (após 2 a 3 meses de coleta).

## Fase 3 — Coleta e diagnóstico · pendente

- 2 a 4 semanas de coleta nos picos; ampliar para as 7 câmeras do recorte.
- Contagem por movimento no cruzamento (RF6) e tempos de semáforo (RF7).
- Velocidades por API para trechos sem câmera (RF8).
- Entregável: diagrama espaço-tempo e diagrama fundamental (fluxo × ocupação) mostrando onde e quando a fila nasce.
- Depende de: fase 2.

## Fase 4 — Gêmeo digital · pendente

- Rede do OpenStreetMap no SUMO, demanda calibrada com as contagens, validação em dias não usados na calibração.
- Depende de: fase 3.

## Fase 5 — Intervenções e relatório · pendente

- Agente propõe intervenções, roda no simulador, ordena por ganho com incerteza (RM4).
- Relatório para a NitTrans; possível artigo.
- Depende de: fase 4.

## Fase 6 — Produto · futuro

- Só se as fases 2 a 5 se sustentarem. Interface (Astryx), operação contínua, outras cidades.
