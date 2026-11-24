#!/usr/bin/env python3
"""Aplica a marca DeskNow sobre o código do RustDesk.

Roda na compilação (GitHub Actions), logo depois do checkout com submódulos.
Usa só a biblioteca padrão do Python 3.

Uso:
    python desknow/aplicar-marca.py               aplica a marca
    python desknow/aplicar-marca.py --verificar   só confere, sem gravar nada
    python desknow/aplicar-marca.py --raiz PASTA  aplica em outra cópia do código

Rodar duas vezes dá o mesmo resultado de rodar uma. Se o RustDesk mudar um
trecho que este script procura, ele para e diz o arquivo e o trecho, para
que a gente ajuste aqui em vez de compilar um app pela metade.
"""
from __future__ import annotations

import argparse
import datetime
import filecmp
import json
import re
import shutil
import sys
from pathlib import Path

PASTA = Path(__file__).resolve().parent  # desknow/
CAMPOS = ("nome", "android_id", "mac_id", "empresa", "servidor", "chave_publica",
          "repositorio", "privacidade", "cores")


class TrechoNaoEncontrado(Exception):
    """O código do RustDesk não tem mais o trecho que o script espera."""


class Arquivo:
    """Arquivo de texto do RustDesk, lido e gravado em UTF-8 sem mexer no fim de linha."""

    def __init__(self, raiz: Path, rel: str):
        self.rel = rel
        self.caminho = raiz / rel
        if not self.caminho.is_file():
            raise TrechoNaoEncontrado(f"{rel}: arquivo não encontrado")
        self.texto = self.caminho.read_bytes().decode("utf-8")
        self.original = self.texto

    @property
    def nl(self) -> str:
        return "\r\n" if "\r\n" in self.texto else "\n"

    def trocar(self, antigo: str, novo: str) -> None:
        """Troca todas as ocorrências do texto literal `antigo` por `novo`."""
        if antigo in self.texto:
            self.texto = self.texto.replace(antigo, novo)
        elif novo not in self.texto:
            raise TrechoNaoEncontrado(f"{self.rel}: trecho não encontrado: {antigo!r}")

    def trocar_re(self, padrao: str, novo: str) -> None:
        """Troca o que casar com a expressão regular `padrao` pelo texto final `novo`."""
        rx = re.compile(padrao)
        if rx.search(self.texto):
            self.texto = rx.sub(lambda _m: novo, self.texto)
        elif novo not in self.texto:
            raise TrechoNaoEncontrado(f"{self.rel}: trecho não encontrado (regex): {padrao!r}")

    def inserir_depois(self, ancora: str, inserir: str) -> None:
        """Insere `inserir` logo depois de `ancora`, que precisa aparecer uma única vez."""
        if ancora + inserir in self.texto:
            return
        n = self.texto.count(ancora)
        if n != 1:
            raise TrechoNaoEncontrado(
                f"{self.rel}: âncora {ancora!r} aparece {n} vez(es); esperava 1")
        self.texto = self.texto.replace(ancora, ancora + inserir, 1)

    @property
    def mudou(self) -> bool:
        return self.texto != self.original

    def gravar(self) -> None:
        self.caminho.write_bytes(self.texto.encode("utf-8"))


def carregar_marca(pasta: Path = PASTA) -> dict:
    marca = json.loads((pasta / "marca.json").read_text(encoding="utf-8"))
    faltando = [c for c in CAMPOS if c not in marca]
    if faltando:
        raise SystemExit(f"marca.json: faltam os campos {', '.join(faltando)}")
    # o RustDesk só aceita letras, números e hífen no nome do app (ver src/lang.rs)
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9-]*", marca["nome"]):
        raise SystemExit("marca.json: 'nome' só pode ter letras, números e hífen")
    if not re.fullmatch(r"[A-Za-z0-9+/]{43}=", marca["chave_publica"]):
        raise SystemExit("marca.json: 'chave_publica' não parece uma chave ed25519 em base64")
    for campo in ("empresa", "repositorio", "privacidade"):
        if re.search(r"['\"\\$]", marca[campo]):
            raise SystemExit(f"marca.json: '{campo}' não pode ter aspas, barra invertida nem $")
    for cor, valor in marca["cores"].items():
        if not re.fullmatch(r"[0-9A-Fa-f]{6}", valor):
            raise SystemExit(f"marca.json: cor '{cor}' deve ter 6 dígitos hexadecimais")
    return marca


def aplicar(raiz: Path, marca: dict, gravar: bool = True) -> tuple[list[str], list[str]]:
    """Aplica a marca em `raiz`. Devolve (arquivos alterados, arquivos copiados)."""
    nome, empresa = marca["nome"], marca["empresa"]
    repositorio, privacidade = marca["repositorio"], marca["privacidade"]
    cores = {k: v.upper() for k, v in marca["cores"].items()}
    ano = datetime.date.today().year
    copyright_ = (f"Copyright © {ano} {empresa}. "
                  "Baseado no RustDesk © Purslane Tech Pte. Ltd. (AGPL-3.0)")
    arquivos: dict[str, Arquivo] = {}

    def arq(rel: str) -> Arquivo:
        if rel not in arquivos:
            arquivos[rel] = Arquivo(raiz, rel)
        return arquivos[rel]

    # 1. Núcleo (submódulo hbb_common): nome, organização, servidor e chave
    cfg = arq("libs/hbb_common/src/config.rs")
    # O ORG ("com.carriez") fica como está: no macOS, parte do código monta o nome do serviço
    # com o ORG e parte com "com.carriez" fixo; trocar só um lado quebraria a instalação.
    cfg.trocar('pub static ref APP_NAME: RwLock<String> = RwLock::new("RustDesk".to_owned());',
               f'pub static ref APP_NAME: RwLock<String> = RwLock::new("{nome}".to_owned());')
    cfg.trocar_re(r'pub const RENDEZVOUS_SERVERS: &\[&str\] = &\[[^\]]*\];',
                  f'pub const RENDEZVOUS_SERVERS: &[&str] = &["{marca["servidor"]}"];')
    cfg.trocar_re(r'pub const RS_PUB_KEY: &str = "[^"]*";',
                  f'pub const RS_PUB_KEY: &str = "{marca["chave_publica"]}";')
    # esconde o "Powered by RustDesk" da tela inicial (opção embutida do próprio RustDesk);
    # o crédito fica na tela Sobre
    cfg.trocar('pub static ref BUILTIN_SETTINGS: RwLock<HashMap<String, String>> = Default::default();',
               'pub static ref BUILTIN_SETTINGS: RwLock<HashMap<String, String>> = '
               'RwLock::new(HashMap::from([("hide-powered-by-me".to_owned(), "Y".to_owned())]));')
    # o servidor aberto do DeskNow não tem contas nem agenda de endereços; sem isto, o botão
    # de login mandaria e-mail e senha para o servidor de contas do RustDesk (admin.rustdesk.com)
    cfg.trocar('pub static ref HARD_SETTINGS: RwLock<HashMap<String, String>> = Default::default();',
               'pub static ref HARD_SETTINGS: RwLock<HashMap<String, String>> = '
               'RwLock::new(HashMap::from([("disable-account".to_owned(), "Y".to_owned()), '
               '("disable-ab".to_owned(), "Y".to_owned())]));')
    arq("src/auth_2fa.rs").trocar('const ISSUER: &str = "RustDesk";', f'const ISSUER: &str = "{nome}";')

    # 2. Dados do programa no Windows (propriedades do .exe do app e do instalador portátil)
    for toml in ("Cargo.toml", "libs/portable/Cargo.toml"):
        cargo = arq(toml)
        cargo.trocar_re(r'(?m)^LegalCopyright = "[^"]*"', f'LegalCopyright = "{copyright_}"')
        cargo.trocar_re(r'(?m)^ProductName = "[^"]*"', f'ProductName = "{nome}"')
        cargo.trocar_re(r'(?m)^FileDescription = "[^"]*"', f'FileDescription = "{nome}"')
    rc = arq("flutter/windows/runner/Runner.rc")
    for campo, valor in (("CompanyName", empresa), ("FileDescription", nome),
                         ("LegalCopyright", copyright_), ("ProductName", nome)):
        rc.trocar_re(rf'VALUE "{campo}", "[^"]*" "\\0"', f'VALUE "{campo}", "{valor}" "\\0"')

    # 3. Android: identificador, nomes visíveis e ícone adaptativo
    arq("flutter/android/app/build.gradle").trocar(
        'applicationId "com.carriez.flutter_hbb"', f'applicationId "{marca["android_id"]}"')
    manifesto = arq("flutter/android/app/src/main/AndroidManifest.xml")
    manifesto.trocar('android:label="RustDesk Input"', f'android:label="{nome} Input"')
    manifesto.trocar('android:label="RustDesk"', f'android:label="{nome}"')
    arq("flutter/android/app/src/main/res/values/strings.xml").trocar("RustDesk", nome)
    for xml in ("ic_launcher.xml", "ic_launcher_round.xml"):
        arq(f"flutter/android/app/src/main/res/mipmap-anydpi-v26/{xml}").trocar(
            '<background android:drawable="@color/ic_launcher_background"/>',
            '<background android:drawable="@mipmap/ic_launcher_background"/>')
    kt = "flutter/android/app/src/main/kotlin/com/carriez/flutter_hbb/"
    arq(kt + "BootReceiver.kt").trocar('"RustDesk is Open"', f'"{nome} is Open"')
    servico = arq(kt + "MainService.kt")
    servico.trocar('const val DEFAULT_NOTIFY_TITLE = "RustDesk"', f'const val DEFAULT_NOTIFY_TITLE = "{nome}"')
    servico.trocar('val channelName = "RustDesk Service"', f'val channelName = "{nome} Service"')
    servico.trocar('description = "RustDesk Service Channel"', f'description = "{nome} Service Channel"')

    # 4. macOS: nome do app, identificador, esquema de link, binário do serviço e ícone da barra
    xc = arq("flutter/macos/Runner/Configs/AppInfo.xcconfig")
    xc.trocar_re(r"(?m)^PRODUCT_NAME = [^\r\n]*", f"PRODUCT_NAME = {nome}")
    xc.trocar_re(r"(?m)^PRODUCT_BUNDLE_IDENTIFIER = [^\r\n]*", f"PRODUCT_BUNDLE_IDENTIFIER = {marca['mac_id']}")
    xc.trocar_re(r"(?m)^PRODUCT_COPYRIGHT = [^\r\n]*", f"PRODUCT_COPYRIGHT = {copyright_}")
    # o MainMenu.xib procura AppDelegate e MainFlutterWindow no módulo Swift "RustDesk":
    # o app muda de nome, o módulo não
    xc.inserir_depois(f"PRODUCT_NAME = {nome}", f"{xc.nl}PRODUCT_MODULE_NAME = RustDesk")
    plist = arq("flutter/macos/Runner/Info.plist")
    plist.trocar("<string>com.carriez.rustdesk</string>", f"<string>{marca['mac_id']}</string>")
    plist.trocar("<string>rustdesk</string>", f"<string>{nome.lower()}</string>")  # esquema desknow://
    arq("build.py").trocar("./build/macos/Build/Products/Release/RustDesk.app/Contents/MacOS/",
                           f"./build/macos/Build/Products/Release/{nome}.app/Contents/MacOS/")
    # a barra de menus do macOS pinta o ícone de uma cor só: usa o símbolo-modelo, não o ladrilho
    arq("src/tray.rs").trocar(
        '"../Frameworks/App.framework/Resources/flutter_assets/assets/icon.png"',
        '"../Frameworks/App.framework/Resources/flutter_assets/assets/icone-bandeja-mac.png"')

    # 5. Interface (Flutter): fonte Geist, cores da marca e telas Sobre
    common = arq("flutter/lib/common.dart")
    for tema in ("lightTheme", "darkTheme"):
        common.inserir_depois(f"static ThemeData {tema} = ThemeData(", f"{common.nl}    fontFamily: 'Geist',")
    pub = arq("flutter/pubspec.yaml")
    n = pub.nl
    pub.inserir_depois(f"{n}  fonts:", (
        f"{n}    - family: Geist{n}      fonts:"
        f"{n}        - asset: assets/fonts/Geist-Regular.ttf"
        f"{n}        - asset: assets/fonts/Geist-Medium.ttf{n}          weight: 500"
        f"{n}        - asset: assets/fonts/Geist-SemiBold.ttf{n}          weight: 600"
        f"{n}        - asset: assets/fonts/Geist-Bold.ttf{n}          weight: 700"))

    mapa = {"0071FF": cores["destaque"], "2C8CFF": cores["botao"], "00B6F0": cores["id"]}
    rx_cor = re.compile(r"0x([0-9A-Fa-f]{2})(0071FF|2C8CFF|00B6F0)(?![0-9A-Fa-f])", re.IGNORECASE)
    for dart in sorted((raiz / "flutter/lib").rglob("*.dart")):
        rel = dart.relative_to(raiz).as_posix()
        texto = arquivos[rel].texto if rel in arquivos else dart.read_bytes().decode("utf-8")
        if rx_cor.search(texto):
            a = arq(rel)
            a.texto = rx_cor.sub(lambda m: "0x" + m.group(1).upper() + mapa[m.group(2).upper()], a.texto)
    if f"0xFF{cores['destaque']}" not in common.texto:
        raise TrechoNaoEncontrado("flutter/lib/common.dart: cor de destaque do RustDesk (0071FF) não encontrada no tema")

    sobre = arq("flutter/lib/desktop/pages/desktop_setting_page.dart")
    sobre.trocar("launchUrlString('https://rustdesk.com/privacy.html');", f"launchUrlString('{privacidade}');")
    sobre.trocar("launchUrlString('https://rustdesk.com');", f"launchUrlString('{repositorio}');")
    sobre.trocar(
        "'Copyright © ${DateTime.now().toString().substring(0, 4)} Purslane Tech Pte. Ltd.\\n$license'",
        "'" + nome + " © ${DateTime.now().toString().substring(0, 4)} " + empresa
        + "\\nBaseado no RustDesk © Purslane Tech Pte. Ltd. Licença AGPL-3.0.\\n$license'")
    sobre.trocar("translate('Slogan_tip'),", f"'Código-fonte: {repositorio}',")

    celular = arq("flutter/lib/mobile/pages/settings_page.dart")
    celular.trocar("const url = 'https://rustdesk.com/';", f"const url = '{repositorio}';")
    celular.trocar("Text('rustdesk.com',", f"Text('{repositorio.split('://', 1)[-1]}',")
    celular.trocar("launchUrlString('https://rustdesk.com/privacy.html')", f"launchUrlString('{privacidade}')")
    celular.inserir_depois("Text('Version: $version'),",
                           f"{celular.nl}        Text('Baseado no RustDesk © Purslane Tech Pte. Ltd. · Licença AGPL-3.0'),")

    # 6. Conferência final: o app tem que sair apontando para o nosso servidor e chave
    final = cfg.texto
    for esperado in (f'RS_PUB_KEY: &str = "{marca["chave_publica"]}"',
                     f'RENDEZVOUS_SERVERS: &[&str] = &["{marca["servidor"]}"]',
                     f'RwLock::new("{nome}".to_owned())'):
        if esperado not in final:
            raise TrechoNaoEncontrado(f"libs/hbb_common/src/config.rs: depois da troca, falta {esperado!r}")

    # 7. Ícones, logos e fontes: desknow/marca/arquivos espelha a raiz do repositório
    origem = PASTA / "marca" / "arquivos"
    fontes = sorted(f for f in origem.rglob("*") if f.is_file()) if origem.is_dir() else []
    if not fontes:
        raise TrechoNaoEncontrado("desknow/marca/arquivos: vazia; rode desknow/ferramentas/gerar-icones.py")
    copiados = []
    for f in fontes:
        rel = f.relative_to(origem).as_posix()
        destino = raiz / rel
        if not (raiz / rel.split("/", 1)[0]).is_dir():
            raise TrechoNaoEncontrado(f"{rel}: a pasta {rel.split('/', 1)[0]} não existe no RustDesk")
        if destino.is_file() and filecmp.cmp(f, destino, shallow=False):
            continue
        copiados.append(rel)
        if gravar:
            destino.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(f, destino)

    alterados = [a.rel for a in arquivos.values() if a.mudou]
    if gravar:
        for a in arquivos.values():
            if a.mudou:
                a.gravar()
    return alterados, copiados


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Aplica a marca DeskNow sobre o código do RustDesk.")
    ap.add_argument("--raiz", type=Path, default=PASTA.parent, help="raiz do código do RustDesk")
    ap.add_argument("--verificar", action="store_true", help="só confere, sem gravar")
    args = ap.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    marca = carregar_marca()
    try:
        alterados, copiados = aplicar(args.raiz.resolve(), marca, gravar=not args.verificar)
    except TrechoNaoEncontrado as erro:
        print(f"ERRO: {erro}", file=sys.stderr)
        print("O código do RustDesk mudou. Ajuste desknow/aplicar-marca.py.", file=sys.stderr)
        return 1
    verbo = "mudaria" if args.verificar else "mudou"
    print(f"Marca {marca['nome']}: {verbo} {len(alterados)} arquivo(s) e "
          f"{'copiaria' if args.verificar else 'copiou'} {len(copiados)} ícone(s)/fonte(s).")
    for rel in alterados:
        print(f"  alterado: {rel}")
    print(f"Servidor: {marca['servidor']} | chave: {marca['chave_publica']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
