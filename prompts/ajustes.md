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

> **Formato:** se `conteudo.so_carrossel` estiver `true` em `config/automacao.yaml`, todo post (inclusive
> o RADAR e o alerta) é `"formato": "carrossel"` no modelo revista, sem `narracao`, de 4 a 7 slides
> (gancho/capa, fatos com selo, `lista` ou `lista` com `"estilo": "tabela"`, `cta`). O kit gera o Reel do
> mesmo post sozinho: o Reel sai no horário e o carrossel 2 horas depois. Nada de `midia`/`tela_cheia` nesse modo: imagem só por
> `fundo_clipe` com `"busca:..."`.

## Estilo

Siga `docs/guia_de_estilo.md` em tudo que escrever: formato do post, capa (até 9 palavras, uma
palavra em `*destaque*`), slides, legenda (abre com emoção em caixa alta, fecha com pergunta) e o
checklist do fim.
