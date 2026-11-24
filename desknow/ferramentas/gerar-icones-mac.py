#!/usr/bin/env python3
"""Gera os ícones do DeskNow para o macOS, a partir do que gerar-icones.py já produziu.

Saídas (em desknow/marca/arquivos/, espelhando o repositório):
  res/mac-icon.png                     ícone 1024 no grid do macOS (corpo de 824 px, sombra leve)
  flutter/macos/Runner/AppIcon.icns    ícone do app (todos os tamanhos)
  res/mac-tray-dark-x2.png (60 px)     imagem-modelo da barra de menus (preto + alfa)
  res/mac-tray-light-x2.png (48 px)    idem
  flutter/assets/icone-bandeja-mac.png imagem-modelo que o app usa no Mac no lugar do icon.png
                                       colorido (o macOS pinta o ícone da barra de uma cor só)

Uso: python desknow/ferramentas/gerar-icones-mac.py   (precisa de Pillow; rode depois de gerar-icones.py)
"""
from pathlib import Path

from PIL import Image, ImageFilter

ARQ = Path(__file__).resolve().parents[1] / "marca" / "arquivos"
LADRILHO = ARQ / "res" / "icon.png"  # 1024, cantos arredondados, já com o degradê e o símbolo
FRENTE = ARQ / "flutter/android/app/src/main/res/mipmap-xxxhdpi/ic_launcher_foreground.png"  # símbolo branco


def icone_mac() -> Image.Image:
    """Ladrilho no grid de ícones do macOS: corpo de 824 px centralizado num quadro de 1024."""
    corpo = Image.open(LADRILHO).convert("RGBA").resize((824, 824), Image.LANCZOS)
    quadro = Image.new("RGBA", (1024, 1024), (0, 0, 0, 0))
    alfa_sombra = Image.new("L", (1024, 1024), 0)
    alfa_sombra.paste(corpo.split()[3], (100, 112))
    alfa_sombra = alfa_sombra.filter(ImageFilter.GaussianBlur(14)).point(lambda v: int(v * 0.35))
    sombra = Image.new("RGBA", (1024, 1024), (0, 0, 0, 255))
    sombra.putalpha(alfa_sombra)
    quadro = Image.alpha_composite(quadro, sombra)
    quadro.alpha_composite(corpo, (100, 100))
    return quadro


def simbolo_modelo(lado: int, ocupacao: float = 0.82) -> Image.Image:
    """Símbolo preto com alfa (imagem-modelo do macOS), centralizado num quadrado de `lado` px."""
    alfa = Image.open(FRENTE).convert("RGBA").split()[3]
    alfa = alfa.crop(alfa.getbbox())
    alvo = round(lado * ocupacao)
    escala = alvo / max(alfa.size)
    alfa = alfa.resize((max(1, round(alfa.width * escala)), max(1, round(alfa.height * escala))), Image.LANCZOS)
    img = Image.new("RGBA", (lado, lado), (0, 0, 0, 0))
    preto = Image.new("RGBA", alfa.size, (0, 0, 0, 255))
    preto.putalpha(alfa)
    img.alpha_composite(preto, ((lado - alfa.width) // 2, (lado - alfa.height) // 2))
    return img


def salvar(img: Image.Image, rel: str, **kw) -> None:
    destino = ARQ / rel
    destino.parent.mkdir(parents=True, exist_ok=True)
    img.save(destino, **kw)
    print(f"{rel}: {img.size[0]}x{img.size[1]}")


def main() -> None:
    mac = icone_mac()
    salvar(mac, "res/mac-icon.png", optimize=True)
    salvar(mac, "flutter/macos/Runner/AppIcon.icns", format="ICNS")
    tamanhos = sorted(Image.open(ARQ / "flutter/macos/Runner/AppIcon.icns").info.get("sizes", []))
    print("  tamanhos no .icns:", tamanhos)
    salvar(simbolo_modelo(60), "res/mac-tray-dark-x2.png", optimize=True)
    salvar(simbolo_modelo(48), "res/mac-tray-light-x2.png", optimize=True)
    salvar(simbolo_modelo(44), "flutter/assets/icone-bandeja-mac.png", optimize=True)


if __name__ == "__main__":
    main()
