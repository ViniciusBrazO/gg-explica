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
   Reel narrado para agora e o carrossel para 2 horas depois (veja a regra do Reel narrado no fim).
   Com a voz desligada, escreva **um** carrossel RADAR
   em `pautas/radar_{hoje}_gg_explica.json` (crie o arquivo com `"marca": "gg_explica"` e `"semana"` se
   não existir; se existir, acrescente à lista `videos`, sem apagar nada). `status: "rascunho"`,
   `serie: "radar"`, `"formato": "carrossel"`, data de hoje e `horario` = **a hora atual** (HH:MM). O kit
   agenda e publica na mesma rodada (o Reel primeiro, o carrossel 2 horas depois).
   Seja rápido: 4 ou 5 slides. Capa com o fato (até 9 palavras, uma palavra em `*destaque*`) → 1 ou 2
   fatos com selo e fonte → o que muda no Brasil (preço em reais, horário de Brasília), se houver →
   `cta` com pergunta. Legenda curta: primeira linha em caixa alta, 2 frases, fonte, pergunta.
   Imagens só por `"busca:<personagem lugar ação>"`, com palavras diferentes das dos outros posts e
   uma por slide, com `credito`.
5. Rode `paginas validar` no arquivo e corrija os bloqueios.
6. Acrescente a afirmação em `saida/placar_selos.csv` se o selo for RELATO ou RUMOR.
7. Responda em até 4 linhas: a notícia com selo, o vídeo criado e o que o Vinicius precisa conferir.


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

> **Formato:** se `conteudo.so_carrossel` estiver `true` (ou `auto` com a voz desligada) em `config/automacao.yaml`, todo post (inclusive
> o RADAR e o alerta) é `"formato": "carrossel"` no modelo revista, sem `narracao`, de 4 a 7 slides
> (gancho/capa, fatos com selo, `lista` ou `lista` com `"estilo": "tabela"`, `cta`). O kit gera o Reel do
> mesmo post sozinho: o Reel sai no horário e o carrossel 2 horas depois. Nada de `midia`/`tela_cheia` nesse modo: imagem só por
> `fundo_clipe` com `"busca:..."`.




## Estilo

Siga `docs/guia_de_estilo.md` em tudo que escrever: formato do post, capa (até 9 palavras, uma
palavra em `*destaque*`), slides, legenda (abre com emoção em caixa alta, fecha com pergunta) e o
checklist do fim.
