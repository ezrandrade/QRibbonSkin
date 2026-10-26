"""Optional Ribbon for QGIS's *native* Georeferencer, v0.9.18.

No GCP, transformer, processing or project code is replaced. We only create
QToolButtons displaying existing QActions. The editor remains a separate Qt
window. Original menus are hidden with a reversible switch. Toolbar buttons already
represented in the Ribbon are temporarily detached from their native bars;
Qt widget controls that cannot be mirrored stay in place. The native
SnappingTypeButton is mirrored in the Ribbon without moving its underlying
QWidgetAction or altering snapping settings. Original submenus
remain reachable via Interface > Menus originais; QWidgetAction controls
stay native. No whole-window Qt state serialization or global
application styles are used. All modifications are reversible.
"""

from qgis.PyQt import sip
from qgis.PyQt.QtCore import QObject, Qt, QEvent, QTimer, QSize
from qgis.PyQt.QtGui import QAction, QFontMetrics
from qgis.PyQt.QtWidgets import (
    QApplication, QMainWindow, QWidget, QWidgetAction, QToolBar, QToolButton,
    QTabWidget, QScrollArea, QFrame, QLabel, QHBoxLayout, QVBoxLayout,
    QSizePolicy, QMenu, QDockWidget,
)

from .i18n import tr
from .georeferencer_model import (
    TABS, GROUP_ORDER, is_georeferencer_class, route_action
)
from .icon_mapping import display_icon

BAR_NAME = 'QRibbonSkinGeoreferencerToolbar'


def _alive(obj):
    if obj is None:
        return False
    try:
        return not sip.isdeleted(obj)
    except (RuntimeError, TypeError):
        return False


def _caption(action):
    for candidate in (action.text(), action.toolTip(), action.objectName()):
        name = str(candidate or '').replace('&', '').strip()
        if name:
            return name
    return ''


def _action_button(action, parent, prominent=False):
    button = QToolButton(parent)
    button.setAutoRaise(True)
    button.setDefaultAction(action)  # executes original QGIS QAction
    caption = _caption(action)
    button.setToolTip(action.toolTip() or caption)
    button.setIcon(display_icon(action.icon(), caption))
    metrics = QFontMetrics(button.font())
    if prominent:
        button.setObjectName('QRibbonGeorefPrimary')
        button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        button.setIconSize(QSize(26, 26))
        button.setFixedSize(106, 88)
    else:
        button.setObjectName('QRibbonGeorefSecondary')
        button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        button.setIconSize(QSize(17, 17))
        button.setFixedHeight(29)
        button.setFixedWidth(min(300, max(108, metrics.horizontalAdvance(caption) + 42)))
    # QToolButton uses the same QAction but this caption belongs to the view.
    # Do not mutate QAction.text(), shortcut or checked state.
    if action.menu() is not None:
        button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
    return button


def _make_snapping_proxy(source, parent):
    """Mirror QGIS' native snapping control without moving its QWidgetAction.

    QgsGeoreferencerMainWindow constructs ``SnappingTypeButton`` with two
    independent interactions: ``clicked(bool)`` enables/disables snapping and
    ``triggered(QAction*)`` selects the snapping type. Both must be forwarded
    to the ORIGINAL QToolButton to preserve the C++ georeferencer callbacks.
    The original button and menu remain owned by QGIS.
    """
    if (not _alive(source) or not isinstance(source, QToolButton)
            or source.objectName() != 'SnappingTypeButton'):
        return None
    native_menu = source.menu()
    if not _alive(native_menu):
        return None
    proxy = QToolButton(parent)
    proxy.setObjectName('QRibbonSnappingProxy')
    proxy.setAutoRaise(True)
    proxy.setText(tr('Aderência'))
    proxy.setToolTip(source.toolTip() or tr('Ativar aderência e escolher o tipo'))
    proxy.setIcon(source.icon())
    proxy.setIconSize(QSize(17, 17))
    proxy.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
    proxy.setCheckable(source.isCheckable())
    proxy.setChecked(source.isChecked())
    proxy.setEnabled(source.isEnabled())
    proxy.setFixedSize(145, 31)
    # Reuse the QGIS-owned menu, preserving checked actions and snapping types.
    proxy.setMenu(native_menu)
    proxy.setPopupMode(QToolButton.ToolButtonPopupMode.MenuButtonPopup)

    def forward_click(_checked=False):
        if _alive(source) and source.isEnabled():
            source.click()  # fires original C++ clicked(bool) handler

    def forward_menu_action(action):
        if _alive(source):
            source.triggered.emit(action)  # fires original C++ triggered handler

    proxy.clicked.connect(forward_click)
    proxy.triggered.connect(forward_menu_action)
    source.toggled.connect(proxy.setChecked)
    return proxy


class _CommandGroup(QFrame):
    def __init__(self, caption, actions, parent):
        super().__init__(parent)
        self.setObjectName('QRibbonGeorefGroup')
        root = QVBoxLayout(self)
        root.setContentsMargins(7, 4, 7, 3)
        root.setSpacing(1)
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(4)
        root.addLayout(row, 1)
        offset = 0
        if len(actions) >= 4 and len(_caption(actions[0])) <= 23:
            row.addWidget(_action_button(actions[0], self, prominent=True))
            offset = 1
        for at in range(offset, len(actions), 3):
            col = QVBoxLayout()
            col.setContentsMargins(0, 1, 0, 1)
            col.setSpacing(1)
            col.setAlignment(Qt.AlignmentFlag.AlignVCenter)
            buttons = [_action_button(a, self) for a in actions[at:at + 3]]
            width = max(b.width() for b in buttons)
            for button in buttons:
                button.setFixedWidth(width)
                col.addWidget(button)
            row.addLayout(col)
        title = QLabel(tr(caption), self)
        title.setObjectName('QRibbonGeorefGroupLabel')
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(title)


class GeoreferencerRibbon(QWidget):
    """Compact per-window Ribbon, no ownership of original QAction objects."""

    QSS = '''
    QWidget#QRibbonGeorefWidget { background: #f7f9fc; color: #24374f; }
    QTabWidget#QRibbonGeorefTabs::pane { border: 0; background: #f7f9fc; }
    QTabWidget#QRibbonGeorefTabs QTabBar::tab { background: #f1f4f8;
        padding: 5px 13px; border: 0; color: #354961; }
    QTabWidget#QRibbonGeorefTabs QTabBar::tab:selected { background: #ffffff;
        color: #1b5db5; border-bottom: 2px solid #3469d5; }
    QWidget#QRibbonGeorefPage { background: #f7f9fc; }
    QToolButton#QRibbonGeorefPrimary, QToolButton#QRibbonGeorefSecondary {
        border: 1px solid transparent; border-radius: 3px; padding: 2px;
        color: #23364b; background: transparent; }
    QToolButton#QRibbonGeorefPrimary:hover, QToolButton#QRibbonGeorefSecondary:hover {
        background: #eaf1ff; border-color: #cfdaee; }
    QLabel#QRibbonGeorefGroupLabel { color: #667994; font-size: 10px; }
    QFrame#QRibbonGeorefDivider { background: #d7e0eb; border: 0; }
    '''

    def __init__(self, window, on_toggle, parent=None):
        super().__init__(parent)
        self.window = window
        self.setObjectName('QRibbonGeorefWidget')
        self.setMinimumWidth(0)
        self.setFixedHeight(149)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setStyleSheet(self.QSS)
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        tabs = QTabWidget(self)
        tabs.setObjectName('QRibbonGeorefTabs')
        tabs.setDocumentMode(True)
        tabs.setUsesScrollButtons(True)
        root.addWidget(tabs)
        self.tabs = tabs
        self.rows = {}
        self.scrolls = {}
        self._seen = set()
        self._planned = {}
        # QWidgetActions are not regular QActions: track only confirmed
        # mirrors, so unsupported Qt controls remain in native toolbars.
        self._mirrored_widget_actions = set()
        self.incomplete_bars = set()
        self._chrome_actions = self._get_chrome_actions()
        for name in TABS:
            page = QWidget(tabs)
            page.setObjectName('QRibbonGeorefPage')
            layout = QHBoxLayout(page)
            layout.setContentsMargins(1, 0, 1, 0)
            layout.setSpacing(0)
            left = QToolButton(page)
            right = QToolButton(page)
            left.setArrowType(Qt.ArrowType.LeftArrow)
            right.setArrowType(Qt.ArrowType.RightArrow)
            for b in (left, right):
                b.setFixedWidth(20)
                b.setToolTip(tr('Percorrer grupos de ferramentas'))
            scroll = QScrollArea(page)
            scroll.setWidgetResizable(True)
            scroll.setFrameShape(QFrame.Shape.NoFrame)
            scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            content = QWidget(scroll)
            row = QHBoxLayout(content)
            row.setContentsMargins(1, 0, 1, 0)
            row.setSpacing(0)
            row.setAlignment(Qt.AlignmentFlag.AlignLeft)
            scroll.setWidget(content)
            left.clicked.connect(lambda _=False, s=scroll: s.horizontalScrollBar().setValue(s.horizontalScrollBar().value() - 240))
            right.clicked.connect(lambda _=False, s=scroll: s.horizontalScrollBar().setValue(s.horizontalScrollBar().value() + 240))
            def sync(*_unused, s=scroll, l=left, r=right):
                sb = s.horizontalScrollBar()
                overflow = sb.maximum() > sb.minimum()
                l.setVisible(overflow)
                r.setVisible(overflow)
                l.setEnabled(overflow and sb.value() > sb.minimum())
                r.setEnabled(overflow and sb.value() < sb.maximum())
            scroll.horizontalScrollBar().rangeChanged.connect(sync)
            scroll.horizontalScrollBar().valueChanged.connect(sync)
            layout.addWidget(left)
            layout.addWidget(scroll, 1)
            layout.addWidget(right)
            tabs.addTab(page, tr(name))
            self.rows[name] = row
            self.scrolls[name] = scroll
            QTimer.singleShot(0, sync)
        self._collect_actions()
        self._build_groups()
        self._install_snapping_proxy()
        self.native_action = QAction(tr('Exibir menus e barras originais'), self)
        self.native_action.setToolTip(
            tr('Restaurar temporariamente os controles nativos; ao desmarcar, a Ribbon volta ao modo exclusivo')
        )
        self.native_action.setCheckable(True)
        self.native_action.setChecked(False)
        self.native_action.toggled.connect(on_toggle)
        self._append_group('Interface', 'Controles', [self.native_action])
        self._create_native_menu_fallback()

    def _collect_action(self, action, source):
        if (not _alive(action) or isinstance(action, QWidgetAction)
                or action.isSeparator() or action in self._chrome_actions):
            return False
        if id(action) in self._seen:
            return True  # existing representation counts as covered
        if not _caption(action):
            return False
        tab, group = route_action(_caption(action), action.toolTip(),
                                  action.objectName(), source)
        if tab not in self.rows:
            return False
        self._planned.setdefault((tab, group), []).append(action)
        self._seen.add(id(action))
        return True

    def _get_chrome_actions(self):
        """Toolbar and dock visibility toggles are not georeferencing commands.

        The QGIS menus 'View > Toolbars > File/Edit/View' expose QAction
        objects which otherwise appear as confusing duplicate Ribbon buttons.
        Their original QMenus are still accessible via Interface.
        """
        actions = set()
        for kind in (QToolBar, QDockWidget):
            for widget in self.window.findChildren(kind):
                if widget.parent() is not self.window:
                    continue
                try:
                    toggle = widget.toggleViewAction()
                    if _alive(toggle):
                        actions.add(toggle)
                except (RuntimeError, AttributeError, TypeError):
                    pass
        return actions

    def _collect_menu(self, menu, prefix='', visited=None):
        if not _alive(menu):
            return
        if visited is None:
            visited = set()
        if id(menu) in visited:
            return
        visited.add(id(menu))
        source = (prefix + ' ' + menu.title()).strip()
        for action in menu.actions():
            if not _alive(action) or action.isSeparator():
                continue
            child = action.menu()
            if child is not None:
                self._collect_menu(child, source, visited)
            else:
                self._collect_action(action, source)

    def _collect_actions(self):
        # Native toolbar actions are captured first; menu duplicates are then
        # identified by identity rather than translated text.
        for bar in self.window.findChildren(QToolBar):
            if bar.parent() is not self.window or bar.objectName() == BAR_NAME:
                continue
            try:
                actions = bar.actions()
                label = bar.windowTitle() or bar.objectName() or 'Ferramentas'
                for action in actions:
                    if action.isSeparator():
                        continue
                    # A toolbar visibility toggle is not a real operation.
                    # Retain it only in QGIS's original View menu.
                    covered = (action in self._chrome_actions or
                               self._collect_action(action, label))
                    if not covered:
                        # An unrepresentable control must remain natively.
                        self.incomplete_bars.add(bar)
            except (RuntimeError, AttributeError, TypeError):
                self.incomplete_bars.add(bar)
        menu_bar = self.window.menuBar()
        if _alive(menu_bar):
            for top_action in menu_bar.actions():
                child = top_action.menu()
                if child is not None:
                    self._collect_menu(child)

    def _install_snapping_proxy(self):
        """Expose QGIS' custom snapping button in the PCT tab, if supported.

        The widget stays inside its original QToolBar. Its controls are
        mirrored by a proxy; only when this has succeeded may the otherwise
        empty native toolbar be hidden. Unsupported builds keep it visible.
        """
        for bar in self.window.findChildren(QToolBar):
            if bar.parent() is not self.window or bar.objectName() == BAR_NAME:
                continue
            for action in bar.actions():
                if not isinstance(action, QWidgetAction):
                    continue
                try:
                    native_button = bar.widgetForAction(action)
                    proxy = _make_snapping_proxy(native_button, self)
                except (RuntimeError, AttributeError, TypeError):
                    proxy = None
                if proxy is None:
                    continue
                box = QFrame(self)
                box.setObjectName('QRibbonGeorefGroup')
                layout = QVBoxLayout(box)
                layout.setContentsMargins(7, 4, 7, 3)
                layout.setSpacing(1)
                layout.addWidget(proxy, 0, Qt.AlignmentFlag.AlignCenter)
                label = QLabel(tr('Aderência'), box)
                label.setObjectName('QRibbonGeorefGroupLabel')
                label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                layout.addWidget(label)
                row = self.rows['Pontos de controle']
                if row.count():
                    divider = QFrame(self)
                    divider.setObjectName('QRibbonGeorefDivider')
                    divider.setFixedSize(1, 68)
                    row.addWidget(divider, 0, Qt.AlignmentFlag.AlignVCenter)
                row.addWidget(box)
                self._mirrored_widget_actions.add(id(action))
                self._snapping_native_action = action
                self._snapping_native_bar = bar
                self._snapping_native_button = native_button
                self._snapping_proxy_button = proxy
                return

    def _create_native_menu_fallback(self):
        """Give access to ALL original menus while the menu bar is hidden.

        Reuse original QMenu menuActions, rather than rebuilding commands or
        taking ownership of menus. If none exist, the menu bar stays visible.
        """
        native = self.window.menuBar()
        if not _alive(native):
            self.has_native_menu_fallback = False
            return
        self._native_menu_fallback = QMenu(tr('Menus originais'), self)
        count = 0
        for action in list(native.actions()):
            if not _alive(action) or action.isSeparator():
                continue
            # QMenu.addAction does not reparent the existing QAction and a
            # submenu's menuAction can be presented in multiple menus.
            self._native_menu_fallback.addAction(action)
            count += 1
        self.has_native_menu_fallback = bool(count)
        if not count:
            return
        button = QToolButton(self)
        button.setObjectName('QRibbonGeorefNativeMenus')
        button.setText(tr('Menus originais'))
        button.setToolTip(tr('Abrir os menus nativos sem exibir a barra superior'))
        button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        button.setMenu(self._native_menu_fallback)
        button.setFixedSize(143, 29)
        content = QFrame(self)
        content.setObjectName('QRibbonGeorefGroup')
        layout = QVBoxLayout(content)
        layout.setContentsMargins(7, 4, 7, 3)
        layout.setSpacing(1)
        layout.addWidget(button, alignment=Qt.AlignmentFlag.AlignCenter)
        label = QLabel(tr('Menus do QGIS'), content)
        label.setObjectName('QRibbonGeorefGroupLabel')
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(label)
        row = self.rows['Interface']
        divider = QFrame(self)
        divider.setObjectName('QRibbonGeorefDivider')
        divider.setFixedSize(1, 68)
        row.addWidget(divider, 0, Qt.AlignmentFlag.AlignVCenter)
        row.addWidget(content)

    def _append_group(self, tab, caption, actions):
        row = self.rows[tab]
        if row.count():
            divider = QFrame(self)
            divider.setObjectName('QRibbonGeorefDivider')
            divider.setFixedSize(1, 68)
            row.addWidget(divider, 0, Qt.AlignmentFlag.AlignVCenter)
        row.addWidget(_CommandGroup(tr(caption), actions, self))

    def _build_groups(self):
        for tab in TABS:
            keys = [key for key in self._planned if key[0] == tab]
            order = GROUP_ORDER.get(tab, ())
            keys.sort(key=lambda key: (order.index(key[1]) if key[1] in order
                                       else len(order), key[1]))
            for _, group in keys:
                self._append_group(tab, group, self._planned[(tab, group)])


class GeoreferencerSession(QObject):
    """Manages one native QMainWindow and a reversible Qt toolbar row."""

    def __init__(self, window, parent=None):
        super().__init__(parent)
        self.window = window
        self._disposed = False
        self._native_menu = None
        self._native_bars = []
        self._bar_action_snapshots = []
        self._native_widget_visibility = []
        self._exclusive = False
        self._anchor = None
        self._inserted_break = False
        self.toolbar = QToolBar(tr('QRibbonSkin — Georreferenciador'), window)
        self.toolbar.setObjectName(BAR_NAME)
        self.toolbar.setMovable(False)
        self.toolbar.setFloatable(False)
        self.toolbar.setAllowedAreas(Qt.ToolBarArea.TopToolBarArea)
        self.toolbar.setMinimumWidth(0)
        self.toolbar.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.toolbar.setStyleSheet('QToolBar#' + BAR_NAME +
                                   ' { background: #f7f9fc; border: 0; spacing: 0; }')
        try:
            self.ribbon = GeoreferencerRibbon(window, self.set_native_visible, self.toolbar)
            self.toolbar.addWidget(self.ribbon)
            self._install_top_row()
            window.installEventFilter(self)
            self.toolbar.show()
            # Default to the native-menu-free interface requested by user.
            # Never hide the native menu if no safe fallback is available.
            self.set_native_visible(False)
        except Exception:
            self.dispose()
            raise

    def _install_top_row(self):
        top = Qt.ToolBarArea.TopToolBarArea
        bars = [b for b in self.window.findChildren(QToolBar)
                if b.parent() is self.window and b is not self.toolbar
                and self.window.toolBarArea(b) == top]
        if not bars:
            self.window.addToolBar(top, self.toolbar)
            return
        visible = [b for b in bars if b.isVisible()]
        anchor = min(visible, key=lambda b: (b.geometry().y(), b.geometry().x())) if visible else bars[0]
        self._anchor = anchor
        had_break = self.window.toolBarBreak(anchor)
        self.window.insertToolBar(anchor, self.toolbar)
        if not had_break:
            self.window.insertToolBarBreak(anchor)
            self._inserted_break = True

    def _detach_redundant_toolbar_actions(self, bar):
        """Remove only duplicate presentations; preserve QGIS ownership.

        Toolbar QWidgetActions are not detached. The mirrored snapping
        QWidgetAction may be made invisible in its *native* toolbar, after a
        functional proxy is constructed. This also removes the orphan magnet
        when the toolbar contains unrelated native Qt controls. All previous
        action visibility and order are restored on exit.
        """
        actions = tuple(bar.actions())
        represented = self.ribbon._seen
        eligible = [action for action in actions
                    if (_alive(action) and not action.isSeparator()
                        and not isinstance(action, QWidgetAction)
                        and id(action) in represented)]
        mirrored_widgets = getattr(self.ribbon, '_mirrored_widget_actions', set())
        if eligible:
            self._bar_action_snapshots.append((bar, actions))
            for action in eligible:
                bar.removeAction(action)
        # Hide ONLY mirrored native Qt widget actions, never an unmirrored
        # widget or one whose state cannot be restored.
        for action in bar.actions():
            if (isinstance(action, QWidgetAction)
                    and id(action) in mirrored_widgets):
                try:
                    if not any(old is action for old, _ in self._native_widget_visibility):
                        was_visible = action.isVisible()
                        self._native_widget_visibility.append((action, was_visible))
                        action.setVisible(False)
                except (RuntimeError, AttributeError, TypeError):
                    pass
        remaining = [action for action in bar.actions()
                     if _alive(action) and not action.isSeparator()
                     and action.isVisible()]
        if not remaining:
            bar.hide()
        # Unsupported Qt controls or uncaptured actions keep the bar visible.

    def _restore_widget_visibility(self):
        saved, self._native_widget_visibility = self._native_widget_visibility, []
        for action, originally_visible in saved:
            if _alive(action):
                try:
                    action.setVisible(originally_visible)
                except (RuntimeError, TypeError, AttributeError):
                    pass

    def _restore_toolbar_actions(self):
        """Insert removed QActions back in their exact original order.

        Iterate backward, using the next surviving original action as the
        anchor. Qt's insertAction() preserves the QAction itself, its signals,
        shortcut, enabled/checked state, menus and owner.
        """
        saved, self._bar_action_snapshots = self._bar_action_snapshots, []
        for bar, original in saved:
            if not _alive(bar):
                continue
            anchor = None
            for action in reversed(original):
                if not _alive(action):
                    continue
                try:
                    if action not in bar.actions():
                        if anchor is not None and anchor in bar.actions():
                            bar.insertAction(anchor, action)
                        else:
                            bar.addAction(action)
                    anchor = action
                except (RuntimeError, TypeError):
                    # Continue trying the other actions; never strand the UI.
                    continue

    def set_native_visible(self, native_visible):
        """Toggle native chrome, removing redundant toolbar *presentations*."""
        if self._disposed:
            return
        native_visible = bool(native_visible)
        if not native_visible and not self._exclusive:
            self._native_menu = (self.window.menuBar(), self.window.menuBar().isVisible())
            self._native_bars = [(b, b.isVisible()) for b in self.window.findChildren(QToolBar)
                                 if b.parent() is self.window and b is not self.toolbar]
            self._bar_action_snapshots = []
            self._native_widget_visibility = []
            for bar, initially_visible in self._native_bars:
                if not initially_visible or not _alive(bar):
                    continue
                try:
                    self._detach_redundant_toolbar_actions(bar)
                except (RuntimeError, TypeError, AttributeError):
                    # Restore later even if one Qt toolbar behaves unusually.
                    continue
            # Original menus stay available in the Ribbon's Interface tab.
            if self.ribbon.has_native_menu_fallback:
                self.window.menuBar().hide()
            self._exclusive = True
        elif native_visible and self._exclusive:
            self._restore_native()

    def _restore_native(self):
        # Restore actions BEFORE revealing native toolbars so no empty bar
        # flashes and the QGIS window state is not saved with missing actions.
        self._restore_toolbar_actions()
        self._restore_widget_visibility()
        for bar, visible in self._native_bars:
            if _alive(bar):
                try:
                    bar.setVisible(visible)
                except RuntimeError:
                    pass
        self._native_bars = []
        if self._native_menu:
            menu, visible = self._native_menu
            if _alive(menu):
                try:
                    menu.setVisible(visible)
                except RuntimeError:
                    pass
        self._native_menu = None
        self._exclusive = False
        ribbon = getattr(self, 'ribbon', None)
        if _alive(ribbon):
            button = ribbon.native_action
            if _alive(button) and not button.isChecked():
                previous = button.blockSignals(True)
                button.setChecked(True)
                button.blockSignals(previous)

    def _remove_break(self):
        if self._inserted_break and _alive(self.window) and _alive(self._anchor):
            try:
                self.window.removeToolBarBreak(self._anchor)
            except RuntimeError:
                pass
        self._inserted_break = False
        self._anchor = None

    def eventFilter(self, watched, event):  # noqa: N802
        if watched is self.window and event.type() == QEvent.Type.Close:
            self.dispose()  # before QGIS persists georeferencer toolbar state
        return False

    def dispose(self):
        if self._disposed:
            return
        self._disposed = True
        self._restore_native()
        if _alive(self.window):
            try:
                self.window.removeEventFilter(self)
            except RuntimeError:
                pass
        self._remove_break()
        if _alive(self.window) and _alive(self.toolbar):
            try:
                self.window.removeToolBar(self.toolbar)
            except RuntimeError:
                pass
        if _alive(self.toolbar):
            self.toolbar.hide()
            self.toolbar.deleteLater()


class GeoreferencerManager(QObject):
    """Detect native QGIS georeferencer windows through Qt's Show events.

    Unlike QgsLayoutDesignerInterface, Georeferencer has no comparable public
    QgisInterface opened signal, so observe the known C++ Qt class instead.
    No replacement or reparenting of its canvas, docks or source layers.
    """

    def __init__(self, iface, parent=None):
        super().__init__(parent)
        self.iface = iface
        self._active = False
        self._sessions = {}
        self.last_error = None
        self._scan_scheduled = False

    def start(self):
        if self._active:
            return
        app = QApplication.instance()
        if app is None:
            return
        self._active = True
        app.installEventFilter(self)
        self._scan()

    def _schedule_scan(self):
        if self._active and not self._scan_scheduled:
            self._scan_scheduled = True
            QTimer.singleShot(0, self._scan)

    def _scan(self):
        self._scan_scheduled = False
        if not self._active:
            return
        app = QApplication.instance()
        if app is None:
            return
        # allWidgets also finds an embedded georeferencer in docked mode.
        for window in app.allWidgets():
            if not isinstance(window, QMainWindow) or not _alive(window):
                continue
            try:
                if (not is_georeferencer_class(window.metaObject().className(),
                                               window.objectName())
                        or not window.isVisible()
                        or not window.isWindow()):  # standalone only (no dock reparenting)
                    continue
                key = id(window)
                old = self._sessions.get(key)
                if old is not None and not old._disposed:
                    continue
                self._sessions[key] = GeoreferencerSession(window, self)
            except (RuntimeError, AttributeError, TypeError) as exc:
                self.last_error = 'QRibbonSkin: Georreferenciador: ' + str(exc)
                try:
                    from qgis.core import QgsMessageLog, Qgis
                    QgsMessageLog.logMessage(self.last_error, 'QRibbonSkin', Qgis.MessageLevel.Warning)
                except (AttributeError, RuntimeError, ImportError, TypeError):
                    pass

    def eventFilter(self, watched, event):  # noqa: N802
        if (self._active and event.type() == QEvent.Type.Show
                and isinstance(watched, QMainWindow)):
            try:
                if is_georeferencer_class(watched.metaObject().className(),
                                         watched.objectName()):
                    self._schedule_scan()
            except RuntimeError:
                pass
        return False

    def stop(self):
        app = QApplication.instance()
        self._active = False
        if app is not None:
            try:
                app.removeEventFilter(self)
            except RuntimeError:
                pass
        for session in list(self._sessions.values()):
            session.dispose()
        self._sessions.clear()
