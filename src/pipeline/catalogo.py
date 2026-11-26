"""Catálogo de clipes: transforma as suas gravações de jogo em algo que o Claude consegue ler.

Para cada vídeo em `clipes/`, gera uma folha de contato (um quadro a cada N segundos, com o
tempo escrito em cima) em `clipes/_folhas/` e uma entrada em `clipes/catalogo.json`.
O Claude olha as folhas, preenche descrição, lugar, personagens e os melhores momentos, e
depois usa o catálogo para escolher o trecho certo (`midia_inicio` / `midia_fim`) na pauta.

O que já foi preenchido no catálogo nunca é apagado: rodar de novo só acrescenta clipes novos.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
import subprocess
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .marca import PASTA_FONTES, RAIZ

PASTA_CLIPES = RAIZ / "clipes"
EXTENSOES = {".mp4", ".mov", ".mkv", ".webm", ".m4v"}
EXT_IMAGENS = {".jpg", ".jpeg", ".png", ".webp"}
PASTAS_IGNORADAS = {"_folhas", "entrada", "_zips"}
POR_FOLHA_IMAGENS = 12
COLUNAS = 4
MAX_QUADROS = 40
LARGURA_QUADRO = 384


def _sondar(arquivo: Path) -> dict:
    from .sonda import sondar
    info = sondar(arquivo)
    s = next(f for f in info["streams"] if f.get("codec_type", "video") == "video")
    return {"duracao_s": round(float(info["format"]["duration"]), 2), "largura": int(s["width"]),
            "altura": int(s["height"])}


def intervalo_para(duracao: float, intervalo: float) -> float:
    """Aumenta o intervalo em clipes longos para a folha não passar de MAX_QUADROS quadros."""
    return max(intervalo, math.ceil(duracao / MAX_QUADROS))


def _folha(arquivo: Path, saida: Path, intervalo: float, duracao: float) -> None:
    quadros = max(1, math.ceil(duracao / intervalo))
    linhas = math.ceil(quadros / COLUNAS)
    fonte = (PASTA_FONTES / "Barlow-SemiBold.ttf").as_posix().replace(":", "\\:")
    filtro = (f"fps=1/{intervalo},scale={LARGURA_QUADRO}:-2,"
              f"drawtext=fontfile='{fonte}':text='%{{pts\\:hms}}':x=10:y=10:fontsize=26:fontcolor=white:"
              f"box=1:boxcolor=black@0.65:boxborderw=6,"
              f"tile={COLUNAS}x{linhas}:padding=6:margin=6:color=0x0B0D12")
    saida.parent.mkdir(parents=True, exist_ok=True)
    r = subprocess.run(["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-y", "-i", str(arquivo),
                        "-vf", filtro, "-frames:v", "1", "-q:v", "3", str(saida)],
                       capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"não consegui montar a folha de {arquivo.name}:\n{r.stderr[-1500:]}")


def detectar_cortes(arquivo: Path, limiar: float = 0.35) -> list[float]:
    """Segundos em que a imagem muda de cena (corte de câmera, menu, troca de lugar)."""
    r = subprocess.run(["ffmpeg", "-nostdin", "-hide_banner", "-i", str(arquivo), "-vf",
                        f"select='gt(scene,{limiar})',showinfo", "-an", "-f", "null", "-"],
                       capture_output=True, text=True)
    return [round(float(m), 2) for m in re.findall(r"pts_time:([0-9.]+)", r.stderr)]


def momentos_por_cortes(cortes: list[float], duracao: float, minimo: float = 0.8,
                        maximo: float = 6.0) -> list[dict]:
    """Transforma os cortes de cena em trechos prontos (um plano do trailer = um trecho).

    Planos curtos demais ficam de fora; planos longos viram pedaços de até `maximo` segundos.
    """
    marcas = [0.0] + [c for c in cortes if 0 < c < duracao] + [duracao]
    momentos = []
    for a, b in zip(marcas, marcas[1:]):
        if b - a < minimo:
            continue
        partes = max(1, math.ceil((b - a) / maximo))
        passo = (b - a) / partes
        for k in range(partes):
            momentos.append({"corte": len(momentos) + 1, "inicio": round(a + k * passo, 2),
                             "fim": round(a + (k + 1) * passo, 2), "o_que_mostra": ""})
    return momentos


def _rotular(img, texto: str):
    from PIL import ImageDraw, ImageFont

    g = ImageDraw.Draw(img)
    fonte = ImageFont.truetype(str(PASTA_FONTES / "Barlow-Bold.ttf"), 26)
    caixa = g.textbbox((10, 8), texto, font=fonte)
    g.rectangle((caixa[0] - 6, caixa[1] - 4, caixa[2] + 6, caixa[3] + 4), fill=(0, 0, 0))
    g.text((10, 8), texto, font=fonte, fill=(200, 255, 46))
    return img


def _montar_folha(miniaturas: list, saida: Path, colunas: int = 5) -> Path:
    from PIL import Image

    w, h = miniaturas[0].size
    linhas = math.ceil(len(miniaturas) / colunas)
    folha = Image.new("RGB", (colunas * (w + 6) + 6, linhas * (h + 6) + 6), (11, 13, 18))
    for i, m in enumerate(miniaturas):
        folha.paste(m, (6 + (i % colunas) * (w + 6), 6 + (i // colunas) * (h + 6)))
    saida.parent.mkdir(parents=True, exist_ok=True)
    folha.save(saida, quality=85)
    return saida


def folhas_de_cortes(arquivo: Path, momentos: list[dict], pasta_folhas: Path, por_folha: int = 30) -> list[Path]:
    """Uma miniatura do meio de cada trecho, numerada ("#12 · 01:23"), para o Claude descrever um a um."""
    import tempfile
    from PIL import Image

    folhas = []
    with tempfile.TemporaryDirectory() as tmp:
        miniaturas = []
        for m in momentos:
            meio = (m["inicio"] + m["fim"]) / 2
            q = Path(tmp) / f"{m['corte']:04d}.jpg"
            subprocess.run(["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-y", "-ss", f"{meio:.2f}", "-i",
                            str(arquivo), "-frames:v", "1", "-vf", "scale=320:180:force_original_aspect_ratio=decrease,"
                            "pad=320:180:(ow-iw)/2:(oh-ih)/2", str(q)], capture_output=True)
            img = Image.open(q).convert("RGB") if q.exists() else Image.new("RGB", (320, 180))
            minutos, segundos = divmod(int(m["inicio"]), 60)
            miniaturas.append(_rotular(img, f"#{m['corte']} · {minutos:02d}:{segundos:02d}"))
        for k in range(0, len(miniaturas), por_folha):
            folhas.append(_montar_folha(miniaturas[k:k + por_folha],
                                        pasta_folhas / f"{arquivo.stem}_cortes_{k // por_folha + 1:02d}.jpg"))
    return folhas


def _rel(p: Path) -> str:
    return p.relative_to(RAIZ).as_posix() if p.is_relative_to(RAIZ) else str(p)


def _campos_para_preencher() -> dict:
    return {
        # Campos que o Claude (ou você) preenche olhando as folhas:
        "descricao": "",
        "lugar": "",
        "personagens": [],
        "tags": [],              # palavras para a busca: "praia", "noite", "carro", "perseguição"...
        "spoiler": None,         # true/false: mostra algo da história além do que já foi divulgado?
    }


def _credito_padrao(arquivo: Path) -> str:
    return "Imagens: Rockstar Games" if "oficial" in arquivo.parts else ""


def etiquetar_momentos(pasta: Path = PASTA_CLIPES, por_lote: int = 24, mostrar=print, max_lotes: int = 3) -> int:
    """Descreve cada plano dos vídeos oficiais (o que aparece, em palavras de busca) olhando um quadro
    do meio do plano. Marca para descarte logo, texto/cartela, tela preta e créditos. Usa o Gemini."""
    from .gemini import disponivel, gerar_json
    if not disponivel():
        raise RuntimeError("falta GEMINI_API_KEY")
    arq = pasta / "catalogo.json"
    catalogo = json.loads(arq.read_text(encoding="utf-8"))
    feitos = 0
    instrucoes = (
        "Você cataloga quadros de trailers oficiais de GTA VI para um editor de vídeo. Para cada imagem, na "
        "ordem, devolva o_que_mostra: 6 a 12 palavras-chave em português do Brasil, minúsculas, separadas por "
        "vírgula (lugar, objeto, ação, clima, horário; personagem só se tiver certeza: jason, lucia), e "
        "descartar: true se for logotipo, cartela de texto, legenda, tela preta, créditos ou quadro borrado. "
        "Responda {\"quadros\": [{\"n\": 1, \"o_que_mostra\": \"...\", \"descartar\": false}, ...]}.")
    for e in catalogo:
        if e.get("tipo") != "video":
            continue
        pendentes = [m for m in e.get("momentos", []) if not m.get("o_que_mostra") and not m.get("descartar")]
        for k in range(0, len(pendentes), por_lote):
            if max_lotes <= 0:
                break
            max_lotes -= 1
            lote = pendentes[k:k + por_lote]
            quadros = []
            for m in lote:
                meio = (float(m["inicio"]) + float(m["fim"])) / 2
                r = subprocess.run(["ffmpeg", "-nostdin", "-loglevel", "error", "-ss", f"{meio:.2f}", "-i",
                                    str(RAIZ / e["arquivo"]), "-frames:v", "1", "-vf", "scale=512:-2", "-q:v", "5",
                                    "-f", "image2", "-c:v", "mjpeg", "pipe:1"], capture_output=True)
                quadros.append(r.stdout)
            resposta = gerar_json(instrucoes, f"{len(quadros)} quadros, na ordem.", temperatura=0.2,
                                  imagens=quadros)
            for item in resposta.get("quadros", []):
                n = int(item.get("n", 0)) - 1
                if 0 <= n < len(lote):
                    lote[n]["o_que_mostra"] = (item.get("o_que_mostra") or "").strip()
                    lote[n]["descartar"] = bool(item.get("descartar"))
                    feitos += 1
            arq.write_text(json.dumps(catalogo, ensure_ascii=False, indent=1), encoding="utf-8")
    mostrar(f"  {feitos} trecho(s) de vídeo descrito(s)")
    return feitos


def catalogar(pasta: Path = PASTA_CLIPES, intervalo: float = 2.0) -> list[dict]:
    """Cataloga vídeos (com cortes por plano) e imagens novos. Devolve as entradas novas."""
    from PIL import Image

    pasta = pasta.resolve()
    arquivo_catalogo = pasta / "catalogo.json"
    catalogo: list[dict] = []
    if arquivo_catalogo.exists():
        catalogo = json.loads(arquivo_catalogo.read_text(encoding="utf-8"))
    conhecidos = {c["arquivo"] for c in catalogo}
    novos, imagens_novas = [], []
    for arquivo in sorted(pasta.rglob("*")):
        sufixo = arquivo.suffix.lower()
        if sufixo not in EXTENSOES | EXT_IMAGENS or PASTAS_IGNORADAS & set(arquivo.parts):
            continue
        rel = _rel(arquivo)
        if rel in conhecidos:
            continue
        if sufixo in EXT_IMAGENS:
            with Image.open(arquivo) as img:
                largura, altura = img.size
            entrada = {"arquivo": rel, "tipo": "imagem", "largura": largura, "altura": altura,
                       "credito": _credito_padrao(arquivo), **_campos_para_preencher()}
            imagens_novas.append((arquivo, entrada))
        else:
            info = _sondar(arquivo)
            passo = intervalo_para(info["duracao_s"], intervalo)
            folha = pasta / "_folhas" / f"{arquivo.stem}.jpg"
            _folha(arquivo, folha, passo, info["duracao_s"])
            cortes = detectar_cortes(arquivo)
            momentos = momentos_por_cortes(cortes, info["duracao_s"])
            folhas = folhas_de_cortes(arquivo, momentos, pasta / "_folhas") if momentos else []
            entrada = {"arquivo": rel, "tipo": "video", **info, "folha": _rel(folha), "intervalo_folha_s": passo,
                       "cortes_s": cortes, "folhas_cortes": [_rel(f) for f in folhas],
                       "credito": _credito_padrao(arquivo), **_campos_para_preencher(),
                       # um trecho por plano; o Claude descreve cada um em "o_que_mostra"
                       "momentos": momentos}
        catalogo.append(entrada)
        novos.append(entrada)
    # imagens: folhas com 12 miniaturas numeradas, para etiquetar várias de uma vez
    for k in range(0, len(imagens_novas), POR_FOLHA_IMAGENS):
        lote = imagens_novas[k:k + POR_FOLHA_IMAGENS]
        miniaturas = []
        for n, (arq, entrada) in enumerate(lote, start=1):
            with Image.open(arq) as img:
                img = img.convert("RGB")
                img.thumbnail((360, 240))
                fundo = Image.new("RGB", (360, 240), (11, 13, 18))
                fundo.paste(img, ((360 - img.width) // 2, (240 - img.height) // 2))
            miniaturas.append(_rotular(fundo, f"#{n}"))
        folha = _montar_folha(miniaturas, pasta / "_folhas" / f"imagens_{len(catalogo):05d}_{k:04d}.jpg", colunas=4)
        for n, (_, entrada) in enumerate(lote, start=1):
            entrada["folha"], entrada["posicao_na_folha"] = _rel(folha), n
    arquivo_catalogo.parent.mkdir(parents=True, exist_ok=True)
    arquivo_catalogo.write_text(json.dumps(catalogo, ensure_ascii=False, indent=2), encoding="utf-8")
    return novos


# ---------------------------------------------------------------- escolha de clipe por busca

ARQUIVO_USO = RAIZ / "saida" / "uso_clipes.json"


@dataclass
class Escolha:
    caminho: Path
    inicio: float = 0.0
    fim: Optional[float] = None
    entrada: Optional[dict] = None     # a entrada do catálogo, quando veio de uma busca


def _normalizar(texto: str) -> list[str]:
    sem_acento = unicodedata.normalize("NFKD", texto.lower()).encode("ascii", "ignore").decode()
    return [p for p in re.split(r"[^a-z0-9]+", sem_acento) if len(p) > 2]


def _texto_entrada(e: dict) -> str:
    partes = [e.get("descricao", ""), e.get("lugar", ""), " ".join(e.get("personagens", [])),
              " ".join(e.get("tags", [])), Path(e.get("arquivo", "")).stem.replace("_", " ")]
    return " ".join(partes)


def _carregar_uso() -> dict:
    if ARQUIVO_USO.exists():
        return json.loads(ARQUIVO_USO.read_text(encoding="utf-8"))
    return {}


def chave_uso(escolha: Escolha) -> str:
    """Imagem: o arquivo. Vídeo: o arquivo e o plano (cada plano do trailer conta como uma cena)."""
    arquivo = escolha.entrada["arquivo"] if escolha.entrada else escolha.caminho.as_posix()
    return arquivo if not escolha.inicio else f"{arquivo}@{escolha.inicio:.1f}"


def registrar_uso(escolha: Escolha) -> None:
    """Conta quantas vezes cada trecho já foi ao ar, para a busca variar os clipes."""
    if escolha.entrada is None:
        return
    uso = _carregar_uso()
    chave = f"{escolha.entrada['arquivo']}@{escolha.inicio:.1f}"
    uso[chave] = uso.get(chave, 0) + 1
    ARQUIVO_USO.parent.mkdir(parents=True, exist_ok=True)
    ARQUIVO_USO.write_text(json.dumps(uso, ensure_ascii=False, indent=2), encoding="utf-8")


MIN_SEGUNDOS_VIDEO = 1.6     # os clipes de 1 s do pacote viram um loop que pisca; plano de trailer passa


def buscar_clipe(consulta: str, pasta: Path = PASTA_CLIPES, aceitar_spoiler: bool = False,
                 evitar: Optional[set] = None, semente: str = "",
                 preferir_video: bool = False) -> Optional[Escolha]:
    """Acha no catálogo o trecho que mais combina com a consulta ("praia pôr do sol carro").

    Pontua cada momento (e o clipe inteiro) pelas palavras em comum; em empate, prefere o
    trecho menos usado e, depois, sorteia pela `semente` (o id do post), para posts diferentes
    não caírem sempre na mesma imagem. Arquivos em `evitar` (já usados em outros posts) ficam de
    fora enquanto houver alternativa. Clipes marcados com spoiler ficam de fora, salvo se pedido.
    """
    arquivo = pasta / "catalogo.json"
    if not arquivo.exists():
        return None
    termos = set(_normalizar(consulta))
    if not termos:
        return None
    uso = _carregar_uso()
    melhores: list[tuple[float, int, Escolha]] = []
    for e in json.loads(arquivo.read_text(encoding="utf-8")):
        if e.get("spoiler") and not aceitar_spoiler:
            continue
        if "logo" in e.get("tags", []) and "logo" not in termos and "logos" not in termos:
            continue      # arte com o logotipo do jogo por cima: só quando pedida
        if pasta == PASTA_CLIPES and not (RAIZ / e["arquivo"]).exists():
            continue      # no catálogo, mas o arquivo sumiu do cache (25/11: travou um Reel inteiro)
        base = set(_normalizar(_texto_entrada(e)))
        candidatos = [(0.0, e.get("duracao_s"), base)]
        for m in e.get("momentos", []):
            if m.get("descartar"):
                continue      # plano marcado como inútil (logo, tela preta, texto do trailer)
            candidatos.append((float(m.get("inicio", 0)), m.get("fim"), base | set(_normalizar(m.get("o_que_mostra", "")))))
        for inicio, fim, palavras in candidatos:
            pontos = len(termos & palavras)
            if not pontos:
                continue
            bonus = 0.5 if fim is not None and inicio > 0 else 0.0   # momento específico vale mais
            dur_trecho = (float(fim) - inicio) if fim is not None else float(e.get("duracao_s") or 0)
            if e.get("tipo") == "video" and dur_trecho < MIN_SEGUNDOS_VIDEO:
                if preferir_video:
                    continue      # clipe de 1 s em repetição parece travado: no Reel, imagem com movimento suave é melhor
            elif preferir_video and e.get("tipo") == "video":
                bonus += 1.0      # trecho de trailer de verdade (3 s ou mais) vale mais que imagem parada
            vezes = uso.get(f"{e['arquivo']}@{inicio:.1f}", 0)
            sorteio = hashlib.sha1(f"{semente}|{e['arquivo']}|{inicio}".encode()).hexdigest()
            melhores.append((pontos + bonus, -vezes, sorteio, Escolha(RAIZ / e["arquivo"], inicio,
                                                                       float(fim) if fim else None, e)))
    if not melhores:
        return None
    if evitar:
        from .variedade import assunto_da_imagem
        livres = [m for m in melhores if chave_uso(m[3]) not in evitar and m[3].entrada["arquivo"] not in evitar
                  and "assunto:" + assunto_da_imagem(m[3].entrada["arquivo"]) not in evitar]
        melhores = livres or melhores
    melhores.sort(key=lambda x: (x[0], x[1], x[2]), reverse=True)
    return melhores[0][3]


def resolver_midia(midia: str, inicio: float = 0.0, fim: Optional[float] = None,
                   evitar: Optional[set] = None, semente: str = "",
                   preferir_video: bool = False) -> Optional[Escolha]:
    """"busca:<palavras>" procura no catálogo; qualquer outro texto é um caminho de arquivo."""
    if midia.startswith("busca:"):
        return buscar_clipe(midia.split(":", 1)[1], evitar=evitar, semente=semente, preferir_video=preferir_video)
    p = Path(midia)
    return Escolha(p if p.is_absolute() else RAIZ / p, inicio, fim)


# ---------------------------------------------------------------- imagens oficiais

PASTA_OFICIAL = PASTA_CLIPES / "oficial"
TIPOS_IMAGEM = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}


def baixar_oficial(url: str, nome: str = "", credito: str = "Imagens: Rockstar Games", sessao=None) -> Path:
    """Baixa uma imagem oficial (galeria de screenshots, post do Newswire) para clipes/oficial/.

    Só imagem e só o link que você (ou o Claude) escolheu: não percorre sites. Registra a origem em
    clipes/oficial/indice.json para o crédito sair certo no vídeo.
    """
    import requests
    from datetime import date

    sessao = sessao or requests.Session()
    r = sessao.get(url, timeout=60, headers={"User-Agent": "Mozilla/5.0 (paginas-nicho)"})
    r.raise_for_status()
    tipo = r.headers.get("Content-Type", "").split(";")[0].strip()
    if tipo not in TIPOS_IMAGEM:
        raise ValueError(f"o link não é uma imagem (veio {tipo or 'sem tipo'})")
    if len(r.content) > 20 * 1024 * 1024:
        raise ValueError("imagem maior que 20 MB")
    base = re.sub(r"[^a-z0-9]+", "_", (nome or Path(url.split("?")[0]).stem).lower()).strip("_")[:50] or "imagem"
    PASTA_OFICIAL.mkdir(parents=True, exist_ok=True)
    destino = PASTA_OFICIAL / f"{date.today().isoformat()}_{base}{TIPOS_IMAGEM[tipo]}"
    destino.write_bytes(r.content)
    indice = PASTA_OFICIAL / "indice.json"
    itens = json.loads(indice.read_text(encoding="utf-8")) if indice.exists() else []
    itens.append({"arquivo": destino.relative_to(RAIZ).as_posix(), "url": url, "credito": credito,
                  "baixado_em": date.today().isoformat()})
    indice.write_text(json.dumps(itens, ensure_ascii=False, indent=2), encoding="utf-8")
    return destino
