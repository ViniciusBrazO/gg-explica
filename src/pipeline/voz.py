"""Narração: transforma o texto de cada cena em áudio e devolve o tempo de cada palavra.

O tempo de cada palavra é o que permite a legenda "karaokê" acender palavra por palavra,
sem precisar transcrever o áudio depois.

Provedores:
- elevenlabs: melhor qualidade em português; exige plano pago para uso comercial.
- azure: vozes neurais pt-BR com cota gratuita mensal; ótima alternativa sem custo.
- silencio: sem áudio, com tempos estimados. Só para testar o visual sem chave de API.
"""
from __future__ import annotations

import base64
import os
import re
import subprocess
import wave
from dataclasses import dataclass
from pathlib import Path

import requests

from .marca import Marca


@dataclass
class Palavra:
    texto: str
    inicio: float
    fim: float


@dataclass
class Fala:
    audio: Path
    duracao: float
    palavras: list[Palavra]
    tempos_estimados: bool = False     # True: o whisper não rodou (não guarda no cache)


# ---------------------------------------------------------------- texto falado

_UNIDADES = ["zero", "um", "dois", "três", "quatro", "cinco", "seis", "sete", "oito", "nove",
             "dez", "onze", "doze", "treze", "catorze", "quinze", "dezesseis", "dezessete",
             "dezoito", "dezenove"]
_DEZENAS = ["", "", "vinte", "trinta", "quarenta", "cinquenta", "sessenta", "setenta", "oitenta", "noventa"]
_CENTENAS = ["", "cento", "duzentos", "trezentos", "quatrocentos", "quinhentos", "seiscentos",
             "setecentos", "oitocentos", "novecentos"]


def por_extenso(n: int) -> str:
    """Número inteiro (0 a 999.999) por extenso em português do Brasil."""
    if n < 20:
        return _UNIDADES[n]
    if n < 100:
        d, u = divmod(n, 10)
        return _DEZENAS[d] + ("" if u == 0 else " e " + _UNIDADES[u])
    if n == 100:
        return "cem"
    if n < 1000:
        c, r = divmod(n, 100)
        return _CENTENAS[c] + ("" if r == 0 else " e " + por_extenso(r))
    milhar, r = divmod(n, 1000)
    prefixo = "mil" if milhar == 1 else por_extenso(milhar) + " mil"
    if r == 0:
        return prefixo
    liga = " e " if (r < 100 or r % 100 == 0) else " "
    return prefixo + liga + por_extenso(r)


def _reais_falado(m: re.Match) -> str:
    inteiro = int(m.group(1).replace(".", ""))
    centavos = int((m.group(2) or "0").ljust(2, "0")[:2])
    texto = por_extenso(inteiro) + (" real" if inteiro == 1 else " reais")
    if centavos:
        texto += " e " + por_extenso(centavos)
    return texto


def texto_para_fala(texto: str) -> str:
    """Prepara o texto para a voz: tira marcações e escreve preços como se fala."""
    t = texto.replace("*", "")
    t = re.sub(r"R\$\s?(\d{1,3}(?:\.\d{3})*|\d+)(?:,(\d{1,2}))?", _reais_falado, t)
    t = re.sub(r"(\d+)\s?%", lambda m: por_extenso(int(m.group(1))) + " por cento", t)
    t = re.sub(r"/\s?ml\b", " por ml", t)
    t = re.sub(r"(?<=\s)[xX](?=\s)", "contra", t)
    return re.sub(r"\s+", " ", t).strip()


# ---------------------------------------------------------------- utilidades de áudio

def _duracao_audio(caminho: Path) -> float:
    from .sonda import duracao
    return duracao(caminho)


def _palavras_de_caracteres(chars: list[str], inicios: list[float], fins: list[float]) -> list[Palavra]:
    palavras, atual, ini, fim = [], "", None, 0.0
    for c, a, b in zip(chars, inicios, fins):
        if c.isspace():
            if atual:
                palavras.append(Palavra(atual, ini, fim))
            atual, ini = "", None
            continue
        if ini is None:
            ini = a
        atual += c
        fim = b
    if atual:
        palavras.append(Palavra(atual, ini, fim))
    return palavras


# ---------------------------------------------------------------- provedores

class ElevenLabs:
    URL = "https://api.elevenlabs.io/v1/text-to-speech/{voz}/with-timestamps"

    def __init__(self, cfg: dict):
        self.chave = os.environ["ELEVENLABS_API_KEY"]
        self.cfg = cfg
        if not cfg.get("voice_id"):
            raise ValueError("Defina voz.elevenlabs.voice_id no YAML da marca.")

    def falar(self, texto: str, saida: Path) -> Fala:
        corpo = {
            "text": texto,
            "model_id": self.cfg.get("modelo", "eleven_multilingual_v2"),
            "voice_settings": {
                "stability": self.cfg.get("estabilidade", 0.45),
                "similarity_boost": self.cfg.get("similaridade", 0.75),
                "style": self.cfg.get("estilo", 0.2),
                "use_speaker_boost": True,
                "speed": self.cfg.get("velocidade", 1.0),
            },
        }
        r = requests.post(
            self.URL.format(voz=self.cfg["voice_id"]),
            params={"output_format": "mp3_44100_128"},
            headers={"xi-api-key": self.chave, "Content-Type": "application/json"},
            json=corpo, timeout=120,
        )
        r.raise_for_status()
        dados = r.json()
        mp3 = saida.with_suffix(".mp3")
        mp3.write_bytes(base64.b64decode(dados["audio_base64"]))
        al = dados.get("normalized_alignment") or dados["alignment"]
        palavras = _palavras_de_caracteres(
            al["characters"], al["character_start_times_seconds"], al["character_end_times_seconds"])
        return Fala(mp3, _duracao_audio(mp3), palavras)


class Azure:
    def __init__(self, cfg: dict):
        import azure.cognitiveservices.speech as sdk  # import tardio: só quem usa Azure precisa instalar
        self.sdk = sdk
        self.cfg = cfg
        self.conf = sdk.SpeechConfig(subscription=os.environ["AZURE_SPEECH_KEY"],
                                     region=os.environ["AZURE_SPEECH_REGION"])
        self.conf.set_speech_synthesis_output_format(
            sdk.SpeechSynthesisOutputFormat.Riff24Khz16BitMonoPcm)

    def falar(self, texto: str, saida: Path) -> Fala:
        sdk = self.sdk
        wav = saida.with_suffix(".wav")
        sintetizador = sdk.SpeechSynthesizer(speech_config=self.conf,
                                             audio_config=sdk.audio.AudioOutputConfig(filename=str(wav)))
        palavras: list[Palavra] = []

        def marcar(evt):
            if evt.boundary_type == sdk.SpeechSynthesisBoundaryType.Word:
                ini = evt.audio_offset / 10_000_000
                palavras.append(Palavra(evt.text, ini, ini + evt.duration.total_seconds()))

        sintetizador.synthesis_word_boundary.connect(marcar)
        ssml = ssml_azure(self.cfg, texto)
        res = sintetizador.speak_ssml_async(ssml).get()
        if res.reason != sdk.ResultReason.SynthesizingAudioCompleted:
            raise RuntimeError(f"Azure não gerou o áudio: {res.reason} {getattr(res, 'cancellation_details', '')}")
        return Fala(wav, _duracao_audio(wav), palavras)


class Gemini:
    """Gemini TTS (Google AI Studio, GEMINI_API_KEY): vozes pt-BR da biblioteca, fala bem humana.
    A API não devolve o tempo de cada palavra; o kit descobre ouvindo o áudio (faster-whisper) e
    alinha com o roteiro. Escolhida pelo Vinicius em 16/11: pt-br-storyteller-2."""

    API = "https://generativelanguage.googleapis.com/v1beta/interactions"

    def __init__(self, cfg: dict):
        self.chave = os.environ["GEMINI_API_KEY"]
        self.cfg = cfg

    def _audio(self, texto: str, destino: Path) -> Path:
        import time
        corpo = {
            "model": self.cfg.get("modelo", "gemini-3.8-flash-tts"),
            "input": [{"type": "user_input", "content": [{
                "type": "text", "text": texto,
                "annotations": [{"type": "speech_metadata", "style": self.cfg.get("estilo", "")}]}]}],
            "response_format": {"type": "audio"},
            "generation_config": {"speech_config": [{"voice": self.cfg["voz"]}]},
        }
        erro = ""
        for tentativa in range(3):
            try:
                r = requests.post(self.API, headers={"x-goog-api-key": self.chave}, json=corpo, timeout=150)
            except requests.RequestException as e:
                erro = str(e)
            else:
                if r.status_code == 200:
                    audios = [c for st in r.json().get("steps", []) if st.get("type") == "model_output"
                              for c in st.get("content", []) if c.get("type") == "audio"]
                    if audios:
                        destino.write_bytes(base64.b64decode(audios[-1]["data"]))
                        return destino
                    erro = "resposta sem áudio"
                else:
                    erro = f"HTTP {r.status_code} {r.text[:200]}"
                    if r.status_code not in (429, 500, 502, 503, 504):
                        break
            time.sleep(10 * (tentativa + 1))
        raise RuntimeError(f"Gemini TTS não gerou o áudio: {erro}")

    def falar(self, texto: str, saida: Path) -> Fala:
        n_palavras = len([w for w in texto.split() if _norm(w)])
        motivo = ""
        for tentativa in range(2):     # o Gemini às vezes corta ou pula um trecho: confere e tenta de novo
            wav = self._audio(texto, saida.with_suffix(".wav"))
            duracao = _duracao_audio(wav)
            ouvidas = ouvir_com_prazo(wav, texto)
            motivo = fala_incompleta(texto, duracao, ouvidas)
            if not motivo:
                return Fala(wav, duracao, tempos_das_palavras(texto, wav, duracao, ouvidas),
                            tempos_estimados=not ouvidas)
            ouviu = " ".join(p.texto for p in ouvidas[:15])
            print(f"  voz: Gemini {motivo} (tentativa {tentativa + 1}, {n_palavras} palavras, {duracao:.1f} s); "
                  f"o whisper ouviu: {ouviu[:160]!r}")
        raise RuntimeError(f"Gemini {motivo}")


def _ouvir(wav: Path, texto: str) -> list[Palavra]:
    """Palavras que o faster-whisper ouviu, com tempo. Vazio se ele não estiver instalado."""
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        print("  voz: faster-whisper não instalado; tempo das palavras estimado")
        return []
    global _MODELO_WHISPER
    if _MODELO_WHISPER is None:
        _MODELO_WHISPER = WhisperModel(os.environ.get("WHISPER_MODELO", "base"), device="cpu",
                                       compute_type="int8")
    # o áudio vai já decodificado (16 kHz mono): o decodificador do faster-whisper quebra com o PyAV novo
    import numpy as np
    dezesseis = wav.with_name(wav.stem + "_16k.wav")
    subprocess.run(["ffmpeg", "-nostdin", "-loglevel", "error", "-y", "-i", str(wav), "-ac", "1", "-ar", "16000",
                    "-c:a", "pcm_s16le", str(dezesseis)], check=True, capture_output=True)
    with wave.open(str(dezesseis), "rb") as w:
        amostras = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768.0
    segmentos, _ = _MODELO_WHISPER.transcribe(amostras, language="pt", word_timestamps=True,
                                              initial_prompt=texto[:800], beam_size=1,
                                              condition_on_previous_text=False)
    return [Palavra(w.word.strip(), float(w.start), float(w.end)) for seg in segmentos for w in seg.words]


_MODELO_WHISPER = None


def ouvir_com_prazo(wav: Path, texto: str, prazo_s: float = 240.0) -> list[Palavra]:
    """O whisper travou uma rodada inteira em 23/11: se passar do prazo, segue com o tempo estimado."""
    import concurrent.futures as cf
    exe = cf.ThreadPoolExecutor(max_workers=1)
    futuro = exe.submit(_ouvir, wav, texto)
    try:
        return futuro.result(timeout=prazo_s)
    except cf.TimeoutError:
        print(f"  voz: whisper passou de {prazo_s:.0f} s; tempo das palavras estimado")
        return []
    except Exception as e:  # noqa: BLE001
        print(f"  voz: whisper falhou ({str(e)[:120]}); tempo das palavras estimado")
        return []
    finally:
        exe.shutdown(wait=False, cancel_futures=True)


def tempos_das_palavras(texto: str, wav: Path, duracao: float,
                        ouvidas: list[Palavra] | None = None) -> list[Palavra]:
    """Dá a cada palavra do roteiro o tempo em que ela é falada: casa com o que o whisper ouviu e
    distribui as que ficaram sem par entre as vizinhas, pelo tamanho."""
    import difflib
    roteiro = [w for w in texto.split() if _norm(w)]
    if not roteiro:
        return []
    if ouvidas is None:
        try:
            ouvidas = _ouvir(wav, texto)
        except Exception as e:  # noqa: BLE001
            print(f"  voz: whisper falhou ({str(e)[:120]}); tempo das palavras estimado")
            ouvidas = []
    tempos: list[tuple[float, float] | None] = [None] * len(roteiro)
    a, b = [_norm(w) for w in roteiro], [_norm(p.texto) for p in ouvidas]
    for bloco in difflib.SequenceMatcher(None, a, b, autojunk=False).get_matching_blocks():
        for k in range(bloco.size):
            p = ouvidas[bloco.b + k]
            tempos[bloco.a + k] = (p.inicio, p.fim)
    # lacunas: entre o fim da última palavra conhecida e o início da próxima, pelo número de letras
    i, n = 0, len(roteiro)
    while i < n:
        if tempos[i] is not None:
            i += 1
            continue
        j = i
        while j < n and tempos[j] is None:
            j += 1
        ini = tempos[i - 1][1] if i > 0 else 0.0
        fim = tempos[j][0] if j < n else max(ini, duracao - 0.15)
        pesos = [len(_norm(w)) + 1 for w in roteiro[i:j]]
        passo, t = (fim - ini) / sum(pesos), ini
        for k, peso in zip(range(i, j), pesos):
            tempos[k] = (t, t + passo * peso)
            t += passo * peso
        i = j
    return [Palavra(w.replace("*", "").strip(PONTUACAO), ini, max(ini + 0.05, fim))
            for w, (ini, fim) in zip(roteiro, tempos)]


PONTUACAO = ".,;:!?\"“”()…'"


def fala_incompleta(texto: str, duracao: float, ouvidas: list[Palavra]) -> str:
    """Motivo para recusar o áudio ("" se está bom): curto demais para o texto, ou o whisper não
    ouviu boa parte do roteiro (fala cortada ou trecho pulado)."""
    import difflib
    roteiro = [_norm(w) for w in texto.split() if _norm(w)]
    if not roteiro:
        return ""
    if duracao < len(roteiro) / 5.5:
        return f"gerou só {duracao:.1f} s de áudio"
    if not ouvidas:
        return ""
    casadas = sum(b.size for b in difflib.SequenceMatcher(
        None, roteiro, [_norm(p.texto) for p in ouvidas], autojunk=False).get_matching_blocks())
    if casadas / len(roteiro) < 0.7:
        return f"falou só {casadas}/{len(roteiro)} palavras do roteiro"
    # o fim do roteiro precisa estar no áudio (as últimas palavras)
    fim = roteiro[-4:]
    ouvidas_fim = {_norm(p.texto) for p in ouvidas[-12:]}
    if not any(w in ouvidas_fim for w in fim):
        return "cortou o fim do roteiro"
    return ""


class ComReserva:
    """Usa a voz principal; se ela falhar (cota do plano gratuito, fora do ar), narra com a reserva."""

    def __init__(self, principal, reserva):
        self.principal, self.reserva = principal, reserva

    def falar(self, texto: str, saida: Path) -> Fala:
        try:
            return self.principal.falar(texto, saida)
        except Exception as e:  # noqa: BLE001
            print(f"  voz principal falhou ({str(e)[:160]}); usando a reserva")
            return self.reserva.falar(texto, saida)


def ssml_azure(cfg: dict, texto: str) -> str:
    """Vozes HD (":DragonHD") não aceitam <prosody>; vozes multilíngues recebem <lang> para falar
    com sotaque brasileiro."""
    nome = cfg["voz"]
    corpo = _escapar_xml(texto)
    if "Multilingual" in nome or ":DragonHD" in nome:
        corpo = f'<lang xml:lang="pt-BR">{corpo}</lang>'
    if ":DragonHD" not in nome:
        corpo = (f'<prosody rate="{cfg.get("velocidade", "+0%")}" pitch="{cfg.get("tom", "+0%")}">'
                 f"{corpo}</prosody>")
    parametros = f' parameters="{cfg["parametros"]}"' if cfg.get("parametros") else ""
    return ('<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" '
            'xmlns:mstts="https://www.w3.org/2001/mstts" xml:lang="pt-BR">'
            f'<voice name="{nome}"{parametros}>{corpo}</voice></speak>')


class Silencio:
    """Sem áudio: estima 2,7 palavras por segundo. Serve para testar o visual."""

    def __init__(self, cfg: dict | None = None):
        self.ritmo = 2.7

    def falar(self, texto: str, saida: Path) -> Fala:
        palavras_txt = texto.split()
        t, palavras = 0.15, []
        for p in palavras_txt:
            dur = max(0.16, len(p) / 20 + 0.07) * (2.7 / self.ritmo)
            palavras.append(Palavra(p, t, t + dur))
            t += dur + (0.18 if p[-1] in ".,:;!?" else 0.03)
        duracao = t + 0.2
        wav = saida.with_suffix(".wav")
        with wave.open(str(wav), "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(24000)
            w.writeframes(b"\x00\x00" * int(24000 * duracao))
        return Fala(wav, duracao, palavras)


def _escapar_xml(t: str) -> str:
    return t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


class VozComCache:
    """Guarda cada narração já gerada: aprovar, refazer o visual ou renderizar de novo não gasta
    crédito de voz outra vez. A chave é o provedor, a configuração da voz e o texto exato."""

    def __init__(self, voz, assinatura: str, pasta: Path):
        self.voz, self.assinatura, self.pasta = voz, assinatura, pasta

    def falar(self, texto: str, saida: Path) -> Fala:
        import hashlib
        import json
        import shutil

        chave = hashlib.sha256(f"{self.assinatura}|{texto}".encode("utf-8")).hexdigest()[:24]
        meta = self.pasta / f"{chave}.json"
        if meta.exists():
            dados = json.loads(meta.read_text(encoding="utf-8"))
            audio = self.pasta / dados["audio"]
            if audio.exists():
                destino = saida.with_suffix(audio.suffix)
                shutil.copy2(audio, destino)
                return Fala(destino, dados["duracao"], [Palavra(*p) for p in dados["palavras"]])
        fala = self.voz.falar(texto, saida)
        if fala.tempos_estimados:
            return fala
        self.pasta.mkdir(parents=True, exist_ok=True)
        guardado = self.pasta / f"{chave}{fala.audio.suffix}"
        shutil.copy2(fala.audio, guardado)
        meta.write_text(json.dumps({"audio": guardado.name, "duracao": fala.duracao,
                                    "palavras": [[p.texto, p.inicio, p.fim] for p in fala.palavras]},
                                   ensure_ascii=False), encoding="utf-8")
        return fala



# ---------------------------------------------------------------- narração contínua

def _norm(palavra: str) -> str:
    import unicodedata
    t = unicodedata.normalize("NFD", palavra.lower())
    return "".join(c for c in t if c.isalnum())


def _wav(audio: Path) -> Path:
    if audio.suffix.lower() == ".wav":
        return audio
    destino = audio.with_suffix(".wav")
    subprocess.run(["ffmpeg", "-nostdin", "-loglevel", "error", "-y", "-i", str(audio), "-ac", "1",
                    "-ar", "24000", str(destino)], check=True, capture_output=True)
    return destino


def cena_de_cada_palavra(textos: list[str], palavras: list[Palavra]) -> list[int] | None:
    """A qual cena pertence cada palavra que a voz devolveu (a voz pode juntar ou separar palavras,
    então alinha pelo texto). None se alguma cena ficar sem palavra."""
    import difflib
    esperado, dono = [], []
    for i, t in enumerate(textos):
        for w in t.split():
            if _norm(w):
                esperado.append(_norm(w))
                dono.append(i)
    recebido = [_norm(p.texto) for p in palavras]
    cenas: list[int | None] = [None] * len(recebido)
    for bloco in difflib.SequenceMatcher(None, esperado, recebido, autojunk=False).get_matching_blocks():
        for k in range(bloco.size):
            cenas[bloco.b + k] = dono[bloco.a + k]
    atual = 0
    for j, c in enumerate(cenas):        # palavra sem par fica com a cena da anterior
        if c is None or c < atual:
            cenas[j] = atual
        else:
            atual = c
    if set(cenas) != set(range(len(textos))):
        return None
    return cenas  # type: ignore[return-value]


def falar_continuo(voz, textos: list[str], pasta: Path) -> tuple[list[Fala], bool]:
    """Narra o roteiro inteiro de uma vez (entonação de fala corrida, sem a pausa e o "recomeço" de
    cada cena) e corta o áudio no respiro entre as cenas. Devolve (falas por cena, ficou_continua).
    Se não der para alinhar, volta a narrar cena por cena."""
    if isinstance(voz, Silencio) or len(textos) < 2:
        return [voz.falar(t, pasta / f"fala_{i:02d}") for i, t in enumerate(textos)], False
    inteira = voz.falar(" ".join(textos), pasta / "fala_inteira")
    cenas = cena_de_cada_palavra(textos, inteira.palavras) if inteira.palavras else None
    if cenas is None:
        print("  voz: não alinhou o roteiro inteiro; narrando cena por cena")
        return [voz.falar(t, pasta / f"fala_{i:02d}") for i, t in enumerate(textos)], False
    origem = _wav(inteira.audio)
    with wave.open(str(origem), "rb") as w:
        params, taxa = w.getparams(), w.getframerate()
        quadros = w.readframes(w.getnframes())
    largura = params.sampwidth * params.nchannels
    total = len(quadros) // largura / taxa
    cortes = [0.0]
    for i in range(1, len(textos)):
        ultima = max(j for j, c in enumerate(cenas) if c == i - 1)
        primeira = min(j for j, c in enumerate(cenas) if c == i)
        fim, ini = inteira.palavras[ultima].fim, inteira.palavras[primeira].inicio
        cortes.append(max(fim, min(ini - 0.03, (fim + ini) / 2)))
    cortes.append(total)
    if any(b - a < 0.3 for a, b in zip(cortes, cortes[1:])):
        print("  voz: alguma cena ficou sem fala no corte; narrando cena por cena")
        return [voz.falar(t, pasta / f"fala_{i:02d}") for i, t in enumerate(textos)], False
    falas = []
    for i in range(len(textos)):
        a, b = cortes[i], cortes[i + 1]
        destino = pasta / f"fala_{i:02d}.wav"
        with wave.open(str(destino), "wb") as w:
            w.setparams(params)
            w.writeframes(quadros[int(a * taxa) * largura:int(b * taxa) * largura])
        palavras = [Palavra(p.texto, max(0.0, p.inicio - a), max(0.0, p.fim - a))
                    for p, c in zip(inteira.palavras, cenas) if c == i]
        falas.append(Fala(destino, b - a, palavras))
    return falas, True

PASTA_CACHE_VOZ = Path(__file__).resolve().parents[2] / "saida" / "cache_voz"


def criar_voz(marca: Marca, forcar: str | None = None, cache: bool = True):
    import json

    provedor = forcar or marca.voz.get("provedor", "silencio")
    if provedor == "gemini" and not os.environ.get("GEMINI_API_KEY"):
        provedor = marca.voz.get("reserva", "azure")
    if provedor == "silencio":
        return Silencio()

    def montar(nome: str):
        if nome == "elevenlabs":
            voz = ElevenLabs(marca.voz["elevenlabs"])
        elif nome == "azure":
            voz = Azure(marca.voz["azure"])
        elif nome == "gemini":
            voz = Gemini(marca.voz["gemini"])
        else:
            raise ValueError(f"provedor de voz desconhecido: {nome}")
        if not cache:
            return voz
        extra = "|whisper3" if nome == "gemini" else ""     # muda quando o jeito de achar o tempo muda
        return VozComCache(voz, f"{nome}|{json.dumps(marca.voz.get(nome, {}), sort_keys=True)}{extra}",
                           PASTA_CACHE_VOZ)

    voz = montar(provedor)
    reserva = marca.voz.get("reserva")
    if provedor == "gemini" and reserva and reserva != "gemini" and not forcar:
        try:
            return ComReserva(voz, montar(reserva))
        except Exception:  # noqa: BLE001  (sem chave da reserva: segue só com a principal)
            return voz
    return voz
