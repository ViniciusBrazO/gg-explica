"""Amostras de voz para comparar (tarefa `vozes-naturais` no GitHub Actions). Não publica nada.

Narra o mesmo roteiro curto (o Reel "3 passos" de 16/11) com:
  - a voz de hoje, cena por cena (como saía até agora, com a pausa entre cenas);
  - a mesma voz em fala corrida (o roteiro inteiro de uma vez);
  - vozes multilíngues e HD da Azure que falam pt-BR;
  - vozes do Gemini TTS (Google), com instrução de estilo.
Os MP3 ficam em saida/amostras_voz/ (o workflow guarda como artefato).
"""
from __future__ import annotations

import base64
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import requests

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))

from pipeline.voz import Azure, falar_continuo, texto_para_fala  # noqa: E402

SAIDA = RAIZ / "saida" / "amostras_voz"
ROTEIRO = [
    "Faltam três dias pra GTA seis. Faz esses três passos hoje e você joga na virada.",
    "Um: confira se o pré-load terminou. Ele abriu em dez de novembro, são nove dias de folga pra baixar.",
    "Dois: comprou a versão em caixa? O código vale pra começar o pré-load assim que você ativa. "
    "Ative hoje, não na quarta à noite.",
    "Três: guarde o horário. Libera à meia-noite local do dia dezenove, ou seja, na virada de quarta pra "
    "quinta no Brasil.",
    "Se o seu já está baixado, comenta pronto. Salva esse vídeo pra checar na quarta.",
]
ESTILO = ("Apresentador brasileiro de notícias de games no Instagram: animado, ritmo rápido e natural, "
          "como um amigo contando uma novidade, sem soar como locutor de rádio.")


def mp3(wav: Path, nome: str) -> None:
    destino = SAIDA / f"{nome}.mp3"
    subprocess.run(["ffmpeg", "-nostdin", "-loglevel", "error", "-y", "-i", str(wav), "-af",
                    "loudnorm=I=-16:TP=-1.5", "-ar", "44100", "-b:a", "128k", str(destino)], check=True)
    dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
                                str(destino)], capture_output=True, text=True).stdout or 0)
    print(f"OK {destino.name}: {dur:.1f} s")


def juntar(wavs: list[Path], pausa: float, destino: Path) -> Path:
    entradas, filtros = [], []
    for i, w in enumerate(wavs):
        entradas += ["-i", str(w)]
        filtros.append(f"[{i}:a]apad=pad_dur={pausa}[a{i}]")
    filtro = ";".join(filtros) + ";" + "".join(f"[a{i}]" for i in range(len(wavs))) + \
        f"concat=n={len(wavs)}:v=0:a=1[s]"
    subprocess.run(["ffmpeg", "-nostdin", "-loglevel", "error", "-y", *entradas, "-filter_complex", filtro,
                    "-map", "[s]", str(destino)], check=True)
    return destino


def azure(cfg: dict, nome: str, continua: bool = True) -> None:
    pasta = SAIDA / "_trab" / nome
    pasta.mkdir(parents=True, exist_ok=True)
    textos = [texto_para_fala(t) for t in ROTEIRO]
    try:
        voz = Azure(cfg)
        if continua:
            falas, ok = falar_continuo(voz, textos, pasta)
            print(f"  {nome}: fala corrida {'alinhada' if ok else 'NÃO alinhou'}, "
                  f"{sum(len(f.palavras) for f in falas)} palavras com tempo")
            mp3(juntar([f.audio for f in falas], 0.0, pasta / "tudo.wav"), nome)
        else:
            falas = [voz.falar(t, pasta / f"c{i}") for i, t in enumerate(textos)]
            mp3(juntar([f.audio for f in falas], 0.18 + 0.15, pasta / "tudo.wav"), nome)
    except Exception as e:  # noqa: BLE001
        print(f"FALHOU {nome}: {str(e)[:300]}")


def vozes_azure() -> list[dict]:
    regiao = os.environ.get("AZURE_SPEECH_REGION", "brazilsouth")
    r = requests.get(f"https://{regiao}.tts.speech.microsoft.com/cognitiveservices/voices/list",
                     headers={"Ocp-Apim-Subscription-Key": os.environ["AZURE_SPEECH_KEY"]}, timeout=30)
    r.raise_for_status()
    vozes = r.json()
    br = [v for v in vozes if v.get("Locale") == "pt-BR" or "pt-BR" in (v.get("SecondaryLocaleList") or [])]
    print(f"Azure ({regiao}): {len(vozes)} vozes, {len(br)} falam pt-BR")
    for v in br:
        if v.get("Locale") == "pt-BR" or "DragonHD" in v["ShortName"]:
            print(f"  {v['ShortName']} | {v.get('Gender')} | {v.get('VoiceType')} | estilos {v.get('StyleList')}")
    return br


def gemini_wav(modelo: str, voz: str, texto: str, destino: Path) -> Path:
    chave = os.environ["GEMINI_API_KEY"]
    base = "https://generativelanguage.googleapis.com/v1beta"
    r = requests.post(f"{base}/interactions", headers={"x-goog-api-key": chave}, timeout=180, json={
        "model": modelo,
        "input": [{"type": "user_input", "content": [{
            "type": "text", "text": texto,
            "annotations": [{"type": "speech_metadata", "style": ESTILO}]}]}],
        "response_format": {"type": "audio"},
        "generation_config": {"speech_config": [{"voice": voz}]},
    })
    if r.status_code == 200:
        audios = [c for s in r.json().get("steps", []) if s.get("type") == "model_output"
                  for c in s.get("content", []) if c.get("type") == "audio"]
        if audios:
            destino.write_bytes(base64.b64decode(audios[-1]["data"]))
            return destino
    erro = f"interactions HTTP {r.status_code} {r.text[:300]}"
    # API antiga (generateContent), para os modelos 2.5
    r = requests.post(f"{base}/models/{modelo}:generateContent", params={"key": chave}, timeout=180, json={
        "contents": [{"parts": [{"text": f"{ESTILO}\n\n{texto}"}]}],
        "generationConfig": {"responseModalities": ["AUDIO"],
                             "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": voz}}}},
    })
    if r.status_code != 200:
        raise RuntimeError(f"{erro} | generateContent HTTP {r.status_code} {r.text[:300]}")
    parte = r.json()["candidates"][0]["content"]["parts"][0]["inlineData"]
    pcm = destino.with_suffix(".pcm")
    pcm.write_bytes(base64.b64decode(parte["data"]))
    subprocess.run(["ffmpeg", "-nostdin", "-loglevel", "error", "-y", "-f", "s16le", "-ar", "24000", "-ac", "1",
                    "-i", str(pcm), str(destino)], check=True)
    return destino


def vozes_gemini() -> list[str]:
    chave = os.environ["GEMINI_API_KEY"]
    achadas = []
    for params in ({"language_code": "pt-BR"}, {"languageCode": "pt-BR"}, {}):
        try:
            r = requests.get("https://generativelanguage.googleapis.com/v1beta/voices",
                             headers={"x-goog-api-key": chave}, params={**params, "pageSize": 200}, timeout=30)
        except requests.RequestException as e:
            print(f"Gemini voices: {e}")
            break
        if r.status_code != 200:
            print(f"Gemini voices {params}: HTTP {r.status_code} {r.text[:200]}")
            continue
        for v in r.json().get("voices", []):
            texto = json.dumps(v, ensure_ascii=False)
            if "pt-BR" in texto or "Portug" in texto or "Brazil" in texto:
                achadas.append(v)
        print(f"Gemini voices {params}: {len(r.json().get('voices', []))} vozes, {len(achadas)} em português")
        for v in achadas[:15]:
            print("  ", json.dumps(v, ensure_ascii=False)[:250])
        if achadas:
            break
    nomes = []
    for v in achadas:
        nome = v.get("voice") or v.get("name") or v.get("displayName")
        if nome:
            nomes.append(str(nome).split("/")[-1])
    return nomes


def gemini(modelo: str, voz: str, nome: str) -> None:
    pasta = SAIDA / "_trab"
    pasta.mkdir(parents=True, exist_ok=True)
    texto = " ".join(texto_para_fala(t) for t in ROTEIRO)
    try:
        mp3(gemini_wav(modelo, voz, texto, pasta / f"{nome}.wav"), nome)
    except Exception as e:  # noqa: BLE001
        print(f"FALHOU {nome}: {str(e)[:400]}")


def main() -> int:
    SAIDA.mkdir(parents=True, exist_ok=True)
    antonio = {"voz": "pt-BR-AntonioNeural", "velocidade": "+12%", "tom": "+3%"}
    azure(antonio, "01_hoje_antonio_cena_por_cena", continua=False)
    azure(antonio, "02_antonio_fala_corrida")
    azure({"voz": "pt-BR-AntonioNeural", "velocidade": "+6%", "tom": "+0%"}, "03_antonio_corrida_sem_tom")

    try:
        br = vozes_azure()
    except Exception as e:  # noqa: BLE001
        print(f"lista da Azure falhou: {e}")
        br = []
    nomes = {v["ShortName"]: v for v in br}
    n = 4
    for nome in ("pt-BR-MacerioMultilingualNeural", "pt-BR-ThalitaMultilingualNeural"):
        if nome in nomes or not br:
            azure({"voz": nome, "velocidade": "+8%", "tom": "+0%"}, f"{n:02d}_azure_{nome[6:-6]}")
            n += 1
    hd = [v["ShortName"] for v in br if "DragonHD" in v["ShortName"] and v.get("Gender") == "Male"]
    hd_br = [x for x in hd if x.startswith("pt-BR")] + [x for x in hd if not x.startswith("pt-BR")]
    for nome in hd_br[:3]:
        azure({"voz": nome}, f"{n:02d}_azure_hd_{nome.split(':')[0][6:]}")
        n += 1

    try:
        br_gemini = vozes_gemini()
    except Exception as e:  # noqa: BLE001
        print(f"lista do Gemini falhou: {e}")
        br_gemini = []
    candidatas = br_gemini[:2] + ["Fenrir", "Puck", "Charon"]
    for modelo in ("gemini-3.8-flash-tts", "gemini-2.5-flash-preview-tts"):
        antes = len(list(SAIDA.glob("*gemini*.mp3")))
        for voz in candidatas[:4]:
            gemini(modelo, voz, f"{n:02d}_gemini_{voz}_{modelo.split('-')[1]}")
            n += 1
            time.sleep(8)          # plano gratuito: poucos pedidos por minuto
        if len(list(SAIDA.glob("*gemini*.mp3"))) > antes:
            break
    print("arquivos:", sorted(p.name for p in SAIDA.glob("*.mp3")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
