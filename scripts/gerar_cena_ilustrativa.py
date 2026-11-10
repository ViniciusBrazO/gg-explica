"""Gera assets/exemplos/cena_ilustrativa.mp4: uma cena animada ORIGINAL (não é do jogo),
no clima de cidade praiana ao pôr do sol, só para demonstrar os formatos com trecho de jogo
enquanto você ainda não tem as suas gravações. Troque pelas suas capturas em clipes/.

Uso:  python scripts/gerar_cena_ilustrativa.py
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

from playwright.sync_api import sync_playwright

RAIZ = Path(__file__).resolve().parents[1]
SAIDA = RAIZ / "assets" / "exemplos" / "cena_ilustrativa.mp4"
L, A, FPS, SEG = 1280, 720, 30, 8

PAGINA = """<!doctype html><html><body style="margin:0;background:#000">
<canvas id="c" width="__L__" height="__A__"></canvas>
<script>
const c = document.getElementById('c'), g = c.getContext('2d'), W = c.width, H = c.height;
function rnd(s) { const x = Math.sin(s * 999.13) * 43758.5453; return x - Math.floor(x); }
const predios = [];
for (let i = 0, x = -80; x < W * 1.6; i++) {
  const w = 40 + rnd(i) * 70, h = 90 + rnd(i + 50) * 230;
  predios.push({x, w, h, cor: rnd(i + 7) > .5 ? '#2a1640' : '#1d1030'}); x += w + 6;
}
const palmeiras = [0.06, 0.24, 0.71, 0.93].map((p, i) => ({x: p, h: 260 + rnd(i + 3) * 120}));
function palmeira(x, base, h, lado) {
  g.strokeStyle = '#0b0712'; g.fillStyle = '#0b0712'; g.lineWidth = 14; g.lineCap = 'round';
  g.beginPath(); g.moveTo(x, base); g.quadraticCurveTo(x + lado * 40, base - h * .5, x + lado * 18, base - h); g.stroke();
  const tx = x + lado * 18, ty = base - h;
  for (let k = 0; k < 7; k++) {
    const a = -Math.PI / 2 + (k - 3) * 0.48;
    g.beginPath(); g.moveTo(tx, ty);
    g.quadraticCurveTo(tx + Math.cos(a) * 90, ty + Math.sin(a) * 60 - 20, tx + Math.cos(a) * 150, ty + Math.sin(a) * 40 + 60);
    g.lineWidth = 9; g.stroke();
  }
}
window.quadro = (t) => {
  const cam = t * 26;                       // câmera andando devagar para a direita
  const ceu = g.createLinearGradient(0, 0, 0, H * .62);
  ceu.addColorStop(0, '#1b0b3a'); ceu.addColorStop(.45, '#7a1f6e'); ceu.addColorStop(.8, '#ff6a3d'); ceu.addColorStop(1, '#ffb347');
  g.fillStyle = ceu; g.fillRect(0, 0, W, H * .62);
  // sol listrado
  const sx = W * .58 - cam * .15, sy = H * .5;
  const sol = g.createLinearGradient(0, sy - 150, 0, sy + 60);
  sol.addColorStop(0, '#ffe66d'); sol.addColorStop(1, '#ff4d8d');
  g.fillStyle = sol; g.beginPath(); g.arc(sx, sy, 150, Math.PI, 0); g.fill();
  g.fillStyle = '#7a1f6e';
  for (let k = 0; k < 6; k++) g.fillRect(sx - 160, sy - 60 + k * 14, 320, 3 + k * 1.4);
  // prédios com janelas acesas
  for (const [i, p] of predios.entries()) {
    const x = p.x - cam * .45, base = H * .62;
    g.fillStyle = p.cor; g.fillRect(x, base - p.h, p.w, p.h);
    for (let jy = base - p.h + 12; jy < base - 10; jy += 16)
      for (let jx = x + 8; jx < x + p.w - 8; jx += 13)
        if (rnd(i * 31 + jx * .7 + jy) > .62) { g.fillStyle = rnd(jx + jy) > .5 ? '#ffd27a' : '#7ef0ff'; g.fillRect(jx, jy, 6, 8); }
  }
  // mar com reflexo
  const mar = g.createLinearGradient(0, H * .62, 0, H);
  mar.addColorStop(0, '#3a1458'); mar.addColorStop(1, '#0d0820');
  g.fillStyle = mar; g.fillRect(0, H * .62, W, H * .38);
  for (let k = 0; k < 26; k++) {
    const y = H * .64 + k * 9, larg = 260 - k * 7 + Math.sin(t * 3 + k) * 20;
    g.fillStyle = `rgba(255,170,90,${0.55 - k * .018})`; g.fillRect(sx - larg / 2 + Math.sin(t * 2 + k) * 8, y, larg, 2);
  }
  // avenida da orla com carro
  g.fillStyle = '#120a1c'; g.fillRect(0, H * .8, W, H * .2);
  g.fillStyle = '#ff2fa0'; g.fillRect(0, H * .8, W, 4);
  for (let k = 0; k < 14; k++) { g.fillStyle = '#ffd27a'; g.fillRect(((k * 120 - cam * 2.2) % (W + 120) + W + 120) % (W + 120) - 60, H * .9, 50, 4); }
  const carX = ((t * 190) % (W + 300)) - 150, carY = H * .84;
  g.fillStyle = '#0b0712'; g.beginPath(); g.roundRect(carX, carY, 170, 34, 10); g.fill();
  g.beginPath(); g.roundRect(carX + 40, carY - 22, 80, 26, 10); g.fill();
  g.fillStyle = '#ffe66d'; g.fillRect(carX + 164, carY + 10, 10, 8);
  const farol = g.createLinearGradient(carX + 170, 0, carX + 330, 0);
  farol.addColorStop(0, 'rgba(255,230,109,.55)'); farol.addColorStop(1, 'rgba(255,230,109,0)');
  g.fillStyle = farol; g.beginPath(); g.moveTo(carX + 172, carY + 12); g.lineTo(carX + 330, carY - 6); g.lineTo(carX + 330, carY + 34); g.fill();
  g.fillStyle = '#ff2f4a'; g.fillRect(carX - 2, carY + 10, 6, 8);
  // palmeiras em primeiro plano
  for (const [i, p] of palmeiras.entries()) palmeira(((p.x * W - cam * 1.4) % (W + 300) + W + 300) % (W + 300) - 150, H, p.h, i % 2 ? -1 : 1);
  // vinheta
  const v = g.createRadialGradient(W / 2, H / 2, H * .3, W / 2, H / 2, W * .75);
  v.addColorStop(0, 'rgba(0,0,0,0)'); v.addColorStop(1, 'rgba(0,0,0,.45)');
  g.fillStyle = v; g.fillRect(0, 0, W, H);
};
</script></body></html>""".replace("__L__", str(L)).replace("__A__", str(A))


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        (tmp / "cena.html").write_text(PAGINA, encoding="utf-8")
        with sync_playwright() as p:
            nav = p.chromium.launch()
            pg = nav.new_page(viewport={"width": L, "height": A})
            pg.goto((tmp / "cena.html").as_uri())
            canvas = pg.locator("#c")
            for i in range(FPS * SEG):
                pg.evaluate(f"window.quadro({i / FPS})")
                canvas.screenshot(path=str(tmp / f"q_{i:04d}.png"))
            nav.close()
        SAIDA.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-framerate", str(FPS), "-i", str(tmp / "q_%04d.png"),
                        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
                        str(SAIDA)], check=True)
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-ss", "4", "-i", str(SAIDA), "-frames:v", "1",
                        "-q:v", "2", str(SAIDA.with_suffix(".jpg"))], check=True)
    print(f"cena ilustrativa em {SAIDA}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
