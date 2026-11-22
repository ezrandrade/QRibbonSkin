# Atribuições — QRibbonSkin

## ArcSkin (código)

A arquitetura reversível de interface do QRibbonSkin (ocultar e restaurar a
barra de menus, as barras de ferramentas e os painéis do QGIS sem alterar
projetos, camadas ou algoritmos) foi inspirada em **ArcSkin**, por
**EnviroSolutions**: https://github.com/envirosolutionspl/arcskin .
A origem está sob **GNU GPL versão 2**; o QRibbonSkin permanece GPL-2.0.

Até a versão 1.3.0, o pacote incluía ícones SVG reproduzidos do ArcSkin
(`resources/icons/`). A partir da versão 1.3.1 eles foram removidos, pois
deixaram de ser usados.

## RustGIS (disposição da interface)

A disposição da Ribbon (botão Projeto, barra de acesso rápido, busca de
comandos, guias, grupos e tamanhos de controles) segue a interface do
**RustGIS**: https://github.com/opengeos/RustGIS . Nenhum código-fonte,
ícone ou recurso do RustGIS foi copiado.

## Ícones

- Todos os ícones exibidos são os do **tema ativo do QGIS**
  (`QgsApplication.getThemeIcon`) ou os das próprias ações do QGIS, lidos em
  execução, sem alterar a instalação do QGIS.
- Três ícones sem equivalente no QGIS foram desenhados para o QRibbonSkin na
  grade de 24×24 px e na paleta dos ícones do QGIS:
  `resources/icons/qgis_style/classic_interface.svg`,
  `resources/icons/qgis_style/focus_map.svg` e
  `resources/icons/qgis_style/chevron_up.svg`.
- `resources/qribbonskin.svg` e `resources/qribbonskin_toolbar.svg` são os
  ícones do próprio complemento.

A autoria dos ícones do QGIS pertence ao projeto QGIS.
