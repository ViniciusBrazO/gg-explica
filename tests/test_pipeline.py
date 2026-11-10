import json
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from pipeline.cartoes import montar_html
from pipeline.fila import montar_legenda
from pipeline.instagram import Credenciais, ErroInstagram, Publicador
from pipeline.legendas import _cor_ass, agrupar, gerar_ass
from pipeline.marca import RAIZ, carregar_marca
from pipeline.modelos import Pauta, Video
from pipeline.montagem import momentos_de_revelacao, preencher_variaveis
from pipeline.qualidade import checar_pauta
from pipeline.voz import Palavra, por_extenso, texto_para_fala

PAUTAS = sorted((RAIZ / "pautas").glob("exemplo_*.json"))


# ---------------------------------------------------------------- texto falado

@pytest.mark.parametrize("n,esperado", [
    (0, "zero"), (15, "quinze"), (21, "vinte e um"), (100, "cem"), (101, "cento e um"),
    (449, "quatrocentos e quarenta e nove"), (1000, "mil"), (1100, "mil e cem"),
    (1250, "mil duzentos e cinquenta"), (2005, "dois mil e cinco"),
])
def test_por_extenso(n, esperado):
    assert por_extenso(n) == esperado


def test_texto_para_fala_precos_e_marcacoes():
    assert texto_para_fala("Sai por *R$ 449,90* hoje") == "Sai por quatrocentos e quarenta e nove reais e noventa hoje"
    assert texto_para_fala("R$ 1.000 com 10% off") == "mil reais com dez por cento off"
    assert texto_para_fala("R$ 3,00/ml") == "três reais por ml"
    assert texto_para_fala("Barato x caro") == "Barato contra caro"
    assert texto_para_fala("Relax total") == "Relax total"


# ---------------------------------------------------------------- legenda

def _palavras(texto, passo=0.3):
    return [Palavra(p, i * passo, i * passo + passo * 0.9) for i, p in enumerate(texto.split())]


def test_agrupar_respeita_limites_e_pontuacao():
    blocos = agrupar(_palavras("Faltam quinze dias. E tem três datas que você precisa anotar"), 3, 20)
    textos = [" ".join(p.texto for p in b.palavras) for b in blocos]
    assert textos[0] == "Faltam quinze dias."
    assert all(len(b.palavras) <= 3 for b in blocos)


def test_cor_ass_inverte_para_bgr():
    assert _cor_ass("#C8FF2E") == "&H002EFFC8"


def test_gerar_ass_um_evento_por_palavra(tmp_path):
    marca = carregar_marca("gamer_pao_duro")
    palavras = _palavras("segue o pão-duro pra não pagar caro")
    ass = gerar_ass(marca, palavras, tmp_path / "x.ass").read_text(encoding="utf-8")
    assert ass.count("Dialogue:") == len(palavras)
    assert "PÃO-DURO" in ass            # caixa alta na marca de games
    assert "Anton" in ass


# ---------------------------------------------------------------- pautas e conformidade

@pytest.mark.parametrize("arquivo", PAUTAS, ids=lambda p: p.name)
def test_pautas_de_exemplo_validam(arquivo):
    pauta = Pauta.carregar(arquivo)
    marca = carregar_marca(pauta.marca)
    for v in pauta.videos:
        bloqueios, _ = checar_pauta(marca, v)
        if v.status == "aprovado":
            assert bloqueios == [], (v.id, bloqueios)
        else:
            assert bloqueios, "modelos em rascunho devem acusar pendência"


def _video_basico(**extra):
    base = dict(id="t", serie="radar_gta6", data="2026-11-05", horario="19:00", legenda_post="x",
                cenas=[{"tipo": "gancho", "titulo": "Oi", "narracao": "oi"}])
    base.update(extra)
    return Video.model_validate(base)


def test_frase_proibida_bloqueia():
    marca = carregar_marca("gamer_pao_duro")
    v = _video_basico(cenas=[{"tipo": "gancho", "titulo": "Eu testei", "narracao": "testei esse controle"}])
    bloqueios, _ = checar_pauta(marca, v)
    assert any("proibida" in b for b in bloqueios)


def test_produto_exige_publi():
    with pytest.raises(ValueError):
        _video_basico(produtos=[{"nome": "x", "loja": "shopee"}])


def test_primeira_cena_precisa_ser_gancho():
    with pytest.raises(ValueError):
        _video_basico(cenas=[{"tipo": "texto", "texto": "a", "narracao": "a"}])


def test_contagem_regressiva():
    assert preencher_variaveis("faltam {dias_ate:2026-11-19} dias", date(2026, 11, 5)) == "faltam 14 dias"
    assert preencher_variaveis("{dias_ate:2026-11-19}", date(2026, 12, 1)) == "0"


def test_revelacao_acompanha_a_fala():
    # cada item começa numa frase nova, mesmo com frases de tamanhos diferentes
    palavras = _palavras("Dia doze libera o pré-download. Dia dezenove é o lançamento, no PS5. "
                         "E quem compra até o dia dezenove leva o bônus.", passo=1.0)
    assert momentos_de_revelacao(3, palavras) == [0.0, 5.0, 12.0]
    assert momentos_de_revelacao(1, palavras) == [0.0]
    # sem pontuação, divide pela proporção de palavras
    assert momentos_de_revelacao(3, _palavras("a b c d e f", passo=1.0)) == [0.0, 2.0, 4.0]


# ---------------------------------------------------------------- legenda do post

def test_legenda_post_publi_no_inicio_e_max_3_hashtags():
    marca = carregar_marca("seul_no_bolso")
    v = _video_basico(serie="cabe_no_bolso", publi=True, hashtags=["#a", "#b", "#c"],
                      produtos=[{"nome": "Sérum", "loja": "shopee"}])
    leg = montar_legenda(marca, v, "Texto do post")
    assert leg.startswith("#publi")
    assert "voz de IA" in leg
    assert leg.splitlines()[-1].count("#") == 3


# ---------------------------------------------------------------- Instagram (simulado)

def _resp(json_data, status=200):
    r = MagicMock()
    r.status_code = status
    r.json.return_value = json_data
    return r


def test_publicar_reel_segue_o_fluxo_oficial(tmp_path):
    video = tmp_path / "v.mp4"
    video.write_bytes(b"0" * 1024)
    s = MagicMock()
    s.post.side_effect = [_resp({"id": "C1", "uri": "x"}), _resp({"success": True}), _resp({"id": "M1"})]
    s.get.side_effect = [_resp({"status_code": "IN_PROGRESS"}), _resp({"status_code": "FINISHED"}),
                         _resp({"permalink": "https://instagram.com/reel/abc"})]
    pub = Publicador(Credenciais("IG1", "TOKEN", "v26.0"), sessao=s, espera_s=0)
    res = pub.publicar_reel(video, "legenda")
    assert res == {"media_id": "M1", "permalink": "https://instagram.com/reel/abc", "container_id": "C1"}
    criar = s.post.call_args_list[0]
    assert criar.args[0].endswith("/v26.0/IG1/media")
    assert criar.kwargs["data"]["media_type"] == "REELS"
    assert criar.kwargs["data"]["upload_type"] == "resumable"
    envio = s.post.call_args_list[1]
    assert envio.args[0] == "https://rupload.facebook.com/ig-api-upload/v26.0/C1"
    assert envio.kwargs["headers"]["file_size"] == "1024"
    assert s.post.call_args_list[2].kwargs["data"]["creation_id"] == "C1"


def test_publicar_reel_erro_de_processamento(tmp_path):
    video = tmp_path / "v.mp4"
    video.write_bytes(b"0")
    s = MagicMock()
    s.post.side_effect = [_resp({"id": "C1"}), _resp({"success": True})]
    s.get.side_effect = [_resp({"status_code": "ERROR", "status": "codec"})]
    with pytest.raises(ErroInstagram):
        Publicador(Credenciais("IG1", "T"), sessao=s, espera_s=0).publicar_reel(video, "x")


# ---------------------------------------------------------------- renderização completa

@pytest.mark.lento
def test_renderiza_video_curto(tmp_path):
    from pipeline.montagem import renderizar_video
    from pipeline.qualidade import checar_arquivo

    marca = carregar_marca("gamer_pao_duro")
    v = _video_basico(cenas=[
        {"tipo": "gancho", "titulo": "Faltam *{dias_ate:2026-11-19} dias*", "narracao": "Faltam poucos dias pro lançamento, anota aí."},
        {"tipo": "lista", "titulo": "Datas", "itens": ["um", "dois"], "narracao": "Primeiro isso, depois aquilo e mais um pouco."},
        {"tipo": "cta", "texto": "Segue", "narracao": "Segue a página pra não perder nada e não pagar caro."},
    ])
    info = renderizar_video(marca, v, tmp_path, voz_forcada="silencio")
    arquivo = tmp_path / info["video"]
    assert arquivo.exists() and (tmp_path / info["capa"]).exists()
    problemas = [p for p in checar_arquivo(marca, arquivo) if "duração" not in p]
    assert problemas == []


@pytest.mark.lento
def test_fundo_em_video(tmp_path, monkeypatch):
    """Simula um clipe do Pexels (vertical, 720x1280) para testar o caminho de fundo em vídeo."""
    import subprocess
    from pipeline import montagem
    from pipeline.qualidade import checar_arquivo

    clipe = tmp_path / "clipe.mp4"
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i",
                    "testsrc2=size=720x1280:rate=30:duration=4", "-c:v", "libx264", "-preset", "veryfast",
                    str(clipe)], check=True)
    monkeypatch.setattr(montagem, "buscar_broll", lambda termo: clipe)
    marca = carregar_marca("seul_no_bolso")
    v = _video_basico(serie="original_ou_falso", cenas=[
        {"tipo": "gancho", "titulo": "Teste com *fundo em vídeo*", "broll": "qualquer",
         "narracao": "Este fundo vem de um clipe vertical que dura menos que a cena, então ele repete."},
        {"tipo": "cta", "texto": "Fim", "narracao": "E aqui o fundo volta a ser o da marca, sem salto."},
    ])
    info = montagem.renderizar_video(marca, v, tmp_path, voz_forcada="silencio")
    assert [p for p in checar_arquivo(marca, tmp_path / info["video"]) if "duração" not in p] == []


# ---------------------------------------------------------------- GG Explica: selos e mídia

def _video_gg(cenas, **extra):
    base = dict(id="g", serie="radar", data="2026-11-05", horario="19:00", legenda_post="x",
                cenas=[{"tipo": "gancho", "titulo": "Oi", "narracao": "oi"}, *cenas])
    base.update(extra)
    return Video.model_validate(base)


def test_selo_confirmado_sem_fonte_bloqueia():
    marca = carregar_marca("gg_explica")
    v = _video_gg([{"tipo": "texto", "selo": "confirmado", "texto": "Sai dia 19", "narracao": "Sai dia 19."}])
    bloqueios, _ = checar_pauta(marca, v)
    assert any("sem fonte" in b for b in bloqueios)
    v.cenas[1].fonte = "Rockstar Newswire · 06/05"
    assert checar_pauta(marca, v)[0] == []


@pytest.mark.parametrize("fala,bloqueia", [
    ("Isso já foi confirmado pela Rockstar.", True),
    ("A Rockstar confirmou o PC.", True),
    ("A Rockstar não confirmou nada.", False),
    ("Sem confirmação oficial, é só rumor.", False),
])
def test_rumor_nao_pode_se_dizer_confirmado(fala, bloqueia):
    marca = carregar_marca("gg_explica")
    v = _video_gg([{"tipo": "texto", "selo": "rumor", "texto": "PC em 2027?", "narracao": fala}])
    bloqueios, _ = checar_pauta(marca, v)
    assert any("diz que está confirmado" in b for b in bloqueios) is bloqueia


def test_selo_exige_marca_com_selos():
    v = _video_gg([{"tipo": "texto", "selo": "teoria", "texto": "x", "narracao": "x"}], serie="cabe_no_bolso")
    bloqueios, _ = checar_pauta(carregar_marca("seul_no_bolso"), v)
    assert any("não tem o selo" in b for b in bloqueios)


def test_midia_de_terceiros_nunca_em_publi():
    with pytest.raises(ValueError, match="publi"):
        _video_gg([{"tipo": "midia", "midia": "clipes/x.mp4", "credito": "Imagens: Rockstar Games", "narracao": "x"}],
                  serie="pao_duro", publi=True, produtos=[{"nome": "SSD", "loja": "amazon"}])


def test_midia_sem_credito_e_sem_arquivo_bloqueia():
    marca = carregar_marca("gg_explica")
    v = _video_gg([{"tipo": "midia", "midia": "clipes/nao_existe.mp4", "narracao": "olha isso"}])
    bloqueios, _ = checar_pauta(marca, v)
    assert any("não encontrado" in b for b in bloqueios)
    assert any("sem crédito" in b for b in bloqueios)


def test_recorte_invalido():
    with pytest.raises(ValueError, match="midia_recorte"):
        _video_gg([{"tipo": "midia", "midia": "a.png", "midia_recorte": [0.8, 0, 0.5, 0.5], "narracao": "x"}])


def test_veredito_com_selo_dispensa_aprovado_e_mostra_rotulo():
    marca = carregar_marca("gg_explica")
    v = _video_gg([{"tipo": "veredito", "selo": "relato", "fonte": "GamesBeat", "texto": "x", "narracao": "x"}])
    html_doc = montar_html(marca, v.cenas[1].model_dump(), modo="cartao")
    assert "RELATO" in html_doc and "#4DB8FF" in html_doc and "Fonte: GamesBeat" in html_doc


def test_legenda_post_credita_imagens_de_terceiros(tmp_path):
    marca = carregar_marca("gg_explica")
    v = _video_gg([{"tipo": "midia", "midia": "clipes/a.jpg", "credito": "Imagens: Rockstar Games", "narracao": "x"},
                   {"tipo": "midia", "midia": "clipes/b.jpg", "credito": "Imagens: Rockstar Games", "narracao": "y"}])
    leg = montar_legenda(marca, v, "Texto")
    assert leg.count("Imagens: Rockstar Games.") == 1
    assert "voz de IA" in leg


def test_trecho_de_jogo_longo_avisa():
    marca = carregar_marca("gg_explica")
    fala = " ".join(["palavra"] * 170)   # cerca de 65 s
    v = _video_gg([{"tipo": "midia", "midia": "assets/exemplos/mapa_leonida_esquema.png",
                    "credito": "Imagens: exemplo", "narracao": fala}])
    _, avisos = checar_pauta(marca, v)
    assert any("programa de criadores" in a for a in avisos)
    v.cenas[1].midia_terceiros = False
    assert not any("programa de criadores" in a for a in checar_pauta(marca, v)[1])


@pytest.mark.lento
def test_catalogar_clipes(tmp_path):
    import json
    import subprocess
    from pipeline.catalogo import catalogar

    clipe = tmp_path / "praia.mp4"
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i",
                    "testsrc2=size=1280x720:rate=30:duration=5", "-c:v", "libx264", "-preset", "veryfast",
                    str(clipe)], check=True)
    novos = catalogar(tmp_path)
    assert len(novos) == 1 and novos[0]["duracao_s"] == pytest.approx(5, abs=0.1)
    assert Path(novos[0]["folha"]).exists()
    # o que foi preenchido não se perde ao rodar de novo
    cat = json.loads((tmp_path / "catalogo.json").read_text(encoding="utf-8"))
    cat[0]["descricao"] = "pôr do sol na praia"
    (tmp_path / "catalogo.json").write_text(json.dumps(cat), encoding="utf-8")
    assert catalogar(tmp_path) == []
    assert json.loads((tmp_path / "catalogo.json").read_text(encoding="utf-8"))[0]["descricao"] == "pôr do sol na praia"


@pytest.mark.lento
def test_cena_midia_com_clipe_e_recorte(tmp_path):
    import subprocess
    from PIL import Image
    from pipeline.cartoes import CAIXA_MIDIA
    from pipeline.montagem import renderizar_video
    from pipeline.qualidade import checar_arquivo

    clipe = tmp_path / "clipe.mp4"   # 16:9 mais curto que a cena: o último quadro fica parado
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i",
                    "color=c=red:size=1280x720:rate=30:duration=2", "-c:v", "libx264", "-preset", "veryfast",
                    str(clipe)], check=True)
    marca = carregar_marca("gg_explica")
    v = _video_gg([{"tipo": "midia", "midia": str(clipe), "midia_inicio": 0.5, "midia_recorte": [0.25, 0.25, 0.5, 0.5],
                    "credito": "Imagens: teste", "selo": "teoria", "titulo": "Olha o *detalhe*",
                    "narracao": "Repara no detalhe do canto, que aparece por um bom tempo enquanto eu explico."},
                   {"tipo": "cta", "texto": "Fim", "narracao": "E é isso, segue a página para mais."}])
    info = renderizar_video(marca, v, tmp_path, voz_forcada="silencio")
    final = tmp_path / info["video"]
    assert [p for p in checar_arquivo(marca, final) if "duração" not in p] == []
    quadro = tmp_path / "q.png"
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-ss", "4", "-i", str(final), "-frames:v", "1",
                    str(quadro)], check=True)
    r, g, b = Image.open(quadro).convert("RGB").getpixel(
        (540, CAIXA_MIDIA["y"] + CAIXA_MIDIA["a"] // 2))
    assert r > 180 and g < 80 and b < 80, "o clipe deveria aparecer nítido no centro da caixa"


# ---------------------------------------------------------------- trechos de jogo no design

def test_buscar_clipe_por_palavras(tmp_path, monkeypatch):
    import json
    from pipeline import catalogo

    monkeypatch.setattr(catalogo, "ARQUIVO_USO", tmp_path / "uso.json")
    (tmp_path / "catalogo.json").write_text(json.dumps([
        {"arquivo": "clipes/a.mp4", "duracao_s": 60, "descricao": "praia de Vice City ao pôr do sol",
         "tags": ["praia", "carro"], "momentos": [{"inicio": 12, "fim": 18, "o_que_mostra": "carro na orla"}]},
        {"arquivo": "clipes/b.mp4", "duracao_s": 30, "descricao": "pântano à noite", "tags": ["pantano"]},
        {"arquivo": "clipes/c.mp4", "duracao_s": 30, "descricao": "praia final da história", "spoiler": True},
    ]), encoding="utf-8")
    e = catalogo.buscar_clipe("carro na praia", tmp_path)
    assert e.caminho.name == "a.mp4" and e.inicio == 12 and e.fim == 18
    assert catalogo.buscar_clipe("pântano", tmp_path).caminho.name == "b.mp4"      # sem acento também acha
    assert catalogo.buscar_clipe("final da história", tmp_path) is None            # spoiler fica de fora
    catalogo.registrar_uso(e)
    catalogo.registrar_uso(e)
    assert json.loads((tmp_path / "uso.json").read_text(encoding="utf-8")) == {"clipes/a.mp4@12.0": 2}
    assert catalogo.resolver_midia("clipes/x.mp4", 3.0).inicio == 3.0


def test_busca_sem_catalogo_bloqueia():
    marca = carregar_marca("gg_explica")
    v = _video_gg([{"tipo": "texto", "texto": "x", "narracao": "x", "fundo_clipe": "busca:qualquer coisa",
                    "credito": "Imagens: Rockstar Games"}])
    bloqueios, _ = checar_pauta(marca, v)
    assert any("nenhum clipe do catálogo" in b for b in bloqueios)


@pytest.mark.parametrize("cena,erro", [
    ({"tipo": "midia", "midia": "a.mp4", "midia_animacao": "aproximar", "narracao": "x"}, "recorte"),
    ({"tipo": "tela_cheia", "midia": "a.mp4", "midia_animacao": "aproximar", "midia_recorte": [0, 0, .5, .5],
      "narracao": "x"}, "só para a cena"),
    ({"tipo": "midia", "midia": "a.mp4", "fundo_clipe": "b.mp4", "narracao": "x"}, "já ocupa o fundo"),
    ({"tipo": "midia", "midia": "a.mp4", "midia_destaque": [0.5, 0.5], "narracao": "x"}, "midia_destaque"),
])
def test_campos_de_midia_invalidos(cena, erro):
    with pytest.raises(ValueError, match=erro):
        _video_gg([cena])


def test_fundo_clipe_conta_como_trecho_de_terceiros():
    with pytest.raises(ValueError, match="publi"):
        _video_gg([{"tipo": "texto", "texto": "x", "narracao": "x", "fundo_clipe": "clipes/a.mp4"}],
                  serie="pao_duro", publi=True, produtos=[{"nome": "SSD", "loja": "amazon"}])


def test_geometria_do_zoom_e_do_anel():
    from pathlib import Path as P
    from pipeline.montagem import MidiaCena, _anel_em_pixels

    m = MidiaCena(P("x.mp4"), True, 1280, 720, recorte=(0.4, 0.2, 0.3, 0.3), animacao="aproximar")
    assert m.regiao_final() == pytest.approx((0.4, 0.2, 0.3, 0.3))
    w, h = m.tamanho_na_caixa()
    assert w / h == pytest.approx(16 / 9, rel=0.01)          # no zoom animado a caixa mantém 16:9
    cx, cy, r = _anel_em_pixels((0.55, 0.35, 0.05), m.regiao_final(), w, h)
    assert (cx, cy) == pytest.approx((w / 2, h / 2)) and r == pytest.approx(0.05 / 0.3 * w)
    assert _anel_em_pixels((0.1, 0.1, 0.05), m.regiao_final(), w, h) is None   # fora da área: sem anel
    tc = MidiaCena(P("x.mp4"), True, 1280, 720, foco_x=0.5)
    x, y, rw, rh = tc.regiao_tela_cheia()
    assert rw == pytest.approx(1080 / (1280 * 1920 / 720)) and x == pytest.approx((1 - rw) / 2) and rh == 1


@pytest.mark.lento
def test_tela_cheia_zoom_e_fundo_em_clipe(tmp_path):
    import subprocess
    from pipeline.montagem import renderizar_video
    from pipeline.qualidade import checar_arquivo

    clipe = tmp_path / "jogo.mp4"
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i",
                    "testsrc2=size=1280x720:rate=30:duration=4", "-c:v", "libx264", "-preset", "veryfast",
                    str(clipe)], check=True)
    foto = tmp_path / "foto.png"
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-ss", "1", "-i", str(clipe), "-frames:v", "1", str(foto)],
                   check=True)
    marca = carregar_marca("gg_explica")
    comum = {"credito": "Imagens: teste", "narracao": "Uma frase curta para durar uns três segundos na tela."}
    v = _video_gg([
        {"tipo": "tela_cheia", "midia": str(foto), "titulo": "Foto", "midia_destaque": [0.5, 0.5, 0.05], **comum},
        {"tipo": "tela_cheia", "midia": str(clipe), "panoramica": True, "titulo": "Passeio", **comum},
        {"tipo": "midia", "midia": str(clipe), "midia_recorte": [0.5, 0.5, 0.25, 0.25], "midia_animacao": "aproximar",
         "midia_destaque": [0.62, 0.62, 0.04], **comum},
        {"tipo": "texto", "texto": "Fundo", "fundo_clipe": str(clipe), "foco_x": 0.2, **comum},
    ])
    v.cenas[0].fundo_clipe = str(clipe)          # o gancho também pode ter o jogo de fundo
    info = renderizar_video(marca, v, tmp_path, voz_forcada="silencio", registrar_clipes=False)
    assert [p for p in checar_arquivo(marca, tmp_path / info["video"]) if "duração" not in p] == []


# ---------------------------------------------------------------- automação

def test_cache_de_voz_nao_gasta_credito_duas_vezes(tmp_path):
    from pipeline.voz import Fala, VozComCache

    class Contador:
        chamadas = 0

        def falar(self, texto, saida):
            Contador.chamadas += 1
            audio = saida.with_suffix(".mp3")
            audio.write_bytes(b"audio")
            return Fala(audio, 1.5, [Palavra("oi", 0.0, 0.4)])

    voz = VozComCache(Contador(), "elevenlabs|abc", tmp_path / "cache")
    a = voz.falar("Fato quinze", tmp_path / "f1")
    b = voz.falar("Fato quinze", tmp_path / "f2")
    voz.falar("Outro texto", tmp_path / "f3")
    assert Contador.chamadas == 2
    assert b.audio.read_bytes() == b"audio" and b.duracao == 1.5 and b.palavras[0].texto == "oi"


RSS = """<?xml version="1.0"?><rss><channel>
<item><title>Rockstar moves GTA 6 pre-load to November 10 - Rockstar Games</title><link>https://n/1</link>
 <pubDate>Wed, 04 Nov 2026 10:00:00 GMT</pubDate><source url="https://www.rockstargames.com">Rockstar Games</source></item>
<item><title>GTA 6 preload moved to November 10, 212GB - IGN</title><link>https://n/2</link>
 <pubDate>Wed, 04 Nov 2026 10:30:00 GMT</pubDate><source url="https://www.ign.com">IGN</source></item>
<item><title>Insider diz que GTA Online 2 sai em março - Fórum</title><link>https://n/3</link>
 <pubDate>Wed, 04 Nov 2026 10:40:00 GMT</pubDate><source url="https://forum.exemplo.com">Fórum</source></item>
</channel></rss>"""


def test_radar_le_feed_sugere_selo_e_alerta():
    from datetime import datetime, timezone
    from pipeline import radar

    fontes = radar.config()["radar"]["fontes"]
    noticias = radar.ler_feed(RSS, fontes)
    assert [n.selo_sugerido for n in noticias] == ["confirmado", "relato", "rumor"]
    assert noticias[1].dominio == "ign.com"
    quentes = radar.alertas(noticias, {"fontes_diferentes": 3, "janela_horas": 3},
                            agora=datetime(2026, 11, 4, 11, 0, tzinfo=timezone.utc))
    assert len(quentes) == 1 and len(quentes[0]) == 2       # Rockstar + IGN no mesmo assunto; o rumor fica fora
    assert "CONFIRMADO" in radar.resumo_alerta(quentes[0])


def test_radar_nao_repete_noticia(tmp_path, monkeypatch):
    from datetime import datetime, timezone
    from pipeline import radar

    monkeypatch.setattr(radar, "PASTA_RADAR", tmp_path)
    s = MagicMock()
    s.get.return_value = MagicMock(status_code=200, text=RSS)
    agora = datetime(2026, 11, 4, 11, 0, tzinfo=timezone.utc)
    novas, quentes = radar.rodar(sessao=s, agora=agora)
    assert len(novas) == 3 and len(quentes) == 1
    assert radar.rodar(sessao=s, agora=agora) == ([], [])
    assert "when%3A2d" in s.get.call_args_list[0].args[0]


def test_claude_cli_monta_comando_seguro(tmp_path, monkeypatch):
    import json as _json
    from pipeline import claude_cli

    monkeypatch.setattr(claude_cli, "PASTA_LOG", tmp_path)
    chamadas = []

    def falso(cmd, **kw):
        chamadas.append((cmd, kw))
        return MagicMock(returncode=0, stdout=_json.dumps({"result": "pronto", "total_cost_usd": 0.12}), stderr="")

    ex = claude_cli.rodar("alerta", contexto="[CONFIRMADO?] pré-download em 10/11", executar=falso)
    assert ex.ok and ex.resumo == "pronto" and ex.custo_usd == 0.12
    cmd, kw = chamadas[0]
    assert cmd[:2] == ["claude", "-p"] and "pré-download em 10/11" in cmd[2]
    assert "{data de hoje}" not in cmd[2]
    ferramentas = cmd[cmd.index("--allowedTools") + 1]
    assert "Bash(paginas validar *)" in ferramentas and "Bash," not in ferramentas + ","   # nada de Bash livre
    assert cmd[cmd.index("--permission-mode") + 1] == "acceptEdits"
    assert kw["cwd"] == RAIZ and kw["timeout"] > 0
    import sys as _sys
    assert kw["env"]["PATH"].startswith(str(Path(_sys.executable).parent))   # `paginas` ao alcance do Claude
    assert list(tmp_path.glob("*_alerta.json"))

    def sem_claude(cmd, **kw):
        raise FileNotFoundError

    assert "instale o Claude Code" in claude_cli.rodar("radar", executar=sem_claude).resumo


def test_vigia_organiza_gravacoes(tmp_path):
    import os
    import subprocess
    from pipeline.vigia import organizar_entrada

    entrada, destino = tmp_path / "entrada", tmp_path / "clipes"
    entrada.mkdir()
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "testsrc2=size=320x180:rate=30:duration=1",
                    "-c:v", "libx264", "-preset", "veryfast", str(entrada / "Replay 2026-11-19.mkv")], check=True)
    (entrada / "pronto.mp4").write_bytes(b"x")
    (entrada / "gravando.mp4").write_bytes(b"x")
    agora = 1_800_000_000
    for nome, idade in (("Replay 2026-11-19.mkv", 120), ("pronto.mp4", 120), ("gravando.mp4", 5)):
        os.utime(entrada / nome, (agora - idade, agora - idade))
    movidos = organizar_entrada(entrada, destino, 45, agora=agora)
    assert len(movidos) == 2 and all(m.suffix == ".mp4" for m in movidos)
    assert (entrada / "gravando.mp4").exists() and not (entrada / "pronto.mp4").exists()


def _pauta_telegram(tmp_path):
    arq = tmp_path / "2026-W46_gg_explica.json"
    arq.write_text(json.dumps({"marca": "gg_explica", "semana": "2026-W46", "videos": [
        {"id": "radar_x", "serie": "radar", "status": "rascunho", "data": "2026-11-05", "horario": "19:00",
         "legenda_post": "Legenda", "cenas": [{"tipo": "gancho", "titulo": "Saiu", "narracao": "Saiu a notícia."},
                                              {"tipo": "texto", "selo": "relato", "fonte": "IGN · 04/11",
                                               "fonte_url": "https://ign.com/x", "texto": "x", "narracao": "x."}]}]}),
        encoding="utf-8")
    return arq


class TelegramFalso:
    def __init__(self, atualizacoes=None):
        self.chat_id = "42"
        self.enviados, self.textos, self.respostas, self.fila = [], [], [], atualizacoes or []

    def video(self, arquivo, legenda, botoes):
        self.enviados.append((arquivo, legenda, botoes))
        return {"message_id": 7}

    def texto(self, mensagem, **extra):
        self.textos.append(mensagem)

    def atualizacoes(self, offset, espera=0):
        return [u for u in self.fila if u["update_id"] >= offset]

    def responder_botao(self, cid, texto):
        self.respostas.append(texto)

    def tirar_botoes(self, mid):
        pass


def test_aprovacao_pelo_telegram(tmp_path, monkeypatch):
    from datetime import date
    from pipeline import telegram
    from pipeline.producao import Resultado
    from pipeline.modelos import Pauta as P

    for nome, valor in (("PASTA", tmp_path), ("ARQ_PENDENTES", tmp_path / "p.json"), ("ARQ_OFFSET", tmp_path / "o.txt")):
        monkeypatch.setattr(telegram, nome, valor)
    arq = _pauta_telegram(tmp_path)
    monkeypatch.setattr(telegram, "pautas_de_trabalho", lambda: [arq])
    video_falso = tmp_path / "v.mp4"
    video_falso.write_bytes(b"0")
    produzidos = []

    def produzir(marca, v, previa=False, voz=None):
        produzidos.append(previa)
        if not previa:
            v.status = "renderizado"
        return Resultado(video_falso, "Legenda montada", [])

    tg = TelegramFalso()
    assert telegram.enviar_para_aprovacao(tg, 1, hoje=date(2026, 11, 5), produzir=produzir) == 1
    _, legenda, botoes = tg.enviados[0]
    assert "https://ign.com/x" in legenda and legenda.index("Confira") < legenda.index("Legenda do post")
    assert telegram.enviar_para_aprovacao(tg, 1, hoje=date(2026, 11, 5), produzir=produzir) == 0   # nada mudou
    tok = botoes[0][0]["callback_data"].split("|")[1]

    tg.fila = [
        {"update_id": 1, "callback_query": {"id": "c0", "data": f"a|{tok}", "message": {"chat": {"id": 999}}}},  # outro chat
        {"update_id": 2, "callback_query": {"id": "c1", "data": f"r|{tok}", "message": {"chat": {"id": 42}}}},
        {"update_id": 3, "message": {"chat": {"id": 42}, "text": "troca o gancho por uma pergunta"}},
    ]
    feito = telegram.processar_respostas(tg, produzir=produzir)
    assert feito == ["ajuste pedido radar_x", "nota em radar_x"]
    assert "AJUSTE PEDIDO: troca o gancho" in P.carregar(arq).videos[0].notas_revisao
    assert telegram.ha_ajustes_pendentes()

    # o Claude refaz (tira o marcador), a prévia nova vai e o Vinicius aprova
    p = P.carregar(arq)
    p.videos[0].notas_revisao = "Ajustado: gancho virou pergunta"
    p.videos[0].cenas[0].titulo = "Saiu?"
    p.salvar(arq)
    assert telegram.enviar_para_aprovacao(tg, 1, hoje=date(2026, 11, 5), produzir=produzir) == 1
    tg.fila = [{"update_id": 4, "callback_query": {"id": "c2", "data": f"a|{tok}", "message": {"chat": {"id": 42}}}}]
    assert telegram.processar_respostas(tg, produzir=produzir) == ["aprovado radar_x"]
    assert P.carregar(arq).videos[0].status == "renderizado" and produzidos[-1] is False
    assert telegram.processar_respostas(tg, produzir=produzir) == []                   # offset guardado


def test_modo_automatico_agenda_avisa_e_cancela(tmp_path, monkeypatch):
    from datetime import date
    from pipeline import fila, telegram
    from pipeline.fila import Item
    from pipeline.producao import Resultado
    from pipeline.modelos import Pauta as P

    monkeypatch.setattr(telegram, "modo_aprovacao", lambda: "automatica")
    for nome, valor in (("PASTA", tmp_path), ("ARQ_PENDENTES", tmp_path / "p.json"), ("ARQ_OFFSET", tmp_path / "o.txt"),
                        ("ARQ_ORIENTACOES", tmp_path / "orientacoes.md")):
        monkeypatch.setattr(telegram, nome, valor)
    monkeypatch.setattr(fila, "ARQUIVO_FILA", tmp_path / "fila.json")
    arq = _pauta_telegram(tmp_path)
    monkeypatch.setattr(telegram, "pautas_de_trabalho", lambda: [arq])
    video_falso = tmp_path / "v.mp4"
    video_falso.write_bytes(b"0")

    def produzir(marca, v, previa=False, voz=None):
        assert previa is False                       # automático: já é a versão final
        v.status = "renderizado"
        fila.enfileirar_instagram(Item(id=v.id, marca="gg_explica", video=str(video_falso), capa="",
                                       legenda="TÍTULO\n\nx", quando="2026-11-05T19:00:00-03:00"))
        return Resultado(video_falso, "Legenda montada", [])

    tg = TelegramFalso()
    assert telegram.enviar_para_aprovacao(tg, 1, hoje=date(2026, 11, 5), produzir=produzir) == 1
    _, texto, botoes = tg.enviados[0]
    assert "Agendado" in texto and [b["text"] for b in botoes[0]] == ["✍️ Ajustar", "🗑 Cancelar"]
    assert P.carregar(arq).videos[0].status == "renderizado" and len(fila.carregar()) == 1
    tok = botoes[0][1]["callback_data"].split("|")[1]

    tg.fila = [{"update_id": 1, "callback_query": {"id": "c1", "data": f"c|{tok}", "message": {"chat": {"id": 42}}}},
               {"update_id": 2, "message": {"chat": {"id": 42}, "text": "menos texto nos slides"}}]
    assert telegram.processar_respostas(tg, produzir=produzir) == ["cancelado radar_x", "orientação anotada"]
    assert P.carregar(arq).videos[0].status == "descartado" and fila.carregar() == []
    assert "menos texto nos slides" in (tmp_path / "orientacoes.md").read_text(encoding="utf-8")


def test_palavra_quente_com_uma_fonte_seria_vira_alerta():
    from datetime import datetime, timezone
    from pipeline.radar import Noticia, alertas
    agora = datetime(2026, 11, 10, 18, 0, tzinfo=timezone.utc)
    n = Noticia(titulo="GTA 6 ganha novo trailer", link="https://ign.com/a", fonte="IGN", dominio="ign.com",
                publicada=agora.isoformat(), selo_sugerido="relato", consulta="GTA 6")
    assert alertas([n], {"palavras_quentes": ["trailer"]}, agora) == [[n]]
    assert alertas([n], {"palavras_quentes": []}, agora) == []
