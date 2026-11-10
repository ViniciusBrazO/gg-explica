# Páginas de nicho: GG Explica e Seul no Bolso

Pipeline que produz posts sem rosto e **sem jogar**: reels verticais (manchete ou cartões +
narração de IA + legenda karaokê + cenas da biblioteca oficial da Rockstar com crédito) e carrosséis
4:5. Publica no Instagram, no Facebook e no YouTube Shorts pelas APIs oficiais e prepara lotes para
TikTok e Kwai. A página de games é a **GG Explica** (`gg_explica`, e `gg_explica_es` para a América
Latina): engajamento primeiro (notícia, GTA no Brasil, história, teorias com selo) e ofertas com
arte própria desde o início, no máximo 1 a cada 6 posts.
`gamer_pao_duro` é a identidade antiga, mantida só como referência.
Dono do projeto: Vinicius. Idioma do código, dos comentários e das mensagens: português do Brasil.

## Regras inegociáveis

Estas regras protegem as contas e o dono do projeto. Nenhuma tarefa justifica quebrá-las.

1. **Nada de robô na rede social.** Nunca automatize curtir, seguir, comentar, mandar DM ou postar
   por navegador controlado. Publicação só pelas APIs oficiais (Instagram, Facebook, YouTube). No TikTok, o kit prepara o
   lote e o Claude no Chrome pode preencher o agendamento no TikTok Studio, mas **para antes do botão
   final**: quem clica é o Vinicius (a API de postagem deixa tudo privado até o app passar por auditoria).
   Rotinas no navegador só leem (métricas, comentários) ou preparam.
2. **Conteúdo original, trecho de terceiros só como citação.** Nunca baixe ou reaproveite vídeo de
   outro criador, fancam, foto de ídolo ou trecho de filme/série. Fundo em vídeo: Pexels, gravação
   própria ou material oficial salvo em `clipes/`. Trecho de jogo (cenas `midia`, `tela_cheia` e
   `fundo_clipe`) só da biblioteca oficial (`paginas biblioteca`, pacotes da página de mídia da
   Rockstar) ou de material oficial salvo com `paginas oficial`, em corte curto, com análise por cima
   e `credito`. Imagem que só existe num veículo de imprensa não entra. Nunca: vazamento ou material de
   antes do lançamento, cena de cinema isolada, o final do jogo, TV/rádio do jogo como atração,
   música licenciada, mods ou trapaça. Trecho de terceiros nunca em vídeo com link (o modelo bloqueia)
   e vídeo com trecho de jogo fica abaixo de 1 minuto (a Rockstar trata ganho com gravação como uso
   comercial).
3. **Selo em todo fato (GG Explica).** CONFIRMADO, RELATO e FALSO levam `fonte` com veículo e data
   e `fonte_url` com o link; RUMOR e TEORIA nunca dizem "confirmado". CONFIRMADO só se a fonte oficial
   foi lida na própria execução; senão, RELATO. Adiamento ou mudança de data só com CONFIRMADO.
4. **Verdade na publicidade (guia CONAR, maio de 2026).** Vídeo com link leva `#publi` no início da
   legenda. A página não manuseia produtos: nunca escreva "testei", "uso", "comprei". Todo preço
   mostrado tem fonte e data (`fonte_preco`). Cosmético não "trata" nem "cura" nada.
5. **IA rotulada.** `voz_ia: true` em todo vídeo; a legenda já inclui o aviso, e o rótulo de IA é
   ativado no app na hora de agendar.
6. **Sem marca de terceiros como se fosse parceira.** Nada de "parceria oficial" ou uso de logo.
7. **Segredos só no `.env`.** Nunca grave chave ou token em código, log ou pauta.

8. **Cada post é único** (pedido fixo do Vinicius): imagens oficiais diferentes em cada post e slide,
   capa, manchete, formato e assunto diferentes dos posts próximos (`src/pipeline/variedade.py` e
   `docs/guia_de_estilo.md`, seção 0). Notícia muito relevante sai na hora, fora dos horários base.

`config/regras.yaml` tem as frases bloqueadas; `paginas validar` aplica tudo isso.

## Modo nuvem (como roda hoje)

Repositório privado `ViniciusBrazO/gg-explica`, `.github/workflows/kit.yml` (GitHub Actions, sem PC):
ciclo a cada 30 min (08h-00h30), radar do Claude às 07h10, 12h10 e 17h10, pauta na segunda, métricas
às 23h30. `telegram.aprovacao: automatica`: o kit agenda sozinho todo rascunho sem bloqueio, avisa no
Telegram (✍️ Ajustar / 🗑 Cancelar até sair) e manda o link quando publica; respostas viram
`saida/telegram/orientacoes.md`. Reel no horário, carrossel 2 h depois. Notícia quente numa rodada leve
chama uma rodada pesada na hora. Segredos no GitHub: META_TOKEN_GG_EXPLICA, TELEGRAM_BOT_TOKEN,
CLAUDE_CODE_OAUTH_TOKEN, AZURE_SPEECH_KEY (voz Antonio) e GEMINI_API_KEY (chat do Telegram em
`saida/telegram/chat_id.txt`). **Redator:** hoje `redator: claude`. Opção `redator: gemini` (grátis, testada em 10/11 e desligada: texto raso e assunto repetido; `src/pipeline/redator.py` +
`prompts/gemini_sistema.md`: o kit lê as matérias, o Gemini escreve, o validador confere); sem a chave
do Gemini, volta para o Claude Code (`claude -p`).

## Como o projeto funciona

```
pautas/*.json  ->  paginas renderizar  ->  saida/videos/<marca>/*.mp4  ->  fila (Instagram, Facebook, YouTube: APIs)
 (Claude, semanal)       |                                              ->  saida/lotes/<rede>/<dia>/ (TikTok, Kwai)
                         |              ->  saida/carrosseis/<marca>/<post>/NN.jpg (carrossel: lote)
                         +-- voz.py (ElevenLabs | Azure | silencio)
                         +-- cartoes.py (HTML/CSS -> PNG via Playwright)
                         +-- legendas.py (ASS karaokê) + montagem.py (ffmpeg)
paginas metricas (diário)         ->  saida/metricas.csv  ->  revisão semanal do Claude

paginas ciclo (a cada 15 min, Agendador do Windows / cron):
  biblioteca.py (1x por dia): pacotes oficiais da Rockstar -> clipes/oficial -> catálogo (um trecho por plano)
  clipes/entrada (imagens salvas à mão) -> vigia.py -> catálogo -> claude -p catalogar_clipes.md
  radar.py (Google Notícias RSS) -> alerta quente -> Telegram + claude -p alerta_radar.md
  telegram.py: prévias dos rascunhos de hoje/amanhã -> ✅ aprova (producao.py: render + fila)
                                                     -> ✍️ ajuste -> claude -p ajustes.md -> nova prévia
  instagram.py / facebook.py / youtube.py: publica o que chegou no horário
paginas claude radar (07:10), pauta (segunda 07:40) e traducao (08:10, se ligada) -> claude_cli.py -> `claude -p`
```

| Arquivo | Papel |
| --- | --- |
| `config/marcas/*.yaml` | Identidade: cores, fontes, voz, séries, textos fixos |
| `templates/cena.html` + `templates/estilos/*.css` | Os 10 tipos de cartão (gancho, texto, lista, produto, comparativo, veredito, contagem, cta, midia, tela_cheia), estilo `manchete`, selos, fonte e crédito |
| `templates/slide_revista.html` + `src/pipeline/carrossel.py` | Carrossel 1080x1350 no estilo das páginas grandes (capa, fato, lista, tabela, final) + `reel.mp4` e `capa_reel.jpg` do mesmo post; `slide.html` é o modelo clássico |
| `docs/guia_de_estilo.md` | **Como os posts devem ser** (estudo das páginas grandes, formatos, capas, legendas, checklist). Toda tarefa de conteúdo segue este guia |
| `src/pipeline/biblioteca.py` | `paginas biblioteca`: baixa os pacotes oficiais (links em `config/automacao.yaml`), só de novo quando mudam |
| `src/pipeline/modelos.py` | Formato da pauta (pydantic). `docs/pauta.schema.json` é gerado dele |
| `src/pipeline/montagem.py` | Monta o vídeo: um trecho por cena, revelação de itens no ritmo da fala, cenas `midia` (caixa `CAIXA_MIDIA`, zoom até o detalhe, anel), `tela_cheia` (recorte vertical, panorâmica) e `fundo_clipe`, cache de voz, legenda, -14 LUFS |
| `src/pipeline/catalogo.py` | `paginas catalogar`: vídeos cortados em planos, imagens em folhas numeradas, `clipes/catalogo.json` e a busca (`busca:...`) |
| `src/pipeline/qualidade.py` | Bloqueios e avisos antes de renderizar; checagem do arquivo final |
| `src/pipeline/fila.py` | Legenda do post, fila das APIs, lotes de TikTok, Kwai e carrossel |
| `src/pipeline/instagram.py` | Upload resumível + publicação de Reels (Graph API) |
| `src/pipeline/meta.py` | Um token só (`META_TOKEN_*` + `FB_PAGE_ID_*`): acha a conta do Instagram, o token da Página e hospeda os slides; `paginas meta conferir` |
| `src/pipeline/facebook.py` | Reels na Página do Facebook (Reels Publishing API), se `FB_PAGE_*` estiver no `.env` |
| `src/pipeline/youtube.py` | Shorts pela YouTube Data API (upload resumível, OAuth); `paginas youtube autorizar` gera o token |
| `src/pipeline/producao.py` | O passo comum: renderizar, conferir, legenda, fila (usado pelo CLI e pelo Telegram) |
| `src/pipeline/ciclo.py` | `paginas ciclo`: a rodada automática de 15 em 15 minutos, cada etapa isolada |
| `src/pipeline/vigia.py` | Organiza `clipes/entrada` (imagens e vídeos oficiais salvos à mão) e atualiza o catálogo |
| `src/pipeline/radar.py` | Notícias do Google Notícias (RSS), selo sugerido pela fonte, alerta quente |
| `src/pipeline/telegram.py` | Aprovação pelo celular: prévia com botões, ajustes por mensagem, só o chat do dono |
| `src/pipeline/claude_cli.py` | Roda as tarefas do Claude Code sem janela (`claude -p`) com ferramentas limitadas |
| `config/automacao.yaml` | Intervalos, buscas do radar, fontes por selo, ferramentas liberadas para o Claude |
| `prompts/` | Tarefas do Claude: `pauta_semanal`, `radar_do_dia`, `alerta_radar`, `catalogar_clipes`, `ajustes`, `traducao`; `chrome/` para as rotinas no navegador (TikTok, métricas, comentários, concorrentes) |
| `scripts/instalar_automacao.ps1` | Agenda tudo no Windows, sem janela |

## Comandos

```bash
pip install -e ".[dev]"            # e, se usar Azure: pip install -e ".[azure]"
playwright install chromium
python scripts/gerar_identidade.py  # avatares, fundos e folhas de estilo
paginas validar pautas/exemplo_gg_explica.json
paginas renderizar pautas/exemplo_gg_explica.json --previa --voz silencio
paginas biblioteca                  # baixa trailers, screenshots e artes oficiais e cataloga
paginas catalogar                   # depois de salvar imagens à mão em clipes/
paginas renderizar pautas/demo_formatos_jogo.json --previa --voz silencio   # os formatos com cena
paginas renderizar pautas/demo_escala.json --previa --voz silencio          # manchete e carrossel
paginas renderizar pautas/demo_revista.json --previa --voz silencio         # carrossel revista + reel
paginas youtube autorizar --marca gg_explica   # uma vez por canal
paginas ciclo                       # a rodada automática (o agendador roda a cada 15 min)
paginas claude radar                # tarefa do Claude sem janela (radar|pauta|alerta|catalogo|ajustes|traducao)
paginas telegram teste              # descobre o TELEGRAM_CHAT_ID / testa o envio
paginas oficial <url>               # salva imagem oficial escolhida em clipes/oficial
paginas aprovar pautas/<semana>_<marca>.json
paginas renderizar pautas/<semana>_<marca>.json
paginas publicar --simular
paginas fila
pytest -m "not lento"              # rápido; `pytest` inclui uma renderização real
```

## Convenções

- Nomes em português, funções pequenas, tipos anotados. Teste para toda regra nova.
- ffmpeg sempre com `-preset veryfast` (a qualidade sai pelo CRF).
- Mudança visual: edite o CSS da marca e rode `scripts/gerar_identidade.py` para conferir a folha de estilo.
- Ao mexer na API do Instagram, confira a documentação oficial atual antes (os nomes de métricas mudam).

## Jogo na tela e selos (resumo)

```json
{"tipo": "midia", "midia": "clipes/2026-11/2026-11-19_203512_Replay.mp4", "midia_inicio": 12.0, "midia_fim": 17.5,
 "midia_recorte": [0.5, 0.1, 0.4, 0.4], "midia_animacao": "aproximar", "midia_destaque": [0.7, 0.3, 0.05],
 "credito": "Imagens: Rockstar Games", "selo": "teoria", "titulo": "Olha o *canto direito*", "narracao": "..."}
{"tipo": "tela_cheia", "midia": "busca:praia vice city pôr do sol", "panoramica": true, "credito": "...", ...}
{"tipo": "gancho", "titulo": "...", "fundo_clipe": "busca:perseguição noite", "foco_x": 0.4, "credito": "...", ...}
```

- `midia`: caixa 16:9 com moldura, fundo desfocado; `aproximar` vai do quadro inteiro ao recorte e
  `midia_destaque` desenha um anel (coordenadas no quadro inteiro).
- `tela_cheia`: o clipe cobre a tela (`foco_x` escolhe a parte da largura; `panoramica` passeia).
- `fundo_clipe`: em qualquer cartão, o jogo vira o fundo em movimento.
- `"busca:..."` escolhe no `clipes/catalogo.json` pelas tags/descrição, sem spoiler, variando os trechos.
- `midia_terceiros: false` para visual próprio (mapa desenhado, arte da página): dispensa crédito e
  pode ir em vídeo de mais de 1 minuto.
- O áudio do clipe entra mudo; a narração conduz.
- `selos` e cores ficam em `config/marcas/gg_explica.yaml`; o `veredito` com `selo` vira o carimbo
  do selo (formato RUMOR OU CONFIRMADO?).

## Roteiro de trabalho (em ordem)

1. **Ambiente.** Instalar dependências, rodar `pytest`, gerar as prévias de `pautas/exemplo_gg_explica.json`.
2. **Voz.** Preencher `voice_id` (ElevenLabs) ou trocar o provedor para `azure`; renderizar um exemplo
   com voz real e ajustar velocidade/estabilidade no YAML até soar natural.
3. **Fundo em vídeo.** Com `PEXELS_API_KEY`, testar `broll` nas cenas de gancho.
4. **Instagram.** Feito em 10/11: app "GG Explica Publicador", usuário do sistema com token que não vence.
   No PC: `INSTALAR.cmd` (instala tudo e pede o token) ou `scripts/configurar_meta.ps1`. Referência antiga: criar app na Meta (tipo Empresa), ligar cada conta profissional a uma Página do
   Facebook, gerar token de longa duração com `instagram_basic`, `instagram_content_publish`,
   `instagram_manage_insights`, `pages_show_list` e `pages_read_engagement`; testar `paginas publicar --simular` e depois um post real.
5. **Biblioteca.** `paginas biblioteca` e depois `paginas claude catalogo` para etiquetar as cenas.
6. **Mais redes.** Facebook (`FB_PAGE_ID_*`, `FB_PAGE_TOKEN_*`) e YouTube (`YT_CLIENT_ID`, `YT_CLIENT_SECRET`,
   `paginas youtube autorizar`). Sem as variáveis, o post vai para o lote manual daquela rede.
7. **Automação.** Telegram (`TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`), Claude Code logado, depois
   `scripts/instalar_automacao.ps1` (Windows) ou `scripts/agendar_mac_linux.sh`.
8. **Página de achados** (link da bio): gerar uma página estática a partir dos produtos das pautas,
   publicada no GitHub Pages, com os links de afiliado organizados por série.
9. **Sem computador ligado:** mover renderização e publicação para GitHub Actions (cron), com os
   segredos em GitHub Secrets.
10. **Alerta de preço:** só com fontes oficiais (APIs dos programas de afiliado). Não raspar sites.

## Limites conhecidos

- TikTok e Kwai: publicação manual em lote (TikTok Studio agenda até 10 dias).
- Carrossel: com `META_TOKEN_*` e `FB_PAGE_ID_*` no `.env`, sai pela API (cada slide sobe como foto não
  publicada da Página, ganha link público e é apagado depois) e a versão em Reel entra 3 h depois; sem isso, lote manual.
- App da Meta "não publicado": Instagram funciona; Reels no Facebook podem ficar visíveis só para quem tem
  função no app até publicar o app (precisa de URL de política de privacidade: `docs/site/privacidade.html`).
- Página em espanhol: desligada até `traducao.ativa: true` em `config/automacao.yaml`.
- Marcar produto da Shopee ou do TikTok Shop no post é feito no app (cerca de 1 min por vídeo).
- ElevenLabs no plano gratuito não permite uso comercial.
- O provedor `silencio` gera vídeo sem som: só para conferir o visual.
