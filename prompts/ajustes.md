# Tarefa automática: refazer vídeos que o Vinicius pediu para ajustar

Hoje é {data de hoje}. Pelo Telegram, o Vinicius pediu ajustes em alguns vídeos.

1. Leia `CLAUDE.md` e `config/marcas/gg_explica.yaml`.
2. Em `pautas/*.json` (sem contar `exemplo_*` e `demo_*`), ache os vídeos em `rascunho` cujo
   `notas_revisao` tem uma linha começando com `AJUSTE PEDIDO:`.
3. Reescreva o vídeo seguindo o pedido. Mantenha as regras (selos, fontes, nada de frase proibida).
   Se o pedido for impossível dentro das regras, faça o mais próximo e explique em `notas_revisao`.
4. Troque a linha `AJUSTE PEDIDO: ...` por `Ajustado em {hoje}: <o que mudou>` (o kit só reenvia a
   prévia quando o marcador some).
5. Rode `paginas validar` no arquivo e corrija os bloqueios.
6. Responda em até 3 linhas o que mudou em cada vídeo.


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
> manchete" você procura em outra fonte com WebSearch/WebFetch. Se nenhuma matéria abrir, mas **2 ou mais
> veículos** trazem o mesmo fato nos títulos/resumos da busca, o Reel pode sair com selo RELATO e as duas
> fontes (sem inventar detalhe que não está nesses resumos). Com uma fonte só e sem texto, fica de fora.
>
> **Os 4 Reels do dia sempre saem (pedido do Vinicius, 15/11).** Se não houver notícia com fonte para os
> 4, complete com **Reels de assunto fixo**, que não dependem de notícia nova, no estilo que mais
> compartilha (o cotidiano do brasileiro): preço do jogo em horas de salário mínimo ou em parcelas (com
> fonte do preço e do salário), quantos dias faltam e a que horas libera no horário de Brasília, o feriado
> e a folga para jogar, quanto espaço liberar no console, curiosidades do trailer e do mapa com selo
> TEORIA, comparação com GTA V (números oficiais com fonte), "5 coisas que você não reparou". Fato
> estável também leva `fonte` e `fonte_url` (Rockstar, PlayStation Blog, Wikipedia, veículo). Nunca
> repita assunto de Reel dos últimos 7 dias.
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

> **Formato:** se `conteudo.so_carrossel` estiver `true` (ou `auto` com a voz desligada) em `config/automacao.yaml`, todo post (inclusive
> o RADAR e o alerta) é `"formato": "carrossel"` no modelo revista, sem `narracao`, de 6 a 8 slides
> (gancho/capa, fatos com selo, `lista` ou `lista` com `"estilo": "tabela"`, `cta`). O kit gera o Reel do
> mesmo post sozinho: o Reel sai no horário e o carrossel 2 horas depois. Nada de `midia`/`tela_cheia` nesse modo: imagem só por
> `fundo_clipe` com `"busca:..."`.

## Estilo

Siga `docs/guia_de_estilo.md` em tudo que escrever: formato do post, capa (até 9 palavras, uma
palavra em `*destaque*`), slides, legenda (abre com emoção em caixa alta, fecha com pergunta) e o
checklist do fim.
