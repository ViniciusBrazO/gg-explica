"""Cada post único: imagens que não se repetem entre posts e capas que giram."""
from __future__ import annotations

import json

import pytest

from pipeline import variedade
from pipeline.modelos import Video


def _video(vid, hora="19:00", imgs=("busca:lucia",), dia="2026-11-10"):
    cenas = [{"tipo": "gancho", "titulo": "a", "fundo_clipe": imgs[0]}]
    cenas += [{"tipo": "texto", "titulo": "b", "texto": "c", "fundo_clipe": i} for i in imgs[1:]]
    cenas.append({"tipo": "cta", "titulo": "d", "texto": "e"})
    return Video.model_validate({"id": vid, "data": dia, "horario": hora, "serie": "gg_explica",
                                 "formato": "carrossel", "legenda_post": "x", "cenas": cenas})


@pytest.fixture
def kit(tmp_path, monkeypatch):
    (tmp_path / "pautas").mkdir()
    monkeypatch.setattr(variedade, "RAIZ", tmp_path)
    monkeypatch.setattr(variedade, "ARQ_ESCOLHAS", tmp_path / "escolhas.json")
    return tmp_path


def _pauta(kit, *videos):
    (kit / "pautas" / "p.json").write_text(json.dumps(
        {"marca": "gg_explica", "semana": "2026-W46", "videos": [json.loads(v.model_dump_json()) for v in videos]}))


def test_imagem_direta_repetida_entre_posts_bloqueia(kit):
    a = _video("a", imgs=("clipes/oficial/X.jpg",))
    b = _video("b", imgs=("clipes/oficial/X.jpg",))
    _pauta(kit, a, b)
    assert any("já está no post a" in p for p in variedade.repetidas(b))


def test_imagem_repetida_no_mesmo_post_bloqueia(kit):
    a = _video("a", imgs=("clipes/oficial/X.jpg", "clipes/oficial/X.jpg"))
    _pauta(kit, a)
    assert any("mais de uma vez" in p for p in variedade.repetidas(a))


def test_escolhas_de_outros_posts_sao_evitadas(kit):
    a, b = _video("a"), _video("b", hora="21:00")
    variedade.registrar(a, ["clipes/oficial/Y.jpg"], "topo")
    assert variedade.imagens_de_outros(b) == {"clipes/oficial/Y.jpg"}
    assert variedade.imagens_de_outros(a) == set()


def test_capa_nunca_repete_as_duas_anteriores(kit):
    variedade.registrar(_video("a", hora="15:00"), [], "base")
    variedade.registrar(_video("b", hora="17:00"), [], "topo")
    assert variedade.estilo_capa(_video("c", hora="19:00")) not in ("base", "topo")


def test_busca_evita_e_varia_pela_semente():
    from pipeline.catalogo import buscar_clipe
    primeira = buscar_clipe("vice city", semente="post1")
    if primeira is None:
        pytest.skip("catálogo vazio")
    outra = buscar_clipe("vice city", semente="post1", evitar={primeira.entrada["arquivo"]})
    assert outra is not None and outra.entrada["arquivo"] != primeira.entrada["arquivo"]


def test_assunto_da_imagem_junta_versoes_do_mesmo_personagem():
    from pipeline.variedade import assunto_da_imagem
    assert assunto_da_imagem("clipes/oficial/screenshots/Boobie_Ike_04.jpg") == "boobie_ike"
    assert assunto_da_imagem("clipes/oficial/artes_e_wallpapers/Boobie_Ike_portrait.jpg") == "boobie_ike"
    assert assunto_da_imagem("x/Leonida_Keys_Postcard_tablet.jpg") == "leonida_keys"


def test_baixar_videos_oficiais_registra_no_estado(tmp_path, monkeypatch):
    from unittest.mock import MagicMock
    from pipeline import biblioteca
    monkeypatch.setattr(biblioteca, "PASTA_OFICIAL", tmp_path)
    monkeypatch.setattr(biblioteca, "ESTADO", tmp_path / "biblioteca.json")
    resp = MagicMock(status_code=200)
    resp.__enter__.return_value = resp
    resp.iter_content.return_value = [b"x" * 2_000_000]
    sessao = MagicMock()
    sessao.get.return_value = resp
    novos = biblioteca.baixar_videos([{"nome": "extended", "url": "https://videos.x/v.mp4"}], sessao, mostrar=lambda *_: None)
    assert novos and (tmp_path / "trailers" / "extended.mp4").exists()
    assert "https://videos.x/v.mp4" in (tmp_path / "biblioteca.json").read_text()
    assert biblioteca.baixar_videos([{"nome": "extended", "url": "https://videos.x/v.mp4"}], sessao) == []


def test_estilo_noticia_manchete_e_tomadas(tmp_path):
    from pipeline.estilo_noticia import _palavras_marcadas, desenhar_manchete, tomadas_por_cena
    from pipeline.marca import carregar_marca
    assert tomadas_por_cena(2.0) == 1 and tomadas_por_cena(7.0) == 3
    assert ("FERIADO", True) in _palavras_marcadas("GTA 6 lança na quinta e *sexta é feriado*")
    png = desenhar_manchete(carregar_marca("gg_explica"), "Teste *ok*", "rumor", "IGN, 11/11/2026",
                            "Imagens: Rockstar Games", tmp_path / "m.png")
    from PIL import Image
    assert Image.open(png).size == (1080, 1920)


def test_ritmo_acelera_reel_longo_e_bloqueia_so_o_muito_longo():
    from pipeline.marca import carregar_marca
    from pipeline.modelos import Video
    from pipeline.montagem import ajustar_ritmo
    from pipeline.qualidade import checar_pauta
    import copy
    import dataclasses
    marca = carregar_marca("gg_explica")
    dados = copy.deepcopy(marca.dados)
    dados["voz"]["provedor"] = "azure"               # a aceleração só existe na voz da Azure
    marca = dataclasses.replace(marca, dados=dados)
    def video(palavras):
        return Video.model_validate({"id": "t", "serie": "radar", "horario": "09:00", "formato": "reel",
            "data": "2026-11-15", "legenda_post": "x", "cenas": [
                {"tipo": "gancho", "titulo": "Manchete", "narracao": "Olha isso."},
                {"tipo": "tela_cheia", "titulo": "T", "midia": "busca:praia", "credito": "Imagens: Rockstar Games",
                 "narracao": " ".join(["palavra"] * palavras)}]})
    v = video(165)                                    # ~57 s na voz da marca: passa
    assert not any("passa de 60s" in b for b in checar_pauta(marca, v)[0])
    assert ajustar_ritmo(marca, video(185)).dados["voz"]["azure"]["velocidade"] != "+12%"
    assert any("passa de 60s" in b for b in checar_pauta(marca, video(230))[0])
