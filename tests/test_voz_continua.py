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
