"""Publicação de Reels pela API oficial do Instagram (Graph API, login do Facebook para empresas).

Fluxo oficial com envio de arquivo local (upload resumível):
1. cria o contêiner do Reel   POST graph.facebook.com/{v}/{ig_user}/media  (upload_type=resumable)
2. envia o arquivo            POST rupload.facebook.com/ig-api-upload/{v}/{contêiner}
3. espera o processamento     GET  graph.facebook.com/{v}/{contêiner}?fields=status_code
4. publica                    POST graph.facebook.com/{v}/{ig_user}/media_publish?creation_id=...

Carrossel (até 10 imagens): cada slide ganha um link público pelo `meta.Hospedeiro` (foto não
publicada da Página), vira um item `is_carousel_item`, e o contêiner CAROUSEL é publicado.

Variáveis de ambiente por marca (ex.: GG_EXPLICA):
  META_TOKEN_GG_EXPLICA + FB_PAGE_ID_GG_EXPLICA  (o kit descobre a conta do Instagram pela Página)
  ou, no formato antigo, IG_USER_ID_GG_EXPLICA + IG_TOKEN_GG_EXPLICA
Opcional: GRAPH_API_VERSION (padrão v26.0)
"""
from __future__ import annotations

import os
import time
from dataclasses import dataclass
from pathlib import Path

import requests

GRAPH = "https://graph.facebook.com"
RUPLOAD = "https://rupload.facebook.com/ig-api-upload"


class ErroInstagram(RuntimeError):
    pass


@dataclass
class Credenciais:
    ig_user_id: str
    token: str
    versao: str = "v26.0"

    @classmethod
    def da_marca(cls, marca_id: str) -> "Credenciais":
        from .meta import ErroMeta, ig_da_pagina, pagina_da_marca, token_meta
        chave = marca_id.upper()
        token = token_meta(marca_id)
        if not token:
            raise ErroInstagram(f"falta META_TOKEN_{chave} (ou IG_TOKEN_{chave}) no .env")
        ig = os.environ.get(f"IG_USER_ID_{chave}")
        if not ig:
            pagina = pagina_da_marca(marca_id)
            if not pagina:
                raise ErroInstagram(f"falta FB_PAGE_ID_{chave} (ou IG_USER_ID_{chave}) no .env")
            try:
                ig = ig_da_pagina(pagina, token)
            except ErroMeta as e:
                raise ErroInstagram(str(e)) from None
        return cls(ig, token, os.environ.get("GRAPH_API_VERSION", "v26.0"))


def _checar(r: requests.Response) -> dict:
    try:
        dados = r.json()
    except ValueError:
        dados = {"texto": r.text[:500]}
    if r.status_code >= 400 or "error" in dados:
        raise ErroInstagram(f"HTTP {r.status_code}: {dados}")
    return dados


class Publicador:
    def __init__(self, cred: Credenciais, sessao: requests.Session | None = None, espera_s: float = 10):
        self.c = cred
        self.s = sessao or requests.Session()
        self.espera_s = espera_s

    def _url(self, caminho: str) -> str:
        return f"{GRAPH}/{self.c.versao}/{caminho}"

    def cota(self) -> dict:
        r = self.s.get(self._url(f"{self.c.ig_user_id}/content_publishing_limit"),
                       params={"fields": "quota_usage,config", "access_token": self.c.token}, timeout=30)
        return _checar(r)

    def _esperar(self, cid: str, limite_espera_s: int) -> None:
        inicio = time.monotonic()
        while True:
            st = _checar(self.s.get(self._url(cid), params={
                "fields": "status_code,status", "access_token": self.c.token}, timeout=30))
            codigo = st.get("status_code")
            if codigo in ("FINISHED", "PUBLISHED"):
                return
            if codigo in ("ERROR", "EXPIRED"):
                raise ErroInstagram(f"processamento falhou: {st}")
            if time.monotonic() - inicio > limite_espera_s:
                raise ErroInstagram(f"processamento demorou demais (último status: {st})")
            time.sleep(self.espera_s)

    def _publicar(self, cid: str) -> dict:
        pub = _checar(self.s.post(self._url(f"{self.c.ig_user_id}/media_publish"), data={
            "creation_id": cid, "access_token": self.c.token}, timeout=60))
        mid = pub["id"]
        link = _checar(self.s.get(self._url(mid), params={
            "fields": "permalink", "access_token": self.c.token}, timeout=30)).get("permalink", "")
        return {"media_id": mid, "permalink": link, "container_id": cid}

    def publicar_carrossel(self, imagens: list[Path], legenda: str, hospedeiro,
                           limite_espera_s: int = 300) -> dict:
        """Publica de 2 a 10 imagens como um post. `hospedeiro.hospedar(caminho)` devolve o link público
        de cada uma; `hospedeiro.limpar()` roda no fim, publicado ou não."""
        if not 2 <= len(imagens) <= 10:
            raise ErroInstagram(f"carrossel precisa de 2 a 10 imagens (tem {len(imagens)})")
        try:
            filhos = []
            for img in imagens:
                url = hospedeiro.hospedar(img)
                filho = _checar(self.s.post(self._url(f"{self.c.ig_user_id}/media"), data={
                    "image_url": url, "is_carousel_item": "true", "access_token": self.c.token}, timeout=60))
                filhos.append(filho["id"])
            for f in filhos:
                self._esperar(f, limite_espera_s)
            cont = _checar(self.s.post(self._url(f"{self.c.ig_user_id}/media"), data={
                "media_type": "CAROUSEL", "children": ",".join(filhos), "caption": legenda,
                "access_token": self.c.token}, timeout=60))
            self._esperar(cont["id"], limite_espera_s)
            return self._publicar(cont["id"])
        finally:
            hospedeiro.limpar()

    def publicar_reel(self, video: Path, legenda: str, capa_ms: int = 600,
                      no_feed: bool = True, limite_espera_s: int = 900, capa_url: str = "") -> dict:
        tamanho = video.stat().st_size
        dados = {"media_type": "REELS", "upload_type": "resumable", "caption": legenda,
                 "share_to_feed": "true" if no_feed else "false", "access_token": self.c.token}
        if capa_url:
            dados["cover_url"] = capa_url
        else:
            dados["thumb_offset"] = str(capa_ms)
        cont = _checar(self.s.post(self._url(f"{self.c.ig_user_id}/media"), data=dados, timeout=60))
        cid = cont["id"]

        with open(video, "rb") as f:
            up = _checar(self.s.post(f"{RUPLOAD}/{self.c.versao}/{cid}", headers={
                "Authorization": f"OAuth {self.c.token}", "offset": "0", "file_size": str(tamanho),
            }, data=f, timeout=600))
        if not up.get("success", False):
            raise ErroInstagram(f"envio do arquivo falhou: {up}")

        self._esperar(cid, limite_espera_s)
        return self._publicar(cid)
