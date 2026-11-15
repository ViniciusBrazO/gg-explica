import pytest


@pytest.fixture(autouse=True)
def _padroes_dos_testes(monkeypatch, request, tmp_path):
    """Os testes de Reel narrado rodam como se a voz estivesse configurada, e a aprovação é manual
    (salvo nos testes do modo automático)."""
    if "so_carrossel" not in request.node.name:
        monkeypatch.setattr("pipeline.qualidade.so_carrossel", lambda: False)
    if "automatic" not in request.node.name:
        monkeypatch.setattr("pipeline.telegram.modo_aprovacao", lambda: "manual")
    # a fila de verdade (saida/fila.json) nunca entra nos testes
    monkeypatch.setattr("pipeline.fila.ARQUIVO_FILA", tmp_path / "fila_teste.json")
    # os testes antigos de montagem conferem o estilo de cartões; o estilo notícia tem os próprios testes
    if "noticia" not in request.node.name:
        monkeypatch.setattr("pipeline.estilo_noticia.ligado", lambda marca: False)
    # o limite diário de carrossel no feed (config real: 0, só Reels) tem teste próprio
    monkeypatch.setattr("pipeline.producao.carrosseis_por_dia", lambda: 99)
