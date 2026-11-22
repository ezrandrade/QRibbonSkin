"""QRibbonSkin 0.4.0: modern light theme isolated to plugin widgets.

Color palette and stylesheet are independently authored. The theme follows a
minimalist design direction informed by RustGIS but contains no copied RustGIS
source code, SVG icons, color tokens or other resources.

The stylesheet must only be applied to the QRibbonSkin widget tree. It NEVER
changes QApplication's global stylesheet, QGIS map projects or Qt dock widgets.
"""

LIGHT = {
    "canvas": "#f7f9fc",
    "tab": "#edf2f7",
    "hover": "#e2ebf6",
    "pressed": "#d2e3f8",
    "text": "#24364a",
    "muted": "#596e83",
    "accent": "#245fba",
    "accent_surface": "#dceafa",
    "divider": "#d5dee9",
    "border": "#c3d0df",
    "field": "#ffffff",
    "disabled": "#f3f5f8",
}

# Keep every selector specific to a QRibbonSkin-owned object: a native QGIS
# QAction, layer, menu or dock panel must never be globally restyled.
TEMPLATE = r"""
QWidget#QRibbonSkinWidget {
    background-color: @canvas@; color: @text@;
    }
QTabWidget#QRibbonSkinTabs::pane { border: none; margin: 0; padding: 0; background-color: @canvas@; }
QTabWidget#QRibbonSkinTabs QTabBar { border: none; margin: 0; padding: 0; background: transparent; }
QTabWidget#QRibbonSkinTabs QTabBar::tab {
    background-color: transparent; color: @text@;
    padding: 5px 12px; margin: 0 1px; border: 0;
    border-bottom: 2px solid transparent;
}
QTabWidget#QRibbonSkinTabs QTabBar::tab:hover {
    background-color: @hover@;
}
QTabWidget#QRibbonSkinTabs QTabBar::tab:selected {
    background-color: @accent_surface@; color: @accent@;
    border-bottom: 2px solid @accent@;
}
QWidget#QRibbonSkinTabContent {
    background-color: @canvas@; border: 0;
    border-bottom: 0;
}
QFrame#QRibbonSkinGroup, QFrame#QRibbonSkinTaskGroup { border: 0; background-color: transparent; }
QToolButton#QRibbonSkinLeadTool { margin: 0 1px; }
QToolButton#QRibbonSkinCompactTool { margin: 0; text-align: left; }
QLabel#QRibbonSkinGroupLabel {
    color: @muted@; font-size: 8pt; border: 0;
}
QToolButton#QRibbonSkinTool, QToolButton#QRibbonSkinMenuTool, QToolButton#QRibbonSkinStackTool, QToolButton#QRibbonSkinStackMenu, QToolButton#QRibbonSkinLeadTool, QToolButton#QRibbonSkinCompactTool {
    border: 0; border-radius: 4px; background: transparent;
    color: @text@; padding: 0;
}
QToolButton#QRibbonSkinTool:hover, QToolButton#QRibbonSkinMenuTool:hover, QToolButton#QRibbonSkinStackTool:hover, QToolButton#QRibbonSkinStackMenu:hover, QToolButton#QRibbonSkinLeadTool:hover, QToolButton#QRibbonSkinCompactTool:hover {
    background-color: @hover@;
}
QToolButton#QRibbonSkinTool:pressed, QToolButton#QRibbonSkinMenuTool:pressed, QToolButton#QRibbonSkinStackTool:pressed, QToolButton#QRibbonSkinStackMenu:pressed, QToolButton#QRibbonSkinLeadTool:pressed, QToolButton#QRibbonSkinCompactTool:pressed {
    background-color: @pressed@;
}
QToolButton#QRibbonSkinTool:checked, QToolButton#QRibbonSkinStackTool:checked, QToolButton#QRibbonSkinLeadTool:checked, QToolButton#QRibbonSkinCompactTool:checked { background-color: @accent_surface@; }
QScrollArea#QRibbonSkinScroll {
    border: 0; background-color: @canvas@;
}
QToolButton#QRibbonSkinOverflowArrow {
    background-color: @tab@; border: 0;
    color: @text@; padding: 1px;
}
QToolButton#QRibbonSkinOverflowArrow:hover { background-color: @hover@; }
QToolButton#QRibbonSkinOverflowArrow:disabled {
    background-color: @disabled@; color: @muted@;
}
QWidget#QRibbonSkinSearchCorner { background-color: transparent; }
QLineEdit#QRibbonSkinSearch {
    background-color: @field@; color: @text@;
    border: 1px solid @border@; border-radius: 5px;
    padding: 1px 7px; font-size: 9pt;
    selection-background-color: @accent@;
}
QLineEdit#QRibbonSkinSearch:focus {
    border: 1px solid @accent@;
}
"""


def _blend(top, bottom, ratio):
    """Mix two QColors (``ratio`` of ``top``) and return a #rrggbb string."""
    r = round(top.red() * ratio + bottom.red() * (1 - ratio))
    g = round(top.green() * ratio + bottom.green() * (1 - ratio))
    b = round(top.blue() * ratio + bottom.blue() * (1 - ratio))
    return "#%02x%02x%02x" % (r, g, b)


def native_palette():
    """Colour tokens taken from the running QGIS/Qt palette.

    QGIS themes (Default, Blend of Gray, Night Mapping, a system dark mode)
    all reach widgets through QPalette, so reading it keeps every
    QRibbonSkin surface in the user's QGIS colours. Without a running
    QApplication (offline tests) the static LIGHT tokens are returned.
    """
    try:
        from qgis.PyQt.QtGui import QPalette
        from qgis.PyQt.QtWidgets import QApplication
        app = QApplication.instance()
        if app is None:
            return LIGHT.copy()
        pal = app.palette()
    except Exception:  # pragma: no cover - only without Qt bindings
        return LIGHT.copy()
    role = QPalette.ColorRole
    window = pal.color(role.Window)
    base = pal.color(role.Base)
    text = pal.color(role.WindowText)
    highlight = pal.color(role.Highlight)
    mid = pal.color(role.Mid)
    disabled = pal.color(QPalette.ColorGroup.Disabled, role.WindowText)
    return {
        "canvas": base.name(),
        "tab": window.name(),
        "hover": _blend(highlight, base, 0.14),
        "pressed": _blend(highlight, base, 0.30),
        "text": text.name(),
        "muted": _blend(text, window, 0.62),
        "accent": highlight.name(),
        "accent_surface": _blend(highlight, base, 0.22),
        "divider": _blend(mid, window, 0.55),
        "border": mid.name(),
        "field": base.name(),
        "disabled": disabled.name(),
    }


def light_palette():
    """Return a fresh copy of the (native) colour tokens."""
    return native_palette()


def light_stylesheet():
    """Return a complete, locally scoped Qt style sheet for the Ribbon."""
    stylesheet = TEMPLATE
    for name, value in native_palette().items():
        stylesheet = stylesheet.replace("@" + name + "@", value)
    return stylesheet


def nativize(qss):
    """Swap the legacy fixed light colours in a style sheet for native ones.

    The auxiliary editor Ribbons (Georeferencer, Model Designer, Layout
    Designer) were written with literal LIGHT colours. Mapping each literal to
    the same token of :func:`native_palette` keeps their layout untouched
    while following the user's QGIS theme.
    """
    native = native_palette()
    pairs = sorted(((value.lower(), native[key]) for key, value in LIGHT.items()),
                   key=lambda pair: -len(pair[0]))
    pairs.append(("#fff;", native["field"] + ";"))
    out = qss
    for legacy, current in pairs:
        out = out.replace(legacy, current).replace(legacy.upper(), current)
    return out
