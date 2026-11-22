"""RustGIS-style Ribbons for the QGIS editor windows.

Layout Designer, Georeferencer and Processing Model Designer get the same
Ribbon component as the main window (ribbon.RibbonFrame), driven by the
declarative specs in editor_specs.py.

Non-invasive by design:
* native toolbars and the menu bar of the editor are only *hidden* (their
  visibility is snapshotted and restored); no QAction is removed from them,
  no dock or canvas is restyled, re-parented or replaced;
* "Barras nativas" (Settings tab) shows the original controls again.

Light by design:
* Layout Designer: QGIS's own layoutDesignerOpened/WillBeClosed signals.
* Georeferencer and Model Designer have no "opened" signal. Instead of an
  application-wide event filter (which would put every QGIS event through
  Python), they are found when (a) their native QGIS "open" action fires or
  (b) keyboard focus moves into a new window (QApplication.focusChanged,
  emitted only on focus changes).
"""

import sys

from qgis.PyQt.QtCore import QObject, Qt, QTimer, QCoreApplication
from qgis.PyQt.QtWidgets import QApplication, QMainWindow, QMenu, QSizePolicy, QToolBar

from .compat import QAction
from .i18n import tr
from .ribbon import RibbonFrame, clean_caption
from .editor_specs import LayoutSpec, GeoreferencerSpec, ModelDesignerSpec, NATIVE_BARS

TOOLBAR_NAME = "QRibbonSkinEditorToolbar"


def _alive(obj):
    """False for None or a deleted Qt object; True for live/non-Qt objects."""
    if obj is None:
        return False
    try:
        from qgis.PyQt import sip
        return not sip.isdeleted(obj)
    except TypeError:
        return True  # not a sip wrapper (e.g. a plain Python object)
    except (ImportError, AttributeError):
        try:
            obj.objectName()
        except RuntimeError:
            return False
        except AttributeError:
            pass
        return True


def _log(message):
    """Warn in the QGIS log; fall back to stderr (logging must never raise)."""
    try:
        from qgis.core import QgsMessageLog, Qgis
        QgsMessageLog.logMessage(message, "QRibbonSkin", Qgis.MessageLevel.Warning)
    except (ImportError, AttributeError, RuntimeError):  # pragma: no cover
        sys.stderr.write("QRibbonSkin: %s\n" % message)


# --------------------------------------------------------------- layout items
def _registry():
    try:
        from qgis.gui import QgsGui
        return QgsGui.layoutItemGuiRegistry()
    except Exception:  # pragma: no cover - outside QGIS
        return None


def _item_types():
    """Item type → Ribbon group, from QgsLayoutItemRegistry (by enum, never
    by translated text). Types missing in a QGIS build are skipped."""
    try:
        from qgis.core import QgsLayoutItemRegistry as R
    except ImportError:  # pragma: no cover
        return {}
    table = {
        "map_frames": ("LayoutMap", "Layout3DMap", "LayoutElevationProfile"),
        "surrounds": ("LayoutLegend", "LayoutScaleBar", "LayoutAttributeTable",
                      "LayoutManualTable", "LayoutChart"),
        "shapes": ("LayoutShape", "LayoutPolygon", "LayoutPolyline"),
        "text": ("LayoutLabel", "LayoutPicture", "LayoutHtml", "LayoutMarker",
                 "LayoutTextTable"),
    }
    out = {}
    for source, names in table.items():
        for name in names:
            value = getattr(R, name, None)
            if value is None and hasattr(R, "ItemType"):
                value = getattr(R.ItemType, name, None)
            if value is not None:
                out[int(value)] = source
    return out


def _north_arrow_name():
    """QGIS registers the north arrow as a *picture* item named
    QObject::tr("North Arrow"); it belongs with the map surrounds."""
    return {QCoreApplication.translate("QObject", "North Arrow"), "North Arrow"}


class EditorRibbon(RibbonFrame):
    """RibbonFrame for an editor window, plus the layout item commands."""

    def __init__(self, window, spec_module, own=None, parent=None):
        self._item_cache = None
        super().__init__(window, spec_module, own, parent)
        self.start()

    # Layout Designer "Add item" commands, classified by registry item type.
    def _layout_items(self):
        if self._item_cache is not None:
            return self._item_cache
        found = {"map_frames": [], "surrounds": [], "shapes": [], "text": []}
        item_menu = self._window.findChild(QMenu, "mItemMenu")
        registry = _registry()
        types = _item_types()
        north = _north_arrow_name()
        if item_menu is None:
            self._item_cache = found
            return found

        def classify(action):
            if registry is None:
                return None, ""
            try:
                meta = registry.itemMetadata(int(action.data()))
            except (TypeError, ValueError):
                return None, ""
            if meta is None:
                return None, ""
            name = meta.visibleName()
            source = types.get(int(meta.type()))
            if source == "text" and name in north:
                source = "surrounds"
            return source, name

        for entry in item_menu.actions():
            if entry.isSeparator() or not entry.isVisible():
                continue
            sub = entry.menu()
            if sub is None:
                source, name = classify(entry)
                if source:
                    entry.setProperty("qrsCaption", name)
                    found[source].append((entry, None))
                continue
            children = [a for a in sub.actions() if not a.isSeparator()]
            sources = {classify(a)[0] for a in children} - {None}
            if not children or not sources:
                # QGIS's "Add Dynamic Text" menu: expressions, no registry type.
                found["text"].append((None, sub))
            else:
                found[sorted(sources)[0]].append((None, sub))
        self._item_cache = found
        return found

    def dynamic_actions(self, source):
        return self._layout_items().get(source, [])

    def dynamic_caption(self, action):
        caption = action.property("qrsCaption")
        return str(caption) if caption else clean_caption(action.text())

    def dynamic_menu_caption(self, menu):
        """QGIS titles item groups tr("Add %1"); show only the %1 part, using
        QGIS's own translation of that pattern (no hard-coded language)."""
        title = clean_caption(menu.title())
        for pattern in {QCoreApplication.translate("QgsLayoutDesignerDialog", "Add %1"),
                        "Add %1"}:
            prefix, _sep, suffix = pattern.partition("%1")
            if prefix and title.startswith(prefix) and title.endswith(suffix):
                core = title[len(prefix):len(title) - len(suffix) if suffix else None].strip()
                return core[:1].upper() + core[1:] if core else title
        return title


class EditorSession(QObject):
    """One Ribbon on one editor window; fully reversible."""

    def __init__(self, window, spec_module, parent=None):
        super().__init__(parent)
        self.window = window
        self._disposed = False
        self._bars = []
        self._menu_bar_visible = None
        self._added_break_before = None
        native = window.menuBar() if hasattr(window, "menuBar") else None
        self._menu_bar = native
        self.native_action = None
        self.toolbar = QToolBar(tr("QRibbonSkin"), window)
        self.toolbar.setObjectName(TOOLBAR_NAME)
        self.toolbar.setMovable(False)
        self.toolbar.setFloatable(False)
        self.toolbar.setAllowedAreas(Qt.ToolBarArea.TopToolBarArea)
        self.toolbar.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.toolbar.setStyleSheet(
            "QToolBar#%s { background: palette(window); border: 0; padding: 0; "
            "margin: 0; spacing: 0; }" % TOOLBAR_NAME)
        try:
            self.native_action = QAction(tr("Barras nativas"), self.toolbar)
            self.native_action.setCheckable(True)
            self.native_action.toggled.connect(self.set_native_visible)
            self.ribbon = EditorRibbon(window, spec_module, {NATIVE_BARS: self.native_action})
            self.toolbar.addWidget(self.ribbon)
            self._install_top_row()
            self._hide_native()
            self.toolbar.show()
            window.destroyed.connect(self._on_window_destroyed)
        except Exception:
            self.dispose()
            raise

    def _native_bars(self):
        return [bar for bar in self.window.findChildren(QToolBar)
                if bar.parent() is self.window and bar is not self.toolbar]

    def _install_top_row(self):
        """Put the Ribbon on its own row above the editor's toolbars."""
        top = Qt.ToolBarArea.TopToolBarArea
        bars = [b for b in self._native_bars() if self.window.toolBarArea(b) == top]
        if not bars:
            self.window.addToolBar(top, self.toolbar)
            return
        anchor = bars[0]
        self.window.insertToolBar(anchor, self.toolbar)
        if not self.window.toolBarBreak(anchor):
            self.window.insertToolBarBreak(anchor)
            self._added_break_before = anchor

    def _hide_native(self):
        self._bars = [(bar, bar.isVisible()) for bar in self._native_bars()]
        for bar, _visible in self._bars:
            bar.hide()
        if self._menu_bar is not None:
            self._menu_bar_visible = self._menu_bar.isVisible()
            self._menu_bar.hide()

    def set_native_visible(self, visible):
        """Show the editor's original toolbars and menu bar again (or not)."""
        for bar, was_visible in self._bars:
            if not _alive(bar):
                continue
            bar.setVisible(bool(visible) and was_visible)
        if self._menu_bar is not None and _alive(self._menu_bar):
            self._menu_bar.setVisible(bool(visible))

    def _on_window_destroyed(self, *_args):
        self._disposed = True

    def dispose(self):
        if self._disposed:
            return
        self._disposed = True
        if not _alive(self.window):
            return
        for bar, was_visible in self._bars:
            if _alive(bar):
                try:
                    bar.setVisible(was_visible)
                except RuntimeError:
                    pass
        if self._menu_bar is not None and _alive(self._menu_bar) and self._menu_bar_visible is not None:
            self._menu_bar.setVisible(self._menu_bar_visible)
        ribbon = getattr(self, "ribbon", None)
        if _alive(ribbon):
            ribbon.release()
        anchor = self._added_break_before
        if anchor is not None and _alive(anchor):
            try:
                self.window.removeToolBarBreak(anchor)
            except RuntimeError:
                pass
        if _alive(self.toolbar):
            try:
                self.window.removeToolBar(self.toolbar)
                self.toolbar.deleteLater()
            except RuntimeError:
                pass


# ------------------------------------------------------------------ managers
class LayoutDesignerManager(QObject):
    """Follow QGIS's documented layout designer lifecycle signals."""

    def __init__(self, iface, parent=None):
        super().__init__(parent)
        self.iface = iface
        self._sessions = {}
        self._started = False
        self.last_error = None

    def start(self):
        if self._started:
            return
        self.iface.layoutDesignerOpened.connect(self._on_opened)
        self.iface.layoutDesignerWillBeClosed.connect(self._on_will_close)
        self._started = True
        for designer in (self.iface.openLayoutDesigners() or []):
            self._on_opened(designer)

    def _on_opened(self, designer):
        if not self._started or not _alive(designer) or id(designer) in self._sessions:
            return
        try:
            window = designer.window()
            if not isinstance(window, QMainWindow):
                return
            self._sessions[id(designer)] = EditorSession(window, LayoutSpec, self)
        except Exception as exc:  # never break QGIS or the main Ribbon
            self.last_error = str(exc)
            _log("Layout Designer Ribbon: %s" % exc)

    def _on_will_close(self, designer):
        session = self._sessions.pop(id(designer), None)
        if session is not None:
            session.dispose()

    def stop(self):
        if self._started:
            for signal, slot in ((self.iface.layoutDesignerOpened, self._on_opened),
                                 (self.iface.layoutDesignerWillBeClosed, self._on_will_close)):
                try:
                    signal.disconnect(slot)
                except (RuntimeError, TypeError):
                    pass
        self._started = False
        for session in list(self._sessions.values()):
            session.dispose()
        self._sessions.clear()


class _WindowManager(QObject):
    """Find an editor window without an application-wide event filter."""

    SPEC = None
    OPEN_ACTION = None

    def __init__(self, iface, parent=None):
        super().__init__(parent)
        self.iface = iface
        self._active = False
        self._sessions = {}
        self._scheduled = False
        self._open_action = None
        self.last_error = None

    def matches(self, window):  # pragma: no cover - overridden
        return False

    def start(self):
        if self._active:
            return
        app = QApplication.instance()
        if app is None:
            return
        self._active = True
        app.focusChanged.connect(self._on_focus_changed)
        try:
            window = self.iface.mainWindow()
            self._open_action = next(
                (a for a in (window.findChild(QAction, n) for n in self.OPEN_ACTION.split("|"))
                 if a is not None), None)
        except (AttributeError, RuntimeError):
            self._open_action = None
        if self._open_action is not None:
            self._open_action.triggered.connect(self._schedule)
        self._scan()

    def _on_focus_changed(self, _old, new):
        if new is None or not self._active:
            return
        try:
            window = new.window()
        except RuntimeError:
            return
        if window is not None and id(window) not in self._sessions and self.matches(window):
            self._schedule()

    def _schedule(self, *_args):
        if self._active and not self._scheduled:
            self._scheduled = True
            QTimer.singleShot(0, self._scan)
            # A window may still be under construction when its action fires.
            QTimer.singleShot(400, self._scan)

    def _scan(self):
        self._scheduled = False
        if not self._active:
            return
        app = QApplication.instance()
        if app is None:
            return
        for key in [k for k, s in self._sessions.items() if s._disposed]:
            self._sessions.pop(key, None)
        for window in app.topLevelWidgets():
            try:
                if (not isinstance(window, QMainWindow) or not window.isVisible()
                        or id(window) in self._sessions or not self.matches(window)):
                    continue
                self._sessions[id(window)] = EditorSession(window, self.SPEC, self)
            except Exception as exc:  # never break QGIS or the main Ribbon
                self.last_error = str(exc)
                _log("%s Ribbon: %s" % (type(self).__name__, exc))

    def stop(self):
        app = QApplication.instance()
        if self._active and app is not None:
            try:
                app.focusChanged.disconnect(self._on_focus_changed)
            except (RuntimeError, TypeError):
                pass
        if self._open_action is not None:
            try:
                self._open_action.triggered.disconnect(self._schedule)
            except (RuntimeError, TypeError):
                pass
        self._active = False
        for session in list(self._sessions.values()):
            session.dispose()
        self._sessions.clear()


class GeoreferencerManager(_WindowManager):
    """Standalone Georeferencer window (QgsGeoreferencerMainWindow)."""

    SPEC = GeoreferencerSpec
    OPEN_ACTION = "mActionShowGeoreferencer"
    CLASSES = ("QgsGeoreferencerMainWindow", "QgsGeorefPluginGui")

    def matches(self, window):
        try:
            return (window.isWindow() and isinstance(window, QMainWindow)
                    and window.metaObject().className() in self.CLASSES)
        except RuntimeError:
            return False


class ModelDesignerManager(_WindowManager):
    """Processing Model Designer (QgsModelDesignerDialog and subclasses)."""

    SPEC = ModelDesignerSpec
    OPEN_ACTION = "mActionModelDesigner|modelerAction"  # QGIS 4.x | QGIS 3.44

    def matches(self, window):
        try:
            return isinstance(window, QMainWindow) and bool(window.inherits("QgsModelDesignerDialog"))
        except (RuntimeError, AttributeError, TypeError):
            return False
