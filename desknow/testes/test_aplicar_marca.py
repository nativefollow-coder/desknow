"""Testes do desknow/aplicar-marca.py (só biblioteca padrão).

Rodar a partir da raiz do repositório:
    python -m unittest discover -s desknow/testes -v
Cada teste trabalha numa cópia dos arquivos que o script mexe; o repositório não é alterado.
"""
from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "desknow" / "aplicar-marca.py"
MARCA = json.loads((REPO / "desknow" / "marca.json").read_text(encoding="utf-8"))

# o que o script lê ou grava, copiado do RustDesk intacto (o repositório não recebe a marca)
PASTAS = ["flutter/lib", "flutter/assets", "flutter/windows/runner", "flutter/macos/Runner",
          "flutter/android/app/src/main", "res"]
ARQUIVOS = ["libs/hbb_common/src/config.rs", "src/auth_2fa.rs", "Cargo.toml",
            "libs/portable/Cargo.toml", "flutter/pubspec.yaml", "flutter/android/app/build.gradle",
            "build.py", "src/tray.rs"]
CONFIG = "libs/hbb_common/src/config.rs"


def montar_copia(destino: Path) -> None:
    for pasta in PASTAS:
        shutil.copytree(REPO / pasta, destino / pasta)
    for arq in ARQUIVOS:
        (destino / arq).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(REPO / arq, destino / arq)


def rodar(raiz: Path, *extra: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(SCRIPT), "--raiz", str(raiz), *extra],
                          capture_output=True, text=True, encoding="utf-8")


def impressao(raiz: Path) -> dict[str, str]:
    return {p.relative_to(raiz).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(raiz.rglob("*")) if p.is_file()}


def ler(raiz: Path, rel: str) -> str:
    return (raiz / rel).read_bytes().decode("utf-8")


class AplicarMarca(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.raiz = Path(self._tmp.name)
        montar_copia(self.raiz)

    def tearDown(self):
        self._tmp.cleanup()

    def test_aplica_em_copia_limpa(self):
        r = rodar(self.raiz)
        self.assertEqual(r.returncode, 0, r.stderr)
        cfg = ler(self.raiz, CONFIG)
        self.assertIn(f'RwLock::new("{MARCA["nome"]}".to_owned())', cfg)
        self.assertIn(f'RENDEZVOUS_SERVERS: &[&str] = &["{MARCA["servidor"]}"]', cfg)
        self.assertIn(f'RS_PUB_KEY: &str = "{MARCA["chave_publica"]}"', cfg)
        self.assertIn('("hide-powered-by-me".to_owned(), "Y".to_owned())', cfg)
        # sem contas: o login não pode mandar credenciais para o servidor de contas do RustDesk
        self.assertIn('("disable-account".to_owned(), "Y".to_owned())', cfg)
        self.assertIn('("disable-ab".to_owned(), "Y".to_owned())', cfg)
        for toml in ("Cargo.toml", "libs/portable/Cargo.toml"):
            texto = ler(self.raiz, toml)
            self.assertIn(f'ProductName = "{MARCA["nome"]}"', texto, toml)
            self.assertNotIn('FileDescription = "RustDesk Remote Desktop"', texto, toml)
        self.assertIn(f'applicationId "{MARCA["android_id"]}"',
                      ler(self.raiz, "flutter/android/app/build.gradle"))
        self.assertNotIn("RustDesk", ler(self.raiz, "flutter/android/app/src/main/res/values/strings.xml"))
        common = ler(self.raiz, "flutter/lib/common.dart")
        self.assertEqual(common.count("fontFamily: 'Geist',"), 2)
        self.assertIn(f"0xFF{MARCA['cores']['destaque'].upper()}", common)
        for dart in (self.raiz / "flutter/lib").rglob("*.dart"):
            self.assertIsNone(re.search(r"0x[0-9A-Fa-f]{2}(0071FF|2C8CFF|00B6F0)",
                                        dart.read_text(encoding="utf-8"), re.IGNORECASE), dart)
        self.assertIn("family: Geist", ler(self.raiz, "flutter/pubspec.yaml"))
        sobre = ler(self.raiz, "flutter/lib/desktop/pages/desktop_setting_page.dart")
        self.assertIn("Baseado no RustDesk", sobre)
        self.assertIn(MARCA["repositorio"], sobre)
        self.assertNotIn("rustdesk.com/privacy", sobre)
        rc = (self.raiz / "flutter/windows/runner/Runner.rc").read_bytes()
        self.assertIn(f'VALUE "ProductName", "{MARCA["nome"]}" "\\0"'.encode("utf-8"), rc)
        self.assertEqual(rc.count(b"\r\n"), rc.count(b"\n"), "Runner.rc perdeu o fim de linha CRLF")
        origem = REPO / "desknow/marca/arquivos/flutter/assets/icon.png"
        self.assertEqual((self.raiz / "flutter/assets/icon.png").read_bytes(), origem.read_bytes())
        self.assertTrue((self.raiz / "flutter/assets/fonts/Geist-SemiBold.ttf").is_file())
        # macOS
        xc = ler(self.raiz, "flutter/macos/Runner/Configs/AppInfo.xcconfig")
        self.assertIn(f"PRODUCT_NAME = {MARCA['nome']}", xc)
        self.assertIn("PRODUCT_MODULE_NAME = RustDesk", xc)
        self.assertIn(f"PRODUCT_BUNDLE_IDENTIFIER = {MARCA['mac_id']}", xc)
        self.assertIn(f"<string>{MARCA['nome'].lower()}</string>", ler(self.raiz, "flutter/macos/Runner/Info.plist"))
        self.assertIn(f"Release/{MARCA['nome']}.app/Contents/MacOS/", ler(self.raiz, "build.py"))
        self.assertIn("assets/icone-bandeja-mac.png", ler(self.raiz, "src/tray.rs"))
        self.assertTrue((self.raiz / "flutter/assets/icone-bandeja-mac.png").is_file())
        icns = REPO / "desknow/marca/arquivos/flutter/macos/Runner/AppIcon.icns"
        self.assertEqual((self.raiz / "flutter/macos/Runner/AppIcon.icns").read_bytes(), icns.read_bytes())
        # o ORG continua o do RustDesk (nomes do serviço no macOS dependem dele)
        self.assertIn('pub static ref ORG: RwLock<String> = RwLock::new("com.carriez".to_owned());', cfg)

    def test_idempotente(self):
        self.assertEqual(rodar(self.raiz).returncode, 0)
        depois_da_primeira = impressao(self.raiz)
        r = rodar(self.raiz)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(impressao(self.raiz), depois_da_primeira)

    def test_falha_quando_trecho_sumiu(self):
        cfg = self.raiz / CONFIG
        texto = cfg.read_text(encoding="utf-8")
        cfg.write_text(re.sub(r".*pub static ref APP_NAME.*\n", "", texto), encoding="utf-8")
        r = rodar(self.raiz)
        self.assertEqual(r.returncode, 1)
        self.assertIn(CONFIG, r.stderr)
        self.assertIn("não encontrado", r.stderr)

    def test_verificar_nao_grava(self):
        antes = impressao(self.raiz)
        r = rodar(self.raiz, "--verificar")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(impressao(self.raiz), antes)


if __name__ == "__main__":
    unittest.main()
