"""Modo nuvem: rodada leve ou pesada, alertas guardados, marcas de tempo e o modo só carrossel."""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta

import pytest

from pipeline import ciclo, nuvem, telegram as tgmod


@pytest.fixture
def kit(tmp_path, monkeypatch):
    pautas = tmp_path / "pautas"
    pautas.mkdir()
    monkeypatch.setattr(tgmod, "ARQ_PENDENTES", tmp_path / "pendentes.json")
    monkeypatch.setattr(tgmod, "ARQ_OFFSET", tmp_path / "offset.txt")
    monkeypatch.setattr(tgmod, "pautas_de_trabalho", lambda: sorted(pautas.glob("*.json")))
    monkeypatch.setattr(nuvem, "ALERTAS_PENDENTES", tmp_path / "alertas.json")
    ultima = tmp_path / "biblioteca_ultimo.txt"
    ultima.write_text(datetime.now().isoformat())
    monkeypatch.setattr(ciclo, "ULTIMA_BIBLIOTECA", ultima)
    return pautas


def _pauta(pastas, status, dia, notas=""):
    v = {"id": "p1", "data": dia.isoformat(), "horario": "19:00", "serie": "gg_explica", "status": status,
         "formato": "carrossel", "legenda_post": "x", "notas_revisao": notas,
         "cenas": [{"tipo": "gancho", "titulo": "a"}, {"tipo": "cta", "titulo": "b", "texto": "c"}]}
    (pastas / "radar.json").write_text(json.dumps({"marca": "gg_explica", "semana": "2026-W46", "videos": [v]}), encoding="utf-8")


class TgFalso:
    def __init__(self, updates=()):
        self.updates = list(updates)

    def atualizacoes(self, offset, espera=0):
        return self.updates


def test_sem_nada_a_fazer_e_leve(kit):
    assert nuvem.motivos_para_pesado(telegram=TgFalso()) == []


def test_aprovado_pede_renderizar(kit):
    _pauta(kit, "aprovado", date.today())
    assert nuvem.motivos_para_pesado(telegram=TgFalso()) == ["renderizar p1"]


def test_rascunho_sem_previa_pede_previa_e_passado_nao(kit):
    _pauta(kit, "rascunho", date.today())
    assert nuvem.motivos_para_pesado(telegram=TgFalso()) == ["prévia de p1"]
    _pauta(kit, "aprovado", date.today() - timedelta(days=1))
    assert nuvem.motivos_para_pesado(telegram=TgFalso()) == []


def test_ajuste_e_resposta_no_telegram(kit):
    _pauta(kit, "rascunho", date.today(), notas=f"{tgmod.MARCADOR_AJUSTE} troca a capa")
    motivos = nuvem.motivos_para_pesado(telegram=TgFalso([{"update_id": 5}]))
    assert motivos == ["ajuste de p1", "respostas no Telegram"]


def test_biblioteca_vencida_e_alerta_guardado(kit):
    ciclo.ULTIMA_BIBLIOTECA.write_text((datetime.now() - timedelta(hours=30)).isoformat())
    nuvem.guardar_alerta("[RELATO?] GTA 6 x")
    motivos = nuvem.motivos_para_pesado(telegram=None)
    assert "conferir a biblioteca oficial" in motivos and "notícia quente para o Claude" in motivos
    assert nuvem.tirar_alertas() == ["[RELATO?] GTA 6 x"] and nuvem.tirar_alertas() == []


def test_marca_de_tempo_vem_do_conteudo(tmp_path):
    arq = tmp_path / "t.txt"
    arq.write_text("2026-11-10T07:10:00")
    assert nuvem.ler_marca_de_tempo(arq) == datetime(2026, 11, 10, 7, 10)
    assert nuvem.ler_marca_de_tempo(tmp_path / "nao.txt") is None


def test_plano_escreve_no_github_output(kit, tmp_path, monkeypatch):
    saida = tmp_path / "out.txt"
    monkeypatch.setenv("GITHUB_OUTPUT", str(saida))
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    _pauta(kit, "aprovado", date.today())
    nuvem.plano()
    assert saida.read_text() == "pesado=true\n"


def test_so_carrossel_bloqueia_reel(monkeypatch):
    from pipeline import qualidade
    from pipeline.marca import carregar_marca
    from pipeline.modelos import Video
    monkeypatch.setattr(qualidade, "so_carrossel", lambda: True)
    v = Video.model_validate({"id": "r", "data": "2026-11-11", "horario": "19:00", "serie": "gg_explica",
                              "legenda_post": "x", "cenas": [
                                  {"tipo": "gancho", "titulo": "a", "narracao": "a"},
                                  {"tipo": "cta", "titulo": "b", "texto": "c", "narracao": "b"}]})
    bloqueios, _ = qualidade.checar_pauta(carregar_marca("gg_explica"), v)
    assert any("carrossel" in b for b in bloqueios)


def test_workflow_instala_a_voz_azure():
    """A marca usa a voz do Azure: sem o SDK no servidor, as prévias quebram e nada é renderizado."""
    from pathlib import Path
    import yaml
    raiz = Path(__file__).resolve().parents[1]
    voz = yaml.safe_load((raiz / "config/marcas/gg_explica.yaml").read_text(encoding="utf-8"))["voz"]["provedor"]
    if voz == "azure":
        assert '.[azure]' in (raiz / ".github/workflows/kit.yml").read_text(encoding="utf-8")


def test_scripts_do_workflow_tem_sintaxe_valida():
    """Um erro de bash no passo 'Rodar' derruba TODAS as rodadas: confere antes de subir."""
    import subprocess
    from pathlib import Path
    import yaml
    raiz = Path(__file__).resolve().parents[1]
    w = yaml.safe_load((raiz / ".github/workflows/kit.yml").read_text(encoding="utf-8"))
    for job in w["jobs"].values():
        for passo in job["steps"]:
            if "run" in passo:
                script = passo["run"].replace("${{", "X").replace("}}", "X")
                r = subprocess.run(["bash", "-n"], input=script, text=True, capture_output=True)
                assert r.returncode == 0, f"{passo.get('name')}: {r.stderr}"


def test_limite_do_claude_passa_a_rodada_para_o_gemini(monkeypatch, tmp_path):
    from types import SimpleNamespace
    from pipeline import claude_cli, redator, gemini
    monkeypatch.setattr(claude_cli, "usa_gemini", lambda: False)
    monkeypatch.setattr(claude_cli, "PASTA_LOG", tmp_path)
    monkeypatch.setattr(gemini, "disponivel", lambda: True)
    monkeypatch.setattr(redator, "rodar", lambda t, c="": claude_cli.Execucao(True, f"gemini fez {t}", 0.0))
    monkeypatch.setattr("pipeline.telegram.Telegram.do_ambiente", classmethod(lambda cls: None))
    falso = lambda *a, **k: SimpleNamespace(returncode=1, stdout="You've hit your weekly limit · resets 4pm", stderr="")
    r = claude_cli.rodar("radar", executar=falso)
    assert r.ok and r.resumo == "gemini fez radar"
    assert not claude_cli.bateu_limite("3 Reels escritos")
