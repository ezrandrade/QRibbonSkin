"""Declarative layout of the main QRibbonSkin Ribbon (Qt-free, testable).

The tab, group and control *arrangement* follows the RustGIS ribbon
(Project button + Home, Data, Style, Labeling, Edit, Analyze, View, Publish,
Plugins, Settings, Help). Every control points at a *native* QGIS object:

* ``mAction…`` / ``Show…Panel`` names are QAction objectNames from QGIS's
  own ``qgisapp.ui`` / ``qgisapp.cpp``; the Ribbon reuses those QActions, so
  their icons, enabled state, check state, shortcuts and translations are
  QGIS's own.
* ``m…Menu`` names are QGIS's native QMenus, shown as-is (never copied), so
  entries added by third-party plugins appear live without rescanning.
* ``icon`` is a QGIS theme icon path (``QgsApplication.getThemeIcon``), used
  only when the native QAction has no icon; ``qrs:`` icons are QRibbonSkin
  SVGs drawn in the QGIS icon style for the few commands QGIS has none for.

A control whose native object does not exist in the running QGIS build is
skipped silently, and an empty group is not drawn: no fake commands.

Labels are short Ribbon captions (PT-BR source strings, translated by
``i18n.tr``); tooltips keep the native QGIS text and shortcut.
"""

# --- control constructors ---------------------------------------------------
# Kinds:
#   big    : large button, 32 px icon over a 1–2 line caption
#   small  : small button, 16 px icon + caption; stacked 3 per column
#   split  : large button with a primary action and an arrow menu
#   menu   : large button whose whole surface opens a menu
#   col    : column of up to three small controls
# Menu entries: action names, "menu:<objectName>" (a native submenu), or "-".


def big(name, label=None, icon=None):
    return {"kind": "big", "name": name, "label": label, "icon": icon}


def small(name, label=None, icon=None):
    return {"kind": "small", "name": name, "label": label, "icon": icon}


def split(name, entries, label=None, icon=None):
    return {"kind": "split", "name": name, "entries": list(entries),
            "label": label, "icon": icon}


def menu(label, icon, entries, small_size=False):
    """A dropdown. ``entries`` may be a single "menu:<native>" to show that
    native QMenu itself (live, including plugin entries)."""
    return {"kind": "small_menu" if small_size else "menu", "label": label,
            "icon": icon, "entries": list(entries)}


def col(*items):
    return {"kind": "col", "items": list(items)}


def group(title, *items, when=None):
    """``when``: None (always), "vector", "raster", "layer" (any layer)."""
    return {"title": title, "items": list(items), "when": when}


# Names: a QAction/QMenu objectName, or "name4|name3" when QGIS 4.x and
# QGIS 3.44 LTR name the same command differently (the first found is used).

# Commands implemented by QRibbonSkin itself (interface only, never data).
PLUGIN = "qrs."
CLASSIC = PLUGIN + "classic"
FOCUS_MAP = PLUGIN + "focus_map"
RESTORE_PANELS = PLUGIN + "restore_panels"
COMMAND_SEARCH = PLUGIN + "command_search"
TOGGLE_RIBBON = PLUGIN + "toggle_ribbon"
# Processing algorithm dialogs (native QGIS algorithms, native dialogs).
ALG = "alg:"
# Native Layer Properties dialog opened on one page (iface.showLayerProperties).
PROPS = "props:"
# (page objectName, caption, icon, tooltip) — page names come from QGIS's
# qgsvectorlayerpropertiesbase.ui / qgsrasterlayerpropertiesbase.ui; QGIS
# opens its default page when a name is unknown, so nothing breaks.
PROPERTY_PAGES = {
    "mOptsPage_SourceFields": ("Campos", "/propertyicons/sourcefieldsandforms.svg",
                               "Campos da camada (Propriedades da camada › Campos)"),
    "mOptsPage_Joins": ("Junções", "/propertyicons/join.svg",
                        "Junções de tabelas (Propriedades da camada › Junções)"),
    "mOptsPage_Information": ("Informações\ndo raster", "/propertyicons/metadata.svg",
                              "Informações do raster (Propriedades da camada › Informações)"),
    "mOptsPage_Histogram": ("Histograma", "/propertyicons/histogram.svg",
                            "Histograma do raster (Propriedades da camada › Histograma)"),
    "mOptsPage_Style": ("Propriedades", "/propertyicons/system.svg",
                        "Propriedades da camada (página Simbologia)"),
}

# Docks whose toggle QAction is looked up by objectName first and, when a
# build lacks that QAction, through QDockWidget.toggleViewAction().
DOCK_FALLBACK = {
    "ShowLayersPanel": "Layers",
    "ShowBrowserPanel": "Browser",
    "ShowLayerStylingPanel": "LayerStyling",
    "ShowBookmarksPanel": "BookmarksDockWidget",
    "ShowUndoPanel": "Undo",
    "ShowLayerOrderPanel": "LayerOrder",
    "ShowOverviewPanel": "Overview",
    "ShowAdvancedDigitizingPanel": "AdvancedDigitizingTools",
    "ShowStatisticsPanel": "StatisticalSummaryDockWidget",
    "ShowGpsPanel": "GPSInformation",
    "ShowDevToolsPanel": "DevTools",
    "dock:MessageLog": "MessageLog",
    # QGIS 4.x | QGIS 3.44 (Processing Python plugin)
    "dock:ProcessingToolbox": ("ProcessingToolboxDockWidget", "ProcessingToolbox"),
}

# QGIS 3.44 LTR: Processing is a core Python plugin; its own commands and its
# top-level "processing" menu are QGIS's, not a third-party plugin's.
PROCESSING_PLUGIN_ACTIONS = frozenset(("toolboxAction", "modelerAction", "historyAction",
                                       "resultsViewer", "editInPlaceFeatures", "optionsAction"))

# Icons for processing dialogs and plugin commands (no native QAction).
COMMAND_ICONS = {
    ALG + "native:selectbylocation": "/algorithms/mAlgorithmSelectLocation.svg",
    ALG + "native:saveselectedfeatures": "/mActionCreateMemory.svg",
    CLASSIC: "qrs:classic_interface.svg",
    FOCUS_MAP: "qrs:focus_map.svg",
    RESTORE_PANELS: "/mDockify.svg",
    COMMAND_SEARCH: "/search.svg",
}

COMMAND_LABELS = {
    ALG + "native:selectbylocation": "Selecionar por\nlocalização",
    ALG + "native:saveselectedfeatures": "Camada da\nseleção",
    CLASSIC: "Interface\nclássica",
    FOCUS_MAP: "Mapa em\nfoco",
    RESTORE_PANELS: "Restaurar painéis",
    COMMAND_SEARCH: "Buscar\ncomandos",
}

COMMAND_TIPS = {
    ALG + "native:selectbylocation": ("Selecionar feições pela relação espacial com outra camada "
                                      "(algoritmo nativo do QGIS)"),
    ALG + "native:saveselectedfeatures": "Criar uma camada com as feições selecionadas (algoritmo nativo do QGIS)",
    CLASSIC: "Desativar QRibbonSkin e restaurar as barras do QGIS",
    FOCUS_MAP: "Ocultar temporariamente os painéis; sem alterar o projeto",
    RESTORE_PANELS: "Restaurar visibilidade dos painéis anterior à Ribbon",
    COMMAND_SEARCH: "Buscar e executar qualquer comando do QGIS (Alt+Q)",
}

# Quick Access Toolbar (RustGIS: New, Open, Save, Undo, Redo, Undo History).
QUICK_ACCESS = ("mActionNewProject", "mActionOpenProject", "mActionSaveProject",
                "mActionUndo", "mActionRedo", "ShowUndoPanel")

# Tab ids are stable and never translated; captions are translated.
TABS = (
    ("home", "Início"),
    ("data", "Dados"),
    ("style", "Estilo"),
    ("labeling", "Rotulagem"),
    ("edit", "Editar"),
    ("analyze", "Analisar"),
    ("view", "Exibir"),
    ("publish", "Publicar"),
    ("plugins", "Complementos"),
    ("settings", "Configurações"),
    ("help", "Ajuda"),
)

# Tabs that hold only *extra* content (RustGIS: Plugins shows plugin content):
# their native dropdowns omit commands with a button on any tab.
GLOBAL_DEDUP_TABS = ("plugins", "settings")

# Native menus where QGIS puts plugin commands (QgisInterface.addPluginTo…Menu
# creates one submenu per plugin in them).
# QGIS toolbars that host plugin buttons (iface.addToolBarIcon and the
# Raster/Vector/Database/Web variants). Every other QGIS toolbar holds only
# QGIS's own commands, some of them without the mAction prefix (snapping,
# annotations, advanced digitizing, mesh editing).
PLUGIN_HOST_TOOLBARS = frozenset(("mPluginToolBar", "mRasterToolBar", "mVectorToolBar",
                                  "mDatabaseToolBar", "mWebToolBar"))
PLUGIN_SOURCE_MENUS = ("mPluginMenu", "mVectorMenu", "mRasterMenu", "mDatabaseMenu",
                       "mWebMenu", "mMeshMenu", "mProcessingMenu")
# Top-level menus of the QGIS menu bar; any other top-level menu is a plugin's.
NATIVE_TOP_MENUS = frozenset(("mProjectMenu", "mEditMenu", "mViewMenu", "mLayerMenu",
                              "mSettingsMenu", "mPluginMenu", "mVectorMenu", "mRasterMenu",
                              "mDatabaseMenu", "mWebMenu", "mMeshMenu", "mProcessingMenu",
                              "mHelpMenu", "mWindowMenu",
                              "processing"))  # QGIS 3.44: Processing plugin menu

# Tabs whose groups depend on the layer selected in the Layers panel.
LAYER_DEPENDENT_TABS = ("data", "style", "labeling")

# Groups shown *in the Ribbon* by the "Projeto" button (RustGIS opens its
# project backstage there). Only native QGIS project commands and menus; the
# QGIS welcome page in the map area is never replaced.
PROJECT_TAB = "project"
PROJECT_BUTTON = ("Projeto", "Abrir, salvar e criar projetos")

# Redundancy rules (checked by an automated audit, as RustGIS does it):
# 1. Inside one tab a command appears once. Native menus used as dropdowns
#    are shown *without* the commands that already have a button on the same
#    tab (see the Ribbon's de-duplicated menu proxy).
# 2. Across tabs, only commands that serve the other tab's work: the
#    repetitions RustGIS makes (attribute table, selection by attributes/
#    location, View › Windows mirroring the panels used on other tabs) and
#    the Select and Clear Selection tools on Edit, since editing acts on the
#    selected features
#    (ArcGIS Pro, RustGIS's model, has it there too).
# 3. The Plugins tab manages plugins once and shows only plugin content.
GROUPS = {
    PROJECT_TAB: (
        group("Projeto",
              big("mActionNewProject", "Novo"),
              big("mActionOpenProject", "Abrir"),
              big("mActionSaveProject", "Salvar"),
              big("mActionSaveProjectAs", "Salvar\ncomo")),
        group("Recentes e modelos",
              menu("Projetos\nrecentes", "/mActionFileOpen.svg",
                   ("menu:mRecentProjectsMenu",)),
              menu("Novo a partir\nde modelo", "/mActionFileNewFromTemplate.svg",
                   ("menu:mProjectFromTemplateMenu",))),
        group("Armazenamento",
              menu("Abrir de", "/mIconFolder24.svg", ("menu:mProjectFromStorageMenu",)),
              menu("Salvar em", "/mActionFileSaveAs.svg", ("menu:mProjectToStorageMenu",))),
        group("Projeto atual",
              big("mActionProjectProperties", "Propriedades"),
              col(small("mActionRevertProject", "Reverter", "/mActionReload.svg"),
                  small("mActionCloseProject", "Fechar", "/mIconClose.svg"),
                  small("mActionExit", "Sair do QGIS"))),
    ),
    "home": (
        group("Projeto",
              big("mActionNewMapCanvas", "Nova vista\nde mapa"),
              big("mActionNewPrintLayout", "Novo\nlayout")),
        group("Navegar",
              big("mActionPan", "Mover\nmapa"),
              menu("Favoritos", "/mActionShowBookmarks.svg",
                   ("mActionNewBookmark", "mActionShowBookmarkManager")),
              col(small("mActionZoomFullExtent", "Extensão total"),
                  small("mActionZoomIn", "Aproximar"),
                  small("mActionZoomOut", "Afastar")),
              col(small("mActionZoomLast", "Anterior"),
                  small("mActionZoomNext", "Próxima"),
                  small("mActionPanToSelected", "Centralizar seleção")),
              col(small("mActionIdentify", "Identificar"),
                  small("mActionDraw", "Atualizar"))),
        group("Adicionar",
              menu("Mapa\nbase", "/mActionAddXyzLayer.svg",
                   ("mActionAddXyzLayer", "mActionAddVectorTileLayer")),
              split("mActionDataSourceManager", ("menu:mAddLayerMenu",),
                    "Adicionar\ndados"),
              menu("Nova\ncamada", "/mActionNewVectorLayer.svg",
                   ("menu:mNewLayerMenu",)),
              menu("Dados\nweb", "/mIconWms.svg",
                   ("mActionAddWmsLayer", "mActionAddWfsLayer",
                    "mActionAddWcsLayer", "mActionAddAfsLayer",
                    "mActionAddStacLayer"))),
        group("Seleção",
              split("mActionSelectFeatures",
                    ("mActionSelectFeatures", "mActionSelectPolygon",
                     "mActionSelectFreehand", "mActionSelectRadius"),
                    "Selecionar"),
              split("mActionSelectByExpression",
                    ("mActionSelectByExpression", "mActionSelectByForm"),
                    "Selecionar por\natributos"),
              big(ALG + "native:selectbylocation"),
              col(small("mActionDeselectAll", "Limpar"),
                  small("mActionZoomToSelected", "Zoom na seleção"),
                  small("mActionOpenTableSelected", "Atributos"))),
        group("Inspecionar",
              split("mActionMeasure",
                    ("mActionMeasure", "mActionMeasureArea",
                     "mActionMeasureAngle", "mActionMeasureBearing"),
                    "Medir"),
              col(small("mActionStatisticalSummary", "Estatísticas"),
                  small("mActionFeatureAction", "Ação"))),
    ),
    "data": (
        group("Fonte de dados",
              col(small("mActionAddLayerDefinition", "Definição de camada",
                        "/mActionAddLayer.svg"),
                  small("mActionEmbedLayers", "Incorporar camadas",
                        "/mActionAddGroup.svg"))),
        group("Alinhamento",
              big("mActionShowGeoreferencer", "Georreferen-\nciador")),
        group("Filtro",
              big("mActionLayerSubsetString", "Consulta de\ndefinição",
                  "/mIconExpressionFilter.svg"), when="vector"),
        group("Tabela",
              split("mActionOpenTable",
                    ("mActionOpenTable", "mActionOpenTableSelected",
                     "mActionOpenTableVisible", "mActionOpenTableEdited"),
                    "Tabela de\natributos"), when="vector"),
        group("Seleção",
              col(small("mActionSelectAll", "Tudo"),
                  small("mActionInvertSelection", "Inverter"),
                  small("mActionDeselectActiveLayer", "Limpar")),
              big(ALG + "native:saveselectedfeatures"), when="vector"),
        group("Estrutura de dados",
              big(PROPS + "mOptsPage_SourceFields"),
              big(PROPS + "mOptsPage_Joins"),
              big("mActionOpenFieldCalc", "Calcular"), when="vector"),
        group("Informações",
              big(PROPS + "mOptsPage_Information"),
              big(PROPS + "mOptsPage_Histogram"), when="raster"),
        group("Camada",
              col(small("mActionDuplicateLayer", "Duplicar"),
                  small("mActionSetLayerCRS", "Definir SRC",
                        "/propertyicons/CRS.svg"),
                  small("mActionSetProjectCRSFromLayer", "SRC do projeto",
                        "/mActionSetProjection.svg")),
              when="layer"),
        group("Exportar",
              big("mActionLayerSaveAs", "Exportar\ncamada", "/mActionFileSaveAs.svg"),
              col(small("mActionSaveLayerDefinition", "Salvar definição",
                        "/mActionFileSave.svg")),
              when="layer"),
    ),
    "style": (
        group("Desenho",
              big("ShowLayerStylingPanel", "Simbologia",
                  "/propertyicons/symbology.svg"),
              big(PROPS + "mOptsPage_Style"), when="layer"),
        group("Camada",
              big("mActionZoomToLayers", "Zoom na\ncamada"),
              col(small("mActionOpenTable", "Tabela de atributos"),
                  small("mActionToggleSelectedLayers", "Visível"),
                  small("mActionRemoveLayer", "Remover")), when="layer"),
        group("Intervalo de visibilidade",
              big("mActionSetLayerScaleVisibility", "Escala\nvisível",
                  "/mActionViewScaleInCanvas.svg"), when="layer"),
        group("Realce",
              col(small("mActionLocalHistogramStretch", "Histograma local"),
                  small("mActionFullHistogramStretch", "Histograma total")),
              col(small("mActionLocalCumulativeCutStretch", "Corte cumulativo local"),
                  small("mActionFullCumulativeCutStretch", "Corte cumulativo total")),
              when="raster"),
        group("Brilho e contraste",
              col(small("mActionIncreaseBrightness", "Mais brilho"),
                  small("mActionDecreaseBrightness", "Menos brilho")),
              col(small("mActionIncreaseContrast", "Mais contraste"),
                  small("mActionDecreaseContrast", "Menos contraste")),
              col(small("mActionIncreaseGamma", "Mais gama"),
                  small("mActionDecreaseGamma", "Menos gama")),
              when="raster"),
        group("Estilos",
              big("mActionStyleManager", "Estilos"),
              col(small("mActionCopyStyle", "Copiar estilo"),
                  small("mActionPasteStyle", "Colar estilo"))),
    ),
    "labeling": (
        group("Rótulos",
              big("mActionLabeling", "Propriedades"),
              big("mActionDiagramProperties", "Diagramas"), when="vector"),
        group("Posicionamento",
              big("mActionMoveLabel", "Mover\nrótulo"),
              col(small("mActionRotateLabel", "Girar rótulo"),
                  small("mActionChangeLabelProperties", "Alterar rótulo")),
              when="vector"),
        group("Rotulagem do mapa",
              col(small("mActionPinLabels", "Fixar"),
                  small("mActionShowHideLabels", "Mostrar/ocultar"),
                  small("mActionShowPinnedLabels", "Destacar fixados")),
              big("mActionShowUnplacedLabels", "Ver não\nposicionados")),
    ),
    "edit": (
        group("Gerenciar edições",
              big("mActionToggleEditing", "Editar"),
              big("mActionSaveLayerEdits", "Salvar"),
              col(small("mActionUndo", "Desfazer"),
                  small("mActionRedo", "Refazer"),
                  small("ShowUndoPanel", "Status", "/mActionHistory.svg")),
              menu("Edições", "/mActionAllEdits.svg",
                   ("mActionSaveEdits", "mActionSaveAllEdits", "-",
                    "mActionRollbackEdits", "mActionRollbackAllEdits", "-",
                    "mActionCancelEdits", "mActionCancelAllEdits"))),
        group("Área de transferência",
              split("mActionPasteFeatures",
                    ("mActionPasteFeatures", "menu:mMenuPasteAs"), "Colar"),
              col(small("mActionCutFeatures", "Recortar"),
                  small("mActionCopyFeatures", "Copiar"))),
        # Snapping toolbar commands (QgsSnappingWidget, same names in 3.44 and 4.x).
        group("Aderência",
              big("EnableSnappingAction", "Aderência", "/mIconSnapping.svg"),
              col(small("TopologicalEditingAction", "Edição topológica",
                        "/mIconTopologicalEditing.svg"),
                  small("IntersectionSnappingAction", "Na interseção",
                        "/mIconSnappingIntersection.svg"),
                  small("SelfSnappingAction", "Autoaderência", "/mIconSnappingSelf.svg")),
              col(small("EnableTracingAction", "Traçado", "/mActionTracing.svg"),
                  small("mActionSnappingOptions", "Opções", "/mIconSnapping.svg"),
                  small("ShowAdvancedDigitizingPanel", "Digitalização avançada",
                        "/cadtools/cad.svg"))),
        group("Seleção",
              split("mActionSelectFeatures",
                    ("mActionSelectFeatures", "mActionSelectPolygon",
                     "mActionSelectFreehand", "mActionSelectRadius"),
                    "Selecionar"),
              big("mActionDeselectAll", "Limpar\nseleção")),
        group("Feições",
              split("mActionAddFeature",
                    ("mActionAddFeature", "-", "mActionDigitizeWithSegment",
                     "mActionDigitizeWithCurve", "mActionDigitizeWithBezier",
                     "mActionDigitizeWithNurbs", "mActionStreamDigitize",
                     "mActionDigitizeShape"), "Criar"),
              split("mActionVertexTool",
                    ("mActionVertexTool", "mActionVertexToolActiveLayer"),
                    "Editar\nvértices"),
              split("mActionMoveFeature",
                    ("mActionMoveFeature", "mActionMoveFeatureCopy",
                     "mActionRotateFeature", "mActionScaleFeature"),
                    "Modificar"),
              big("mActionDeleteSelected", "Excluir"),
              col(small("mActionMergeFeatures", "Mesclar feições"),
                  small("mActionMergeFeatureAttributes", "Mesclar atributos"),
                  small("mActionMultiEditAttributes", "Editar atributos"))),
        group("Ferramentas",
              col(small("mActionReshapeFeatures", "Remodelar"),
                  small("mActionSplitFeatures", "Dividir feições"),
                  small("mActionSplitParts", "Dividir partes")),
              col(small("mActionOffsetCurve", "Deslocar curva"),
                  small("mActionSimplifyFeature", "Simplificar"),
                  small("mActionTrimExtendFeature", "Aparar/estender")),
              menu("Mais\nferramentas", "/mActionMultiEdit.svg",
                   ("menu:mMenuEditGeometry",))),
        group("Anotações",
              menu("Anotação", "/mActionAnnotation.svg",
                   ("menu:mMenuAnnotation",))),
    ),
    "analyze": (
        group("Geoprocessamento",
              big("mProcessingHistoryAction|historyAction", "Histórico"),
              big("mActionShowProcessingToolbox|toolboxAction", "Caixa de\nFerramentas"),
              big("mActionModelDesigner|modelerAction", "Designer de\nmodelos"),
              col(small("mActionShowPythonDialog", "Python"),
                  small("mActionEditFeaturesInPlace|editInPlaceFeatures", "Editar no local"),
                  small("mActionQueryHistory", "Histórico SQL"))),
        # "native:" = the QGIS menu without plugin entries: plugins have
        # their own groups on the Plugins tab (RustGIS rule).
        group("Ferramentas",
              menu("Vetor", "/mActionAddOgrLayer.svg", ("native:mVectorMenu",)),
              menu("Raster", "/mActionAddRasterLayer.svg", ("native:mRasterMenu",)),
              menu("Malha", "/mActionAddMeshLayer.svg", ("native:mMeshMenu",)),
              menu("Banco de\ndados", "/propertyicons/database.svg",
                   ("native:mDatabaseMenu",))),
        group("Calculadoras",
              col(small("mActionShowRasterCalculator", "Calculadora raster"),
                  small("mActionShowMeshCalculator", "Calculadora de malha"))),
        group("Seleção",
              big("mActionSelectByExpression", "Por\natributos"),
              big(ALG + "native:selectbylocation", "Por\nlocalização")),
    ),
    "view": (
        group("Interface",
              big(FOCUS_MAP),
              col(small("mActionToggleFullScreen", "Tela cheia",
                        "/mActionZoomFullExtent.svg"),
                  small("mActionTogglePanelsVisibility", "Painéis visíveis",
                        "/mDockify.svg"),
                  small(RESTORE_PANELS))),
        group("Exibição",
              menu("Decorações", "/grid.svg", ("menu:mMenuDecorations",)),
              col(small("mActionMapTips", "Dicas de mapa"),
                  small("mActionZoomActualSize", "Resolução nativa"))),
        group("Vista",
              menu("3D", "/mActionNew3DMap.svg",
                   ("mActionNew3DMapCanvas", "mActionNew3DMapCanvasGlobe",
                    "mActionManage3DMapViews"))),
        group("Efeitos",
              menu("Visão de\ncores", "/mIconColorWheel.svg",
                   ("menu:mMenuPreviewMode",))),
        group("Janelas",
              big("ShowLayersPanel", "Camadas", "/mActionLayers.svg"),
              big("ShowBrowserPanel", "Navegador", "/mIconFolder24.svg"),
              big("dock:ProcessingToolbox", "Painel de\nferramentas",
                  "/processingAlgorithm.svg"),
              col(small("ShowLayerStylingPanel", "Simbologia",
                        "/propertyicons/symbology.svg"),
                  small("ShowUndoPanel", "Histórico", "/mActionHistory.svg"),
                  small("ShowBookmarksPanel", "Favoritos",
                        "/mActionShowBookmarks.svg")),
              col(small("ShowLayerOrderPanel", "Ordem das camadas",
                        "/mIconLayerTree.svg"),
                  small("ShowOverviewPanel", "Visão geral",
                        "/mActionInOverview.svg"),
                  small("dock:MessageLog", "Mensagens", "/mMessageLog.svg")),
              menu("Painéis", "/mDockify.svg", ("menu:mPanelMenu",))),
        group("Tempo",
              big("mActionTemporalController", "Controle\ntemporal",
                  "/propertyicons/temporal.svg")),
        group("Perfil",
              big("mActionElevationProfile", "Perfil"),
              col(small("mActionElevationController", "Elevação"))),
    ),
    "publish": (
        group("Layout",
              big("mActionShowLayoutManager", "Gerenciador\nde layouts"),
              menu("Layouts", "/mActionComposerManager.svg",
                   ("menu:mLayoutsMenu",))),
        group("Relatório",
              big("mActionNewReport", "Novo\nrelatório")),
        group("Saída",
              big("mActionSaveMapAsImage", "Exportar\nmapa"),
              big("mActionSaveMapAsPdf", "Exportar\nPDF"),
              col(small("mActionDxfExport", "Exportar DXF", "/mActionSharingExport.svg"),
                  small("mActionDwgImport", "Importar DWG/DXF",
                        "/mActionSharingImport.svg"))),
    ),
    # Then one group per installed plugin, built at run time from the menus
    # and toolbars the plugin added (RustGIS: a group per enabled plugin).
    "plugins": (
        group("Complementos",
              big("mActionManagePlugins", "Gerenciar\ncomplementos")),
    ),
    "settings": (
        group("Personalizar",
              big("mActionOptions", "Opções"),
              big("mActionConfigureShortcuts", "Atalhos de\nteclado"),
              big("mActionCustomization", "Interface"),
              menu("Barras de\nferramentas", "/mActionInterfaceCustomization.svg",
                   ("menu:mToolbarMenu",))),
        group("Sistemas de referência",
              big("mActionCustomProjection", "Projeções\npersonalizadas")),
        group("Perfis",
              menu("Perfis de\nusuário", "/user.svg", ("menu:mUserProfileMenu",))),
        group("QRibbonSkin",
              big(CLASSIC),
              col(small(TOGGLE_RIBBON, "Recolher a Ribbon", "qrs:chevron_up.svg"))),
        group("Mais",
              menu("Configurações", "/propertyicons/settings.svg",
                   ("menu:mSettingsMenu",))),
    ),
    "help": (
        group("Ajuda",
              big("mActionHelpContents", "Conteúdo\nda ajuda"),
              big("mActionAbout", "Sobre", "/mIconInfo.svg"),
              big("mActionCheckQgisVersion", "Verificar\nversão"),
              big(COMMAND_SEARCH)),
        group("Aprender",
              big("mActionQgisHomePage", "Página do\nQGIS"),
              col(small("mActionHelpAPI", "API C++", "/mActionHelpContents.svg"),
                  small("mActionHelpPyQgisAPI", "API PyQGIS", "/mIconPythonFile.svg"),
                  small("mActionReportaBug", "Relatar problema", "/mIconWarning.svg")),
              menu("Ajuda de\ncomplementos", "/propertyicons/plugins.svg",
                   ("menu:mMenuPluginHelp",))),
        group("Comunidade",
              col(small("mActionSponsors", "Membros mantenedores"),
                  small("mActionGetInvolved", "Participar", "/user.svg"),
                  small("mActionDonate", "Doar", "/mIconFavorites.svg"))),
    ),
}


def iter_names(groups=None):
    """Every native/plugin name referenced by the spec (for audits/tests)."""
    tabs = GROUPS.values() if groups is None else [groups]
    for tab_groups in tabs:
        for grp in tab_groups:
            stack = list(grp["items"])
            while stack:
                item = stack.pop(0)
                if item["kind"] == "col":
                    stack[:0] = item["items"]
                    continue
                if "name" in item:
                    yield item["name"]
                for entry in item.get("entries", ()):
                    if entry != "-":
                        yield entry


def iter_icons():
    """Every icon path referenced by the spec."""
    yield from (page[1] for page in PROPERTY_PAGES.values())
    for tab_groups in GROUPS.values():
        for grp in tab_groups:
            stack = list(grp["items"])
            while stack:
                item = stack.pop(0)
                if item["kind"] == "col":
                    stack[:0] = item["items"]
                    continue
                if item.get("icon"):
                    yield item["icon"]
    yield from COMMAND_ICONS.values()


def visible_groups(tab_id, layer_kind):
    """Groups of ``tab_id`` for the selected layer: None, "vector", "raster"
    or "other" (mesh, point cloud, …)."""
    out = []
    for grp in GROUPS.get(tab_id, ()):
        when = grp["when"]
        if when is None:
            out.append(grp)
        elif when == "layer" and layer_kind is not None:
            out.append(grp)
        elif when == layer_kind:
            out.append(grp)
    return out
