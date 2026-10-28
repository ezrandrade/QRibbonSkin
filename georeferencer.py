"""Optional ergonomic Ribbon for QGIS's *native* Georeferencer.

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
from qgis.PyQt.QtGui import QAction, QFontMetrics, QIcon, QKeySequence, QShortcut
from qgis.PyQt.QtWidgets import (
    QApplication, QMainWindow, QWidget, QWidgetAction, QToolBar, QToolButton,
    QDialog, QLineEdit, QListWidget, QListWidgetItem,
    QTabWidget, QScrollArea, QFrame, QLabel, QHBoxLayout, QVBoxLayout,
    QSizePolicy, QMenu, QDockWidget, QStyle,
)

from .i18n import tr, ui_label
from .georeferencer_model import (
    TABS, GROUP_ORDER, is_georeferencer_class, route_action,
    preferred_action_index, is_native_pan_action, is_native_zoom_to_layer_action,
    connection_display_caption, georeferencer_display_caption
)
from .icon_mapping import display_icon
from .theme import light_palette
from .ribbon import RibbonActionButton
from .georeferencer_model import canonical

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
    """Reuse the approved main-Ribbon action button and dimensions."""
    caption = _caption(action)
    if prominent:
        button = RibbonActionButton(parent)
        button.setDefaultAction(action)
        button.setFixedHeight(72)
        button.setIconSize(QSize(25, 25))
        button.setMinimumWidth(84)
    else:
        button = QToolButton(parent)
        button.setAutoRaise(True)
        button.setDefaultAction(action)
        button.setObjectName('QRibbonGeorefSecondary')
        button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        button.setIconSize(QSize(16, 16))
        button.setFixedHeight(30)
        metrics = QFontMetrics(button.font())
        button.setFixedWidth(min(300, max(108, metrics.horizontalAdvance(caption) + 42)))
        font = button.font()
        font.setPointSizeF(8.1)
        button.setFont(font)
    button.setToolTip(action.toolTip() or caption)
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
    proxy.setIconSize(QSize(25, 25))
    proxy.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
    proxy.setCheckable(source.isCheckable())
    proxy.setChecked(source.isChecked())
    proxy.setEnabled(source.isEnabled())
    proxy.setFixedHeight(72)
    proxy.setMinimumWidth(94)
    font = proxy.font()
    font.setPointSizeF(8.5)
    proxy.setFont(font)
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
    """Principal-style group: one native leading QAction, remaining in dropdown.

    The QActions stay owned by QGIS. No toolbar widget is moved or copied.
    The group resembles the approved Main tab: one large icon over its title,
    one drop-down arrow, a bottom-centered section heading and slim dividers.
    """

    def __init__(self, caption, actions, parent, leader_action=None,
                 local_titles=None):
        super().__init__(parent)
        self.setObjectName('QRibbonGeorefGroup')
        actions = [a for a in actions if _alive(a) and not isinstance(a, QWidgetAction)
                   and not a.isSeparator()]
        seen = set()
        unique_actions = []
        for action in actions:
            if id(action) not in seen:
                seen.add(id(action))
                unique_actions.append(action)
        actions = unique_actions
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 3, 10, 1)
        layout.setSpacing(1)
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        layout.addLayout(row, 1)
        if actions:
            chosen = preferred_action_index(caption, [_caption(a) for a in actions])
            # The selected Pan QAction is always the lead in the Principal
            # navigation section, regardless of source-tab routing/order.
            leader = (leader_action if leader_action in actions else
                      actions[chosen if chosen is not None else 0])
            button = _action_button(leader, self, prominent=True)
            if local_titles:
                local_label = local_titles(leader)
                if local_label:
                    button.set_display_caption(local_label)
            others = [a for a in actions if a is not leader]
            if others:
                # Populate on open so action enabled/checked state remains
                # current; local labels never modify QGIS-owned QAction text.
                menu = QMenu(self)
                menu.aboutToShow.connect(
                    lambda items=tuple(others), target=menu, titles=local_titles:
                    self._fill_menu(target, items, titles))
                button.setMenu(menu)
                button.setPopupMode(QToolButton.ToolButtonPopupMode.MenuButtonPopup)
            row.addWidget(button)
        title = QLabel(ui_label(caption), self)
        title.setObjectName('QRibbonGeorefGroupLabel')
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setFixedHeight(19)
        title.setToolTip(ui_label(caption))
        layout.addWidget(title)
        # Native title must remain fully visible even when compact captions
        # are preferred and viewport horizontal scroll is active.
        self.setMinimumWidth(max(92, title.fontMetrics().horizontalAdvance(ui_label(caption)) + 20))
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)

    @staticmethod
    def _fill_menu(menu, actions, local_titles=None):
        menu.clear()
        for action in actions:
            if not _alive(action) or not action.isVisible():
                continue
            native_menu = action.menu()
            if _alive(native_menu):
                # Native submenus may populate lazily; preserve the original.
                menu.addAction(native_menu.menuAction())
                continue
            title = local_titles(action) if local_titles else None
            if not title:
                menu.addAction(action)
                continue
            # A presentation alias is required: changing action.setText()
            # would also rename commands in the QGIS native menus/toolbars.
            alias = menu.addAction(action.icon(), ui_label(title))
            alias.setToolTip(action.toolTip() or _caption(action))
            alias.setEnabled(action.isEnabled())
            alias.setCheckable(action.isCheckable())
            if action.isCheckable():
                alias.setChecked(action.isChecked())
            alias.triggered.connect(lambda _checked=False, native=action:
                                    native.trigger() if _alive(native) else None)
        if not menu.actions():
            placeholder = menu.addAction(tr('Nenhuma ferramenta disponível'))
            placeholder.setEnabled(False)


class GeoreferencerSpotlight(QDialog):
    """Centered, native-QAction search confined to one Georeferencer window."""

    def __init__(self, ribbon):
        super().__init__(ribbon.window, Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        self.setObjectName('QRibbonGeorefSpotlight')
        self._ribbon = ribbon
        self._matches = []
        self.setModal(False)
        self.setMinimumWidth(320)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 12)
        layout.setSpacing(8)
        title = QLabel(tr('Buscar ferramentas'), self)
        font = title.font()
        font.setPointSize(11)
        font.setBold(True)
        title.setFont(font)
        layout.addWidget(title)
        self.query = QLineEdit(self)
        self.query.setPlaceholderText(tr('Digite para buscar ferramentas'))
        self.query.setClearButtonEnabled(True)
        self.query.setMinimumHeight(36)
        self.query.textChanged.connect(self._populate)
        self.query.returnPressed.connect(self._activate_selected)
        self.query.installEventFilter(self)
        layout.addWidget(self.query)
        self.results = QListWidget(self)
        self.results.setIconSize(QSize(20, 20))
        self.results.setMinimumHeight(200)
        self.results.itemActivated.connect(self._activate_item)
        self.results.itemClicked.connect(self._activate_item)
        layout.addWidget(self.results)
        layout.addWidget(QLabel(tr('Enter: executar  ·  Esc: fechar'), self))
        colors = light_palette()
        self.setStyleSheet('QDialog#QRibbonGeorefSpotlight {'
                           'background: %s; color: %s; border: 1px solid %s; '
                           'border-radius: 10px; }'
                           % (colors['field'], colors['text'], colors['border']))

    def eventFilter(self, watched, event):  # noqa: N802
        if watched is self.query and event.type() == QEvent.Type.KeyPress:
            if event.key() == Qt.Key.Key_Escape:
                self.close()
                return True
            if event.key() in (Qt.Key.Key_Down, Qt.Key.Key_Up):
                delta = 1 if event.key() == Qt.Key.Key_Down else -1
                self.results.setCurrentRow(max(0, min(self.results.count() - 1,
                                                     self.results.currentRow() + delta)))
                return True
        return super().eventFilter(watched, event)

    def keyPressEvent(self, event):  # noqa: N802
        if event.key() == Qt.Key.Key_Escape:
            self.close()
        else:
            super().keyPressEvent(event)

    def open_centered(self, initial_text=''):
        window = self._ribbon.window
        width = max(280, min(660, window.width() - 48))
        self.resize(width, 340)
        center = window.mapToGlobal(window.rect().center())
        self.move(center.x() - self.width() // 2, center.y() - self.height() // 2)
        self.query.setText(initial_text)
        self._populate(initial_text)
        self.show()
        self.raise_()
        self.activateWindow()
        self.query.setFocus()
        self.query.selectAll()

    def _populate(self, text):
        self.results.clear()
        self._matches = self._ribbon.search_actions(text)
        for name, action in self._matches:
            item = QListWidgetItem(action.icon(), name, self.results)
            item.setToolTip(action.toolTip() or name)
        if self.results.count():
            self.results.setCurrentRow(0)
        else:
            placeholder = QListWidgetItem(tr('Nenhum comando encontrado'), self.results)
            placeholder.setFlags(Qt.ItemFlag.NoItemFlags)

    def _activate_selected(self):
        self._activate_item(self.results.currentItem())

    def _activate_item(self, item):
        if item is None:
            return
        index = self.results.row(item)
        if 0 <= index < len(self._matches):
            action = self._matches[index][1]
            self.close()
            if _alive(action) and action.isEnabled() and action.isVisible():
                action.trigger()


class GeoreferencerRibbon(QWidget):
    """Compact per-window Ribbon, no ownership of original QAction objects."""

    QSS = r'''
    QWidget#QRibbonGeorefWidget {
        background-color: #f7f9fc; color: #24364a;
        font-family: 'Segoe UI', 'Noto Sans', sans-serif;
    }
    /* Uniform canvas across the tab strip, pane and scroll viewport.
       Qt can otherwise paint the Georeferencer's native toolbar palette as
       a contrasting horizontal band behind the Ribbon tab labels. */
    QTabWidget#QRibbonGeorefTabs { border: 0; margin: 0; padding: 0;
        background-color: #f7f9fc; }
    QTabWidget#QRibbonGeorefTabs::pane { border: 0; margin: 0; padding: 0;
        background-color: #f7f9fc; }
    QTabWidget#QRibbonGeorefTabs QTabBar { border: 0; margin: 0;
        padding: 0; background-color: #f7f9fc; }
    QTabWidget#QRibbonGeorefTabs QTabBar::tab { background: transparent;
        padding: 5px 12px; margin: 0 1px; border: 0;
        border-bottom: 2px solid transparent; color: #24364a; }
    QTabWidget#QRibbonGeorefTabs QTabBar::tab:hover { background: #e2ebf6; }
    QTabWidget#QRibbonGeorefTabs QTabBar::tab:selected { background: #dceafa;
        color: #245fba; border-bottom: 2px solid #245fba; }
    QWidget#QRibbonGeorefPage { background-color: #f7f9fc; border: 0; }
    QScrollArea#QRibbonGeorefScroll { background-color: #f7f9fc; border: 0; }
    QWidget#QRibbonGeorefScrollViewport { background-color: #f7f9fc; }
    QWidget#QRibbonGeorefScrollContent { background-color: #f7f9fc; }
    QFrame#QRibbonGeorefGroup { background: transparent; border: 0; }
    QLabel#QRibbonGeorefGroupLabel { color: #596e83; font-size: 8pt; border: 0; }
    QToolButton#QRibbonSkinTool, QToolButton#QRibbonGeorefSecondary,
    QToolButton#QRibbonSnappingProxy, QToolButton#QRibbonGeorefNativeMenus {
        border: 0; border-radius: 4px; margin: 0; padding: 0;
        background: transparent; color: #24364a; }
    QToolButton#QRibbonSkinTool:hover, QToolButton#QRibbonGeorefSecondary:hover,
    QToolButton#QRibbonSnappingProxy:hover, QToolButton#QRibbonGeorefNativeMenus:hover {
        background: #e2ebf6; }
    QToolButton#QRibbonSkinTool:pressed, QToolButton#QRibbonGeorefSecondary:pressed {
        background: #d2e3f8; }
    QToolButton#QRibbonSkinTool:checked, QToolButton#QRibbonSnappingProxy:checked {
        background: #dceafa; }
    QFrame#QRibbonGeorefDivider { background: #d5dee9; border: 0; }
    QFrame#QRibbonGeorefSearchCorner { background: transparent; border: 0; }
    QLineEdit#QRibbonGeorefSearch { background: #ffffff; color: #24364a;
        border: 1px solid #c3d0df; border-radius: 5px;
        padding: 1px 7px; font-size: 9pt;
        selection-background-color: #245fba; }
    QLineEdit#QRibbonGeorefSearch:focus { border: 1px solid #245fba; }
    '''


    def __init__(self, window, on_toggle, parent=None):
        super().__init__(parent)
        self.window = window
        self.setObjectName('QRibbonGeorefWidget')
        self.setMinimumWidth(0)
        self.setFixedHeight(124)  # same compact height as the main QGIS Ribbon
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setStyleSheet(self.QSS)
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        tabs = QTabWidget(self)
        tabs.setObjectName('QRibbonGeorefTabs')
        tabs.setDocumentMode(True)
        tabs.setUsesScrollButtons(True)
        tabs.tabBar().setExpanding(False)
        tabs.tabBar().setDrawBase(False)
        tabs.tabBar().setElideMode(Qt.TextElideMode.ElideNone)
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
            scroll.setObjectName('QRibbonGeorefScroll')
            scroll.viewport().setObjectName('QRibbonGeorefScrollViewport')
            scroll.setWidgetResizable(True)
            scroll.setFrameShape(QFrame.Shape.NoFrame)
            scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            content = QWidget(scroll)
            content.setObjectName('QRibbonGeorefScrollContent')
            row = QHBoxLayout(content)
            row.setContentsMargins(1, 0, 1, 0)
            row.setSpacing(0)
            row.setAlignment(Qt.AlignmentFlag.AlignLeft)
            scroll.setWidget(content)
            left.clicked.connect(lambda _=False, s=scroll: s.horizontalScrollBar().setValue(s.horizontalScrollBar().value() - 240))
            right.clicked.connect(lambda _=False, s=scroll: s.horizontalScrollBar().setValue(s.horizontalScrollBar().value() + 240))
            def sync(*_unused, s=scroll, left_button=left, right_button=right):
                sb = s.horizontalScrollBar()
                overflow = sb.maximum() > sb.minimum()
                left_button.setVisible(overflow)
                right_button.setVisible(overflow)
                left_button.setEnabled(overflow and sb.value() > sb.minimum())
                right_button.setEnabled(overflow and sb.value() < sb.maximum())
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
        self._make_search_corner()
        self._spotlight = GeoreferencerSpotlight(self)
        self._search_shortcut = QShortcut(QKeySequence('Alt+Q'), self.window)
        self._search_shortcut.setContext(Qt.ShortcutContext.WindowShortcut)
        self._search_shortcut.activated.connect(self.open_spotlight)
        self._update_search_geometry()

    def _make_search_corner(self):
        """Match the main Ribbon search field in the tab-header row."""
        host = QFrame(self)
        host.setObjectName('QRibbonGeorefSearchCorner')
        layout = QHBoxLayout(host)
        layout.setContentsMargins(5, 2, 5, 2)
        layout.setSpacing(3)
        self.search = QLineEdit(host)
        self.search.setObjectName('QRibbonGeorefSearch')
        self.search.setPlaceholderText(tr('Buscar ferramenta...  Alt+Q'))
        self.search.setToolTip(tr('Abrir busca central (Alt+Q)'))
        self.search.setFixedHeight(24)
        self.search.setClearButtonEnabled(True)
        self.search.returnPressed.connect(lambda: self.open_spotlight(self.search.text()))
        from pathlib import Path
        icon = QIcon(str(Path(__file__).resolve().parent / 'resources' / 'search.svg'))
        search_action = self.search.addAction(
            icon, QLineEdit.ActionPosition.TrailingPosition)
        search_action.triggered.connect(
            lambda _checked=False: self.open_spotlight(self.search.text()))
        layout.addWidget(self.search)
        self.search_host = host
        host.raise_()

    def _update_search_geometry(self):
        if not hasattr(self, 'search_host'):
            return
        width = self.width()
        if width < 100:
            return
        search_width = 168 if width < 850 else (210 if width < 1240 else 260)
        host_width = search_width + 12
        self.search.setFixedWidth(search_width)
        self.search_host.setGeometry(max(0, width - host_width - 5),
                                     0, host_width, 30)
        self.tabs.tabBar().setMaximumWidth(max(100, width - host_width - 14))
        self.search_host.raise_()

    def resizeEvent(self, event):  # noqa: N802
        super().resizeEvent(event)
        self._update_search_geometry()

    def search_actions(self, text, limit=35):
        """Find existing native QActions without changing their ownership."""
        query = canonical(text)
        if len(query) < 2:
            return []
        result = []
        seen = set()
        # _planned retains native QActions even after toolbar buttons are
        # detached from their original toolbars by GeoreferencerSession.
        all_actions = [a for actions in self._planned.values() for a in actions]
        all_actions.extend(self.window.findChildren(QAction))
        for action in all_actions:
            if (not _alive(action) or isinstance(action, QWidgetAction)
                    or id(action) in seen or action.isSeparator()
                    or not action.isEnabled() or not action.isVisible()
                    or action.menu() is not None):
                continue
            seen.add(id(action))
            name = _caption(action)
            if name and query in canonical(name + ' ' + action.toolTip()):
                result.append((name, action))
                if len(result) >= limit:
                    break
        return result

    def open_spotlight(self, initial_text=''):
        if hasattr(self, '_spotlight') and _alive(self._spotlight):
            self._spotlight.open_centered(initial_text)

    def dispose_search(self):
        shortcut = getattr(self, '_search_shortcut', None)
        if _alive(shortcut):
            shortcut.setEnabled(False)
            shortcut.deleteLater()
        self._search_shortcut = None
        spotlight = getattr(self, '_spotlight', None)
        if _alive(spotlight):
            spotlight.close()
            spotlight.deleteLater()
        self._spotlight = None

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
                label = QLabel(ui_label('Aderência'), box)
                label.setObjectName('QRibbonGeorefGroupLabel')
                label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                layout.addWidget(label)
                # Keep the native snapping button in the workflow-oriented
                # Principal tab, mirroring the main QGIS Ribbon philosophy.
                row = self.rows['Principal']
                if row.count():
                    divider = QFrame(self)
                    divider.setObjectName('QRibbonGeorefDivider')
                    divider.setFixedSize(1, 76)
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
        button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_TitleBarMenuButton))
        button.setIconSize(QSize(25, 25))
        button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        button.setMenu(self._native_menu_fallback)
        button.setFixedHeight(72)
        button.setMinimumWidth(94)
        font = button.font()
        font.setPointSizeF(8.5)
        button.setFont(font)
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
        divider.setFixedSize(1, 76)
        row.addWidget(divider, 0, Qt.AlignmentFlag.AlignVCenter)
        row.addWidget(content)

    def _append_group(self, tab, caption, actions, leader_action=None,
                      local_titles=None):
        row = self.rows[tab]
        if row.count():
            divider = QFrame(self)
            divider.setObjectName('QRibbonGeorefDivider')
            divider.setFixedSize(1, 76)
            row.addWidget(divider, 0, Qt.AlignmentFlag.AlignVCenter)
        row.addWidget(_CommandGroup(tr(caption), actions, self,
                                    leader_action=leader_action,
                                    local_titles=local_titles))

    @staticmethod
    def _find_move_navigation_action(planned):
        """Locate QGIS' native pan/move QAction, even when routed to Exibir.

        Only native actions collected from the Georeferencer are candidates;
        the original tab/action remains available and is never reparented.
        """
        candidates = [action for actions in planned.values() for action in actions
                      if _alive(action) and not isinstance(action, QWidgetAction)
                      and not action.isSeparator()]
        # Prefer explicit 'Mover' / 'Pan' over generic zoom and GCP movements.
        for action in candidates:
            if is_native_pan_action(_caption(action), action.objectName()):
                return action
        return None

    @staticmethod
    def _find_zoom_to_layer_action(planned):
        """Choose the native Georeferencer Zoom-to-Layer QAction by identity.

        Search all collected native actions because QGIS versions can route
        this command to different menu/toolbar groups. Never substitute the
        similarly named Zoom In or Move GCP tools.
        """
        candidates = [action for actions in planned.values() for action in actions
                      if _alive(action) and not isinstance(action, QWidgetAction)
                      and not action.isSeparator()]
        for action in candidates:
            if is_native_zoom_to_layer_action(_caption(action), action.objectName()):
                return action
        return None

    def _build_principal_groups(self):
        """Offer a workflow-oriented Main tab, using already captured actions.

        The original contextual tabs remain available, so no command is lost.
        Actions may be presented in both tabs without changing QAction owners.
        Do not guess unknown QGIS toolbar actions from captions alone.
        """
        groups = (
            ('Abrir dados', (('Arquivo', 'Abrir dados'),)),
            ('Pontos de controle', (('Pontos de controle', 'Editar PCT'),
                                   ('Pontos de controle', 'Arquivos PCT'))),
            ('Navegação', (('Navegar', 'Visualização'),
                           ('Navegar', 'Navegação'))),
            ('Sincronização', (('Navegar', 'Sincronização'),)),
            # Reuse Exibir's actual native actions; its existing section remains.
            ('Conectar', (('Exibir', 'Outras ferramentas'),)),
            ('Transformação', (('Transformar', 'Executar'),
                               ('Transformar', 'Configurações'),
                               ('Transformar', 'Transformação'))),
            ('Histograma', (('Exibir', 'Painéis'),)),
        )
        for heading, sources in groups:
            items = []
            seen = set()
            leader_action = None
            for source in sources:
                for action in self._planned.get(source, ()):
                    if id(action) not in seen:
                        seen.add(id(action))
                        items.append(action)
            if heading == 'Navegação':
                # Explicitly prefer the QGIS native 'Aproximar para Camada'
                # action, independently of source tab and original ordering.
                zoom_layer_action = self._find_zoom_to_layer_action(self._planned)
                if zoom_layer_action is not None:
                    leader_action = zoom_layer_action
                    if id(zoom_layer_action) not in seen:
                        seen.add(id(zoom_layer_action))
                        items.insert(0, zoom_layer_action)
            elif heading == 'Conectar':
                # Use the QGIS -> Georeferencer direction as the primary
                # action. Do not mistake the inverse command for it.
                for action in items:
                    if connection_display_caption(_caption(action)) == 'QGIS ao Georreferenciador':
                        leader_action = action
                        break
            if items:
                if heading == 'Histograma':
                    preferred = preferred_action_index('Histograma',
                                                       [_caption(a) for a in items])
                    if preferred is not None:
                        leader_action = items[preferred]
                self._append_group(
                    'Principal', heading, items, leader_action=leader_action,
                    local_titles=(
                        (lambda action: tr(connection_display_caption(_caption(action)))
                         if connection_display_caption(_caption(action)) else None)
                        if heading == 'Conectar' else
                        (lambda action: tr('Zoom à Camada')
                         if is_native_zoom_to_layer_action(_caption(action),
                                                           action.objectName())
                         else None)
                        if heading == 'Navegação' else
                        (lambda action, group=heading: tr(
                            georeferencer_display_caption(group, _caption(action)))
                         if georeferencer_display_caption(group, _caption(action))
                         else None)
                        if heading == 'Histograma' else None))

    def _build_groups(self):
        self._build_principal_groups()
        for tab in TABS:
            if tab == 'Principal':
                continue
            keys = [key for key in self._planned if key[0] == tab]
            order = GROUP_ORDER.get(tab, ())
            keys.sort(key=lambda key: (order.index(key[1]) if key[1] in order
                                       else len(order), key[1]))
            for _, group in keys:
                if (tab == 'Pontos de controle' and group == 'Pontos de controle'
                        and ('Pontos de controle', 'Editar PCT') in self._planned):
                    # Integrate unclassified GCP tools with the renamed Editar
                    # PCT group. Do not show two identically named sections.
                    continue
                actions = list(self._planned[(tab, group)])
                display_group = ('Pontos de Controle' if tab == 'Pontos de controle'
                                 and group == 'Pontos de controle' else group)
                local_titles = None
                if tab == 'Pontos de controle' and group == 'Editar PCT':
                    display_group = 'Pontos de Controle'
                    seen = {id(action) for action in actions}
                    for action in self._planned.get((tab, 'Pontos de controle'), ()):
                        if id(action) not in seen:
                            actions.append(action)
                            seen.add(id(action))
                    def _pct_title(action):
                        return (
                            tr(georeferencer_display_caption('Pontos de Controle', _caption(action)))
                            if georeferencer_display_caption('Pontos de Controle', _caption(action))
                            else None)
                    local_titles = _pct_title
                elif tab == 'Pontos de controle' and group == 'Aderência':
                    def _snapping_title(action):
                        return (
                            tr(georeferencer_display_caption('Aderência', _caption(action)))
                            if georeferencer_display_caption('Aderência', _caption(action))
                            else None)
                    local_titles = _snapping_title
                leader_action = None
                if tab == 'Pontos de controle' and display_group == 'Pontos de Controle':
                    preferred = preferred_action_index('Pontos de Controle',
                                                       [_caption(a) for a in actions])
                    if preferred is not None:
                        leader_action = actions[preferred]
                self._append_group(tab, display_group, actions,
                                   leader_action=leader_action,
                                   local_titles=local_titles)


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
        if _alive(getattr(self, 'ribbon', None)):
            self.ribbon.dispose_search()
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
