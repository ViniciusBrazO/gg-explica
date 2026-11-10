# Kit das páginas de nicho

Gera posts sem rosto e **sem jogar** para **GG Explica** (games: notícia, GTA no Brasil, história e
teorias, GTA 6 primeiro; versão em espanhol opcional) e **Seul no Bolso**: reels com manchete ou
cartões sobre cenas da biblioteca oficial da Rockstar, narração com voz de IA, legenda que acende
palavra por palavra, selos de confiança (CONFIRMADO, RELATO, RUMOR, TEORIA, FALSO), carrosséis 4:5,
publicação automática no Instagram, no Facebook e no YouTube Shorts e lotes prontos para TikTok e Kwai.

O manual (nomes, bios, voz, formatos e passo a passo) e o plano da página de games estão nos
documentos que acompanham este kit. Para o Claude Code, as instruções ficam em `CLAUDE.md`.
A identidade antiga de games (Gamer Pão-Duro) continua em `config/marcas/gamer_pao_duro.yaml`
como referência; o "Pão-Duro" agora é um quadro da GG Explica.

## Instalação (uma vez)

**Windows, jeito rápido:** dois cliques em `INSTALAR.cmd`. Ele instala Python, ffmpeg e o kit, pede o
token da Meta (sem mostrá-lo), testa o acesso e liga o Agendador. O passo a passo manual está abaixo.

1. Instale o **Python 3.11 ou mais novo** (python.org; no Windows marque "Add Python to PATH").
2. Instale o **ffmpeg**:
   - Windows: `winget install Gyan.FFmpeg`
   - Mac: `brew install ffmpeg`
3. Na pasta do kit, rode:

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate     Mac/Linux: source .venv/bin/activate
pip install -e ".[dev]"
playwright install chromium
copy .env.example .env      # Mac/Linux: cp .env.example .env
```

4. Confira se está tudo certo:

```bash
pytest -m "not lento"
python scripts/gerar_identidade.py
paginas renderizar pautas/exemplo_gg_explica.json --previa --voz silencio
```

O último comando gera os vídeos de prévia (sem som) em `saida/videos/gg_explica/`. O quarto vídeo
do exemplo é pulado de propósito: ele espera um quadro do trailer em `clipes/`. Para ver a manchete
e o carrossel: `paginas renderizar pautas/demo_escala.json --previa --voz silencio`.

## Automação (uma vez)

1. **Telegram:** crie um bot com o @BotFather, ponha o token em `TELEGRAM_BOT_TOKEN` no `.env`, mande
   um "oi" para o bot e rode `paginas telegram teste` para descobrir o `TELEGRAM_CHAT_ID`.
2. **Claude Code:** instale, faça login e confira com `claude -p "oi"`. As tarefas automáticas
   (`paginas claude ...`) usam o seu login.
3. **Biblioteca oficial:** `paginas biblioteca` baixa os trailers, screenshots e artes que a
   Rockstar oferece para download e corta cada vídeo em cenas; `paginas claude catalogo` etiqueta.
   Imagem oficial nova (Newswire, PlayStation Blog, Xbox Wire): `paginas oficial <link>`.
4. **Facebook e YouTube (opcional):** preencha `FB_PAGE_ID_*`/`FB_PAGE_TOKEN_*` e
   `YT_CLIENT_ID`/`YT_CLIENT_SECRET` no `.env` e rode `paginas youtube autorizar --marca gg_explica`.
   Sem isso, os vídeos dessas redes vão para o lote manual.
5. **Agendar:** `powershell -ExecutionPolicy Bypass -File scripts\instalar_automacao.ps1`
   (Mac/Linux: `bash scripts/agendar_mac_linux.sh`).

Depois disso, o dia a dia é aprovar no celular. O passo a passo completo está no plano da página de games.

## Uso semanal

| Quando | Comando | O que faz |
| --- | --- | --- |
| Sozinho, 07:10 | `paginas claude radar` | O Claude escreve o Radar do dia (notícia com selo e fonte) |
| Sozinho, 1x por dia | `paginas biblioteca` (dentro do ciclo) | Baixa o material oficial novo e cataloga |
| Segunda, depois da pauta | `paginas validar pautas/<arquivo>.json` | Mostra o que falta (links, clipes) e o que está bloqueado |
| Depois de colar os links | `paginas aprovar pautas/<arquivo>.json` | Aprova os vídeos sem pendência |
| Logo em seguida | `paginas renderizar pautas/<arquivo>.json` | Gera vídeos e carrosséis, agenda Instagram, Facebook e YouTube e monta os lotes |
| Uma vez por semana | Abrir `saida/lotes/` | TikTok (o atalho /tiktok-agendar preenche), Kwai e carrosséis, seguindo o `.md` de cada pasta |
| Sozinho, a cada 15 min | `paginas ciclo` | Biblioteca, notícias, prévias no Telegram, publicação nas APIs |
| Domingo | atalho /concorrentes | O Claude no Chrome lê o que bombou nas páginas grandes (só leitura) |
| Sozinho, todo dia | `paginas metricas` | Guarda as métricas para a revisão semanal |

## Estrutura

```
config/        identidade das páginas e regras de conformidade
templates/     design dos cartões (HTML + CSS)
assets/        fontes (licença OFL), avatares, fundos, ilustrações de exemplo
pautas/        pautas semanais (JSON) e exemplos
prompts/       prompts das tarefas do Claude (pauta, radar, tradução) e rotinas do Chrome
clipes/        biblioteca oficial (clipes/oficial) e imagens salvas à mão (não vão para o Git)
src/pipeline/  código
scripts/       identidade visual e agendador do sistema
saida/         vídeos, fila, lotes e métricas (não vai para o Git)
```
