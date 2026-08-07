# Feed de stock Valpi Motor (temporario)

Gera `valpimotor_stock.xml` cruzando DUAS fontes por `id` e publica-o num URL fixo
para o auto.pt consumir enquanto nao ha integracao definitiva:

1. **Pagina** https://www.valpimotor.pt/viaturas  -> campos estruturados
   (potencia, lugares, carrocaria, combustivel correto, preco, matricula...).
2. **Feed do Meta** https://auto21.pt/valpi/filesxml/facebook_loja_auto_v2.xml
   -> galeria completa de imagens + cor exterior.

Cada viatura fica com: capa (`<cover_image>`) + galeria (`<images>`) + cor, alem
dos campos estruturados. **So entram viaturas com imagens completas.**

## Imagens em falta -> imagens_extra.json
O feed do Meta nao tem todos os carros (faltam-lhe os mais recentes: Audi A6, Cupra,
BMW X1, os BMW 320 e/e, os Mercedes A250/C300, Peugeot 508 SW, etc.). Esses so existem
na pagina, sem galeria automatica, por isso ficam DE FORA ate teres as imagens no
`imagens_extra.json` (id -> lista de URLs; a 1a e a capa).

Em cada corrida o `build_feed.py` imprime a lista dos ids que continuam sem galeria —
essa e a verdade do momento. O ficheiro ja vem com esses ids pre-listados para
preencheres. Um id que esteja no mapa manual tem prioridade sobre o Meta (util para
corrigir fotos mas).

## Setup (uma vez)
1. Repositorio publico. Poe la: `build_feed.py`, `imagens_extra.json` e
   `.github/workflows/feed.yml`.
2. Corre o workflow (Actions -> Run workflow) ou `python build_feed.py` local.
3. (Recomendado) Settings -> Pages -> Deploy from a branch -> `main` / `(root)`.

## URL do feed para o Diogo
- Pages (serve como application/xml):
  `https://<user>.github.io/<repo>/valpimotor_stock.xml`
- raw (funciona ja, serve como text/plain):
  `https://raw.githubusercontent.com/<user>/<repo>/main/valpimotor_stock.xml`

## Avisos
- **Rollout**: ao passar para esta versao com o mapa vazio, os ~19 carros que so
  existem na pagina saem do feed ate lhes pores imagens. Os restantes ganham galeria
  completa (em vez da miniatura unica). Preenche os que interessam antes de anunciar.
- **Duas fontes, horas diferentes**: um carro novo pode aparecer na pagina antes de
  estar no Meta -> fica sem galeria (logo, fora) ate o Meta o apanhar, ou poes no mapa.
- **Cache** raw/Pages ~5-10 min. **Sincronizacao**: o feed e snapshot; o que sai tem
  de ser tratado pelo auto.pt como vendido/removido.
- **Seguranca**: se a pagina der 0 viaturas, ou se nenhuma tiver galeria, o script
  FALHA de proposito e nao publica um XML vazio (ves o erro em Actions).
- **Cron adormecido** (repos publicos, 60 dias sem atividade): commit manual de vez em
  quando, ou push com Personal Access Token.
