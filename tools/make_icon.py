"""Gera o ícone do LegendAI (conceito "Play + Legenda").

Desenha em alta resolução (supersampling) e exporta um .ico multi-resolução
e um .png de prévia. Reproduzível: basta rodar `python tools/make_icon.py`.
"""

from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

SS = 2048  # tela de supersampling
ASSETS = Path(__file__).resolve().parent.parent / "assets"
GRAD_TOP = np.array([155, 107, 255], dtype=float)  # #9B6BFF
GRAD_BOTTOM = np.array([98, 52, 216], dtype=float)  # #6234D8
ICO_SIZES = [16, 32, 48, 64, 128, 256]


def _s(value: float) -> float:
    """Converte coordenadas do espaço 512 (do design) para a tela SS."""
    return value * SS / 512


def _diagonal_gradient() -> Image.Image:
    yy, xx = np.mgrid[0:SS, 0:SS]
    t = (xx + yy) / (2 * (SS - 1))
    rgb = (GRAD_TOP * (1 - t)[..., None] + GRAD_BOTTOM * t[..., None]).astype(np.uint8)
    return Image.fromarray(rgb, "RGB").convert("RGBA")


def _rounded_mask() -> Image.Image:
    mask = Image.new("L", (SS, SS), 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        [_s(16), _s(16), _s(496), _s(496)], radius=_s(112), fill=255
    )
    return mask


def build_icon() -> Image.Image:
    mask = _rounded_mask()
    base = _diagonal_gradient()
    base.putalpha(mask)

    # Brilho suave na metade superior, recortado pela máscara arredondada.
    highlight = Image.new("RGBA", (SS, SS), (0, 0, 0, 0))
    ImageDraw.Draw(highlight).rounded_rectangle(
        [_s(16), _s(16), _s(496), _s(256)], radius=_s(112), fill=(255, 255, 255, 18)
    )
    highlight.putalpha(
        Image.composite(highlight.getchannel("A"), Image.new("L", (SS, SS), 0), mask)
    )
    base = Image.alpha_composite(base, highlight)

    draw = ImageDraw.Draw(base)
    # Triângulo de play.
    draw.polygon(
        [(_s(212), _s(150)), (_s(212), _s(306)), (_s(338), _s(228))],
        fill=(255, 255, 255, 255),
    )
    # Barra de legenda principal.
    draw.rounded_rectangle(
        [_s(150), _s(356), _s(362), _s(390)], radius=_s(17), fill=(255, 255, 255, 255)
    )
    # Barra secundária a 60% de opacidade.
    overlay = Image.new("RGBA", (SS, SS), (0, 0, 0, 0))
    ImageDraw.Draw(overlay).rounded_rectangle(
        [_s(150), _s(406), _s(290), _s(440)], radius=_s(17), fill=(255, 255, 255, 153)
    )
    return Image.alpha_composite(base, overlay)


def main() -> None:
    ASSETS.mkdir(parents=True, exist_ok=True)
    icon = build_icon()
    frames = [icon.resize((n, n), Image.LANCZOS) for n in ICO_SIZES]
    frames[-1].save(
        ASSETS / "legendai.ico", format="ICO", sizes=[(n, n) for n in ICO_SIZES]
    )
    icon.resize((256, 256), Image.LANCZOS).save(ASSETS / "legendai.png")
    print(f"Ícone gerado em {ASSETS / 'legendai.ico'}")


if __name__ == "__main__":
    main()
