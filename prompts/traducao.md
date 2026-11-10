# Tarefa automática: versão em espanhol (GG Explica ES)

Hoje é {data de hoje}. A página em espanhol usa o mesmo material e as mesmas pautas da página em
português, adaptadas para a América Latina.

1. Leia `CLAUDE.md`, `config/marcas/gg_explica_es.yaml` e `docs/pauta.schema.json`.
2. Em `pautas/`, ache as pautas da GG Explica em português (`"marca": "gg_explica"`, sem contar
   `exemplo_*` e `demo_*`) que ainda não têm a versão `<mesmo nome>_es.json`, e as que mudaram depois
   da última versão em espanhol (compare a data de modificação).
3. Escreva `pautas/<mesmo nome>_es.json` com `"marca": "gg_explica_es"`:
   - **Adapte, não traduza palavra por palavra.** Espanhol latino neutro, que soe natural no México,
     na Colômbia e na Argentina. Ganchos curtos e diretos.
   - Preço em reais vira preço em dólar (o preço oficial em US$) ou some; referência brasileira
     (feriado, salário mínimo, time de futebol) vira uma equivalente latina ou sai.
   - Mantenha selos, `fonte`, `fonte_url`, `midia`, `fundo_clipe`, `credito` (traduzido: "Imágenes:
     Rockstar Games") e a estrutura das cenas. Ids terminam em `_es`.
   - Horários: os mesmos números (o público latino está a 1 a 3 horas de Brasília; o horário de pico
     é parecido).
   - `status: "rascunho"`. Vídeo com produto (`publi`) não é traduzido: os links são do Brasil.
4. Rode `paginas validar` em cada arquivo criado e corrija os bloqueios.
5. Responda em até 3 linhas: quantos vídeos traduziu e o que precisou adaptar.

> **Formato:** se `conteudo.so_carrossel` estiver `true` em `config/automacao.yaml`, todo post (inclusive
> o RADAR e o alerta) é `"formato": "carrossel"` no modelo revista, sem `narracao`, de 4 a 7 slides
> (gancho/capa, fatos com selo, `lista` ou `lista` com `"estilo": "tabela"`, `cta`). O kit gera o Reel do
> mesmo post sozinho e o publica 3 horas depois. Nada de `midia`/`tela_cheia` nesse modo: imagem só por
> `fundo_clipe` com `"busca:..."`.

