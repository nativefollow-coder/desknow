# Privacidade do DeskNow

O DeskNow é um app de acesso remoto baseado no [RustDesk](https://github.com/rustdesk/rustdesk). Ele é mantido por Gomes Analist e usa um servidor próprio, `desknow.analistagomes.com`.

## O que passa pelo servidor

- **Para um aparelho achar o outro:** o servidor recebe o ID do aparelho, o endereço IP, a chave pública do aparelho e dados técnicos da conexão, como a versão do app e o sistema operacional.
- **Quando a conexão direta entre os dois aparelhos não é possível:** a sessão passa pelo servidor de relay. Ela é criptografada de ponta a ponta, então o servidor não vê a tela, o áudio, os arquivos nem o chat.

## O que o servidor não guarda

- O conteúdo das sessões: tela, áudio, arquivos transferidos e mensagens.
- A senha de acesso ao aparelho. Ela fica no próprio aparelho e é conferida diretamente entre os dois lados.

## Controle de quem acessa

Ninguém acessa o seu aparelho sem o ID e a senha, ou sem você aceitar o pedido na tela. Você pode trocar a senha ou fechar o DeskNow a qualquer momento.

## Registros

O servidor guarda registros técnicos, como IDs, IPs e horários de conexão, para funcionar e para investigar falhas e abusos.

## Contato

Dúvidas sobre privacidade: abra uma issue no [repositório do DeskNow](https://github.com/nativefollow-coder/desknow/issues).

*Versão inicial (novembro de 2026). Revise este texto antes de distribuir o app a clientes.*
