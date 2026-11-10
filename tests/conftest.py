import pytest


@pytest.fixture(autouse=True)
def _reels_liberados(monkeypatch, request):
    """Os testes de Reel narrado rodam como se a voz estivesse configurada."""
    if "so_carrossel" not in request.node.name:
        monkeypatch.setattr("pipeline.qualidade.so_carrossel", lambda: False)
