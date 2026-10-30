"""Pure data definitions for the QGIS Layout Designer Ribbon.

Keep the original QAction identity and dispatch; no native actions are cloned.
The Layout Designer API gives each independent editor its own native sources.
"""
import re
import unicodedata

# The names are labels on our own Ribbon, not translated searches for Qt widgets.
TAB_NAMES = ("Principal", "Interface")
SOURCE_TABS = {
    "layoutMenu": "Layout", "layoutToolbar": "Layout",
    "itemsMenu": "Inserir", "editMenu": "Editar", "actionsToolbar": "Editar",
    "viewMenu": "Exibir", "navigationToolbar": "Exibir",
    "atlasMenu": "Atlas", "atlasToolbar": "Atlas", "reportMenu": "Atlas",
    "settingsMenu": "Interface",
}

OUTPUT_TERMS = ("export", "imprim", "print", "pdf", "svg", "imagem", "image", "picture",
                "salvar como imagem", "save as image", "rasterizar", "render")


def normalized(text):
    text = unicodedata.normalize("NFKD", str(text).replace("&", "").casefold())
    text = "".join(char for char in text if not unicodedata.combining(char))
    return " ".join(re.split(r"\s+", text)).strip()


def is_output_action(text):
    """Classify only clearly export/print-related actions, in English or PT-BR."""
    term = normalized(text)
    return any(part in term for part in OUTPUT_TERMS)


def title_for_source(name):
    return {
        "layoutMenu": "Projeto de layout", "layoutToolbar": "Arquivo",
        "itemsMenu": "Inserir elementos", "editMenu": "Organizar",
        "actionsToolbar": "Ferramentas", "viewMenu": "Visualização",
        "navigationToolbar": "Navegação", "atlasMenu": "Atlas",
        "atlasToolbar": "Percorrer atlas", "reportMenu": "Relatório",
        "settingsMenu": "Preferências",
    }.get(name, name)


def unique_identity(actions):
    """Preserve distinct same-caption actions; eliminate duplicate references."""
    result, seen = [], set()
    for action in actions:
        identity = id(action)
        if identity not in seen:
            result.append(action)
            seen.add(identity)
    return result


def tab_for_native_toolbar(title):
    """Route extra native layout toolbars to task tabs, without moving actions."""
    name = normalized(title)
    if any(x in name for x in ('naveg', 'navigation', 'zoom', 'map view', 'visualiz', 'view')):
        return 'Exibir'
    if any(x in name for x in ('edit', 'edita', 'action', 'align', 'alinh', 'arrange', 'organiza')):
        return 'Editar'
    if any(x in name for x in ('item', 'element', 'add item', 'adicionar', 'insert', 'inser')):
        return 'Inserir'
    if any(x in name for x in ('atlas', 'relatorio', 'report')):
        return 'Atlas'
    if any(x in name for x in ('export', 'print', 'imprim', 'pdf')):
        return 'Exportar'
    return 'Layout'


# QRibbonSkin 0.9.10 — semantic placement for native layout actions.
# An action may be referenced by multiple native menus/toolbars; routing works
# from its actual meaning and the source, not the accident of traversal order.
EDIT_ORGANIZE = (
    "agrupar", "desagrupar", "group", "ungroup", "levantar", "baixar",
    "frente", "tras", "front", "back", "align", "alinh", "distribu",
    "resize", "redimension", "lock", "unlock", "bloque", "desbloque",
    "ordenar", "order", "posicao", "position", "empilh", "stack",
)
EDIT_GEOMETRY = (
    "selecionar", "selection", "select", "mover item", "move item",
    "editar nos", "edit node", "node tool", "mover conteudo", "move content",
    "conteudo do item", "item content", "vertice", "vertex",
)
EDIT_HISTORY = ("desfazer", "refazer", "undo", "redo", "historico")
VIEW_NAV = (
    "zoom", "aproximar", "afastar", "pan ", "deslocar layout", "move layout",
    "mover layout", "recentraliz", "refresh", "atualizar", "ruler", "regua",
    "guide", "guia", "grade", "grid", "visualiz", "view page",
)
INSERT_ITEMS = (
    "adicionar", "add ", "insert", "inserir", "mapa 3d", "legenda",
    "barra de escala", "scale bar", "seta norte", "rótulo", "rotulo",
    "imagem", "marcador", "marker", "figura", "shape", "html",
    "tabela", "picture", "label", "quadro",
)
FILE_ACTIONS = (
    "salvar", "save", "abrir", "open", "novo layout", "new layout",
    "fechar", "close", "configurar pagina", "page setup", "page properties",
)


def layout_action_placement(caption, source, source_title=""):
    """Return (tab, group) for an existing QAction, without changing its owner.

    Priority is intentional: atlas actions stay in Atlas even if they are
    exporters, item arrangement goes to Editar even if exposed by itemsMenu.
    Strings are normalized for common PT-BR/English QGIS translations.
    """
    label = normalized(caption)
    origin = normalized(source)
    title = normalized(source_title)
    atlas_source = any(x in (origin + " " + title) for x in
                       ("atlas", "reportmenu", "relatorio", "report"))
    if atlas_source or "atlas" in label:
        return "Atlas", "Atlas"
    if origin == "settingmenu" or origin == "settingsmenu":
        return "Interface", "Preferências"
    if any(x in label for x in EDIT_HISTORY):
        return "Editar", "Histórico"
    if any(x in label for x in EDIT_ORGANIZE):
        return "Editar", "Organizar itens"
    if any(x in label for x in EDIT_GEOMETRY):
        return "Editar", "Ferramentas de edição"
    if any(x in label for x in VIEW_NAV):
        return "Exibir", "Navegação"
    # Creation actions can contain words like Image/SVG; they are NOT export.
    if label.startswith(("adicionar", "add ", "insert", "inserir")):
        return "Inserir", "Adicionar elementos"
    if is_output_action(label):
        return "Exportar", "Impressão e exportação"
    if any(x in label for x in INSERT_ITEMS):
        return "Inserir", "Adicionar elementos"
    if any(x in label for x in FILE_ACTIONS):
        return "Layout", "Arquivo"
    if origin in ("actionstoolbar", "editmenu"):
        return "Editar", "Edição"
    if origin in ("navigationtoolbar", "viewmenu"):
        return "Exibir", "Visualização"
    if origin in ("itemsmenu",):
        return "Inserir", "Elementos"
    if origin in ("layouttoolbar", "layoutmenu"):
        return "Layout", "Projeto de layout"
    if origin in ("reportmenu", "atlasmenu", "atlastoolbar"):
        return "Atlas", "Atlas"
    for name, tab in SOURCE_TABS.items():
        if origin == normalized(name):
            return tab, title_for_source(name)
    tab = tab_for_native_toolbar(source_title or source)
    defaults = {
        "Layout": "Arquivo", "Inserir": "Adicionar elementos", "Editar": "Organizar itens",
        "Exibir": "Navegação", "Atlas": "Atlas", "Exportar": "Impressão e exportação",
    }
    return tab, defaults.get(tab, "Ferramentas")


LAYOUT_GROUP_ORDER = {
    "Layout": ("Arquivo", "Projeto de layout", "Preferências"),
    "Inserir": ("Adicionar elementos", "Elementos"),
    "Editar": ("Ferramentas de edição", "Organizar itens", "Histórico", "Edição"),
    "Exibir": ("Navegação", "Visualização"),
    "Atlas": ("Atlas", "Relatório"),
    "Exportar": ("Impressão e exportação", "Arquivo"),
    "Interface": ("Preferências", "QRibbonSkin"),
}
