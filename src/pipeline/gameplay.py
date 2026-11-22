"""Gameplay do Vinicius: da pasta do Google Drive aos cortes prontos para o roteiro (pedido de 22/11).

Fluxo (roda numa rodada pesada do kit, no GitHub Actions):
  1. procura vídeos novos na pasta "GG Gameplay" do Google Drive (API oficial, token OAuth do Vinicius);
  2. baixa a gravação e manda o original para a lixeira do Drive (some sozinho em 30 dias);
  3. faz uma cópia leve (360p, 2 quadros/s) e o Gemini assiste: devolve os melhores momentos com o tempo
     exato, sem história nem cena de cinema (spoiler);
  4. corta cada momento da gravação original em saida/cache/gameplay/ (fica no cache das rodadas);
  5. registra tudo em saida/gameplay/momentos.json. Depois, a tarefa `gameplay` do Claude escreve o
     roteiro curto de cada corte e o kit edita, narra e agenda como qualquer Reel.

Variáveis: YT_CLIENT_ID e YT_CLIENT_SECRET (o mesmo cliente OAuth do YouTube, com a Google Drive API
ativada) e GDRIVE_REFRESH_TOKEN (gerado uma vez com `paginas drive autorizar`). GEMINI_API_KEY para assistir.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

import requests

from .marca import RAIZ

DRIVE = "https://www.googleapis.com/drive/v3"
TOKEN = "https://oauth2.googleapis.com/token"
ESCOPO_DRIVE = "https://www.googleapis.com/auth/drive"
PASTA_CORTES = RAIZ / "saida" / "cache" / "gameplay"
PASTA_BRUTOS = RAIZ / "saida" / "gameplay_brutos"        # só durante a rodada (fora do cache)
ARQ_MOMENTOS = RAIZ / "saida" / "gameplay" / "momentos.json"
ARQ_ESTADO = RAIZ / "saida" / "gameplay" / "estado.json"
UPLOAD_GEMINI = "https://generativelanguage.googleapis.com/upload/v1beta/files"
API_GEMINI = "https://generativelanguage.googleapis.com/v1beta"

MIN_S, MAX_S = 10.0, 50.0          # corte com trecho de jogo: o Reel fica abaixo de 60 s
MAX_MOMENTOS_POR_GRAVACAO = 6
NOTA_MINIMA = 6


class ErroGameplay(RuntimeError):
    pass


def config() -> dict:
    from .radar import config as cfg
    return cfg().get("gameplay", {})


# ---------------------------------------------------------------- Google Drive

def credenciais() -> Optional[tuple[str, str, str]]:
    cid, segredo = os.environ.get("YT_CLIENT_ID"), os.environ.get("YT_CLIENT_SECRET")
    refresh = os.environ.get("GDRIVE_REFRESH_TOKEN")
    return (cid, segredo, refresh) if cid and segredo and refresh else None


def ligado() -> bool:
    return credenciais() is not None and bool(os.environ.get("GEMINI_API_KEY")) and config().get("ativo", True)


class Drive:
    def __init__(self, sessao=None):
        cred = credenciais()
        if cred is None:
            raise ErroGameplay("falta YT_CLIENT_ID, YT_CLIENT_SECRET ou GDRIVE_REFRESH_TOKEN")
        self.s = sessao or requests.Session()
        r = self.s.post(TOKEN, timeout=30, data={"client_id": cred[0], "client_secret": cred[1],
                                                 "refresh_token": cred[2], "grant_type": "refresh_token"})
        if r.status_code != 200:
            raise ErroGameplay(f"Google recusou o token do Drive: HTTP {r.status_code} {r.text[:200]}")
        self.s.headers["Authorization"] = f"Bearer {r.json()['access_token']}"

    def _get(self, caminho: str, **params) -> dict:
        r = self.s.get(f"{DRIVE}/{caminho}", params=params, timeout=60)
        if r.status_code != 200:
            raise ErroGameplay(f"Drive {caminho}: HTTP {r.status_code} {r.text[:200]}")
        return r.json()

    def pasta(self, nome: str) -> Optional[str]:
        nome_seguro = nome.replace("'", "\\'")
        achadas = self._get("files", q=f"name = '{nome_seguro}' and mimeType = "
                            "'application/vnd.google-apps.folder' and trashed = false",
                            fields="files(id,name)", pageSize=10)["files"]
        return achadas[0]["id"] if achadas else None

    def videos(self, pasta_id: str) -> list[dict]:
        return self._get("files", q=f"'{pasta_id}' in parents and trashed = false and mimeType contains 'video/'",
                         fields="files(id,name,size,createdTime,mimeType)", orderBy="createdTime",
                         pageSize=50)["files"]

    def baixar(self, arquivo: dict, destino: Path) -> Path:
        destino.parent.mkdir(parents=True, exist_ok=True)
        with self.s.get(f"{DRIVE}/files/{arquivo['id']}", params={"alt": "media"}, stream=True, timeout=600) as r:
            if r.status_code != 200:
                raise ErroGameplay(f"Drive não baixou {arquivo['name']}: HTTP {r.status_code}")
            with open(destino, "wb") as f:
                for bloco in r.iter_content(8 * 1024 * 1024):
                    f.write(bloco)
        return destino

    def para_lixeira(self, arquivo_id: str) -> None:
        """Lixeira, não exclusão: o Drive apaga sozinho em 30 dias e dá para recuperar até lá."""
        r = self.s.patch(f"{DRIVE}/files/{arquivo_id}", json={"trashed": True}, timeout=60)
        if r.status_code != 200:
            print(f"  Drive não mandou para a lixeira: HTTP {r.status_code} {r.text[:120]}")


def autorizar_drive(client_id: str, client_secret: str, abrir=None) -> str:
    """Mesmo login do `paginas youtube autorizar`, só que pedindo acesso ao Drive."""
    import webbrowser
    from .youtube import autorizar
    return autorizar(client_id, client_secret, abrir=abrir or webbrowser.open, escopo=ESCOPO_DRIVE)


# ---------------------------------------------------------------- estado

def _ler(arq: Path, padrao):
    try:
        return json.loads(arq.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return padrao


def _gravar(arq: Path, dados) -> None:
    arq.parent.mkdir(parents=True, exist_ok=True)
    arq.write_text(json.dumps(dados, ensure_ascii=False, indent=1), encoding="utf-8")


def ja_processados() -> set[str]:
    return set(_ler(ARQ_ESTADO, {}).get("processados", []))


def marcar_processado(arquivo_id: str) -> None:
    estado = _ler(ARQ_ESTADO, {})
    estado["processados"] = sorted(set(estado.get("processados", [])) | {arquivo_id})[-500:]
    _gravar(ARQ_ESTADO, estado)


def pendentes(drive: Optional[Drive] = None) -> list[dict]:
    """Gravações na pasta do Drive que o kit ainda não processou."""
    drive = drive or Drive()
    pasta = drive.pasta(config().get("pasta_drive", "GG Gameplay"))
    if not pasta:
        return []
    feitos = ja_processados()
    return [v for v in drive.videos(pasta) if v["id"] not in feitos]


# ---------------------------------------------------------------- Gemini assiste

@dataclass
class Momento:
    inicio: float
    fim: float
    nota: int
    tipo: str
    descricao: str
    por_que_prende: str = ""
    spoiler: bool = False


@dataclass
class Corte:
    id: str
    arquivo: str                 # caminho relativo do corte (vai em `midia` da cena)
    origem: str                  # nome da gravação no Drive
    duracao: float
    nota: int
    tipo: str
    descricao: str
    por_que_prende: str = ""
    criado_em: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))
    usado: bool = False


INSTRUCOES = """Você assiste gravações de gameplay de GTA 6 para a página GG Explica (Reels de 20 a 50 s no
Instagram, público brasileiro). Escolha os MELHORES momentos para virar Reel: ação (perseguição, fuga da
polícia, tiroteio, acrobacia de carro, explosão), coisa engraçada ou absurda (NPC, física, bug), lugar bonito
ou detalhe impressionante do mapa, dica útil (onde achar algo, como ganhar dinheiro, atalho), segredo ou
easter egg. Regras:
- NUNCA escolha cena de cinema (cutscene), diálogo de missão da história, menu, mapa aberto, tela de
  carregamento ou de pausa. Marque spoiler=true em qualquer coisa ligada à história principal.
- Cada momento tem de 10 a 50 segundos, começa já na ação (sem tempo morto) e termina num ponto natural.
- Nota de 1 a 10 = quanto aquilo prende alguém rolando o feed nos 2 primeiros segundos.
- Tempos em segundos desde o início do vídeo (número), conferidos no próprio vídeo.
Responda só JSON: {"momentos": [{"inicio": 0, "fim": 0, "nota": 0, "tipo": "acao|engracado|paisagem|dica|
segredo|bug", "descricao": "o que acontece, em português, 1 a 2 frases concretas", "por_que_prende": "o gancho
em até 10 palavras", "spoiler": false}]} com até 8 momentos, os melhores primeiro."""


def copia_leve(video: Path, destino: Path) -> Path:
    """360p, 2 quadros/s, áudio mono: cabe no Gemini (até 2 GB) e gasta poucos tokens; os tempos não mudam."""
    subprocess.run(["ffmpeg", "-nostdin", "-loglevel", "error", "-y", "-i", str(video),
                    "-vf", "fps=2,scale=-2:360", "-c:v", "libx264", "-preset", "veryfast", "-crf", "32",
                    "-c:a", "aac", "-ac", "1", "-b:a", "32k", str(destino)], check=True, timeout=3600)
    return destino


def _enviar_ao_gemini(arquivo: Path, sessao) -> dict:
    chave = os.environ["GEMINI_API_KEY"]
    tamanho = arquivo.stat().st_size
    r = sessao.post(UPLOAD_GEMINI, params={"key": chave}, timeout=60, headers={
        "X-Goog-Upload-Protocol": "resumable", "X-Goog-Upload-Command": "start",
        "X-Goog-Upload-Header-Content-Length": str(tamanho), "X-Goog-Upload-Header-Content-Type": "video/mp4",
        "Content-Type": "application/json"}, json={"file": {"display_name": arquivo.name}})
    url = r.headers.get("X-Goog-Upload-URL")
    if not url:
        raise ErroGameplay(f"Gemini não abriu o envio: HTTP {r.status_code} {r.text[:200]}")
    with open(arquivo, "rb") as f:
        r = sessao.post(url, data=f, timeout=1800, headers={
            "Content-Length": str(tamanho), "X-Goog-Upload-Offset": "0", "X-Goog-Upload-Command": "upload, finalize"})
    if r.status_code != 200:
        raise ErroGameplay(f"Gemini não recebeu o vídeo: HTTP {r.status_code} {r.text[:200]}")
    info = r.json()["file"]
    for _ in range(120):                       # processa o vídeo antes de deixar usar
        if info.get("state") == "ACTIVE":
            return info
        if info.get("state") == "FAILED":
            raise ErroGameplay("Gemini não conseguiu processar o vídeo")
        time.sleep(10)
        info = sessao.get(f"{API_GEMINI}/{info['name']}", params={"key": chave}, timeout=60).json()
    raise ErroGameplay("Gemini demorou demais para processar o vídeo")


def _apagar_do_gemini(info: dict, sessao) -> None:
    try:
        sessao.delete(f"{API_GEMINI}/{info['name']}", params={"key": os.environ["GEMINI_API_KEY"]}, timeout=60)
    except requests.RequestException:
        pass                                    # o Gemini apaga sozinho em 48 h


def ler_momentos(dados: dict, duracao_video: float) -> list[Momento]:
    """Confere o que o Gemini devolveu: tempo dentro do vídeo, duração entre 10 e 50 s, sem spoiler."""
    saida = []
    for m in dados.get("momentos", []):
        try:
            ini, fim, nota = float(m["inicio"]), float(m["fim"]), int(m.get("nota", 0))
        except (KeyError, TypeError, ValueError):
            continue
        if m.get("spoiler") or nota < NOTA_MINIMA or ini < 0 or fim > duracao_video + 1:
            continue
        if fim - ini > MAX_S:
            fim = ini + MAX_S
        if fim - ini < MIN_S:
            continue
        if any(not (fim <= o.inicio or ini >= o.fim) for o in saida):     # sem sobreposição
            continue
        saida.append(Momento(ini, fim, nota, str(m.get("tipo", "acao")), str(m.get("descricao", "")).strip(),
                             str(m.get("por_que_prende", "")).strip()))
    return sorted(saida, key=lambda x: -x.nota)[:MAX_MOMENTOS_POR_GRAVACAO]


def assistir(video: Path, duracao: float, sessao=None) -> list[Momento]:
    from .gemini import modelos_candidatos
    s = sessao or requests.Session()
    leve = copia_leve(video, video.with_name(video.stem + "_leve.mp4"))
    info = _enviar_ao_gemini(leve, s)
    try:
        ultimo = ""
        for modelo in [m for m in modelos_candidatos(config().get("modelo", "auto"), s) if "lite" not in m][:4]:
            r = s.post(f"{API_GEMINI}/models/{modelo}:generateContent", params={"key": os.environ["GEMINI_API_KEY"]},
                       timeout=900, json={
                           "systemInstruction": {"parts": [{"text": INSTRUCOES}]},
                           "contents": [{"role": "user", "parts": [
                               {"file_data": {"mime_type": "video/mp4", "file_uri": info["uri"]}},
                               {"text": f"Vídeo de {duracao / 60:.0f} min. Escolha os melhores momentos."}]}],
                           "generationConfig": {"temperature": 0.4, "responseMimeType": "application/json",
                                                "mediaResolution": "MEDIA_RESOLUTION_LOW"}})
            if r.status_code == 200:
                texto = r.json()["candidates"][0]["content"]["parts"][0]["text"]
                return ler_momentos(json.loads(texto), duracao)
            ultimo = f"{modelo}: HTTP {r.status_code} {r.text[:200]}"
            time.sleep(10)
        raise ErroGameplay(f"Gemini não assistiu: {ultimo}")
    finally:
        _apagar_do_gemini(info, s)
        leve.unlink(missing_ok=True)


# ---------------------------------------------------------------- cortes

def _slug(texto: str) -> str:
    import unicodedata
    t = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "_", t).strip("_")[:40] or "gravacao"


def cortar(video: Path, m: Momento, destino: Path) -> Path:
    """Corte em 1080p a 60 quadros, com o som do jogo (a montagem deixa mudo e põe a narração)."""
    destino.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["ffmpeg", "-nostdin", "-loglevel", "error", "-y", "-ss", f"{m.inicio:.2f}", "-i", str(video),
                    "-t", f"{m.fim - m.inicio:.2f}", "-vf", "scale=-2:1080", "-c:v", "libx264",
                    "-preset", "veryfast", "-crf", "19", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k",
                    "-movflags", "+faststart", str(destino)], check=True, timeout=900)
    return destino


def registrar(cortes: list[Corte]) -> None:
    todos = _ler(ARQ_MOMENTOS, [])
    todos.extend(asdict(c) for c in cortes)
    _gravar(ARQ_MOMENTOS, todos[-300:])


def cortes_livres() -> list[dict]:
    """Cortes ainda sem Reel, cujo arquivo existe (o cache das rodadas guarda por ~7 dias sem uso)."""
    return [c for c in _ler(ARQ_MOMENTOS, []) if not c.get("usado") and (RAIZ / c["arquivo"]).exists()]


def marcar_usados(pautas_dir: Path = RAIZ / "pautas") -> int:
    """Corte que já virou cena de alguma pauta não volta para o Claude."""
    usados = set()
    for arq in pautas_dir.glob("*.json"):
        texto = arq.read_text(encoding="utf-8")
        usados |= set(re.findall(r'saida/cache/gameplay/[^"]+\.mp4', texto))
    todos = _ler(ARQ_MOMENTOS, [])
    n = 0
    for c in todos:
        if not c.get("usado") and c["arquivo"] in usados:
            c["usado"], n = True, n + 1
    _gravar(ARQ_MOMENTOS, todos)
    return n


def registrar_falha(erro: str) -> int:
    """Gravação que falha 3 vezes (vídeo quebrado, cota do Gemini) sai da fila e avisa no Telegram."""
    estado = _ler(ARQ_ESTADO, {})
    falhas = estado.get("falhas", {})
    try:
        fila = pendentes()
    except Exception:  # noqa: BLE001
        fila = []
    if not fila:
        return 0
    atual = fila[0]
    n = falhas.get(atual["id"], 0) + 1
    falhas[atual["id"]] = n
    estado["falhas"] = falhas
    _gravar(ARQ_ESTADO, estado)
    if n >= 3:
        marcar_processado(atual["id"])
        try:
            from .telegram import Telegram
            tg = Telegram.do_ambiente()
            if tg:
                tg.texto(f"⚠️ Não consegui aproveitar a gravação \"{atual['name']}\" depois de 3 tentativas: "
                         f"{erro[:200]}. Ela continua no Drive; pode apagar ou mandar de novo.")
        except Exception:  # noqa: BLE001
            pass
    return n


def pode_pedir_roteiro(agora: Optional[datetime] = None, horas: int = 6) -> bool:
    """Cortes livres sem rascunho pedem roteiro ao Claude no máximo a cada 6 h (se ele falhar, não insiste
    de hora em hora gastando a rodada)."""
    ultima = _ler(ARQ_ESTADO, {}).get("ultimo_pedido_roteiro")
    agora = agora or datetime.now()
    return not ultima or (agora - datetime.fromisoformat(ultima)).total_seconds() >= horas * 3600


def marcar_pedido_roteiro() -> None:
    estado = _ler(ARQ_ESTADO, {})
    estado["ultimo_pedido_roteiro"] = datetime.now().isoformat(timespec="seconds")
    _gravar(ARQ_ESTADO, estado)


def precisa_roteiro() -> bool:
    return bool(cortes_livres()) and not ha_rascunho_de_gameplay() and pode_pedir_roteiro()


def ha_rascunho_de_gameplay(pautas_dir: Path = RAIZ / "pautas") -> bool:
    """Já tem Reel de gameplay esperando sair: não pede roteiro novo ainda (evita encher a fila)."""
    for arq in pautas_dir.glob("gameplay_*.json"):
        dados = _ler(arq, {})
        if any(v.get("status") in ("rascunho", "aprovado") for v in dados.get("videos", [])):
            return True
    return False


def processar(drive: Optional[Drive] = None, mostrar=print) -> int:
    """Uma gravação nova por rodada (cabe nos 55 min). Devolve quantos cortes saíram."""
    from .sonda import duracao as duracao_de
    drive = drive or Drive()
    fila = pendentes(drive)
    if not fila:
        return 0
    arquivo = fila[0]
    mostrar(f"gameplay: {arquivo['name']} ({int(arquivo.get('size', 0)) / 1e9:.1f} GB), {len(fila) - 1} na fila")
    bruto = drive.baixar(arquivo, PASTA_BRUTOS / _slug(arquivo["name"]) / "gravacao.mp4")
    try:
        dur = duracao_de(bruto)
        momentos = assistir(bruto, dur)
        base = f"{datetime.now():%Y%m%d}_{_slug(Path(arquivo['name']).stem)}"
        cortes = []
        for n, m in enumerate(momentos, 1):
            destino = PASTA_CORTES / f"{base}_{n:02d}.mp4"
            cortar(bruto, m, destino)
            cortes.append(Corte(id=f"{base}_{n:02d}", arquivo=str(destino.relative_to(RAIZ)).replace("\\", "/"),
                                origem=arquivo["name"], duracao=round(m.fim - m.inicio, 1), nota=m.nota,
                                tipo=m.tipo, descricao=m.descricao, por_que_prende=m.por_que_prende))
        registrar(cortes)
        marcar_processado(arquivo["id"])
        drive.para_lixeira(arquivo["id"])
        mostrar(f"gameplay: {len(cortes)} corte(s) de {arquivo['name']}")
        return len(cortes)
    finally:
        import shutil
        shutil.rmtree(bruto.parent, ignore_errors=True)
