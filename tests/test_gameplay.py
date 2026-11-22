import json

from pipeline import gameplay as gp


def test_momentos_do_gemini_sao_conferidos():
    dados = {"momentos": [
        {"inicio": 10, "fim": 40, "nota": 9, "tipo": "acao", "descricao": "fuga de lancha"},
        {"inicio": 30, "fim": 50, "nota": 8, "descricao": "sobrepõe o anterior"},
        {"inicio": 100, "fim": 190, "nota": 7, "descricao": "longo demais: corta em 50 s"},
        {"inicio": 300, "fim": 305, "nota": 9, "descricao": "curto demais"},
        {"inicio": 400, "fim": 430, "nota": 10, "spoiler": True, "descricao": "cena da história"},
        {"inicio": 500, "fim": 530, "nota": 3, "descricao": "fraco"},
        {"inicio": 3590, "fim": 3700, "nota": 9, "descricao": "passa do fim do vídeo"},
        {"inicio": "x", "fim": 1, "nota": 9},
    ]}
    m = gp.ler_momentos(dados, duracao_video=3600)
    assert [(x.inicio, x.fim) for x in m] == [(10.0, 40.0), (100.0, 150.0)]
    assert m[0].nota == 9 and m[0].descricao == "fuga de lancha"


def test_cortes_livres_usados_e_rascunho(tmp_path, monkeypatch):
    monkeypatch.setattr(gp, "RAIZ", tmp_path)
    monkeypatch.setattr(gp, "ARQ_MOMENTOS", tmp_path / "saida/gameplay/momentos.json")
    monkeypatch.setattr(gp, "ARQ_ESTADO", tmp_path / "saida/gameplay/estado.json")
    corte = tmp_path / "saida/cache/gameplay/a_01.mp4"
    corte.parent.mkdir(parents=True)
    corte.write_bytes(b"x")
    gp.registrar([gp.Corte(id="a_01", arquivo="saida/cache/gameplay/a_01.mp4", origem="a.mp4", duracao=30,
                           nota=9, tipo="acao", descricao="fuga"),
                  gp.Corte(id="a_02", arquivo="saida/cache/gameplay/a_02.mp4", origem="a.mp4", duracao=30,
                           nota=8, tipo="acao", descricao="arquivo sumiu do cache")])
    assert [c["id"] for c in gp.cortes_livres()] == ["a_01"]
    pautas = tmp_path / "pautas"
    pautas.mkdir()
    assert not gp.ha_rascunho_de_gameplay(pautas)
    (pautas / "gameplay_2026-11-23_gg_explica.json").write_text(json.dumps({"videos": [
        {"id": "gameplay_x_reel", "status": "rascunho",
         "cenas": [{"midia": "saida/cache/gameplay/a_01.mp4"}]}]}), encoding="utf-8")
    assert gp.ha_rascunho_de_gameplay(pautas)
    assert gp.marcar_usados(pautas) == 1 and gp.cortes_livres() == []
    assert gp.pode_pedir_roteiro()
    gp.marcar_pedido_roteiro()
    assert not gp.pode_pedir_roteiro()


def test_gameplay_tem_preferencia_sobre_pauta_antiga(tmp_path, monkeypatch):
    from pipeline import fila
    monkeypatch.setattr(fila, "ARQUIVO_FILA", tmp_path / "fila.json")
    def item(vid, hora):
        return fila.Item(id=vid, marca="gg", video="v.mp4", capa="", legenda="",
                         quando=f"2026-11-23T{hora}:00-03:00", plataforma="instagram")
    fila.salvar([item("radar_a", "09:00"), item("2026-W48_pauta", "13:00"), item("radar_b", "15:00"),
                 item("radar_c", "19:00")])
    assert fila.abrir_vaga("gg", "gameplay_x_reel", "2026-11-23", limite=4)[0]
    assert "2026-W48_pauta" not in [i.id for i in fila.carregar()]
    cabe, _ = fila.abrir_vaga("gg", "radar_d", "2026-11-23", limite=3)
    assert not cabe                                  # notícia não tira gameplay nem outra notícia


def test_cena_de_gameplay_corre_continua():
    from pipeline.modelos import Cena
    from pipeline.montagem import e_gameplay
    assert e_gameplay(Cena(tipo="tela_cheia", midia="saida/cache/gameplay/a_01.mp4", narracao="x"))
    assert not e_gameplay(Cena(tipo="tela_cheia", midia="busca:lancha", narracao="x"))
