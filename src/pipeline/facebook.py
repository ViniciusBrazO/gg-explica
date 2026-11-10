"""Publicação de Reels na Página do Facebook pela API oficial (Reels Publishing API).

Mesmo vídeo do Instagram, público diferente e sem trabalho a mais. Fluxo oficial:
1. POST graph.facebook.com/{v}/{page_id}/video_reels   upload_phase=start  -> video_id
2. POST rupload.facebook.com/video-upload/{v}/{video_id}  (arquivo, cabeçalhos offset e file_size)
3. POST graph.facebook.com/{v}/{page_id}/video_reels   upload_phase=finish, video_state=PUBLISHED

Variáveis no .env (por marca): FB_PAGE_ID_GG_EXPLICA e META_TOKEN_GG_EXPLICA (o token do usuário do
sistema; o kit pega o token da Página com ele) ou FB_PAGE_TOKEN_GG_EXPLICA (token de Página com
pages_show_list, pages_read_engagement e pages_manage_posts). Sem elas, o vídeo vai para o lote manual.
Limite da Meta: 30 Reels por API a cada 24 horas por Página.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import requests

GRAPH = "https://graph.facebook.com"
RUPLOAD = "https://rupload.facebook.com/video-upload"


class ErroFacebook(RuntimeError):
    pass


@dataclass
class CredenciaisFacebook:
    page_id: str
    token: str                   # token da Página; vazio = pegar com o token_sistema na hora de publicar
    versao: str = "v26.0"
    token_sistema: str = ""

    @classmethod
    def da_marca(cls, marca_id: str) -> Optional["CredenciaisFacebook"]:
        from .meta import token_meta
        chave = marca_id.upper()
        page = os.environ.get(f"FB_PAGE_ID_{chave}")
        token = os.environ.get(f"FB_PAGE_TOKEN_{chave}", "")
        sistema = "" if token else token_meta(marca_id)
        if not page or not (token or sistema):
            return None
        return cls(page, token, os.environ.get("GRAPH_API_VERSION", "v26.0"), sistema)

    def garantir_token(self, sessao=None) -> str:
        if not self.token:
            from .meta import ErroMeta, token_da_pagina
            try:
                self.token = token_da_pagina(self.page_id, self.token_sistema, sessao)
            except ErroMeta as e:
                raise ErroFacebook(str(e)) from None
        return self.token


def _checar(r) -> dict:
    try:
        dados = r.json()
    except ValueError:
        dados = {"texto": r.text[:500]}
    if r.status_code >= 400 or "error" in dados:
        raise ErroFacebook(f"HTTP {r.status_code}: {dados}")
    return dados


class PublicadorFacebook:
    def __init__(self, cred: CredenciaisFacebook, sessao=None):
        self.c = cred
        self.s = sessao or requests.Session()

    def publicar_reel(self, video: Path, descricao: str) -> dict:
        self.c.garantir_token(self.s)
        url = f"{GRAPH}/{self.c.versao}/{self.c.page_id}/video_reels"
        inicio = _checar(self.s.post(url, data={"upload_phase": "start", "access_token": self.c.token}, timeout=60))
        vid = inicio["video_id"]
        with open(video, "rb") as f:
            envio = _checar(self.s.post(f"{RUPLOAD}/{self.c.versao}/{vid}", data=f, timeout=600, headers={
                "Authorization": f"OAuth {self.c.token}", "offset": "0",
                "file_size": str(video.stat().st_size), "Content-Type": "application/octet-stream"}))
        if not envio.get("success"):
            raise ErroFacebook(f"envio do arquivo falhou: {envio}")
        fim = _checar(self.s.post(url, data={"upload_phase": "finish", "video_id": vid, "video_state": "PUBLISHED",
                                             "description": descricao, "access_token": self.c.token}, timeout=60))
        if not fim.get("success"):
            raise ErroFacebook(f"publicação não confirmada: {fim}")
        return {"media_id": vid, "permalink": f"https://www.facebook.com/reel/{vid}"}
