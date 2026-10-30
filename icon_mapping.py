"""Presentation-only icon fallback, without changing QGIS QAction objects.

Priority: native QGIS icon -> correlated ArcSkin icon -> new neutral glyph.
The neutral glyphs follow the general light, fine-line aesthetic of RustGIS;
they are newly drawn, not copies of RustGIS artwork.
"""
import unicodedata
from pathlib import Path

ICON_DIR = Path(__file__).resolve().parent / "resources" / "icons"

# More specific patterns first. Portuguese and English labels are supported.
ICON_RULES = (
    (("zoom in", "aproxim", "aumentar zoom"), "zoom_in"),
    (("zoom out", "afast", "diminuir zoom"), "zoom_out"),
    (("identif", "identify", "inspecionar fei"), "identify"),
    (("medir", "measure", "distancia", "area da"), "measure"),
    (("calculadora", "field calculator", "calcular campo"), "field_calculator"),
    (("tabela de atributo", "attribute table", "abrir atributo"), "attribute_table"),
    (("novo projeto", "new project"), "new_project"),
    (("abrir projeto", "open project"), "open_project"),
    (("salvar projeto", "save project", "guardar projeto"), "save_project"),
    (("mapa base", "basemap", "mapa de fundo"), "basemap"),
    (("geoprocess", "processamento", "processing"), "tool"),
    (("estilo", "style", "simbologia", "symbol", "paleta"), "style_manager"),
    (("etiquet", "rotulo", "label"), "labeling"),
    (("estatistic", "statistics", "grafico", "chart", "histograma"), "statistics"),
    (("vetor", "vector", "geometria", "geometry", "buffer"), "vector_tools"),
    (("raster", "pixel", "imagem", "image", "matriz"), "raster_tools"),
    (("database", "banco de dados", "postgis", "sql"), "database"),
    (("plugin", "complement", "extension", "extensao", "add-in"), "plugins"),
    (("camada", "layer", "grupo", "group"), "layer"),
    (("barra de ferramenta", "toolbar"), "toolbars"),
    (("painel", "paineis", "panels", "pane"), "panes"),
    (("navegador", "catalog", "browser"), "catalog"),
    (("atualiz", "refresh", "recarreg"), "refresh"),
    (("selecion", "select", "escolher"), "select"),
    (("mover mapa", "pan map", "deslocar mapa"), "pan"),
    (("editar", "editing", "edit"), "edit"),
    (("3d", "tridimensional"), "map_3d"),
    (("opcoes", "configur", "preferenc", "settings", "options"), "view"),
    (("ajuda", "help", "sobre ", "about"), "help"),
    (("export", "imprimir", "print", "layout"), "print"),
    (("desfazer", "undo", "reverter"), "undo"),
    (("filtro", "filtrar", "filter"), "filter"),
    (("internet", "web", "wms", "xyz", "online"), "web"),
    (("compartilhar", "share", "publicar"), "share"),
    (("coordenada", "coordinates", "projecao", "crs"), "coordinates"),
    (("criar", "adicionar", "new ", "novo ", "add "), "add"),
    (("projeto", "project", "arquivo", "file"), "file"),
    (("exibir", "visualiz", "view", "interface", "classica"), "view"),
)


def normalize_caption(caption):
    text = str(caption or "").replace("&", "").casefold()
    return "".join(char for char in unicodedata.normalize("NFKD", text)
                   if not unicodedata.combining(char))


def icon_name_for_caption(caption):
    text = normalize_caption(caption)
    for fragments, icon_name in ICON_RULES:
        if any(fragment in text for fragment in fragments):
            return icon_name
    return "command"


def fallback_icon(caption):
    from qgis.PyQt.QtGui import QIcon
    # The Processing Toolbox must use QGIS's own themed resource, never
    # ArcSkin's removed geoprocessing.svg. This is presentation-only and
    # does not mutate the native QAction or theme configuration.
    label = normalize_caption(caption)
    if ("caixa de ferramenta" in label or "processing toolbox" in label
            or label.strip() in ("toolbox", "tool box")):
        from qgis.core import QgsApplication
        icon = QgsApplication.getThemeIcon("/processingAlgorithm.svg")
        if not icon.isNull():
            return icon
        # Theme unavailable: use Qt's resource path as a last QGIS fallback.
        return QIcon(":/images/themes/default/processingAlgorithm.svg")
    name = icon_name_for_caption(caption)
    path = ICON_DIR / (name + ".svg")
    if not path.is_file():
        path = ICON_DIR / "command.svg"
    return QIcon(str(path))


def display_icon(qicon, caption):
    """Never mutate `QAction.setIcon` or project icon/theme settings."""
    if qicon is not None and not qicon.isNull():
        return qicon
    return fallback_icon(caption)
