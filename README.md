# Fluxo Niterói

Painel público e aberto do trânsito na saída da Ponte Rio–Niterói: conta veículos nas câmeras públicas da NitTrans, compara cada hora com o habitual do mesmo dia e horário, registra ocorrências lidas por um modelo de visão local e cruza tudo com os sinistros oficiais. Ao vivo em <https://transito.fanara.com.br/>.

Um projeto de **Labs.fanara.com.br** · licença [AGPL-3.0](LICENSE) · estudo cívico independente, sem vínculo com a Prefeitura de Niterói ou a NitTrans.

> **Dados preliminares.** A contagem automática ainda não foi conferida por amostragem e o classificador de ocorrências nunca viu um acidente real, só enguiços e veículos estacionados. Use como indicação, não como estatística oficial. Nenhum vídeo, imagem ou placa é guardado: só números e texto.

Documentação do projeto: `REQUIREMENTS.md` (o que faz e as regras), `ARCHITECTURE.md` (como está construído, com os limites conhecidos) e `STEPS.md` (fases, achados e ideias a amadurecer).

## Dados abertos

O site publica, a cada 5 minutos de coleta: `dados.json` (o que o painel mostra), `feed.xml` (RSS com um texto pronto por período e por ocorrência, para ligar a redes sociais), `texto.html` (versão só texto, sem JavaScript, para internet fraca e para incorporar em outros sites por `<iframe>`; o código está na página Sobre) e `dados-por-hora.csv` (uma linha por câmera e hora, com a chuva). Os sinistros vêm da PRF (dados abertos) e de uma tabela da NitTrans publicada só como imagem e transcrita em `dados-externos/`.

## Contribuir

Issues e pull requests são bem-vindos, em especial: referência de campo para virar velocidade relativa em km/h, conferência das posições das câmeras no mapa, testes da parte de vídeo e novas fontes de dados abertos. Antes de enviar, rode a seção "Verificações" abaixo.

## Montar o ambiente

O `pyproject.toml` instala o PyTorch com CUDA 12.6 (índice `pytorch-cu126`), para usar a placa de vídeo. Em máquina sem GPU NVIDIA ele roda na CPU, mais devagar.

Requer [uv](https://docs.astral.sh/uv/). O uv instala o Python certo sozinho.

```bash
uv sync
```

## Rodar

A classificação de incidentes usa um modelo de visão local, via [Ollama](https://ollama.com). Instale o Ollama e baixe o modelo uma vez (cerca de 3 GB):

```
ollama pull qwen3-vl:4b-instruct
```

```bash
uv run coletor.py --uma-vez
```

```bash
uv run coletor.py --intervalo 60
```

Com o Ollama fechado ou sem o modelo, a contagem funciona igual e os incidentes ficam gravados como `indeterminado`, fora do painel.

## Coleta contínua (desde 19/11/2026)

Para coletar o dia todo e manter o site, o feed, o CSV, a chuva por hora e a cópia diária do banco em dia, deixe rodando num terminal próprio (fora do Claude Code, que encerra o processo ao fechar a sessão):

```bash
uv run coletor.py --modelo yolo11s.pt --imgsz 960 --conf 0.10 --tracker rastreador_permissivo.yaml --publicar hostgator-fanara:transito.fanara.com.br
```

Essa é a configuração do detector adotada em 19/11/2026 (ver `STEPS.md`, fase 2j); o modelo é baixado sozinho na primeira execução. O notebook precisa ficar ligado na tomada e configurado para não suspender. As janelas de pico (`--janelas`) continuam disponíveis como plano B.

## Incidentes

Quando um veículo fica parado 20 s ou mais no mesmo ponto em dois clipes seguidos, o coletor manda quatro imagens (três quadros e uma ampliação do veículo) ao modelo local `qwen3-vl:4b-instruct`, que responde `acidente`, `enguico`, `estacionado`, `fila`, `bloqueio` ou `indeterminado`, com confiança e uma frase do que vê. Nada sai do notebook e as imagens não são guardadas; o banco recebe só o texto (tabelas `parados` e `incidentes` em `fluxo.db`). O painel mostra acidente, enguiço e bloqueio das últimas 24 h, só quando o incidente durou 3 clipes seguidos (cerca de 3 min), com aviso de classificação automática. Limiares no topo de `incidentes.py` e `MIN_CLIPES_PUBLICAR` em `exportar.py`. Use a variante `instruct`: a padrão `qwen3-vl:4b` "pensa" e esgota o limite de resposta sem devolver o JSON.

Não use `--passo 2`: o rastreador perde os veículos e a contagem desaba (medido em 12/11/2026, ver `STEPS.md`).

Os dados vão para `fluxo.db` (tabela `clipes`). Para adicionar câmera ou ajustar a linha de contagem, edite `CAMERAS` em `coletor.py`.

## Painel público

O painel está em https://transito.fanara.com.br/ (e a apresentação em `/sobre/`). Para coletar nas janelas de pico dos dias úteis e manter o site atualizado a cada 5 minutos, deixe rodando:

```bash
uv run coletor.py --publicar hostgator-fanara:transito.fanara.com.br
```

Fora das janelas ele espera sem processar nada. Sem `--janelas`, coleta o tempo todo; `--fim-de-semana` inclui sábado e domingo. Para parar, `Ctrl+C`. O notebook precisa estar ligado e sem suspender; sem o coletor, o site mostra "coleta pausada".

Depois de mudar o código do painel, compile, verifique e envie:

```bash
cd painel && npm run build && npx astryx doctor --built dist && scp -r dist/. hostgator-fanara:transito.fanara.com.br/
```

Para ver o painel localmente: `uv run exportar.py` e depois `npm run dev` dentro de `painel/`. Verificações do painel: `npm run lint` e `npm run build` (inclui a checagem de tipos).

## Validar a contagem (fase 2)

1. Guardar clipes para contar à mão (repita em dia, noite, pico e chuva):

```bash
uv run validar.py amostrar --condicao noite --clipes 3
```

2. Contar à mão, por tipo de veículo, no contador por teclado:

```bash
uv run validar.py contar
```

Abre uma janela com cada clipe ainda não contado. Aperte uma tecla no instante em que a base do veículo cruza o trecho amarelo:

| | carro | moto | ônibus | caminhão |
|---|---|---|---|---|
| **desce** (para baixo na imagem) | `1` | `2` | `3` | `4` |
| **sobe** (para cima na imagem) | `q` | `w` | `e` | `r` |

`espaço` pausa, `a` volta 3 s, `s` alterna meia velocidade, `z` desfaz o último toque, `Enter` grava o clipe e abre o próximo, `Esc` sai sem gravar o clipe atual. Carro inclui SUV, picape e van; ônibus inclui micro-ônibus; caminhão inclui VUC; bicicleta e quem passa fora do trecho amarelo não contam. O resultado vai para `validacao/manual.csv` (totais) e `validacao/eventos.csv` (instante de cada veículo). Não rode o passo 3 antes de contar: a contagem tem de ser às cegas.

3. Comparar com o automático, nas três configurações candidatas de uma vez:

```bash
uv run validar.py comparar --todas --diag
```

A tabela mostra, por câmera, condição, sentido e tipo, o erro de cada configuração e quantos veículos ela perdeu, contou a mais (fantasma ou o mesmo veículo duas vezes) ou classificou errado. O detalhe por clipe fica em `validacao/resultado_*.csv`, e a lista veículo a veículo, com o segundo do clipe, em `validacao/divergencias_*.csv`. Com `--diag`, cada clipe ganha um `_diag*.mp4` com caixas, IDs e contagem acumulada: abra no segundo indicado para ver a causa. Leva cerca de 1,5 minuto por clipe em CPU.

Para avaliar uma configuração só, troque `--todas` por opções do detector: `--modelo yolo11s.pt`, `--imgsz 960`, ou `--conf 0.10 --tracker rastreador_permissivo.yaml`. As mesmas opções existem no `coletor.py`.

Sem contagem manual, dá para comparar com um detector mais forte (`yolo11x` a 1280 px), que conta todos os clipes guardados:

```bash
uv run validar.py referencia
uv run validar.py comparar --todas --contra referencia
```

Isso diz quanto a contagem do coletor muda com mais modelo e resolução (onde ela perde veículos), não o erro real: a referência também erra. Alguns clipes contados à mão dizem se ela está perto da realidade.

4. Quando a configuração estiver decidida, apagar os vídeos já contados (os CSV ficam):

```bash
uv run validar.py limpar
```

## Verificações (rodar antes de qualquer commit)

```bash
uv run ruff format --check . && uv run ruff check . && uv run pytest
```

Só os testes, com cobertura:

```bash
uv run pytest
```

## Regras do projeto

- Código novo ou alterado vem com teste unitário; bug corrigido vira teste de regressão.
- Lint e formatação (`ruff`) limpos antes de commit.
- Nenhum vídeo, imagem, placa ou credencial entra no repositório nem no banco. Os clipes de `validacao/` são temporários e ignorados pelo Git; os CSV de validação são evidência e ficam.
- Nenhum número vai para relatório sem a validação descrita na fase 2 do `STEPS.md`.

Ainda não há tipagem estática, teste de integração da parte de vídeo nem CI; estão listados como débito em `ARCHITECTURE.md`.
