from datetime import datetime, timedelta

from pipeline.fila import FUSO, Item
from pipeline.ritmo import motivo_para_segurar


def _item(n, quando, status="pendente", publicado_em=""):
    return Item(id=f"p{n}", marca="gg_explica", video="v", capa="", legenda="x", quando=quando.isoformat(),
                status=status, publicado_em=publicado_em)


def test_freio_intervalo_e_limite_diario():
    agora = datetime(2026, 11, 11, 15, 0, tzinfo=FUSO)
    novo = _item(99, agora)
    # saiu há 30 min: espera
    recente = _item(1, agora, "publicado", (agora - timedelta(minutes=30)).isoformat())
    assert "intervalo" in motivo_para_segurar(novo, [recente, novo], agora)
    # 6 nas últimas 24 h, espaçados: bate o limite
    seis = [_item(i, agora, "publicado", (agora - timedelta(hours=2 * i + 2)).isoformat()) for i in range(6)]
    assert "limite" in motivo_para_segurar(novo, seis + [novo], agora)
    # 5 no dia e o último há 2 h: pode sair
    assert motivo_para_segurar(novo, seis[:5] + [novo], agora) == ""
    # outra rede não conta
    for i in seis:
        i.plataforma = "facebook"
    assert motivo_para_segurar(novo, seis + [novo], agora) == ""


def test_bastidor_do_redator_e_kicker_igual_ao_selo_bloqueiam():
    from pipeline.marca import carregar_marca
    from pipeline.modelos import Video
    from pipeline.qualidade import checar_pauta
    marca = carregar_marca("gg_explica")
    v = Video.model_validate({"id": "t", "serie": "radar", "horario": "12:00", "formato": "carrossel", "data": "2026-11-11",
        "legenda_post": "Detalhes eu não li: confira nos links.",
        "cenas": [{"tipo": "gancho", "kicker": "RELATO", "selo": "relato", "titulo": "Festival",
                   "fonte": "Eurogamer, 09/11/2026", "fonte_url": "https://www.eurogamer.net/x"},
                  {"tipo": "texto", "titulo": "Mais", "texto": "x"}]})
    bloqueios, _ = checar_pauta(marca, v)
    texto = " ".join(bloqueios)
    assert "kicker repete o selo" in texto and "frase proibida" in texto


def test_carrossel_com_mais_de_10_slides_bloqueia():
    from pipeline.marca import carregar_marca
    from pipeline.modelos import Video
    from pipeline.qualidade import checar_pauta
    cenas = [{"tipo": "gancho", "titulo": "Capa"}] + [{"tipo": "texto", "titulo": f"Slide {n}", "texto": f"fato {n}"}
                                                    for n in range(10)]
    v = Video.model_validate({"id": "t", "serie": "radar", "horario": "12:00", "formato": "carrossel",
                              "data": "2026-11-11", "legenda_post": "x", "cenas": cenas})
    assert any("até 10" in b for b in checar_pauta(carregar_marca("gg_explica"), v)[0])


def test_promessa_sem_entrega_e_carrossel_curto_bloqueiam():
    from pipeline.marca import carregar_marca
    from pipeline.modelos import Video
    from pipeline.qualidade import checar_pauta
    cenas = [{"tipo": "gancho", "titulo": "Capa"},
             {"tipo": "texto", "titulo": "Horas", "texto": "O Canaltech calculou quantas horas o brasileiro trabalha."},
             {"tipo": "cta", "titulo": "Fim", "texto": "Segue"}]
    v = Video.model_validate({"id": "t", "serie": "radar", "horario": "12:00", "formato": "carrossel",
                              "data": "2026-11-11", "legenda_post": "x", "cenas": cenas})
    texto = " ".join(checar_pauta(carregar_marca("gg_explica"), v)[0])
    assert "mínimo é 5" in texto and "calculou" in texto


def test_dossie_monta_com_texto_das_materias(tmp_path, monkeypatch):
    from datetime import date
    from pipeline import dossie, redator
    monkeypatch.setattr(dossie, "ARQUIVO", tmp_path / "dossie.md")
    monkeypatch.setattr(redator, "noticias_pendentes", lambda hoje, maximo: [{"ids": ["a"], "manchetes": []}])
    monkeypatch.setattr(redator, "com_textos", lambda assuntos, por: [{"ids": ["a"], "outras_manchetes": [],
        "fontes": [{"veiculo": "Canaltech", "data": "2026-11-11", "selo_sugerido": "relato",
                    "manchete": "Horas de trabalho", "link": "https://x", "texto": "São 37 horas de trabalho."}]}])
    assert dossie.montar(date(2026, 11, 11)) == (1, 1)
    assert "37 horas" in (tmp_path / "dossie.md").read_text(encoding="utf-8")


def test_freio_segura_o_segundo_post_da_mesma_rodada():
    agora = datetime(2026, 11, 11, 19, 14, tzinfo=FUSO)
    acabou_de_sair = _item(1, agora - timedelta(hours=5), "publicado", (agora + timedelta(seconds=40)).isoformat())
    proximo = _item(2, agora - timedelta(hours=4))
    assert "intervalo" in motivo_para_segurar(proximo, [acabou_de_sair, proximo], agora)


def test_passos_do_titulo_e_barra():
    from pipeline.montagem import MAX_PASSOS_TITULO, filtro_barra, passos_do_titulo
    assert passos_do_titulo(4) == [1, 2, 3]
    assert len(passos_do_titulo(20)) == MAX_PASSOS_TITULO - 1
    assert passos_do_titulo(1) == []
    assert "W*t/30.000" in filtro_barra(30, "#C6FF3D")


def test_busca_prefere_video_no_reel(tmp_path, monkeypatch):
    import json
    from pipeline import catalogo
    (tmp_path / "catalogo.json").write_text(json.dumps([
        {"arquivo": "clipes/a.jpg", "tipo": "imagem", "tags": ["praia"], "descricao": "praia"},
        {"arquivo": "clipes/b.mp4", "tipo": "video", "tags": ["praia"], "descricao": "praia", "duracao_s": 5},
    ]), encoding="utf-8")
    monkeypatch.setattr(catalogo, "_carregar_uso", lambda: {})
    assert catalogo.buscar_clipe("praia", pasta=tmp_path, preferir_video=True).entrada["tipo"] == "video"


def test_clipe_curto_nao_entra_no_reel(tmp_path, monkeypatch):
    import json
    from pipeline import catalogo
    (tmp_path / "catalogo.json").write_text(json.dumps([
        {"arquivo": "clipes/a.jpg", "tipo": "imagem", "tags": ["jason"], "descricao": "jason"},
        {"arquivo": "clipes/b.mp4", "tipo": "video", "tags": ["jason"], "descricao": "jason", "duracao_s": 1.0},
    ]), encoding="utf-8")
    monkeypatch.setattr(catalogo, "_carregar_uso", lambda: {})
    assert catalogo.buscar_clipe("jason", pasta=tmp_path, preferir_video=True).entrada["tipo"] == "imagem"


def test_saida_no_formato_dos_reels_da_meta():
    from pipeline.montagem import parametros_instagram
    p = " ".join(parametros_instagram())
    for exigido in ("-use_editlist 0", "+faststart", "-b:a 128k", "-ar 48000", "yuv420p", "open-gop=0", "-maxrate"):
        assert exigido in p


def test_reel_vai_por_link_quando_o_envio_direto_falha(tmp_path, monkeypatch):
    from unittest.mock import MagicMock
    from pipeline import instagram
    from pipeline.instagram import Credenciais, ErroInstagram, Publicador
    video = tmp_path / "r.mp4"
    video.write_bytes(b"x" * 10)
    hosp = MagicMock()
    hosp.hospedar_video.return_value = "https://video.fbcdn.net/r.mp4"
    pub = Publicador(Credenciais("IG1", "tok"), sessao=MagicMock(), espera_s=0, hospedeiro=hosp)
    monkeypatch.setattr(pub, "_contener_e_enviar", MagicMock(side_effect=ErroInstagram("ProcessingFailedError")))
    monkeypatch.setattr(pub, "_esperar", lambda cid, lim: None)
    monkeypatch.setattr(pub, "_publicar", lambda cid: {"media_id": "M1", "container_id": cid})
    monkeypatch.setattr(instagram, "_checar", lambda r: {"id": "C9"})
    assert pub.publicar_reel(video, "legenda")["container_id"] == "C9"
    corpo = pub.s.post.call_args.kwargs["data"]
    assert corpo["video_url"] == "https://video.fbcdn.net/r.mp4" and "upload_type" not in corpo
    hosp.limpar.assert_called_once()


def test_falha_da_meta_no_video_reconhecida():
    from pipeline.cli import falha_da_meta_no_video
    assert falha_da_meta_no_video("Media upload has failed with error code 2207076")
    assert falha_da_meta_no_video("{'type': 'ProcessingFailedError'}")
    assert not falha_da_meta_no_video("OAuthException code 190")


def test_post_liberado_fura_o_freio():
    agora = datetime(2026, 11, 12, 14, 30, tzinfo=FUSO)
    seis = [_item(i, agora, "publicado", (agora - timedelta(hours=2 * i + 2)).isoformat()) for i in range(6)]
    novo = _item(99, agora)
    novo.furar_freio = True
    assert motivo_para_segurar(novo, seis + [novo], agora) == ""


def test_reel_manual_vai_para_o_telegram(tmp_path, monkeypatch):
    from argparse import Namespace
    from pipeline import cli
    from pipeline.fila import carregar, salvar
    agora = datetime.now(FUSO)
    item = _item(1, agora - timedelta(minutes=5))
    item.tipo = "reel"
    salvar([item])
    entregues = []
    monkeypatch.setattr(cli, "reels_manuais", lambda: True)
    monkeypatch.setattr(cli, "entregar_reel_manual", lambda i: entregues.append(i.id) or True)
    cli.cmd_publicar(Namespace(simular=False))
    assert entregues == ["p1"] and carregar()[0].status == "manual"


def test_so_um_carrossel_por_dia_no_feed(monkeypatch):
    from pipeline import producao
    from pipeline.fila import salvar
    agora = datetime(2026, 11, 14, 11, 0, tzinfo=FUSO)
    c = _item(1, agora)
    c.tipo = "carrossel"
    salvar([c])
    monkeypatch.setattr(producao, "carrosseis_por_dia", lambda: 1)
    assert producao.carrosseis_no_dia("gg_explica", agora) == 1
    assert producao.carrosseis_no_dia("gg_explica", agora + timedelta(days=1)) == 0


def test_legenda_sem_aviso_e_hashtag_repetidos():
    from pipeline.fila import montar_legenda
    from pipeline.marca import carregar_marca
    from pipeline.modelos import Video
    marca = carregar_marca("gg_explica")
    v = Video.model_validate({"id": "t", "serie": "radar", "horario": "09:00", "formato": "reel", "data": "2026-11-15",
        "legenda_post": "x", "hashtags": ["#gta6"], "cenas": [{"tipo": "gancho", "titulo": "G", "narracao": "oi"},
        {"tipo": "tela_cheia", "titulo": "T", "narracao": "oi",
        "midia": "busca:praia", "credito": "Imagens: Rockstar Games"}]})
    texto = f"Gancho\n\nComenta PS5\n\n{marca.post['aviso_ia']}\n#gta6 #gtavi"
    leg = montar_legenda(marca, v, texto)
    assert leg.count(marca.post["aviso_ia"].rstrip(".")) == 1
    assert leg.lower().count("#gta6") == 1 and leg.count("Imagens: Rockstar Games") == 1


def test_teto_de_reels_por_dia_da_preferencia_ao_radar(tmp_path, monkeypatch):
    from pipeline import fila
    monkeypatch.setattr(fila, "ARQUIVO_FILA", tmp_path / "fila.json")
    def item(vid, hora, status="pendente"):
        return fila.Item(id=vid, marca="gg", video="v.mp4", capa="", legenda="",
                         quando=f"2026-11-19T{hora}:00-03:00", plataforma="instagram", status=status)
    fila.salvar([item("radar_a", "09:00", "manual"), item("2026-W47_pauta1", "13:00"),
                 item("radar_b", "15:00"), item("2026-W47_pauta2", "21:30")])
    assert fila.abrir_vaga("gg", "radar_c", "2026-11-19", limite=4) == (True, "saiu 2026-W47_pauta2 (pauta) para caber a notícia")
    assert [i.id for i in fila.carregar()] == ["radar_a", "2026-W47_pauta1", "radar_b"]
    fila.salvar(fila.carregar() + [item("radar_c", "19:00")])
    cabe, motivo = fila.abrir_vaga("gg", "2026-W47_pauta3", "2026-11-19", limite=4)
    assert not cabe and "4 Reels" in motivo
    assert fila.abrir_vaga("gg", "radar_b", "2026-11-19", limite=4)[0]      # o próprio item não conta


def test_modo_dos_reels_testa_a_api_uma_vez_por_dia(tmp_path, monkeypatch):
    from pipeline import cli
    monkeypatch.setattr(cli, "ARQ_API_INSTAGRAM", tmp_path / "api.json")
    monkeypatch.setattr(cli, "reels_manuais", lambda: True)
    assert cli.modo_dos_reels("2026-11-19") == "teste"
    cli.guardar_estado_api(ultimo_teste="2026-11-19", api_ok=False)
    assert cli.modo_dos_reels("2026-11-19") == "teste"          # cada Reel tenta de novo
    assert cli.modo_dos_reels("2026-11-20") == "teste"
    cli.guardar_estado_api(api_ok=True)
    assert cli.modo_dos_reels("2026-11-19") == "api"
    monkeypatch.setattr(cli, "reels_manuais", lambda: False)
    cli.guardar_estado_api(api_ok=False)
    assert cli.modo_dos_reels("2026-11-19") == "api"


def test_facebook_desligado_nao_entra_na_fila(monkeypatch):
    from pipeline import producao
    monkeypatch.setattr("pipeline.radar.config", lambda: {"publicacao": {"desligar": ["facebook"]}})
    assert producao.redes_desligadas() == {"facebook"}
