"""RustGIS-style Ribbon for the QGIS main window, built from native QGIS objects.

Layout (top to bottom), as in RustGIS:

1. Header row      – Quick Access Toolbar (left) and command search (right).
2. Tab strip       – a "Projeto" button, the tabs and a collapse chevron.
3. Ribbon          – the active tab's labelled groups; arrow buttons scroll it
                     when the window is too narrow.

Every control reuses a QGIS-owned QAction or QMenu (see ribbon_spec.py), so
icons, translations, enabled/checked state and shortcuts stay native. Colours
come from the running QPalette, so the Ribbon follows the user's QGIS theme.

Performance rules: no timers, no application-wide event filter, no menu
rescans. Tab pages are built lazily on first view; the three layer-dependent
tabs (Data, Style, Labeling) are rebuilt only when the kind of the selected
layer changes, and only when they are visible. The Project button opens the
native Project menu: the QGIS welcome page and project workflow are untouched.
"""

from pathlib import Path

from qgis.PyQt.QtCore import Qt, QSize, QRect, QPointF, QTimer, QStringListModel
from qgis.PyQt.QtGui import (QAction, QColor, QFontMetrics, QIcon, QKeySequence, QPainter,
                             QPainterPath, QPalette, QPen, QPixmap, QShortcut)
from qgis.PyQt.QtWidgets import (
    QCompleter, QDockWidget, QFrame, QHBoxLayout, QLabel, QLineEdit, QMenu,
    QScrollArea, QSizePolicy, QStackedWidget, QStyle, QStyleOptionToolButton, QStylePainter,
    QTabBar, QToolBar, QToolButton, QVBoxLayout, QWidget,
)

from .i18n import tr
from . import ribbon_spec as spec

ICON_DIR = Path(__file__).resolve().parent / "resources" / "icons" / "qgis_style"

# RustGIS metrics (crates/ui-egui/src/widgets.rs, ribbon.rs, chrome.rs).
HEADER_H = 30
TAB_STRIP_H = 30
CONTENT_H = 72
LABEL_H = 18
RIBBON_H = CONTENT_H + LABEL_H + 10
BIG_H = CONTENT_H - 2
BIG_ICON = 32
SMALL_H = 22
SMALL_ICON = 16
SCROLL_BUTTON_W = 18
COLLAPSE_SHORTCUT = "Ctrl+F1"
SEARCH_SHORTCUT = "Alt+Q"

# QGIS's own toolbars (qgisapp.ui); anything else belongs to a plugin.
CORE_TOOLBARS = frozenset((
    "mFileToolBar", "mLayerToolBar", "mDigitizeToolBar", "mAdvancedDigitizeToolBar",
    "mMapNavToolBar", "mAttributesToolBar", "mPluginToolBar", "mHelpToolBar",
    "mRasterToolBar", "mLabelToolBar", "mVectorToolBar", "mDatabaseToolBar",
    "mWebToolBar", "mSnappingToolBar", "mDataSourceManagerToolBar",
    "mShapeDigitizeToolBar", "mSelectionToolBar", "mMeshToolBar",
    "mAnnotationsToolBar", "mLayerTreeToolBar", "QRibbonSkinToolbar",
))


def clean_caption(text):
    """Native QAction text without mnemonics, ellipsis or shortcut suffix."""
    text = str(text or "").split("\t")[0]
    text = text.replace("&&", "\u0000").replace("&", "").replace("\u0000", "&")
    return text.replace("…", "").replace("...", "").strip()


def theme_icon(path):
    """A QGIS theme icon ("/name.svg") or a QRibbonSkin one ("qrs:name.svg")."""
    if not path:
        return QIcon()
    if path.startswith("qrs:"):
        return QIcon(str(ICON_DIR / path[4:]))
    try:
        from qgis.core import QgsApplication
        icon = QgsApplication.getThemeIcon(path)
        if icon is not None and not icon.isNull():
            return icon
    except Exception:  # pragma: no cover - outside QGIS
        pass
    return QIcon(":/images/themes/default" + path)


def _mix(top, bottom, ratio):
    return QColor(round(top.red() * ratio + bottom.red() * (1 - ratio)),
                  round(top.green() * ratio + bottom.green() * (1 - ratio)),
                  round(top.blue() * ratio + bottom.blue() * (1 - ratio)))


def stylesheet():
    """Style sheet scoped to QRibbonSkin objects; colours are palette roles."""
    return """
QWidget#QRibbonSkinWidget { background: palette(window); }
QWidget#QRibbonSkinHeader { background: palette(window); }
QWidget#QRibbonSkinTabStrip { background: palette(window); }
QWidget#QRibbonSkinBody, QStackedWidget#QRibbonSkinPages,
QScrollArea#QRibbonSkinScroll, QWidget#QRibbonSkinScrollContent {
    background: palette(base); border: 0;
}
QTabBar#QRibbonSkinTabs { background: transparent; border: 0; }
QTabBar#QRibbonSkinTabs::tab {
    background: transparent; color: palette(window-text);
    border: 1px solid transparent; border-bottom: 0;
    border-top-left-radius: 4px; border-top-right-radius: 4px;
    padding: 4px 13px 5px 13px; margin: 3px 1px 0 1px;
}
QTabBar#QRibbonSkinTabs::tab:hover:!selected { background: palette(midlight); }
QTabBar#QRibbonSkinTabs::tab:selected {
    background: palette(base); border-color: palette(mid);
    border-bottom: 2px solid palette(highlight); font-weight: 600;
}
QToolButton#QRibbonSkinProjectButton {
    background: palette(highlight); color: palette(highlighted-text);
    border: 0; border-radius: 4px; padding: 2px 12px; font-weight: 600;
}
QToolButton#QRibbonSkinProjectButton:hover { background: palette(dark); }
QToolButton#QRibbonSkinProjectButton::menu-indicator { image: none; width: 0; }
QLineEdit#QRibbonSkinSearch {
    background: palette(base); color: palette(text);
    border: 1px solid palette(mid); border-radius: 11px; padding: 1px 10px;
}
QLineEdit#QRibbonSkinSearch:focus { border: 1px solid palette(highlight); }
QLabel#QRibbonSkinGroupLabel { background: transparent; }
QLabel#QRibbonSkinHint { background: transparent; }
"""


class ActionIndex:
    """objectName → QAction/QMenu of the QGIS main window, read once.

    One ``findChildren`` pass replaces hundreds of recursive ``findChild``
    calls. Objects created later by QGIS (rare) are looked up on demand.
    """

    def __init__(self, window):
        self.window = window
        self.actions = {}
        self.menus = {}
        for action in window.findChildren(QAction):
            name = action.objectName()
            if name and name not in self.actions:
                self.actions[name] = action
        for qmenu in window.findChildren(QMenu):
            name = qmenu.objectName()
            if name and name not in self.menus:
                self.menus[name] = qmenu

    def action(self, name):
        found = self.actions.get(name)
        if found is None:
            found = self.window.findChild(QAction, name)
            if found is None:
                dock_name = spec.DOCK_FALLBACK.get(name)
                if dock_name:
                    dock = self.window.findChild(QDockWidget, dock_name)
                    if dock is not None:
                        found = dock.toggleViewAction()
            if found is not None:
                self.actions[name] = found
        return found

    def menu(self, name):
        found = self.menus.get(name)
        if found is None:
            found = self.window.findChild(QMenu, name)
            if found is not None:
                self.menus[name] = found
        return found


class RibbonButton(QToolButton):
    """A big (icon over caption) or small (icon left of caption) control.

    The QAction (when there is one) drives trigger, enabled, checked and
    tooltip natively through ``setDefaultAction``. The frame is drawn by the
    native QStyle (as QGIS toolbars are); only icon/caption placement is ours.
    """

    def __init__(self, size, caption, fallback_icon=None, action=None, parent=None):
        super().__init__(parent)
        self._size = size
        self._caption = caption
        self._fallback = fallback_icon or QIcon()
        self.setAutoRaise(True)
        self.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        if action is not None:
            self.setDefaultAction(action)
            tip = clean_caption(action.toolTip() or action.text())
            shortcut = action.shortcut().toString(QKeySequence.SequenceFormat.NativeText)
            if shortcut and shortcut not in tip:
                tip = "%s (%s)" % (tip, shortcut)
            self.setToolTip(tip)
        self._fit()

    def set_tooltip_text(self, text):
        if text:
            self.setToolTip(text)

    def actionEvent(self, event):  # noqa: N802
        # QToolButton copies the QAction's tooltip on every change; keep ours.
        tip = self.toolTip()
        super().actionEvent(event)
        if tip:
            self.setToolTip(tip)
        self.update()

    def _icon(self):
        icon = self.icon()
        return self._fallback if icon.isNull() else icon

    def _has_menu_arrow(self):
        return self.menu() is not None and \
            self.popupMode() == QToolButton.ToolButtonPopupMode.InstantPopup

    def _fit(self):
        metrics = QFontMetrics(self.font())
        caret = 9 if self._has_menu_arrow() else 0
        if self._size == "big":
            lines = self._caption.split("\n") if self._caption else [""]
            width = max(metrics.horizontalAdvance(line) for line in lines) + caret
            if self.popupMode() == QToolButton.ToolButtonPopupMode.MenuButtonPopup:
                width += 12
            self.setFixedSize(max(50, width + 14), BIG_H)
        else:
            text = metrics.horizontalAdvance(self._caption) + 8 if self._caption else 0
            extra = 12 if self.menu() is not None else 0
            self.setFixedSize(SMALL_ICON + 8 + text + extra, SMALL_H)

    def setMenu(self, menu):  # noqa: N802
        super().setMenu(menu)
        self._fit()

    def setPopupMode(self, mode):  # noqa: N802
        super().setPopupMode(mode)
        self._fit()

    def paintEvent(self, _event):  # noqa: N802
        opt = QStyleOptionToolButton()
        self.initStyleOption(opt)
        opt.text = ""
        opt.icon = QIcon()
        if self._has_menu_arrow():
            # A RustGIS-style caret is drawn after the caption instead.
            opt.features &= ~QStyleOptionToolButton.ToolButtonFeature.HasMenu
        painter = QStylePainter(self)
        painter.drawComplexControl(QStyle.ComplexControl.CC_ToolButton, opt)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        enabled = self.isEnabled()
        mode = QIcon.Mode.Normal if enabled else QIcon.Mode.Disabled
        state = QIcon.State.On if self.isChecked() else QIcon.State.Off
        group = QPalette.ColorGroup.Normal if enabled else QPalette.ColorGroup.Disabled
        color = self.palette().color(group, QPalette.ColorRole.ButtonText)
        painter.setPen(color)
        metrics = QFontMetrics(self.font())
        arrow_room = 12 if self.popupMode() == QToolButton.ToolButtonPopupMode.MenuButtonPopup else 0
        body = QRect(0, 0, self.width() - arrow_room, self.height())
        icon = self._icon()
        if self._size == "big":
            icon_rect = QRect(body.center().x() - BIG_ICON // 2 + 1, 5, BIG_ICON, BIG_ICON)
            if not icon.isNull():
                icon.paint(painter, icon_rect, Qt.AlignmentFlag.AlignCenter, mode, state)
            lines = self._caption.split("\n") if self._caption else []
            y = 41
            for index, line in enumerate(lines):
                last = index == len(lines) - 1
                width = metrics.horizontalAdvance(line)
                caret = 9 if (last and self._has_menu_arrow()) else 0
                x = body.center().x() - (width + caret) // 2 + 1
                painter.drawText(QRect(x, y, width + 2, metrics.height()),
                                 Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop, line)
                if caret:
                    self._caret(painter, QPointF(x + width + 5.5, y + metrics.ascent() / 2 + 2), color)
                y += metrics.lineSpacing() - 1
        else:
            icon_rect = QRect(4, (self.height() - SMALL_ICON) // 2, SMALL_ICON, SMALL_ICON)
            if not icon.isNull():
                icon.paint(painter, icon_rect, Qt.AlignmentFlag.AlignCenter, mode, state)
            text_rect = QRect(SMALL_ICON + 8, 0, body.width() - SMALL_ICON - 8, self.height())
            painter.drawText(text_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                             self._caption)
            if self._has_menu_arrow():
                self._caret(painter, QPointF(self.width() - 7, self.height() / 2), color)
        painter.end()

    @staticmethod
    def _caret(painter, centre, color):
        path = QPainterPath()
        path.moveTo(centre.x() - 3.5, centre.y() - 1.8)
        path.lineTo(centre.x() + 3.5, centre.y() - 1.8)
        path.lineTo(centre.x(), centre.y() + 2.2)
        path.closeSubpath()
        painter.fillPath(path, color)


class RibbonGroup(QWidget):
    """Controls over a centred caption, closed by a vertical divider."""

    def __init__(self, title, parent=None):
        super().__init__(parent)
        self.setObjectName("QRibbonSkinGroup")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(3, 2, 9, 0)
        outer.setSpacing(0)
        self.row = QHBoxLayout()
        self.row.setContentsMargins(0, 0, 0, 0)
        self.row.setSpacing(2)
        self.row.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        holder = QWidget(self)
        holder.setFixedHeight(CONTENT_H)
        holder.setLayout(self.row)
        outer.addWidget(holder)
        self.label = QLabel(title, self)
        self.label.setObjectName("QRibbonSkinGroupLabel")
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label.setFixedHeight(LABEL_H)
        font = self.label.font()
        font.setPointSizeF(max(7.0, font.pointSizeF() - 1.0))
        self.label.setFont(font)
        pal = self.label.palette()
        window = pal.color(QPalette.ColorRole.Window)
        text = pal.color(QPalette.ColorRole.WindowText)
        pal.setColor(QPalette.ColorRole.WindowText, _mix(text, window, 0.62))
        self.label.setPalette(pal)
        outer.addWidget(self.label)
        self.count = 0

    def add(self, widget):
        self.row.addWidget(widget, 0, Qt.AlignmentFlag.AlignTop)
        self.count += 1

    def paintEvent(self, event):  # noqa: N802
        super().paintEvent(event)
        painter = QPainter(self)
        pal = self.palette()
        painter.setPen(QPen(_mix(pal.color(QPalette.ColorRole.Mid),
                                 pal.color(QPalette.ColorRole.Base), 0.6), 1))
        x = self.width() - 4
        painter.drawLine(x, 6, x, self.height() - 4)
        painter.end()


class ScrollArrow(QToolButton):
    """Left/right arrow at the edge of an overflowing Ribbon (RustGIS)."""

    def __init__(self, left, parent=None):
        super().__init__(parent)
        self.left = left
        self.setAutoRaise(True)
        self.setFixedWidth(SCROLL_BUTTON_W)
        self.setToolTip(tr("Rolar a Ribbon para a esquerda") if left
                        else tr("Rolar a Ribbon para a direita"))

    def paintEvent(self, event):  # noqa: N802
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(QPen(self.palette().color(QPalette.ColorRole.ButtonText), 1.6,
                            Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap,
                            Qt.PenJoinStyle.RoundJoin))
        c = QPointF(self.width() / 2, self.height() / 2)
        d = -1 if self.left else 1
        painter.drawPolyline([QPointF(c.x() - 2.5 * d, c.y() - 5), QPointF(c.x() + 2.5 * d, c.y()),
                              QPointF(c.x() - 2.5 * d, c.y() + 5)])
        painter.end()


class RibbonPage(QWidget):
    """Horizontally scrolling row of groups with edge arrows when needed."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("QRibbonSkinBody")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.left = ScrollArrow(True, self)
        self.right = ScrollArrow(False, self)
        self.scroll = QScrollArea(self)
        self.scroll.setObjectName("QRibbonSkinScroll")
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setWidgetResizable(False)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.content = QWidget()
        self.content.setObjectName("QRibbonSkinScrollContent")
        self.row = QHBoxLayout(self.content)
        self.row.setContentsMargins(6, 3, 6, 0)
        self.row.setSpacing(0)
        self.row.setSizeConstraint(QHBoxLayout.SizeConstraint.SetFixedSize)
        self.scroll.setWidget(self.content)
        layout.addWidget(self.left)
        layout.addWidget(self.scroll, 1)
        layout.addWidget(self.right)
        bar = self.scroll.horizontalScrollBar()
        bar.valueChanged.connect(self._update_arrows)
        bar.rangeChanged.connect(self._update_arrows)
        self.left.clicked.connect(lambda: self._step(-1))
        self.right.clicked.connect(lambda: self._step(1))
        self._update_arrows()

    def add_group(self, grp):
        self.row.addWidget(grp, 0, Qt.AlignmentFlag.AlignTop)

    def wheelEvent(self, event):  # noqa: N802
        delta = event.angleDelta().y() or event.angleDelta().x()
        bar = self.scroll.horizontalScrollBar()
        bar.setValue(bar.value() - delta)
        event.accept()

    def _step(self, direction):
        bar = self.scroll.horizontalScrollBar()
        bar.setValue(bar.value() + direction * max(120, int(self.scroll.width() * 0.6)))

    def _update_arrows(self, *_args):
        bar = self.scroll.horizontalScrollBar()
        self.left.setVisible(bar.value() > bar.minimum())
        self.right.setVisible(bar.value() < bar.maximum())

    def resizeEvent(self, event):  # noqa: N802
        super().resizeEvent(event)
        QTimer.singleShot(0, self._update_arrows)


class CommandSearch(QLineEdit):
    """RustGIS "Command Search": find any native QGIS/plugin command by name.

    The command list is gathered from the native menus and toolbars only when
    the box gains focus (never in the background); a QCompleter pops up the
    matches and running one triggers the native QAction.
    """

    def __init__(self, window, parent=None):
        super().__init__(parent)
        self._window = window
        self._commands = {}
        self.setObjectName("QRibbonSkinSearch")
        self.setPlaceholderText(tr("Buscar comandos") + "   " + SEARCH_SHORTCUT)
        self.setClearButtonEnabled(True)
        self.setFixedHeight(24)
        self.setMinimumWidth(150)
        self.setMaximumWidth(260)
        self.addAction(theme_icon("/search.svg"), QLineEdit.ActionPosition.LeadingPosition)
        self._model = QStringListModel(self)
        completer = QCompleter(self._model, self)
        completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        completer.setFilterMode(Qt.MatchFlag.MatchContains)
        completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        completer.setMaxVisibleItems(14)
        completer.activated[str].connect(self._run)
        self.setCompleter(completer)
        self.returnPressed.connect(lambda: self._run(self.text()))

    def focusInEvent(self, event):  # noqa: N802
        self._collect()
        super().focusInEvent(event)

    def _collect(self):
        commands = {}

        def visit(actions, path):
            for action in actions:
                if action.isSeparator() or not action.isVisible():
                    continue
                caption = clean_caption(action.text())
                sub = action.menu()
                if sub is not None:
                    visit(sub.actions(), path + [caption] if caption else path)
                elif caption:
                    key = caption if not path else "%s  —  %s" % (caption, " › ".join(path))
                    commands.setdefault(key, action)

        menu_bar = self._window.menuBar()
        if menu_bar is not None:
            visit(menu_bar.actions(), [])
        for bar in self._window.findChildren(QToolBar):
            if bar.objectName() not in CORE_TOOLBARS:
                visit(bar.actions(), [bar.windowTitle()])
        self._commands = commands
        self._model.setStringList(sorted(commands, key=str.casefold))

    def _run(self, text):
        action = self._commands.get(text)
        if action is None and text:
            low = text.casefold()
            action = next((a for k, a in self._commands.items() if k.casefold().startswith(low)), None)
        if action is not None and action.isEnabled():
            self.clear()
            self.clearFocus()
            action.trigger()


class RibbonWidget(QWidget):
    """The main-window Ribbon. Constructor signature kept for plugin.py."""

    def __init__(self, iface, restore_action, focus_action, restore_panels_action, parent=None):
        super().__init__(parent)
        self.iface = iface
        self._window = iface.mainWindow()
        self._index = ActionIndex(self._window)
        self._own = {}
        self._pages = {}
        self._dirty = set()
        self._layer_kind = None
        self._collapsed = False
        self._peek = False
        self._project_chrome_callback = None
        for action in (restore_action, focus_action, restore_panels_action):
            action.setParent(self)
        restore_panels_action.triggered.connect(lambda _c=False: focus_action.setChecked(False))
        self._own[spec.CLASSIC] = restore_action
        self._own[spec.FOCUS_MAP] = focus_action
        self._own[spec.RESTORE_PANELS] = restore_panels_action
        self._make_plugin_actions()

        self.setObjectName("QRibbonSkinWidget")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setStyleSheet(stylesheet())
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        outer.addWidget(self._make_header())
        outer.addWidget(self._make_tab_strip())
        self.pages = QStackedWidget(self)
        self.pages.setObjectName("QRibbonSkinPages")
        self.pages.setFixedHeight(RIBBON_H)
        outer.addWidget(self.pages)
        self._divider = QFrame(self)
        self._divider.setFrameShape(QFrame.Shape.HLine)
        self._divider.setFrameShadow(QFrame.Shadow.Plain)
        pal = self._divider.palette()
        pal.setColor(QPalette.ColorRole.WindowText, pal.color(QPalette.ColorRole.Mid))
        self._divider.setPalette(pal)
        self._divider.setFixedHeight(1)
        outer.addWidget(self._divider)

        self._layer_kind = self._current_layer_kind()
        try:
            iface.currentLayerChanged.connect(self._on_layer_changed)
        except (AttributeError, RuntimeError, TypeError):
            pass
        self._keep_native_shortcuts()
        self._shortcuts = []
        for keys, slot in ((COLLAPSE_SHORTCUT, self.toggle_collapsed),
                           (SEARCH_SHORTCUT, self.focus_search)):
            # Parented to the Ribbon: Qt removes them together with it.
            shortcut = QShortcut(QKeySequence(keys), self)
            shortcut.setContext(Qt.ShortcutContext.WindowShortcut)
            shortcut.activated.connect(slot)
            shortcut.activatedAmbiguously.connect(slot)
            self._shortcuts.append(shortcut)
        self.tabs.setCurrentIndex(0)
        self._show_tab(0)
        self._update_height()

    # ----------------------------------------------------------- plugin actions
    def _make_plugin_actions(self):
        def add(name, slot, checkable=False):
            action = QAction(theme_icon(spec.COMMAND_ICONS.get(name)),
                             tr(spec.COMMAND_LABELS.get(name, name)).replace("\n", " "), self)
            action.setToolTip(tr(spec.COMMAND_TIPS.get(name, "")))
            action.setCheckable(checkable)
            action.triggered.connect(slot)
            self._own[name] = action

        add(spec.COMMAND_SEARCH, lambda _c=False: self.focus_search())
        add(spec.TOGGLE_RIBBON, lambda _c=False: self.toggle_collapsed())
        for name in spec.COMMAND_ICONS:
            if name.startswith(spec.ALG):
                alg = name[len(spec.ALG):]
                add(name, lambda _c=False, a=alg: self._run_algorithm(a))
        for name in (spec.CLASSIC, spec.FOCUS_MAP, spec.RESTORE_PANELS):
            action = self._own[name]
            if action.icon().isNull():
                action.setIcon(theme_icon(spec.COMMAND_ICONS[name]))

    def _run_algorithm(self, alg_id):
        """Open a native Processing algorithm dialog (no algorithm is ours)."""
        try:
            try:
                from qgis import processing
            except ImportError:
                import processing  # QGIS builds exposing the plugin module
            processing.execAlgorithmDialog(alg_id)
        except Exception as exc:  # Processing disabled or algorithm missing
            try:
                from qgis.core import Qgis
                self.iface.messageBar().pushMessage(
                    "QRibbonSkin", tr("Algoritmo indisponível: {alg}").format(alg=alg_id),
                    Qgis.MessageLevel.Warning, 5)
            except Exception:
                pass
            from qgis.core import QgsMessageLog, Qgis
            QgsMessageLog.logMessage(str(exc), "QRibbonSkin", Qgis.MessageLevel.Warning)

    def _resolve(self, name):
        """The QAction for a spec name, or None when this QGIS lacks it."""
        if name in self._own:
            return self._own[name]
        return self._index.action(name)

    # ------------------------------------------------------------------ chrome
    def _make_header(self):
        header = QWidget(self)
        header.setObjectName("QRibbonSkinHeader")
        header.setFixedHeight(HEADER_H)
        row = QHBoxLayout(header)
        row.setContentsMargins(8, 2, 10, 2)
        row.setSpacing(1)
        for name in spec.QUICK_ACCESS:
            action = self._resolve(name)
            if action is None:
                continue
            button = QToolButton(header)
            button.setDefaultAction(action)
            button.setAutoRaise(True)
            button.setIconSize(QSize(16, 16))
            button.setFixedSize(26, 24)
            button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
            if button.icon().isNull():
                button.setIcon(theme_icon("/mActionHistory.svg"))
            row.addWidget(button)
        row.addStretch(1)
        self.search = CommandSearch(self._window, header)
        row.addWidget(self.search)
        return header

    def _make_tab_strip(self):
        strip = QWidget(self)
        strip.setObjectName("QRibbonSkinTabStrip")
        strip.setFixedHeight(TAB_STRIP_H)
        row = QHBoxLayout(strip)
        row.setContentsMargins(8, 0, 8, 0)
        row.setSpacing(6)
        project = QToolButton(strip)
        project.setObjectName("QRibbonSkinProjectButton")
        project.setText(tr("Projeto"))
        project.setToolTip(tr("Abrir, salvar e criar projetos"))
        project.setFixedHeight(24)
        project.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        native_project = None
        try:
            native_project = self.iface.projectMenu()
        except (AttributeError, RuntimeError):
            native_project = self._index.menu("mProjectMenu")
        if native_project is not None:
            project.setMenu(native_project)
        row.addWidget(project, 0, Qt.AlignmentFlag.AlignVCenter)
        self.tabs = QTabBar(strip)
        self.tabs.setObjectName("QRibbonSkinTabs")
        self.tabs.setDrawBase(False)
        self.tabs.setExpanding(False)
        self.tabs.setUsesScrollButtons(True)
        self.tabs.setElideMode(Qt.TextElideMode.ElideNone)
        self.tabs.setDocumentMode(True)
        for tab_id, caption in spec.TABS:
            index = self.tabs.addTab(tr(caption))
            self.tabs.setTabData(index, tab_id)
        self.tabs.currentChanged.connect(self._show_tab)
        self.tabs.tabBarClicked.connect(self._on_tab_clicked)
        self.tabs.tabBarDoubleClicked.connect(lambda _i: self.toggle_collapsed())
        row.addWidget(self.tabs, 1, Qt.AlignmentFlag.AlignBottom)
        self.collapse_button = QToolButton(strip)
        self.collapse_button.setAutoRaise(True)
        self.collapse_button.setFixedSize(24, 24)
        self.collapse_button.clicked.connect(self.toggle_collapsed)
        row.addWidget(self.collapse_button, 0, Qt.AlignmentFlag.AlignVCenter)
        self._sync_collapse_button()
        return strip

    # ------------------------------------------------------------- tab pages
    def _tab_id(self, index):
        return self.tabs.tabData(index)

    def _show_tab(self, index):
        tab_id = self._tab_id(index)
        if tab_id is None:
            return
        page = self._pages.get(tab_id)
        if page is None or tab_id in self._dirty:
            page = self._build_page(tab_id, page)
        self.pages.setCurrentWidget(page)

    def _build_page(self, tab_id, old=None):
        page = RibbonPage(self.pages)
        groups = spec.visible_groups(tab_id, self._layer_kind)
        drawn = 0
        for grp in groups:
            widget = self._build_group(grp)
            if widget is not None:
                page.add_group(widget)
                drawn += 1
        if tab_id in spec.LAYER_DEPENDENT_TABS and self._layer_kind is None:
            page.row.insertWidget(0, self._hint_group(tab_id), 0, Qt.AlignmentFlag.AlignTop)
        page.row.addStretch(1)
        self.pages.addWidget(page)
        if old is not None:
            self.pages.removeWidget(old)
            old.deleteLater()
        self._pages[tab_id] = page
        self._dirty.discard(tab_id)
        return page

    def _hint_group(self, tab_id):
        texts = {
            "data": "Selecione uma camada no painel Camadas para ver suas ferramentas de dados.",
            "style": "Selecione uma camada no painel Camadas para definir seu estilo.",
            "labeling": "Selecione uma camada vetorial no painel Camadas para rotulá-la.",
        }
        grp = RibbonGroup(tr("Camada"))
        label = QLabel(tr(texts[tab_id]), grp)
        label.setObjectName("QRibbonSkinHint")
        label.setWordWrap(True)
        label.setFixedSize(230, CONTENT_H - 6)
        label.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
        pal = label.palette()
        pal.setColor(QPalette.ColorRole.WindowText,
                     _mix(pal.color(QPalette.ColorRole.WindowText),
                          pal.color(QPalette.ColorRole.Window), 0.62))
        label.setPalette(pal)
        grp.add(label)
        return grp

    def _build_group(self, grp):
        widget = RibbonGroup(tr(grp["title"]))
        for item in grp["items"]:
            control = self._build_item(item, widget)
            if control is not None:
                widget.add(control)
        if widget.count == 0:
            widget.deleteLater()
            return None
        return widget

    def _build_item(self, item, parent):
        kind = item["kind"]
        if kind == "col":
            column = QWidget(parent)
            layout = QVBoxLayout(column)
            layout.setContentsMargins(0, 1, 0, 0)
            layout.setSpacing(1)
            layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
            added = 0
            for sub in item["items"]:
                control = self._build_item(sub, column)
                if control is not None:
                    layout.addWidget(control)
                    added += 1
            if not added:
                column.deleteLater()
                return None
            return column
        if kind in ("menu", "small_menu"):
            menu = self._build_menu(item["entries"], parent)
            if menu is None:
                return None
            size = "small" if kind == "small_menu" else "big"
            caption = tr(item["label"] or "")
            if size == "small":
                caption = caption.replace("\n", " ")
            button = RibbonButton(size, caption, theme_icon(item["icon"]), None, parent)
            button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
            button.setMenu(menu)
            button.setToolTip(caption.replace("\n", " "))
            button.triggered.connect(self._end_peek)
            return button
        action = self._resolve(item["name"])
        if action is None:
            return None
        size = "small" if kind == "small" else "big"
        label = item.get("label") or spec.COMMAND_LABELS.get(item["name"])
        caption = tr(label) if label else clean_caption(action.text())
        if size == "small":
            caption = caption.replace("\n", " ")
        icon = item.get("icon") or spec.COMMAND_ICONS.get(item["name"])
        button = RibbonButton(size, caption, theme_icon(icon), action, parent)
        if kind == "split":
            menu = self._build_menu(item["entries"], parent)
            if menu is not None:
                button.setPopupMode(QToolButton.ToolButtonPopupMode.MenuButtonPopup)
                button.setMenu(menu)
        button.triggered.connect(self._end_peek)
        return button

    def _build_menu(self, entries, parent):
        """A native QMenu (single "menu:" entry) or a menu of native actions."""
        if len(entries) == 1 and entries[0] == spec.PLUGIN_TOOLBARS:
            menu = QMenu(parent)
            menu.aboutToShow.connect(lambda m=menu: self._fill_plugin_toolbars(m))
            return menu
        if len(entries) == 1 and entries[0].startswith("menu:"):
            return self._index.menu(entries[0][5:])
        menu = QMenu(parent)
        pending_separator = False
        for entry in entries:
            if entry == "-":
                pending_separator = bool(menu.actions())
                continue
            if entry.startswith("menu:"):
                native = self._index.menu(entry[5:])
                target = native.menuAction() if native is not None else None
            else:
                target = self._resolve(entry)
            if target is None:
                continue
            if pending_separator:
                menu.addSeparator()
                pending_separator = False
            menu.addAction(target)
        return menu if menu.actions() else None

    def _fill_plugin_toolbars(self, menu):
        """List the commands of third-party toolbars, read when opened."""
        menu.clear()
        for bar in self._window.findChildren(QToolBar):
            if bar.parent() is not self._window or bar.objectName() in CORE_TOOLBARS:
                continue
            actions = [a for a in bar.actions() if not a.isSeparator()
                       and (a.menu() is not None or clean_caption(a.text()))]
            if not actions:
                continue
            sub = menu.addMenu(bar.windowTitle() or bar.objectName())
            for action in actions:
                sub.addAction(action)
        if not menu.actions():
            empty = menu.addAction(tr("Nenhuma barra de complementos"))
            empty.setEnabled(False)

    # --------------------------------------------------------- layer context
    def _current_layer_kind(self):
        try:
            layer = self.iface.activeLayer()
        except (AttributeError, RuntimeError):
            return None
        return self._kind_of(layer)

    @staticmethod
    def _kind_of(layer):
        if layer is None:
            return None
        try:
            from qgis.core import QgsRasterLayer, QgsVectorLayer
        except ImportError:  # pragma: no cover
            return "other"
        if isinstance(layer, QgsVectorLayer):
            return "vector"
        if isinstance(layer, QgsRasterLayer):
            return "raster"
        return "other"

    def _on_layer_changed(self, layer):
        kind = self._kind_of(layer)
        if kind == self._layer_kind:
            return
        self._layer_kind = kind
        self._dirty.update(spec.LAYER_DEPENDENT_TABS)
        current = self._tab_id(self.tabs.currentIndex())
        if current in spec.LAYER_DEPENDENT_TABS:
            self._show_tab(self.tabs.currentIndex())

    # -------------------------------------------------------------- collapse
    def _on_tab_clicked(self, index):
        if self._collapsed:
            # RustGIS: on a collapsed ribbon a tab click shows it for one use.
            same = index == self.tabs.currentIndex() and self._peek
            self._peek = not same
            self._update_height()

    def toggle_collapsed(self):
        self._collapsed = not self._collapsed
        self._peek = False
        self._sync_collapse_button()
        self._update_height()

    def _sync_collapse_button(self):
        self.collapse_button.setIcon(self._chevron_icon(down=self._collapsed))
        title = tr("Expandir a Ribbon") if self._collapsed else tr("Recolher a Ribbon")
        self.collapse_button.setToolTip("%s (%s)" % (title, COLLAPSE_SHORTCUT))

    def _chevron_icon(self, down):
        """Chevron in the palette's text colour (legible on any QGIS theme)."""
        ratio = self.devicePixelRatioF()
        pixmap = QPixmap(int(16 * ratio), int(16 * ratio))
        pixmap.setDevicePixelRatio(ratio)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(QPen(self.palette().color(QPalette.ColorRole.ButtonText), 1.6,
                            Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap,
                            Qt.PenJoinStyle.RoundJoin))
        y0, y1 = (5.5, 10.5) if down else (10.5, 5.5)
        painter.drawPolyline([QPointF(3, y0), QPointF(8, y1), QPointF(13, y0)])
        painter.end()
        return QIcon(pixmap)

    def _update_height(self):
        show = not self._collapsed or self._peek
        self.pages.setVisible(show)
        self.setFixedHeight(HEADER_H + TAB_STRIP_H + (RIBBON_H if show else 0) + 1)

    def focus_search(self):
        self.search.setFocus(Qt.FocusReason.ShortcutFocusReason)
        self.search.selectAll()

    def _end_peek(self, *_args):
        if self._peek:
            self._peek = False
            self._update_height()

    # ---------------------------------------------------- native shortcuts
    def _keep_native_shortcuts(self):
        """Keep QGIS shortcuts working while the native menu bar is hidden.

        Qt ignores the shortcut of a QAction whose only widgets are hidden (a
        hidden QMenuBar, hidden toolbars). Registering the *same* QAction on
        this visible widget keeps Ctrl+S, F5, etc. alive. Nothing is changed
        on the QAction itself, and Qt drops the registration with this widget.
        """
        seen = set()

        def visit(actions):
            for action in actions:
                sub = action.menu()
                if sub is not None:
                    visit(sub.actions())
                    continue
                if id(action) in seen or action.shortcut().isEmpty():
                    continue
                seen.add(id(action))
                self.addAction(action)

        menu_bar = self._window.menuBar()
        if menu_bar is not None:
            visit(menu_bar.actions())
        for bar in self._window.findChildren(QToolBar):
            if bar.objectName() != "QRibbonSkinToolbar":
                visit(bar.actions())

    # ---------------------------------------------------- plugin.py contract
    def set_project_chrome_callback(self, callback):
        """Kept for plugin.py; the Project button now opens the native menu."""
        self._project_chrome_callback = callback

    def release_project_dashboard(self):
        """Kept for plugin.py; there is no custom backstage any more."""
        self.release()

    def release(self):
        """Disconnect from QGIS before the Ribbon is deleted."""
        try:
            self.iface.currentLayerChanged.disconnect(self._on_layer_changed)
        except (AttributeError, RuntimeError, TypeError):
            pass
        for shortcut in self._shortcuts:
            try:
                shortcut.setEnabled(False)
            except RuntimeError:
                pass
