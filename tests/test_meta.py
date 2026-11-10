"""Um token só para a Meta: descoberta da conta, token da Página, carrossel pela API e fila."""
from __future__ import annotations

from datetime import date, time
from pathlib import Path

import pytest

from pipeline import meta
from pipeline.facebook import CredenciaisFacebook
from pipeline.instagram import Credenciais, ErroInstagram, Publicador


class Resp:
    def __init__(self, dados, status=200):
        self.dados, self.status_code, self.text = dados, status, str(dados)

    def json(self):
        return self.dados


class SessaoFalsa:
    """Responde como a Graph API e guarda as chamadas."""

    def __init__(self):
        self.chamadas: list[tuple[str, str, dict]] = []
        self.n = 0

    def _novo(self, prefixo):
        self.n += 1
        return f"{prefixo}{self.n}"

    def get(self, url, params=None, timeout=None):
        self.chamadas.append(("GET", url, params or {}))
        campos = (params or {}).get("fields", "")
        if campos == "instagram_business_account":
            return Resp({"instagram_business_account": {"id": "17841"}, "id": "PAG"})
        if campos == "access_token":
            return Resp({"access_token": "TOKEN_DA_PAGINA", "id": "PAG"})
        if campos == "images":
            return Resp({"images": [{"width": 720, "source": "https://cdn/p.jpg"},
                                    {"width": 1080, "source": "https://cdn/g.jpg"}]})
        if campos.startswith("status_code"):
            return Resp({"status_code": "FINISHED"})
        if campos == "permalink":
            return Resp({"permalink": "https://www.instagram.com/p/X/"})
        return Resp({}, 404)

    def post(self, url, data=None, files=None, headers=None, timeout=None):
        self.chamadas.append(("POST", url, dict(data or {}) if isinstance(data, dict) else {}))
        if url.endswith("/photos"):
            return Resp({"id": self._novo("foto")})
        if url.endswith("/media"):
            return Resp({"id": self._novo("cont")})
        if url.endswith("/media_publish"):
            return Resp({"id": "MIDIA"})
        return Resp({}, 404)

    def delete(self, url, params=None, timeout=None):
        self.chamadas.append(("DELETE", url, params or {}))
        return Resp({"success": True})


@pytest.fixture(autouse=True)
def _limpo(monkeypatch):
    for v in ("META_TOKEN_GG_EXPLICA", "IG_TOKEN_GG_EXPLICA", "IG_USER_ID_GG_EXPLICA", "FB_PAGE_ID_GG_EXPLICA",
              "FB_PAGE_TOKEN_GG_EXPLICA"):
        monkeypatch.delenv(v, raising=False)
    meta.limpar_cache()
    yield
    meta.limpar_cache()


def test_token_unico_descobre_a_conta_do_instagram(monkeypatch):
    monkeypatch.setenv("META_TOKEN_GG_EXPLICA", "T" * 60)
    monkeypatch.setenv("FB_PAGE_ID_GG_EXPLICA", "PAG")
    sessao = SessaoFalsa()
    monkeypatch.setattr(meta.requests, "Session", lambda: sessao)
    cred = Credenciais.da_marca("gg_explica")
    assert cred.ig_user_id == "17841" and cred.token == "T" * 60


def test_formato_antigo_tem_prioridade(monkeypatch):
    monkeypatch.setenv("IG_USER_ID_GG_EXPLICA", "111")
    monkeypatch.setenv("IG_TOKEN_GG_EXPLICA", "velho")
    monkeypatch.setenv("META_TOKEN_GG_EXPLICA", "novo")
    cred = Credenciais.da_marca("gg_explica")
    assert (cred.ig_user_id, cred.token) == ("111", "novo")   # META_TOKEN vence o IG_TOKEN


def test_sem_nada_explica_o_que_falta():
    with pytest.raises(ErroInstagram, match="META_TOKEN_GG_EXPLICA"):
        Credenciais.da_marca("gg_explica")


def test_facebook_pega_o_token_da_pagina_na_hora(monkeypatch):
    monkeypatch.setenv("META_TOKEN_GG_EXPLICA", "T" * 60)
    monkeypatch.setenv("FB_PAGE_ID_GG_EXPLICA", "PAG")
    cred = CredenciaisFacebook.da_marca("gg_explica")
    assert cred is not None and cred.token == ""          # nada de rede só para saber se dá
    assert cred.garantir_token(SessaoFalsa()) == "TOKEN_DA_PAGINA"
    assert meta.pode_hospedar("gg_explica")


def test_carrossel_hospeda_publica_e_apaga(tmp_path):
    slides = []
    for i in range(3):
        f = tmp_path / f"{i + 1:02d}.jpg"
        f.write_bytes(b"jpg")
        slides.append(f)
    s = SessaoFalsa()
    hosp = meta.Hospedeiro("PAG", "TOKEN_DA_PAGINA", s)
    pub = Publicador(Credenciais("17841", "T"), sessao=s, espera_s=0)
    res = pub.publicar_carrossel(slides, "legenda", hosp)
    assert res["media_id"] == "MIDIA"
    itens = [c for c in s.chamadas if c[0] == "POST" and c[2].get("is_carousel_item") == "true"]
    assert [c[2]["image_url"] for c in itens] == ["https://cdn/g.jpg"] * 3     # a maior versão
    pai = [c for c in s.chamadas if c[2].get("media_type") == "CAROUSEL"][0]
    assert len(pai[2]["children"].split(",")) == 3 and pai[2]["caption"] == "legenda"
    assert sum(1 for c in s.chamadas if c[0] == "DELETE") == 3               # as fotos somem da Página


def test_carrossel_recusa_uma_imagem_so(tmp_path):
    f = tmp_path / "01.jpg"
    f.write_bytes(b"jpg")
    s = SessaoFalsa()
    hosp = meta.Hospedeiro("PAG", "TP", s)
    pub = Publicador(Credenciais("17841", "T"), sessao=s, espera_s=0)
    with pytest.raises(ErroInstagram, match="2 a 10"):
        pub.publicar_carrossel([f], "x", hosp)


def test_reel_com_capa_usa_cover_url(tmp_path):
    v = tmp_path / "reel.mp4"
    v.write_bytes(b"0" * 10)
    s = SessaoFalsa()
    s.post_original = s.post

    def post(url, data=None, files=None, headers=None, timeout=None):
        if "rupload" in url:
            return Resp({"success": True})
        return s.post_original(url, data=data, files=files, headers=headers, timeout=timeout)
    s.post = post
    Publicador(Credenciais("17841", "T"), sessao=s, espera_s=0).publicar_reel(v, "x", capa_url="https://cdn/c.jpg")
    cont = [c for c in s.chamadas if c[2].get("media_type") == "REELS"][0][2]
    assert cont["cover_url"] == "https://cdn/c.jpg" and "thumb_offset" not in cont


def test_erro_da_api_nao_mostra_o_token():
    with pytest.raises(meta.ErroMeta) as e:
        meta._checar(Resp({"error": {"message": "Invalid OAuth", "code": 190, "fbtrace_id": "x",
                                     "access_token": "SEGREDO"}}, 400))
    assert "SEGREDO" not in str(e.value) and "190" in str(e.value)


def test_carrossel_entra_na_fila_com_o_reel_depois(monkeypatch, tmp_path):
    from pipeline import fila, producao
    from pipeline.marca import carregar_marca
    from pipeline.modelos import Video

    monkeypatch.setenv("META_TOKEN_GG_EXPLICA", "T" * 60)
    monkeypatch.setenv("FB_PAGE_ID_GG_EXPLICA", "PAG")
    monkeypatch.setattr(fila, "ARQUIVO_FILA", tmp_path / "fila.json")
    monkeypatch.setattr(fila, "PASTA_LOTES", tmp_path / "lotes")
    monkeypatch.setattr(producao, "exportar_lote", lambda plat, *a, **k: tmp_path / plat)
    pasta = tmp_path / "post"
    pasta.mkdir()
    for n in ("01.jpg", "02.jpg", "reel.mp4", "capa_reel.jpg"):
        (pasta / n).write_bytes(b"x")
    video = Video.model_validate({
        "id": "guia", "data": date(2026, 11, 10).isoformat(), "horario": time(12, 30).isoformat(),
        "serie": "gg_explica", "formato": "carrossel", "plataformas": ["instagram", "tiktok"],
        "legenda_post": "x", "cenas": [{"tipo": "gancho", "titulo": "a"}, {"tipo": "cta", "titulo": "b", "texto": "c"}]})
    producao.enfileirar_carrossel(carregar_marca("gg_explica"), video, pasta, "legenda", [])
    itens = {(i.id, i.plataforma, i.tipo): i for i in fila.carregar()}
    assert ("guia", "instagram", "carrossel") in itens
    reel = itens[("guia_reel", "instagram", "reel")]
    assert reel.quando.startswith("2026-11-10T15:30") and reel.capa.endswith("capa_reel.jpg")
    assert ("guia_reel", "facebook", "reel") in itens


def test_carrossel_sem_pagina_vai_para_o_lote(monkeypatch, tmp_path):
    from pipeline import fila, producao
    from pipeline.marca import carregar_marca
    from pipeline.modelos import Video

    monkeypatch.setattr(fila, "ARQUIVO_FILA", tmp_path / "fila.json")
    lotes = []
    monkeypatch.setattr(producao, "exportar_lote", lambda plat, *a, **k: lotes.append(plat))
    video = Video.model_validate({
        "id": "g", "data": "2026-11-10", "horario": "12:30", "serie": "gg_explica", "formato": "carrossel",
        "plataformas": ["instagram", "tiktok"], "legenda_post": "x",
        "cenas": [{"tipo": "gancho", "titulo": "a"}, {"tipo": "cta", "titulo": "b", "texto": "c"}]})
    producao.enfileirar_carrossel(carregar_marca("gg_explica"), video, tmp_path, "l", [])
    assert lotes == ["instagram", "tiktok"] and fila.carregar() == []
