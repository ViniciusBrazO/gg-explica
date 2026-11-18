"""O passo comum a todo vídeo aprovado: renderizar, conferir, montar a legenda e pôr na fila.

Usado pelo `paginas renderizar` e pela aprovação no Telegram, para os dois fazerem exatamente
a mesma coisa.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from .facebook import CredenciaisFacebook
from .fila import Item, enfileirar_instagram, exportar_lote, horario_publicacao, montar_legenda
from .marca import RAIZ, Marca
from .modelos import Video
from .montagem import preencher_variaveis, renderizar_video
from .qualidade import checar_arquivo, checar_pauta


@dataclass
class Resultado:
    arquivo: Optional[Path]
    legenda: str = ""
    problemas: list[str] = None
    pulado: str = ""
    duracao_s: float = 0.0


def redes_desligadas() -> set[str]:
    """Redes que o kit não usa agora (publicacao.desligar em config/automacao.yaml)."""
    from .radar import config
    return set(config().get("publicacao", {}).get("desligar", []))


def automatico_em(plataforma: str, marca_id: str) -> bool:
    """Instagram sempre pela API; Facebook e YouTube quando as credenciais estão no .env;
    TikTok e Kwai vão para o lote (o clique final é seu)."""
    if plataforma == "instagram":
        return True
    if plataforma == "facebook":
        return CredenciaisFacebook.da_marca(marca_id) is not None
    if plataforma == "youtube":
        from .youtube import CredenciaisYouTube
        return CredenciaisYouTube.da_marca(marca_id) is not None
    return False


HORAS_ENTRE_REEL_E_CARROSSEL = 2
MINUTOS_ENTRE_POSTS = 90      # igual a publicacao.instagram.minutos_entre_posts (config/automacao.yaml)


def horario_livre(quando, video_id: str):
    """Empurra o horário até ficar a 90 min de qualquer outro post da fila (dois posts juntos se canibalizam)."""
    from .fila import carregar
    from datetime import datetime as _dt
    ocupados = [_dt.fromisoformat(i.quando) for i in carregar()
                if i.plataforma == "instagram" and i.status != "erro"
                and i.id not in (video_id, f"{video_id}_reel")]
    while any(abs((quando - o).total_seconds()) < MINUTOS_ENTRE_POSTS * 60 for o in ocupados):
        quando = quando + timedelta(minutes=30)
    return quando   # o Reel sai no horário do post (é o que leva a quem não segue)


def carrosseis_por_dia() -> int:
    from .radar import config
    return int(config().get("publicacao", {}).get("instagram_carrosseis_por_dia", 99))


def carrosseis_no_dia(marca_id: str, quando: datetime) -> int:
    """Carrosséis do Instagram já na fila (ou publicados) no mesmo dia."""
    from .fila import carregar
    return sum(1 for i in carregar() if i.marca == marca_id and i.tipo == "carrossel" and i.plataforma == "instagram"
               and i.status != "erro" and i.quando[:10] == quando.isoformat()[:10])


def enfileirar_carrossel(marca: Marca, video: Video, pasta: Path, legenda: str, produtos: list[str]) -> None:
    """Com a Página ligada (META_TOKEN + FB_PAGE_ID), o Reel do post sai no horário (Instagram e Página
    do Facebook) e o carrossel 2 horas depois; sem ela, tudo vai para o lote manual. TikTok sempre no lote."""
    from .meta import pode_hospedar
    quando = horario_livre(horario_publicacao(video), video.id)
    if "instagram" in video.plataformas:
        if pode_hospedar(marca.id):
            reel = pasta / "reel.mp4"
            depois = quando
            if reel.exists() and video.gerar_reel:
                capa = pasta / "capa_reel.jpg"
                for plataforma in ("instagram", "facebook"):
                    if plataforma not in redes_desligadas() and automatico_em(plataforma, marca.id):
                        enfileirar_instagram(Item(id=f"{video.id}_reel", marca=marca.id, video=str(reel),
                                                  capa=str(capa) if capa.exists() else "", legenda=legenda,
                                                  quando=quando.isoformat(), plataforma=plataforma,
                                                  produtos_para_marcar=produtos))
                depois = horario_livre(quando + timedelta(hours=HORAS_ENTRE_REEL_E_CARROSSEL), video.id)
            if carrosseis_no_dia(marca.id, depois) >= carrosseis_por_dia():
                print(f"  {video.id}: carrossel fora do feed (já tem {carrosseis_por_dia()} no dia; foco em Reels)")
            else:
                enfileirar_instagram(Item(id=video.id, marca=marca.id, video=str(pasta), capa=str(pasta / "01.jpg"),
                                          legenda=legenda, quando=depois.isoformat(), tipo="carrossel",
                                          produtos_para_marcar=produtos))
        else:
            exportar_lote("instagram", marca, video, pasta, legenda, produtos)
    if "tiktok" in video.plataformas:
        exportar_lote("tiktok", marca, video, pasta, legenda, produtos)


def pasta_videos(marca: Marca) -> Path:
    return RAIZ / "saida" / "videos" / marca.id


def produzir(marca: Marca, video: Video, previa: bool = False, voz: Optional[str] = None) -> Resultado:
    """Renderiza um vídeo. Fora da prévia, coloca na fila do Instagram e no lote do TikTok
    e marca o vídeo como renderizado (quem chama salva a pauta)."""
    bloqueios, _ = checar_pauta(marca, video)
    if bloqueios and not previa:
        return Resultado(None, pulado="; ".join(bloqueios))
    sem_arquivo = [b for b in bloqueios if "não encontrado" in b or "nenhum clipe" in b]
    if sem_arquivo:   # nem a prévia sai sem o clipe ou a imagem da cena
        return Resultado(None, pulado="; ".join(sem_arquivo))
    legenda = montar_legenda(marca, video, preencher_variaveis(video.legenda_post, video.data))
    produtos = [p.nome for p in video.produtos]
    if video.formato == "carrossel":
        from .carrossel import renderizar_carrossel
        pasta = renderizar_carrossel(marca, video, RAIZ / "saida" / "carrosseis" / marca.id)
        (pasta / "legenda.txt").write_text(legenda, encoding="utf-8")
        if not previa:
            enfileirar_carrossel(marca, video, pasta, legenda, produtos)
            video.status = "renderizado"
        return Resultado(pasta, legenda, [])
    pasta = pasta_videos(marca)
    info = renderizar_video(marca, video, pasta, voz_forcada=voz, registrar_clipes=not previa)
    arquivo = pasta / info["video"]
    problemas = checar_arquivo(marca, arquivo)
    arquivo.with_suffix(".txt").write_text(legenda, encoding="utf-8")
    capa = pasta / info["capa"]
    try:                       # capa de verdade do Reel (vai como cover_url), não um quadro do vídeo
        from .carrossel import capa_do_reel
        capa = capa_do_reel(marca, video, info.get("midia_capa"), arquivo.with_name(arquivo.stem + "_capa.jpg"),
                            info.get("estilo_capa", "base"))
    except Exception as e:
        problemas = list(problemas) + [f"capa do Reel não saiu ({e}); vai um quadro do vídeo"]
    if not previa:
        quando = horario_livre(horario_publicacao(video), video.id).isoformat()
        for plataforma in video.plataformas:
            if plataforma in redes_desligadas():
                continue
            if automatico_em(plataforma, marca.id):
                enfileirar_instagram(Item(id=video.id, marca=marca.id, video=str(arquivo), capa=str(capa.resolve()),
                                          legenda=legenda, quando=quando, plataforma=plataforma,
                                          produtos_para_marcar=produtos))
            else:
                exportar_lote(plataforma, marca, video, arquivo, legenda, produtos)
        video.status = "renderizado"
    return Resultado(arquivo, legenda, problemas, duracao_s=info["duracao_s"])
