"""Cliente mínimo da API do Gemini (Google AI Studio), plano gratuito.

GEMINI_API_KEY no ambiente (GitHub Secrets). O modelo é escolhido sozinho: o Flash mais novo que a
chave pode usar (`gemini.modelo: auto` em config/automacao.yaml), ou o nome fixo que estiver lá.
"""
from __future__ import annotations

import json
import os
import re
import time

import requests

API = "https://generativelanguage.googleapis.com/v1beta"


class ErroGemini(RuntimeError):
    pass


def disponivel() -> bool:
    return bool(os.environ.get("GEMINI_API_KEY"))


def _chave() -> str:
    chave = os.environ.get("GEMINI_API_KEY", "").strip()
    if not chave:
        raise ErroGemini("falta GEMINI_API_KEY")
    return chave


def _versao(nome: str) -> tuple:
    return tuple(int(x) for x in re.findall(r"\d+", nome)[:3]) or (0,)


def modelos_candidatos(preferido: str = "auto", sessao=None) -> list[str]:
    """Do melhor para o pior: Flash estáveis mais novos primeiro, depois prévias, depois Flash-Lite."""
    if preferido and preferido != "auto":
        return [preferido]
    s = sessao or requests.Session()
    r = s.get(f"{API}/models", params={"key": _chave(), "pageSize": 200}, timeout=30)
    if r.status_code != 200:
        raise ErroGemini(f"lista de modelos: HTTP {r.status_code} {r.text[:200]}")
    candidatos = []
    for m in r.json().get("models", []):
        nome = m.get("name", "").removeprefix("models/")
        if "generateContent" not in m.get("supportedGenerationMethods", []) or "flash" not in nome:
            continue
        if any(x in nome for x in ("image", "tts", "audio", "live", "thinking-exp", "embedding", "omni")):
            continue
        estavel = 0 if ("preview" in nome or "exp" in nome) else 1
        cheio = 0 if "lite" in nome else 1
        candidatos.append((cheio, estavel, _versao(nome), nome))
    if not candidatos:
        raise ErroGemini("nenhum modelo Flash disponível para esta chave")
    return [c[3] for c in sorted(candidatos, reverse=True)]


def escolher_modelo(preferido: str = "auto", sessao=None) -> str:
    return modelos_candidatos(preferido, sessao)[0]


def gerar_json(instrucoes: str, conteudo: str, modelo: str = "auto", temperatura: float = 0.8,
               tentativas: int = 2, sessao=None) -> dict:
    """Pede uma resposta em JSON. Repete em erro temporário (429/500/503) com espera crescente."""
    s = sessao or requests.Session()
    ultimo = ""
    todos = modelos_candidatos(modelo, s)
    cheios = [m for m in todos if "lite" not in m][:7]
    # modelo lotado: tenta o próximo; duas voltas nos modelos cheios antes de cair para o Flash-Lite
    for nome in cheios + cheios + [m for m in todos if "lite" in m][:3]:
        corpo = {
            "systemInstruction": {"parts": [{"text": instrucoes}]},
            "contents": [{"role": "user", "parts": [{"text": conteudo}]}],
            "generationConfig": {"temperature": temperatura, "responseMimeType": "application/json"},
        }
        for k in range(tentativas):
            r = s.post(f"{API}/models/{nome}:generateContent", params={"key": _chave()}, json=corpo, timeout=180)
            if r.status_code in (429, 500, 503):
                ultimo = f"{nome}: HTTP {r.status_code}: {r.text[:200]}"
                time.sleep(6 * (k + 1))
                continue
            if r.status_code == 404:
                ultimo = f"{nome}: não disponível"
                break
            if r.status_code != 200:
                raise ErroGemini(f"{nome}: HTTP {r.status_code}: {r.text[:500]}")
            dados = r.json()
            try:
                texto = "".join(p.get("text", "") for p in dados["candidates"][0]["content"]["parts"])
            except (KeyError, IndexError):
                ultimo = f"{nome}: resposta sem texto"
                continue
            texto = re.sub(r"^```(?:json)?\s*|\s*```$", "", texto.strip())
            try:
                resultado = json.loads(texto)
                if isinstance(resultado, list):
                    resultado = {"videos": resultado}
                print(f"(redator: {nome})")
                return resultado
            except json.JSONDecodeError as e:
                ultimo = f"{nome}: JSON inválido ({e})"
                corpo["contents"].append({"role": "model", "parts": [{"text": texto}]})
                corpo["contents"].append({"role": "user", "parts": [{"text": "Responda só com JSON válido, sem texto fora."}]})
    raise ErroGemini(f"o Gemini não respondeu direito: {ultimo}")
