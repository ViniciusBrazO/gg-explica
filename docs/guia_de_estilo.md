# Guia de estilo dos posts da GG Explica

Instrução fixa para toda criação de post (pauta semanal, radar do dia, alerta, ajustes). Feito a
partir do estudo das páginas grandes de games em 10/11/2026. Copiamos **o jeito** de fazer, nunca
o conteúdo, a imagem ou o texto de outra página.

## 1. O que as páginas grandes fazem

| Página | Seguidores (10/11) | O que funciona lá |
| --- | --- | --- |
| IGN Brasil | 835 mil | Carrossel de notícia. Capa com "NEWS" pequeno no alto e manchete condensada branca sobre a arte oficial. Slides internos com a imagem inteira, título amarelo e texto branco condensado embaixo. |
| MeuPS | 626 mil | Quase só Reels de GTA VI. Capa com quadro oficial e manchete centralizada embaixo, assinatura "MEUPS.COM.BR" no alto e logo no canto. Contagem regressiva ("FALTAM 8 DIAS"). Lista "7 coisas pra fazer antes do lançamento": 20,6 mil curtidas e 6,7 mil envios. |
| Flow Games | 437 mil | Notícia e meme. Legenda que abre gritando ("URGENTE:", "ATENÇÃO AQUI!") e fala como gente. |
| Portal GTA BR | 174 mil | Página de fã. Comparações (2013 x 2026, edição Ultimate x Padrão, notas GTA x Zelda), "quanto tempo pra atravessar o mapa", pergunta que divide. |
| Fluid Game | 144 mil | Modelo de capa fixo: imagem inteira, "GTA VI" pequeno acima da manchete colorida, rodapé "FLUID GAME \| VIA: DEXERTO". Slide de dado ("tempo pra baixar"): 4,8 mil envios. |
| Seek Key | 48 mil | Etiqueta vermelha ("OFICIAL", "NOTÍCIA", "GUIA"), manchete branca com palavra verde. Guia com ícones ("Entenda os ícones de GTA 6"). |

**O que se repete em todas:**

1. Imagem oficial ocupando o post inteiro.
2. Manchete condensada, em caixa alta, de 2 a 3 linhas, com 1 ou 2 palavras na cor da marca.
3. Etiqueta curta no alto (selo ou chamada).
4. Véu escuro só onde está o texto; o resto da imagem aparece.
5. Assinatura e logo pequenos, sempre no mesmo lugar: o perfil vira uma revista reconhecível.
6. Crédito da imagem e fonte da notícia.
7. **Utilidade é o que mais gera envio:** lista "o que fazer antes", tabela de dado, guia de ícones.
   Envio é o sinal que mais leva o post a quem não segue.
8. Legenda abre com emoção em caixa alta, explica em 2 a 4 frases e fecha com uma pergunta.

**O que não copiar:**

- "VAZOU" com coisa não confirmada. O post dos "códigos de trapaça vazados" teve 22,8 mil envios,
  mas notícia falsa queima a página depois e contraria a regra dos selos. Na GG Explica, boato é
  RUMOR, e a capa diz "É verdade que...?".
- Foto de pessoa famosa, imagem tirada do post de outra página ou de veículo de imprensa, dublagem
  de personagem feita por IA.

## 2. Os formatos da GG Explica

Todos saem no modelo **revista** do carrossel (`templates/slide_revista.html`). Cada carrossel
também gera `reel.mp4` e `capa_reel.jpg`, para postar a versão em Reel 2 a 4 horas depois.

| Formato | Como montar na pauta | Exemplo de capa |
| --- | --- | --- |
| Notícia | `gancho` + 2 a 4 `texto` (um fato por slide, com `selo`) + `cta` | "Pré-download de GTA 6 *liberado*" |
| Guia "o que fazer" | `gancho` + 1 `texto` + 1 `lista` com 4 a 6 itens "Título: descrição" + `cta` | "9 dias pra GTA 6: o que fazer *antes do dia 19*" |
| Dado | `gancho` + `lista` com `"estilo": "tabela"` ("rótulo: valor") + `cta` | "Quanto tempo pra baixar *212 GB*" |
| Comparação | `gancho` + 2 `texto` (um lado por slide, imagem de cada um) + `lista` com o resumo + `cta` | "Edição Ultimate x Padrão: *qual vale*?" |
| Guia de ícones e sistemas | `gancho` + 2 a 4 `lista` (ícone no começo do item: "📷 Câmera: ...") + `cta` | "Entenda os *ícones* de GTA 6" |
| Rumor ou confirmado | `gancho` "É verdade que...?" + `texto` com `selo` RUMOR, RELATO ou FALSO + `cta` | "GTA 6 no PC em 2027? *O que se sabe*" |
| Contagem | Reel com capa "Faltam *X dias*" | "Faltam *9 dias*" |

## 3. Regras de texto

- **Capa:** até 9 palavras, número sempre que der, 1 ou 2 palavras em `*destaque*`. Fórmulas:
  "X dias pra GTA 6: ...", "O que já é oficial sobre ...", "Entenda ...", "Tempo pra ...",
  "A x B: qual ...?", "É verdade que ...?". `texto` da capa é a promessa curta ("Salva pra não esquecer").
- **Etiqueta da capa:** `selo` quando for fato; senão `kicker` de uma palavra (GUIA, NOTÍCIA, COMPARAÇÃO, DADO).
- **Slide de fato:** título de 2 a 4 palavras (sai na cor da marca) e corpo de 1 ou 2 frases, até 25 palavras.
- **Lista:** 4 a 6 itens no formato "Título: descrição curta". `kicker` vira o subtítulo.
  `rodape` diz de onde veio ("Com base no que a Rockstar mostrou até agora.").
- **Tabela:** 4 a 7 linhas "rótulo: valor"; `rodape` explica a conta. Faça a conta, não copie a de outra página.
- **Slide final:** pede envio primeiro ("Manda pra quem vai jogar no dia 19"), depois salvar e seguir.
- **Legenda do post:**
  1. Primeira linha em caixa alta, com emoção e verdadeira ("PRÉ-DOWNLOAD LIBERADO!").
  2. 2 a 4 frases de contexto.
  3. A fonte.
  4. Uma pergunta que dá vontade de responder ("Xbox ou PS5?").
  5. 3 hashtags.

## 4. Visual

- Imagem: `fundo_clipe: "busca:<personagem lugar ação>"` da biblioteca oficial, `foco_x` para
  escolher o lado e `credito: "Imagem: Rockstar Games"`. Uma imagem diferente por slide.
- Cores: verde-limão no destaque, etiqueta vermelha para chamada, selos nas cores próprias.
- Assinatura "GG.EXPLICA" no alto à esquerda e logo no canto direito em todos os slides.
- Para trocar o visual de uma marca: `carrossel: {modelo: revista | classico}` no YAML da marca.

## 5. Cadência e horários

- Por dia: 1 carrossel (10h), 3 Reels (12h30 GTA no Brasil, 19h Radar, 21h30 Explica ou Rumor) e,
  2 a 4 horas depois de cada carrossel, a versão dele em Reel.
- Notícia oficial quente sai em até 2 horas. Nesse caso, velocidade vale mais que o horário.

## 6. Antes de aprovar

- [ ] A capa entende-se em 1 segundo, com no máximo 9 palavras e uma palavra colorida.
- [ ] Todo fato tem selo e fonte; nada de "vazou" sem confirmação.
- [ ] As imagens são da biblioteca oficial e cada slide tem uma diferente.
- [ ] Há pelo menos um slide útil para salvar ou mandar (lista, tabela, passo a passo).
- [ ] A legenda abre forte e fecha com pergunta.
- [ ] Post com link: sem imagem do jogo e com `#publi`.
