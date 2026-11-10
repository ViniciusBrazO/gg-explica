# Tarefa automática: catalogar a biblioteca

Chegou material novo em `clipes/` (pacotes oficiais da Rockstar ou imagens salvas à mão).
Hoje é {data de hoje}.

Abra `clipes/catalogo.json` e trate só as entradas com `descricao` vazia.

## Vídeos (`"tipo": "video"`)

O kit já cortou o vídeo em planos: cada item de `momentos` é um plano, com `corte` (o número),
`inicio` e `fim`. As imagens de `folhas_cortes` mostram um quadro de cada plano com "#número · tempo".

1. Para **cada** momento, preencha `o_que_mostra` com uma frase curta e concreta
   ("Lucia de perfil no carro, noite, luzes neon"). Use os nomes só de quem você reconhece com segurança.
2. Marque `"descartar": true` nos planos inúteis: logo, tela preta, texto do trailer, plano borrado.
3. Na entrada do vídeo: `descricao` (o vídeo em uma frase), `lugar`, `personagens` e `tags`
   (6 a 12 palavras simples para a busca: praia, noite, carro, perseguição, chuva, barco, festa...).

## Imagens (`"tipo": "imagem"`)

Várias imagens dividem a mesma folha (`folha`); cada uma tem o número `posicao_na_folha` escrito no canto.
Preencha `descricao`, `lugar`, `personagens` e `tags` de cada uma, olhando o número certo.

## Para as duas

- `lugar`: região de Leonida, se der para saber (Vice City, Leonida Keys, Grassrivers, Port Gellhorn,
  Ambrosia, Mount Kalaga), ou "".
- `spoiler`: true se mostrar algo da história além das primeiras horas (missão avançada, morte de
  personagem, final). Na dúvida, true.
- Não invente: se a imagem não deixa claro, escreva menos. Mantenha o JSON válido.

Responda em até 3 linhas: quantos vídeos, planos e imagens catalogou e as 3 cenas mais fortes para
capa de manchete nesta semana (com a busca que acha cada uma).
