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
import shutil
import subprocess
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
from .voz import Fala, Palavra, criar_voz, texto_para_fala

FPS = 30
PAUSA_ENTRE_CENAS = 0.18
DURACAO_MINIMA_CENA = 1.6
ENTRADA_CARTAO = 0.28
EXT_IMAGEM = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
BORDA_MIDIA = 4          # moldura colorida em volta do clipe, em pixels
ZOOM_IMAGEM = 0.08       # imagem parada ganha uma aproximação lenta de 8% durante a cena


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
            escolha = resolver_midia(cena.fundo_clipe, cena.fundo_inicio, evitar=evitar, semente=semente)
        else:
            escolha = resolver_midia(cena.midia, cena.midia_inicio, cena.midia_fim, evitar=evitar, semente=semente)
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
        nitido = (f"scale={w * 2}:{h * 2},zoompan=z='1+({1 / f:.4f}-1)*{s_}'"
                  f":x='clip(iw*(0.5+({cx:.4f}-0.5)*{s_})-iw/zoom/2,0,iw-iw/zoom)'"
                  f":y='clip(ih*(0.5+({cy:.4f}-0.5)*{s_})-ih/zoom/2,0,ih-ih/zoom)'"
                  f":d=1:s={w}x{h}:fps={FPS}")
    elif m.e_video:
        nitido = f"scale={w}:{h}"
    else:
        quadros = max(1, round(d * FPS))
        nitido = (f"scale={w * 2}:{h * 2},zoompan=z='1+{ZOOM_IMAGEM}*on/{quadros}'"
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
    if m.panoramica:
        x_expr = f"'(iw-ow)*(0.1+0.8*t/{d:.3f})'"     # passeia de um lado ao outro durante a cena
    else:
        x_expr = f"'(iw-ow)*{m.foco_x:.3f}'"
    zoom = "" if m.e_video else f",scale=iw*(1+{ZOOM_IMAGEM}*t/{d:.3f}):-2:eval=frame"
    partes = [
        f"[0:v]{recorte}fps={FPS},setsar=1{prolonga},trim=duration={d:.3f},setpts=PTS-STARTPTS,"
        f"scale=1080:1920:force_original_aspect_ratio=increase{zoom},"
        f"crop=1080:1920:x={x_expr}:y='(ih-oh)/2',setsar=1[f0]",
    ]
    if t.anel:
        partes.append(f"[2:v]format=rgba,fade=t=in:st={t.anel_inicio:.2f}:d=0.25:alpha=1[anel]")
        partes.append("[f0][anel]overlay=0:0:shortest=0[f1]")
        base = "f1"
    else:
        base = "f0"
    partes += ["[1:v]format=rgba[m]", f"[{base}][m]overlay=x=0:y=0:shortest=0[s0]"]
    _ffmpeg_trecho(entrada, partes, t, saida, idx_moldura=1)


def _trecho_ffmpeg(t: Trecho, saida: Path) -> None:
    if t.midia is not None:
        if t.tipo == "tela_cheia":
            return _trecho_tela_cheia_ffmpeg(t, saida)
        return _trecho_midia_ffmpeg(t, saida)
    d = t.duracao
    # Fundo um pouco maior que a tela, com deriva lenta: dá vida sem distrair.
    t0 = 0.0 if t.fundo_e_video else t.inicio_global
    deriva = (f"crop=1080:1920:x='(iw-ow)/2+(iw-ow)/2*sin(2*PI*(t+{t0:.3f})/14)'"
              f":y='(ih-oh)/2+(ih-oh)/2*cos(2*PI*(t+{t0:.3f})/18)'")
    if t.fundo_midia is not None:
        # Clipe do jogo atrás do cartão: recorte vertical no foco escolhido, com a mesma deriva.
        fm = t.fundo_midia
        entrada_fundo, prolonga = fm.entrada(d)
        cobrir = (f"scale=1166:2074:force_original_aspect_ratio=increase,"
                  f"crop=1166:2074:x='(iw-1166)*{fm.foco_x:.3f}':y='(ih-2074)/2',{deriva}{prolonga}")
    else:
        if t.fundo_e_video:
            entrada_fundo = ["-stream_loop", "-1", "-i", str(t.fundo)]
        else:
            entrada_fundo = ["-loop", "1", "-framerate", str(FPS), "-i", str(t.fundo)]
        cobrir = f"scale=1166:2074:force_original_aspect_ratio=increase,crop=1166:2074,{deriva}"
    partes = [f"[0:v]{cobrir},fps={FPS},setsar=1,trim=duration={d:.3f},setpts=PTS-STARTPTS[f0]",
              "[1:v]format=rgba[m]", "[f0][m]overlay=x=0:y=0:shortest=0[s0]"]
    _ffmpeg_trecho(entrada_fundo, partes, t, saida, idx_moldura=1)


def _juntar_narracao(trechos: list[Trecho], saida: Path) -> None:
    entradas, filtros, rotulos = [], [], []
    for i, t in enumerate(trechos):
        entradas += ["-i", str(t.fala.audio)]
        filtros.append(f"[{i}:a]aformat=sample_rates=48000:channel_layouts=stereo,"
                       f"apad=whole_dur={t.duracao:.3f},atrim=duration={t.duracao:.3f}[a{i}]")
        rotulos.append(f"[a{i}]")
    filtro = ";".join(filtros) + f";{''.join(rotulos)}concat=n={len(trechos)}:v=0:a=1[narr]"
    _ff([*entradas, "-filter_complex", filtro, "-map", "[narr]", "-c:a", "pcm_s16le", str(saida)])


def renderizar_video(marca: Marca, video: Video, pasta_saida: Path, voz_forcada: Optional[str] = None,
                     hoje: Optional[date] = None, musica: Optional[Path] = None,
                     registrar_clipes: bool = True) -> dict:
    hoje = hoje or video.data   # contagens são calculadas para o dia da publicação
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
    estilo_capa = variedade.estilo_capa(video)
    usadas: list[str] = []
    midia_capa: Optional[tuple[str, float]] = None

    with desenhista() as d:
        fundo_marca = marca.pasta_assets / "fundo.png"
        if not fundo_marca.exists():
            desenhar_fundo(d, marca, fundo_marca)

        for i, cena in enumerate(video.cenas):
            dados = cena.model_dump()
            for campo in ("titulo", "texto", "numero", "rotulo", "rodape", "narracao", "kicker", "fonte"):
                dados[campo] = preencher_variaveis(dados[campo], hoje)
            dados["itens"] = [preencher_variaveis(x, hoje) for x in dados["itens"]]

            # números e "R$" por extenso só em português; em espanhol a voz lê do jeito certo sozinha
            texto_falado = texto_para_fala(dados["narracao"]) if marca.dados.get("idioma", "pt") == "pt" \
                else dados["narracao"].replace("*", "")
            fala = voz.falar(texto_falado, trabalho / f"fala_{i:02d}")
            duracao = max(DURACAO_MINIMA_CENA, fala.duracao + PAUSA_ENTRE_CENAS)

            midia = MidiaCena.da_cena(cena, evitar=evitar | set(usadas), semente=video.id) \
                if cena.tipo in TIPOS_COM_MIDIA else None
            if midia is not None and midia.escolha is not None:
                usadas.append(chave_uso(midia.escolha))
            fundo_midia = MidiaCena.da_cena(cena, fundo=True, evitar=evitar | set(usadas), semente=video.id) \
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
            for k, inicio in enumerate(momentos_de_revelacao(n_itens, fala.palavras), start=1):
                revelar = k if n_itens > 1 else None
                html_doc = montar_html(marca, dados, serie=serie, produto=produto,
                                       fundo_solido=True, revelar=revelar, modo="cartao")
                cartoes.append((d.desenhar(html_doc, trabalho / f"cartao_{i:02d}_{k:02d}.png"), inicio))
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
        _trecho_ffmpeg(t, arq)
        arquivos.append(arq)
    lista = trabalho / "lista.txt"
    lista.write_text("".join(f"file '{a.as_posix()}'\n" for a in arquivos), encoding="utf-8")
    mudo = trabalho / "mudo.mp4"
    _ff(["-f", "concat", "-safe", "0", "-i", str(lista), "-c", "copy", str(mudo)])

    # narração contínua + palavras com tempo global
    narr = trabalho / "narracao.wav"
    _juntar_narracao(trechos, narr)
    palavras: list[Palavra] = []
    deslocamento = 0.0
    for t in trechos:
        palavras += [Palavra(p.texto, p.inicio + deslocamento, p.fim + deslocamento) for p in t.fala.palavras]
        deslocamento += t.duracao
    ass = gerar_ass(marca, palavras, trabalho / "legenda.ass")

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
    filtro = f"[0:v]ass='{ass.name}':fontsdir='{fontes}'[v];{audio}"
    _ff([*entradas, "-filter_complex", filtro, "-map", "[v]", "-map", "[a]",
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
         "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-movflags", "+faststart",
         "-t", f"{deslocamento:.3f}", str(final)], cwd=trabalho)

    variedade.registrar(video, usadas, estilo_capa)
    # capa: quadro do primeiro cartão, já com o fundo
    capa = final.with_suffix(".jpg")
    _ff(["-ss", "0.6", "-i", str(final), "-frames:v", "1", "-q:v", "2", str(capa)])

    info = {
        "video": final.name, "capa": capa.name, "duracao_s": round(deslocamento, 2),
        "midia_capa": midia_capa, "estilo_capa": estilo_capa,
        "cenas": len(trechos), "palavras": len(palavras), "voz": type(getattr(voz, "voz", voz)).__name__,
    }
    (trabalho / "info.json").write_text(json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8")
    return info
