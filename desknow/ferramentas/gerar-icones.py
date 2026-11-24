#!/usr/bin/env python3
"""Gerador de ícones e logos do DeskNow.

Rode a partir da raiz do repositório:
    python desknow/ferramentas/gerar-icones.py

Lê desknow/marca.json, o degradê em desknow/marca/fonte/ e a fonte Geist
variável em desknow/marca/fontes/. Escreve em desknow/marca/arquivos/
(espelhando os caminhos do repositório) e em desknow/marca/kit/. No fim,
imprime a tabela de conferência e gera a folha em docs/prints/kit-icones.png.
"""

from __future__ import annotations

import json
import math
import shutil
import sys
from pathlib import Path

from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont
from fontTools.varLib import instancer
from PIL import Image, ImageChops, ImageDraw, ImageFont

# ---------------------------------------------------------------- caminhos
AQUI = Path(__file__).resolve().parent
DESKNOW = AQUI.parent
REPO = DESKNOW.parent
MARCA = DESKNOW / "marca"
ARQUIVOS = MARCA / "arquivos"
KIT = MARCA / "kit"
PRINTS = REPO.parent / "docs" / "prints"

# ---------------------------------------------------------------- geometria
SS = 8  # supersampling
CAIXA = 68.0  # o símbolo ocupa 68x68 unidades
LADO = 51.0
TRACO = 7.0
R_EXT = 10.7
R_INT = 3.7
DESLOC = 17.0

TEXTO_TAMANHO = 45.495
TEXTO_TRACKING = -1.221
TEXTO_X = 84.165
TEXTO_BASE = 50.379

FRACAO_SIMBOLO = 0.56
FRACAO_PEQUENO = 0.70
TRACO_PEQUENO = 1.2
RAIO_LADRILHO = 0.225

ICO_APP = [16, 24, 32, 48, 64, 128, 256]
ICO_TRAY = [16, 20, 24, 32, 48]
DENSIDADES = {"mdpi": 1, "hdpi": 1.5, "xhdpi": 2, "xxhdpi": 3, "xxxhdpi": 4}


# ---------------------------------------------------------------- símbolo
def _canto(cx, cy, r, ang0, n=20):
    """Pontos de um quarto de círculo; r == 0 vira um único ponto vivo."""
    if r <= 0:
        return [(cx, cy)]
    return [
        (cx + r * math.cos(math.radians(ang0 + 90 * i / n)),
         cy + r * math.sin(math.radians(ang0 + 90 * i / n)))
        for i in range(n + 1)
    ]


def retangulo_arredondado(x, y, w, h, raios):
    """Polígono (sentido horário na tela) com raios (se, sd, id, ie)."""
    se, sd, id_, ie = raios
    pts = []
    pts += _canto(x + se, y + se, se, 180)
    pts += _canto(x + w - sd, y + sd, sd, 270)
    pts += _canto(x + w - id_, y + h - id_, id_, 0)
    pts += _canto(x + ie, y + h - ie, ie, 90)
    return pts


def aneis(traco: float = TRACO):
    """Contornos do símbolo, em unidades: lista de (polígono, é_buraco, anel)."""
    saida = []
    # anel de trás: canto inferior direito vivo; anel da frente: superior esquerdo vivo
    for idx, (dx, raios_ext, raios_int) in enumerate([
        (0.0, (R_EXT, R_EXT, 0, R_EXT), (R_INT, R_INT, 0, R_INT)),
        (DESLOC, (0, R_EXT, R_EXT, R_EXT), (0, R_INT, R_INT, R_INT)),
    ]):
        saida.append((retangulo_arredondado(dx, dx, LADO, LADO, raios_ext), False, idx))
        saida.append((retangulo_arredondado(dx + traco, dx + traco, LADO - 2 * traco,
                                            LADO - 2 * traco, raios_int), True, idx))
    return saida


def mascara_simbolo(tela: int, caixa: float, traco: float = TRACO) -> Image.Image:
    """Máscara L (tela x tela) com o símbolo centralizado numa caixa de `caixa` px."""
    n = round(tela * SS)
    k = caixa * SS / CAIXA
    o = (tela - caixa) / 2 * SS
    camadas = [Image.new("L", (n, n), 0), Image.new("L", (n, n), 0)]
    for poligono, buraco, idx in aneis(traco):
        d = ImageDraw.Draw(camadas[idx])
        d.polygon([(o + px * k, o + py * k) for px, py in poligono],
                  fill=0 if buraco else 255)
    uniao = ImageChops.lighter(*camadas)
    return uniao.resize((tela, tela), Image.BOX)


def caminho_svg(escala=1.0, dx=0.0, dy=0.0, traco: float = TRACO) -> str:
    """Path do símbolo (união por nonzero: externos num sentido, buracos no outro)."""
    def f(v):
        return f"{v:.3f}".rstrip("0").rstrip(".")

    partes = []
    for poligono, buraco, _ in aneis(traco):
        pts = poligono[::-1] if buraco else poligono
        # remove pontos repetidos (cantos vivos)
        limpo = [p for i, p in enumerate(pts) if i == 0 or p != pts[i - 1]]
        cmds = [("M" if i == 0 else "L") + f"{f(dx + x * escala)} {f(dy + y * escala)}"
                for i, (x, y) in enumerate(limpo)]
        partes.append("".join(cmds) + "Z")
    return "".join(partes)


# ---------------------------------------------------------------- ladrilho
def carregar_fundo() -> Image.Image:
    img = Image.open(MARCA / "fonte" / "fundo-logo.png").convert("RGB")
    return img.crop((161, 0, 716, img.height))


def fundo(tam: int, base: Image.Image) -> Image.Image:
    return base.resize((tam, tam), Image.LANCZOS)


def forma(tam: int, tipo: str) -> Image.Image:
    """Máscara de alfa: 'ladrilho' (cantos 22,5%), 'circulo' ou 'cheio'."""
    if tipo == "cheio":
        return Image.new("L", (tam, tam), 255)
    n = tam * SS
    m = Image.new("L", (n, n), 0)
    d = ImageDraw.Draw(m)
    if tipo == "circulo":
        d.ellipse((0, 0, n - 1, n - 1), fill=255)
    else:
        r = RAIO_LADRILHO * n
        d.polygon(retangulo_arredondado(0, 0, n, n, (r, r, r, r)), fill=255)
    return m.resize((tam, tam), Image.BOX)


def ladrilho(tam: int, base: Image.Image, tipo: str = "ladrilho") -> Image.Image:
    pequeno = tam <= 32
    frac = FRACAO_PEQUENO if pequeno else FRACAO_SIMBOLO
    traco = TRACO * TRACO_PEQUENO if pequeno else TRACO
    bg = fundo(tam, base)
    sim = mascara_simbolo(tam, tam * frac, traco)
    rgb = Image.composite(Image.new("RGB", (tam, tam), "white"), bg, sim)
    img = rgb.convert("RGBA")
    img.putalpha(forma(tam, tipo))
    return img


def simbolo_branco(tela: int, caixa: float, cor=(255, 255, 255)) -> Image.Image:
    img = Image.new("RGBA", (tela, tela), cor + (0,))
    img.putalpha(mascara_simbolo(tela, caixa))
    return img


# ---------------------------------------------------------------- fontes/logo
def gerar_fontes() -> Path:
    destino = ARQUIVOS / "flutter" / "assets" / "fonts"
    destino.mkdir(parents=True, exist_ok=True)
    for nome, peso in [("Regular", 400), ("Medium", 500), ("SemiBold", 600), ("Bold", 700)]:
        var = TTFont(MARCA / "fontes" / "Geist-Variavel.ttf")
        est = instancer.instantiateVariableFont(var, {"wght": peso})
        est.save(destino / f"Geist-{nome}.ttf")
    shutil.copyfile(MARCA / "fontes" / "OFL.txt", destino / "OFL.txt")
    return destino / "Geist-SemiBold.ttf"


class Texto:
    """Layout do nome: avanço de cada glifo + tracking, sem kerning."""

    def __init__(self, ttf: Path, nome: str):
        self.ttf = ttf
        self.nome = nome
        self.fonte = TTFont(ttf)
        cmap = self.fonte.getBestCmap()
        self.glifos = [cmap[ord(c)] for c in nome]
        self.k = TEXTO_TAMANHO / self.fonte["head"].unitsPerEm
        hmtx = self.fonte["hmtx"]
        self.posicoes = []
        x = TEXTO_X
        for g in self.glifos:
            self.posicoes.append(x)
            x += hmtx[g][0] * self.k + TEXTO_TRACKING
        # fim do texto: último avanço, sem o tracking que sobraria
        self.fim = x - TEXTO_TRACKING
        self.largura = self.fim

    def svg_path(self) -> str:
        def ntos(v):
            return f"{v:.3f}".rstrip("0").rstrip(".")
        gs = self.fonte.getGlyphSet()
        partes = []
        for g, x in zip(self.glifos, self.posicoes):
            pen = SVGPathPen(gs, ntos=ntos)
            gs[g].draw(TransformPen(pen, (self.k, 0, 0, -self.k, x, TEXTO_BASE)))
            partes.append(pen.getCommands())
        return "".join(partes)

    def mascara(self, altura: int) -> Image.Image:
        """Máscara L da logo inteira (símbolo + texto) com a altura dada."""
        e = altura / CAIXA
        larg = round(self.largura * e)
        W, H = larg * SS, altura * SS
        es = e * SS
        # símbolo
        sim = Image.new("L", (W, H), 0)
        camadas = [Image.new("L", (W, H), 0), Image.new("L", (W, H), 0)]
        for poligono, buraco, idx in aneis():
            ImageDraw.Draw(camadas[idx]).polygon(
                [(px * es, py * es) for px, py in poligono], fill=0 if buraco else 255)
        sim = ImageChops.lighter(*camadas)
        # texto, letra por letra (sem kerning)
        fonte = ImageFont.truetype(str(self.ttf), size=TEXTO_TAMANHO * es)
        txt = Image.new("L", (W, H), 0)
        d = ImageDraw.Draw(txt)
        for c, x in zip(self.nome, self.posicoes):
            d.text((x * es, TEXTO_BASE * es), c, font=fonte, fill=255, anchor="ls")
        total = ImageChops.lighter(sim, txt)
        return total.resize((larg, altura), Image.BOX)

    def imagem(self, altura: int, cor) -> Image.Image:
        m = self.mascara(altura)
        img = Image.new("RGBA", m.size, tuple(cor) + (0,))
        img.putalpha(m)
        return img

    def svg(self) -> str:
        return (
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {self.largura:.3f} 68" '
            f'width="{self.largura * 4:.0f}" height="272">\n'
            f'  <title>{self.nome}</title>\n'
            f'  <path fill="#fff" d="{caminho_svg()}"/>\n'
            f'  <path fill="#fff" d="{self.svg_path()}"/>\n</svg>\n'
        )


# ---------------------------------------------------------------- saída
def salvar_png(img: Image.Image, rel: str, raiz: Path = ARQUIVOS):
    destino = raiz / rel
    destino.parent.mkdir(parents=True, exist_ok=True)
    img.save(destino, optimize=True)


def salvar_ico(rel: str, tamanhos: list[int], base: Image.Image):
    destino = ARQUIVOS / rel
    destino.parent.mkdir(parents=True, exist_ok=True)
    imgs = {t: ladrilho(t, base) for t in tamanhos}
    maior = imgs[max(tamanhos)]
    outros = [imgs[t] for t in tamanhos if t != max(tamanhos)]
    maior.save(destino, format="ICO", sizes=[(t, t) for t in tamanhos], append_images=outros)


def escrever(destino: Path, texto: str):
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(texto, encoding="utf-8")


def gerar_tudo(marca: dict):
    base = carregar_fundo()
    cor_claro = tuple(int(marca["cores"]["logo_claro"][i:i + 2], 16) for i in (0, 2, 4))
    branco = (255, 255, 255)

    # ícones .ico
    salvar_ico("res/icon.ico", ICO_APP, base)
    salvar_ico("res/tray-icon.ico", ICO_TRAY, base)
    salvar_ico("flutter/windows/runner/resources/app_icon.ico", ICO_APP, base)
    salvar_ico("flutter/assets/icon.ico", ICO_APP, base)

    # PNGs do ladrilho
    for rel, t in [("res/icon.png", 1024), ("res/32x32.png", 32), ("res/64x64.png", 64),
                   ("res/128x128.png", 128), ("res/128x128@2x.png", 256),
                   ("flutter/assets/icon.png", 256)]:
        salvar_png(ladrilho(t, base), rel)

    # SVG do ícone
    esc = 100 * FRACAO_SIMBOLO / CAIXA
    desl = 100 * (1 - FRACAO_SIMBOLO) / 2
    escrever(ARQUIVOS / "flutter/assets/icon.svg", (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" width="512" height="512">\n'
        '  <defs>\n'
        '    <linearGradient id="g" gradientUnits="userSpaceOnUse" x1="0" y1="100" x2="100" y2="0">\n'
        '      <stop offset="0" stop-color="#0CBAE7"/>\n'
        '      <stop offset="0.5" stop-color="#4F5BE8"/>\n'
        '      <stop offset="1" stop-color="#2C2148"/>\n'
        '    </linearGradient>\n'
        '  </defs>\n'
        '  <rect width="100" height="100" rx="22.5" ry="22.5" fill="url(#g)"/>\n'
        f'  <path fill="#fff" d="{caminho_svg(esc, desl, desl)}"/>\n'
        '</svg>\n'))

    # fontes e logos
    semibold = gerar_fontes()
    texto = Texto(semibold, marca["nome"])
    salvar_png(texto.imagem(180, branco), "flutter/assets/logo_dark.png")
    salvar_png(texto.imagem(180, cor_claro), "flutter/assets/logo_light.png")

    # Android
    for dens, f in DENSIDADES.items():
        pasta = f"flutter/android/app/src/main/res/mipmap-{dens}"
        t48, t108, t24 = round(48 * f), round(108 * f), round(24 * f)
        salvar_png(ladrilho(t48, base), f"{pasta}/ic_launcher.png")
        salvar_png(ladrilho(t48, base, "circulo"), f"{pasta}/ic_launcher_round.png")
        salvar_png(simbolo_branco(t108, 46 * f), f"{pasta}/ic_launcher_foreground.png")
        salvar_png(fundo(t108, base).convert("RGBA"), f"{pasta}/ic_launcher_background.png")
        m = mascara_simbolo(t24, 20 * f)
        la = Image.merge("LA", (Image.new("L", m.size, 255), m))
        salvar_png(la, f"{pasta}/ic_stat_logo.png")

    # kit para uso humano
    escrever(KIT / "simbolo.svg", (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 68 68" width="272" height="272">\n'
        f'  <path fill="#fff" d="{caminho_svg()}"/>\n</svg>\n'))
    escrever(KIT / "logo-branca.svg", texto.svg())
    salvar_png(texto.imagem(270, branco), "logo-branca.png", KIT)
    salvar_png(texto.imagem(270, cor_claro), "logo-escura.png", KIT)
    return base


# ---------------------------------------------------------------- conferência
def descrever(p: Path) -> tuple[str, set]:
    suf = p.suffix.lower()
    if suf == ".ico":
        tam = Image.open(p).ico.sizes()
        return "ico " + ",".join(str(w) for w, _ in sorted(tam)), set(tam)
    if suf == ".png":
        im = Image.open(p)
        return f"{im.size[0]}x{im.size[1]} {im.mode}", {im.size}
    if suf == ".svg":
        return "svg", set()
    return suf.lstrip(".") or "arquivo", set()


def tabela():
    print(f"\n{'arquivo':<68} {'gerado':<26} conferência")
    print("-" * 120)
    problemas = 0
    for raiz in (ARQUIVOS, KIT):
        for p in sorted(raiz.rglob("*")):
            if not p.is_file():
                continue
            rel = p.relative_to(raiz).as_posix()
            nome = f"{raiz.name}/{rel}"
            desc, tam = descrever(p)
            orig = REPO / rel if raiz == ARQUIVOS else None
            if orig is None or not orig.is_file() or p.suffix.lower() not in (".png", ".ico"):
                nota = "sem original" if p.suffix.lower() in (".png", ".ico") else "-"
                print(f"{nome:<68} {desc:<26} {nota}")
                continue
            d_orig, t_orig = descrever(orig)
            if p.suffix.lower() == ".ico":
                ok = t_orig <= tam
            else:
                ok = t_orig == tam
            problemas += not ok
            print(f"{nome:<68} {desc:<26} {'OK' if ok else 'DIFERENTE'} (original: {d_orig})")
    print("-" * 120)
    print("Conferência:", "tudo compatível com o RustDesk." if not problemas
          else f"{problemas} arquivo(s) fora do esperado!")


# ---------------------------------------------------------------- folha
def folha(base: Image.Image):
    PRINTS.mkdir(parents=True, exist_ok=True)
    claro, escuro = (244, 242, 250), (13, 11, 16)
    W = 1500
    fonte = ImageFont.truetype(str(ARQUIVOS / "flutter/assets/fonts/Geist-Medium.ttf"), 16)
    pequena = ImageFont.truetype(str(ARQUIVOS / "flutter/assets/fonts/Geist-Regular.ttf"), 13)
    img = Image.new("RGB", (W, 1280), (128, 128, 140))
    d = ImageDraw.Draw(img)

    def colar(im, x, y):
        img.paste(im, (x, y), im)

    def banda(y, h, cor, x0=0, x1=W):
        d.rectangle((x0, y, x1, y + h), fill=cor)

    d.text((20, 10), "DeskNow - kit de icones", font=fonte, fill="white")
    # A. ladrilhos
    y = 40
    for cor, nome, txt in [(claro, "claro", (30, 30, 40)), (escuro, "escuro", (220, 220, 230))]:
        banda(y, 210, cor)
        x = 20
        d.text((x, y + 6), f"ladrilho sobre fundo {nome} (tamanho real)", font=pequena, fill=txt)
        for t in (16, 24, 32, 48, 128):
            colar(ladrilho(t, base), x, y + 40)
            d.text((x, y + 40 + t + 6), str(t), font=pequena, fill=txt)
            x += t + 40
        x = 560
        d.text((x, y + 6), "ampliado (vizinho mais próximo)", font=pequena, fill=txt)
        for t, z in ((16, 8), (24, 6), (32, 4)):
            im = ladrilho(t, base).resize((t * z, t * z), Image.NEAREST)
            colar(im, x, y + 40)
            x += t * z + 30
        y += 210
    # B. android
    y += 0
    banda(y, 360, (200, 200, 208))
    d.text((20, y + 6), "Android: adaptativo (frente sobre fundo, máscara circular) | ic_launcher_round | ic_launcher | ic_stat_logo",
           font=pequena, fill=(20, 20, 30))
    res = ARQUIVOS / "flutter/android/app/src/main/res/mipmap-xxxhdpi"
    fg = Image.open(res / "ic_launcher_foreground.png")
    bg = Image.open(res / "ic_launcher_background.png").convert("RGBA")
    comp = Image.alpha_composite(bg, fg)
    circ = forma(432, "circulo")
    ad = Image.new("RGBA", comp.size, (0, 0, 0, 0))
    ad.paste(comp, (0, 0), circ)
    # a área visível do adaptativo é o círculo de 72dp no meio dos 108dp
    vis = round(432 * 72 / 108)
    o = (432 - vis) // 2
    ad_vis = comp.crop((o, o, o + vis, o + vis))
    ad_vis.putalpha(forma(vis, "circulo"))
    colar(ad_vis, 20, y + 40)
    comp_full = comp.copy()
    colar(comp_full.resize((216, 216), Image.LANCZOS), 360, y + 40)
    d.text((20, y + 40 + vis + 6), "visível (72dp, circular)", font=pequena, fill=(20, 20, 30))
    d.text((360, y + 40 + 222), "108dp completo (sem máscara)", font=pequena, fill=(20, 20, 30))
    colar(Image.open(res / "ic_launcher_round.png"), 620, y + 40)
    d.text((620, y + 240), "round 192", font=pequena, fill=(20, 20, 30))
    colar(Image.open(res / "ic_launcher.png"), 840, y + 40)
    d.text((840, y + 240), "launcher 192", font=pequena, fill=(20, 20, 30))
    banda(y + 40, 150, escuro, 1060, 1480)
    for i, dens in enumerate(("xxxhdpi", "xxhdpi", "xhdpi", "mdpi")):
        p = ARQUIVOS / f"flutter/android/app/src/main/res/mipmap-{dens}/ic_stat_logo.png"
        la = Image.open(p)
        rgba = Image.new("RGBA", la.size, (255, 255, 255, 0))
        rgba.putalpha(la.getchannel("A"))
        colar(rgba, 1080 + [0, 120, 200, 260][i], y + 60)
        d.text((1080 + [0, 120, 200, 260][i], y + 40 + 120), dens, font=pequena, fill=(220, 220, 230))
    y += 360
    # C. logos
    assets = ARQUIVOS / "flutter/assets"
    ld = Image.open(assets / "logo_dark.png")
    ll = Image.open(assets / "logo_light.png")
    esc = 0.5
    ld_s = ld.resize((round(ld.width * esc), round(ld.height * esc)), Image.LANCZOS)
    ll_s = ll.resize((round(ll.width * esc), round(ll.height * esc)), Image.LANCZOS)
    banda(y, 260, claro, 0, W // 2)
    banda(y, 260, escuro, W // 2, W)
    d.text((20, y + 6), "logo_light.png (#2C2148) e logo_dark.png (branca), a 50%", font=pequena, fill=(30, 30, 40))
    colar(ll_s, 40, y + 50)
    colar(ld_s, W // 2 + 40, y + 50)
    # logos no tamanho real da fonte, pequenas, para checar corte do texto
    colar(ll.resize((ll.width // 4, ll.height // 4), Image.LANCZOS), 40, y + 180)
    colar(ld.resize((ld.width // 4, ld.height // 4), Image.LANCZOS), W // 2 + 40, y + 180)
    y += 260
    img = img.crop((0, 0, W, y))
    img.save(PRINTS / "kit-icones.png")
    print(f"\nFolha de conferência: {PRINTS / 'kit-icones.png'}")


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    marca = json.loads((DESKNOW / "marca.json").read_text(encoding="utf-8"))
    print(f"Gerando ícones e logos de {marca['nome']}...")
    base = gerar_tudo(marca)
    tabela()
    folha(base)


if __name__ == "__main__":
    main()
