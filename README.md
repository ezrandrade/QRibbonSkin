# QRibbonSkin 1.0.0

O **QRibbonSkin** oferece ao QGIS 4.x uma interface de guias no estilo Ribbon, reversível, construída a partir dos comandos nativos do QGIS. Não substitui nem altera os algoritmos de geoprocessamento.

## Recursos

- Interface de guias com seção **Principal** dedicada ao fluxo de trabalho SIG.
- Menus suspensos que preservam as ações nativas do QGIS.
- Integração de complementos instalados e atualização dos menus.
- Barra de acesso rápido e busca centralizada de comandos pelo atalho **Alt+Q**.
- Adaptação das interfaces do Editor de Layout e do Georreferenciador.
- Português brasileiro e inglês, conforme o idioma da interface do QGIS.
- Retorno à interface clássica e recuperação de barras e painéis.

## Compatibilidade verificada

| Sistema | QGIS | Resultado |
|---|---|---|
| Windows 10 | 4.0 | Homologado |
| Windows 11 26H2 | 4.2.2 | Homologado |
| Ubuntu Linux 26.04 (Flatpak) | 4.2.3 | Homologado |

Essas validações foram comunicadas pelo responsável pelos testes; não constituem garantia de compatibilidade com todas as configurações do QGIS.

## Instalação

1. Abra **Complementos → Gerenciar e Instalar Complementos** no QGIS 4.x.
2. Escolha **Instalar a partir de ZIP** e selecione o arquivo distribuído.
3. Ative o QRibbonSkin. A opção de retorno à interface clássica fica na guia **Interface**; o complemento também pode ser desativado pelo gerenciador de complementos.

## Utilização

Use a guia **Principal** para adicionar camadas, navegar, selecionar feições, medir, identificar, acessar a tabela de atributos, processar dados e criar layouts. As outras guias apresentam as ferramentas do QGIS e de complementos instalados. A opção **Interface → Atualizar Menus** permite atualizar a listagem quando extensões forem instaladas ou removidas.

## Licença e créditos

Consulte `LICENSE` e `ATTRIBUTION.md`. A implementação contém trabalho derivado/inspirado no ArcSkin, com as atribuições preservadas. O estilo de interface foi influenciado visualmente pelo RustGIS, sem incorporar seu código.

## Código-fonte, suporte e publicação

Para publicação no repositório oficial de plugins do QGIS, será necessário vincular uma página pública do projeto, um repositório de código-fonte e um rastreador de problemas. Esses endereços não foram definidos neste pacote; não são inventados nos metadados.
