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


# Commands implemented by QRibbonSkin itself (interface only, never data).
PLUGIN = "qrs."
CLASSIC = PLUGIN + "classic"
FOCUS_MAP = PLUGIN + "focus_map"
RESTORE_PANELS = PLUGIN + "restore_panels"
PLUGIN_TOOLBARS = PLUGIN + "plugin_toolbars"
COMMAND_SEARCH = PLUGIN + "command_search"
TOGGLE_RIBBON = PLUGIN + "toggle_ribbon"
# Processing algorithm dialogs (native QGIS algorithms, native dialogs).
ALG = "alg:"

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
    "dock:ProcessingToolbox": "ProcessingToolboxDockWidget",
}

# Icons for processing dialogs and plugin commands (no native QAction).
COMMAND_ICONS = {
    ALG + "native:selectbylocation": "/algorithms/mAlgorithmSelectLocation.svg",
    ALG + "native:saveselectedfeatures": "/mActionCreateMemory.svg",
    CLASSIC: "qrs:classic_interface.svg",
    FOCUS_MAP: "qrs:focus_map.svg",
    RESTORE_PANELS: "/mDockify.svg",
    PLUGIN_TOOLBARS: "/mActionInterfaceCustomization.svg",
    COMMAND_SEARCH: "/search.svg",
}

COMMAND_LABELS = {
    ALG + "native:selectbylocation": "Selecionar por\nlocalização",
    ALG + "native:saveselectedfeatures": "Camada da\nseleção",
    CLASSIC: "Interface\nclássica",
    FOCUS_MAP: "Mapa em\nfoco",
    RESTORE_PANELS: "Restaurar painéis",
    PLUGIN_TOOLBARS: "Barras de\ncomplementos",
    COMMAND_SEARCH: "Buscar\ncomandos",
}

COMMAND_TIPS = {
    ALG + "native:selectbylocation": "Selecionar feições pela relação espacial com outra camada (algoritmo nativo do QGIS)",
    ALG + "native:saveselectedfeatures": "Criar uma camada com as feições selecionadas (algoritmo nativo do QGIS)",
    CLASSIC: "Desativar QRibbonSkin e restaurar as barras do QGIS",
    FOCUS_MAP: "Ocultar temporariamente os painéis; sem alterar o projeto",
    RESTORE_PANELS: "Restaurar visibilidade dos painéis anterior à Ribbon",
    PLUGIN_TOOLBARS: "Comandos das barras de ferramentas de complementos instalados",
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

# Tabs whose groups depend on the layer selected in the Layers panel.
LAYER_DEPENDENT_TABS = ("data", "style", "labeling")

# Groups shown *in the Ribbon* by the "Projeto" button (RustGIS opens its
# project backstage there). Only native QGIS project commands and menus; the
# QGIS welcome page in the map area is never replaced.
PROJECT_TAB = "project"

GROUPS = {
    PROJECT_TAB: (
        group("Projeto",
              big("mActionNewProject", "Novo"),
              split("mActionOpenProject", ("mActionOpenProject", "-",
                                           "menu:mRecentProjectsMenu"), "Abrir"),
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
        group("Layouts",
              big("mActionNewPrintLayout", "Novo\nlayout"),
              big("mActionShowLayoutManager", "Gerenciador\nde layouts"),
              menu("Layouts", "/mActionComposerManager.svg", ("menu:mLayoutsMenu",))),
        group("Importar e exportar",
              menu("Importar/\nexportar", "/mActionSharing.svg", ("menu:menuImport_Export",)),
              col(small("mActionDxfExport", "Exportar DXF", "/mActionSharingExport.svg"),
                  small("mActionDwgImport", "Importar DWG/DXF", "/mActionSharingImport.svg"))),
        group("Projeto atual",
              big("mActionProjectProperties", "Propriedades"),
              col(small("mActionRevertProject", "Reverter", "/mActionReload.svg"),
                  small("mActionCloseProject", "Fechar", "/mIconClose.svg"),
                  small("mActionExit", "Sair do QGIS"))),
    ),
    "home": (
        group("Projeto",
              big("mActionNewMapCanvas", "Nova vista\nde mapa"),
              split("mActionNewPrintLayout",
                    ("mActionNewPrintLayout", "mActionNewReport", "-",
                     "mActionShowLayoutManager", "menu:mLayoutsMenu"),
                    "Novo\nlayout")),
        group("Navegar",
              big("mActionPan", "Mover\nmapa"),
              menu("Favoritos", "/mActionShowBookmarks.svg",
                   ("mActionNewBookmark", "mActionShowBookmarks",
                    "mActionShowBookmarkManager")),
              col(small("mActionZoomFullExtent", "Extensão total"),
                  small("mActionZoomIn", "Aproximar"),
                  small("mActionZoomOut", "Afastar")),
              col(small("mActionZoomLast", "Anterior"),
                  small("mActionZoomNext", "Próxima"),
                  small("mActionZoomToLayers", "Zoom na camada")),
              col(small("mActionIdentify", "Identificar"),
                  small("mActionMapTips", "Dicas de mapa"),
                  small("mActionDraw", "Atualizar"))),
        group("Adicionar",
              menu("Mapa\nbase", "/mActionAddXyzLayer.svg",
                   ("mActionAddXyzLayer", "mActionAddVectorTileLayer",
                    "mActionAddWmsLayer", "mActionAddAfsLayer")),
              split("mActionDataSourceManager", ("menu:mAddLayerMenu",),
                    "Adicionar\ndados"),
              menu("Nova\ncamada", "/mActionNewVectorLayer.svg",
                   ("menu:mNewLayerMenu",)),
              menu("Dados\nweb", "/mIconWms.svg",
                   ("mActionAddWmsLayer", "mActionAddWfsLayer",
                    "mActionAddWcsLayer", "mActionAddXyzLayer",
                    "mActionAddVectorTileLayer", "mActionAddAfsLayer",
                    "mActionAddPointCloudLayer", "mActionAddStacLayer"))),
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
              big("mActionDataSourceManager", "Fontes de\ndados"),
              col(small("mActionAddLayerDefinition", "Definição de camada",
                        "/mActionAddLayer.svg"),
                  small("mActionEmbedLayers", "Incorporar camadas",
                        "/mActionAddGroup.svg"),
                  small("mActionDraw", "Recarregar"))),
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
              big("mActionLayerProperties", "Campos",
                  "/propertyicons/sourcefieldsandforms.svg"),
              big("mActionOpenFieldCalc", "Calcular"),
              col(small("mActionMultiEditAttributes", "Editar atributos"),
                  small("mActionStatisticalSummary", "Estatísticas")),
              when="vector"),
        group("Informações",
              big("mActionLayerProperties", "Informações\ndo raster",
                  "/propertyicons/metadata.svg"),
              big("mActionShowRasterCalculator", "Calculadora\nraster"),
              big("mActionShowGeoreferencer", "Georreferen-\nciador"),
              when="raster"),
        group("Camada",
              col(small("mActionDuplicateLayer", "Duplicar"),
                  small("mActionRemoveLayer", "Remover"),
                  small("mActionSetLayerCRS", "Definir SRC",
                        "/propertyicons/CRS.svg")),
              col(small("mActionSetProjectCRSFromLayer", "SRC do projeto",
                        "/mActionSetProjection.svg"),
                  small("mActionSetLayerScaleVisibility", "Escala visível",
                        "/mActionViewScaleInCanvas.svg")),
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
              big("mActionLayerProperties", "Propriedades",
                  "/propertyicons/system.svg"), when="layer"),
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
        group("Aderência",
              big("mActionSnappingOptions", "Aderência", "/mIconSnapping.svg"),
              col(small("ToggleTracing", "Traçado", "/mActionTracing.svg"),
                  small("ShowAdvancedDigitizingPanel", "Digitalização avançada",
                        "/cadtools/cad.svg"))),
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
              menu("Ferramentas\nde edição", "/mActionMultiEdit.svg",
                   ("menu:mMenuEditGeometry",))),
        group("Anotações",
              menu("Anotação", "/mActionAnnotation.svg",
                   ("menu:mMenuAnnotation",))),
    ),
    "analyze": (
        group("Geoprocessamento",
              big("mProcessingHistoryAction", "Histórico"),
              big("mActionShowProcessingToolbox", "Caixa de\nFerramentas"),
              big("mActionModelDesigner", "Designer de\nmodelos"),
              col(small("mActionShowPythonDialog", "Python"),
                  small("mActionEditFeaturesInPlace", "Editar no local"),
                  small("mActionQueryHistory", "Histórico SQL"))),
        group("Ferramentas",
              menu("Vetor", "/mActionAddOgrLayer.svg", ("menu:mVectorMenu",)),
              menu("Raster", "/mActionAddRasterLayer.svg", ("menu:mRasterMenu",)),
              menu("Malha", "/mActionAddMeshLayer.svg", ("menu:mMeshMenu",)),
              menu("Banco de\ndados", "/propertyicons/database.svg",
                   ("menu:mDatabaseMenu",))),
        group("Raster",
              col(small("mActionShowRasterCalculator", "Calculadora raster"),
                  small("mActionShowMeshCalculator", "Calculadora de malha"),
                  small("mActionShowGeoreferencer", "Georreferenciador"))),
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
                  small("mActionDraw", "Atualizar"))),
        group("Vista",
              big("mActionNewMapCanvas", "Nova vista\n2D"),
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
        group("Navegação",
              big("mActionZoomFullExtent", "Mundo"),
              col(small("mActionZoomActualSize", "Resolução nativa"),
                  small("mActionPanToSelected", "Centralizar seleção"))),
        group("Tempo",
              big("mActionTemporalController", "Controle\ntemporal",
                  "/propertyicons/temporal.svg")),
        group("Perfil",
              big("mActionElevationProfile", "Perfil"),
              col(small("mActionElevationController", "Elevação"))),
    ),
    "publish": (
        group("Layout",
              big("mActionNewPrintLayout", "Novo\nlayout"),
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
        group("Exportar dados",
              big("mActionLayerSaveAs", "Exportar\nfeições", "/mActionFileSaveAs.svg"),
              col(small("mActionSaveLayerDefinition", "Definição de camada",
                        "/mActionFileSave.svg"))),
        group("Salvar como",
              big("mActionSaveProjectAs", "Projeto"),
              menu("Armazenamento", "/mIconFolder24.svg",
                   ("menu:mProjectToStorageMenu",)),
              col(small("mActionProjectProperties", "Propriedades do projeto"))),
    ),
    "plugins": (
        group("Complementos",
              big("mActionManagePlugins", "Gerenciar\ncomplementos"),
              col(small("mActionShowPythonDialog", "Console Python"))),
        group("Menus de complementos",
              menu("Complementos", "/propertyicons/plugins.svg", ("menu:mPluginMenu",)),
              menu("Vetor", "/mActionAddOgrLayer.svg", ("menu:mVectorMenu",)),
              menu("Raster", "/mActionAddRasterLayer.svg", ("menu:mRasterMenu",)),
              menu("Banco de\ndados", "/propertyicons/database.svg",
                   ("menu:mDatabaseMenu",)),
              menu("Web", "/mIconWms.svg", ("menu:mWebMenu",)),
              menu("Processamento", "/processingAlgorithm.svg",
                   ("menu:mProcessingMenu",))),
        group("Barras",
              menu(COMMAND_LABELS[PLUGIN_TOOLBARS], COMMAND_ICONS[PLUGIN_TOOLBARS],
                   (PLUGIN_TOOLBARS,))),
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
        group("Estilos",
              big("mActionStyleManager", "Gerenciador\nde estilos")),
        group("QRibbonSkin",
              big(CLASSIC),
              col(small(RESTORE_PANELS),
                  small(TOGGLE_RIBBON, "Recolher a Ribbon", "qrs:chevron_up.svg"))),
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
