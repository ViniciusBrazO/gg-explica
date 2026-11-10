# Tarefa automática: resumo do dia e músicas para os posts (GG Explica)

Roda sozinha às 23h30. Hoje é {data de hoje}. Ninguém está olhando: só escreva o arquivo pedido.

O Vinicius troca a música dos posts de hoje pelo app do Instagram (a API não coloca música do
Instagram). Ele quer saber quantos Reels saíram e que músicas **em alta** combinam com cada um.

1. A lista dos posts publicados hoje está no fim deste texto ("Contexto desta execução"), com tipo
   (Reel ou carrossel), título e link.
2. Pesquise na web as músicas e áudios **em alta nos Reels do Instagram no Brasil nesta semana**
   (listas de "trending audio" / "músicas em alta no Reels" de sites como Later, Metricool, Tokchart,
   Buffer, blogs de marketing brasileiros; prefira publicações desta semana ou do mês). Anote a fonte.
3. Para cada post, escolha **2 músicas** da lista em alta que combinem com o clima do post: notícia
   urgente pede batida forte e rápida; guia e dado pedem algo mais leve; rumor e teoria pedem suspense.
   Prefira músicas sem letra ou com refrão curto (o texto do slide precisa ser lido). Nunca música do
   próprio GTA (trilha ou rádio do jogo).
4. Escreva `saida/telegram/resumo_{hoje}.md` em texto simples (vai para o Telegram, até 3.500
   caracteres, sem tabela e sem markdown pesado), neste formato:

   📊 Resumo de DD/MM: N Reels e M carrosséis no ar

   1) <título curto> (Reel)
   <link>
   🎵 <música> — <artista> | <música> — <artista>

   (um bloco por post, na ordem em que saíram)

   Como trocar: abra o post > ⋯ > Editar > toque no nome do áudio (ou em "Adicionar música") > escolha
   > Concluir. Se a opção não aparecer no Reel, ela ainda não chegou para a sua conta; no carrossel
   costuma aparecer.

   Fontes das músicas em alta: <sites e datas>

5. Se a lista de posts estiver vazia, escreva só "📊 Resumo de DD/MM: nenhum post saiu hoje." e pare.
