"""Publicação de Shorts pela API oficial do YouTube (Data API v3, upload resumível).

O mesmo vídeo vertical do Reel vira Short. Fluxo oficial:
1. troca o refresh token por um token de acesso    POST oauth2.googleapis.com/token
2. abre a sessão de envio com os metadados          POST googleapis.com/upload/youtube/v3/videos?uploadType=resumable
3. envia o arquivo para o endereço devolvido        PUT  <Location>

Página da API conferida em 9/11/2026 (atualizada em 15/10/2026): o envio custa 1 unidade da cota
"Video Uploads" (100 envios por dia) e vídeo enviado por projeto não verificado não fica mais preso
no modo privado.

Variáveis no .env: YT_CLIENT_ID e YT_CLIENT_SECRET (um cliente OAuth "App para computador" no Google
Cloud, com a YouTube Data API v3 ativada) e YT_REFRESH_TOKEN_<MARCA>, que o `paginas youtube autorizar
--marca <id>` gera com o login do canal. Sem elas, o vídeo vai para o lote manual do YouTube Studio.
Deixe a tela de consentimento OAuth "Em produção": em modo de teste o refresh token vence em 7 dias.
"""
from __future__ import annotations

import json
import os
import secrets
import webbrowser
from dataclasses import dataclass
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Optional
from urllib.parse import parse_qs, urlencode, urlparse

import requests

TOKEN = "https://oauth2.googleapis.com/token"
AUTORIZAR = "https://accounts.google.com/o/oauth2/v2/auth"
UPLOAD = "https://www.googleapis.com/upload/youtube/v3/videos"
ESCOPO = "https://www.googleapis.com/auth/youtube.upload"
CATEGORIA_GAMES = "20"
IDIOMAS = {"pt": "pt-BR", "es": "es-419"}


class ErroYouTube(RuntimeError):
    pass


@dataclass
class CredenciaisYouTube:
    client_id: str
    client_secret: str
    refresh_token: str

    @classmethod
    def da_marca(cls, marca_id: str) -> Optional["CredenciaisYouTube"]:
        cid, segredo = os.environ.get("YT_CLIENT_ID"), os.environ.get("YT_CLIENT_SECRET")
        refresh = os.environ.get(f"YT_REFRESH_TOKEN_{marca_id.upper()}")
        return cls(cid, segredo, refresh) if cid and segredo and refresh else None


def _checar(r) -> dict:
    try:
        dados = r.json()
    except ValueError:
        dados = {"texto": r.text[:500]}
    if r.status_code >= 400 or "error" in dados:
        raise ErroYouTube(f"HTTP {r.status_code}: {dados}")
    return dados


def _limpar(texto: str) -> str:
    """O YouTube recusa < e > no título e na descrição."""
    return texto.replace("<", "‹").replace(">", "›")


def titulo_da_legenda(legenda: str, limite: int = 100) -> str:
    """Primeira linha de verdade da legenda (pula o aviso #publi), sem hashtag solta, até 100 caracteres."""
    for linha in legenda.splitlines():
        linha = linha.strip()
        if not linha or linha.lower().startswith("#publi") or linha.startswith("#"):
            continue
        linha = _limpar(linha)
        if len(linha) <= limite:
            return linha
        return linha[:limite - 1].rsplit(" ", 1)[0].rstrip(",.;:") + "…"
    return "Short"


def metadados(titulo: str, descricao: str, idioma: str = "pt", tags: list[str] | None = None,
              publicar_em: datetime | None = None, sintetico: bool = True) -> dict:
    status = {"privacyStatus": "public", "selfDeclaredMadeForKids": False, "containsSyntheticMedia": sintetico}
    if publicar_em is not None:      # programado: o YouTube exige privado + publishAt (UTC, ISO 8601)
        status.update(privacyStatus="private", publishAt=publicar_em.astimezone().isoformat())
    return {
        "snippet": {"title": _limpar(titulo)[:100], "description": _limpar(descricao)[:4900],
                    "categoryId": CATEGORIA_GAMES, "tags": [t.lstrip("#") for t in (tags or [])][:15],
                    "defaultLanguage": IDIOMAS.get(idioma, idioma),
                    "defaultAudioLanguage": IDIOMAS.get(idioma, idioma)},
        "status": status,
    }


class PublicadorYouTube:
    def __init__(self, cred: CredenciaisYouTube, sessao=None):
        self.c = cred
        self.s = sessao or requests.Session()

    def _token(self) -> str:
        dados = _checar(self.s.post(TOKEN, timeout=30, data={
            "client_id": self.c.client_id, "client_secret": self.c.client_secret,
            "refresh_token": self.c.refresh_token, "grant_type": "refresh_token"}))
        return dados["access_token"]

    def publicar_short(self, video: Path, legenda: str, idioma: str = "pt", tags: list[str] | None = None,
                       publicar_em: datetime | None = None) -> dict:
        token = self._token()
        corpo = metadados(titulo_da_legenda(legenda), legenda, idioma, tags, publicar_em)
        tamanho = video.stat().st_size
        r = self.s.post(f"{UPLOAD}?{urlencode({'uploadType': 'resumable', 'part': 'snippet,status'})}",
                        data=json.dumps(corpo), timeout=60, headers={
                            "Authorization": f"Bearer {token}", "Content-Type": "application/json; charset=UTF-8",
                            "X-Upload-Content-Type": "video/mp4", "X-Upload-Content-Length": str(tamanho)})
        if r.status_code >= 400:
            _checar(r)
        destino = r.headers.get("Location")
        if not destino:
            raise ErroYouTube(f"o YouTube não devolveu o endereço de envio (HTTP {r.status_code})")
        with open(video, "rb") as f:
            enviado = _checar(self.s.put(destino, data=f, timeout=900, headers={
                "Authorization": f"Bearer {token}", "Content-Type": "video/mp4", "Content-Length": str(tamanho)}))
        vid = enviado.get("id")
        if not vid:
            raise ErroYouTube(f"envio sem id de vídeo: {enviado}")
        return {"media_id": vid, "permalink": f"https://youtube.com/shorts/{vid}"}


# ---------------------------------------------------------------- autorização (uma vez por canal)

def autorizar(client_id: str, client_secret: str, porta: int = 8765, abrir=webbrowser.open,
              sessao=None) -> str:
    """Abre o login do Google no navegador, recebe o código em http://127.0.0.1:<porta> e devolve
    o refresh token. Rode uma vez por canal e cole o resultado no .env."""
    estado = secrets.token_urlsafe(16)
    retorno = f"http://127.0.0.1:{porta}"
    url = AUTORIZAR + "?" + urlencode({
        "client_id": client_id, "redirect_uri": retorno, "response_type": "code", "scope": ESCOPO,
        "access_type": "offline", "prompt": "consent", "state": estado})
    recebido: dict = {}

    class Receptor(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802 (nome exigido pelo http.server)
            q = parse_qs(urlparse(self.path).query)
            recebido.update({k: v[0] for k, v in q.items()})
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write("<h2>Pronto. Pode fechar esta aba e voltar ao terminal.</h2>".encode("utf-8"))

        def log_message(self, *args):
            pass

    with HTTPServer(("127.0.0.1", porta), Receptor) as servidor:
        print("Abrindo o login do Google. Se não abrir, copie este endereço no navegador:\n" + url)
        abrir(url)
        while "code" not in recebido and "error" not in recebido:
            servidor.handle_request()
    if recebido.get("state") != estado:
        raise ErroYouTube("resposta do login não confere (state diferente); tente de novo")
    if "error" in recebido:
        raise ErroYouTube(f"login recusado: {recebido['error']}")
    dados = _checar((sessao or requests).post(TOKEN, timeout=30, data={
        "code": recebido["code"], "client_id": client_id, "client_secret": client_secret,
        "redirect_uri": retorno, "grant_type": "authorization_code"}))
    if "refresh_token" not in dados:
        raise ErroYouTube("o Google não mandou refresh token; remova o acesso do app na conta e rode de novo")
    return dados["refresh_token"]
