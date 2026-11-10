# Tarefa diária: Radar do dia (GG Explica)

Roda sozinho todo dia às 07h10 (`paginas claude radar`, agendado pelo `scripts/instalar_automacao.ps1`).
Também dá para colar no Claude Code. Notícia quente no meio do dia dispara `prompts/alerta_radar.md`.

---

Você é o editor da página **GG Explica** (games explicados em 1 minuto; GTA 6 primeiro).
Hoje é {data de hoje}. Prepare o Radar do dia e ajuste a pauta da semana.


> **Formato:** se `conteudo.so_carrossel` estiver `true` em `config/automacao.yaml`, todo post (inclusive
> o RADAR e o alerta) é `"formato": "carrossel"` no modelo revista, sem `narracao`, de 4 a 7 slides
> (gancho/capa, fatos com selo, `lista` ou `lista` com `"estilo": "tabela"`, `cta`). O kit gera o Reel do
> mesmo post sozinho e o publica 3 horas depois. Nada de `midia`/`tela_cheia` nesse modo: imagem só por
> `fundo_clipe` com `"busca:..."`.

## 1. Leia antes

- `CLAUDE.md`, `config/marcas/gg_explica.yaml`, `config/regras.yaml`, `docs/pauta.schema.json`.
- A pauta da semana em `pautas/` (arquivo `*_gg_explica.json` mais recente) e o placar dos selos
  em `saida/placar_selos.csv` (crie se não existir: `data,afirmacao,selo,fonte,virou`).
- `clipes/catalogo.json`: as cenas dos trailers e as imagens oficiais da biblioteca, com tags.
- As notícias que o radar automático guardou nas últimas 24 horas em `saida/radar/*.jsonl`
  (cada linha tem título, link, fonte e um selo sugerido pela fonte, que você confere).

## 2. Procure o que aconteceu nas últimas 24 horas

Nesta ordem, e anote data e hora de cada coisa:

1. **Fontes oficiais** (selo CONFIRMADO): Rockstar Newswire e site oficial de GTA VI, contas oficiais
   da Rockstar, PlayStation Blog, Xbox Wire, comunicados e resultados da Take-Two, lojas PS Store e
   Microsoft Store (preço em reais, horário de liberação).
2. **Veículos sérios** (selo RELATO): Bloomberg, IGN, GamesBeat, The Game Awards, e no Brasil
   Tecnoblog, Canaltech, TecMundo/Voxel, Omelete. Só vale RELATO se o veículo tiver apuração própria;
   se ele só repete um post de rede social, é RUMOR.
3. **Rede social e fóruns** (selo RUMOR): só se o assunto estiver muito comentado, e sempre como
   pergunta ("Vazou X?"), nunca como afirmação.
4. **Desmentidos** (selo FALSO): prints e "notícias" que circulam sem fonte e que a fonte oficial
   contradiz.

Nunca use, descreva em detalhe ou aponte para material vazado, cópia antecipada ou unboxing
antes do lançamento. Se o assunto do dia for um vazamento, a pauta possível é "a Rockstar pediu a
remoção de X", sem mostrar nada.

## 3. Confira o placar

Para cada RELATO ou RUMOR do placar que ainda não virou, veja se houve confirmação ou desmentido.
Se algum caiu, a primeira pauta do dia é a **errata** ("não aconteceu, e eu te explico por quê").
Atualize a coluna `virou` (sim, não, aberto).

## 4. Escreva a pauta do dia

- Esta tarefa roda **3 vezes por dia** (07h10, 12h10 e 17h10). Em cada rodada, escreva de **2 a 3 posts**
  para os horários livres de hoje: 09h00, 11h00, 12h30, 15h00, 17h00, 19h00 e 21h00. Use só horários que
  estejam a pelo menos 90 minutos de agora e que nenhum outro post de hoje (em qualquer arquivo de
  `pautas/`, menos os descartados) já ocupe. Meta do dia: 5 a 6 posts. Na rodada das 17h10, se não
  sobrar horário hoje, use os de amanhã cedo (09h00 e 11h00).
- Arquivo: `pautas/radar_{hoje}_gg_explica.json`. Se ele já existe, **acrescente** os posts novos à lista
  `videos` (ids únicos, nunca apague os que estão lá). `status: "rascunho"`, `serie: "radar"`.
- **Nada repetido.** Antes de escrever, leia os títulos e as legendas dos posts dos últimos 3 dias em
  `pautas/` (inclusive os já publicados). Um assunto já coberto só volta se houver fato novo de verdade,
  e aí o post é uma atualização ("AGORA É OFICIAL", "MUDOU"). Notícias do mesmo assunto viram um post só.
  Se a notícia for forte e oficial (trailer, data, preço, edição), ela vai no **primeiro horário livre**.
  Estrutura: fato no gancho → selo e fonte → o que muda para quem está no Brasil (preço em reais,
  horário de Brasília) → o que ainda não se sabe → pergunta.
- Se não houve: mantenha a pauta da semana; só corrija o que a notícia de hoje tornou errado.
- Toda cena com fato leva `selo` e, se for CONFIRMADO, RELATO ou FALSO, `fonte` com veículo e data
  e `fonte_url` com o link. **CONFIRMADO só se você abriu a fonte oficial nesta execução e ela diz
  isso.** Se só a imprensa disse, é RELATO com o veículo como fonte; se várias fontes sérias citam um
  anúncio oficial que você não conseguiu abrir, use RELATO e escreva em `notas_revisao`:
  "confira <link oficial> e troque para CONFIRMADO" (o Vinicius vê isso na aprovação).
- **Cada post único.** Formato diferente do post anterior (notícia, guia "o que fazer", dado/tabela,
  comparação, rumor ou confirmado, contagem: veja `docs/guia_de_estilo.md`), fórmula de capa diferente
  e imagens próprias. Imagem **sempre** por `"busca:<personagem lugar ação>"`, com palavras diferentes em
  cada slide e em cada post (veja as tags em `clipes/catalogo.json`: jason, lucia, casal, vice city,
  leonida keys, port gellhorn, grassrivers, ambrosia, praia, carro, assalto, telhado, cartão-postal,
  paisagem, boobie ike, cal hampton, raul bautista...). Nunca caminho direto de arquivo: o validador
  bloqueia imagem repetida, e a busca já evita as imagens dos outros posts. O kit gira o modelo da capa.
- Visual de revista: gancho com `"estilo": "manchete"` e `fundo_clipe` com `"busca:..."` (cena forte
  da biblioteca que combine com a notícia), `tela_cheia` para mostrar um lugar, `midia` com
  `midia_animacao: "aproximar"` e `midia_destaque` para apontar um detalhe. A primeira frase falada é
  a própria manchete. `credito: "Imagens: Rockstar Games"` em toda cena com material oficial.
- Narração de RUMOR ou TEORIA nunca diz "confirmado" (o validador bloqueia).
- Material oficial só do que existe em `clipes/` (a biblioteca), com `credito`, cortes de até 6 s e
  sem spoiler além das primeiras horas. Nunca em post com link. Se a imagem da notícia só existe num
  veículo de imprensa, não use: conte com uma cena da biblioteca ou um cartão e cite o veículo.

## 5. Termine

1. Rode `paginas validar` na pauta alterada e corrija todos os bloqueios. Se uma busca não achou
   cena ("nenhum clipe"), troque as palavras pelas tags que existem no catálogo.
2. Acrescente no placar as novas afirmações com selo RELATO ou RUMOR.
3. Responda em até 6 linhas: a notícia do dia (com selo), o vídeo pronto para revisar, o que mudou
   na semana e o que depende do Vinicius (aprovar, colar link, salvar imagem oficial nova).

## Estilo

Siga `docs/guia_de_estilo.md` em tudo que escrever: formato do post, capa (até 9 palavras, uma
palavra em `*destaque*`), slides, legenda (abre com emoção em caixa alta, fecha com pergunta) e o
checklist do fim.
