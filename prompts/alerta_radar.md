# Tarefa automática: notícia quente (GG Explica)

Esta tarefa roda sozinha quando o radar acha uma notícia grande. Ninguém está olhando: decida
com bom senso e deixe tudo pronto para o Vinicius aprovar pelo celular. Hoje é {data de hoje}.

1. Leia `CLAUDE.md`, `config/marcas/gg_explica.yaml` e `docs/pauta.schema.json`.
2. A notícia está no fim deste texto ("Contexto desta execução"). **Abra a fonte oficial** (Newswire
   ou site da Rockstar, PlayStation Blog, Xbox Wire, Take-Two) e confirme o que diz.
   - Abriu e confirma: selo CONFIRMADO, `fonte` com o nome e a data, `fonte_url` com o link oficial.
   - Não conseguiu abrir a oficial: selo RELATO, `fonte` com o veículo sério que publicou e
     `fonte_url` com o link dele. Nunca marque CONFIRMADO sem ter lido a fonte oficial nesta execução.
   - Se for boato sem fonte séria, não escreva vídeo: registre em `saida/placar_selos.csv` e pare.
3. Confira se o assunto já está em alguma pauta de `pautas/` (sem contar `exemplo_*` e `demo_*`).
   Se já estiver, só corrija o que mudou.
4. Escreva um vídeo RADAR (20 a 35 s) em `pautas/radar_{hoje}_gg_explica.json` (crie o arquivo com
   `"marca": "gg_explica"` se não existir; se existir, acrescente o vídeo). `status: "rascunho"`,
   `serie: "radar"`, data de hoje e horário = a hora cheia seguinte a daqui a 2 horas.
   Estrutura: fato no gancho → selo e fonte → o que muda no Brasil (preço em reais, horário de
   Brasília) → o que falta saber → pergunta no `cta`.
   Se houver em `clipes/catalogo.json` um trecho que combine (sem spoiler), use `fundo_clipe`
   (ex.: `"busca:vice city noite"`) no gancho, com `credito`.
5. Rode `paginas validar` no arquivo e corrija os bloqueios.
6. Acrescente a afirmação em `saida/placar_selos.csv` se o selo for RELATO ou RUMOR.
7. Responda em até 4 linhas: a notícia com selo, o vídeo criado e o que o Vinicius precisa conferir.


> **Formato:** se `conteudo.so_carrossel` estiver `true` em `config/automacao.yaml`, todo post (inclusive
> o RADAR e o alerta) é `"formato": "carrossel"` no modelo revista, sem `narracao`, de 4 a 7 slides
> (gancho/capa, fatos com selo, `lista` ou `lista` com `"estilo": "tabela"`, `cta`). O kit gera o Reel do
> mesmo post sozinho e o publica 3 horas depois. Nada de `midia`/`tela_cheia` nesse modo: imagem só por
> `fundo_clipe` com `"busca:..."`.


> **Antes de tudo:** leia os posts de hoje e de ontem em `pautas/`. Se o assunto desta notícia já tem
> post (rascunho, aprovado ou publicado), não crie outro: só acrescente o fato novo ao rascunho que
> existe, se ainda for rascunho. Senão, crie **um** post no primeiro horário livre de hoje (09h00, 11h00,
> 12h30, 15h00, 17h00, 19h00, 21h00) a pelo menos 60 minutos de agora, no arquivo
> `pautas/radar_{hoje}_gg_explica.json` (acrescente à lista, não apague nada). Imagens só por `busca:`
> com palavras diferentes das dos outros posts.

## Estilo

Siga `docs/guia_de_estilo.md` em tudo que escrever: formato do post, capa (até 9 palavras, uma
palavra em `*destaque*`), slides, legenda (abre com emoção em caixa alta, fecha com pergunta) e o
checklist do fim.
