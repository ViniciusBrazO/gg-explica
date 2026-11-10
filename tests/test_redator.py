"""Redator gratuito (Gemini): horários, normalização e regra do CONFIRMADO."""
from __future__ import annotations

from datetime import date, datetime

from pipeline import redator


def test_horarios_livres_respeita_antecedencia_e_ocupados(monkeypatch):
    monkeypatch.setattr(redator, "posts_recentes", lambda hoje, dias=3: [
        {"data": "2026-11-11", "horario": "15:00"}])
    livres = redator.horarios_livres(date(2026, 11, 11), datetime(2026, 11, 11, 12, 0))
    assert livres == ["17:00", "19:00", "21:00"]          # 12:30 está a menos de 90 min; 15:00 ocupado


def test_confirmado_sem_fonte_oficial_lida_vira_relato(monkeypatch):
    monkeypatch.setattr(redator, "voz_ligada", lambda: True)
    bruto = {"id": "Post X!", "formato": "carrossel", "cenas": [
        {"tipo": "gancho", "titulo": "a", "selo": "confirmado", "fonte_url": "https://ign.com/x",
         "fundo_clipe": "clipes/oficial/Lucia_01.jpg"},
        {"tipo": "texto", "texto": "b", "selo": "confirmado", "fonte_url": "https://blog.playstation.com/p"}]}
    v = redator.normalizar(bruto, date(2026, 11, 11), lidos={"https://blog.playstation.com/p"})
    assert v["id"] == "post_x" and v["status"] == "rascunho" and v["gerar_reel"] is False
    assert v["cenas"][0]["selo"] == "relato"                # imprensa: RELATO
    assert v["cenas"][1]["selo"] == "confirmado"            # oficial e lido nesta rodada
    assert v["cenas"][0]["fundo_clipe"].startswith("busca:") and v["cenas"][0]["credito"]


def test_rodar_tarefa_sem_redator_nao_falha():
    ex = redator.rodar("catalogo")
    assert ex.ok
