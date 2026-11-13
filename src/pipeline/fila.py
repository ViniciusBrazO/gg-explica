"""Fila de publicação: o que está pronto, para quando, e o que já foi ao ar.

Instagram: publicado automaticamente pela API quando chega o horário
           (o comando `paginas publicar` roda a cada 15 minutos no agendador do sistema).
TikTok:    vai para uma pasta de lote com legenda pronta, para agendar no TikTok Studio.
"""
from __future__ import annotations

import json
import shutil
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from .marca import RAIZ, Marca
from .modelos import Video

FUSO = ZoneInfo("America/Sao_Paulo")
ARQUIVO_FILA = RAIZ / "saida" / "fila.json"
PASTA_LOTES = RAIZ / "saida" / "lotes"
PASTA_TIKTOK = PASTA_LOTES / "tiktok"

# Como publicar cada lote à mão (plataformas sem API aberta para o kit).
INSTRUCOES_LOTE = {
    "tiktok": "TikTok Studio > Publicar > enviar o .mp4 > colar o .txt > ativar 'Conteúdo gerado por IA' > "
              "ativar 'Conteúdo comercial' se tiver #publi > Agendar no horário do nome do arquivo. "
              "O atalho /tiktok-agendar do Claude no Chrome preenche tudo e para antes do botão final.",
    "youtube": "YouTube Studio > Criar > Enviar vídeos > o .mp4 (vertical vira Short) > título = primeira linha do "
               ".txt (até 100 caracteres) > descrição = o .txt > responder a pergunta de conteúdo alterado ou "
               "sintético > Visibilidade: Programar no horário do nome do arquivo.",
    "kwai": "App do Kwai > + > enviar o .mp4 > colar o .txt > publicar no horário do nome do arquivo.",
    "facebook": "Meta Business Suite > Criar reel > enviar o .mp4 > colar o .txt > Programar no horário do nome "
                "do arquivo (ou configure FB_PAGE_ID/FB_PAGE_TOKEN no .env e o kit publica sozinho).",
    "carrossel": "(Com META_TOKEN e FB_PAGE_ID no .env, o kit publica o carrossel e o Reel dele sozinho.) "
                 "Instagram: + > Post > selecione os slides na ordem (01, 02...) > legenda do .txt > Compartilhar "
                 "(ou programe no Meta Business Suite). TikTok: + > Foto > os mesmos slides > o mesmo .txt. "
                 "Reel do mesmo post: + > Reel > reel.mp4 > música em alta em volume baixo > Editar capa > "
                 "capa_reel.jpg > a mesma legenda (poste 2 a 4 horas depois do carrossel).",
}


@dataclass
class Item:
    id: str
    marca: str
    video: str
    capa: str
    legenda: str
    quando: str                  # ISO com fuso de Brasília
    plataforma: str = "instagram"
    tipo: str = "reel"           # reel | carrossel (video = pasta dos slides NN.jpg)
    status: str = "pendente"     # pendente | publicado | erro
    produtos_para_marcar: list[str] = field(default_factory=list)
    media_id: str = ""
    permalink: str = ""
    erro: str = ""
    tentativas: int = 0
    publicado_em: str = ""
    furar_freio: bool = False    # liberado pelo Vinicius: sai mesmo acima do limite diário       # ISO; a hora real em que saiu (o freio conta por ela)


def montar_legenda(marca: Marca, video: Video, legenda_post: str) -> str:
    """#publi no começo (visível sem tocar em 'mais'), aviso de IA, créditos e no máximo 3 hashtags."""
    partes = []
    if video.publi:
        partes.append(marca.post["aviso_publi"])
    partes.append(legenda_post.strip())
    avisos = []
    if video.voz_ia:
        avisos.append(marca.post["aviso_ia"])
    # Crédito das imagens de terceiros (lei 9.610/98, art. 46, III: citar autor e fonte).
    avisos += [c if c.endswith(".") else c + "." for c in video.creditos()]
    if avisos:
        partes.append(" ".join(avisos))
    tags = []
    for t in list(video.hashtags) + list(marca.post.get("hashtags_base", [])):
        if t not in tags:
            tags.append(t)
    if tags:
        partes.append(" ".join(tags[:3]))
    return "\n\n".join(partes)


def carregar() -> list[Item]:
    if not ARQUIVO_FILA.exists():
        return []
    return [Item(**x) for x in json.loads(ARQUIVO_FILA.read_text(encoding="utf-8"))]


def salvar(itens: list[Item]) -> None:
    ARQUIVO_FILA.parent.mkdir(parents=True, exist_ok=True)
    ARQUIVO_FILA.write_text(json.dumps([asdict(i) for i in itens], ensure_ascii=False, indent=2), encoding="utf-8")


def enfileirar_instagram(item: Item) -> None:
    """Põe na fila de publicação automática (Instagram ou Facebook, conforme item.plataforma)."""
    itens = [i for i in carregar() if not (i.id == item.id and i.marca == item.marca
                                           and i.plataforma == item.plataforma and i.status not in ("publicado", "manual"))]
    itens.append(item)
    itens.sort(key=lambda i: i.quando)
    salvar(itens)


def cancelar(marca: str, video_id: str) -> int:
    """Tira da fila o que ainda não saiu deste post (carrossel e Reel). Devolve quantos itens saíram."""
    itens = carregar()
    ficam = [i for i in itens if not (i.marca == marca and i.status == "pendente"
                                      and i.id in (video_id, f"{video_id}_reel"))]
    salvar(ficam)
    return len(itens) - len(ficam)


def _titulo(legenda: str) -> str:
    linhas = [l for l in legenda.splitlines() if l.strip() and not l.startswith("#publi")]
    return (linhas[0] if linhas else "")[:120]


def exportar_lote(plataforma: str, marca: Marca, video: Video, origem: Path, legenda: str,
                  produtos: list[str]) -> Path:
    """Copia o vídeo (ou os slides do carrossel) e a legenda para saida/lotes/<plataforma>/<dia>/
    e atualiza o roteiro de publicação do dia."""
    pasta = PASTA_LOTES / plataforma / video.data.isoformat()
    pasta.mkdir(parents=True, exist_ok=True)
    base = f"{video.horario.strftime('%H%M')}_{marca.id}_{video.id}"
    if origem.is_dir():
        destino = pasta / base
        if destino.exists():
            shutil.rmtree(destino)
        shutil.copytree(origem, destino)
    else:
        destino = pasta / f"{base}.mp4"
        shutil.copy2(origem, destino)
    (pasta / f"{base}.txt").write_text(legenda, encoding="utf-8")
    roteiro = pasta / "COMO_PUBLICAR.md"
    linhas = [] if not roteiro.exists() else roteiro.read_text(encoding="utf-8").splitlines()
    if not linhas:
        instrucao = INSTRUCOES_LOTE["carrossel" if origem.is_dir() else plataforma]
        linhas = [f"# Lote {plataforma} de {video.data.strftime('%d/%m/%Y')}", "", instrucao, ""]
    linhas.append(f"- [ ] {video.horario.strftime('%H:%M')} · {marca.nome} · `{destino.name}`"
                  + (f" · marcar no carrinho: {', '.join(produtos)}" if produtos else ""))
    roteiro.write_text("\n".join(linhas) + "\n", encoding="utf-8")
    return destino


def exportar_tiktok(marca: Marca, video: Video, arquivo: Path, legenda: str, produtos: list[str]) -> Path:
    return exportar_lote("tiktok", marca, video, arquivo, legenda, produtos)


def horario_publicacao(video: Video) -> datetime:
    return datetime.combine(video.data, video.horario, tzinfo=FUSO)
