"""Dossiê do radar: o texto das matérias, aberto pelo kit antes de o Claude escrever.

Post escrito só com a manchete sai raso ("o Canaltech calculou..." sem o resultado). O kit abre as
matérias que o radar achou (artigos.py, com cache) e entrega o texto; as que não abrirem ficam marcadas
para o Claude procurar outra fonte.
"""
from __future__ import annotations

from datetime import date

from .marca import RAIZ

ARQUIVO = RAIZ / "saida" / "radar" / "dossie.md"


def montar(hoje: date | None = None, maximo: int = 8, por_assunto: int = 3) -> tuple[int, int]:
    """Grava saida/radar/dossie.md; devolve (assuntos, matérias com texto)."""
    from .redator import com_textos, noticias_pendentes
    hoje = hoje or date.today()
    assuntos = com_textos(noticias_pendentes(hoje, maximo), por_assunto)
    partes = [f"# Dossiê do radar ({hoje:%d/%m/%Y})\n",
              "Texto das matérias aberto pelo kit. Use os números, nomes e datas daqui. Matéria marcada "
              "\"só a manchete\" não abriu: procure outra fonte com WebSearch/WebFetch antes de escrever.\n"]
    lidas = 0
    for n, a in enumerate(assuntos, 1):
        partes.append(f"\n## Assunto {n}\n")
        for f in a["fontes"]:
            if not f["texto"].startswith("(só"):
                lidas += 1
            partes.append(f"### {f['veiculo']} ({f['data']}), selo sugerido {f['selo_sugerido']}\n"
                          f"Manchete: {f['manchete']}\nLink: {f['link']}\n\n{f['texto']}\n")
        if a["outras_manchetes"]:
            partes.append("Outras manchetes: " + " | ".join(a["outras_manchetes"]) + "\n")
    ARQUIVO.parent.mkdir(parents=True, exist_ok=True)
    ARQUIVO.write_text("\n".join(partes), encoding="utf-8")
    return len(assuntos), lidas
