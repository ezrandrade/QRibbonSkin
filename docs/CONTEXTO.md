# QRibbonSkin: contexto do projeto

Documento de passagem para retomar o desenvolvimento, por uma pessoa ou por um assistente de IA. Fica em `docs/`, que não entra no pacote do complemento (`.gitattributes`).

Situação em 22/11/2026: **desenvolvimento encerrado na versão 1.6.2**, homologada pelo autor.

## 1. O que é

Complemento do QGIS que troca menus e barras por uma **Ribbon com a disposição do RustGIS** (https://github.com/opengeos/RustGIS). Os ícones, as cores, os comandos e as traduções são **os do próprio QGIS**. O complemento é reversível, ou seja, desligá-lo devolve a interface clássica. A página inicial do QGIS não é alterada, e o mapa-múndi do RustGIS ficou de fora de propósito.

- Repositório: https://github.com/ezrandrade/QRibbonSkin (branch `main`)
- Autor: Esdras Andrade, com atribuição ao ArcSkin (ver `ATTRIBUTION.md`). Licença GPL (`LICENSE`).
- Publicado no plugins.qgis.org com o nome de pacote **`qribbonskin`**, todo em minúsculas.
- Compatibilidade declarada: QGIS 3.44 LTR (Qt5/PyQt5) até 4.99 (Qt6/PyQt6).

### Homologação da 1.6.2 (feita pelo autor)

| Sistema | QGIS 3.44.15 | QGIS 4.2.2 |
|---|---|---|
| Windows 11 26H2 | aprovado | aprovado |
| Ubuntu 26.04 LTS (Flatpak) | aprovado | aprovado |

## 2. Funcionalidades

- **Janela principal:** botão Projeto, com os comandos de projeto exibidos dentro da própria Ribbon e não em menu suspenso; barra de acesso rápido; busca de comandos (Spotlight, Alt+Q); e 11 guias: Início, Dados, Estilo, Rotulagem, Editar, Analisar, Exibir, Publicar, Complementos, Configurações e Ajuda. As guias Dados, Estilo e Rotulagem mudam conforme a camada selecionada. A Ribbon recolhe com Ctrl+F1.
- **Editores:** o Compositor de Layout, o Georreferenciador e o Designer de Modelos usam o mesmo componente de Ribbon.
- **Tabela de atributos:** tem Ribbon própria (guias Início, Campos e Configurações), tanto flutuante quanto acoplada. Acoplada, começa recolhida e deixa Alt+Q e Ctrl+F1 para a Ribbon principal.
- **Guia Complementos:** um botão por complemento instalado. Se o complemento tem um só comando, o botão o executa direto; se tem vários, abre um menu.
- **Ativar:** Exibir > Ativar interface QRibbonSkin. **Desativar:** Configurações > Interface clássica, ou Ctrl+Alt+Shift+R. **Emergência:** Exibir > Recuperar barras do QGIS.
- **Idiomas:** português brasileiro e inglês (`i18n.py`).

## 3. Decisões aprovadas pelo autor (não reverter sem consultá-lo)

1. **Só comandos nativos.** Todo controle é uma `QAction` ou um `QMenu` nativo do QGIS, localizado pelo `objectName`. Nenhuma ação é removida: as barras nativas são apenas ocultadas e depois restauradas.
2. **Ícones** no tamanho nativo de 24 px, sem ampliar ícones bitmap. Só existem três SVG próprios, desenhados no padrão QGIS (`resources/icons/qgis_style/`), além dos ícones do complemento.
3. **Medidas derivadas da fonte**, para que as legendas não sejam cortadas com fonte grande, escala do Windows ou a fonte do Qt5. A largura das guias é calculada com a fonte em negrito da guia ativa (`RibbonTabBar`).
4. **Sem redundâncias, pelo critério do RustGIS:** nenhum comando aparece duas vezes na mesma guia; repetição entre guias só onde o RustGIS também repete. Exceções pedidas pelo autor: Selecionar e Limpar seleção também ficam na guia Editar, e o Georreferenciador fica sempre visível na guia Dados (grupo Alinhamento).
5. **Botão pequeno sozinho numa coluna vira botão grande.**
6. **Sem linha escura** sob a Ribbon. As cores vêm da paleta do tema ativo, inclusive nos temas escuros.
7. **Spotlight** é um painel dentro da janela do QGIS, e não um popup de nível superior, porque no sistema do autor o popup não aparecia centralizado. Abre só com o campo de busca, centralizado, e os resultados crescem para baixo, até 8 linhas.
8. **Leveza:** nada de filtros de eventos globais nem de temporizadores. A detecção usa sinais do QGIS, `QApplication.focusChanged`, o `triggered` das ações que abrem janelas e o evento `ChildAdded` da janela principal.
9. **Painéis:** ao desligar o complemento ou fechar o QGIS, só se restauram os painéis que o próprio QRibbonSkin ocultou (modo Mapa em foco). Esse foi o bug corrigido na 1.6.2: o Navegador reabria a cada inicialização.

## 4. Arquitetura (cerca de 4.800 linhas)

| Arquivo | Papel |
|---|---|
| `plugin.py` | Ciclo de vida (`initGui`/`unload`, ativar e desativar), ocultar e restaurar barras e menus, modo Mapa em foco (`_focus_snapshot`), sincronização de barras de complementos via `ChildAdded`. Registra `QRibbonSkin <versão> ativo (<pasta>)` no log. |
| `ribbon.py` | `RibbonFrame` (componente genérico), `RibbonWidget` (janela principal), `RibbonTabBar`, `Spotlight`, `Metrics`, `collect_commands`, grupos de complementos, `is_native_action`. |
| `ribbon_spec.py` | Especificação declarativa das guias e grupos da janela principal. |
| `editor_specs.py` | Especificações de Layout, Georreferenciador, Designer de Modelos e Tabela de atributos (`TABLE_ACTIONS`, `TABLE_DOCK`). |
| `editors.py` | `EditorSession`, gerenciadores dos editores, `AttributeTableRibbon`, `AttributeTableSession`, `AttributeTableManager`. A busca usa `QApplication.allWidgets()`, porque a tabela flutuante é um `QDialog` sem pai. |
| `compat.py` | Importações que diferem entre Qt5 e Qt6 (`QAction` e `QShortcut` ficam em QtWidgets no Qt5 e em QtGui no Qt6). |
| `i18n.py` | Dicionário de inglês (os textos do código estão em português). |

**Sintaxe das specs:** `"nome4|nome3"` dá nomes alternativos para QGIS 4 e 3.44 (o Processing é um complemento Python no 3.44: `toolboxAction`, `modelerAction` etc.); `"menu:<objectName>"` insere um menu nativo; `"native:..."` e `"key:<StandardKey>"` usam outros resolvedores. Os itens de layout são classificados pelo tipo, via `QgsGui.layoutItemGuiRegistry()`. Recursos ausentes no 3.44 (digitalização Bézier/NURBS, contagem de feições no Designer de Modelos) são omitidos automaticamente.

**Identidade de objetos:** `qt_key()` usa `sip.unwrapinstance`, porque wrappers Python diferentes podem apontar para o mesmo objeto C++.

## 5. Empacotamento e publicação

```bash
git archive --format=zip --prefix=qribbonskin/ HEAD -o QRibbonSkin_vX.Y.Z.zip
```

- A pasta raiz do zip **precisa** se chamar `qribbonskin`. Com outro nome, o site recusa o envio ("Plugin folder name mismatch").
- `docs/` e `.gitattributes` ficam fora do zip. Não faça commit de `__pycache__/`.
- Antes de enviar, rode os critérios do plugins.qgis.org: Bandit `-ll` sem achados, detect-secrets sem achados, flake8 com `max-line-length=120` sem avisos, nenhum `.py` executável, nenhum arquivo oculto ou suspeito, `LICENSE` presente, `metadata.txt` válido e URLs acessíveis. A 1.6.2 passou em todos.
- Ao lançar uma versão: atualize `version`, `about` e `changelog` em `metadata.txt` (a versão mais nova fica em `changelog=` e as anteriores em linhas `; x.y.z - ...`) e o README (tabela de compatibilidade e histórico).
- Tags: as do repositório são v1.0.0, v1.1.30, v1.1.44, v1.4.3, v1.5.1 e v1.6.2. Nas sessões em nuvem do Claude, o push de tags foi bloqueado (403), então releases e tags são criadas pela página do GitHub.
- No Linux, uma pasta antiga `QRibbonSkin` instalada à mão coexiste com `qribbonskin` e carrega o complemento duas vezes. Apague-a antes de instalar.

## 6. Testes

Não há suíte automatizada no repositório. Durante o desenvolvimento foi usado um ambiente de testes offscreen, fora do repositório e já descartado: o `qgisapp.ui` real e os `.ui` dos editores do QGIS (master e release-3_44), com stubs de `qgis.core` e `qgis.gui`, rodando em PyQt6 e em PyQt5. Se o desenvolvimento for retomado, vale recriá-lo dentro do repositório (por exemplo, em `tests/`, com `export-ignore`) e acrescentar uma verificação do nome da pasta no zip.

## 7. Pendências conhecidas e ideias não feitas

- `.gitignore` para `__pycache__/` e `*.pyc` (com `.gitignore export-ignore`): sugerido, não feito.
- Verificação automática do nome da pasta do zip antes do envio: sugerida, não feita.
- A homologação foi manual, nos quatro cenários da tabela. Não foi testado em macOS nem em QGIS 3.44 instalado via OSGeo4W com Qt6.

## 8. Histórico resumido

Versão 1.0 até 1.1.44: base original (ArcSkin adaptado). 1.2.x: Ribbon reescrita no padrão RustGIS, com ícones nativos e Spotlight. 1.3.x: editores com a mesma Ribbon e limpeza de cerca de 9.650 para 4.400 linhas. 1.4.x: guia Complementos com um botão por complemento; Selecionar e Limpar seleção na guia Editar. 1.5.x: suporte ao QGIS 3.44 LTR (Qt5), correção das guias cortadas e conformidade com o scanner de segurança. 1.6.x: Ribbon na tabela de atributos, tabela flutuante e correção dos painéis reabertos. O histórico detalhado está em `metadata.txt` (changelog) e no README.
