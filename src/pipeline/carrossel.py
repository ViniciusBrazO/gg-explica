"""Carrossel 4:5 (1080x1350): cada cena da pauta vira um slide em JPEG.

Modelo padrão "revista" (templates/slide_revista.html), no estilo das grandes páginas de games:
imagem oficial ocupando o slide inteiro, manchete condensada com palavra-chave colorida, etiqueta
(selo ou chamada), crédito da imagem. Papéis de slide:

- capa:   a primeira cena (gancho)
- fato:   texto com imagem inteira, título colorido e corpo embaixo (estilo IGN)
- lista:  guia com ícones e "Título: descrição" por item (estilo Seek Key)
- tabela: lista com `"estilo": "tabela"`, dado que se compara (estilo Fluid Game)
- final:  a cena cta, com o @ e o convite para salvar e mandar

O mesmo post também sai como Reel (`reel.mp4`, 1080x1920) e com a capa vertical do Reel
(`capa_reel.jpg`), porque Reel é o que leva a página a quem ainda não segue.
O guia de estilo completo está em docs/guia_de_estilo.md.
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from .cartoes import _ambiente, desenhista
from .catalogo import resolver_midia
from .marca import RAIZ, Marca
from .modelos import Video
from .montagem import EXT_IMAGEM, preencher_variaveis

LARGURA, ALTURA = 1080, 1350
ALTURA_REEL = 1920
TEXTO_ARRASTE = {"pt": "Arraste para o lado", "es": "Desliza para ver más"}
TEXTO_CONVITE = {"pt": "Salva e manda pra quem vai jogar", "es": "Guárdalo y compártelo con quien va a jugar"}
SEGUNDOS_POR_SLIDE = 2.6


def _imagem_da_cena(cena, trabalho: Path, i: int, evitar: set | None = None, semente: str = "") -> Path | None:
    origem = cena.midia or cena.fundo_clipe
    if not origem:
        return None
    escolha = resolver_midia(origem, cena.midia_inicio if cena.midia else cena.fundo_inicio,
                             evitar=evitar, semente=semente)
    if escolha is None or not escolha.caminho.exists():
        return None
    if escolha.caminho.suffix.lower() in EXT_IMAGEM:
        return escolha.caminho
    quadro = trabalho / f"quadro_{i:02d}.jpg"     # de um clipe, usa o quadro do meio do trecho
    meio = escolha.inicio + ((escolha.fim - escolha.inicio) / 2 if escolha.fim else 0.5)
    subprocess.run(["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-y", "-ss", f"{meio:.2f}", "-i",
                    str(escolha.caminho), "-frames:v", "1", "-q:v", "2", str(quadro)], check=True)
    return quadro


def papel_do_slide(video: Video, i: int) -> str:
    cena = video.cenas[i]
    if i == 0:
        return "capa"
    if cena.tipo == "cta":
        return "final"
    if cena.tipo == "lista":
        return "tabela" if cena.estilo == "tabela" else "lista"
    return "fato"


def dividir_item(item: str) -> dict:
    """'Câmera: Uma câmera filmou o crime' -> título colorido + descrição. Sem ':' vira só descrição.
    Um emoji ou símbolo no começo ('📷 Câmera: ...') vira o ícone do item."""
    icone = ""
    if item and not item[0].isalnum() and item[0] not in "*\"'(":
        icone, _, item = item.partition(" ")
    titulo, sep, desc = item.partition(":")
    if not sep:
        return {"icone": icone, "t": "", "d": item.strip()}
    desc = desc.strip()
    return {"icone": icone, "t": titulo.strip(), "d": desc[:1].upper() + desc[1:]}


def _foco_vertical(foto: Path | None) -> int:
    """Arte em pé (retrato): mostra a parte de cima, onde ficam os rostos; o texto cobre a de baixo."""
    if foto is None:
        return 50
    try:
        from PIL import Image
        with Image.open(foto) as im:
            return 28 if im.height > im.width * 1.2 else 50
    except OSError:
        return 50


def modelo_da_marca(marca: Marca) -> str:
    return (marca.dados.get("carrossel") or {}).get("modelo", "revista")


def montar_slide(marca: Marca, video: Video, i: int, foto: Path | None, *, vertical: bool = False,
                 mostrar_arraste: bool = True, estilo_capa: str = "base") -> str:
    cena = video.cenas[i].model_dump()
    for campo in ("titulo", "texto", "kicker", "fonte", "rodape"):
        cena[campo] = preencher_variaveis(cena[campo], video.data)
    cena["itens"] = [preencher_variaveis(x, video.data) for x in cena["itens"]]
    idioma = marca.dados.get("idioma", "pt")
    papel = "capa" if vertical else papel_do_slide(video, i)
    modelo = modelo_da_marca(marca)
    arquivo = "slide.html" if modelo == "classico" else f"slide_{modelo}.html"
    logo = marca.pasta_assets / "avatar.png"
    return _ambiente().get_template(arquivo).render(
        fontes=(RAIZ / "assets" / "fontes").as_uri(), cores=marca.cores, marca_id=marca.id,
        marca_nome=marca.nome, arroba=marca.dados["arroba"], selos=marca.dados.get("selos", {}),
        serie=marca.nome_serie(video.serie), cena=cena, papel=papel, n=i + 1, total=len(video.cenas),
        itens=[dividir_item(x) for x in cena["itens"]],
        foto=foto.resolve().as_uri() if foto else "", foco=round(video.cenas[i].foco_x * 100),
        estilo_capa=estilo_capa,
        foco_y=_foco_vertical(foto),
        logo=logo.resolve().as_uri() if logo.exists() else "", idioma=idioma,
        largura=LARGURA, altura=ALTURA_REEL if vertical else ALTURA, mostrar_arraste=mostrar_arraste,
        arraste=TEXTO_ARRASTE.get(idioma, TEXTO_ARRASTE["pt"]), convite=TEXTO_CONVITE.get(idioma, TEXTO_CONVITE["pt"]))


def _fotografar(d, html_doc: str, tmp: Path, destino: Path, altura: int) -> None:
    tmp.write_text(html_doc, encoding="utf-8")
    d._pagina.set_viewport_size({"width": LARGURA, "height": altura})
    d._pagina.goto(tmp.as_uri())
    d._pagina.evaluate("() => window.__ajustar && window.__ajustar()")
    d._pagina.screenshot(path=str(destino), type="jpeg", quality=92)


PASTA_MUSICAS = RAIZ / "assets" / "musicas"


def musica_de_fundo(semente: str) -> Path | None:
    """Uma trilha de assets/musicas (mp3, m4a, wav), escolhida pelo nome do post para variar entre posts.
    Só trilhas de uso livre e comercial (Biblioteca de áudio do YouTube "sem atribuição", Pixabay Music)."""
    if not PASTA_MUSICAS.exists():
        return None
    trilhas = sorted(f for f in PASTA_MUSICAS.iterdir() if f.suffix.lower() in (".mp3", ".m4a", ".wav"))
    if not trilhas:
        return None
    return trilhas[sum(map(ord, semente)) % len(trilhas)]


def reel_dos_slides(slides: list[Path], capa_vertical: Path | None, destino: Path,
                    segundos: float = SEGUNDOS_POR_SLIDE) -> Path:
    """Reel 1080x1920 sem som: a capa vertical no primeiro segundo (vira a capa do Reel na grade) e
    depois cada slide sobre o próprio fundo desfocado, com um zoom lento. A música entra no app."""
    entradas, filtros, rotulos = [], [], []
    k = 0
    if capa_vertical is not None:
        entradas += ["-loop", "1", "-t", "1.2", "-i", str(capa_vertical)]
        filtros.append(f"[{k}]scale=1080:1920,fps=30,format=yuv420p,trim=duration=1.2,setpts=PTS-STARTPTS[v{k}]")
        rotulos.append(f"[v{k}]")
        k += 1
    quadros = round(segundos * 30)
    for s in slides:
        entradas += ["-loop", "1", "-t", f"{segundos}", "-i", str(s)]
        filtros.append(
            f"[{k}]split[b{k}][f{k}];[b{k}]scale=1536:1920,crop=1080:1920,gblur=sigma=40,eq=brightness=-0.15[bg{k}];"
            f"[f{k}]scale=2160:2700,zoompan=z='1+0.0005*on':d={quadros}:s=1080x1350:fps=30[fg{k}];"
            f"[bg{k}][fg{k}]overlay=0:285,fps=30,format=yuv420p,trim=duration={segundos},setpts=PTS-STARTPTS[v{k}]")
        rotulos.append(f"[v{k}]")
        k += 1
    grafo = ";".join(filtros) + f";{''.join(rotulos)}concat=n={k}:v=1:a=0[v]"
    duracao = (1.2 if capa_vertical is not None else 0) + segundos * len(slides)
    trilha = musica_de_fundo(destino.parent.name)
    if trilha is not None:     # Reel publicado pela API não ganha música do app: vai uma trilha livre
        audio = ["-stream_loop", "-1", "-i", str(trilha)]
        grafo += (f";[{k}:a]atrim=duration={duracao:.2f},volume=0.35,"
                  f"afade=t=out:st={max(duracao - 1.5, 0):.2f}:d=1.5[a]")
        mapa = "[a]"
    else:
        audio = ["-f", "lavfi", "-t", f"{duracao:.2f}", "-i", "anullsrc=r=44100:cl=stereo"]
        mapa = f"{k}:a"
    subprocess.run(["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-y", *entradas, *audio,
                    "-filter_complex", grafo, "-map", "[v]", "-map", mapa, "-c:v", "libx264",
                    "-preset", "veryfast", "-crf", "20", "-c:a", "aac", "-shortest", "-movflags", "+faststart",
                    str(destino)], check=True)
    return destino


def renderizar_carrossel(marca: Marca, video: Video, pasta_saida: Path, com_reel: bool = True) -> Path:
    """Gera os slides em pasta_saida/<data>_<id>/NN.jpg (e capa_reel.jpg + reel.mp4) e devolve a pasta."""
    pasta = (pasta_saida / f"{video.data.isoformat()}_{video.id}").resolve()
    if pasta.exists():
        shutil.rmtree(pasta)
    trabalho = pasta / "_trabalho"
    trabalho.mkdir(parents=True)
    fundo_marca = marca.pasta_assets / "fundo.png"
    from . import variedade
    evitar = variedade.imagens_de_outros(video)      # cada post com imagens próprias
    estilo = variedade.estilo_capa(video)
    slides, fotos, usadas = [], [], []
    with desenhista() as d:
        for i, cena in enumerate(video.cenas):
            foto = _imagem_da_cena(cena, trabalho, i, evitar=evitar | set(usadas), semente=video.id)
            if foto is not None:
                try:
                    usadas.append(foto.resolve().relative_to(RAIZ.resolve()).as_posix())
                except ValueError:
                    pass
            if foto is None and fotos and papel_do_slide(video, i) == "final":
                foto = fotos[0]      # o slide final repete a imagem da capa, desfocada
            foto = foto or (fundo_marca if fundo_marca.exists() else None)
            fotos.append(foto)
            destino = pasta / f"{i + 1:02d}.jpg"
            _fotografar(d, montar_slide(marca, video, i, foto, estilo_capa=estilo),
                        trabalho / f"slide_{i:02d}.html", destino, ALTURA)
            slides.append(destino)
        capa = None
        if com_reel and modelo_da_marca(marca) != "classico":
            capa = pasta / "capa_reel.jpg"
            _fotografar(d, montar_slide(marca, video, 0, fotos[0], vertical=True, mostrar_arraste=False,
                                        estilo_capa=estilo),
                        trabalho / "capa_reel.html", capa, ALTURA_REEL)
    variedade.registrar(video, usadas, estilo)
    if com_reel:
        reel_dos_slides(slides, capa, pasta / "reel.mp4")
    shutil.rmtree(trabalho)
    return pasta
