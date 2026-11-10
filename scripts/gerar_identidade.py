"""Gera a identidade visual de cada página em assets/marcas/<marca>/:

- avatar.png       foto de perfil 1080x1080 (suba esta no Instagram e no TikTok)
- fundo.png        fundo padrão 1080x1920, usado quando não há vídeo de fundo
- previa_*.png     cada tipo de cena com dados de exemplo
- folha_estilo.png todas as cenas lado a lado, para conferir o padrão

Uso:  python scripts/gerar_identidade.py
"""
from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageFilter

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))

from pipeline.cartoes import CAIXA_MIDIA, desenhar_fundo, desenhista, montar_html  # noqa: E402
from pipeline.marca import carregar_marca  # noqa: E402
from pipeline.modelos import Produto  # noqa: E402

EX = RAIZ / "assets" / "exemplos"

AMOSTRAS = {
    "gg_explica": {
        "serie": "15 FATOS EM 15 DIAS",
        "produto": None,
        "cenas": [
            {"tipo": "gancho", "kicker": "Fato 15 de 15", "titulo": "Faltam *15 dias*. E ela acabou de sair da cadeia"},
            {"tipo": "texto", "selo": "confirmado", "fonte": "Rockstar Games · site oficial",
             "texto": "Lutar pela família levou a Lucia para a *Penitenciária de Leonida*."},
            {"tipo": "texto", "selo": "teoria", "texto": "Foi sorte… ou *alguém tirou ela de lá*?"},
            {"tipo": "lista", "selo": "confirmado", "fonte": "Rockstar Games", "titulo": "Leonida em 3 lugares",
             "itens": ["Vice City: *praia* e neon", "Grassrivers: *pântanos*", "Leonida Keys: *ilhas*"]},
            {"tipo": "midia", "midia": "assets/exemplos/mapa_leonida_esquema.png", "midia_terceiros": False,
             "selo": "confirmado", "fonte": "Rockstar Games", "titulo": "Leonida tem *6 regiões*",
             "credito": "Mapa: GG Explica (esquema)"},
            {"tipo": "contagem", "kicker": "GTA VI", "numero": "15", "rotulo": "dias para o *lançamento*",
             "rodape": "19/11 · PS5 e Xbox Series X|S"},
            {"tipo": "veredito", "selo": "relato", "kicker": "Veredito", "fonte": "GamesBeat, via Tecnoblog",
             "texto": "Fonte séria, mas *a Rockstar não confirmou*."},
            {"tipo": "cta", "texto": "Time Lucia ou *time Jason*?", "rodape": "Amanhã: fato 14"},
        ],
    },
    "gamer_pao_duro": {
        "serie": "PÃO-DURO APROVA?",
        "produto": Produto(nome="Controle sem fio (exemplo)", loja="shopee", preco=189.9,
                           preco_referencia=249.9, imagem=(EX / "controle.svg").as_uri(), loja_oficial=True),
        "cenas": [
            {"tipo": "gancho", "kicker": "Pão-Duro aprova?", "titulo": "Controle de *R$ 189* vale a pena?"},
            {"tipo": "texto", "texto": "Dá pra comparar pelo *custo por hora* de bateria, não só pelo preço.", "rodape": "Dados de exemplo"},
            {"tipo": "lista", "titulo": "Antes de comprar", "itens": ["Confira se é *loja oficial*", "Compare com o preço médio", "Leia as avaliações com foto"]},
            {"tipo": "produto", "produto": 0, "rodape": "Preço de exemplo"},
            {"tipo": "comparativo", "titulo": "Barato x caro", "coluna_a": "R$ 189", "coluna_b": "R$ 449",
             "linhas": [["Bateria", "20 h", "12 h", "a"], ["Garantia", "3 meses", "1 ano", "b"], ["Peso", "210 g", "280 g", "a"]]},
            {"tipo": "veredito", "aprovado": True, "texto": "Pelo preço, *vale a pena*."},
            {"tipo": "contagem", "kicker": "Radar GTA 6", "numero": "15", "rotulo": "dias para o *lançamento*",
             "rodape": "19 de novembro · PS5 e Xbox Series X|S"},
            {"tipo": "cta", "texto": "Segue pra não *pagar caro*", "rodape": "Link no carrinho"},
        ],
    },
    "seul_no_bolso": {
        "serie": "CABE NO BOLSO?",
        "produto": Produto(nome="Sérum hidratante 30 ml (exemplo)", loja="shopee", preco=89.9,
                           preco_referencia=119.9, imagem=(EX / "frasco.svg").as_uri(), loja_oficial=True),
        "cenas": [
            {"tipo": "gancho", "kicker": "Cabe no bolso?", "titulo": "O sérum coreano que *viralizou* vale o preço?"},
            {"tipo": "texto", "texto": "Compare pelo *preço por ml*, não pelo preço do frasco.", "rodape": "Dados de exemplo"},
            {"tipo": "lista", "titulo": "Rotina de manhã", "itens": ["Limpeza *suave*", "Sérum hidratante", "Protetor solar *sempre*"]},
            {"tipo": "produto", "produto": 0, "rotulo": "R$ 3,00/ml", "rodape": "Preço de exemplo"},
            {"tipo": "comparativo", "titulo": "Coreano x farmácia", "coluna_a": "Coreano", "coluna_b": "Farmácia",
             "linhas": [["Preço", "R$ 89,90", "R$ 129,90", "a"], ["Tamanho", "30 ml", "30 ml", ""], ["Por ml", "R$ 3,00", "R$ 4,33", "a"]]},
            {"tipo": "veredito", "aprovado": True, "texto": "Mais barato por ml e vendido por *loja oficial*."},
            {"tipo": "contagem", "kicker": "Original ou falso?", "numero": "4", "rotulo": "sinais de skincare *falso*"},
            {"tipo": "cta", "texto": "Salva e manda pra amiga que *ama skincare*", "rodape": "Link no carrinho"},
        ],
    },
}


def avatar_html(svg: str) -> str:
    fontes = (RAIZ / "assets" / "fontes").as_uri()
    return f"""<!doctype html><html><head><meta charset="utf-8"><style>
    @font-face {{ font-family: "Anton"; src: url("{fontes}/Anton-Regular.ttf"); }}
    html,body{{margin:0;width:1080px;height:1080px;overflow:hidden}} svg{{display:block;width:1080px;height:1080px}}
    </style></head><body>{svg}</body></html>"""


def previa_midia(d, marca, cena: dict, serie: str, saida: Path) -> Image.Image:
    """Mesma composição do vídeo: fundo desfocado, moldura, clipe na caixa e cartão por cima."""
    imagem = Image.open(RAIZ / cena["midia"]).convert("RGBA")
    escala = max(1080 / imagem.width, 1920 / imagem.height)
    fundo = imagem.resize((round(imagem.width * escala), round(imagem.height * escala)), Image.LANCZOS)
    x0, y0 = (fundo.width - 1080) // 2, (fundo.height - 1920) // 2
    quadro = fundo.crop((x0, y0, x0 + 1080, y0 + 1920)).filter(ImageFilter.GaussianBlur(30))
    moldura = d.desenhar(montar_html(marca, cena, serie=serie, modo="moldura"), saida.with_name("_moldura.png"))
    quadro = Image.alpha_composite(quadro, Image.open(moldura).convert("RGBA"))
    borda = 4
    cl, ca = CAIXA_MIDIA["l"] - 2 * borda, CAIXA_MIDIA["a"] - 2 * borda
    s = min(cl / imagem.width, ca / imagem.height)
    caixa = Image.new("RGBA", (round(imagem.width * s) + 2 * borda, round(imagem.height * s) + 2 * borda),
                      marca.cores["destaque"])
    caixa.paste(imagem.resize((round(imagem.width * s), round(imagem.height * s)), Image.LANCZOS), (borda, borda))
    quadro.paste(caixa, ((1080 - caixa.width) // 2, CAIXA_MIDIA["y"] + (CAIXA_MIDIA["a"] - caixa.height) // 2))
    cartao = d.desenhar(montar_html(marca, cena, serie=serie, modo="cartao"), saida)
    quadro = Image.alpha_composite(quadro, Image.open(cartao).convert("RGBA"))
    saida.with_name("_moldura.png").unlink(missing_ok=True)
    return quadro


def main() -> None:
    with desenhista() as d:
        d._pagina.set_viewport_size({"width": 1080, "height": 1920})
        for marca_id, amostra in AMOSTRAS.items():
            marca = carregar_marca(marca_id)
            pasta = marca.pasta_assets
            fundo = desenhar_fundo(d, marca, pasta / "fundo.png")
            base = Image.open(fundo).convert("RGBA")
            miniaturas = []
            for n, cena in enumerate(amostra["cenas"]):
                nome = f"previa_{n + 1:02d}_{cena['tipo']}{'_' + cena['selo'] if cena.get('selo') else ''}.png"
                if cena["tipo"] == "midia":
                    quadro = previa_midia(d, marca, cena, amostra["serie"], pasta / nome)
                else:
                    html_doc = montar_html(marca, cena, serie=amostra["serie"],
                                           produto=amostra["produto"] if cena["tipo"] == "produto" else None,
                                           fundo_solido=True)
                    png = d.desenhar(html_doc, pasta / nome)
                    quadro = Image.alpha_composite(base, Image.open(png).convert("RGBA"))
                quadro.convert("RGB").save(pasta / nome)
                miniaturas.append(quadro.resize((360, 640), Image.LANCZOS))
            folha = Image.new("RGB", (4 * 360 + 5 * 24, 2 * 640 + 3 * 24), marca.cores["fundo"])
            for i, m in enumerate(miniaturas):
                x = 24 + (i % 4) * (360 + 24)
                y = 24 + (i // 4) * (640 + 24)
                folha.paste(m.convert("RGB"), (x, y))
            folha.save(pasta / "folha_estilo.png")

            d._pagina.set_viewport_size({"width": 1080, "height": 1080})
            d.desenhar(avatar_html((pasta / "avatar.svg").read_text(encoding="utf-8")), pasta / "avatar.png",
                       transparente=False)
            d._pagina.set_viewport_size({"width": 1080, "height": 1920})
            print(f"{marca.nome}: identidade gerada em {pasta}")


if __name__ == "__main__":
    main()
