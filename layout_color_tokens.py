"""Light-color tokens for the native QGIS Layout Designer chrome.

Limited to the Layout Designer's own Qt widgets. The workspace, layout scene,
map canvas, custom item previews, global QApplication palette and QGIS project
styles are intentionally excluded. This module is importable without QGIS.
"""

from .theme import light_palette

LAYOUT_CHROME = light_palette()
LAYOUT_CHROME.update({
    'panel': '#f7f9fc',            # same neutral base as Ribbon chrome
    'paper_surround': '#d5d5d5',   # documentation ONLY; canvas not styled
})


def _render(qss):
    for key, color in LAYOUT_CHROME.items():
        qss = qss.replace('@'+key+'@', color)
    return qss.strip()


RIBBON_LIGHT_QSS = _render("""
QWidget#QRibbonLayoutWidget { background: @canvas@; color: @text@; }
QTabWidget#QRibbonLayoutTabs::pane { background: @canvas@; border: 0; }
QTabWidget#QRibbonLayoutTabs QTabBar::tab {
    color: @text@; background: transparent; border: 0;
    border-bottom: 2px solid transparent; padding: 5px 13px;
}
QTabWidget#QRibbonLayoutTabs QTabBar::tab:selected {
    color: @accent@; background: @accent_surface@;
    border-bottom: 2px solid @accent@;
}
QTabWidget#QRibbonLayoutTabs QTabBar::tab:hover {background: @hover@;}
QFrame#QRibbonLayoutGroup {border: 0; background: transparent;}
QFrame#QRibbonLayoutDivider {border: 0; background: @divider@;}
QLabel#QRibbonLayoutGroupName {color: @muted@; font-size: 8pt;}
QToolButton {
    color: @text@; background: transparent; border: 1px solid transparent;
    border-radius: 4px; padding: 2px;
}
QToolButton:hover {background: @hover@;}
QToolButton:checked {background: @accent_surface@; border-color: @border@;}
QToolButton:pressed {background: @pressed@;}
QToolButton:disabled {color: @muted@;}
QToolButton#QRibbonLayoutPrimary {padding: 2px;}
""")

RIBBON_TOOLBAR_QSS = _render("""
QToolBar#QRibbonSkinLayoutDesignerToolbar {
    background: @canvas@; border: 0; border-bottom: 1px solid @divider@;
    spacing: 0; padding: 0;
}
""")

TOOLBAR_LIGHT_QSS = _render("""
QToolBar {background: @canvas@; color: @text@; border: 0;
    border-bottom: 1px solid @divider@; spacing: 2px; padding: 2px;}
QToolBar QToolButton {color: @text@; background: transparent;
    border: 1px solid transparent; border-radius: 4px; padding: 2px;}
QToolBar QToolButton:hover {background: @hover@;}
QToolBar QToolButton:checked {background: @accent_surface@;}
QToolBar QToolButton:disabled {color: @muted@;}
QToolBar QComboBox, QToolBar QSpinBox {color: @text@; background: @field@;
    border: 1px solid @border@; border-radius: 3px; padding: 2px;}
""")

DOCK_LIGHT_QSS = _render("""
QDockWidget {background: @panel@; border: 1px solid @divider@;}
QDockWidget::title {background: @canvas@; color: @text@;
    border-bottom: 1px solid @divider@; padding: 5px 9px;}
QDockWidget QTabBar::tab {background: @tab@; color: @muted@;
    border: 0; border-bottom: 2px solid transparent; padding: 6px 10px;}
QDockWidget QTabBar::tab:selected {background: @panel@; color: @accent@;
    border-bottom: 2px solid @accent@;}
QDockWidget QTabBar::tab:hover {background: @hover@;}
QDockWidget QGroupBox {
    color: @text@; background: @panel@;
    border: 1px solid @divider@; border-radius: 2px;
    padding: 1px 2px 3px 2px;
}
QDockWidget QGroupBox::title {color: @text@; background: @panel@;}
QDockWidget QTabWidget::pane {background: @panel@;
    border-top: 1px solid @divider@;}
QDockWidget QScrollArea {background: @panel@; border: 0;}
QDockWidget QScrollArea > QWidget#qt_scrollarea_viewport {background: @panel@;}
QDockWidget QTreeView, QDockWidget QTableView {background: @panel@; color: @text@;}
QDockWidget QToolButton {
    color: @text@; background: transparent;
    border: 1px solid transparent; border-radius: 3px; padding: 2px;}
QDockWidget QPushButton {color: @text@; background: @tab@;
    border: 1px solid @border@; border-radius: 3px; padding: 2px;}
QDockWidget QToolButton:hover, QDockWidget QPushButton:hover {background: @hover@;}
QDockWidget QLineEdit, QDockWidget QComboBox,
QDockWidget QAbstractSpinBox, QDockWidget QSpinBox,
QDockWidget QDoubleSpinBox {
    background: @field@; color: @text@;
    selection-background-color: @accent_surface@;
    border: 1px solid @divider@; border-radius: 2px;
    padding: 1px 2px;
}
QDockWidget QComboBox::drop-down {
    background: @field@; border: 0;
    border-left: 1px solid @divider@; width: 17px;
}
QDockWidget QLineEdit:focus, QDockWidget QComboBox:focus,
QDockWidget QAbstractSpinBox:focus {
    border: 1px solid @accent@;
}
""")

# Native tab strips for dock widgets which Qt places directly under QMainWindow.
TAB_LIGHT_QSS = _render("""
QTabBar::tab {background: @tab@; color: @muted@;
    border: 0; border-bottom: 2px solid transparent; padding: 6px 10px;}
QTabBar::tab:selected {background: @panel@; color: @accent@;
    border-bottom: 2px solid @accent@;}
QTabBar::tab:hover {background: @hover@;}
""")

MENU_LIGHT_QSS = _render("""
QMenuBar {background: @canvas@; color: @text@;
    border-bottom: 1px solid @divider@;}
QMenuBar::item:selected {background: @hover@;}
""")

STATUS_LIGHT_QSS = _render("""
QStatusBar {background: @canvas@; color: @text@;
    border-top: 1px solid @divider@;}
QStatusBar::item {border: 0;}
""")

RULER_LIGHT_QSS = _render("""
QgsLayoutRuler {background: @canvas@; color: @text@;
    border: 0; border-bottom: 1px solid @divider@;}
""")
