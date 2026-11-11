import shutil
import subprocess

import pytest

from pipeline import sonda


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="sem ffmpeg")
def test_sonda_sem_ffprobe_le_igual(tmp_path, monkeypatch):
    arq = tmp_path / "t.mp4"
    subprocess.run(["ffmpeg", "-nostdin", "-loglevel", "error", "-f", "lavfi", "-i", "testsrc=s=320x240:d=1",
                    "-f", "lavfi", "-i", "sine=d=1", "-shortest", "-preset", "veryfast", str(arq)], check=True)
    monkeypatch.setattr(sonda.shutil, "which", lambda nome: None)
    assert sonda.video(arq)["width"] == 320 and sonda.video(arq)["height"] == 240
    assert abs(sonda.duracao(arq) - 1.0) < 0.1
    assert any(f["codec_type"] == "audio" for f in sonda.sondar(arq)["streams"])
