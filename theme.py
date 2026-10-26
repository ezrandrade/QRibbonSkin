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
    font-family: 'Segoe UI', 'Noto Sans', sans-serif;
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


def light_palette():
    """Return a copy to prevent callers from modifying shared theme tokens."""
    return LIGHT.copy()


def light_stylesheet():
    """Return a complete, locally scoped Qt style sheet for the Ribbon."""
    stylesheet = TEMPLATE
    for name, value in LIGHT.items():
        stylesheet = stylesheet.replace("@" + name + "@", value)
    return stylesheet
