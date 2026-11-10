# clipes/

A biblioteca de imagens da página. Você não precisa jogar nem gravar nada:

    paginas biblioteca          # baixa os pacotes oficiais da Rockstar para clipes/oficial/
    paginas claude catalogo     # o Claude descreve cada cena e cada imagem

O kit corta cada trailer em planos (um plano = um trecho pronto), monta folhas numeradas em
`clipes/_folhas/` e guarda tudo em `clipes/catalogo.json`. As pautas pedem cenas por busca
(`"busca:lucia noite carro"`) e o kit escolhe o trecho menos usado.

Material oficial novo (Rockstar Newswire, PlayStation Blog, Xbox Wire): `paginas oficial <link>`,
ou salve o arquivo em `clipes/entrada/` e o ciclo organiza e cataloga.

Regras (detalhes no plano da página):
- só material oficial; nada vazado ou de antes do lançamento; imagem de veículo de imprensa não entra;
- cortes curtos, sempre com narração e análise por cima, e crédito na cena (`credito`);
- sem o final da história; o som dos trechos sai sempre mudo;
- material oficial nunca em post com link de afiliado (o kit bloqueia).

Os arquivos desta pasta não vão para o Git (são pesados).
