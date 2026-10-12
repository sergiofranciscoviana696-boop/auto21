# Feed de stock Valpi Motor -> catalogo Meta

Gera o feed do catalogo de veiculos da Meta (`meta_vehicles.xml`) para os anuncios de
catalogo da Valpi Motor e publica-o no GitHub Pages, de onde o Commerce Manager o vai
buscar por agendamento.

**O Meta e o destino principal.** E pelo `meta_vehicles.xml` que se avalia se uma
alteracao esta certa. O `valpimotor_stock.xml` (feito para o auto.pt) ja nao tem
consumidor; continua a ser gerado so por compatibilidade e pode ser ignorado.

## URL do feed (para o Commerce Manager)
`https://sergiofranciscoviana696-boop.github.io/auto21/meta_vehicles.xml`

No catalogo: origem de dados -> feed agendado com este URL, em modo de
**substituicao completa** (para viaturas vendidas sairem do catalogo).

## Fontes (cruzadas por `id`)
1. **Pagina** https://www.valpimotor.pt/viaturas -> marca, modelo, versao, ano,
   matricula, km, combustivel, transmissao, potencia, lugares, carrocaria, preco, estado.
2. **Feed AUTO21** https://auto21.pt/valpi/filesxml/facebook_loja_auto_v2.xml
   -> so galeria de imagens, cor exterior e transmissao de recurso. Os restantes campos
   desse feed nao sao fiaveis (carrocaria e combustivel vem como `OTHER`) e sao
   substituidos pelos da pagina.

## O que entra no feed Meta
- So viaturas **Disponiveis com preco**. Reservadas e sem preco ficam de fora.
- Imagens, por ordem de prioridade (so URLs do AUTO21; a miniatura da listagem nunca e usada):
  1. galeria do feed AUTO21 (ate 20 imagens);
  2. `imagens_extra.json` (id -> lista de URLs AUTO21; a 1a e a principal);
  3. capa em resolucao total reconstruida a partir da miniatura
     (`P<ts>.jpg` -> `N<ts>.jpg`), so se o URL responder com uma imagem.
  Sem nenhuma destas, a viatura fica fora e aparece no log.
- Carrocaria, combustivel, transmissao e tracao mapeados para os valores do Meta
  (`SUV`, `HATCHBACK`, `VAN`, `MINIBUS`, `PLUGIN_HYBRID`, `AWD`...), com correcoes por
  modelo (`MODEL_BODY_OVERRIDE`) e sub-modelos (`MODEL_SPLITS`, ex.: Transit Courier).
- Morada, codigo postal e coordenadas do stand (Gandra, Paredes) fixas em `DEALER`.
- Custom labels ja formatados (segmentacao e textos da capa):

| Label | Conteudo | Exemplo |
|---|---|---|
| `custom_label_0` | Segmento | passageiros / comercial |
| `custom_label_1` | Combustivel em PT | Hibrido Plug-in |
| `custom_label_2` | Km formatados | 108 000 km |
| `custom_label_3` | Preco formatado | 69.950 € |

## O que o log de cada corrida diz (Actions)
- `So com capa`: viaturas que nao estao na exportacao Facebook do AUTO21 e entraram
  so com 1 imagem. Correcao: ativar a exportacao no backoffice do AUTO21, ou por a
  galeria no `imagens_extra.json`.
- `Fora do feed Meta por falta de imagem valida`: ids sem nenhuma imagem utilizavel.
- `Combustivel fora da lista do template`: o `custom_label_1` sai com o texto do site.
- `Feed Meta NAO atualizado`: protecao ativada (ver Seguranca).

## Capa 1:1 gerada pelo builder -- EM CURSO (ficou a meio)
**Objetivo:** a 1a `<image>` de cada viatura passa a ser uma capa 1080x1080 com a barra
de preco; a galeria vem a seguir.

**Porque:** o modelo de catalogo do Gestor de Anuncios e aplicado de forma inconsistente
(o Advantage+ alterna entre a imagem com e sem modelo, e nao o aplica as imagens da
galeria). Com a barra dentro da propria imagem, a Meta nao tem nada para tirar.

**Layout** (`template/template.json`; Open Sans; canvas 1080x1080):
- Foto em cima, 1080x810 (cover, corte ao centro). Sem remocao de fundo.
- Barra #022F6E de 270 px em baixo, com linha de 6 px #5BC2E7 no topo (`template/bg.png`).
- Textos: titulo (Bold 52), combustivel (SemiBold 32, #5BC2E7), preco (ExtraBold 80,
  alinhado a direita), ano e km (Regular 28, #C9D6E8). Margem de seguranca de 60 px.
- O tamanho de letra reduz ate `min_size` em vez de cortar com reticencias.

**Feito**
- [x] `template/template.json` e `template/bg.png`
- [x] Referencia em Figma: ficheiro `VhwwxLjBLbecxg85LA5Wfq`, frames `2:2` (1:1) e `6:2` (4:5)
- [x] `custom_label_1` a `custom_label_3` ja trazem os textos que a capa usa

**Por fazer**
- [ ] `template/fonts` e hoje um ficheiro de texto, nao uma pasta: apagar e criar a pasta
      com `OpenSans-Bold.ttf`, `-SemiBold`, `-ExtraBold` e `-Regular`
      (Co Headline so se houver ficheiro com licenca)
- [ ] Titulo da capa: falta o `custom_label_4` (titulo cortado na ultima palavra
      inteira ate 33 caracteres), ou usar o mesmo corte so dentro do render
- [ ] Passar o render para o repo (`render.py`, Pillow) e chama-lo no `build_feed.py`:
      por viatura, descarregar a 1a foto, renderizar e gravar `capas/<id>-<hash>.jpg`
- [ ] `<hash>` a partir de preco + km + titulo + URL da foto. A Meta faz cache das
      imagens pelo URL; sem hash, uma mudanca de preco nao aparece
- [ ] No `meta_vehicles.xml`: capa como 1a `<image>`
      (`https://sergiofranciscoviana696-boop.github.io/auto21/capas/...`), galeria a seguir
- [ ] Apagar capas orfas (viaturas vendidas, hashes antigos)
- [ ] Workflow: instalar `Pillow` e fazer `git add capas/` alem dos XML
- [ ] Limpeza: `template.json` e `bg.png` na raiz sao copias de `template/`; apagar
- [ ] Depois de confirmar no Commerce Manager: **remover o modelo de catalogo no
      Gestor de Anuncios**, senao ficam duas barras sobrepostas

**Decisao em aberto:** capa + galeria (recomendado) ou so a capa (barra garantida em
100% dos posicionamentos, mas perde-se a galeria).

## Ficheiros
| Ficheiro | Funcao |
|---|---|
| `build_feed.py` | Gera os dois XML |
| `.github/workflows/feed.yml` | Corre as 06:00 e 14:00 UTC e faz commit se o stock mudou |
| `meta_vehicles.xml` | **Feed do catalogo Meta (principal)** |
| `valpimotor_stock.xml` | Legado (auto.pt), sem consumidor |
| `imagens_extra.json` | Opcional, ainda nao existe no repo; criar so quando for preciso |
| `template/` | Template da capa (em curso) |

## Correr
- Actions -> "Atualizar feed Valpi Motor" -> Run workflow, ou local:
  `pip install requests beautifulsoup4 && python build_feed.py`
- Testes com ficheiros locais: `python build_feed.py pagina.html meta.xml`

## Avisos
- **Duas fontes, horas diferentes**: um carro novo pode aparecer na pagina antes de estar
  no feed AUTO21 -> entra so com capa (ou fica fora) ate la estar.
- **Snapshot**: o que sai do XML sai do catalogo no fetch seguinte.
- **Cache** do Pages ~5-10 min; depois conta o agendamento do Commerce Manager.
- **Seguranca**: se a pagina der 0 viaturas o script falha e nao publica nada. Se o feed
  Meta novo ficar vazio ou com menos de 50% das viaturas do anterior, mantem o ficheiro
  antigo e escreve `::error::` no log, mas o workflow **termina a verde**: confirma o log
  se o numero de viaturas no catalogo nao mexer.
- **Cron adormecido** (repos publicos, 60 dias sem atividade no repo): os commits do bot
  contam, mas se o stock nao mudar durante 60 dias o GitHub desativa o agendamento.
