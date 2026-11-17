import wave
from pathlib import Path

from pipeline.voz import Fala, Palavra, cena_de_cada_palavra, falar_continuo, ssml_azure


class VozFalsa:
    """Gera 24 kHz de silêncio com 0,3 s por palavra e 0,4 s de respiro depois de cada ponto final."""

    def __init__(self, juntar=False):
        self.chamadas, self.juntar = [], juntar

    def falar(self, texto, saida: Path) -> Fala:
        self.chamadas.append(texto)
        t, palavras = 0.05, []
        for w in texto.split():
            palavras.append(Palavra(w.strip(".,:?"), t, t + 0.3))
            t += 0.3 + (0.4 if w.endswith(".") else 0.05)
        if self.juntar:   # a voz junta "pré" e "load" e lê "GTA" como "gê tê á"
            palavras = [p for p in palavras if p.texto != "extra"]
        wav = saida.with_suffix(".wav")
        with wave.open(str(wav), "wb") as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(24000)
            w.writeframes(b"\0\0" * int((t + 0.1) * 24000))
        return Fala(wav, t + 0.1, palavras)


def test_narra_o_roteiro_inteiro_uma_vez_e_corta_no_respiro(tmp_path):
    textos = ["Faltam três dias pra GTA seis.", "Um: confira o pré-load hoje.", "Comenta pronto."]
    voz = VozFalsa()
    falas, continua = falar_continuo(voz, textos, tmp_path)
    assert continua and len(voz.chamadas) == 1
    assert [len(f.palavras) for f in falas] == [6, 5, 2]
    # cada cena começa perto de zero e o corte fica no respiro (depois do fim da última palavra)
    for f in falas:
        assert f.palavras[0].inicio < 0.3
        assert f.palavras[-1].fim <= f.duracao
    with wave.open(str(falas[1].audio)) as w:
        assert abs(w.getnframes() / 24000 - falas[1].duracao) < 0.01


def test_alinha_mesmo_quando_a_voz_muda_palavras():
    textos = ["Faltam três dias extra.", "Comenta pronto."]
    palavras = [Palavra(x, i, i + 0.5) for i, x in enumerate(["Faltam", "3", "dias", "Comenta", "pronto"])]
    assert cena_de_cada_palavra(textos, palavras) == [0, 0, 0, 1, 1]


def test_volta_para_cena_por_cena_se_uma_cena_some():
    assert cena_de_cada_palavra(["Oi.", "Tchau."], [Palavra("Oi", 0, 0.2)]) is None


def test_ssml_hd_sem_prosody_e_multilingue_com_lang():
    hd = ssml_azure({"voz": "en-US-Andrew:DragonHDLatestNeural", "velocidade": "+10%"}, "Olá")
    assert "<prosody" not in hd and 'xml:lang="pt-BR">Olá' in hd
    multi = ssml_azure({"voz": "pt-BR-MacerioMultilingualNeural", "velocidade": "+8%"}, "Olá")
    assert '<lang xml:lang="pt-BR">' in multi and 'rate="+8%"' in multi
    comum = ssml_azure({"voz": "pt-BR-AntonioNeural", "velocidade": "+12%", "tom": "+3%"}, "A & B")
    assert "<lang" not in comum and "A &amp; B" in comum


def test_tempo_das_palavras_casa_com_o_que_o_whisper_ouviu(tmp_path):
    from pipeline.voz import tempos_das_palavras
    texto = "Faltam três dias pra GTA seis. Comenta pronto."
    ouvidas = [Palavra("Faltam", 0.1, 0.4), Palavra("3", 0.45, 0.7), Palavra("dias", 0.75, 1.0),
               Palavra("pra", 1.05, 1.2), Palavra("gtá", 1.25, 1.6), Palavra("seis.", 1.65, 1.9),
               Palavra("Comenta", 2.3, 2.7), Palavra("pronto.", 2.75, 3.1)]
    p = tempos_das_palavras(texto, tmp_path / "x.wav", 3.3, ouvidas)
    assert [x.texto for x in p] == ["Faltam", "três", "dias", "pra", "GTA", "seis", "Comenta", "pronto"]
    assert p[0].inicio == 0.1 and p[6].inicio == 2.3
    # "três" e "GTA" não casaram: ficam entre as vizinhas, em ordem
    assert 0.4 <= p[1].inicio < p[1].fim <= 0.75
    assert 1.2 <= p[4].inicio < p[4].fim <= 1.65
    assert all(a.inicio <= b.inicio for a, b in zip(p, p[1:]))


def test_tempo_estimado_sem_whisper(tmp_path):
    from pipeline.voz import tempos_das_palavras
    p = tempos_das_palavras("um dois três", tmp_path / "x.wav", 3.0, [])
    assert len(p) == 3 and p[0].inicio == 0.0 and p[-1].fim <= 3.0


def test_gemini_com_reserva_e_sem_chave_vai_para_azure(monkeypatch):
    import dataclasses
    from pipeline import voz as v
    from pipeline.marca import carregar_marca
    marca = carregar_marca("gg_explica")
    assert marca.voz["provedor"] == "gemini" and marca.voz["gemini"]["voz"] == "pt-br-storyteller-2"
    monkeypatch.setenv("GEMINI_API_KEY", "x")
    monkeypatch.setattr(v, "Azure", lambda cfg: "azure")
    escolhida = v.criar_voz(marca, cache=False)
    assert isinstance(escolhida, v.ComReserva) and isinstance(escolhida.principal, v.Gemini)
    monkeypatch.delenv("GEMINI_API_KEY")
    assert v.criar_voz(marca, cache=False) == "azure"

    class Quebra:
        def falar(self, texto, saida):
            raise RuntimeError("429")

    class Boa:
        def falar(self, texto, saida):
            return "ok"
    assert v.ComReserva(Quebra(), Boa()).falar("oi", None) == "ok"


def test_fala_incompleta_recusa_audio_cortado():
    from pipeline.voz import fala_incompleta
    texto = " ".join(f"palavra{i}" for i in range(100))
    assert "só" in fala_incompleta(texto, 10.0, [])            # 100 palavras em 10 s: cortou
    metade = [Palavra(f"palavra{i}", i * 0.3, i * 0.3 + 0.25) for i in range(50)]
    assert fala_incompleta(texto, 31.0, metade)                  # ouviu só a metade
    inteira = [Palavra(f"palavra{i}", i * 0.3, i * 0.3 + 0.25) for i in range(100)]
    assert fala_incompleta(texto, 31.0, inteira) == ""


def test_corte_sem_fala_volta_para_cena_por_cena(tmp_path):
    class VozQuePula(VozFalsa):
        def falar(self, texto, saida):
            fala = super().falar(texto, saida)
            if len(self.chamadas) == 1:     # roteiro inteiro: o fim sai espremido em 0,1 s (fala cortada)
                fim = fala.duracao - 0.05
                for k, p in enumerate(fala.palavras[3:]):
                    p.inicio = p.fim = fim - 0.1 + k * 0.02
            return fala
    textos = ["Um um um.", "Dois.", "Três três três."]
    voz = VozQuePula()
    falas, continua = falar_continuo(voz, textos, tmp_path)
    assert not continua and len(voz.chamadas) == 4
