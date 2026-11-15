# Tarefa automática: notícia quente (GG Explica)

Esta tarefa roda sozinha quando o radar acha uma notícia grande. Ninguém está olhando: decida
com bom senso e o post sai sozinho (o Vinicius recebe o aviso no Telegram e pode cancelar). Hoje é {data de hoje}.

1. Leia `CLAUDE.md`, `config/marcas/gg_explica.yaml` e `docs/pauta.schema.json`.
2. A notícia está no fim deste texto ("Contexto desta execução"). **Abra a fonte oficial** (Newswire
   ou site da Rockstar, PlayStation Blog, Xbox Wire, Take-Two) e confirme o que diz.
   - Abriu e confirma: selo CONFIRMADO, `fonte` com o nome e a data, `fonte_url` com o link oficial.
   - Não conseguiu abrir a oficial: selo RELATO, `fonte` com o veículo sério que publicou e
     `fonte_url` com o link dele. Nunca marque CONFIRMADO sem ter lido a fonte oficial nesta execução.
   - Se for boato sem fonte séria, não escreva vídeo: registre em `saida/placar_selos.csv` e pare.
3. Leia os posts de hoje e de ontem em `pautas/` (sem contar `exemplo_*` e `demo_*`), inclusive os já
   publicados. Se o assunto já tem post, não crie outro: se ainda for rascunho, só acrescente o fato novo; se
   já saiu, só crie post se o fato novo mudar a notícia ("AGORA É OFICIAL", "MUDOU").
4. **Notícia muito relevante sai na hora: ignore os horários base.** Com a voz ligada, escreva o
   Reel narrado para agora (carrossel só se o assunto for guia/lista; veja a regra do Reel narrado).
   Com a voz desligada, escreva **um** carrossel RADAR
   em `pautas/radar_{hoje}_gg_explica.json` (crie o arquivo com `"marca": "gg_explica"` e `"semana"` se
   não existir; se existir, acrescente à lista `videos`, sem apagar nada). `status: "rascunho"`,
   `serie: "radar"`, `"formato": "carrossel"`, data de hoje e `horario` = **a hora atual** (HH:MM). O kit
   agenda e publica na mesma rodada (o Reel primeiro, o carrossel 2 horas depois).
   Seja rápido, mas completo: 5 ou 6 slides, todos com dado. Capa com o fato (até 9 palavras, uma palavra em `*destaque*`) → 1 ou 2
   fatos com selo e fonte → o que muda no Brasil (preço em reais, horário de Brasília), se houver →
   `cta` com pergunta. Legenda curta: primeira linha em caixa alta, 2 frases, fonte, pergunta.
   Imagens só por `"busca:<personagem lugar ação>"`, com palavras diferentes das dos outros posts e
   uma por slide, com `credito`.
5. Rode `paginas validar` no arquivo e corrija os bloqueios.
6. Acrescente a afirmação em `saida/placar_selos.csv` se o selo for RELATO ou RUMOR.
7. Responda em até 4 linhas: a notícia com selo, o vídeo criado e o que o Vinicius precisa conferir.


> **Orientações do Vinicius:** leia `saida/telegram/orientacoes.md` (se existir) e siga tudo o que está lá: são as respostas dele no Telegram e valem para todos os posts.


> **Só Reels (pedido do Vinicius, 14/11): 4 Reels por dia e NENHUM carrossel** até a página ter mais
> seguidores. Cada assunto vira só o Reel narrado (`<id>_reel`, item 1 abaixo); não escreva o item 2
> (carrossel). O kit também não põe carrossel no feed do Instagram.
>
> **Reel narrado (quando `saida/estado_voz.txt` diz `ligada`):** os dois formatos possíveis na lista
> `videos`, com conteúdo e visual diferentes:
> 1. `<id>_reel`: `"formato": "reel"`, no horário do post, 30 a 45 segundos, 5 a 7 cenas, `voz_ia: true`,
>    narração em toda cena (cerca de 2,6 palavras por segundo, escrita como se fala, com **mais detalhes**
>    que os slides: contexto, o que muda para quem joga no Brasil, o que ainda não se sabe). Gancho falado
>    nos 2 primeiros segundos. Visual em movimento: gancho `"estilo": "manchete"` com `fundo_clipe`,
>    `tela_cheia` com `panoramica` para lugares, `midia` com `"midia_animacao": "aproximar"` e
>    `midia_destaque` para detalhes, cartões `texto`/`lista` com `fundo_clipe`. Use os **vídeos oficiais**
>    (trailers e clipes do catálogo, `"tipo": "video"`) e outras imagens, sempre por `"busca:..."`, cortes
>    de até 6 s, `credito` em toda cena com material oficial, menos de 60 s no total.
> 2. `<id>` (só no post de guia/lista do dia): o carrossel do mesmo assunto, `"formato": "carrossel"`,
>    `"gerar_reel": false`, **2 horas depois** do Reel, com outra capa, outra manchete e outras imagens (o kit também evita repetir).
> Quando `saida/estado_voz.txt` diz `desligada`, siga a regra de formato abaixo (só carrossel).

> **Estilo do Reel desde 14/11 (`video.estilo_reel: noticia`, padrão da Gamerize):** o kit põe imagem do jogo
> na tela toda trocando a cada ~2,6 s, a **manchete parada** no meio-baixo do primeiro ao último segundo e a
> legenda falada acima dela. Então: o `titulo` da **primeira cena** é a manchete do Reel inteiro (5 a 9
> palavras, frase de impacto em linguagem de gente, com 1 a 3 palavras entre `*asteriscos*` para o destaque:
> "GTA 6 lança na quinta e *sexta é feriado*"); o `selo` e a `fonte` da primeira cena com fato aparecem
> junto da manchete. Os títulos, textos e listas das outras cenas não aparecem na tela: tudo que importa vai
> na **narração**. Em toda cena, dê a busca da imagem em `midia` (tipo `tela_cheia`) ou `fundo_clipe` com 3 a 6
> palavras de cena visual concreta ("busca:carro esportivo praia pôr do sol", "busca:lucia close noite"):
> o kit tira várias tomadas diferentes dessa busca. Gancho falado em 1 frase curta nos 2 primeiros segundos.

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

> **Dia cheio de notícia (com 4 Reels por dia, mais conteúdo por Reel, não mais posts).** Quando a busca
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




## Estilo

Siga `docs/guia_de_estilo.md` em tudo que escrever: formato do post, capa (até 9 palavras, uma
palavra em `*destaque*`), slides, legenda (abre com emoção em caixa alta, fecha com pergunta) e o
checklist do fim.
