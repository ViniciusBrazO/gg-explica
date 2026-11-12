"""Diagnóstico: os vídeos de GTA VI estão no CDN de vídeos da Rockstar? E como a página os toca?"""
import subprocess

from playwright.sync_api import sync_playwright

for vid in ("55kss26g", "76orsa95", "rk721912", "cpys7u21", "rkoCtr1r"):
    for q in ("2160p", "1080p", "720p"):
        url = f"https://videos-rockstargames-com.akamaized.net/v4/{vid}/flv/en-us-{q}.mp4"
        r = subprocess.run(["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}", "-r", "0-1023", url],
                           capture_output=True, text=True)
        print(vid, q, r.stdout)
with sync_playwright() as p:
    b = p.chromium.launch()
    g = b.new_page()
    g.goto("https://www.rockstargames.com/videos/76orsa95", wait_until="networkidle", timeout=60000)
    g.wait_for_timeout(5000)
    for f in g.frames:
        print("frame:", f.url[:150])
    print("iframes:", g.eval_on_selector_all("iframe", "e => e.map(x => x.src)"))
    print("videos:", g.eval_on_selector_all("video", "e => e.map(x => x.currentSrc || x.src)"))
    b.close()
