"""QRibbonSkin 0.9.0: isolated, reversible light chrome for native QGIS docks.

Only the *dock chrome* of QGIS Layers, Browser and Processing is styled.
The layer tree, legend nodes, map canvas, symbology, project and global
QApplication palette are deliberately untouched.

This module does NOT move, re-parent, replace, tabify or resize a QDockWidget.
2026-10-23, QRibbonSkin contributors; GPL-2.0.
"""

import unicodedata

from qgis.PyQt.QtCore import QTimer
from qgis.PyQt.QtWidgets import QDockWidget
from qgis.PyQt import sip


BEGIN = "/* QRIBBONSKIN_PANEL_LIGHT_BEGIN_v090 */"
END = "/* QRIBBONSKIN_PANEL_LIGHT_END_v090 */"

# QDockWidget's title bar is provided by Qt when there is no custom title widget.
# A QGIS build with its own title widget retains it untouched.
# Do not target QTreeView, QgsLayerTreeView, QLabel, QAbstractItemView,
# QScrollArea::viewport or QGIS data-driven colors: text and legends need to
# remain exactly as their QGIS renderer and installed theme specify.
DOCK_CHROME_QSS = r"""
QDockWidget {
    border: 1px solid #dce4ed;
    background-color: #ffffff;
}
QDockWidget::title {
    background-color: #f1f5fa;
    color: #233b54;
    border-bottom: 1px solid #dce4ed;
    padding: 5px 8px;
    font-weight: 600;
    text-align: left;
}
QDockWidget::close-button:hover, QDockWidget::float-button:hover {
    background-color: #e1ebf7;
    border-radius: 3px;
}
QDockWidget QToolBar {
    background-color: #f8fafc;
    border: 0;
    border-bottom: 1px solid #e6edf3;
    spacing: 2px;
    padding: 2px;
}
QDockWidget QToolButton {
    background: transparent;
    border: 1px solid transparent;
    border-radius: 4px;
    padding: 2px;
}
QDockWidget QToolButton:hover {
    background: #e8f0fa;
    border-color: #d1e2f6;
}
QDockWidget QToolButton:pressed, QDockWidget QToolButton:checked {
    background: #dbe9fb;
}
QDockWidget QLineEdit {
    background-color: #ffffff;
    color: #253b51;
    selection-color: #ffffff;
    selection-background-color: #2869bf;
    border: 1px solid #cbd7e4;
    border-radius: 5px;
    padding: 3px 6px;
}
QDockWidget QLineEdit:focus {
    border: 1px solid #377ac4;
}
QDockWidget QTabBar::tab {
    background-color: #f1f5fa;
    color: #52667b;
    border: 0;
    border-bottom: 2px solid transparent;
    padding: 4px 9px;
}
QDockWidget QTabBar::tab:selected {
    color: #225dae;
    border-bottom: 2px solid #377ac4;
    background-color: #ffffff;
}
QDockWidget QTabBar::tab:hover {
    background-color: #e7eef7;
}
""".strip()


def normal(text):
    """Locale-independent matching for native translated panel titles."""
    x = unicodedata.normalize("NFKD", str(text or "").casefold())
    return "".join(c for c in x if not unicodedata.combining(c)).strip()


def panel_kind(object_name, title, from_layer_tree=False):
    """Only explicit QGIS panel identities qualify; no arbitrary plugin docks."""
    name = normal(object_name).replace("_", "").replace(" ", "")
    title = normal(title).strip(" -:0123456789")
    if from_layer_tree:
        return "layers"
    if name in ("layers", "layerdock", "layerdockwidget", "layertreedock"):
        return "layers"
    if title in ("camadas", "layers", "painel de camadas"):
        return "layers"
    if name in ("browser", "browserdock", "browserdockwidget", "qgsbrowserdockwidget", "browser2dockwidget"):
        return "browser"
    if title in ("navegador", "navegador 2", "browser", "browser 2"):
        return "browser"
    if name in ("processingtoolbox", "processingtoolboxdock", "processingtoolboxdockwidget"):
        return "processing"
    if title in ("caixa de ferramentas de processamento", "caixa de ferramentas do processamento", "processing toolbox"):
        return "processing"
    return None


def without_own_qss(text):
    """Remove only our marked block; preserve stylesheet changes by others."""
    text = str(text or "")
    start = text.find(BEGIN)
    if start < 0:
        return text
    stop = text.find(END, start + len(BEGIN))
    if stop < 0:
        # Never erase a third-party style if our marker became malformed.
        return text
    return text[:start] + text[stop + len(END):]


def with_own_qss(text):
    """Idempotent injection; the pre-existing dock QSS remains unchanged."""
    base = without_own_qss(text)
    if BEGIN in base:  # malformed delimiter; avoid duplicating the QSS
        return base
    return base + ("\n" if base and not base.endswith("\n") else "") + BEGIN + "\n" + DOCK_CHROME_QSS + "\n" + END


class PanelLightTheme:
    """Live, limited-to-three-panels QSS manager with exact reversible teardown."""

    def __init__(self, iface):
        self.iface = iface
        self._styled = {}  # live Qt dock -> original QSS, never serialized
        self._active = False
        self._timer = QTimer()
        self._timer.setInterval(1800)
        self._timer.timeout.connect(self.refresh)

    def _is_gone(self, widget):
        try:
            return sip.isdeleted(widget)
        except (RuntimeError, TypeError):
            return True

    def _is_layer_tree_dock(self, dock):
        try:
            tree = self.iface.layerTreeView()
            if tree is None or self._is_gone(tree):
                return False
            ancestor = tree
            for _ in range(30):
                if ancestor is dock:
                    return True
                ancestor = ancestor.parentWidget()
                if ancestor is None:
                    break
        except (AttributeError, RuntimeError, TypeError):
            pass
        return False

    def _targets(self):
        main = self.iface.mainWindow()
        for dock in main.findChildren(QDockWidget):
            try:
                if (dock.parent() is main and
                    panel_kind(dock.objectName(), dock.windowTitle(),
                               self._is_layer_tree_dock(dock))):
                    yield dock
            except (RuntimeError, TypeError):
                continue

    def start(self):
        if self._active:
            self.refresh()
            return
        self._active = True
        self.refresh()
        self._timer.start()

    def refresh(self):
        if not self._active:
            return
        for dock in self._targets():
            if dock in self._styled:
                continue
            try:
                original = dock.styleSheet()
                # Do not alter third-party stylesheet content, only append.
                dock.setStyleSheet(with_own_qss(original))
                self._styled[dock] = original
            except (RuntimeError, TypeError):
                continue

    def stop(self):
        self._active = False
        self._timer.stop()
        styled = self._styled
        self._styled = {}
        for dock, original in styled.items():
            try:
                if self._is_gone(dock):
                    continue
                current = dock.styleSheet()
                # If another plugin changed the QSS, preserve its edits.
                restored = without_own_qss(current)
                if restored == original or restored.rstrip("\n") == original.rstrip("\n"):
                    restored = original
                dock.setStyleSheet(restored)
            except (RuntimeError, TypeError):
                # A destroyed dock must not abort toolbar/menu restoration.
                continue

