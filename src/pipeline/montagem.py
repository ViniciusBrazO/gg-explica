"""Monta o vídeo final 1080x1920: fundo em movimento + cartão animado + narração + legenda.

Etapas por vídeo:
1. narra cada cena (voz.py) e mede a duração;
2. desenha o cartão de cada cena (cartoes.py);
3. gera um trecho por cena com ffmpeg (fundo com movimento lento + cartão entrando);
4. junta os trechos, a narração, a legenda karaokê e normaliza o volume (-14 LUFS).
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import dataclasses
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Optional

from .cartoes import CAIXA_MIDIA, desenhar_fundo, desenhista, montar_html
from .catalogo import Escolha, registrar_uso, resolver_midia
from .legendas import gerar_ass
from .marca import RAIZ, Marca
from .midia import buscar_broll, imagem_produto
from .modelos import TIPOS_COM_MIDIA, Cena, Video
from .voz import Fala, Palavra, criar_voz, falar_continuo, texto_para_fala

FPS = 60                 # movimento mais liso no celular (o Instagram aceita até 60)
PAUSA_ENTRE_CENAS = 0.18
DURACAO_MINIMA_CENA = 1.6
DURACAO_MINIMA_CENA_CONTINUA = 0.8
PAUSA_FINAL = 0.4         # respiro depois da última frase, antes do vídeo acabar
ENTRADA_CARTAO = 0.28
EXT_IMAGEM = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
BORDA_MIDIA = 4          # moldura colorida em volta do clipe, em pixels
ZOOM_IMAGEM = 0.10       # imagem parada ganha uma aproximação lenta de 10% durante a cena
SUPER = 4                # zoom/deriva calculados em 4x e reduzidos: passo de 1/4 de pixel, sem tremer
SUPER_FUNDO = 3          # o fundo dos cartões é grande; 3x já tira o "degrau" da deriva
TRANSICAO = 0.35         # segundos de transição entre cenas (o trecho anterior dura isso a mais)
PASSO_PALAVRA = 0.11     # o título entra palavra por palavra, uma a cada 0,11 s
MAX_PASSOS_TITULO = 9    # título longo: as últimas palavras entram juntas
BARRA_ALTURA = 9         # barra de progresso no topo do Reel
TRANSICOES = ("fade", "smoothleft", "fade", "smoothup", "fade", "slideleft")


def _ff(args: list[str], cwd: Path | None = None) -> None:
    cmd = ["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-y", *args]
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd)
    if r.returncode != 0:
        raise RuntimeError(f"ffmpeg falhou:\n{' '.join(cmd)}\n{r.stderr[-2000:]}")


def preencher_variaveis(texto: str, hoje: date) -> str:
    """Troca {dias_ate:AAAA-MM-DD} pelo número de dias que faltam (para contagens)."""
    import re

    def dias(m):
        alvo = date.fromisoformat(m.group(1))
        return str(max(0, (alvo - hoje).days))

    return re.sub(r"\{dias_ate:(\d{4}-\d{2}-\d{2})\}", dias, texto)


@dataclass
class MidiaCena:
    """Clipe ou imagem usado numa cena: na caixa ("midia"), na tela toda ("tela_cheia") ou de fundo."""
    caminho: Path
    e_video: bool
    largura: int
    altura: int
    inicio: float = 0.0
    fim: Optional[float] = None
    recorte: tuple[float, float, float, float] | None = None   # x, y, largura, altura (0 a 1)
    animacao: str = "nenhuma"
    destaque: tuple[float, float, float] | None = None          # x, y, raio no quadro inteiro (0 a 1)
    foco_x: float = 0.5
    panoramica: bool = False
    escolha: Optional[Escolha] = None

    @classmethod
    def da_cena(cls, cena: Cena, fundo: bool = False, evitar: set | None = None, semente: str = "") -> "MidiaCena":
        if fundo:
            escolha = resolver_midia(cena.fundo_clipe, cena.fundo_inicio, evitar=evitar, semente=semente,
                                     preferir_video=True)
        else:
            escolha = resolver_midia(cena.midia, cena.midia_inicio, cena.midia_fim, evitar=evitar, semente=semente,
                                     preferir_video=True)
        if escolha is None:
            raise FileNotFoundError(f"nenhum clipe do catálogo para '{cena.fundo_clipe if fundo else cena.midia}'")
        largura, altura = _dimensoes(escolha.caminho)
        return cls(escolha.caminho, escolha.caminho.suffix.lower() not in EXT_IMAGEM, largura, altura,
                   escolha.inicio, escolha.fim,
                   None if fundo or not cena.midia_recorte else tuple(cena.midia_recorte),
                   "nenhuma" if fundo else cena.midia_animacao,
                   None if fundo or not cena.midia_destaque else tuple(cena.midia_destaque),
                   cena.foco_x, False if fundo else cena.panoramica, escolha)

    @property
    def aproxima(self) -> bool:
        return self.animacao == "aproximar" and self.recorte is not None

    def tamanho_na_caixa(self) -> tuple[int, int]:
        """Maior tamanho (par) que cabe na caixa mantendo a proporção do trecho mostrado."""
        rw, rh = (self.recorte[2], self.recorte[3]) if self.recorte and not self.aproxima else (1.0, 1.0)
        proporcao = (self.largura * rw) / (self.altura * rh)
        cl, ca = CAIXA_MIDIA["l"] - 2 * BORDA_MIDIA, CAIXA_MIDIA["a"] - 2 * BORDA_MIDIA
        w, h = (cl, cl / proporcao) if proporcao >= cl / ca else (ca * proporcao, ca)
        return int(w) // 2 * 2, int(h) // 2 * 2

    def regiao_final(self) -> tuple[float, float, float, float]:
        """Parte do quadro inteiro (x, y, l, a em frações) que aparece na caixa ao fim da animação."""
        if self.recorte is None:
            return 0.0, 0.0, 1.0, 1.0
        x, y, w, h = self.recorte
        if not self.aproxima:
            return x, y, w, h
        f = max(w, h)
        cx, cy = x + w / 2, y + h / 2
        return min(max(cx - f / 2, 0.0), 1 - f), min(max(cy - f / 2, 0.0), 1 - f), f, f

    def regiao_tela_cheia(self) -> tuple[float, float, float, float]:
        """Parte do quadro inteiro que aparece na tela 1080x1920 (sem panorâmica)."""
        rx, ry, rw, rh = self.recorte if self.recorte else (0.0, 0.0, 1.0, 1.0)
        w0, h0 = self.largura * rw, self.altura * rh
        esc = max(1080 / w0, 1920 / h0)
        vis_l, vis_a = 1080 / (w0 * esc), 1920 / (h0 * esc)
        return rx + rw * (1 - vis_l) * self.foco_x, ry + rh * (1 - vis_a) / 2, rw * vis_l, rh * vis_a

    def entrada(self, d: float, laco: bool = False) -> tuple[list[str], str]:
        """Argumentos de entrada do ffmpeg e o filtro que estica o clipe até a duração da cena."""
        if not self.e_video:
            return ["-loop", "1", "-framerate", str(FPS), "-i", str(self.caminho)], ""
        dur = (self.fim - self.inicio) if self.fim is not None else d
        if self.inicio == 0 and self.fim is not None and dur < 3 and dur < d:
            # clipe oficial curto (os retratos animados têm 1 s): repete em laço até o fim da cena
            return ["-stream_loop", "-1", "-t", f"{d:.3f}", "-i", str(self.caminho)], ""
        return (["-ss", f"{self.inicio:.3f}", "-t", f"{min(dur, d):.3f}", "-i", str(self.caminho)],
                f",tpad=stop_mode=clone:stop_duration={d:.3f}")


def _dimensoes(arquivo: Path) -> tuple[int, int]:
    from .sonda import video
    s = video(arquivo)
    return int(s["width"]), int(s["height"])


def desenhar_anel(largura: int, altura: int, cx: float, cy: float, raio: float, cor: str, saida: Path) -> Path:
    """PNG transparente do tamanho da área do clipe com um anel no detalhe (cx, cy, raio em pixels)."""
    from PIL import Image, ImageDraw

    k = 3   # desenha maior e reduz: borda lisa
    img = Image.new("RGBA", (largura * k, altura * k), (0, 0, 0, 0))
    g = ImageDraw.Draw(img)
    r = raio * k
    for extra, espessura, tinta in ((10, 26, (11, 13, 18, 170)), (0, 13, cor)):
        rr = r + extra
        g.ellipse((cx * k - rr, cy * k - rr, cx * k + rr, cy * k + rr), outline=tinta, width=espessura * k // 3)
    img.resize((largura, altura), Image.LANCZOS).save(saida)
    return saida


def _anel_em_pixels(destaque, regiao, largura: int, altura: int) -> Optional[tuple[float, float, float]]:
    fx, fy, fr = destaque
    rx, ry, rw, rh = regiao
    u, v = (fx - rx) / rw, (fy - ry) / rh
    if not (0 <= u <= 1 and 0 <= v <= 1):
        return None
    return u * largura, v * altura, max(18.0, fr / rw * largura)


@dataclass
class Trecho:
    cartoes: list[tuple[Path, float]]   # (cartão, segundo em que aparece); o primeiro entra animado
    moldura: Path                       # véu + topo com nome da página e da série: fica parado
    fundo: Path
    fundo_e_video: bool
    fala: Fala
    duracao: float
    inicio_global: float = 0.0          # para o fundo seguir a mesma deriva entre cenas
    midia: Optional[MidiaCena] = None   # cena "midia" ou "tela_cheia"
    cor_borda: str = "#FFFFFF"
    tipo: str = ""
    fundo_midia: Optional[MidiaCena] = None   # clipe do jogo atrás de um cartão comum
    anel: Optional[Path] = None
    anel_inicio: float = 0.5
    tomadas: list = dataclasses.field(default_factory=list)   # estilo notícia: várias tomadas na mesma cena


def momentos_de_revelacao(n_itens: int, palavras: list[Palavra]) -> list[float]:
    """Quando cada item de lista/comparativo aparece: quando a voz começa a falar dele.

    Usa o início das frases da narração (depois de . ! ? ;). O item k aparece no início
    de frase mais próximo da fração k/n da fala. O primeiro item já entra com o cartão.
    """
    if n_itens <= 1 or not palavras:
        return [0.0] * max(n_itens, 1)
    inicios_frase = [0] + [i + 1 for i, p in enumerate(palavras[:-1]) if p.texto[-1:] in ".!?;"]
    tempos, ultimo = [0.0], 0
    for k in range(1, n_itens):
        alvo = k * len(palavras) / n_itens
        candidatos = [i for i in inicios_frase if i > ultimo] or [min(round(alvo), len(palavras) - 1)]
        escolhido = min(candidatos, key=lambda i: abs(i - alvo))
        tempos.append(palavras[escolhido].inicio)
        ultimo = escolhido
    return tempos


def _filtros_cartoes(t: Trecho, primeiro_indice: int) -> tuple[list[str], list[str]]:
    """Entradas e filtros dos cartões, por cima de [s0]. Devolve (entradas, filtros)."""
    entradas, partes = [], []
    for k, (cartao, inicio) in enumerate(t.cartoes, start=1):
        idx = primeiro_indice + k - 1
        entradas += ["-loop", "1", "-framerate", str(FPS), "-i", str(cartao)]
        if k == 1:
            partes.append(f"[{idx}:v]format=rgba,fade=t=in:st=0:d={ENTRADA_CARTAO}:alpha=1[c{k}]")
            partes.append(f"[s{k-1}][c{k}]overlay=x=0:y='if(lt(t,{ENTRADA_CARTAO}),48*(1-t/{ENTRADA_CARTAO}),0)'"
                          f":eval=frame:shortest=0[s{k}]")
        else:
            # cartão seguinte é o mesmo com mais um item visível; troca no tempo certo
            partes.append(f"[{idx}:v]format=rgba[c{k}]")
            partes.append(f"[s{k-1}][c{k}]overlay=x=0:y=0:enable='gte(t,{inicio:.3f})':shortest=0[s{k}]")
    partes.append(f"[s{len(t.cartoes)}]format=yuv420p[v]")
    return entradas, partes


def _ffmpeg_trecho(entradas: list[str], partes: list[str], t: Trecho, saida: Path, idx_moldura: int) -> None:
    entradas_c, partes_c = _filtros_cartoes(t, primeiro_indice=idx_moldura + 1 + (1 if t.anel else 0))
    entradas = [*entradas, "-loop", "1", "-framerate", str(FPS), "-i", str(t.moldura)]
    if t.anel:
        entradas += ["-loop", "1", "-framerate", str(FPS), "-i", str(t.anel)]
    _ff([*entradas, *entradas_c, "-filter_complex", ";".join(partes + partes_c), "-map", "[v]",
         "-t", f"{t.duracao:.3f}", "-r", str(FPS), "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
         "-an", str(saida)])


def _expr_suave_t(d: float) -> str:
    """0 no início da cena, 1 no fim, com aceleração e freada suaves (em segundos, para crop/overlay)."""
    p = f"clip(t/{max(d, 0.01):.3f},0,1)"
    return f"({p}*{p}*(3-2*{p}))"


def _imagem_ampliada(origem: Path, largura: int, altura: int, foco_x: float, destino: Path) -> Path:
    """Imagem parada já do tamanho final (cobrindo e recortada no foco), feita uma vez só:
    o ffmpeg não precisa ampliar o quadro a cada frame."""
    from PIL import Image
    with Image.open(origem) as im:
        im = im.convert("RGB")
        esc = max(largura / im.width, altura / im.height)
        im = im.resize((round(im.width * esc), round(im.height * esc)), Image.LANCZOS)
        x = round((im.width - largura) * foco_x)
        y = (im.height - altura) // 2
        im.crop((x, y, x + largura, y + altura)).save(destino, quality=95)
    return destino


def _expr_suave(a: int, b: int) -> str:
    """0 até o quadro a, sobe suave até 1 no quadro b (smoothstep), para o zoom da câmera."""
    p = f"clip((on-{a})/{max(1, b - a)},0,1)"
    return f"({p}*{p}*(3-2*{p}))"


def _trecho_midia_ffmpeg(t: Trecho, saida: Path) -> None:
    """Cena "midia": clipe nítido na caixa central, a mesma imagem desfocada no fundo."""
    m, d = t.midia, t.duracao
    w, h = m.tamanho_na_caixa()
    entrada, prolonga = m.entrada(d)
    recorte = ""
    if m.recorte and not m.aproxima:
        x, y, rw, rh = m.recorte
        recorte = f"crop=iw*{rw:.4f}:ih*{rh:.4f}:iw*{x:.4f}:ih*{y:.4f},"
    if m.aproxima:
        # Câmera parada meio segundo no quadro inteiro e depois aproxima até o detalhe.
        rx, ry, f, _ = m.regiao_final()
        cx, cy = rx + f / 2, ry + f / 2
        a, b = round(0.5 * FPS), round(1.4 * FPS)
        s_ = _expr_suave(a, b)
        nitido = (f"scale={w * SUPER}:{h * SUPER}:flags=lanczos,zoompan=z='1+({1 / f:.4f}-1)*{s_}'"
                  f":x='clip(iw*(0.5+({cx:.4f}-0.5)*{s_})-iw/zoom/2,0,iw-iw/zoom)'"
                  f":y='clip(ih*(0.5+({cy:.4f}-0.5)*{s_})-ih/zoom/2,0,ih-ih/zoom)'"
                  f":d=1:s={w}x{h}:fps={FPS}")
    elif m.e_video:
        nitido = f"scale={w}:{h}"
    else:
        quadros = max(1, round(d * FPS))
        nitido = (f"scale={w * SUPER}:{h * SUPER}:flags=lanczos,"
                  f"zoompan=z='1+{ZOOM_IMAGEM}*{_expr_suave(0, quadros)}'"
                  f":x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:s={w}x{h}:fps={FPS}")
    borda = t.cor_borda.lstrip("#")
    topo = CAIXA_MIDIA["y"] + (CAIXA_MIDIA["a"] - (h + 2 * BORDA_MIDIA)) // 2
    partes = [
        f"[0:v]{recorte}fps={FPS},setsar=1{prolonga},trim=duration={d:.3f},setpts=PTS-STARTPTS,split[mb][ms]",
        "[mb]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,gblur=sigma=30,"
        "eq=brightness=-0.05:saturation=1.15[bg]",
        f"[ms]{nitido},setsar=1[nit]",
        "[1:v]format=rgba[m]",
        "[bg][m]overlay=x=0:y=0:shortest=0[sm]",
    ]
    if t.anel:
        partes.append(f"[2:v]format=rgba,fade=t=in:st={t.anel_inicio:.2f}:d=0.25:alpha=1[anel]")
        partes.append("[nit][anel]overlay=0:0:shortest=0[nita]")
        rotulo = "nita"
    else:
        rotulo = "nit"
    partes.append(f"[{rotulo}]pad={w + 2 * BORDA_MIDIA}:{h + 2 * BORDA_MIDIA}:{BORDA_MIDIA}:{BORDA_MIDIA}"
                  f":color=0x{borda}[caixa]")
    partes.append(f"[sm][caixa]overlay=x=(W-w)/2:y={topo}:shortest=0[s0]")
    _ffmpeg_trecho(entrada, partes, t, saida, idx_moldura=1)


def _trecho_tela_cheia_ffmpeg(t: Trecho, saida: Path) -> None:
    """Cena "tela_cheia": o clipe cobre a tela toda (recorte vertical), com barra de título por cima."""
    m, d = t.midia, t.duracao
    entrada, prolonga = m.entrada(d)
    recorte = ""
    if m.recorte:
        x, y, rw, rh = m.recorte
        recorte = f"crop=iw*{rw:.4f}:ih*{rh:.4f}:iw*{x:.4f}:ih*{y:.4f},"
    e = _expr_suave_t(d)
    if m.panoramica:
        x_expr = f"'(iw-ow)*(0.1+0.8*{e})'"     # passeia de um lado ao outro, sem tranco no começo e no fim
    else:
        x_expr = f"'(iw-ow)*{m.foco_x:.3f}'"
    base = f"[0:v]{recorte}fps={FPS},setsar=1{prolonga},trim=duration={d:.3f},setpts=PTS-STARTPTS,"
    if not m.e_video and not m.panoramica:
        quadros = max(1, round(d * FPS))
        cobre = f"{1080 * SUPER}:{1920 * SUPER}"
        partes = [base + f"scale={cobre}:force_original_aspect_ratio=increase:flags=lanczos,"
                  f"crop={cobre}:x={x_expr}:y='(ih-oh)/2',"
                  f"zoompan=z='1+{ZOOM_IMAGEM}*{_expr_suave(0, quadros)}':x='iw/2-(iw/zoom/2)'"
                  f":y='ih/2-(ih/zoom/2)':d=1:s=1080x1920:fps={FPS},setsar=1[f0]"]
    else:
        partes = [base + f"scale=1080:1920:force_original_aspect_ratio=increase,"
                  f"crop=1080:1920:x={x_expr}:y='(ih-oh)/2',setsar=1[f0]"]
    if t.anel:
        partes.append(f"[2:v]format=rgba,fade=t=in:st={t.anel_inicio:.2f}:d=0.25:alpha=1[anel]")
        partes.append("[f0][anel]overlay=0:0:shortest=0[f1]")
        base = "f1"
    else:
        base = "f0"
    partes += ["[1:v]format=rgba[m]", f"[{base}][m]overlay=x=0:y=0:shortest=0[s0]"]
    _ffmpeg_trecho(entrada, partes, t, saida, idx_moldura=1)


def _trecho_tomadas_ffmpeg(t: Trecho, saida: Path) -> None:
    """Estilo notícia: a cena troca de tomada a cada ~2,6 s (corte seco, como as páginas grandes)."""
    n = len(t.tomadas)
    base = t.duracao / n
    partes = []
    for k, tomada in enumerate(t.tomadas):
        d = base if k < n - 1 else t.duracao - base * (n - 1)
        arq = saida.with_name(f"{saida.stem}_t{k:02d}.mp4")
        _trecho_tela_cheia_ffmpeg(dataclasses.replace(t, midia=tomada, duracao=d, tomadas=[], anel=None), arq)
        partes.append(arq)
    lista = saida.with_name(saida.stem + "_tomadas.txt")
    lista.write_text("".join(f"file '{a.as_posix()}'\n" for a in partes), encoding="utf-8")
    _ff(["-f", "concat", "-safe", "0", "-i", str(lista), "-c", "copy", str(saida)])


def _trecho_ffmpeg(t: Trecho, saida: Path) -> None:
    if len(t.tomadas) > 1:
        return _trecho_tomadas_ffmpeg(t, saida)
    if t.midia is not None:
        if t.tipo == "tela_cheia":
            return _trecho_tela_cheia_ffmpeg(t, saida)
        return _trecho_midia_ffmpeg(t, saida)
    d = t.duracao
    # Fundo um pouco maior que a tela, com deriva lenta: dá vida sem distrair.
    t0 = t.inicio_global
    S = SUPER_FUNDO
    deriva = (f"crop={1080 * S}:{1920 * S}:x='(iw-ow)/2+(iw-ow)/2*sin(2*PI*(t+{t0:.3f})/14)'"
              f":y='(ih-oh)/2+(ih-oh)/2*cos(2*PI*(t+{t0:.3f})/18)',scale=1080:1920:flags=lanczos")
    fm = t.fundo_midia
    if fm is not None and fm.e_video:
        # Clipe do jogo atrás do cartão: recorte vertical no foco escolhido (o clipe já tem movimento).
        entrada_fundo, prolonga = fm.entrada(d)
        cobrir = (f"scale=1080:1920:force_original_aspect_ratio=increase,"
                  f"crop=1080:1920:x='(iw-1080)*{fm.foco_x:.3f}':y='(ih-1920)/2'{prolonga}")
    elif fm is not None or not t.fundo_e_video:
        origem, foco = (fm.caminho, fm.foco_x) if fm is not None else (t.fundo, 0.5)
        ampliada = _imagem_ampliada(Path(origem), 1166 * S, 2074 * S, foco,
                                    saida.with_name(saida.stem + "_fundo.jpg"))
        entrada_fundo = ["-loop", "1", "-framerate", str(FPS), "-i", str(ampliada)]
        cobrir = deriva
    else:
        entrada_fundo = ["-stream_loop", "-1", "-i", str(t.fundo)]
        cobrir = "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920"
    partes = [f"[0:v]{cobrir},fps={FPS},setsar=1,trim=duration={d:.3f},setpts=PTS-STARTPTS[f0]",
              "[1:v]format=rgba[m]", "[f0][m]overlay=x=0:y=0:shortest=0[s0]"]
    _ffmpeg_trecho(entrada_fundo, partes, t, saida, idx_moldura=1)


def parametros_instagram() -> list[str]:
    """Saída dentro da especificação de Reels da Meta: H.264 4:2:0, GOP fechado, até 25 Mbps
    (usamos teto de 16), AAC 128k 48 kHz estéreo, moov no início e SEM edit list (o ffmpeg grava uma
    por padrão para o atraso do AAC, e o Instagram recusa com ProcessingFailedError)."""
    return ["-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-maxrate", "16M", "-bufsize", "32M",
            "-profile:v", "high", "-level", "4.2", "-pix_fmt", "yuv420p", "-g", str(FPS * 2),
            "-x264-params", "open-gop=0", "-c:a", "aac", "-b:a", "128k", "-ar", "48000", "-ac", "2",
            "-movflags", "+faststart", "-use_editlist", "0"]


def conformar_para_instagram(arquivo: Path, alvo_mb: float | None = None) -> Path:
    """Recodifica um vídeo já pronto com os parâmetros acima (no lugar do original). Com `alvo_mb`,
    limita a taxa para o arquivo ficar perto desse tamanho (o Instagram recusou Reels acima de ~10 MB)."""
    tmp = arquivo.with_name(arquivo.stem + "_ig.mp4")
    params = parametros_instagram()
    if alvo_mb:
        from .sonda import duracao
        kbps = max(600, int(alvo_mb * 8192 / max(duracao(arquivo), 1)) - 140)
        i = params.index("-crf")
        params[i:i + 2] = ["-b:v", f"{kbps}k"]
        j = params.index("-maxrate")
        params[j + 1], params[j + 3] = f"{int(kbps * 1.3)}k", f"{kbps * 2}k"
    _ff(["-i", str(arquivo), "-map", "0:v:0", "-map", "0:a:0?", *params, str(tmp)])
    tmp.replace(arquivo)
    return arquivo


def passos_do_titulo(n_palavras: int) -> list[int]:
    """Quantas palavras aparecem em cada passo (o último passo é o cartão completo, que vem depois)."""
    passos = list(range(1, n_palavras))
    if len(passos) > MAX_PASSOS_TITULO - 1:
        passos = passos[:MAX_PASSOS_TITULO - 1]
    return passos


def filtro_barra(duracao: float, cor: str) -> str:
    """Barra fina no topo que enche do começo ao fim do vídeo (trilha escura por baixo)."""
    c = cor.lstrip("#")
    return (f"color=c=black@0.35:s=1080x{BARRA_ALTURA}:r={FPS}[trilha];"
            f"color=c=0x{c}:s=1080x{BARRA_ALTURA}:r={FPS}[barra];"
            f"[vl][trilha]overlay=x=0:y=0:shortest=1[vt];"
            f"[vt][barra]overlay=x='-w+W*t/{max(duracao, 0.1):.3f}':y=0:shortest=1[v]")


def filtro_transicoes(duracoes: list[float]) -> tuple[str, str]:
    """Cadeia de xfade: a cena i entra no segundo em que a narração dela começa (soma das anteriores)."""
    if len(duracoes) == 1:
        return "[0:v]null[vx]", "vx"
    partes, atual, inicio = [], "0:v", 0.0
    for i in range(1, len(duracoes)):
        inicio += duracoes[i - 1]
        saida = f"x{i}"
        partes.append(f"[{atual}][{i}:v]xfade=transition={TRANSICOES[(i - 1) % len(TRANSICOES)]}"
                      f":duration={TRANSICAO}:offset={inicio:.3f}[{saida}]")
        atual = saida
    return ";".join(partes), atual


def _juntar_com_transicoes(arquivos: list[Path], duracoes: list[float], saida: Path) -> None:
    entradas = [x for a in arquivos for x in ("-i", str(a))]
    filtro, rotulo = filtro_transicoes(duracoes)
    _ff([*entradas, "-filter_complex", filtro, "-map", f"[{rotulo}]", "-r", str(FPS),
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p", "-an", str(saida)])


def _juntar_narracao(trechos: list[Trecho], saida: Path) -> None:
    entradas, filtros, rotulos = [], [], []
    for i, t in enumerate(trechos):
        entradas += ["-i", str(t.fala.audio)]
        filtros.append(f"[{i}:a]aformat=sample_rates=48000:channel_layouts=stereo,"
                       f"apad=whole_dur={t.duracao:.3f},atrim=duration={t.duracao:.3f}[a{i}]")
        rotulos.append(f"[a{i}]")
    filtro = ";".join(filtros) + f";{''.join(rotulos)}concat=n={len(trechos)}:v=0:a=1[narr]"
    _ff([*entradas, "-filter_complex", filtro, "-map", "[narr]", "-c:a", "pcm_s16le", str(saida)])


PASTA_GAMEPLAY = "saida/cache/gameplay/"   # cortes da gravação do Vinicius (ficam no cache das rodadas)


def arquivo_gameplay(cena: Cena) -> str:
    """O corte da gravação do Vinicius usado na cena (em `midia` ou, no gancho, em `fundo_clipe`)."""
    for campo in (cena.midia, cena.fundo_clipe):
        if campo and campo.replace("\\", "/").startswith(PASTA_GAMEPLAY):
            return campo
    return ""


def e_gameplay(cena: Cena) -> bool:
    return bool(arquivo_gameplay(cena))


def _tomada_gameplay(cena: Cena, duracao: float, andamento: dict[str, float]) -> MidiaCena:
    """Uma tomada só, do ponto em que a cena anterior do mesmo trecho parou."""
    arquivo = arquivo_gameplay(cena)
    inicio = (cena.midia_inicio or 0.0 if cena.midia == arquivo else 0.0) + andamento.get(arquivo, 0.0)
    falsa = cena.model_copy(update={"tipo": "tela_cheia", "midia": arquivo, "midia_inicio": inicio,
                                    "midia_fim": inicio + duracao,
                                    "midia_recorte": None, "midia_animacao": "nenhuma", "midia_destaque": None,
                                    "panoramica": False})
    return MidiaCena.da_cena(falsa)


def _tomadas_da_cena(cena: Cena, duracao: float, evitar: set, usadas: list[str], semente: str) -> list[MidiaCena]:
    """Estilo notícia: 1 tomada a cada ~2,6 s, cada uma de uma imagem ou trecho diferente.
    Usa a busca/arquivo da cena (midia ou fundo_clipe); a primeira respeita o arquivo escolhido."""
    from . import estilo_noticia
    from .catalogo import chave_uso
    consulta = cena.midia or cena.fundo_clipe or "busca:vice city cidade"
    tomadas: list[MidiaCena] = []
    for k in range(estilo_noticia.tomadas_por_cena(duracao)):
        titulo = re.sub(r"[*_]", "", cena.titulo or "")
        alvo = consulta if (k == 0 or consulta.startswith("busca:")) else (
            cena.fundo_clipe or f"busca:{titulo} vice city")
        falsa = cena.model_copy(update={"midia": alvo, "tipo": "tela_cheia", "midia_recorte": None,
                                        "midia_animacao": "nenhuma", "midia_destaque": None,
                                        "panoramica": bool(k % 2)})
        try:
            t = MidiaCena.da_cena(falsa, evitar=evitar | set(usadas), semente=f"{semente}|{k}")
        except (FileNotFoundError, OSError, subprocess.CalledProcessError):
            continue          # arquivo do catálogo ausente: segue com as tomadas que deram certo
        if t.escolha is not None:
            usadas.append(chave_uso(t.escolha))
        tomadas.append(t)
    return tomadas


def copia_para_telegram(final: Path) -> Path:
    """Cópia leve (~8 a 12 MB) para o Telegram: o vídeo final em 60 fps passa de 30 MB e o Telegram
    devolve Gateway Timeout. 1080x1920 a 30 fps com taxa limitada: no app do Instagram fica igual."""
    copia = final.with_name(final.stem + "_tg.mp4")
    _ff(["-i", str(final), "-vf", "fps=30", "-c:v", "libx264", "-preset", "veryfast", "-crf", "24",
         "-maxrate", "2500k", "-bufsize", "5000k", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k",
         "-movflags", "+faststart", str(copia)])
    return copia


def ajustar_ritmo(marca: Marca, video: Video) -> Marca:
    """Reel com trecho de jogo precisa ficar abaixo de 60 s: se a narração estimada passa de 57 s, acelera
    a voz do Azure só neste vídeo (no máximo +12% sobre a velocidade normal da marca)."""
    from .qualidade import ACELERACAO_MAXIMA, ALVO_REEL_S, palavras_por_segundo
    voz = marca.dados.get("voz", {})
    if voz.get("provedor") != "azure" or not video.usa_midia_de_terceiros:
        return marca
    palavras = sum(len(c.narracao.split()) for c in video.cenas)
    estimativa = palavras / palavras_por_segundo(marca)
    if estimativa <= ALVO_REEL_S:
        return marca
    fator = min(estimativa / ALVO_REEL_S, ACELERACAO_MAXIMA)
    base = float(str(voz["azure"].get("velocidade", "+0%")).strip("%+")) / 100
    nova = f"+{round(((1 + base) * fator - 1) * 100)}%"
    print(f"  narração de ~{estimativa:.0f}s: voz em {nova} neste vídeo para caber em {ALVO_REEL_S:.0f}s")
    dados = json.loads(json.dumps(marca.dados))
    dados["voz"]["azure"]["velocidade"] = nova
    return dataclasses.replace(marca, dados=dados)


def renderizar_video(marca: Marca, video: Video, pasta_saida: Path, voz_forcada: Optional[str] = None,
                     hoje: Optional[date] = None, musica: Optional[Path] = None,
                     registrar_clipes: bool = True) -> dict:
    hoje = hoje or video.data   # contagens são calculadas para o dia da publicação
    marca = ajustar_ritmo(marca, video)
    pasta_saida = pasta_saida.resolve()
    trabalho = pasta_saida / "_trabalho" / video.id
    if trabalho.exists():
        shutil.rmtree(trabalho)
    trabalho.mkdir(parents=True)

    voz = criar_voz(marca, voz_forcada)
    serie = marca.nome_serie(video.serie)
    trechos: list[Trecho] = []
    molduras: dict[str, Path] = {}

    from . import variedade
    from .catalogo import chave_uso
    evitar = variedade.imagens_de_outros(video)     # o Reel não repete imagem nem plano de outro post
    capas_vizinhas = variedade.assuntos_de_capas(video)
    estilo_capa = variedade.estilo_capa(video)
    usadas: list[str] = []
    midia_capa: Optional[tuple[str, float]] = None
    from . import estilo_noticia
    noticia = estilo_noticia.ligado(marca)

    with desenhista() as d:
        fundo_marca = marca.pasta_assets / "fundo.png"
        if not fundo_marca.exists():
            desenhar_fundo(d, marca, fundo_marca)

        # números e "R$" por extenso só em português; em espanhol a voz lê do jeito certo sozinha
        portugues = marca.dados.get("idioma", "pt") == "pt"
        textos = [texto_para_fala(preencher_variaveis(c.narracao, hoje)) if portugues
                  else preencher_variaveis(c.narracao, hoje).replace("*", "") for c in video.cenas]
        # o roteiro inteiro numa narração só: fala corrida, sem pausa nem "recomeço" a cada cena
        falas, continua = falar_continuo(voz, textos, trabalho)

        andamento_gameplay: dict[str, float] = {}
        for i, cena in enumerate(video.cenas):
            dados = cena.model_dump()
            for campo in ("titulo", "texto", "numero", "rotulo", "rodape", "narracao", "kicker", "fonte"):
                dados[campo] = preencher_variaveis(dados[campo], hoje)
            dados["itens"] = [preencher_variaveis(x, hoje) for x in dados["itens"]]

            fala = falas[i]
            if continua:   # o respiro natural entre as frases já está no áudio
                ultima = i == len(video.cenas) - 1
                duracao = max(DURACAO_MINIMA_CENA_CONTINUA, fala.duracao + (PAUSA_FINAL if ultima else 0.0))
            else:
                duracao = max(DURACAO_MINIMA_CENA, fala.duracao + PAUSA_ENTRE_CENAS)

            # a primeira cena vira a capa: também não repete o rosto/lugar da capa de outro post
            evitar_aqui = evitar | set(usadas) | (capas_vizinhas if i == 0 else set())
            if noticia and e_gameplay(cena):
                # gravação própria: o trecho corre contínuo de uma cena para a outra, sem trocar de imagem
                tomadas = [_tomada_gameplay(cena, duracao, andamento_gameplay)]
                arq = arquivo_gameplay(cena)
                andamento_gameplay[arq] = andamento_gameplay.get(arq, 0.0) + duracao
            elif noticia:
                tomadas = _tomadas_da_cena(cena, duracao, evitar_aqui, usadas, f"{video.id}|{i}")
                if midia_capa is None and tomadas:
                    midia_capa = (str(tomadas[0].caminho), tomadas[0].inicio or 0.0)
                trechos.append(Trecho([], estilo_noticia.moldura_vazia(trabalho / "moldura_vazia.png"),
                                      fundo_marca, False, fala, duracao, sum(x.duracao for x in trechos),
                                      tomadas[0] if tomadas else None, marca.cores["destaque"],
                                      "tela_cheia" if tomadas else "texto", tomadas=tomadas))
                for tomada in tomadas:
                    if registrar_clipes and tomada.escolha is not None:
                        registrar_uso(tomada.escolha)
                continue
            midia = MidiaCena.da_cena(cena, evitar=evitar_aqui, semente=video.id) \
                if cena.tipo in TIPOS_COM_MIDIA else None
            if midia is not None and midia.escolha is not None:
                usadas.append(chave_uso(midia.escolha))
            fundo_midia = MidiaCena.da_cena(cena, fundo=True, evitar=evitar_aqui | set(usadas), semente=video.id) \
                if cena.fundo_clipe else None
            if fundo_midia is not None and fundo_midia.escolha is not None:
                usadas.append(chave_uso(fundo_midia.escolha))
            if midia_capa is None:          # a imagem da capa do Reel: a primeira cena com imagem
                for m in (fundo_midia, midia):
                    if m is not None:
                        midia_capa = (str(m.caminho), m.inicio or 0.0)
                        break
            broll = buscar_broll(cena.broll) if cena.broll and midia is None and fundo_midia is None else None
            anel, anel_inicio = None, 0.5
            if midia is not None and midia.destaque:
                if cena.tipo == "midia":
                    w, h = midia.tamanho_na_caixa()
                    px = _anel_em_pixels(midia.destaque, midia.regiao_final(), w, h)
                    anel_inicio = 1.55 if midia.aproxima else 0.5
                elif not midia.panoramica:
                    w, h = 1080, 1920
                    px = _anel_em_pixels(midia.destaque, midia.regiao_tela_cheia(), w, h)
                else:
                    px = None
                if px:
                    anel = desenhar_anel(w, h, *px, marca.cores["destaque"], trabalho / f"anel_{i:02d}.png")
            produto = None
            if cena.produto is not None:
                produto = video.produtos[cena.produto].model_copy()
                produto.imagem = imagem_produto(produto.imagem)

            solido = broll is None and midia is None and fundo_midia is None
            chave_moldura = "solida" if solido else "video"
            if chave_moldura not in molduras:
                html_m = montar_html(marca, dados, serie=serie, fundo_solido=solido, modo="moldura")
                molduras[chave_moldura] = d.desenhar(html_m, trabalho / f"moldura_{chave_moldura}.png")
            n_itens = len(dados["itens"]) if cena.tipo == "lista" else (
                len(dados["linhas"]) if cena.tipo == "comparativo" else 1)
            cartoes = []
            # título palavra por palavra no começo da cena (cartões com título, menos o final)
            n_palavras = len(re.findall(r"\S+", re.sub(r"[*_]", "", dados.get("titulo") or "")))
            if cena.tipo not in ("cta",) and n_palavras > 1:
                for passo, mostrar in enumerate(passos_do_titulo(n_palavras)):
                    html_doc = montar_html(marca, dados, serie=serie, produto=produto, fundo_solido=True,
                                           revelar=1 if n_itens > 1 else None, modo="cartao",
                                           palavras_titulo=mostrar)
                    cartoes.append((d.desenhar(html_doc, trabalho / f"cartao_{i:02d}_t{passo:02d}.png"),
                                    passo * PASSO_PALAVRA))
            atraso = len(cartoes) * PASSO_PALAVRA
            for k, inicio in enumerate(momentos_de_revelacao(n_itens, fala.palavras), start=1):
                revelar = k if n_itens > 1 else None
                html_doc = montar_html(marca, dados, serie=serie, produto=produto,
                                       fundo_solido=True, revelar=revelar, modo="cartao")
                cartoes.append((d.desenhar(html_doc, trabalho / f"cartao_{i:02d}_{k:02d}.png"),
                                max(inicio, atraso) if k == 1 else inicio))
            inicio_global = sum(x.duracao for x in trechos)
            trechos.append(Trecho(cartoes, molduras[chave_moldura], broll or fundo_marca, broll is not None,
                                  fala, duracao, inicio_global, midia, marca.cores["destaque"], cena.tipo,
                                  fundo_midia, anel, anel_inicio))
            for usada in (midia, fundo_midia):
                if registrar_clipes and usada is not None and usada.escolha is not None:
                    registrar_uso(usada.escolha)

    # trechos de vídeo
    arquivos = []
    for i, t in enumerate(trechos):
        arq = trabalho / f"trecho_{i:02d}.mp4"
        # cada cena (menos a última) dura TRANSICAO a mais: é o pedaço que se mistura com a seguinte
        extra = TRANSICAO if i < len(trechos) - 1 else 0.0
        _trecho_ffmpeg(dataclasses.replace(t, duracao=t.duracao + extra), arq)
        arquivos.append(arq)
    mudo = trabalho / "mudo.mp4"
    _juntar_com_transicoes(arquivos, [t.duracao for t in trechos], mudo)

    # narração contínua + palavras com tempo global
    narr = trabalho / "narracao.wav"
    _juntar_narracao(trechos, narr)
    palavras: list[Palavra] = []
    deslocamento = 0.0
    for t in trechos:
        palavras += [Palavra(p.texto, p.inicio + deslocamento, p.fim + deslocamento) for p in t.fala.palavras]
        deslocamento += t.duracao
    ass = gerar_ass(marca, palavras, trabalho / "legenda.ass",
                    topo=estilo_noticia.LEGENDA_MARGEM_TOPO if noticia else None)
    manchete = None
    if noticia:
        primeira = video.cenas[0]
        selo = next((c.selo for c in video.cenas if c.selo), None)
        fonte_txt = next((c.fonte for c in video.cenas if c.fonte), "")
        credito = next((c.credito for c in video.cenas if c.credito), "") or "Imagens: Rockstar Games"
        manchete = estilo_noticia.desenhar_manchete(marca, preencher_variaveis(primeira.titulo, hoje), selo,
                                                    fonte_txt, credito, trabalho / "manchete.png")

    # final: legenda queimada, áudio normalizado, pronto para celular
    final = pasta_saida / f"{video.data.isoformat()}_{video.id}.mp4"
    # Caminhos relativos à pasta de trabalho: no Windows, o "C:" de um caminho absoluto
    # quebra o filtro de legenda do ffmpeg.
    fontes = Path(os.path.relpath(RAIZ / "assets" / "fontes", trabalho)).as_posix()
    entradas = ["-i", str(mudo), "-i", str(narr)]
    if musica and musica.exists():
        entradas += ["-stream_loop", "-1", "-i", str(musica)]
        vol = marca.video.get("musica_volume_db", -24)
        audio = (f"[2:a]volume={vol}dB[m];[1:a][m]amix=inputs=2:duration=first:dropout_transition=0,"
                 f"loudnorm=I=-14:TP=-1.5:LRA=11[a]")
    else:
        audio = "[1:a]loudnorm=I=-14:TP=-1.5:LRA=11[a]"
    base_video = "[0:v]"
    if manchete is not None:
        idx = 3 if (musica and musica.exists()) else 2
        entradas += ["-loop", "1", "-framerate", str(FPS), "-i", str(manchete)]
        audio = f"[0:v][{idx}:v]overlay=0:0:shortest=1[vm];" + audio
        base_video = "[vm]"
    filtro = (f"{base_video}ass='{ass.name}':fontsdir='{fontes}'[vl];"
              f"{filtro_barra(deslocamento, marca.cores['destaque'])};{audio}")
    _ff([*entradas, "-filter_complex", filtro, "-map", "[v]", "-map", "[a]", *parametros_instagram(),
         "-t", f"{deslocamento:.3f}", str(final)], cwd=trabalho)

    variedade.registrar(video, usadas, estilo_capa)
    # capa: quadro do primeiro cartão, já com o fundo
    capa = final.with_suffix(".jpg")
    _ff(["-ss", "0.6", "-i", str(final), "-frames:v", "1", "-q:v", "2", str(capa)])
    copia_para_telegram(final)

    info = {
        "video": final.name, "capa": capa.name, "duracao_s": round(deslocamento, 2),
        "midia_capa": midia_capa, "estilo_capa": estilo_capa,
        "cenas": len(trechos), "palavras": len(palavras), "voz": type(getattr(voz, "voz", voz)).__name__,
    }
    (trabalho / "info.json").write_text(json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8")
    return info
