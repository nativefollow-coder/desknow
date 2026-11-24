# DeskNow: como este fork funciona

O DeskNow é o RustDesk com outra marca e outro servidor. Nesta branch (`desknow`), o código do RustDesk fica **intacto**. A marca entra só na compilação, pelo script `desknow/aplicar-marca.py`.

## Peças

| Arquivo | Para quê |
|---|---|
| `desknow/marca.json` | Nome, identificadores, servidor, chave pública, links e cores. É o único lugar para trocar o nome do app. |
| `desknow/aplicar-marca.py` | Aplica a marca no código do RustDesk. Usa só Python 3, sem dependências. |
| `desknow/testes/` | Testes do script: `python -m unittest discover -s desknow/testes -v` |
| `desknow/marca/arquivos/` | Ícones, logos e fontes prontos. Espelham os caminhos do repositório; o script copia tudo para a raiz. |
| `desknow/ferramentas/gerar-icones.py` | Gera `marca/arquivos/` e `marca/kit/` a partir do símbolo, da fonte Geist e do fundo da logo. Precisa de Pillow e fontTools, e só roda no PC. |
| `desknow/marca/kit/` | Logo e símbolo para uso fora do app (SVG e PNG). |
| `desknow/servidor/compose.yaml` | Servidor de ID e relay (RustDesk Server 1.1.16), igual ao que roda na VPS. |
| `.github/workflows/desknow.yml` | Compila o Windows x64 e o Android aarch64 e publica o release. |

## Compilar

- **Teste:** em Actions, escolha **DeskNow** e depois **Run workflow**. Os instaladores saem como artefatos da execução.
- **Versão publicada:** envie a tag `desknow-v<versão do RustDesk>`, por exemplo `desknow-v1.5.3`. Outra opção é rodar o workflow com `publicar` ligado. O release sai com `DeskNow-<versão>-x86_64.exe` e `DeskNow-<versão>-aarch64.apk`.

O DeskNow usa o mesmo número de versão do RustDesk de propósito: as duas pontas de uma conexão comparam versões para ligar recursos.

## Atualizar o RustDesk

```bash
git fetch upstream
git merge upstream/master        # na branch desknow
python -m unittest discover -s desknow/testes -v
git push
```

Se o RustDesk mudou algum trecho que o script procura, o teste e a compilação param com `ERRO: <arquivo>: trecho não encontrado`. Nesse caso, ajuste o trecho em `aplicar-marca.py` e rode os testes de novo.

## Mudar a marca

1. Edite `desknow/marca.json`.
2. Se o nome mudou, rode `python desknow/ferramentas/gerar-icones.py` para refazer as logos com o nome novo.
3. Rode os testes e faça commit.

## Assinaturas

- **Android:** sem os secrets `ANDROID_SIGNING_KEY`, `ANDROID_ALIAS`, `ANDROID_KEY_STORE_PASSWORD` e `ANDROID_KEY_PASSWORD`, o APK sai assinado com a chave de debug. Ele instala, mas não atualiza uma versão assinada com a chave definitiva.
- **Windows:** sai sem assinatura. Antes de entregar a clientes, compre um certificado de assinatura de código.

## Licença

AGPL-3.0, a mesma do RustDesk (`LICENCE`). O DeskNow é baseado no RustDesk © Purslane Tech Pte. Ltd. O nome e a logo do DeskNow pertencem ao Gomes Analist. A licença do código não dá direito de uso da marca.
