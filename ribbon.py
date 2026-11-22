"""RustGIS-style Ribbon for the QGIS main window, built from native QGIS objects.

Layout (top to bottom), as in RustGIS:

1. Header row      – Quick Access Toolbar (left) and command search (right).
2. Tab strip       – a "Projeto" button, the tabs and a collapse chevron.
3. Ribbon          – the active tab's labelled groups; arrow buttons scroll it
                     when the window is too narrow. The "Projeto" button shows
                     the native project commands here, in the Ribbon.

Every control reuses a QGIS-owned QAction or QMenu (see ribbon_spec.py), so
icons, translations, enabled/checked state and shortcuts stay native. Colours
come from the running QPalette, so the Ribbon follows the user's QGIS theme.

Sizes follow QGIS, not pixels: large icons are drawn at 24 px (the size the
QGIS theme icons are designed for), small ones at 16 px, bitmap icons are
never enlarged past their own size, and every height is derived from the
font metrics, so captions are never clipped at larger fonts or DPI scaling.

Performance rules: no timers, no application-wide event filter, no menu
rescans. Tab pages are built lazily on first view; the three layer-dependent
tabs (Data, Style, Labeling) are rebuilt only when the kind of the selected
layer changes. The command list for the Spotlight is read only when it opens.
"""

import unicodedata
from pathlib import Path

from qgis.PyQt.QtCore import Qt, QSize, QRect, QRectF, QPointF, QTimer
from qgis.PyQt.QtGui import (QColor, QFont, QFontMetrics, QIcon, QKeySequence,
                             QPainter, QPainterPath, QPalette, QPen, QPixmap)
from qgis.PyQt.QtWidgets import (
    QDockWidget, QFrame, QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem,
    QMenu, QScrollArea, QSizePolicy, QStackedWidget, QStyle, QStyleOptionToolButton,
    QStylePainter, QTabBar, QToolBar, QToolButton, QVBoxLayout, QWidget, QWidgetAction,
)

from .compat import QAction, QShortcut
from .i18n import tr
from . import ribbon_spec as spec

ICON_DIR = Path(__file__).resolve().parent / "resources" / "icons" / "qgis_style"

BIG_ICON = 24     # QGIS theme icons are drawn on a 24 px grid
SMALL_ICON = 16   # QGIS "small icons" toolbar size
SCROLL_BUTTON_W = 18
COLLAPSE_SHORTCUT = "Ctrl+F1"
SEARCH_SHORTCUT = "Alt+Q"
SPOTLIGHT_LIMIT = 40

# QGIS's own toolbars (qgisapp.ui); anything else belongs to a plugin.
CORE_TOOLBARS = frozenset((
    "mFileToolBar", "mLayerToolBar", "mDigitizeToolBar", "mAdvancedDigitizeToolBar",
    "mMapNavToolBar", "mAttributesToolBar", "mPluginToolBar", "mHelpToolBar",
    "mRasterToolBar", "mLabelToolBar", "mVectorToolBar", "mDatabaseToolBar",
    "mWebToolBar", "mSnappingToolBar", "mDataSourceManagerToolBar",
    "mShapeDigitizeToolBar", "mSelectionToolBar", "mMeshToolBar",
    "mAnnotationsToolBar", "mLayerTreeToolBar", "QRibbonSkinToolbar",
    "ProcessingAlgorithms",
))


def qt_key(obj):
    """Stable identity of a Qt object: its C++ address. id() is not stable
    for objects created in C++, whose Python wrappers PyQt may recreate."""
    try:
        from qgis.PyQt import sip
        return sip.unwrapinstance(obj)
    except Exception:  # pragma: no cover
        return id(obj)


def is_native_action(action):
    """True for QGIS's own commands (Processing algorithms included).

    QGIS names its actions mAction… (qgisapp.ui/.cpp) and Processing menu
    entries mProcessingUserMenu_<algorithm id> (qgsappprocessingutils.cpp);
    plugin actions created by Python code have other or empty names. A
    submenu is native when every command inside it is native.
    """
    sub = action.menu()
    if sub is None:
        name = action.objectName()
        return (name.startswith(("mAction", "mProcessing"))
                or name in spec.PROCESSING_PLUGIN_ACTIONS)
    leaves = [a for a in sub.actions() if not a.isSeparator()]
    return bool(leaves) and all(is_native_action(a) for a in leaves)


def clean_caption(text):
    """Native QAction text without mnemonics, ellipsis or shortcut suffix."""
    text = str(text or "").split("\t")[0]
    text = text.replace("&&", "\u0000").replace("&", "").replace("\u0000", "&")
    return text.replace("…", "").replace("...", "").strip()


def fold(text):
    """Case- and accent-insensitive form used for searching."""
    text = unicodedata.normalize("NFKD", str(text or "").casefold())
    return "".join(ch for ch in text if not unicodedata.combining(ch))


def theme_icon(path):
    """A QGIS theme icon ("/name.svg") or a QRibbonSkin one ("qrs:name.svg")."""
    if not path:
        return QIcon()
    if path.startswith("qrs:"):
        return QIcon(str(ICON_DIR / path[4:]))
    try:
        from qgis.core import QgsApplication
    except ImportError:  # pragma: no cover - outside QGIS
        return QIcon(":/images/themes/default" + path)
    icon = QgsApplication.getThemeIcon(path)
    if icon is not None and not icon.isNull():
        return icon
    return QIcon(":/images/themes/default" + path)


def icon_rect(icon, size, centre_x, top):
    """Where to paint ``icon``: ``size`` px, but never larger than a bitmap
    icon's own pixmaps (QIcon.actualSize never scales up), so PNG icons are
    not pixelated. Scalable SVG icons get the full ``size``."""
    actual = icon.actualSize(QSize(size, size))
    w = min(size, actual.width()) if actual.width() > 0 else size
    h = min(size, actual.height()) if actual.height() > 0 else size
    return QRect(int(centre_x - w / 2), int(top + (size - h) / 2), w, h)


def _mix(top, bottom, ratio):
    return QColor(round(top.red() * ratio + bottom.red() * (1 - ratio)),
                  round(top.green() * ratio + bottom.green() * (1 - ratio)),
                  round(top.blue() * ratio + bottom.blue() * (1 - ratio)))


class Metrics:
    """All Ribbon sizes, derived from the QGIS interface font."""

    def __init__(self, font):
        fm = QFontMetrics(font)
        self.font = QFont(font)
        self.line = fm.lineSpacing()
        self.label_font = QFont(font)
        if font.pointSizeF() > 0:
            self.label_font.setPointSizeF(max(7.0, font.pointSizeF() - 1.0))
        lfm = QFontMetrics(self.label_font)
        # Big button: margin, 24 px icon, gap, two caption lines, margin.
        self.big_top = 5
        self.big_text_top = self.big_top + BIG_ICON + 4
        self.big_h = max(64, self.big_text_top + 2 * self.line + 4)
        self.small_h = max(22, fm.height() + 6)
        self.content_h = max(self.big_h + 2, 3 * self.small_h + 4)
        self.label_h = lfm.height() + 4
        self.ribbon_h = self.content_h + self.label_h + 8
        self.tab_h = max(30, fm.height() + 14)
        self.header_h = max(30, fm.height() + 12)


def stylesheet(palette):
    """Style sheet scoped to QRibbonSkin objects; every colour is native."""
    highlight = palette.color(QPalette.ColorRole.Highlight)
    pressed = highlight.darker(125).name()
    hover = highlight.darker(112).name()
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
QTabBar#QRibbonSkinTabs[projectActive="true"]::tab:selected {
    background: transparent; border-color: transparent; font-weight: normal;
}
QToolButton#QRibbonSkinProjectButton {
    background: palette(highlight); color: palette(highlighted-text);
    border: 0; border-radius: 4px; padding: 2px 12px; font-weight: 600;
}
QToolButton#QRibbonSkinProjectButton:hover { background: %(hover)s; }
QToolButton#QRibbonSkinProjectButton:checked,
QToolButton#QRibbonSkinProjectButton:pressed { background: %(pressed)s; }
QLineEdit#QRibbonSkinSearch {
    background: palette(base); color: palette(text);
    border: 1px solid palette(mid); border-radius: 11px; padding: 1px 10px;
}
QLineEdit#QRibbonSkinSearch:hover { border: 1px solid palette(highlight); }
QLabel#QRibbonSkinGroupLabel, QLabel#QRibbonSkinHint { background: transparent; }
""" % {"hover": hover, "pressed": pressed}


class ActionIndex:
    """objectName → QAction/QMenu of the QGIS main window, read once."""

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
        if "|" in name:  # QGIS 4.x name | QGIS 3.44 name
            for alternative in name.split("|"):
                found = self.action(alternative)
                if found is not None:
                    return found
            return None
        found = self.actions.get(name)
        if found is None:
            found = self.window.findChild(QAction, name)
            if found is None:
                docks = spec.DOCK_FALLBACK.get(name, ())
                for dock_name in (docks,) if isinstance(docks, str) else docks:
                    dock = self.window.findChild(QDockWidget, dock_name)
                    if dock is not None:
                        found = dock.toggleViewAction()
                        break
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

    The QAction drives trigger, enabled, checked and tooltip natively through
    ``setDefaultAction``. The frame is drawn by the native QStyle (as QGIS
    toolbars are); only icon/caption placement is ours.
    """

    def __init__(self, metrics, size, caption, fallback_icon=None, action=None, parent=None):
        super().__init__(parent)
        self._m = metrics
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

    def _split(self):
        return self.popupMode() == QToolButton.ToolButtonPopupMode.MenuButtonPopup

    def _fit(self):
        metrics = QFontMetrics(self.font())
        caret = 9 if self._has_menu_arrow() else 0
        if self._size == "big":
            lines = self._caption.split("\n") if self._caption else [""]
            width = max(metrics.horizontalAdvance(line) for line in lines) + caret
            if self._split():
                width += 12
            self.setFixedSize(max(48, width + 14), self._m.big_h)
        else:
            text = metrics.horizontalAdvance(self._caption) + 8 if self._caption else 0
            extra = 12 if self.menu() is not None else 0
            self.setFixedSize(SMALL_ICON + 8 + text + extra, self._m.small_h)

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
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        enabled = self.isEnabled()
        mode = QIcon.Mode.Normal if enabled else QIcon.Mode.Disabled
        state = QIcon.State.On if self.isChecked() else QIcon.State.Off
        group = QPalette.ColorGroup.Normal if enabled else QPalette.ColorGroup.Disabled
        color = self.palette().color(group, QPalette.ColorRole.ButtonText)
        painter.setPen(color)
        metrics = QFontMetrics(self.font())
        body_w = self.width() - (12 if self._split() else 0)
        icon = self._icon()
        if self._size == "big":
            if not icon.isNull():
                rect = icon_rect(icon, BIG_ICON, body_w / 2, self._m.big_top)
                icon.paint(painter, rect, Qt.AlignmentFlag.AlignCenter, mode, state)
            lines = self._caption.split("\n") if self._caption else []
            y = self._m.big_text_top
            for index, line in enumerate(lines):
                last = index == len(lines) - 1
                width = metrics.horizontalAdvance(line)
                caret = 9 if (last and self._has_menu_arrow()) else 0
                x = int(body_w / 2 - (width + caret) / 2)
                painter.drawText(QRect(x, y, width + 2, metrics.height()),
                                 Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop, line)
                if caret:
                    self._caret(painter, QPointF(x + width + 5.5, y + metrics.ascent() * 0.6), color)
                y += self._m.line
        else:
            if not icon.isNull():
                rect = icon_rect(icon, SMALL_ICON, 4 + SMALL_ICON / 2,
                                 (self.height() - SMALL_ICON) / 2)
                icon.paint(painter, rect, Qt.AlignmentFlag.AlignCenter, mode, state)
            text_rect = QRect(SMALL_ICON + 8, 0, body_w - SMALL_ICON - 8, self.height())
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

    def __init__(self, metrics, title, parent=None):
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
        holder.setFixedHeight(metrics.content_h)
        holder.setLayout(self.row)
        outer.addWidget(holder)
        self.label = QLabel(title, self)
        self.label.setObjectName("QRibbonSkinGroupLabel")
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label.setFixedHeight(metrics.label_h)
        self.label.setFont(metrics.label_font)
        pal = self.label.palette()
        pal.setColor(QPalette.ColorRole.WindowText,
                     _mix(pal.color(QPalette.ColorRole.WindowText),
                          pal.color(QPalette.ColorRole.Window), 0.62))
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
                                 pal.color(QPalette.ColorRole.Base), 0.5), 1))
        x = self.width() - 4
        painter.drawLine(x, 6, x, self.height() - 4)
        painter.end()


class RibbonTabBar(QTabBar):
    """Tab bar whose tabs always fit their caption in the *selected* style.

    The style sheet shows the active tab semi-bold. Qt6 sizes tabs with the
    selected-state font, but Qt5 (QGIS 3.44) sizes them with the regular
    font, so the bold caption was clipped at both ends. Each tab is therefore
    sized from its semi-bold width plus the style sheet's horizontal padding.
    """

    PADDING = 13   # QTabBar#QRibbonSkinTabs::tab { padding: … 13px }
    SLACK = 6      # borders, margins and rounding

    def tabSizeHint(self, index):  # noqa: N802
        size = super().tabSizeHint(index)
        bold = QFont(self.font())
        bold.setWeight(QFont.Weight.DemiBold)
        need = (QFontMetrics(bold).horizontalAdvance(self.tabText(index))
                + 2 * self.PADDING + self.SLACK)
        if size.width() < need:
            size.setWidth(need)
        return size

    def minimumTabSizeHint(self, index):  # noqa: N802
        return self.tabSizeHint(index)  # never elide or squeeze a caption


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


def collect_commands(window):
    """{display key: (QAction, caption, path)} from native menus and the
    toolbars of plugins. Read only when the Spotlight opens."""
    commands = {}

    def visit(actions, path):
        for action in actions:
            if action.isSeparator() or not action.isVisible():
                continue
            caption = clean_caption(action.text())
            sub = action.menu()
            if sub is not None:
                # Toolbar toggles make no sense while the Ribbon replaces them.
                if sub.objectName() != "mToolbarMenu":
                    visit(sub.actions(), path + [caption] if caption else path)
            elif caption:
                where = " › ".join(path)
                key = caption + ("\u0001" + where if where else "")
                commands.setdefault(key, (action, caption, where))

    menu_bar = window.menuBar()
    if menu_bar is not None:
        visit(menu_bar.actions(), [])
    for bar in window.findChildren(QToolBar):
        if bar.objectName() not in CORE_TOOLBARS:
            visit(bar.actions(), [bar.windowTitle()])
    return commands


def rank_commands(commands, query, limit=SPOTLIGHT_LIMIT):
    """Commands whose caption/path contain every word of ``query``; caption
    prefix matches first, then word-start matches, then the rest."""
    words = fold(query).split()
    if not words:
        return []
    scored = []
    for key, (action, caption, where) in commands.items():
        cap = fold(caption)
        hay = cap + " " + fold(where)
        if not all(w in hay for w in words):
            continue
        if cap.startswith(words[0]):
            score = 0
        elif any(part.startswith(words[0]) for part in cap.split()):
            score = 1
        elif words[0] in cap:
            score = 2
        else:
            score = 3
        scored.append((score, len(caption), cap, key))
    scored.sort()
    return [key for *_rest, key in scored[:limit]]


class Spotlight(QWidget):
    """Alt+Q command palette over QGIS, in the style of macOS Spotlight.

    It is a *child overlay* of the QGIS main window, not a separate window:
    its position is computed in QGIS's own coordinates, so no window manager
    (Wayland, mixed-DPI Windows) can move it. The overlay covers the window
    transparently only to catch a click outside the panel, which closes it.

    The panel opens as the search field alone, centred on the QGIS window;
    results grow *downwards* while the field stays put (it must not jump while
    the user types). Enter runs the selected native QAction.
    """

    MAX_ROWS = 8
    RADIUS = 12
    SHADOW = 10

    def __init__(self, window):
        super().__init__(window)
        self._window = window
        self._commands = {}
        self._recent = []
        self._anchor_y = 0
        self.setObjectName("QRibbonSkinSpotlightOverlay")
        self.hide()
        self.panel = QWidget(self)
        self.panel.setObjectName("QRibbonSkinSpotlight")
        self.panel.setStyleSheet(
            "QLineEdit#QRibbonSkinSpotlightQuery { background: transparent; border: 0; "
            "color: palette(text); padding: 2px 2px; }"
            "QListWidget#QRibbonSkinSpotlightList { background: transparent; border: 0; "
            "outline: 0; }"
            "QListWidget#QRibbonSkinSpotlightList::item { padding: 4px 6px; border-radius: 6px; }"
            "QListWidget#QRibbonSkinSpotlightList::item:selected { "
            "background: palette(highlight); color: palette(highlighted-text); }"
            "QLabel { background: transparent; }")
        layout = QVBoxLayout(self.panel)
        layout.setContentsMargins(self.SHADOW + 14, self.SHADOW + 8,
                                  self.SHADOW + 14, self.SHADOW + 8)
        layout.setSpacing(4)
        top = QHBoxLayout()
        top.setSpacing(8)
        icon = QLabel(self.panel)
        icon.setPixmap(theme_icon("/search.svg").pixmap(QSize(20, 20)))
        top.addWidget(icon)
        self.query = QLineEdit(self.panel)
        self.query.setObjectName("QRibbonSkinSpotlightQuery")
        self.query.setPlaceholderText(tr("Digite para buscar ferramentas"))
        font = self.query.font()
        font.setPointSizeF(font.pointSizeF() + 4 if font.pointSizeF() > 0 else 14)
        self.query.setFont(font)
        top.addWidget(self.query, 1)
        layout.addLayout(top)
        self.separator = QFrame(self.panel)
        self.separator.setFixedHeight(1)
        self.separator.setAutoFillBackground(True)
        pal = self.separator.palette()
        pal.setColor(QPalette.ColorRole.Window,
                     _mix(pal.color(QPalette.ColorRole.Mid), pal.color(QPalette.ColorRole.Base), 0.5))
        self.separator.setPalette(pal)
        layout.addWidget(self.separator)
        self.results = QListWidget(self.panel)
        self.results.setObjectName("QRibbonSkinSpotlightList")
        self.results.setIconSize(QSize(BIG_ICON, BIG_ICON))
        self.results.setUniformItemSizes(True)
        self.results.setFrameShape(QFrame.Shape.NoFrame)
        self.results.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        # Spotlight style: no scroll bar; wheel and arrow keys still scroll.
        self.results.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        layout.addWidget(self.results)
        self.footer = QLabel(self.panel)
        pal = self.footer.palette()
        pal.setColor(QPalette.ColorRole.WindowText,
                     _mix(pal.color(QPalette.ColorRole.WindowText),
                          pal.color(QPalette.ColorRole.Base), 0.55))
        self.footer.setPalette(pal)
        layout.addWidget(self.footer)
        self.query.textChanged.connect(self._populate)
        self.query.installEventFilter(self)
        self.results.itemActivated.connect(self._run_item)
        self.results.itemClicked.connect(self._run_item)

    # ---------------------------------------------------------------- open
    def open(self, text=""):
        self._commands = collect_commands(self._window)
        self.setGeometry(self._window.rect())
        self.query.blockSignals(True)
        self.query.setText(text)
        self.query.blockSignals(False)
        self._window.installEventFilter(self)  # follow resizes while open only
        self.show()
        self.raise_()
        self._populate(text)
        # Field centred on the QGIS window; results then grow downwards.
        self._anchor_y = (self.height() - self._field_height()) // 2
        self._layout_panel()
        self.query.setFocus(Qt.FocusReason.PopupFocusReason)
        self.query.end(False)

    def close(self):  # noqa: D401 - keep QWidget semantics
        try:
            self._window.removeEventFilter(self)
        except RuntimeError:
            pass
        return super().close()

    def _field_height(self):
        margins = self.panel.layout().contentsMargins()
        return margins.top() + self.query.sizeHint().height() + margins.bottom()

    def _layout_panel(self):
        width = min(640, max(420, int(self.width() * 0.46)))
        rows = min(self.results.count(), self.MAX_ROWS)
        showing = rows > 0
        self.results.setVisible(showing)
        self.separator.setVisible(showing or bool(self.footer.text()))
        self.footer.setVisible(bool(self.footer.text()))
        height = self._field_height()
        spacing = self.panel.layout().spacing()
        if showing:
            row_h = self._row_height()
            self.results.setFixedHeight(rows * row_h + 4)
            height += spacing + 1 + spacing + rows * row_h + 4
        if self.footer.isVisible():
            if not showing:
                height += spacing + 1
            height += spacing + self.footer.sizeHint().height()
        y = self._anchor_y
        if y + height > self.height() - 8:          # keep it on screen
            y = max(8, self.height() - 8 - height)
        self.panel.setGeometry((self.width() - width) // 2, y, width, height)
        self.update()

    # --------------------------------------------------------------- paint
    def paintEvent(self, _event):  # noqa: N802
        """Rounded panel with a soft shadow, in palette colours."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = self.panel.geometry().adjusted(self.SHADOW, self.SHADOW,
                                              -self.SHADOW, -self.SHADOW)
        for i in range(self.SHADOW, 0, -2):
            shadow = QColor(0, 0, 0, max(2, 22 - 2 * i))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(shadow)
            painter.drawRoundedRect(rect.adjusted(-i, -i + 2, i, i + 2),
                                    self.RADIUS + i, self.RADIUS + i)
        pal = self.palette()
        painter.setBrush(pal.color(QPalette.ColorRole.Base))
        painter.setPen(QPen(pal.color(QPalette.ColorRole.Mid), 1))
        painter.drawRoundedRect(QRectF(rect).adjusted(0.5, 0.5, -0.5, -0.5),
                                self.RADIUS, self.RADIUS)
        painter.end()

    def mousePressEvent(self, event):  # noqa: N802
        # Only reached for clicks on the transparent overlay: outside the panel.
        self.close()
        event.accept()

    # ------------------------------------------------------------- results
    def _row_height(self):
        """One fixed row height (icon or not), so the panel grows evenly."""
        return max(BIG_ICON, QFontMetrics(self.results.font()).height()) + 10

    def _populate(self, text):
        self.results.clear()
        row_h = self._row_height()
        keys = rank_commands(self._commands, text) if text.strip() else \
            [k for k in self._recent if k in self._commands]
        for key in keys:
            action, caption, where = self._commands[key]
            item = QListWidgetItem(action.icon(), caption)
            if where:
                item.setToolTip(where)
                item.setText("%s   —   %s" % (caption, where))
            item.setData(Qt.ItemDataRole.UserRole, key)
            item.setSizeHint(QSize(0, row_h))
            if not action.isEnabled():
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEnabled)
            self.results.addItem(item)
        if self.results.count():
            self.results.setCurrentRow(next(
                (i for i in range(self.results.count())
                 if self.results.item(i).flags() & Qt.ItemFlag.ItemIsEnabled), 0))
        if text.strip() and not keys:
            self.footer.setText(tr("Nenhum comando encontrado"))
        elif keys:
            self.footer.setText(tr("Enter: executar  ·  Esc: fechar"))
        else:
            self.footer.setText("")
        if self.isVisible():
            self._layout_panel()

    def eventFilter(self, watched, event):  # noqa: N802
        if watched is self._window and event.type() == event.Type.Resize:
            self.setGeometry(self._window.rect())
            self._anchor_y = (self.height() - self._field_height()) // 2
            self._layout_panel()
            return False
        if watched is self.query and event.type() == event.Type.KeyPress:
            key = event.key()
            if key == Qt.Key.Key_Escape:
                self.close()
                return True
            if key in (Qt.Key.Key_Down, Qt.Key.Key_Up, Qt.Key.Key_PageDown, Qt.Key.Key_PageUp):
                step = {Qt.Key.Key_Down: 1, Qt.Key.Key_Up: -1,
                        Qt.Key.Key_PageDown: self.MAX_ROWS,
                        Qt.Key.Key_PageUp: -self.MAX_ROWS}[key]
                count = self.results.count()
                if count:
                    row = max(0, min(count - 1, self.results.currentRow() + step))
                    self.results.setCurrentRow(row)
                return True
            if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                self._run_item(self.results.currentItem())
                return True
        return super().eventFilter(watched, event)

    def _run_item(self, item):
        if item is None or not (item.flags() & Qt.ItemFlag.ItemIsEnabled):
            return
        key = item.data(Qt.ItemDataRole.UserRole)
        entry = self._commands.get(key)
        self.close()
        if entry is None:
            return
        if key in self._recent:
            self._recent.remove(key)
        self._recent.insert(0, key)
        del self._recent[12:]
        # Let the overlay close before a modal QGIS dialog opens.
        QTimer.singleShot(0, entry[0].trigger)


class SearchBox(QLineEdit):
    """RustGIS "Command Search" box: a click or typing opens the Spotlight."""

    def __init__(self, open_spotlight, parent=None):
        super().__init__(parent)
        self._open = open_spotlight
        self.setObjectName("QRibbonSkinSearch")
        self.setPlaceholderText(tr("Buscar comandos") + "   " + SEARCH_SHORTCUT)
        fm = QFontMetrics(self.font())
        self.setFixedHeight(max(24, fm.height() + 8))
        hint = fm.horizontalAdvance(self.placeholderText()) + 56
        self.setMinimumWidth(max(150, min(hint, 300)))
        self.setMaximumWidth(max(260, min(hint, 300)))
        self.setToolTip(tr("Buscar e executar qualquer comando do QGIS (Alt+Q)"))
        self.addAction(theme_icon("/search.svg"), QLineEdit.ActionPosition.LeadingPosition)
        self.textEdited.connect(self._hand_over)

    def mousePressEvent(self, event):  # noqa: N802
        event.accept()
        self._hand_over(self.text())

    def _hand_over(self, text):
        self.clear()
        self.clearFocus()
        self._open(text)


def _spec_value(spec_module, name, default):
    return getattr(spec_module, name, default)


class RibbonFrame(QWidget):
    """A RustGIS-style Ribbon for any QGIS QMainWindow, driven by a spec.

    The spec module provides TABS, GROUPS, QUICK_ACCESS and optionally
    PROJECT_TAB/PROJECT_BUTTON (the "Projeto"-style button whose commands open
    in the Ribbon), GLOBAL_DEDUP_TABS and COMMAND_LABELS/ICONS/TIPS. The main
    window and the Layout Designer, Georeferencer and Model Designer share
    this class, so they share the look, metrics, Spotlight and the rule that
    no command appears twice in one tab.

    Names in a spec are resolved against the hosting window:
    * an objectName of a QAction or QMenu of that window;
    * ``key:<StandardKey>`` for QGIS actions without objectName that carry a
      platform standard shortcut (Cut, Copy, Paste, Undo, Redo, …);
    * names registered in ``own`` (QRibbonSkin's interface commands).
    """

    def __init__(self, window, spec_module, own=None, parent=None):
        super().__init__(parent)
        self.spec = spec_module
        self._window = window
        self._index = ActionIndex(window)
        self._m = Metrics(self.font())
        self._own = dict(own or {})
        for action in self._own.values():
            if action.parent() is None:
                action.setParent(self)
        self._pages = {}
        self._dirty = set()
        self._collapsed = False
        self._peek = False
        self._project_active = False
        self._claimed = set()
        self._shortcuts = []
        self._make_own_actions()

        self.setObjectName("QRibbonSkinWidget")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setStyleSheet(stylesheet(self.palette()))
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        outer.addWidget(self._make_header())
        outer.addWidget(self._make_tab_strip())
        self.pages = QStackedWidget(self)
        self.pages.setObjectName("QRibbonSkinPages")
        self.pages.setFixedHeight(self._m.ribbon_h)
        outer.addWidget(self.pages)
        self.spotlight = Spotlight(self._window)

    def start(self):
        """Finish set-up once subclasses are initialised."""
        self._keep_native_shortcuts()
        for keys, slot in ((COLLAPSE_SHORTCUT, self.toggle_collapsed),
                           (SEARCH_SHORTCUT, self.open_spotlight)):
            # Parented to the Ribbon: Qt removes them together with it.
            shortcut = QShortcut(QKeySequence(keys), self)
            shortcut.setContext(Qt.ShortcutContext.WindowShortcut)
            shortcut.activated.connect(slot)
            shortcut.activatedAmbiguously.connect(slot)
            self._shortcuts.append(shortcut)
        if self.tabs.count():
            self.tabs.setCurrentIndex(0)
            self._show_tab(0)
        self._update_height()

    # ----------------------------------------------------------- own actions
    def _add_own(self, name, slot, checkable=False):
        labels = _spec_value(self.spec, "COMMAND_LABELS", {})
        icons = _spec_value(self.spec, "COMMAND_ICONS", {})
        tips = _spec_value(self.spec, "COMMAND_TIPS", {})
        action = QAction(theme_icon(icons.get(name)),
                         tr(labels.get(name, name)).replace("\n", " "), self)
        action.setToolTip(tr(tips.get(name, "")))
        action.setCheckable(checkable)
        action.triggered.connect(slot)
        self._own[name] = action
        return action

    def _make_own_actions(self):
        self._add_own(spec.COMMAND_SEARCH, lambda _c=False: self.open_spotlight())
        self._add_own(spec.TOGGLE_RIBBON, lambda _c=False: self.toggle_collapsed())

    def _resolve(self, name):
        """The QAction for a spec name, or None when this QGIS lacks it."""
        if name in self._own:
            return self._own[name]
        if name.startswith("key:"):
            return self._action_by_standard_key(name[4:])
        return self._index.action(name)

    def _action_by_standard_key(self, key_name):
        key = getattr(QKeySequence.StandardKey, key_name, None)
        if key is None:
            return None
        wanted = QKeySequence.keyBindings(key)
        if not wanted:
            return None
        for action in self._window.findChildren(QAction):
            if any(seq in wanted for seq in action.shortcuts()):
                return action
        return None

    # ------------------------------------------------------------------ chrome
    def _make_header(self):
        header = QWidget(self)
        header.setObjectName("QRibbonSkinHeader")
        header.setFixedHeight(self._m.header_h)
        row = QHBoxLayout(header)
        row.setContentsMargins(8, 2, 10, 2)
        row.setSpacing(1)
        for name in _spec_value(self.spec, "QUICK_ACCESS", ()):
            action = self._resolve(name)
            if action is None:
                continue
            button = QToolButton(header)
            button.setDefaultAction(action)
            button.setAutoRaise(True)
            button.setIconSize(QSize(SMALL_ICON, SMALL_ICON))
            button.setFixedSize(26, 24)
            button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
            if button.icon().isNull():
                button.setIcon(theme_icon("/mActionHistory.svg"))
            row.addWidget(button)
        row.addStretch(1)
        self.search = SearchBox(self.open_spotlight, header)
        row.addWidget(self.search)
        return header

    def _tab_available(self, tab):
        """A tab listed as (id, caption, "menu:<objectName>") exists only
        while that native menu exists (QGIS deletes, e.g., the Atlas menu in
        report designers)."""
        if len(tab) < 3 or not tab[2]:
            return True
        requirement = tab[2]
        if requirement.startswith("menu:"):
            return self._window.findChild(QMenu, requirement[5:]) is not None
        return self._resolve(requirement) is not None

    def _make_tab_strip(self):
        strip = QWidget(self)
        strip.setObjectName("QRibbonSkinTabStrip")
        strip.setFixedHeight(self._m.tab_h)
        row = QHBoxLayout(strip)
        row.setContentsMargins(8, 0, 8, 0)
        row.setSpacing(6)
        self.project_button = None
        button_spec = _spec_value(self.spec, "PROJECT_BUTTON", None)
        if button_spec is not None:
            # RustGIS's Project button: its commands open *in the Ribbon*.
            self.project_button = QToolButton(strip)
            self.project_button.setObjectName("QRibbonSkinProjectButton")
            self.project_button.setText(tr(button_spec[0]))
            self.project_button.setToolTip(tr(button_spec[1]))
            self.project_button.setCheckable(True)
            self.project_button.setFixedHeight(min(26, self._m.tab_h - 4))
            self.project_button.clicked.connect(self._on_project_clicked)
            row.addWidget(self.project_button, 0, Qt.AlignmentFlag.AlignVCenter)
        self.tabs = RibbonTabBar(strip)
        self.tabs.setObjectName("QRibbonSkinTabs")
        self.tabs.setDrawBase(False)
        self.tabs.setExpanding(False)
        self.tabs.setUsesScrollButtons(True)
        self.tabs.setElideMode(Qt.TextElideMode.ElideNone)
        self.tabs.setDocumentMode(True)
        self.tabs.setProperty("projectActive", False)
        for tab in self.spec.TABS:
            if not self._tab_available(tab):
                continue
            index = self.tabs.addTab(tr(tab[1]))
            self.tabs.setTabData(index, tab[0])
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

    def page_is_stale(self, tab_id):
        """Subclasses: True when a built page must be rebuilt on show."""
        return False

    def _page(self, tab_id):
        page = self._pages.get(tab_id)
        if page is None or tab_id in self._dirty or self.page_is_stale(tab_id):
            page = self._build_page(tab_id, page)
        return page

    def _show_tab(self, index):
        tab_id = self._tab_id(index)
        if tab_id is None:
            return
        if self._project_active:
            self._set_project_active(False, show=False)
        self.pages.setCurrentWidget(self._page(tab_id))

    def _on_project_clicked(self):
        active = not self._project_active
        if self._collapsed:
            self._peek = active
        self._set_project_active(active)

    def _set_project_active(self, active, show=True):
        if self.project_button is None:
            return
        self._project_active = active
        self.project_button.setChecked(active)
        self.tabs.setProperty("projectActive", active)
        self.tabs.style().unpolish(self.tabs)
        self.tabs.style().polish(self.tabs)
        self.tabs.update()
        if show:
            if active:
                self.pages.setCurrentWidget(self._page(self.spec.PROJECT_TAB))
            else:
                self.pages.setCurrentWidget(self._page(self._tab_id(self.tabs.currentIndex())))
        self._update_height()

    def visible_groups(self, tab_id):
        """Groups of a tab; subclasses filter them by context."""
        return [g for g in self.spec.GROUPS.get(tab_id, ()) if g.get("when") is None]

    def leading_groups(self, tab_id):
        """Extra widgets placed before a tab's groups (hints)."""
        return []

    def trailing_groups(self, tab_id):
        """Extra group widgets placed after a tab's groups (run-time content)."""
        return []

    def _build_page(self, tab_id, old=None):
        page = RibbonPage(self.pages)
        groups = self.visible_groups(tab_id)
        if tab_id in _spec_value(self.spec, "GLOBAL_DEDUP_TABS", ()):
            everywhere = [g for t in self.spec.GROUPS.values() for g in t]
            self._claimed = self._claimed_actions(everywhere)
        else:
            self._claimed = self._claimed_actions(groups)
        for widget in self.leading_groups(tab_id):
            page.add_group(widget)
        for grp in groups:
            widget = self._build_group(grp)
            if widget is not None:
                page.add_group(widget)
        for widget in self.trailing_groups(tab_id):
            page.add_group(widget)
        page.row.addStretch(1)
        self.pages.addWidget(page)
        if old is not None:
            self.pages.removeWidget(old)
            old.deleteLater()
        self._pages[tab_id] = page
        self._dirty.discard(tab_id)
        return page

    def hint_group(self, text):
        grp = RibbonGroup(self._m, tr("Camada"))
        label = QLabel(tr(text), grp)
        label.setObjectName("QRibbonSkinHint")
        label.setWordWrap(True)
        label.setFixedSize(230, self._m.content_h - 6)
        label.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
        pal = label.palette()
        pal.setColor(QPalette.ColorRole.WindowText,
                     _mix(pal.color(QPalette.ColorRole.WindowText),
                          pal.color(QPalette.ColorRole.Window), 0.62))
        label.setPalette(pal)
        grp.add(label)
        return grp

    def dynamic_actions(self, source):
        """Actions for a ``dynamic`` spec item (subclasses); [] by default."""
        return []

    def _claimed_actions(self, groups):
        """QActions that have their own control on this tab: buttons and
        entries of curated menus. Native dropdowns on the same tab omit them,
        so no command appears twice in one tab (RustGIS rule)."""
        claimed = set()
        for grp in groups:
            stack = list(grp["items"])
            while stack:
                item = stack.pop(0)
                if item["kind"] == "col":
                    stack[:0] = item["items"]
                    continue
                if item["kind"] == "dynamic":
                    claimed.update(a for a, _menu in self.dynamic_actions(item["source"])
                                   if a is not None)
                    continue
                names = [item["name"]] if "name" in item else []
                entries = item.get("entries", ())
                if not (len(entries) == 1 and entries[0].startswith(("menu:", "native:"))):
                    names += [e for e in entries if e != "-" and not e.startswith("menu:")]
                for name in names:
                    action = self._resolve(name)
                    if action is not None:
                        claimed.add(action)
        return claimed

    def _deduplicated(self, native, parent, native_only=False):
        """Show ``native`` without the actions claimed by this tab, or the
        native QMenu itself when nothing overlaps. The proxy is refilled from
        the live native menu each time it opens (plugin entries included);
        actions and submenus are referenced, never copied."""
        claimed = frozenset(self._claimed)

        def hidden(action):
            return action in claimed or (native_only and not is_native_action(action))

        if not any(hidden(a) for a in native.actions() if not a.isSeparator()):
            return native
        if native_only and not any(not hidden(a) for a in native.actions()
                                   if not a.isSeparator() and a.isVisible()):
            return None  # nothing of QGIS's own left: no empty button
        proxy = QMenu(native.title(), parent)

        def refill():
            proxy.clear()
            pending = False
            for action in native.actions():
                if action.isSeparator():
                    pending = bool(proxy.actions())
                    continue
                if hidden(action) or not action.isVisible():
                    continue
                if pending:
                    proxy.addSeparator()
                    pending = False
                proxy.addAction(action)
            if not proxy.actions():
                empty = proxy.addAction(tr("Nenhum comando adicional"))
                empty.setEnabled(False)

        proxy.aboutToShow.connect(refill)
        return proxy

    def _build_group(self, grp):
        widget = RibbonGroup(self._m, tr(grp["title"]))
        for item in grp["items"]:
            for control in self._build_controls(item, widget):
                widget.add(control)
        if widget.count == 0:
            widget.deleteLater()
            return None
        return widget

    def _build_controls(self, item, parent):
        """Controls for one spec item (a ``dynamic`` item may yield many)."""
        if item["kind"] != "dynamic":
            control = self._build_item(item, parent)
            return [control] if control is not None else []
        controls = []
        size = item.get("size", "big")
        for action, menu in self.dynamic_actions(item["source"]):
            if menu is not None:
                caption = self.dynamic_menu_caption(menu)
                button = RibbonButton(self._m, size, self._two_lines(caption) if size == "big"
                                      else caption, menu.icon(), None, parent)
                button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
                button.setMenu(menu)
                button.setToolTip(caption)
            else:
                caption = self.dynamic_caption(action)
                button = RibbonButton(self._m, size, self._two_lines(caption) if size == "big"
                                      else caption, None, action, parent)
            button.triggered.connect(self._end_peek)
            controls.append(button)
        return controls

    def dynamic_caption(self, action):
        return clean_caption(action.text())

    def dynamic_menu_caption(self, menu):
        return clean_caption(menu.title())

    @staticmethod
    def _two_lines(caption):
        """Break a long single-line caption into two balanced lines."""
        words = caption.split()
        if len(words) < 2 or len(caption) <= 10:
            return caption
        best = min(range(1, len(words)),
                   key=lambda i: abs(len(" ".join(words[:i])) - len(" ".join(words[i:]))))
        return " ".join(words[:best]) + "\n" + " ".join(words[best:])

    def _label_for(self, name):
        return _spec_value(self.spec, "COMMAND_LABELS", {}).get(name)

    def _icon_for(self, name):
        return _spec_value(self.spec, "COMMAND_ICONS", {}).get(name)

    def _build_item(self, item, parent):
        kind = item["kind"]
        if kind == "col":
            column = QWidget(parent)
            layout = QVBoxLayout(column)
            layout.setContentsMargins(0, 1, 0, 0)
            layout.setSpacing(1)
            layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
            built = []
            for sub in item["items"]:
                for control in self._build_controls(sub, column):
                    layout.addWidget(control)
                    built.append((sub, control))
            if not built:
                column.deleteLater()
                return None
            if len(built) == 1 and built[0][0]["kind"] in ("small", "small_menu"):
                # A small control alone in its column leaves an empty space
                # under it: show it as a big button instead (all windows, and
                # also when a QGIS build lacks the other commands of a column).
                column.setParent(None)  # leave the group's tree right away
                column.deleteLater()
                sub = dict(built[0][0])
                sub["kind"] = "big" if sub["kind"] == "small" else "menu"
                sub["wrap"] = True
                return self._build_item(sub, parent)
            return column
        if kind in ("menu", "small_menu"):
            menu = self._build_menu(item["entries"], parent)
            if menu is None:
                return None
            size = "small" if kind == "small_menu" else "big"
            caption = tr(item["label"] or "")
            if size == "small":
                caption = caption.replace("\n", " ")
            elif item.get("wrap"):
                caption = self._two_lines(caption)
            button = RibbonButton(self._m, size, caption, theme_icon(item["icon"]), None, parent)
            button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
            button.setMenu(menu)
            button.setToolTip(caption.replace("\n", " "))
            button.triggered.connect(self._end_peek)
            return button
        action = self._resolve(item["name"])
        if action is None or not action.isVisible():
            return None
        size = "small" if kind == "small" else "big"
        label = item.get("label") or self._label_for(item["name"])
        caption = tr(label) if label else clean_caption(action.text())
        if size == "small":
            caption = caption.replace("\n", " ")
        elif item.get("wrap"):
            # Promoted from a small control: translated first, then wrapped.
            caption = self._two_lines(caption.replace("\n", " "))
        icon = item.get("icon") or self._icon_for(item["name"])
        button = RibbonButton(self._m, size, caption, theme_icon(icon), action, parent)
        if kind == "split":
            menu = self._build_menu(item["entries"], parent)
            if menu is not None:
                button.setPopupMode(QToolButton.ToolButtonPopupMode.MenuButtonPopup)
                button.setMenu(menu)
        button.triggered.connect(self._end_peek)
        return button

    def special_menu(self, entry, parent):
        """Menus built by QRibbonSkin for a single special entry (subclasses)."""
        return None

    def _build_menu(self, entries, parent):
        """A native QMenu (single "menu:" entry) or a menu of native actions."""
        if len(entries) == 1:
            special = self.special_menu(entries[0], parent)
            if special is not None:
                return special
            if entries[0].startswith(("menu:", "native:")):
                prefix, _sep, name = entries[0].partition(":")
                native = self._index.menu(name)
                return None if native is None else \
                    self._deduplicated(native, parent, native_only=prefix == "native")
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
            if target is None or not target.isVisible():
                continue
            if pending_separator:
                menu.addSeparator()
                pending_separator = False
            menu.addAction(target)
        return menu if menu.actions() else None

    # -------------------------------------------------------------- collapse
    def _on_tab_clicked(self, index):
        if self._project_active and index == self.tabs.currentIndex():
            # currentChanged is not emitted for the current tab.
            self._set_project_active(False)
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
        self.setFixedHeight(self._m.header_h + self._m.tab_h + (self._m.ribbon_h if show else 0))

    def _end_peek(self, *_args):
        if self._peek:
            self._peek = False
            if self._project_active:
                self._set_project_active(False)
            self._update_height()

    def open_spotlight(self, text=""):
        self.spotlight.open(text if isinstance(text, str) else "")

    # Backwards-compatible name used by older callers.
    focus_search = open_spotlight

    # ---------------------------------------------------- native shortcuts
    def _keep_native_shortcuts(self):
        """Keep QGIS shortcuts working while the native menu bar is hidden.

        Qt ignores the shortcut of a QAction whose only widgets are hidden (a
        hidden QMenuBar, hidden toolbars). Registering the *same* QAction on
        this visible widget keeps Ctrl+S, F6, etc. alive. Nothing is changed
        on the QAction itself, and Qt drops the registration with this widget.
        """
        seen = set()

        def visit(actions):
            for action in actions:
                sub = action.menu()
                if sub is not None:
                    visit(sub.actions())
                    continue
                if qt_key(action) in seen or action.shortcut().isEmpty():
                    continue
                seen.add(qt_key(action))
                self.addAction(action)

        menu_bar = self._window.menuBar()
        if menu_bar is not None:
            visit(menu_bar.actions())
        for bar in self._window.findChildren(QToolBar):
            if not bar.objectName().startswith("QRibbonSkin"):
                visit(bar.actions())

    def release(self):
        """Disconnect before the Ribbon is deleted."""
        for shortcut in self._shortcuts:
            try:
                shortcut.setEnabled(False)
            except RuntimeError:
                pass
        try:
            self.spotlight.close()
            self.spotlight.deleteLater()
        except RuntimeError:
            pass


class RibbonWidget(RibbonFrame):
    """The QGIS main-window Ribbon. Constructor signature kept for plugin.py."""

    def __init__(self, iface, restore_action, focus_action, restore_panels_action, parent=None):
        self.iface = iface
        self._layer_kind = None
        self._project_chrome_callback = None
        restore_panels_action.triggered.connect(lambda _c=False: focus_action.setChecked(False))
        own = {spec.CLASSIC: restore_action, spec.FOCUS_MAP: focus_action,
               spec.RESTORE_PANELS: restore_panels_action}
        super().__init__(iface.mainWindow(), spec, own, parent)
        for action in (restore_action, focus_action, restore_panels_action):
            action.setParent(self)
        self._layer_kind = self._current_layer_kind()
        self._sync_layer_actions()
        try:
            iface.currentLayerChanged.connect(self._on_layer_changed)
        except (AttributeError, RuntimeError, TypeError):
            pass
        self.start()

    # ----------------------------------------------------------- own actions
    def _make_own_actions(self):
        super()._make_own_actions()
        for page, (caption, icon, tip) in spec.PROPERTY_PAGES.items():
            action = QAction(theme_icon(icon), tr(caption).replace("\n", " "), self)
            action.setToolTip(tr(tip))
            action.triggered.connect(lambda _c=False, p=page: self._show_properties(p))
            self._own[spec.PROPS + page] = action
        for name in spec.COMMAND_ICONS:
            if name.startswith(spec.ALG):
                alg = name[len(spec.ALG):]
                self._add_own(name, lambda _c=False, a=alg: self._run_algorithm(a))
        for name in (spec.CLASSIC, spec.FOCUS_MAP, spec.RESTORE_PANELS):
            action = self._own[name]
            if action.icon().isNull():
                action.setIcon(theme_icon(spec.COMMAND_ICONS[name]))

    def _label_for(self, name):
        label = super()._label_for(name)
        if label is None and name.startswith(spec.PROPS):
            label = spec.PROPERTY_PAGES[name[len(spec.PROPS):]][0]
        return label

    def _show_properties(self, page):
        """Native Layer Properties dialog, opened on ``page``."""
        layer = self.iface.activeLayer()
        if layer is not None:
            self.iface.showLayerProperties(layer, page)

    def _sync_layer_actions(self):
        has_layer = self._layer_kind is not None
        for page in spec.PROPERTY_PAGES:
            self._own[spec.PROPS + page].setEnabled(has_layer)

    def _run_algorithm(self, alg_id):
        """Open a native Processing algorithm dialog (no algorithm is ours)."""
        try:
            try:
                from qgis import processing
            except ImportError:
                import processing  # QGIS builds exposing the plugin module
            processing.execAlgorithmDialog(alg_id)
        except Exception as exc:  # Processing disabled or algorithm missing
            from qgis.core import QgsMessageLog, Qgis
            message_bar = getattr(self.iface, "messageBar", None)
            if callable(message_bar) and message_bar() is not None:
                message_bar().pushMessage(
                    "QRibbonSkin", tr("Algoritmo indisponível: {alg}").format(alg=alg_id),
                    Qgis.MessageLevel.Warning, 5)
            QgsMessageLog.logMessage(str(exc), "QRibbonSkin", Qgis.MessageLevel.Warning)

    # ------------------------------------------------------------ context
    def visible_groups(self, tab_id):
        return spec.visible_groups(tab_id, self._layer_kind)

    def leading_groups(self, tab_id):
        texts = {
            "data": "Selecione uma camada no painel Camadas para ver suas ferramentas de dados.",
            "style": "Selecione uma camada no painel Camadas para definir seu estilo.",
            "labeling": "Selecione uma camada vetorial no painel Camadas para rotulá-la.",
        }
        if tab_id in spec.LAYER_DEPENDENT_TABS and self._layer_kind is None:
            return [self.hint_group(texts[tab_id])]
        return []

    # ------------------------------------------------------------ plugins

    def _plugin_fingerprint(self):
        """Cheap identity of everything plugins added (menus and toolbars)."""
        ids = []
        for name in spec.PLUGIN_SOURCE_MENUS:
            native = self._index.menu(name)
            if native is not None:
                ids.extend(qt_key(a) for a in native.actions())
        menu_bar = self._window.menuBar()
        if menu_bar is not None:
            ids.extend(qt_key(a) for a in menu_bar.actions())
        for bar in self._window.findChildren(QToolBar):
            if bar.parent() is self._window and not bar.objectName().startswith("QRibbonSkin"):
                ids.append(qt_key(bar))
                ids.extend(qt_key(a) for a in bar.actions())
        return tuple(ids)

    def page_is_stale(self, tab_id):
        # A plugin installed, enabled or removed since the tab was built.
        return (tab_id == "plugins" and tab_id in self._pages
                and getattr(self, "_plugin_print", None) != self._plugin_fingerprint())

    def collect_plugins(self):
        """Group the commands plugins added to QGIS, one group per plugin.

        QGIS gives each plugin its own submenu in the Plugins, Vector, Raster,
        Database, Web, Mesh and Processing menus (addPluginTo…Menu); a plugin
        may also add a top-level menu or its own toolbar. QGIS's own entries
        (mAction…, Processing's mProcessingUserMenu_…) are left out. The same
        QAction found in a menu and in a toolbar is shown once.
        Returns [{"title", "actions": [QAction], "toolbar": QToolBar|None}].
        """
        groups, order, seen = {}, [], set()

        def group(title):
            key = fold(clean_caption(title))
            if key not in groups:
                groups[key] = {"title": clean_caption(title), "actions": [], "toolbar": None}
                order.append(key)
            return groups[key]

        def take(target, actions):
            for action in actions:
                if (action.isSeparator() or not action.isVisible() or qt_key(action) in seen
                        or isinstance(action, QWidgetAction) or is_native_action(action)
                        or not (clean_caption(action.text()) or action.menu() is not None)):
                    continue
                seen.add(qt_key(action))
                target["actions"].append(action)

        others = tr("Outros complementos")
        for name in spec.PLUGIN_SOURCE_MENUS:
            native = self._index.menu(name)
            if native is None:
                continue
            for entry in native.actions():
                if entry.isSeparator() or is_native_action(entry):
                    continue
                sub = entry.menu()
                if sub is not None:
                    take(group(sub.title() or entry.text()), sub.actions())
                else:
                    take(group(others), [entry])
        menu_bar = self._window.menuBar()
        if menu_bar is not None:
            for entry in menu_bar.actions():
                sub = entry.menu()
                if (sub is not None and sub.objectName() not in spec.NATIVE_TOP_MENUS
                        and not is_native_action(entry)):
                    take(group(sub.title() or entry.text()), sub.actions())
        for bar in self._window.findChildren(QToolBar):
            if bar.parent() is not self._window:
                continue
            name = bar.objectName()
            if name.startswith("QRibbonSkin") or name == "ProcessingAlgorithms":
                continue
            actions = list(bar.actions())
            if name in CORE_TOOLBARS:
                take(group(others), actions)  # addToolBarIcon & co.
                continue
            # A plugin toolbar joins the group of the menu entries it repeats.
            keys = {qt_key(a) for a in actions}
            owner = next((groups[k] for k in order
                          if any(qt_key(a) in keys for a in groups[k]["actions"])), None)
            target = owner or group(bar.windowTitle() or name)
            take(target, actions)
            if any(isinstance(a, QWidgetAction) for a in actions):
                target["toolbar"] = bar  # controls that only work on the bar
        result = [groups[k] for k in order if groups[k]["actions"] or groups[k]["toolbar"]]
        result.sort(key=lambda g: (g["title"] == others, fold(g["title"])))
        return result

    @staticmethod
    def _plugin_icon(entry):
        """The plugin's own icon: its first command (or submenu) with one."""
        for action in entry["actions"]:
            for icon in (action.icon(), action.menu().icon() if action.menu() else QIcon()):
                if not icon.isNull():
                    return icon
        return theme_icon("/propertyicons/plugins.svg")

    def _plugin_control(self, entry, parent):
        """One button per plugin (saves Ribbon width):
        * a single command: the button runs it directly (no one-item menu);
        * otherwise: a dropdown with the plugin's commands and submenus, and,
          for a bar with controls that only work on it, "Show toolbar".
        Commands are the plugin's own QActions, referenced, never copied."""
        caption = self._two_lines(entry["title"])
        icon = self._plugin_icon(entry)
        actions = list(entry["actions"])
        bar = entry["toolbar"]
        if len(actions) == 1 and bar is None and actions[0].menu() is None:
            button = RibbonButton(self._m, "big", caption, icon, actions[0], parent)
            button.setToolTip("%s — %s" % (entry["title"], clean_caption(actions[0].text())))
        else:
            button = RibbonButton(self._m, "big", caption, icon, None, parent)
            if len(actions) == 1 and bar is None:
                menu = actions[0].menu()  # the plugin is a single submenu
            else:
                menu = QMenu(button)
                for action in actions:
                    menu.addAction(action)
                if bar is not None:
                    if menu.actions():
                        menu.addSeparator()
                    show_bar = menu.addAction(theme_icon("/mActionInterfaceCustomization.svg"),
                                              tr("Mostrar barra de ferramentas"))
                    show_bar.setCheckable(True)
                    show_bar.toggled.connect(lambda on, b=bar: b.setVisible(on))
                    menu.aboutToShow.connect(
                        lambda a=show_bar, b=bar: self._sync_check(a, b.isVisible()))
            button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
            button.setMenu(menu)
            button.setToolTip(entry["title"])
        button.triggered.connect(self._end_peek)
        return button

    @staticmethod
    def _sync_check(action, checked):
        action.blockSignals(True)
        action.setChecked(checked)
        action.blockSignals(False)

    def trailing_groups(self, tab_id):
        if tab_id != "plugins":
            return []
        self._plugin_print = self._plugin_fingerprint()
        entries = self.collect_plugins()
        if not entries:
            hint = self.hint_group("Nenhum complemento com comandos está instalado ou ativo. "
                                   "Use Gerenciar complementos.")
            hint.label.setText(tr("Complementos instalados"))
            return [hint]
        # All plugins in one group: a separate group per one-button plugin
        # would only repeat its name and add dividers.
        grp = RibbonGroup(self._m, tr("Complementos instalados"))
        for entry in entries:
            grp.add(self._plugin_control(entry, grp))
        return [grp]

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
        self._sync_layer_actions()
        self._dirty.update(spec.LAYER_DEPENDENT_TABS)
        current = self._tab_id(self.tabs.currentIndex())
        if not self._project_active and current in spec.LAYER_DEPENDENT_TABS:
            self.pages.setCurrentWidget(self._page(current))

    # ---------------------------------------------------- plugin.py contract
    def set_project_chrome_callback(self, callback):
        """Kept for plugin.py; the Project page now lives in the Ribbon."""
        self._project_chrome_callback = callback

    def release_project_dashboard(self):
        """Kept for plugin.py: disconnect before the Ribbon is deleted."""
        self.release()

    def release(self):
        try:
            self.iface.currentLayerChanged.disconnect(self._on_layer_changed)
        except (AttributeError, RuntimeError, TypeError):
            pass
        super().release()
