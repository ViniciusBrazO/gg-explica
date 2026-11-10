"""Testes das peças de escala: biblioteca oficial, carrossel, manchete, página em espanhol,
Facebook, YouTube e o despacho da fila. Nada aqui acessa a internet."""
import io
import json
import zipfile
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from PIL import Image

from pipeline import biblioteca, catalogo, claude_cli, fila, producao
from pipeline.cartoes import montar_html
from pipeline.facebook import CredenciaisFacebook, ErroFacebook, PublicadorFacebook
from pipeline.marca import RAIZ, carregar_marca
from pipeline.modelos import Video
from pipeline.telegram import Telegram
from pipeline.youtube import (CredenciaisYouTube, ErroYouTube, PublicadorYouTube, metadados,
                              titulo_da_legenda)


def _resposta(status=200, dados=None, headers=None, conteudo=b""):
    r = MagicMock()
    r.status_code = status
    r.json.return_value = dados if dados is not None else {}
    r.text = json.dumps(dados or {})
    r.headers = headers or {}
    r.iter_content.return_value = [conteudo]
    r.__enter__.return_value = r
    r.__exit__.return_value = False
    r.raise_for_status.return_value = None
    return r


def _zip_de_teste() -> bytes:
    buf = io.BytesIO()
    img = io.BytesIO()
    Image.new("RGB", (64, 36), (200, 255, 46)).save(img, "JPEG")
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("GTAVI_Screenshots/Jason_e_Lucia_01.jpg", img.getvalue())
        z.writestr("../../fora_da_pasta.jpg", img.getvalue())     # caminho malicioso: vira só o nome
        z.writestr("leia-me.txt", "não é mídia")
        z.writestr("GTAVI_Screenshots/", "")
    return buf.getvalue()


def _carrossel(marca="gg_explica", **extra) -> Video:
    return Video.model_validate({
        "id": "tudo_sobre_lucia", "serie": "gg_explica", "data": "2026-11-12", "horario": "19:00",
        "formato": "carrossel", "legenda_post": "Tudo o que é oficial sobre a Lucia até agora.",
        "cenas": [
            {"tipo": "gancho", "titulo": "Tudo sobre a *Lucia*"},
            {"tipo": "texto", "selo": "confirmado", "titulo": "Primeira protagonista",
             "texto": "Lucia Caminos é a primeira protagonista mulher da série.",
             "fonte": "Rockstar Games, 12/2023", "fonte_url": "https://www.rockstargames.com/VI"},
            {"tipo": "cta", "texto": "Salva pra consultar no lançamento"},
        ], **extra})


# ---------------------------------------------------------------- biblioteca oficial

def test_extrair_so_midia_sem_subpasta_e_sem_escapar(tmp_path):
    arq = tmp_path / "pacote.zip"
    arq.write_bytes(_zip_de_teste())
    destino = tmp_path / "oficial" / "screenshots"
    extraidos = biblioteca.extrair(arq, destino)
    assert sorted(p.name for p in extraidos) == ["Jason_e_Lucia_01.jpg", "fora_da_pasta.jpg"]
    assert all(p.parent == destino for p in extraidos)
    assert not (tmp_path / "fora_da_pasta.jpg").exists()
    assert biblioteca.extrair(arq, destino) == []     # segunda vez: nada repetido


@pytest.fixture
def biblioteca_isolada(tmp_path, monkeypatch):
    monkeypatch.setattr(biblioteca, "PASTA_OFICIAL", tmp_path / "clipes" / "oficial")
    monkeypatch.setattr(biblioteca, "PASTA_CLIPES", tmp_path / "clipes")
    monkeypatch.setattr(biblioteca, "ESTADO", tmp_path / "saida" / "biblioteca.json")
    monkeypatch.setattr(biblioteca, "config", lambda: {"biblioteca": {"pacotes": [
        {"nome": "screenshots", "url": "https://exemplo.test/GTAVI_Screenshots.zip"},
        {"nome": "videos", "url": "https://exemplo.test/GTAVI_Videos.zip"}]}})
    catalogados = []
    monkeypatch.setattr(biblioteca, "catalogar", lambda pasta: catalogados.append(pasta))
    return tmp_path, catalogados


def test_biblioteca_baixa_uma_vez_e_so_baixa_de_novo_quando_muda(biblioteca_isolada):
    tmp_path, catalogados = biblioteca_isolada
    conteudo = _zip_de_teste()
    cab = {"Content-Length": str(len(conteudo)), "Last-Modified": "Mon, 03 Nov 2026 12:00:00 GMT"}
    sessao = MagicMock()
    sessao.head.side_effect = lambda url, **kw: (_resposta(404) if "Videos" in url else _resposta(headers=cab))
    sessao.get.return_value = _resposta(conteudo=conteudo)
    msgs = []
    novos = biblioteca.atualizar(sessao=sessao, mostrar=msgs.append)
    assert {p.name for p in novos} == {"Jason_e_Lucia_01.jpg", "fora_da_pasta.jpg"}
    assert any("404" in m for m in msgs)                 # link quebrado avisa e segue
    assert catalogados == [tmp_path / "clipes"]
    assert not list((tmp_path / "clipes" / "oficial" / "_zips").glob("*.zip"))   # zip apagado
    estado = json.loads((tmp_path / "saida" / "biblioteca.json").read_text(encoding="utf-8"))
    assert estado["https://exemplo.test/GTAVI_Screenshots.zip"]["arquivos"] == 2

    sessao.get.reset_mock()
    msgs.clear()
    assert biblioteca.atualizar(sessao=sessao, mostrar=msgs.append) == []
    sessao.get.assert_not_called()
    assert any("sem novidade" in m for m in msgs)

    cab["Last-Modified"] = "Fri, 21 Nov 2026 12:00:00 GMT"     # a Rockstar trocou o pacote
    biblioteca.atualizar(sessao=sessao, mostrar=msgs.append)
    sessao.get.assert_called_once()


# ---------------------------------------------------------------- catálogo: planos e imagens

def test_momentos_por_cortes_um_plano_por_trecho():
    m = catalogo.momentos_por_cortes([0.5, 3.0, 15.0], 20.0)
    assert [(x["inicio"], x["fim"]) for x in m] == [(0.5, 3.0), (3.0, 9.0), (9.0, 15.0), (15.0, 20.0)]
    assert [x["corte"] for x in m] == [1, 2, 3, 4]


def test_catalogar_imagens_com_folha_numerada_e_busca(tmp_path, monkeypatch):
    pasta = tmp_path / "clipes"
    (pasta / "oficial" / "screenshots").mkdir(parents=True)
    for nome, cor in (("praia_vice_city.jpg", (255, 120, 60)), ("Jason_carro.png", (40, 80, 200))):
        Image.new("RGB", (1920, 1080), cor).save(pasta / "oficial" / "screenshots" / nome)
    (pasta / "_folhas").mkdir()
    Image.new("RGB", (10, 10)).save(pasta / "_folhas" / "ignorar.jpg")   # folha não vira mídia
    novos = catalogo.catalogar(pasta)
    assert {Path(e["arquivo"]).name for e in novos} == {"praia_vice_city.jpg", "Jason_carro.png"}
    assert all(e["tipo"] == "imagem" and e["largura"] == 1920 for e in novos)
    assert {e["posicao_na_folha"] for e in novos} == {1, 2}
    assert len({e["folha"] for e in novos}) == 1

    monkeypatch.setattr(catalogo, "ARQUIVO_USO", tmp_path / "uso.json")
    escolha = catalogo.buscar_clipe("praia de vice city", pasta)
    assert escolha is not None and escolha.caminho.name == "praia_vice_city.jpg" and escolha.fim is None
    assert catalogo.catalogar(pasta) == []               # já catalogadas


# ---------------------------------------------------------------- formatos: carrossel e manchete

def test_carrossel_dispensa_narracao_mas_reel_nao():
    v = _carrossel()
    assert v.formato == "carrossel" and v.cenas[1].narracao == ""
    with pytest.raises(ValueError, match="narração"):
        _carrossel(formato="reel")


def test_carrossel_precisa_de_2_a_20_slides():
    with pytest.raises(ValueError, match="2 a 20"):
        Video.model_validate({"id": "x", "serie": "radar", "data": "2026-11-12", "horario": "19:00",
                              "formato": "carrossel", "legenda_post": "x",
                              "cenas": [{"tipo": "gancho", "titulo": "Só a capa"}]})


@pytest.mark.parametrize("marca_id,fonte,arraste,lang", [
    ("gg_explica", "Fonte:", "Arraste para o lado", 'lang="pt-BR"'),
    ("gg_explica_es", "Fuente:", "Desliza para ver más", 'lang="es"'),
])
def test_slide_revista_no_idioma_da_pagina(marca_id, fonte, arraste, lang):
    from pipeline.carrossel import montar_slide

    marca, v = carregar_marca(marca_id), _carrossel()
    capa, fato, final = (montar_slide(marca, v, i, None) for i in range(3))
    assert arraste in capa and 'class="p-capa' in capa and lang in capa
    assert fonte in fato and 'class="p-fato' in fato and marca.dados["selos"]["confirmado"]["rotulo"] in fato
    assert 'class="p-final' in final and marca.dados["arroba"] in final
    assert marca.dados["arroba"].replace("@", "") in capa          # assinatura no alto do slide


def test_modelo_classico_continua_disponivel(monkeypatch):
    from pipeline.carrossel import montar_slide

    marca, v = carregar_marca("gg_explica"), _carrossel()
    monkeypatch.setitem(marca.dados, "carrossel", {"modelo": "classico"})   # a marca fica em cache
    capa = montar_slide(marca, v, 0, None)
    assert "slide-capa" in capa and "1/3" in capa


def test_papeis_e_itens_do_carrossel():
    from pipeline.carrossel import dividir_item, papel_do_slide

    v = _carrossel()
    v.cenas.insert(2, v.cenas[1].model_copy(update={"tipo": "lista", "itens": ["a: b"], "estilo": "tabela"}))
    v.cenas.insert(2, v.cenas[1].model_copy(update={"tipo": "lista", "itens": ["a: b"]}))
    assert [papel_do_slide(v, i) for i in range(len(v.cenas))] == ["capa", "fato", "lista", "tabela", "final"]
    assert dividir_item("Câmera: Uma câmera filmou o crime") == {"icone": "", "t": "Câmera", "d": "Uma câmera filmou o crime"}
    assert dividir_item("📷 Câmera: filmou") == {"icone": "📷", "t": "Câmera", "d": "Filmou"}
    assert dividir_item("Só descrição") == {"icone": "", "t": "", "d": "Só descrição"}
    assert dividir_item("*Lucia* é a protagonista")["d"] == "*Lucia* é a protagonista"


def test_manchete_usa_o_estilo_proprio():
    marca = carregar_marca("gg_explica")
    html_doc = montar_html(marca, {"tipo": "gancho", "estilo": "manchete", "titulo": "GTA VI *chegou*",
                                   "kicker": "RADAR", "itens": []}, modo="cartao")
    assert "estilo-manchete" in html_doc and "manchete-titulo" in html_doc


def test_cena_em_espanhol_rotula_a_fonte():
    marca = carregar_marca("gg_explica_es")
    html_doc = montar_html(marca, {"tipo": "texto", "titulo": "Fecha", "texto": "19 de noviembre",
                                   "selo": "confirmado", "fonte": "Rockstar Games, 2026", "itens": []})
    assert "Fuente: Rockstar Games" in html_doc and 'lang="es"' in html_doc


@pytest.mark.lento
def test_renderizar_carrossel_gera_slides_4x5(tmp_path, monkeypatch):
    from pipeline.carrossel import renderizar_carrossel

    pasta = renderizar_carrossel(carregar_marca("gg_explica"), _carrossel(), tmp_path)
    slides = sorted(pasta.glob("*.jpg"))
    assert [s.name for s in slides] == ["01.jpg", "02.jpg", "03.jpg", "capa_reel.jpg"]
    with Image.open(slides[0]) as img:
        assert img.size == (1080, 1350)
    with Image.open(pasta / "capa_reel.jpg") as img:
        assert img.size == (1080, 1920)
    assert (pasta / "reel.mp4").stat().st_size > 10_000
    assert not (pasta / "_trabalho").exists()


# ---------------------------------------------------------------- Telegram: álbum do carrossel

@pytest.mark.parametrize("quantos,esperado", [(11, ["sendMediaGroup", "sendPhoto"]),
                                              (12, ["sendMediaGroup", "sendMediaGroup"])])
def test_album_agrupa_de_10_em_10(tmp_path, quantos, esperado):
    fotos = []
    for i in range(quantos):
        f = tmp_path / f"{i + 1:02d}.jpg"
        f.write_bytes(b"jpg")
        fotos.append(f)
    tg = Telegram("token", "123")
    tg._chamar = MagicMock(return_value={})
    tg.album(fotos)
    assert [c.args[0] for c in tg._chamar.call_args_list] == esperado
    primeiro = tg._chamar.call_args_list[0].kwargs
    assert len(json.loads(primeiro["data"]["media"])) == 10


# ---------------------------------------------------------------- Facebook

def test_facebook_reel_em_tres_passos(tmp_path):
    video = tmp_path / "v.mp4"
    video.write_bytes(b"0" * 2048)
    sessao = MagicMock()
    sessao.post.side_effect = [_resposta(dados={"video_id": "555"}), _resposta(dados={"success": True}),
                               _resposta(dados={"success": True})]
    res = PublicadorFacebook(CredenciaisFacebook("pagina", "tok"), sessao).publicar_reel(video, "legenda")
    assert res == {"media_id": "555", "permalink": "https://www.facebook.com/reel/555"}
    inicio, envio, fim = sessao.post.call_args_list
    assert inicio.kwargs["data"]["upload_phase"] == "start"
    assert envio.args[0].endswith("/555") and envio.kwargs["headers"]["file_size"] == "2048"
    assert fim.kwargs["data"]["video_state"] == "PUBLISHED" and fim.kwargs["data"]["description"] == "legenda"


def test_facebook_erro_da_api_vira_excecao(tmp_path):
    video = tmp_path / "v.mp4"
    video.write_bytes(b"0")
    sessao = MagicMock()
    sessao.post.return_value = _resposta(400, {"error": {"message": "token inválido"}})
    with pytest.raises(ErroFacebook, match="token inválido"):
        PublicadorFacebook(CredenciaisFacebook("p", "t"), sessao).publicar_reel(video, "x")


# ---------------------------------------------------------------- YouTube

def test_titulo_do_short_pula_publi_e_hashtag():
    legenda = "#publi Link de afiliado: posso ganhar comissão.\n\nGTA VI sai dia 19: o que já é oficial\n\n#gta6 #games"
    assert titulo_da_legenda(legenda) == "GTA VI sai dia 19: o que já é oficial"
    longo = "palavra " * 30
    t = titulo_da_legenda(longo)
    assert len(t) <= 100 and t.endswith("…") and "palavra…" in t
    assert titulo_da_legenda("<b>Vice City</b>") == "‹b›Vice City‹/b›"


def test_metadados_do_short():
    m = metadados("Título", "desc", "es", ["#gta6", "#games"])
    assert m["status"] == {"privacyStatus": "public", "selfDeclaredMadeForKids": False,
                           "containsSyntheticMedia": True}
    assert m["snippet"]["defaultLanguage"] == "es-419" and m["snippet"]["tags"] == ["gta6", "games"]
    assert m["snippet"]["categoryId"] == "20"
    quando = datetime(2026, 11, 19, 22, 0, tzinfo=timezone.utc)
    prog = metadados("T", "d", publicar_em=quando)["status"]
    assert prog["privacyStatus"] == "private" and prog["publishAt"].startswith("2026-11-19")


def test_youtube_envio_resumivel(tmp_path):
    video = tmp_path / "v.mp4"
    video.write_bytes(b"0" * 4096)
    sessao = MagicMock()
    sessao.post.side_effect = [_resposta(dados={"access_token": "ya29"}),
                               _resposta(headers={"Location": "https://upload.test/sessao/1"})]
    sessao.put.return_value = _resposta(dados={"id": "abc123", "status": {"uploadStatus": "uploaded"}})
    pub = PublicadorYouTube(CredenciaisYouTube("cid", "segredo", "refresh"), sessao)
    res = pub.publicar_short(video, "Linha de título\n\n#gta6", tags=["#gta6"])
    assert res == {"media_id": "abc123", "permalink": "https://youtube.com/shorts/abc123"}
    token, abrir = sessao.post.call_args_list
    assert token.kwargs["data"]["grant_type"] == "refresh_token"
    assert "uploadType=resumable" in abrir.args[0]
    assert abrir.kwargs["headers"]["X-Upload-Content-Length"] == "4096"
    corpo = json.loads(abrir.kwargs["data"])
    assert corpo["snippet"]["title"] == "Linha de título"
    put = sessao.put.call_args
    assert put.args[0] == "https://upload.test/sessao/1" and put.kwargs["headers"]["Authorization"] == "Bearer ya29"


def test_youtube_sem_endereco_de_envio_falha(tmp_path):
    video = tmp_path / "v.mp4"
    video.write_bytes(b"0")
    sessao = MagicMock()
    sessao.post.side_effect = [_resposta(dados={"access_token": "ya29"}), _resposta(headers={})]
    with pytest.raises(ErroYouTube, match="endereço"):
        PublicadorYouTube(CredenciaisYouTube("c", "s", "r"), sessao).publicar_short(video, "x")


# ---------------------------------------------------------------- o que sai sozinho e o que vai para o lote

def test_automatico_conforme_credenciais(monkeypatch):
    for var in ("FB_PAGE_ID_GG_EXPLICA", "FB_PAGE_TOKEN_GG_EXPLICA", "YT_CLIENT_ID", "YT_CLIENT_SECRET",
                "YT_REFRESH_TOKEN_GG_EXPLICA"):
        monkeypatch.delenv(var, raising=False)
    assert producao.automatico_em("instagram", "gg_explica")
    assert not any(producao.automatico_em(p, "gg_explica") for p in ("tiktok", "kwai", "facebook", "youtube"))
    monkeypatch.setenv("FB_PAGE_ID_GG_EXPLICA", "1")
    monkeypatch.setenv("FB_PAGE_TOKEN_GG_EXPLICA", "t")
    monkeypatch.setenv("YT_CLIENT_ID", "c")
    monkeypatch.setenv("YT_CLIENT_SECRET", "s")
    assert producao.automatico_em("facebook", "gg_explica")
    assert not producao.automatico_em("youtube", "gg_explica")       # falta o refresh do canal
    monkeypatch.setenv("YT_REFRESH_TOKEN_GG_EXPLICA", "r")
    assert producao.automatico_em("youtube", "gg_explica")
    assert not producao.automatico_em("tiktok", "gg_explica")         # TikTok: o clique é seu


def test_publicar_despacha_para_o_youtube(tmp_path, monkeypatch):
    from argparse import Namespace

    import pipeline.youtube as yt
    from pipeline.cli import cmd_publicar

    monkeypatch.setattr(fila, "ARQUIVO_FILA", tmp_path / "fila.json")
    for var, valor in (("YT_CLIENT_ID", "c"), ("YT_CLIENT_SECRET", "s"), ("YT_REFRESH_TOKEN_GG_EXPLICA_ES", "r")):
        monkeypatch.setenv(var, valor)
    video = tmp_path / "v.mp4"
    video.write_bytes(b"0")
    antes = (datetime.now(fila.FUSO) - timedelta(minutes=5)).isoformat()
    fila.salvar([fila.Item(id="v1", marca="gg_explica_es", video=str(video), capa="", plataforma="youtube",
                           legenda="GTA VI ya salió\n\n#gta6 #games", quando=antes)])
    chamadas = []

    class Falso:
        def __init__(self, cred):
            assert cred.refresh_token == "r"

        def publicar_short(self, arquivo, legenda, idioma, tags):
            chamadas.append((arquivo, idioma, tags))
            return {"media_id": "yt1", "permalink": "https://youtube.com/shorts/yt1"}

    monkeypatch.setattr(yt, "PublicadorYouTube", Falso)
    cmd_publicar(Namespace(simular=False))
    assert chamadas == [(video, "es", ["#gta6", "#games"])]
    item = fila.carregar()[0]
    assert item.status == "publicado" and item.permalink.endswith("yt1")


# ---------------------------------------------------------------- tarefas do Claude

def test_tarefa_de_traducao_existe_e_tem_data():
    assert "traducao" in claude_cli.TAREFAS
    texto = claude_cli.montar_prompt("traducao", hoje=datetime(2026, 11, 9, 8, 0))
    assert "09/11/2026" in texto and "gg_explica_es" in texto


def test_pagina_em_espanhol_herda_selos_e_tem_idioma():
    es, pt = carregar_marca("gg_explica_es"), carregar_marca("gg_explica")
    assert es.dados["idioma"] == "es" and pt.dados["idioma"] == "pt"
    assert set(es.dados["selos"]) == set(pt.dados["selos"])
    assert es.dados["selos"]["relato"]["rotulo"] == "REPORTE"


def test_traducao_desligada_nao_chama_o_claude(monkeypatch, capsys):
    from argparse import Namespace

    import pipeline.claude_cli as cc
    import pipeline.radar as radar
    from pipeline.cli import cmd_claude

    monkeypatch.setattr(radar, "config", lambda: {"traducao": {"ativa": False}})
    monkeypatch.setattr(cc, "rodar", lambda *a, **k: pytest.fail("não devia chamar o Claude"))
    assert cmd_claude(Namespace(tarefa="traducao", contexto="")) == 0
    assert "desligada" in capsys.readouterr().out


def test_series_novas_existem_nas_duas_paginas():
    for marca_id in ("gg_explica", "gg_explica_es"):
        series = carregar_marca(marca_id).series
        assert "gta_no_brasil" in series and series["pao_duro"]["leva_link"]
