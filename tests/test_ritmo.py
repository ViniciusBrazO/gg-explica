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
