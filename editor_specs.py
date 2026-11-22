"""Declarative Ribbons of the QGIS editor windows (Qt-free, testable).

Same vocabulary and rules as ribbon_spec.py (one component, one look):
every name is a QAction/QMenu objectName from the editor's own QGIS .ui file
(src/ui/layout/qgslayoutdesignerbase.ui,
src/ui/georeferencer/qgsgeorefpluginguibase.ui,
src/ui/processing/models/qgsmodeldesignerdialogbase.ui), ``key:<StandardKey>``
for QGIS actions created in C++ without objectName but with a standard
shortcut (Cut, Copy, Paste, Undo, Redo), or a QRibbonSkin interface command.

Layout Designer: its first tab follows the RustGIS layout groups (Page, Map
Frames, Map Surrounds, Shapes, Text, Export). The "Add item" commands are
created by QGIS from its layout item registry, so they are ``dynamic``
items classified by item *type* (never by translated text).
Georeferencer and Model Designer have no RustGIS counterpart window; they use
the same Ribbon language with groups taken from QGIS's own toolbars/menus
(the Model Designer's order follows RustGIS ModelBuilder's toolbar).
"""

from .ribbon_spec import big, small, split, menu, col, group, COMMAND_SEARCH, TOGGLE_RIBBON

NATIVE_BARS = "qrs.native_bars"


def dynamic(source, size="big"):
    """Controls produced at run time by the editor Ribbon (layout items)."""
    return {"kind": "dynamic", "source": source, "size": size}


_COMMON_LABELS = {
    COMMAND_SEARCH: "Buscar\ncomandos",
    TOGGLE_RIBBON: "Recolher a Ribbon",
    NATIVE_BARS: "Barras\nnativas",
}
_COMMON_ICONS = {
    COMMAND_SEARCH: "/search.svg",
    TOGGLE_RIBBON: "qrs:chevron_up.svg",
    NATIVE_BARS: "/mActionInterfaceCustomization.svg",
}
_COMMON_TIPS = {
    COMMAND_SEARCH: "Buscar e executar qualquer comando desta janela (Alt+Q)",
    TOGGLE_RIBBON: "Recolher ou expandir a Ribbon (Ctrl+F1)",
    NATIVE_BARS: "Mostrar ou ocultar as barras e menus originais desta janela",
}


def _ribbon_group():
    return group("QRibbonSkin",
                 big(NATIVE_BARS),
                 col(small(TOGGLE_RIBBON)))


class LayoutSpec:
    """QGIS Layout Designer (print layouts and reports)."""

    COMMAND_LABELS = dict(_COMMON_LABELS)
    COMMAND_ICONS = dict(_COMMON_ICONS)
    COMMAND_TIPS = dict(_COMMON_TIPS)
    QUICK_ACCESS = ("mActionSaveProject", "key:Undo", "key:Redo")
    PROJECT_TAB = "layout"
    PROJECT_BUTTON = ("Layout", "Salvar, criar e gerenciar layouts")
    GLOBAL_DEDUP_TABS = ("settings",)
    TABS = (
        ("home", "Início"),
        ("edit", "Editar"),
        ("arrange", "Organizar"),
        ("view", "Exibir"),
        ("atlas", "Atlas", "menu:mMenuAtlas"),
        ("report", "Relatório", "menu:mMenuReport"),
        ("settings", "Configurações"),
    )
    GROUPS = {
        "layout": (
            group("Layout",
                  big("mActionSaveProject", "Salvar\nprojeto"),
                  big("mActionNewLayout", "Novo"),
                  big("mActionDuplicateLayout", "Duplicar"),
                  col(small("mActionRenameLayout", "Renomear", "/mActionEditTable.svg"),
                      small("mActionRemoveLayout", "Excluir"))),
            group("Gerenciar",
                  big("mActionLayoutManager", "Gerenciador\nde layouts"),
                  menu("Layouts", "/mActionComposerManager.svg", ("menu:mLayoutsMenu",))),
            group("Modelos",
                  big("mActionSaveAsTemplate", "Salvar como\nmodelo"),
                  big("mActionLoadFromTemplate", "Itens de\nmodelo")),
            group("Propriedades",
                  big("mActionLayoutProperties", "Propriedades\ndo layout",
                      "/propertyicons/settings.svg"),
                  col(small("mActionClose", "Fechar", "/mIconClose.svg"))),
        ),
        "home": (
            group("Página",
                  big("mActionAddPages", "Adicionar\npáginas"),
                  col(small("mActionPageProperties", "Propriedades da página",
                            "/propertyicons/general.svg"),
                      small("mActionSnapGrid", "Aderir à grade", "/mIconSnapping.svg"),
                      small("mActionShowRulers", "Réguas", "/mActionMeasure.svg")),
                  col(small("mActionClearGuides", "Limpar guias", "/mIconClearItem.svg"))),
            group("Quadros de mapa",
                  dynamic("map_frames"),
                  big("mActionMoveItemContent", "Mover\nconteúdo"),
                  col(small("mActionRefreshView", "Atualizar"))),
            group("Elementos de mapa", dynamic("surrounds")),
            group("Formas", dynamic("shapes")),
            group("Texto e imagens", dynamic("text")),
            group("Exportar",
                  big("mActionExportAsPDF", "Exportar\nPDF"),
                  big("mActionExportAsImage", "Exportar\nimagem"),
                  big("mActionPrint", "Imprimir"),
                  col(small("mActionExportAsSVG", "Exportar SVG"),
                      small("mActionPageSetup", "Configurar página", "/mActionFilePrint.svg"))),
        ),
        "edit": (
            group("Ferramentas",
                  big("mActionSelectMoveItem", "Selecionar/\nmover"),
                  big("mActionPan", "Mover\nlayout"),
                  big("mActionEditNodesItem", "Editar\nnós"),
                  col(small("mActionZoomTool", "Zoom"))),
            group("Área de transferência",
                  split("key:Paste", ("key:Paste", "mActionPasteInPlace"), "Colar",
                        "/mActionEditPaste.svg"),
                  col(small("key:Cut", "Recortar", "/mActionEditCut.svg"),
                      small("key:Copy", "Copiar", "/mActionEditCopy.svg"))),
            group("Histórico",
                  col(small("key:Undo", "Desfazer", "/mActionUndo.svg"),
                      small("key:Redo", "Refazer", "/mActionRedo.svg"))),
            group("Seleção",
                  big("mActionSelectAll", "Selecionar\ntudo"),
                  col(small("mActionDeselectAll", "Desmarcar"),
                      small("mActionInvertSelection", "Inverter")),
                  col(small("mActionSelectNextAbove", "Item acima", "/mActionArrowUp.svg"),
                      small("mActionSelectNextBelow", "Item abaixo", "/mActionArrowDown.svg")),
                  big("mActionDeleteSelection", "Excluir")),
        ),
        "arrange": (
            group("Agrupar",
                  big("mActionGroupItems", "Agrupar"),
                  big("mActionUngroupItems", "Desagrupar")),
            group("Ordem",
                  col(small("mActionRaiseItems", "Avançar"),
                      small("mActionLowerItems", "Recuar")),
                  col(small("mActionMoveItemsToTop", "Trazer para a frente"),
                      small("mActionMoveItemsToBottom", "Enviar para trás"))),
            group("Alinhamento",
                  menu("Alinhar", "/mActionAlignLeft.svg", ("menu:menuAlign_Items",)),
                  menu("Distribuir", "/mActionDistributeHSpace.svg",
                       ("menu:menu_Distribute_Items",)),
                  menu("Redimen-\nsionar", "/mActionResizeWidest.svg", ("menu:menuResize",))),
            group("Bloqueio",
                  big("mActionLockItems", "Bloquear"),
                  big("mActionUnlockAll", "Desbloquear\ntudo")),
        ),
        "view": (
            group("Navegar",
                  big("mActionZoomAll", "Zoom\ntotal"),
                  col(small("mActionZoomIn", "Aproximar"),
                      small("mActionZoomOut", "Afastar"),
                      small("mActionZoomActual", "Zoom 100%")),
                  col(small("mActionZoomToWidth", "Largura da página",
                            "/mActionZoomToArea.svg"))),
            group("Grade e guias",
                  col(small("mActionShowGrid", "Mostrar grade"),
                      small("mActionShowGuides", "Mostrar guias", "/mActionAddArrow.svg"),
                      small("mActionSnapGuides", "Aderir às guias", "/mIconSnappingSegment.svg")),
                  col(small("mActionSmartGuides", "Guias inteligentes",
                            "/mIconSnappingIntersection.svg"),
                      small("mActionManageGuides", "Gerenciar guias",
                            "/propertyicons/general.svg"))),
            group("Mostrar",
                  col(small("mActionShowBoxes", "Caixas delimitadoras",
                            "/mActionAddBasicRectangle.svg"),
                      small("mActionShowPage", "Páginas", "/mActionNewPage.svg"))),
            group("Efeitos",
                  menu("Visão de\ncores", "/mIconColorWheel.svg", ("menu:menuPreview",))),
            group("Janelas",
                  menu("Painéis", "/mDockify.svg", ("menu:mPanelsMenu",)),
                  col(small("mActionHidePanels", "Painéis visíveis", "/mDockify.svg"),
                      small("mActionToggleFullScreen", "Tela cheia",
                            "/mActionZoomFullExtent.svg"))),
        ),
        "atlas": (
            group("Visualizar",
                  big("mActionAtlasPreview", "Visualizar\natlas")),
            group("Navegar",
                  col(small("mActionAtlasFirst", "Primeira feição"),
                      small("mActionAtlasPrev", "Feição anterior")),
                  col(small("mActionAtlasNext", "Próxima feição"),
                      small("mActionAtlasLast", "Última feição"))),
            group("Exportar",
                  big("mActionExportAtlasAsPDF", "Exportar\nPDF"),
                  big("mActionPrintAtlas", "Imprimir\natlas"),
                  col(small("mActionExportAtlasAsImage", "Exportar imagens"),
                      small("mActionExportAtlasAsSVG", "Exportar SVG"))),
            group("Configurar",
                  big("mActionAtlasSettings", "Configurações\ndo atlas")),
        ),
        "report": (
            group("Exportar",
                  big("mActionExportReportAsPDF", "Exportar\nPDF"),
                  big("mActionPrintReport", "Imprimir\nrelatório"),
                  col(small("mActionExportReportAsImage", "Exportar imagens"),
                      small("mActionExportReportAsSVG", "Exportar SVG"))),
            group("Configurar",
                  big("mActionReportSettings", "Configurações\ndo relatório")),
        ),
        "settings": (
            group("Personalizar",
                  big("mActionOptions", "Opções do\nlayout"),
                  big("mActionKeyboardShortcuts", "Atalhos de\nteclado")),
            _ribbon_group(),
        ),
    }


class GeoreferencerSpec:
    """QGIS Georeferencer window."""

    COMMAND_LABELS = dict(_COMMON_LABELS)
    COMMAND_ICONS = dict(_COMMON_ICONS)
    COMMAND_TIPS = dict(_COMMON_TIPS)
    QUICK_ACCESS = ("mActionOpenRaster", "mActionLoadGCPpoints", "mActionSaveGCPpoints",
                    "mActionStartGeoref")
    PROJECT_TAB = "file"
    PROJECT_BUTTON = ("Arquivo", "Abrir raster ou vetor, carregar e salvar pontos")
    TABS = (
        ("home", "Início"),
        ("view", "Exibir"),
        ("settings", "Configurações"),
    )
    GROUPS = {
        "file": (
            group("Abrir",
                  big("mActionOpenRaster", "Abrir\nraster"),
                  big("mActionOpenVector", "Abrir\nvetor"),
                  big("mActionReset", "Redefinir")),
            group("Pontos de controle",
                  big("mActionLoadGCPpoints", "Carregar\npontos"),
                  big("mActionSaveGCPpoints", "Salvar\npontos")),
            group("Janela",
                  col(small("mActionQuit", "Fechar", "/mIconClose.svg"))),
        ),
        "home": (
            group("Pontos de controle",
                  big("mActionAddPoint", "Adicionar\nponto"),
                  big("mActionMoveGCPPoint", "Mover\nponto"),
                  big("mActionDeletePoint", "Excluir\nponto"),
                  col(small("mActionAdvancedDigitizingDock", "Digitalização avançada",
                            "/cadtools/cad.svg"))),
            group("Georreferenciar",
                  big("mActionTransformSettings", "Configurações\nde transformação"),
                  big("mActionStartGeoref", "Iniciar"),
                  col(small("mActionGDALScript", "Script GDAL"))),
            group("Navegar",
                  big("mActionPan", "Mover"),
                  col(small("mActionZoomIn", "Aproximar"),
                      small("mActionZoomOut", "Afastar"),
                      small("mActionZoomToLayer", "Zoom na camada")),
                  col(small("mActionZoomLast", "Anterior"),
                      small("mActionZoomNext", "Próxima"))),
        ),
        "view": (
            group("Vínculo com o QGIS",
                  big("mActionLinkGeorefToQgis", "Vincular\nao QGIS"),
                  big("mActionLinkQGisToGeoref", "Vincular\ndo QGIS")),
            group("Realce",
                  col(small("mActionFullHistogramStretch", "Histograma total"),
                      small("mActionLocalHistogramStretch", "Histograma local"))),
        ),
        "settings": (
            group("Georreferenciador",
                  big("mActionSourceProperties", "Propriedades\nda fonte",
                      "/propertyicons/system.svg"),
                  big("mActionGeorefConfig", "Configurar")),
            _ribbon_group(),
        ),
    }


class ModelDesignerSpec:
    """QGIS Processing Model Designer (order of RustGIS ModelBuilder)."""

    COMMAND_LABELS = dict(_COMMON_LABELS)
    COMMAND_ICONS = dict(_COMMON_ICONS)
    COMMAND_TIPS = dict(_COMMON_TIPS)
    QUICK_ACCESS = ("mActionNew", "mActionOpen", "mActionSave", "key:Undo", "key:Redo",
                    "mActionRun")
    PROJECT_TAB = "model"
    PROJECT_BUTTON = ("Modelo", "Criar, abrir, salvar e exportar modelos")
    TABS = (
        ("home", "Início"),
        ("view", "Exibir"),
        ("settings", "Configurações"),
    )
    GROUPS = {
        "model": (
            group("Modelo",
                  big("mActionNew", "Novo"),
                  big("mActionOpen", "Abrir"),
                  big("mActionSave", "Salvar"),
                  big("mActionSaveAs", "Salvar\ncomo"),
                  big("mActionSaveInProject", "Salvar no\nprojeto")),
            group("Exportar",
                  menu("Exportar", "/mActionSharingExport.svg", ("menu:menuExport",)),
                  big("mActionExportAsScriptAlgorithm", "Algoritmo\nde script")),
            group("Documentação",
                  big("mActionEditHelp", "Editar\najuda")),
            group("Janela",
                  col(small("mActionClose", "Fechar", "/mIconClose.svg"))),
        ),
        "home": (
            group("Executar",
                  big("mActionRun", "Executar"),
                  big("mActionRunSelectedSteps", "Executar\nselecionados"),
                  big("mActionValidate", "Validar")),
            group("Editar",
                  col(small("key:Undo", "Desfazer", "/mActionUndo.svg"),
                      small("key:Redo", "Refazer", "/mActionRedo.svg")),
                  col(small("mActionSelectAll", "Selecionar tudo"),
                      small("mActionDeleteComponents", "Excluir"),
                      small("mActionAddGroupBox", "Caixa de grupo",
                            "/mActionAddBasicRectangle.svg"))),
            group("Organizar",
                  col(small("mActionReorderInputs", "Reordenar entradas",
                            "/mActionArrowDown.svg"),
                      small("mActionReorderOutputs", "Reordenar saídas",
                            "/mActionArrowUp.svg"),
                      small("mActionSnapSelected", "Alinhar à grade",
                            "/mIconSnapping.svg"))),
            group("Navegar",
                  big("mActionSelectMoveItem", "Selecionar/\nmover"),
                  big("mActionPan", "Mover"),
                  big("mActionZoomToItems", "Zoom\ntotal"),
                  col(small("mActionZoomIn", "Aproximar"),
                      small("mActionZoomOut", "Afastar"),
                      small("mActionZoomActual", "Zoom 100%"))),
        ),
        "view": (
            group("Mostrar",
                  col(small("mActionShowComments", "Comentários", "/mActionFormAnnotation.svg"),
                      small("mActionShowFeatureCount", "Contagem de feições",
                            "/mActionSum.svg"),
                      small("mActionSnappingEnabled", "Aderência", "/mIconSnapping.svg"))),
            group("Janelas",
                  col(small("mActionHidePanels", "Painéis visíveis", "/mDockify.svg"))),
        ),
        "settings": (_ribbon_group(),),
    }


TABLE_ACTIONS = "qrs.table_feature_actions"   # the dialog's "Actions" tool button
TABLE_DOCK = "qrs.table_dock"                  # QGIS's dock/undock toggle (no objectName)


class AttributeTableSpec:
    """QGIS attribute table (QgsAttributeTableDialog, floating or docked).

    No RustGIS window to mirror: RustGIS keeps table commands in its Data
    tab (Table, Selection, Data Design), whose wording is used here; groups
    and commands come from the dialog's own toolbar (qgsattributetabledialog.ui).
    Commands QGIS removes from that toolbar for the layer (e.g. Delete when
    the provider cannot delete) are not shown either.
    """

    COMMAND_LABELS = dict(_COMMON_LABELS)
    COMMAND_LABELS.update({TABLE_ACTIONS: "Ações", TABLE_DOCK: "Acoplar"})
    COMMAND_ICONS = dict(_COMMON_ICONS)
    COMMAND_ICONS.update({TABLE_ACTIONS: "/mAction.svg", TABLE_DOCK: "/mDockify.svg"})
    COMMAND_TIPS = dict(_COMMON_TIPS)
    QUICK_ACCESS = ("mActionToggleEditing", "mActionSaveEdits", "mActionReload")
    TABS = (
        ("home", "Início"),
        ("fields", "Campos"),
        ("settings", "Configurações"),
    )
    GROUPS = {
        "home": (
            group("Edição",
                  big("mActionToggleEditing", "Editar"),
                  big("mActionSaveEdits", "Salvar"),
                  col(small("mActionToggleMultiEdit", "Edição múltipla"),
                      small("mActionReload", "Recarregar"))),
            group("Feições",
                  split("mActionAddFeature",
                        ("mActionAddFeatureViaAttributeTable", "mActionAddFeatureViaAttributeForm"),
                        "Adicionar"),
                  big("mActionDeleteSelected", "Excluir")),
            group("Área de transferência",
                  big("mActionPasteFeatures", "Colar"),
                  col(small("mActionCutSelectedRows", "Recortar"),
                      small("mActionCopySelectedRows", "Copiar"))),
            group("Seleção",
                  big("mActionExpressionSelect", "Por\nexpressão"),
                  big("mActionSearchForm", "Por\nformulário"),
                  col(small("mActionSelectAll", "Tudo"),
                      small("mActionInvertSelection", "Inverter"),
                      small("mActionRemoveSelection", "Limpar")),
                  col(small("mActionSelectedToTop", "Seleção no topo"))),
            group("Mapa",
                  col(small("mActionPanMapToSelectedRows", "Centralizar seleção"),
                      small("mActionZoomMapToSelectedRows", "Zoom na seleção"))),
            group("Ações",
                  menu("Ações", "/mAction.svg", (TABLE_ACTIONS,))),
        ),
        "fields": (
            group("Estrutura de dados",
                  big("mActionAddAttribute", "Novo\ncampo"),
                  big("mActionRemoveAttribute", "Excluir\ncampo"),
                  big("mActionOpenFieldCalculator", "Calcular")),
            group("Exibição",
                  big("mActionOrganizeColumns", "Organizar\ncolunas"),
                  big("mActionSetStyles", "Formatação\ncondicional")),
        ),
        "settings": (
            group("Janela",
                  big(TABLE_DOCK, "Acoplar"),
                  big("mActionHelp", "Ajuda")),
            _ribbon_group(),
        ),
    }


EDITOR_SPECS = {"layout": LayoutSpec, "georeferencer": GeoreferencerSpec,
                "model": ModelDesignerSpec, "table": AttributeTableSpec}
