// Perguntas da página Sobre. O mesmo texto está no JSON-LD de sobre/index.html
// (buscadores leem o HTML sem executar JavaScript): mudou aqui, mude lá.
export const FAQ = [
  {
    pergunta: 'O que é o Fluxo Niterói?',
    resposta:
      'É um estudo cívico que conta automaticamente os veículos que passam pela Av. Jansen de Melo, na saída da Ponte Rio–Niterói, usando os vídeos públicos das câmeras da NitTrans. O objetivo é localizar o gargalo do trecho com dados e testar correções em simulação antes de propô-las à prefeitura.',
  },
  {
    pergunta: 'De onde vêm os dados?',
    resposta:
      'Das câmeras de videomonitoramento que a NitTrans publica na internet. A cada minuto o sistema baixa o último clipe de cada câmera, conta os veículos que cruzam uma linha fixa na imagem e guarda apenas os números.',
  },
  {
    pergunta: 'Os números já são confiáveis?',
    resposta:
      'Ainda não. A contagem automática está sendo conferida contra contagem manual às cegas, por câmera e por condição de luz e trânsito. Até essa validação terminar, os números servem para acompanhar o estudo, não como resultado.',
  },
  {
    pergunta: 'O sistema guarda imagens ou placas?',
    resposta:
      'Não. O vídeo é apagado logo depois da contagem e só os números ficam no banco. O sistema não lê placas nem identifica pessoas.',
  },
  {
    pergunta: 'Por que às vezes o painel diz que a coleta está pausada?',
    resposta:
      'A coleta roda em um notebook pessoal. Quando ele está desligado ou ocupado, o painel mostra o horário do último clipe analisado e os gráficos ficam com um intervalo sem dados.',
  },
  {
    pergunta: 'O projeto tem relação com a prefeitura?',
    resposta:
      'Não. É um estudo independente do Labs.fanara.com.br, de código aberto (licença AGPL-3.0). A intenção é levar os resultados validados à NitTrans e à prefeitura como contribuição.',
  },
];
