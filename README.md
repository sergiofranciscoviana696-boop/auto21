# Feed de stock Valpi Motor (temporario)

Gera automaticamente `valpimotor_stock.xml` a partir de https://www.valpimotor.pt/viaturas
e publica-o num URL fixo, para o auto.pt consumir enquanto nao ha integracao definitiva.

## Setup (uma vez)
1. Cria um repositorio **publico** no GitHub (ex.: `valpi-feed`).
2. Poe la dentro: `build_feed.py` e `.github/workflows/feed.yml`.
3. Faz um primeiro `python build_feed.py` local (ou corre o workflow a mao em Actions
   -> "Atualizar feed Valpi Motor" -> Run workflow) para criar o XML.
4. (Opcional, recomendado) Ativa GitHub Pages: Settings -> Pages -> Deploy from a branch
   -> branch `main`, pasta `/root`.

## URL do feed para dar ao Diogo
- Via **Pages** (melhor, serve como `application/xml`):
  `https://<utilizador>.github.io/valpi-feed/valpimotor_stock.xml`
- Via **raw** (funciona ja, sem Pages, mas serve como `text/plain`):
  `https://raw.githubusercontent.com/<utilizador>/valpi-feed/main/valpimotor_stock.xml`

## Como muda sozinho
O workflow corre no horario do cron (2x/dia por defeito), le a pagina, regenera o XML
e so faz commit se algo mudou. Nao precisas de tocar em nada.

## Avisos
- **Cache**: raw e Pages tem CDN (~5-10 min). Uma alteracao demora esse tempo a aparecer.
- **Cron adormece**: em repos publicos, o GitHub desativa workflows agendados apos 60 dias
  sem atividade — e commits feitos pelo proprio bot NAO contam. Solucao: de vez em quando
  faz um commit manual, OU usa um Personal Access Token para o push (commits com PAT contam).
- **Sincronizacao**: o feed e um snapshot. O que sai do XML tem de ser tratado pelo auto.pt
  como vendido/removido.
- **Estrutura**: se a pagina mudar de layout, o script pode extrair 0 viaturas — nesse caso
  ele falha de proposito (nao publica um XML vazio) e ves o erro em Actions.
