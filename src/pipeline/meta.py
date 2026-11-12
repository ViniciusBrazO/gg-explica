"""Um token só para a Meta: Instagram, Página do Facebook e hospedagem das imagens do carrossel.

O token do usuário do sistema (Configurações do negócio > Usuários do sistema > Gerar token, validade
"Nunca") fica no .env como META_TOKEN_<MARCA>, junto com FB_PAGE_ID_<MARCA>. A partir dele o kit
descobre sozinho:

- a conta do Instagram ligada à Página (GET /{page}?fields=instagram_business_account);
- o token da Página, para os Reels do Facebook (GET /{page}?fields=access_token);
- um link público para cada slide do carrossel: a imagem sobe para a Página como foto não publicada
  (não aparece para ninguém), o Instagram busca pelo link e o kit apaga a foto depois.

As variáveis antigas (IG_USER_ID_*, IG_TOKEN_*, FB_PAGE_TOKEN_*) continuam valendo e têm prioridade.
`paginas meta conferir --marca gg_explica` testa tudo sem publicar e sem mostrar o token.
"""
from __future__ import annotations

import os
import time
from dataclasses import dataclass
from pathlib import Path

import requests

GRAPH = "https://graph.facebook.com"


class ErroMeta(RuntimeError):
    pass


def versao() -> str:
    return os.environ.get("GRAPH_API_VERSION", "v26.0")


def token_meta(marca_id: str) -> str:
    """O token geral da marca: META_TOKEN_<MARCA> ou, no formato antigo, IG_TOKEN_<MARCA>."""
    chave = marca_id.upper()
    return os.environ.get(f"META_TOKEN_{chave}") or os.environ.get(f"IG_TOKEN_{chave}") or ""


def pagina_da_marca(marca_id: str) -> str:
    return os.environ.get(f"FB_PAGE_ID_{marca_id.upper()}", "")


def _checar(r: requests.Response) -> dict:
    try:
        dados = r.json()
    except ValueError:
        dados = {"texto": r.text[:500]}
    if r.status_code >= 400 or (isinstance(dados, dict) and "error" in dados):
        erro = dados.get("error", dados) if isinstance(dados, dict) else dados
        if isinstance(erro, dict):     # nunca repete o token na mensagem
            erro = {k: erro[k] for k in ("message", "type", "code", "error_subcode") if k in erro}
        raise ErroMeta(f"HTTP {r.status_code}: {erro}")
    return dados


_cache: dict[tuple[str, str], str] = {}


def _campo_da_pagina(page_id: str, token: str, campo: str, sessao: requests.Session | None = None) -> dict:
    s = sessao or requests.Session()
    return _checar(s.get(f"{GRAPH}/{versao()}/{page_id}", params={"fields": campo, "access_token": token},
                         timeout=30))


def ig_da_pagina(page_id: str, token: str, sessao: requests.Session | None = None) -> str:
    chave = (page_id, "ig")
    if chave not in _cache:
        dados = _campo_da_pagina(page_id, token, "instagram_business_account", sessao)
        conta = dados.get("instagram_business_account") or {}
        if not conta.get("id"):
            raise ErroMeta("a Página não tem conta do Instagram ligada (Configurações do negócio > Contas do "
                           "Instagram) ou o token não tem instagram_basic/pages_show_list")
        _cache[chave] = conta["id"]
    return _cache[chave]


def token_da_pagina(page_id: str, token: str, sessao: requests.Session | None = None) -> str:
    chave = (page_id, "token")
    if chave not in _cache:
        dados = _campo_da_pagina(page_id, token, "access_token", sessao)
        if not dados.get("access_token"):
            raise ErroMeta("o token não dá acesso à Página: atribua a Página ao usuário do sistema "
                           "(Configurações do negócio > Usuários do sistema > Atribuir ativos)")
        _cache[chave] = dados["access_token"]
    return _cache[chave]


def limpar_cache() -> None:
    _cache.clear()


@dataclass
class Hospedeiro:
    """Dá um link público a uma imagem local subindo-a como foto não publicada da Página."""
    page_id: str
    token_pagina: str
    sessao: requests.Session | None = None

    def __post_init__(self):
        self.s = self.sessao or requests.Session()
        self.enviadas: list[str] = []

    def hospedar(self, imagem: Path) -> str:
        with open(imagem, "rb") as f:
            foto = _checar(self.s.post(f"{GRAPH}/{versao()}/{self.page_id}/photos",
                                       data={"published": "false", "access_token": self.token_pagina},
                                       files={"source": (imagem.name, f, "image/jpeg")}, timeout=120))
        fid = foto["id"]
        self.enviadas.append(fid)
        dados = _checar(self.s.get(f"{GRAPH}/{versao()}/{fid}", params={
            "fields": "images", "access_token": self.token_pagina}, timeout=30))
        imagens = sorted(dados.get("images") or [], key=lambda x: x.get("width", 0), reverse=True)
        if not imagens:
            raise ErroMeta(f"a foto {fid} subiu sem link público")
        return imagens[0]["source"]

    def hospedar_video(self, video: Path, espera_s: int = 300) -> str:
        """Link público de um vídeo: sobe como vídeo NÃO publicado da Página (ninguém vê) e espera o
        Facebook gerar o arquivo. Caminho de reserva quando o envio direto ao Instagram falha."""
        with open(video, "rb") as f:
            v = _checar(self.s.post(f"https://graph-video.facebook.com/{versao()}/{self.page_id}/videos",
                                    data={"published": "false", "access_token": self.token_pagina},
                                    files={"source": (video.name, f, "video/mp4")}, timeout=600))
        vid = v["id"]
        self.enviadas.append(vid)
        limite = time.time() + espera_s
        while time.time() < limite:
            dados = _checar(self.s.get(f"{GRAPH}/{versao()}/{vid}", params={
                "fields": "source,status", "access_token": self.token_pagina}, timeout=30))
            if dados.get("source"):
                return dados["source"]
            time.sleep(10)
        raise ErroMeta(f"o vídeo {vid} não ficou pronto no Facebook em {espera_s} s")

    def limpar(self) -> None:
        """Apaga as fotos e vídeos não publicados depois que o Instagram já buscou os arquivos."""
        for fid in self.enviadas:
            try:
                self.s.delete(f"{GRAPH}/{versao()}/{fid}", params={"access_token": self.token_pagina}, timeout=30)
            except requests.RequestException:
                pass
        self.enviadas.clear()


def hospedeiro_da_marca(marca_id: str, sessao: requests.Session | None = None) -> Hospedeiro | None:
    """O hospedeiro da marca, ou None se faltar FB_PAGE_ID ou token (o carrossel vai para o lote)."""
    page, token = pagina_da_marca(marca_id), token_meta(marca_id)
    if not page or not (token or os.environ.get(f"FB_PAGE_TOKEN_{marca_id.upper()}")):
        return None
    token_pagina = os.environ.get(f"FB_PAGE_TOKEN_{marca_id.upper()}") or token_da_pagina(page, token, sessao)
    return Hospedeiro(page, token_pagina, sessao)


def pode_hospedar(marca_id: str) -> bool:
    """Sem chamar a rede: há o que é preciso para publicar carrossel pela API?"""
    return bool(pagina_da_marca(marca_id)) and bool(
        token_meta(marca_id) or os.environ.get(f"FB_PAGE_TOKEN_{marca_id.upper()}"))


def conferir(marca_id: str, sessao: requests.Session | None = None) -> list[str]:
    """Testa o acesso sem publicar nada. Devolve as linhas do relatório (sem o token)."""
    s = sessao or requests.Session()
    linhas = []
    token, page = token_meta(marca_id), pagina_da_marca(marca_id)
    chave = marca_id.upper()
    if not token:
        return [f"falta META_TOKEN_{chave} no .env"]
    eu = _checar(s.get(f"{GRAPH}/{versao()}/me", params={"fields": "id,name", "access_token": token}, timeout=30))
    linhas.append(f"token ok: {eu.get('name', '?')} ({eu.get('id')})")
    try:
        perms = _checar(s.get(f"{GRAPH}/{versao()}/me/permissions", params={"access_token": token}, timeout=30))
        dadas = sorted(x["permission"] for x in perms.get("data", []) if x.get("status") == "granted")
        linhas.append("permissões: " + ", ".join(dadas))
    except ErroMeta as e:
        linhas.append(f"permissões: não deu para ler ({e})")
    if not page:
        return linhas + [f"falta FB_PAGE_ID_{chave} no .env"]
    pagina = _campo_da_pagina(page, token, "name,instagram_business_account{id,username}", s)
    linhas.append(f"Página: {pagina.get('name')} ({page})")
    conta = pagina.get("instagram_business_account") or {}
    if conta:
        linhas.append(f"Instagram: @{conta.get('username')} ({conta.get('id')})")
        cota = _checar(s.get(f"{GRAPH}/{versao()}/{conta['id']}/content_publishing_limit",
                             params={"fields": "quota_usage,config", "access_token": token}, timeout=30))
        uso = (cota.get("data") or [{}])[0]
        limite = (uso.get("config") or {}).get("quota_total", "?")
        linhas.append(f"posts pela API nas últimas 24 h: {uso.get('quota_usage', 0)} de {limite}")
    else:
        linhas.append("Instagram: nenhuma conta ligada à Página")
    tp = token_da_pagina(page, token, s)
    linhas.append("token da Página: ok")
    # testa a hospedagem dos slides (foto não publicada na Página, apagada logo depois)
    import tempfile
    from PIL import Image
    with tempfile.TemporaryDirectory() as d:
        img = Path(d) / "teste.jpg"
        Image.new("RGB", (64, 64), (20, 20, 20)).save(img)
        h = Hospedeiro(page, tp, s)
        try:
            url = h.hospedar(img)
            linhas.append(f"hospedagem dos slides: ok ({url[:40]}...)")
        except ErroMeta as e:
            linhas.append(f"hospedagem dos slides: FALHOU ({e})")
        finally:
            h.limpar()
    return linhas
