"""Aprovação pelo celular.

Modo automático (`telegram.aprovacao: automatica` em config/automacao.yaml, o padrão): o kit agenda
sozinho cada rascunho sem bloqueio e avisa no Telegram com os slides e dois botões, ✍️ Ajustar e
🗑 Cancelar, que valem até o post sair. Quando sai, chega o link. Resposta a esse aviso vira
orientação para os próximos posts (saida/telegram/orientacoes.md, lida pelo Claude).

Modo manual (`aprovacao: manual`): o kit manda cada prévia com três botões.

  ✅ Aprovar   -> renderiza a versão final (voz já em cache), agenda o Instagram e monta o lote do TikTok
  ✍️ Ajustar   -> você responde dizendo o que mudar; o Claude refaz e manda de novo
  🗑 Descartar -> o vídeo sai da pauta

Também avisa quando o radar acha notícia quente e quando alguma etapa automática falha.
Só responde ao seu chat (TELEGRAM_CHAT_ID). Configuração no .env:
  TELEGRAM_BOT_TOKEN=...   (crie o bot com o @BotFather)
  TELEGRAM_CHAT_ID=...     (rode `paginas telegram teste` depois de mandar um "oi" para o bot)
"""
from __future__ import annotations

import hashlib
import json
import os
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional

import requests

from .marca import RAIZ, carregar_marca
from .modelos import Pauta
from .qualidade import checar_pauta

PASTA = RAIZ / "saida" / "telegram"
ARQ_PENDENTES = PASTA / "pendentes.json"
ARQ_OFFSET = PASTA / "offset.txt"
MARCADOR_AJUSTE = "AJUSTE PEDIDO:"
ARQ_CHAT = RAIZ / "saida" / "telegram" / "chat_id.txt"
ARQ_ORIENTACOES = RAIZ / "saida" / "telegram" / "orientacoes.md"


def modo_aprovacao() -> str:
    from .radar import config
    return (config().get("telegram") or {}).get("aprovacao", "manual")


def guardar_orientacao(texto: str) -> None:
    ARQ_ORIENTACOES.parent.mkdir(parents=True, exist_ok=True)
    novo = not ARQ_ORIENTACOES.exists()
    with ARQ_ORIENTACOES.open("a", encoding="utf-8") as f:
        if novo:
            f.write("# Orientações do Vinicius (respostas no Telegram). Valem para todos os próximos posts.\n\n")
        f.write(f"- {datetime.now():%d/%m/%Y %H:%M}: {texto.strip()}\n")


def chat_salvo() -> str:
    """O chat do dono, gravado pelo `paginas telegram teste` (no modo nuvem dispensa o segredo)."""
    return ARQ_CHAT.read_text(encoding="utf-8").strip() if ARQ_CHAT.exists() else ""


class Telegram:
    def __init__(self, token: str, chat_id: str, sessao=None):
        self.base = f"https://api.telegram.org/bot{token}"
        self.chat_id = str(chat_id)
        self.s = sessao or requests.Session()

    @classmethod
    def do_ambiente(cls, sessao=None) -> Optional["Telegram"]:
        token = (os.environ.get("TELEGRAM_BOT_TOKEN") or "").strip()
        chat = (os.environ.get("TELEGRAM_CHAT_ID") or "").strip() or chat_salvo()
        return cls(token, chat, sessao) if token and chat else None

    def _chamar(self, metodo: str, **kw) -> dict:
        r = self.s.post(f"{self.base}/{metodo}", timeout=kw.pop("timeout", 60), **kw)
        dados = r.json()
        if not dados.get("ok"):
            raise RuntimeError(f"Telegram {metodo}: {dados.get('description', dados)}")
        return dados["result"]

    def texto(self, mensagem: str, **extra) -> dict:
        return self._chamar("sendMessage", data={"chat_id": self.chat_id, "text": mensagem[:4000], **extra})

    def video(self, arquivo: Path, legenda: str, botoes: list[list[dict]]) -> dict:
        leve = arquivo.with_name(arquivo.stem + "_tg.mp4")   # cópia leve feita na renderização
        arquivo = leve if leve.exists() else arquivo
        with open(arquivo, "rb") as f:
            return self._chamar("sendVideo", timeout=300,
                                data={"chat_id": self.chat_id, "caption": legenda[:1024], "supports_streaming": "true",
                                      "reply_markup": json.dumps({"inline_keyboard": botoes})},
                                files={"video": (arquivo.name, f, "video/mp4")})

    def video_por_link(self, url: str, legenda: str) -> dict:
        """O Telegram baixa o vídeo de um link público (até 20 MB): não depende do envio sair do servidor."""
        return self._chamar("sendVideo", timeout=120, data={"chat_id": self.chat_id, "video": url,
                                                             "caption": legenda[:1024], "supports_streaming": "true"})

    def documento(self, arquivo: Path, legenda: str = "") -> dict:
        with open(arquivo, "rb") as f:
            return self._chamar("sendDocument", timeout=300, data={"chat_id": self.chat_id, "caption": legenda[:1024]},
                                files={"document": (arquivo.name, f, "video/mp4")})

    def foto(self, arquivo: Path, legenda: str = "") -> dict:
        with open(arquivo, "rb") as f:
            return self._chamar("sendPhoto", timeout=120, data={"chat_id": self.chat_id, "caption": legenda[:1024]},
                                files={"photo": (arquivo.name, f, "image/jpeg")})

    def album(self, fotos: list[Path]) -> None:
        """Manda os slides de um carrossel (o Telegram agrupa de 2 a 10 fotos por mensagem)."""
        for i in range(0, len(fotos), 10):
            lote = fotos[i:i + 10]
            if len(lote) == 1:
                with open(lote[0], "rb") as f:
                    self._chamar("sendPhoto", timeout=120, data={"chat_id": self.chat_id},
                                 files={"photo": (lote[0].name, f, "image/jpeg")})
                continue
            abertos = [open(foto, "rb") for foto in lote]
            try:
                media = [{"type": "photo", "media": f"attach://f{k}"} for k in range(len(lote))]
                self._chamar("sendMediaGroup", timeout=300, data={"chat_id": self.chat_id, "media": json.dumps(media)},
                             files={f"f{k}": (foto.name, arq, "image/jpeg") for k, (foto, arq) in enumerate(zip(lote, abertos))})
            finally:
                for arq in abertos:
                    arq.close()

    def atualizacoes(self, offset: int, espera: int = 0) -> list[dict]:
        return self._chamar("getUpdates", timeout=espera + 30,
                            data={"offset": offset, "timeout": espera,
                                  "allowed_updates": json.dumps(["message", "callback_query"])})

    def responder_botao(self, callback_id: str, texto: str) -> None:
        self._chamar("answerCallbackQuery", data={"callback_query_id": callback_id, "text": texto[:190]})

    def tirar_botoes(self, message_id: int) -> None:
        self._chamar("editMessageReplyMarkup", data={"chat_id": self.chat_id, "message_id": message_id,
                                                     "reply_markup": json.dumps({"inline_keyboard": []})})


# ---------------------------------------------------------------- estado

def _carregar(arq: Path, padrao):
    return json.loads(arq.read_text(encoding="utf-8")) if arq.exists() else padrao


def _salvar(arq: Path, dados) -> None:
    arq.parent.mkdir(parents=True, exist_ok=True)
    arq.write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")


def _token(pauta: Path, video_id: str) -> str:
    return hashlib.sha1(f"{pauta.name}|{video_id}".encode()).hexdigest()[:10]


def _impressao(video) -> str:
    return hashlib.sha1(video.model_dump_json().encode()).hexdigest()[:12]


def pautas_de_trabalho() -> list[Path]:
    """Pautas de verdade (os exemplos e a demonstração ficam de fora)."""
    return sorted(p for p in (RAIZ / "pautas").glob("*.json")
                  if not p.name.startswith(("exemplo_", "demo_")))


# ---------------------------------------------------------------- envio das prévias

def enviar_para_aprovacao(tg: Telegram, dias_a_frente: int = 1, hoje: Optional[date] = None,
                          produzir=None) -> int:
    """Manda as prévias dos rascunhos de hoje até `dias_a_frente`. Reenvia só o que mudou."""
    if produzir is None:
        from .producao import produzir
    hoje = hoje or date.today()
    limite = hoje + timedelta(days=dias_a_frente)
    pendentes = _carregar(ARQ_PENDENTES, {})
    enviados = 0
    for arq in pautas_de_trabalho():
        pauta = Pauta.carregar(arq)
        marca = carregar_marca(pauta.marca)
        for v in pauta.videos:
            if v.status != "rascunho" or not hoje <= v.data <= limite:
                continue
            tok, imp = _token(arq, v.id), _impressao(v)
            anterior = pendentes.get(tok, {})
            ja_avisado = anterior.get("impressao") == imp and anterior.get("situacao") == "bloqueado"
            automatico = modo_aprovacao() == "automatica"
            esperando_ok = automatico and anterior.get("situacao") == "aguardando"   # prévia do modo manual
            if anterior.get("impressao") == imp and not ja_avisado and not esperando_ok:
                continue
            bloqueios, avisos = checar_pauta(marca, v)
            if MARCADOR_AJUSTE in (v.notas_revisao or ""):
                continue    # esperando o Claude refazer
            if bloqueios:
                if not ja_avisado:   # avisa uma vez; quando o bloqueio sumir, a prévia sai sozinha
                    tg.texto(f"⚠️ {v.id} ({v.data:%d/%m} {v.horario:%H:%M}) ainda não pode ir:\n- " + "\n- ".join(bloqueios))
                pendentes[tok] = {"pauta": str(arq), "video": v.id, "impressao": imp, "situacao": "bloqueado",
                                  "conferido": datetime.now().isoformat(timespec="minutes")}
                continue
            try:
                if automatico:
                    v.status = "aprovado"
                    r = produzir(marca, v, previa=False)
                    if r.arquivo is None:
                        v.status = "rascunho"
                        continue
                    pauta.salvar(arq)
                else:
                    r = produzir(marca, v, previa=True)
            except Exception as e:  # noqa: BLE001  (um vídeo com erro não segura os outros)
                v.status = "rascunho"
                print(f"  {v.id}: erro ao renderizar ({str(e)[:300]})")
                continue
            if r.arquivo is None:
                continue
            corpo = f"{marca.nome_serie(v.serie)} · {v.data:%d/%m} às {v.horario:%H:%M}"
            if automatico:
                reel = r.arquivo.is_dir() and (r.arquivo / "reel.mp4").exists()
                corpo = ("🗓️ Agendado, sai sozinho: " + (f"Reel às {v.horario:%H:%M} e carrossel 2 h depois"
                         if reel else f"{v.horario:%H:%M}") + f" de {v.data:%d/%m}.\n"
                         "Quer mudar algo? ✍️ Ajustar (o Claude refaz) ou 🗑 Cancelar, até a hora de sair.")
            links = sorted({c.fonte_url for c in v.cenas if c.fonte_url})
            if links:   # primeiro as fontes: a legenda do Telegram corta depois de 1024 caracteres
                corpo += "\n\nConfira as fontes:\n" + "\n".join(links)
            if avisos:
                corpo += "\n\nAvisos: " + "; ".join(avisos)
            corpo += f"\n\nLegenda do post:\n{r.legenda}"
            botoes = [[{"text": "✅ Aprovar", "callback_data": f"a|{tok}"},
                       {"text": "✍️ Ajustar", "callback_data": f"r|{tok}"},
                       {"text": "🗑 Descartar", "callback_data": f"d|{tok}"}]]
            if automatico:
                botoes = [[{"text": "✍️ Ajustar", "callback_data": f"r|{tok}"},
                           {"text": "🗑 Cancelar", "callback_data": f"c|{tok}"}]]
            if r.arquivo.is_dir():    # carrossel: os slides primeiro, depois o texto com os botões
                tg.album(sorted(r.arquivo.glob("*.jpg")))
                msg = tg.texto(corpo, reply_markup=json.dumps({"inline_keyboard": botoes}))
            else:
                try:
                    msg = tg.video(r.arquivo, corpo, botoes)
                except Exception as e:     # o vídeo já está na fila; sem a prévia, manda só o texto
                    print(f"  prévia em vídeo não foi ({str(e)[:80]}); mandando só o texto")
                    msg = tg.texto("🎬 (vídeo da prévia não carregou)\n" + corpo,
                                   reply_markup=json.dumps({"inline_keyboard": botoes}))
            pendentes[tok] = {"pauta": str(arq), "video": v.id, "impressao": _impressao(v),
                              "situacao": "agendado" if automatico else "aguardando",
                              "message_id": msg.get("message_id"), "enviado": datetime.now().isoformat()}
            enviados += 1
    _salvar(ARQ_PENDENTES, pendentes)
    return enviados


# ---------------------------------------------------------------- respostas

def _achar_video(info: dict):
    arq = Path(info["pauta"])
    pauta = Pauta.carregar(arq)
    video = next((v for v in pauta.videos if v.id == info["video"]), None)
    return arq, pauta, video


def processar_respostas(tg: Telegram, produzir=None) -> list[str]:
    """Lê os botões e mensagens desde a última vez e age. Devolve um resumo do que fez."""
    if produzir is None:
        from .producao import produzir
    offset = int(ARQ_OFFSET.read_text()) if ARQ_OFFSET.exists() else 0
    pendentes = _carregar(ARQ_PENDENTES, {})
    feito: list[str] = []
    for u in tg.atualizacoes(offset):
        offset = max(offset, u["update_id"] + 1)
        cb, msg = u.get("callback_query"), u.get("message")
        chat = str(((cb or {}).get("message") or msg or {}).get("chat", {}).get("id", ""))
        if chat != tg.chat_id:
            continue                      # só o seu chat manda no kit
        if cb:
            acao, _, tok = cb.get("data", "").partition("|")
            info = pendentes.get(tok)
            if not info:
                tg.responder_botao(cb["id"], "Não achei este vídeo (já foi tratado?)")
                continue
            arq, pauta, v = _achar_video(info)
            if v is None:
                tg.responder_botao(cb["id"], "O vídeo não está mais na pauta")
                continue
            if acao in ("r", "c") and info.get("situacao") == "agendado" and v.status in ("aprovado", "renderizado"):
                from .fila import cancelar
                cancelar(pauta.marca, v.id)                 # sai da fila antes de ir ao ar
                v.status = "rascunho" if acao == "r" else "descartado"
                pauta.salvar(arq)
                if acao == "c":
                    info["situacao"] = "descartado"
                    tg.responder_botao(cb["id"], "Cancelado: não vai ao ar")
                    if info.get("message_id"):
                        tg.tirar_botoes(info["message_id"])
                    feito.append(f"cancelado {v.id}")
                    continue
            elif v.status != "rascunho":      # prévia antiga de um post já aprovado, descartado ou publicado
                tg.responder_botao(cb["id"], f"Esse post já está {v.status}; nada mudou")
                continue
            marca = carregar_marca(pauta.marca)
            if acao == "a":
                v.status = "aprovado"
                r = produzir(marca, v, previa=False)
                if r.arquivo is None:
                    v.status = "rascunho"
                    tg.responder_botao(cb["id"], "Não deu para aprovar: " + r.pulado)
                    continue
                pauta.salvar(arq)
                info["situacao"] = "aprovado"
                tg.responder_botao(cb["id"], f"Aprovado. Instagram às {v.horario:%H:%M} de {v.data:%d/%m}")
                feito.append(f"aprovado {v.id}")
            elif acao == "r":
                info["situacao"] = "aguardando_nota"
                tg.responder_botao(cb["id"], "Me diga o que mudar")
                tg.texto(f"✍️ O que mudar em {v.id}? Responda com uma mensagem.")
                feito.append(f"ajuste pedido {v.id}")
            elif acao == "d":
                v.status = "descartado"
                pauta.salvar(arq)
                info["situacao"] = "descartado"
                tg.responder_botao(cb["id"], "Descartado")
                feito.append(f"descartado {v.id}")
            if info.get("message_id") and acao in ("a", "d"):
                tg.tirar_botoes(info["message_id"])
        elif msg and msg.get("text"):
            texto = msg["text"].strip()
            if texto.startswith("/fila"):
                from .fila import carregar
                linhas = [f"{i.quando[5:16].replace('T', ' ')} {i.status} {i.id}" for i in carregar()[-10:]]
                tg.texto("Fila do Instagram:\n" + ("\n".join(linhas) or "vazia"))
                continue
            esperando = [(t, i) for t, i in pendentes.items() if i.get("situacao") == "aguardando_nota"]
            if not esperando:
                guardar_orientacao(texto)
                tg.texto("Anotado ✅ Vale para os próximos posts. (Post que já saiu se edita no app: "
                         "a API do Instagram não muda post publicado.)")
                feito.append("orientação anotada")
                continue
            tok, info = esperando[-1]
            arq, pauta, v = _achar_video(info)
            if v is not None:
                v.notas_revisao = (v.notas_revisao + "\n" if v.notas_revisao else "") + f"{MARCADOR_AJUSTE} {texto}"
                pauta.salvar(arq)
                info["situacao"] = "ajustando"
                tg.texto(f"Anotado. O Claude refaz {v.id} e eu te mando a nova prévia.")
                feito.append(f"nota em {v.id}")
    _salvar(ARQ_PENDENTES, pendentes)
    ARQ_OFFSET.parent.mkdir(parents=True, exist_ok=True)
    ARQ_OFFSET.write_text(str(offset))
    return feito


def ha_ajustes_pendentes() -> bool:
    for arq in pautas_de_trabalho():
        if any(MARCADOR_AJUSTE in (v.notas_revisao or "") and v.status == "rascunho"
               for v in Pauta.carregar(arq).videos):
            return True
    return False
