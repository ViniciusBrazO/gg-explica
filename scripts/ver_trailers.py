"""Diagnóstico: abre a página de vídeos oficiais da Rockstar e lista os vídeos de GTA VI e os
endereços de mídia que o player oficial carrega (só leitura; não baixa nada)."""
import re
import sys

from playwright.sync_api import sync_playwright

PAGINAS = sys.argv[1:] or ["https://www.rockstargames.com/videos?game=VI", "https://www.rockstargames.com/VI"]

with sync_playwright() as p:
    nav = p.chromium.launch()
    pag = nav.new_page()
    midias = set()
    pag.on("request", lambda r: midias.add(r.url) if re.search(r"\.(mp4|m3u8|mpd)(\?|$)", r.url) else None)
    for url in PAGINAS:
        try:
            pag.goto(url, wait_until="networkidle", timeout=60000)
        except Exception as e:
            print("falhou", url, e)
            continue
        print("==", url, "|", pag.title())
        links = {a for a in pag.eval_on_selector_all("a[href]", "els => els.map(e => e.href)") if "/videos/" in a}
        for a in sorted(links)[:40]:
            print("  video:", a)
    alvo = next((a for a in sorted(links) if "/videos/" in a), None)
    if alvo:
        pag.goto(alvo, wait_until="networkidle", timeout=60000)
        pag.wait_for_timeout(8000)
        print("== player:", alvo)
    for m in sorted(midias)[:30]:
        print("  midia:", m[:200])
    nav.close()
