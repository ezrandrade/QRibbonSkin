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

from qgis.PyQt.QtCore import Qt, QSize, QRect, QPointF, QTimer
from qgis.PyQt.QtGui import (QAction, QColor, QFont, QFontMetrics, QIcon, QKeySequence,
                             QPainter, QPainterPath, QPalette, QPen, QPixmap, QShortcut)
from qgis.PyQt.QtWidgets import (
    QDockWidget, QFrame, QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem,
    QMenu, QScrollArea, QSizePolicy, QStackedWidget, QStyle, QStyleOptionToolButton,
    QStylePainter, QTabBar, QToolBar, QToolButton, QVBoxLayout, QWidget,
)

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
))


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
        icon = QgsApplication.getThemeIcon(path)
        if icon is not None and not icon.isNull():
            return icon
    except Exception:  # pragma: no cover - outside QGIS
        pass
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
    """Alt+Q command palette centred over QGIS, in the style of macOS Spotlight.

    A frameless popup (closes on Esc or a click outside) with a large query
    field and the matching native commands (icon, name and menu path). Enter
    runs the selected QAction; nothing is executed by the plugin itself.
    """

    def __init__(self, window):
        super().__init__(window, Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)
        self._window = window
        self._commands = {}
        self._recent = []
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setObjectName("QRibbonSkinSpotlightWindow")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        panel = QFrame(self)
        panel.setObjectName("QRibbonSkinSpotlight")
        panel.setStyleSheet(
            "QFrame#QRibbonSkinSpotlight { background: palette(base); "
            "border: 1px solid palette(mid); border-radius: 12px; }"
            "QLineEdit#QRibbonSkinSpotlightQuery { background: transparent; border: 0; "
            "color: palette(text); padding: 4px 2px; }"
            "QListWidget#QRibbonSkinSpotlightList { background: transparent; border: 0; "
            "outline: 0; }"
            "QListWidget#QRibbonSkinSpotlightList::item { padding: 4px 6px; border-radius: 6px; }"
            "QListWidget#QRibbonSkinSpotlightList::item:selected { "
            "background: palette(highlight); color: palette(highlighted-text); }"
            "QLabel { background: transparent; }")
        outer.addWidget(panel)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(6)
        top = QHBoxLayout()
        top.setSpacing(8)
        icon = QLabel(panel)
        icon.setPixmap(theme_icon("/search.svg").pixmap(QSize(20, 20)))
        top.addWidget(icon)
        self.query = QLineEdit(panel)
        self.query.setObjectName("QRibbonSkinSpotlightQuery")
        self.query.setPlaceholderText(tr("Digite para buscar ferramentas"))
        font = self.query.font()
        font.setPointSizeF(font.pointSizeF() + 4 if font.pointSizeF() > 0 else 14)
        self.query.setFont(font)
        top.addWidget(self.query, 1)
        layout.addLayout(top)
        self.results = QListWidget(panel)
        self.results.setObjectName("QRibbonSkinSpotlightList")
        self.results.setIconSize(QSize(BIG_ICON, BIG_ICON))
        self.results.setUniformItemSizes(True)
        self.results.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        # Spotlight style: no scroll bar; wheel and arrow keys still scroll.
        self.results.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        layout.addWidget(self.results, 1)
        self.footer = QLabel(tr("Enter: executar  ·  Esc: fechar"), panel)
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

    def open(self, text=""):
        self._commands = collect_commands(self._window)
        win = self._window.frameGeometry()
        width = min(640, max(420, int(win.width() * 0.46)))
        row = QFontMetrics(self.results.font()).height() + 10
        height = 70 + row * 9 + QFontMetrics(self.footer.font()).height()
        self.setFixedSize(width, height)
        self.move(win.x() + (win.width() - width) // 2, win.y() + int(win.height() * 0.16))
        self.query.blockSignals(True)
        self.query.setText(text)
        self.query.blockSignals(False)
        self._populate(text)
        self.show()
        self.raise_()
        self.activateWindow()
        self.query.setFocus(Qt.FocusReason.PopupFocusReason)
        self.query.end(False)

    def _populate(self, text):
        self.results.clear()
        keys = rank_commands(self._commands, text) if text.strip() else \
            [k for k in self._recent if k in self._commands]
        for key in keys:
            action, caption, where = self._commands[key]
            label = caption if not where else "%s\n%s" % (caption, where)
            item = QListWidgetItem(action.icon(), label.split("\n")[0])
            if where:
                item.setToolTip(where)
                item.setText("%s   —   %s" % (caption, where))
            item.setData(Qt.ItemDataRole.UserRole, key)
            if not action.isEnabled():
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEnabled)
            self.results.addItem(item)
        if self.results.count():
            self.results.setCurrentRow(next(
                (i for i in range(self.results.count())
                 if self.results.item(i).flags() & Qt.ItemFlag.ItemIsEnabled), 0))
        if text.strip() and not keys:
            self.footer.setText(tr("Nenhum comando encontrado"))
        elif not text.strip():
            self.footer.setText(tr("Digite para buscar ferramentas") + "  ·  " +
                                tr("Enter: executar  ·  Esc: fechar"))
        else:
            self.footer.setText(tr("Enter: executar  ·  Esc: fechar"))

    def eventFilter(self, watched, event):  # noqa: N802
        if watched is self.query and event.type() == event.Type.KeyPress:
            key = event.key()
            if key == Qt.Key.Key_Escape:
                self.close()
                return True
            if key in (Qt.Key.Key_Down, Qt.Key.Key_Up, Qt.Key.Key_PageDown, Qt.Key.Key_PageUp):
                step = {Qt.Key.Key_Down: 1, Qt.Key.Key_Up: -1,
                        Qt.Key.Key_PageDown: 8, Qt.Key.Key_PageUp: -8}[key]
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
        # Let the popup close before a modal QGIS dialog opens.
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


class RibbonWidget(QWidget):
    """The main-window Ribbon. Constructor signature kept for plugin.py."""

    def __init__(self, iface, restore_action, focus_action, restore_panels_action, parent=None):
        super().__init__(parent)
        self.iface = iface
        self._window = iface.mainWindow()
        self._index = ActionIndex(self._window)
        self._m = Metrics(self.font())
        self._own = {}
        self._pages = {}
        self._dirty = set()
        self._layer_kind = None
        self._collapsed = False
        self._peek = False
        self._project_active = False
        self._claimed = set()
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

        self._layer_kind = self._current_layer_kind()
        self._sync_layer_actions()
        try:
            iface.currentLayerChanged.connect(self._on_layer_changed)
        except (AttributeError, RuntimeError, TypeError):
            pass
        self._keep_native_shortcuts()
        self._shortcuts = []
        for keys, slot in ((COLLAPSE_SHORTCUT, self.toggle_collapsed),
                           (SEARCH_SHORTCUT, self.open_spotlight)):
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

        add(spec.COMMAND_SEARCH, lambda _c=False: self.open_spotlight())
        add(spec.TOGGLE_RIBBON, lambda _c=False: self.toggle_collapsed())
        for page, (caption, icon, tip) in spec.PROPERTY_PAGES.items():
            action = QAction(theme_icon(icon), tr(caption).replace("\n", " "), self)
            action.setToolTip(tr(tip))
            action.triggered.connect(lambda _c=False, p=page: self._show_properties(p))
            self._own[spec.PROPS + page] = action
        for name in spec.COMMAND_ICONS:
            if name.startswith(spec.ALG):
                alg = name[len(spec.ALG):]
                add(name, lambda _c=False, a=alg: self._run_algorithm(a))
        for name in (spec.CLASSIC, spec.FOCUS_MAP, spec.RESTORE_PANELS):
            action = self._own[name]
            if action.icon().isNull():
                action.setIcon(theme_icon(spec.COMMAND_ICONS[name]))

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
            try:
                self.iface.messageBar().pushMessage(
                    "QRibbonSkin", tr("Algoritmo indisponível: {alg}").format(alg=alg_id),
                    Qgis.MessageLevel.Warning, 5)
            except Exception:
                pass
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
        header.setFixedHeight(self._m.header_h)
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

    def _make_tab_strip(self):
        strip = QWidget(self)
        strip.setObjectName("QRibbonSkinTabStrip")
        strip.setFixedHeight(self._m.tab_h)
        row = QHBoxLayout(strip)
        row.setContentsMargins(8, 0, 8, 0)
        row.setSpacing(6)
        # RustGIS's Project button: its commands open *in the Ribbon*.
        self.project_button = QToolButton(strip)
        self.project_button.setObjectName("QRibbonSkinProjectButton")
        self.project_button.setText(tr("Projeto"))
        self.project_button.setToolTip(tr("Abrir, salvar e criar projetos"))
        self.project_button.setCheckable(True)
        self.project_button.setFixedHeight(min(26, self._m.tab_h - 4))
        self.project_button.clicked.connect(self._on_project_clicked)
        row.addWidget(self.project_button, 0, Qt.AlignmentFlag.AlignVCenter)
        self.tabs = QTabBar(strip)
        self.tabs.setObjectName("QRibbonSkinTabs")
        self.tabs.setDrawBase(False)
        self.tabs.setExpanding(False)
        self.tabs.setUsesScrollButtons(True)
        self.tabs.setElideMode(Qt.TextElideMode.ElideNone)
        self.tabs.setDocumentMode(True)
        self.tabs.setProperty("projectActive", False)
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

    def _page(self, tab_id):
        page = self._pages.get(tab_id)
        if page is None or tab_id in self._dirty:
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
        self._project_active = active
        self.project_button.setChecked(active)
        self.tabs.setProperty("projectActive", active)
        self.tabs.style().unpolish(self.tabs)
        self.tabs.style().polish(self.tabs)
        self.tabs.update()
        if show:
            if active:
                self.pages.setCurrentWidget(self._page(spec.PROJECT_TAB))
            else:
                self.pages.setCurrentWidget(self._page(self._tab_id(self.tabs.currentIndex())))
        self._update_height()

    def _build_page(self, tab_id, old=None):
        page = RibbonPage(self.pages)
        groups = spec.visible_groups(tab_id, self._layer_kind)
        if tab_id in spec.GLOBAL_DEDUP_TABS:
            everywhere = [g for t in spec.GROUPS.values() for g in t]
            self._claimed = self._claimed_actions(everywhere)
        else:
            self._claimed = self._claimed_actions(groups)
        for grp in groups:
            widget = self._build_group(grp)
            if widget is not None:
                page.add_group(widget)
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
        grp = RibbonGroup(self._m, tr("Camada"))
        label = QLabel(tr(texts[tab_id]), grp)
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
                names = [item["name"]] if "name" in item else []
                entries = item.get("entries", ())
                if not (len(entries) == 1 and entries[0].startswith("menu:")):
                    names += [e for e in entries if e != "-" and not e.startswith("menu:")]
                for name in names:
                    action = self._resolve(name)
                    if action is not None:
                        claimed.add(action)
        return claimed

    def _deduplicated(self, native, parent):
        """Show ``native`` without the actions claimed by this tab, or the
        native QMenu itself when nothing overlaps. The proxy is refilled from
        the live native menu each time it opens (plugin entries included);
        actions and submenus are referenced, never copied."""
        claimed = frozenset(self._claimed)
        if not any(a in claimed for a in native.actions()):
            return native
        proxy = QMenu(native.title(), parent)

        def refill():
            proxy.clear()
            pending = False
            for action in native.actions():
                if action.isSeparator():
                    pending = bool(proxy.actions())
                    continue
                if action in claimed or not action.isVisible():
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
            button = RibbonButton(self._m, size, caption, theme_icon(item["icon"]), None, parent)
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
        if label is None and item["name"].startswith(spec.PROPS):
            label = spec.PROPERTY_PAGES[item["name"][len(spec.PROPS):]][0]
        caption = tr(label) if label else clean_caption(action.text())
        if size == "small":
            caption = caption.replace("\n", " ")
        icon = item.get("icon") or spec.COMMAND_ICONS.get(item["name"])
        button = RibbonButton(self._m, size, caption, theme_icon(icon), action, parent)
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
            native = self._index.menu(entries[0][5:])
            return None if native is None else self._deduplicated(native, parent)
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
        self._sync_layer_actions()
        self._dirty.update(spec.LAYER_DEPENDENT_TABS)
        current = self._tab_id(self.tabs.currentIndex())
        if not self._project_active and current in spec.LAYER_DEPENDENT_TABS:
            self.pages.setCurrentWidget(self._page(current))

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
        """Kept for plugin.py; the Project page now lives in the Ribbon."""
        self._project_chrome_callback = callback

    def release_project_dashboard(self):
        """Kept for plugin.py: disconnect before the Ribbon is deleted."""
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
        try:
            self.spotlight.close()
            self.spotlight.deleteLater()
        except RuntimeError:
            pass
