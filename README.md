# Troca de rede

Um interruptor de rede para Windows, em forma de widget de área de trabalho. Com um clique ele alterna entre Wi-Fi e Ethernet: para um lado, habilita o Wi-Fi e desabilita a rede cabeada; para o outro, faz o contrário.

```
   Wi-Fi  ( ●   )  Ethernet
          Wi-Fi ativo
```

## Requisitos

- Windows 10 ou 11
- Python 3 (com o `tkinter`, que já vem no instalador oficial)
- Conta com permissão de administrador

Não há dependências externas: só a biblioteca padrão do Python e o PowerShell do Windows.

## Como usar

Dê dois cliques em `troca_rede.pyw`, ou rode:

```
pythonw troca_rede.pyw
```

O Windows pede confirmação de administrador, porque habilitar e desabilitar adaptadores de rede exige esse privilégio. O widget aparece no canto inferior direito da tela.

| Ação | Como |
| --- | --- |
| Trocar de rede | Clique no widget (ou tecle Espaço) |
| Mover | Arraste; a posição fica salva |
| Opções | Botão direito |
| Fechar | Botão direito → Fechar (ou Esc) |

### Opções do menu

- **Sempre visível**: mantém o widget por cima das outras janelas.
- **Iniciar com o Windows**: cria uma tarefa agendada (`InterruptorDeRede`) que abre o widget no logon já com privilégio elevado, sem pedir confirmação a cada vez. Desmarcar a opção remove a tarefa.

## Como funciona

- Os adaptadores são detectados automaticamente com `Get-NetAdapter -Physical`, pelo tipo de mídia (802.11 para Wi-Fi, 802.3 para Ethernet). Não é preciso configurar nomes.
- A troca usa `Enable-NetAdapter` no adaptador de destino e `Disable-NetAdapter` no outro.
- Depois de cada troca, o widget relê o estado real dos adaptadores, então o que ele mostra é sempre o que está valendo no sistema.
- Se os dois adaptadores estiverem habilitados (ou os dois desabilitados), o botão fica no meio; clique no lado desejado.
- A posição e a opção "Sempre visível" ficam em `%APPDATA%\troca_rede.json`.

## Observações

- Se você passar para Ethernet sem o cabo conectado, fica sem rede até voltar para o Wi-Fi.
- Em máquinas com mais de um adaptador do mesmo tipo, o widget usa o primeiro que encontrar.
- Só uma instância do widget roda por vez.
