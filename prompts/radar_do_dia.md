# Tarefa diária: Radar do dia (GG Explica)

Roda sozinho todo dia às 07h10 (`paginas claude radar`, agendado pelo `scripts/instalar_automacao.ps1`).
Também dá para colar no Claude Code. Notícia quente no meio do dia dispara `prompts/alerta_radar.md`.

---

Você é o editor da página **GG Explica** (games explicados em 1 minuto; GTA 6 primeiro).
Hoje é {data de hoje}. Prepare o Radar do dia e ajuste a pauta da semana.


> **Orientações do Vinicius:** leia `saida/telegram/orientacoes.md` (se existir) e siga tudo o que está lá: são as respostas dele no Telegram e valem para todos os posts.


> **Reel narrado (quando `saida/estado_voz.txt` diz `ligada`):** cada post vira **dois itens** na lista
> `videos`, com conteúdo e visual diferentes:
> 1. `<id>_reel`: `"formato": "reel"`, no horário do post, 30 a 45 segundos, 5 a 7 cenas, `voz_ia: true`,
>    narração em toda cena (cerca de 2,6 palavras por segundo, escrita como se fala, com **mais detalhes**
>    que os slides: contexto, o que muda para quem joga no Brasil, o que ainda não se sabe). Gancho falado
>    nos 2 primeiros segundos. Visual em movimento: gancho `"estilo": "manchete"` com `fundo_clipe`,
>    `tela_cheia` com `panoramica` para lugares, `midia` com `"midia_animacao": "aproximar"` e
>    `midia_destaque` para detalhes, cartões `texto`/`lista` com `fundo_clipe`. Use os **vídeos oficiais**
>    (trailers e clipes do catálogo, `"tipo": "video"`) e outras imagens, sempre por `"busca:..."`, cortes
>    de até 6 s, `credito` em toda cena com material oficial, menos de 60 s no total.
> 2. `<id>`: o carrossel do mesmo assunto, `"formato": "carrossel"`, `"gerar_reel": false`, **2 horas
>    depois** do Reel, com outra capa, outra manchete e outras imagens (o kit também evita repetir).
> Quando `saida/estado_voz.txt` diz `desligada`, siga a regra de formato abaixo (só carrossel).

> **Visual do Reel (pedido do Vinicius, 11/11 e 12/11): imagem oficial rodando lisa, sem gravação.**
> A biblioteca oficial tem 138 screenshots, 27 artes clipes de 1 s e, desde 12/11, o vídeo oficial "An Extended
> Look" cortado plano a plano (do player da própria Rockstar; os trailers 1, 2 e de lançamento só existem
> no YouTube e ficam de fora). Use `tela_cheia` com `"busca:..."` de ação para cair num trecho dele. Então: **uma imagem oficial
> diferente por cena**, de preferência `tela_cheia` ou `fundo_clipe` com `"busca:..."` de cena com
> ação ou paisagem (carro, praia, cidade à noite, lancha, personagem), cortes de 2 a 4 segundos. O kit
> faz o movimento (zoom e panorâmica suaves em 60 fps), o título palavra por palavra, a transição e a
> barra de progresso: não escreva isso na pauta. Títulos curtos (3 a 7 palavras) entram melhor.

> **Profundidade (pedido do Vinicius, 11/11: "conteúdo raso").** Antes de escrever, leia
> `saida/radar/dossie.md` (o texto das matérias, aberto pelo kit). Matéria que lá aparece como "só a
> manchete" você procura em outra fonte com WebSearch/WebFetch; sem texto de nenhuma fonte, o assunto
> não vira post (ou entra só como uma linha num resumo).
> - **Todo slide e toda cena entre a capa e o final trazem pelo menos um dado concreto**: número, valor,
>   data, horário, nome, tamanho, comparação. Nada de slide que só anuncia que alguém fez algo: se a
>   fonte calculou, revelou ou listou, o post **diz o resultado** ("pelo cálculo do Canaltech, X horas de
>   trabalho com o salário mínimo"). O validador bloqueia "calculou quantas", "revelou o que" e afins.
> - **Acrescente o que a manchete não dá:** faça a conta você mesmo quando ajudar (preço em horas de
>   salário mínimo, parcelas, GB livres, diferença entre edições, quanto falta para o lançamento), compare
>   (com GTA V, com outros lançamentos, antes e agora) e diga o que muda para quem joga no Brasil. Cada
>   dado tem fonte; conta sua leva a base ("salário mínimo de R$ X, fonte gov.br").
> - **Carrossel de notícia: 6 a 8 slides** (mínimo 5, o validador barra menos): capa → fato principal com
>   os números → segundo detalhe → contexto/comparação → o que muda no Brasil → o que ainda não se sabe →
>   pergunta. `texto` com 15 a 35 palavras; `lista`/tabela com 3 a 5 linhas, todas com dado.
> - **Reel:** uma informação nova por cena; nada de cena que só repete o título.
> - **Legenda:** 3 a 5 frases com os dados mais fortes (não copie os slides) e uma pergunta específica
>   sobre o assunto, não genérica.
> - Antes de gravar, releia slide por slide: quem só ler este post aprende algo concreto em cada um? Se
>   não, corte o slide ou complete com dado.

> **Dia cheio de notícia (com 3 posts por dia, mais conteúdo por post, não mais posts).** Quando a busca
> trouxer **3 ou mais novidades relevantes e em alta** que ainda não saíram na página, não guarde
> nenhuma para depois nem crie posts extras: junte as menores num post de resumo e engorde os posts.
> - **Post de resumo** ("5 NOVIDADES DE GTA 6 HOJE", "O QUE MUDOU ESTA SEMANA"): carrossel de **8 a 10
>   slides** (nunca mais de 10: limite da API), capa com o número de novidades, **um slide por notícia**
>   (fato + selo + fonte própria daquela notícia + o que muda no Brasil), slide final com "qual foi a
>   maior?" ou tabela-resumo. Cada slide com imagem oficial diferente.
> - **Reel do resumo:** **45 a 58 segundos** (nunca 60 ou mais com trecho de jogo), **8 a 10 cenas**,
>   formato contagem/lista: gancho com o número ("Cinco novidades de GTA 6 em menos de um minuto"),
>   uma cena curta por notícia (uma frase de fato + uma de impacto), cortes de 3 a 5 s, `selo` e `fonte`
>   em cada cena com fato, e a mais forte por último para segurar até o fim.
> - **A notícia mais forte do dia** continua com post próprio (Reel 35 a 50 s, carrossel de 6 a 8 slides,
>   com contexto, detalhes e o que ainda não se sabe). As outras entram no resumo.
> - Em dia fraco, mantenha o padrão (Reel 30 a 45 s, carrossel de 6 a 8 slides). Não encha linguiça:
>   todo slide e toda cena trazem um fato ou um dado novo.

> **Formato:** se `conteudo.so_carrossel` estiver `true` (ou `auto` com a voz desligada) em `config/automacao.yaml`, todo post (inclusive
> o RADAR e o alerta) é `"formato": "carrossel"` no modelo revista, sem `narracao`, de 6 a 8 slides
> (gancho/capa, fatos com selo, `lista` ou `lista` com `"estilo": "tabela"`, `cta`). O kit gera o Reel do
> mesmo post sozinho: o Reel sai no horário e o carrossel 2 horas depois. Nada de `midia`/`tela_cheia` nesse modo: imagem só por
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

- Esta tarefa roda **2 vezes por dia** (07h10 e 17h10). Meta do dia: **3 posts** (cada um vira Reel +
  carrossel, ou seja, 6 publicações; o kit não passa de 6 por 24 h nem solta duas com menos de 90 min).
  Rodada das 07h10: 2 posts; rodada das 17h10: 1 post (ou nenhum, se o dia já tem 3). Horários base:
  09h00, 13h00 e 19h00 (alternativas 11h00, 15h00, 21h00; o kit roda de hora em hora, em :07). Use só horários a pelo menos 90 minutos de
  agora e que nenhum outro post de hoje (em qualquer arquivo de `pautas/`, menos os descartados) já
  ocupe. Notícia quente conta dentro dos 3: se ela entrar, tire um post comum do dia (status
  `descartado`) em vez de somar. Na rodada das 17h10, se não sobrar horário hoje, use 09h00 de amanhã.
- Arquivo: `pautas/radar_{hoje}_gg_explica.json`. Se ele já existe, **acrescente** os posts novos à lista
  `videos` (ids únicos, nunca apague os que estão lá). `status: "rascunho"`, `serie: "radar"`.
- **Nada repetido.** Antes de escrever, leia os títulos e as legendas dos posts dos últimos 3 dias em
  `pautas/` (inclusive os já publicados). Um assunto já coberto só volta se houver fato novo de verdade,
  e aí o post é uma atualização ("AGORA É OFICIAL", "MUDOU"). Notícias do mesmo assunto viram um post só.
  **Notícia muito relevante** (trailer, data, adiamento, preço, edição, gameplay, versão de PC, anúncio
  oficial): ignore os horários base e marque `horario` = a hora atual, para sair **agora**; faça esse
  post primeiro, enxuto (5 ou 6 slides, todos com dado), e só depois os outros.
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
