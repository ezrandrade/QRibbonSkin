# QRibbonSkin 1.4.0

O **QRibbonSkin** oferece ao QGIS 4.x uma interface Ribbon reversível com a **mesma disposição da Ribbon do RustGIS**, construída exclusivamente com comandos, menus, ícones e cores **nativos do QGIS**. Não substitui nem altera os algoritmos de geoprocessamento, e a **página inicial original do QGIS** é preservada.

## Recursos

- Disposição do RustGIS: barra de acesso rápido (Novo, Abrir, Salvar, Desfazer, Refazer, Histórico) e **Buscar comandos** no topo; **Alt+Q** abre o Spotlight: um campo de busca centralizado na janela do QGIS, cujos resultados aparecem abaixo à medida que são encontrados; botão **Projeto** e as guias **Início, Dados, Estilo, Rotulagem, Editar, Analisar, Exibir, Publicar, Complementos, Configurações e Ajuda**; grupos rotulados com botões grandes (ícone 24 px) e pequenos (ícone 16 px, até três por coluna; um botão pequeno que ficaria sozinho na coluna é exibido como grande).
- Guias **Dados, Estilo e Rotulagem contextuais**: mostram ferramentas de vetor ou de raster conforme a camada selecionada no painel Camadas, como no RustGIS.
- **Recolher/expandir** a Ribbon pelo chevron, por duplo clique numa guia ou **Ctrl+F1**; com a Ribbon recolhida, clicar numa guia a exibe temporariamente.
- Setas de rolagem nas bordas quando a janela é estreita (também roda do mouse).
- **Somente objetos nativos**: cada botão reutiliza a QAction do próprio QGIS (ícone, tradução da dica, estado habilitado/marcado, atalho); os menus suspensos de Vetor, Raster, Banco de dados, Web, Malha, Processamento e Complementos são os **próprios menus do QGIS**, portanto entradas de complementos aparecem automaticamente, sem varredura.
- **Cores do tema ativo do QGIS** (inclusive temas escuros), também nos editores de Layout, Georreferenciador e Designer de Modelos; painéis do QGIS mantêm a aparência nativa.
- O botão **Projeto** mostra na própria Ribbon os comandos nativos de projeto (novo, abrir, recentes, modelos, armazenamento, layouts, importar/exportar, propriedades): a página inicial do QGIS não é substituída.
- Ícones grandes em 24 px e pequenos em 16 px, os tamanhos para os quais o tema do QGIS os desenha; alturas derivadas da fonte da interface.
- Atalhos de teclado nativos continuam funcionando com a barra de menus oculta.
- Sem redundâncias: dentro de uma guia nenhum comando aparece duas vezes (os menus nativos usados como botões suspensos omitem o que já tem botão na guia); entre guias, só as repetições que o RustGIS também faz (tabela de atributos, seleção por atributos/localização e Exibir › Janelas espelhando os painéis). A guia Complementos mostra só o gerenciador e o conteúdo dos complementos instalados.
- Georreferenciador sempre visível na guia **Dados** (grupo Alinhamento).
- **Complementos** como no RustGIS: o Gerenciador de complementos e **um grupo por complemento instalado**, com os comandos que ele adicionou aos menus do QGIS (Complementos, Vetor, Raster, Banco de dados, Web, Malha, Processamento), a um menu próprio ou à sua barra de ferramentas, sem repetir o mesmo comando. Se a barra do complemento tiver controles que só funcionam nela (como caixas de seleção), o grupo oferece um botão para mostrá-la. A guia é remontada apenas quando um complemento é instalado, ativado ou removido. Os comandos do próprio QGIS (incluindo os algoritmos do Processing) permanecem nas guias de origem; um complemento que nomeie seus comandos no padrão interno do QGIS (`mAction…`) seria tratado como comando do QGIS.
- Leve: sem temporizadores e sem filtros de eventos globais; janelas detectadas por sinais do QGIS, mudança de foco e criação de barras; guias montadas sob demanda.
- Retorno à interface clássica (Configurações → Interface clássica, ou Ctrl+Alt+Shift+R) e recuperação de barras e painéis.

Ícones: usados os do tema do QGIS (`QgsApplication.getThemeIcon`). Apenas três comandos sem equivalente no QGIS (Interface clássica, Mapa em foco e Recolher a Ribbon) usam ícones novos, desenhados na grade 24×24 e na paleta dos ícones do QGIS (`resources/icons/qgis_style`).

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
3. Ative o QRibbonSkin. A opção de retorno à interface clássica fica na guia **Configurações**; o complemento também pode ser desativado pelo gerenciador de complementos.

## Utilização

Use a guia **Início** para navegar, adicionar dados, selecionar, medir e identificar; **Dados**, **Estilo** e **Rotulagem** para a camada selecionada; **Editar** para edição vetorial; **Analisar** para a Caixa de Ferramentas, o Designer de Modelos e os menus Vetor/Raster/Malha/Banco de dados; **Exibir** para painéis, decorações e vistas; **Publicar** para layouts, relatórios e exportação; **Complementos** para o gerenciador e os comandos de cada complemento instalado, agrupados por complemento.

## Licença e créditos

Consulte `LICENSE` e `ATTRIBUTION.md`. A arquitetura reversível foi inspirada no ArcSkin, com a atribuição preservada. O estilo de interface foi influenciado visualmente pelo RustGIS, sem incorporar seu código.

## Código-fonte, suporte e publicação

Para publicação no repositório oficial de plugins do QGIS, será necessário vincular uma página pública do projeto, um repositório de código-fonte e um rastreador de problemas. Esses endereços não foram definidos neste pacote; não são inventados nos metadados.


### Janelas de edição / Editor windows (v1.3.0)

O **Compositor de Layout**, o **Georreferenciador** e o **Designer de Modelos** recebem a mesma Ribbon da janela principal: mesmo componente, ícones nativos em 24 px, cores do tema do QGIS, Spotlight (**Alt+Q**) e a mesma regra contra redundâncias. Cada janela tem seu botão no estilo "Projeto" (**Layout**, **Arquivo**, **Modelo**).

- **Layout:** a guia Início segue os grupos de layout do RustGIS (Página, Quadros de mapa, Elementos de mapa, Formas, Texto e imagens, Exportar). Os botões de inserir itens vêm do registro de itens do QGIS e são classificados pelo tipo do item, com os nomes traduzidos pelo próprio QGIS. As guias **Atlas** e **Relatório** aparecem conforme o tipo de documento aberto.
- **Georreferenciador:** pontos de controle, transformação e navegação na guia Início; vínculo com o QGIS e realce em Exibir.
- **Designer de Modelos:** a ordem segue a barra do ModelBuilder do RustGIS (executar, editar, organizar, navegar).

As barras e menus originais de cada janela ficam apenas ocultos (**Configurações → Barras nativas** os mostra novamente) e são restaurados ao fechar a janela ou desativar o QRibbonSkin; nenhuma ação é removida delas e nenhum painel é estilizado.

**English:** the Layout Designer, Georeferencer and Model Designer share the main window's Ribbon component (native icons, theme colours, Alt+Q Spotlight). Native toolbars are only hidden and are restored on close; nothing is removed from them.
