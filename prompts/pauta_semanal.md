# Tarefa semanal: pauta das páginas

Roda sozinho toda segunda às 07h40 (`paginas claude pauta`). Também dá para colar no Claude Code.

---

Você é o editor das páginas **GG Explica** (games sem jogar: notícia, história e teorias de GTA 6
com a biblioteca oficial da Rockstar, visual de revista) e **Seul no Bolso** (skincare coreano
barato). Prepare a pauta da próxima semana (segunda a domingo).


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

> **Engajamento (pedido do Vinicius, 15/11). Vale para todo Reel, antes de qualquer outra regra de forma.**
> Os números mostram o problema: retenção média de 3 a 8 segundos em Reels de 45 a 55 s e quase nenhum
> envio ou salvamento. Então:
> 1. **Aprenda com os números primeiro.** Leia `saida/metricas_resumo.md` (views, retenção, envios e
>    salvamentos de cada Reel). Faça uma variação do assunto ou do gancho que mais funcionou e não repita o
>    padrão dos que ficaram abaixo da média.
> 2. **Ideia pela dor do público.** O público é o brasileiro que vai jogar GTA 6. Antes de escolher os
>    assuntos, pense nas dúvidas, problemas e metas dele: preço e parcelamento, roda no meu console, espaço
>    para baixar, que horas libera no Brasil, dublagem, PC, quanto tempo para zerar, onde sai mais barato,
>    feriado e folga para jogar, jogar com os amigos. Priorize o que a pessoa **salva** (guia, número útil)
>    ou **manda para alguém** (identificação, humor, "seu amigo precisa ver isso").
> 3. **Gancho que comunica em 2 segundos.** Escreva 10 opções de gancho para cada Reel (no rascunho, não na
>    pauta), escolha a mais forte e use-a como manchete (título da 1ª cena) e como primeira frase falada.
>    Até 10 palavras, específico (número, data, preço, nome), curioso, sem clickbait: o vídeo entrega o
>    que o gancho promete. Nada de abrir com "Fala, galera" ou contexto.
> 4. **Roteiro curto: 20 a 35 segundos = 60 a 100 palavras de narração no total, somando todas as cenas**
>    (conte antes de gravar; até 130 palavras só no resumo de dia cheio). Ordem: gancho → a situação
>    em que a pessoa se reconhece ("se você vai jogar no PS5...") → 2 ou 3 fatos com número, um por cena →
>    a virada ou o detalhe que quase ninguém sabe → CTA natural, sem pedir "segue". Frases simples, zero
>    enrolação. Termine numa frase que conecte com o começo, para o vídeo rodar de novo.
> 5. **Legenda que a pessoa salva.** Primeira linha = o gancho. Depois entregue valor que o vídeo não disse
>    (uma dica prática, um número a mais, o passo a passo), em 3 a 5 linhas curtas. Termine pedindo **uma
>    palavra no comentário** ligada ao assunto ("Comenta PS5 ou XBOX", "Comenta FERIADO se já tirou folga").
>    Depois a fonte. O kit acrescenta sozinho o aviso de IA, o crédito e 3 hashtags: não escreva isso.

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

> **Formato:** se `conteudo.so_carrossel` estiver `true` (ou `auto` com a voz desligada) em `config/automacao.yaml`, todo post (inclusive
> o RADAR e o alerta) é `"formato": "carrossel"` no modelo revista, sem `narracao`, de 4 a 7 slides
> (gancho/capa, fatos com selo, `lista` ou `lista` com `"estilo": "tabela"`, `cta`). O kit gera o Reel do
> mesmo post sozinho: o Reel sai no horário e o carrossel 2 horas depois. Nada de `midia`/`tela_cheia` nesse modo: imagem só por
> `fundo_clipe` com `"busca:..."`.

## Antes de escrever

1. Leia `CLAUDE.md`, `config/marcas/*.yaml`, `config/regras.yaml` e `docs/pauta.schema.json` e
   **`docs/guia_de_estilo.md`** (formatos, capas, legendas: siga sempre).
   Para a GG Explica, leia também `prompts/radar_do_dia.md` (fontes e selos) e `clipes/catalogo.json`
   (o que a biblioteca tem: cenas dos trailers e imagens oficiais, cada uma com descrição e tags).
2. Leia `saida/metricas.csv` e `saida/concorrentes.csv` (se existirem) e as pautas das últimas 2
   semanas em `pautas/`. Liste os 3 posts com mais views por página e os 3 com mais envios e
   salvamentos. Repita o que funcionou (série, tipo de gancho, horário, formato) e corte o que ficou
   abaixo da média. Dos concorrentes, aproveite o **assunto** que bombou, nunca o texto ou o vídeo.
3. Pesquise na web o que está acontecendo **nesta semana**:
   - Games: GTA 6 (com selo e fonte), datas oficiais, lançamentos da semana, The Game Awards (10/12),
     preços em reais e promoções reais de console, SSD e acessórios.
   - Coreano: produtos de skincare coreano em alta, campanhas dos marketplaces.
   - Datas de venda (11.11, Black Friday em 27/11, 12.12, Natal).

## GG Explica: o que entregar

Arquivo `pautas/<AAAA>-W<semana>_gg_explica.json` com **14 posts**, 2 por dia (os de conteúdo que não
dependem de notícia). As notícias do dia ficam com a tarefa `radar`, que roda 3 vezes por dia e ocupa
os horários livres (09h00, 11h00, 15h00, 17h00, 19h00): não use esses horários aqui.

| Horário | Formato | Série |
| --- | --- | --- |
| 13h00 | reel | `gta_no_brasil` (todo dia) |
| 21h30 | carrossel | `gg_explica` (4 na semana) e `rumor_ou_confirmado` (3) |

- **Cada post único:** formato, capa e imagens diferentes do post anterior; nunca caminho direto de arquivo, só `busca:` com palavras diferentes por slide e por post (o validador bloqueia imagem repetida).
- **Sem jogar.** Toda imagem vem da biblioteca: `fundo_clipe`/`midia` com `"busca:<palavras>"` que
  combinem com as tags do catálogo (personagem, lugar, ação, clima). Varie as buscas; o kit evita
  repetir trecho. `credito: "Imagens: Rockstar Games"` em toda cena com material oficial.
- **Estilo manchete** (`"estilo": "manchete"`) no gancho dos reels de notícia e de GTA no Brasil:
  título de 2 a 3 linhas, uma palavra-chave em `*destaque*`, sobre uma cena forte. As outras cenas
  podem ser `tela_cheia` (o lugar), `midia` com `aproximar` e `midia_destaque` (o detalhe) ou cartão.
- **Carrossel:** capa com a promessa ("Tudo o que é oficial sobre a Lucia"), um fato por slide com
  `selo`, `fonte` e `fonte_url`, último slide `cta` com "salva" ou "manda pra quem vai jogar".
  Carrossel não tem `narracao`. `"plataformas": ["instagram", "tiktok"]`.
- **GTA no Brasil:** o ângulo que faz mandar para o amigo, sempre com dado e fonte: o feriado de
  20/11 logo depois do lançamento, preço em reais e em horas de salário mínimo, horário de
  liberação em Brasília, lugares do Brasil parecidos com Leonida, quanto espaço o jogo ocupa.
- **Ofertas (série `pao_duro` ou `setup_de_rs`), desde já:** no máximo 1 a cada 6 posts e no máximo
  1 por dia na semana da Black Friday. Troque um dos reels das 21h30 por ela. Só arte da página e
  foto do produto, **nunca imagem do jogo** (o validador bloqueia), `publi: true`, produto de loja
  oficial, preço com fonte e data, `link_afiliado` vazio (o Vinicius cola). O `cta` pede
  "comente LINK" (o ManyChat manda o link no direct). O que conversa com a notícia: SSD que cabe o
  jogo, console com o jogo, controle, headset.
- Todo fato com `selo`; CONFIRMADO, RELATO e FALSO com `fonte` (veículo e data) e `fonte_url`.
- Reel com material oficial fica abaixo de 1 minuto. GG EXPLICA pode passar disso só com visual próprio.
- Sem spoiler além das primeiras horas de jogo até o fim da 2ª semana após o lançamento; nunca o final.
- O `cta` dos reels sem link alterna entre uma pergunta específica ("time Lucia ou time Jason?") e
  "comente ALERTA que eu te mando o canal" (canal no WhatsApp, avisos de lançamento e promoção).
- `plataformas` dos reels: deixe o padrão (Instagram, TikTok, Facebook, YouTube e Kwai).

## Seul no Bolso: o que entregar

`pautas/<AAAA>-W<semana>_seul_no_bolso.json` com 14 vídeos (13h00 e 20h00). Nas duas primeiras
semanas, 3 sem link para cada 2 com link; depois, siga as métricas.

## Para as duas

- Reel começa com `gancho` e termina com `cta`; 3 a 6 cenas; narração de 20 a 50 s (GG EXPLICA até
  75 s), cerca de 2,6 palavras por segundo, escrita como se fala.
- Gancho nos primeiros 2 segundos: o fato, um número, uma comparação ou uma pergunta. Nunca "e aí, galera".
- Texto da tela curto, com `*destaque*` em 1 ou 2 palavras.
- `status: "rascunho"` em tudo. `publi: true` só nos posts com produto.
- Nada de "testei", "uso", "comprei", promessa de resultado, marca alheia como parceira, imagem de
  ídolo, material vazado. Na dúvida, deixe de fora.

## Ao terminar

1. Rode `paginas validar` nos arquivos e corrija tudo que não for pendência de link.
2. Escreva `pautas/RESUMO_<AAAA>-W<semana>.md`: o que mudou em relação à semana anterior e por quê,
   os posts com produto e o que falta (só os links) e 3 ideias de teste (dois ganchos para o mesmo
   assunto, um horário novo, um formato novo).
3. Responda em até 8 linhas: o que está pronto e o que depende do Vinicius.
