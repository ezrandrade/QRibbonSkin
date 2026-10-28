"""Experimental Ribbon for the native QGIS Layout Designer (QGIS 4.x / Qt6).

Each QgsLayoutDesignerInterface is transient and may coexist with others.
The manager listens to the documented lifecycle signals, then wraps *native*
QActions/QMenus in QToolButtons without reimplementing any layout/export logic.

Native Layout Designer QActions already represented in the Ribbon are removed
from native toolbars only while the Ribbon is exclusive. Any embedded QWidgetAction
(page, Atlas and custom editors) remains in place. On deactivation, the exact
native action order and original toolbar/menu visibility are restored.
No QMainWindow.saveState/restoreState calls, QGIS settings or layout data writes.
"""

from qgis.PyQt.QtCore import QObject, Qt, QEvent, QTimer, QSize
from qgis.PyQt.QtGui import QAction, QIcon, QFontMetrics, QKeySequence, QShortcut
from qgis.PyQt.QtWidgets import (
    QDockWidget, QFrame, QHBoxLayout, QLabel, QMainWindow, QMenu, QMenuBar, QStatusBar, QTabBar, QScrollArea, QSizePolicy,
    QTabWidget, QToolBar, QToolButton, QVBoxLayout, QWidget, QWidgetAction,
    QDialog, QLineEdit, QListWidget, QListWidgetItem, QStyle,
)

from .i18n import tr, ui_label
from .layout_designer_model import (
    TAB_NAMES, SOURCE_TABS, is_output_action, title_for_source,
    tab_for_native_toolbar, layout_action_placement, LAYOUT_GROUP_ORDER, normalized,
)
from .icon_mapping import display_icon
from .ribbon import RibbonActionButton
from .theme import light_palette
from .layout_color_tokens import (
    DOCK_LIGHT_QSS, TOOLBAR_LIGHT_QSS,
    MENU_LIGHT_QSS, TAB_LIGHT_QSS, STATUS_LIGHT_QSS, RULER_LIGHT_QSS,
    RIBBON_LIGHT_QSS, RIBBON_TOOLBAR_QSS,
)


RIBBON_TOOLBAR_NAME = "QRibbonSkinLayoutDesignerToolbar"


def _qobject_alive(value):
    if value is None:
        return False
    try:
        from qgis.PyQt import sip
        return not sip.isdeleted(value)
    except (ImportError, AttributeError):
        # The caller must additionally guard RuntimeError on deleted wrappers.
        return True


def _menu_actions(menu):
    if not _qobject_alive(menu):
        return []
    try:
        return [act for act in menu.actions() if not act.isSeparator()]
    except RuntimeError:
        return []


def _action_label(action):
    """Read a label from native QAction without modifying its text or owner."""
    for value in (action.text(), action.toolTip(), action.objectName()):
        title = str(value or "").replace("&", "").strip()
        if title:
            return title
    return ""


def _layout_action_by_labels(actions, labels, object_names=()):
    """Locate the *native* QAction by task, not by its position in a toolbar.

    Native QGIS captions vary across locales. Search exact captions first,
    then more descriptive captions/tooltips and lastly QObject identifiers.
    This does not alter QAction text, ownership or shortcuts.
    """
    terms = tuple(normalized(label) for label in labels)
    for term in terms:
        for action in actions:
            if normalized(str(action.text() or '')) == term:
                return action
    for term in terms:
        for action in actions:
            for value in (action.text(), action.toolTip()):
                if term in normalized(str(value or '')):
                    return action
    identifiers = tuple(name.casefold() for name in object_names)
    for identifier in identifiers:
        for action in actions:
            if identifier in str(action.objectName() or '').casefold():
                return action
    return None


def _principal_preferred_action(section, actions):
    """Choose a native action for the principal button of each section."""
    # Select/Move Item is different from Move Content or Select All.
    # Zoom Full (Ver Tudo) is different from Pan Layout or Zoom to Page.
    preferred = {
        'Editar itens': (
            ('selecionar/mover item', 'selecionar mover item',
             'select/move item', 'select move item'),
            ('mActionSelectMoveItem', 'mActionSelectMove'),
        ),
        'Navegação': (
            ('ver tudo', 'zoom total', 'zoom full', 'zoom to full extent',
             'zoom para toda a pagina'),
            ('mActionZoomFull', 'mActionZoomToFullExtent'),
        ),
    }
    if section in preferred:
        labels, names = preferred[section]
        found = _layout_action_by_labels(actions, labels, names)
        if found is not None:
            return found
        # Do not silently choose 'Select All' or 'Pan Layout' when a
        # version-specific QGIS translation cannot be matched.
        return None
    priorities = {
        'Arquivo': ('salvar layout', 'save layout', 'salvar', 'save', 'abrir', 'open'),
        'Inserir elementos': ('adicionar mapa', 'add map', 'adicionar item', 'add item'),
        'Organizar itens': ('agrupar', 'group', 'alinhar', 'align'),
        'Atlas': ('visualizar atlas', 'preview atlas', 'atlas preview',
                  'habilitar atlas', 'enable atlas'),
        'Exportar': ('exportar como pdf', 'export as pdf', 'export pdf',
                     'imprimir layout', 'print layout'),
    }
    keywords = priorities.get(section, ())
    names = [normalized(_action_label(action)) for action in actions]
    for term in keywords:
        for index, name in enumerate(names):
            if name == term:
                return actions[index]
    for term in keywords:
        for index, name in enumerate(names):
            if term in name:
                return actions[index]
    return actions[0] if actions else None


def _principal_first_dropdown_action(section, actions):
    """Return the first *secondary* action requested by the UI layout."""
    if section == 'Editar itens':
        return _layout_action_by_labels(
            actions,
            ('mover conteudo', 'mover o conteudo', 'move content',
             'move item content'),
            ('mActionMoveItemContent', 'mActionMoveContent'),
        )
    if section == 'Navegação':
        return _layout_action_by_labels(
            actions,
            ('deslocar layout', 'mover layout', 'movimentar layout',
             'pan layout', 'move layout'),
            ('mActionPan', 'mActionPanLayout'),
        )
    return None


class _LayoutGroup(QFrame):
    """Compact 124px style: one leading native action and optional dropdown."""

    def __init__(self, title, parent, leader=None):
        super().__init__(parent)
        self.setObjectName('QRibbonLayoutGroup')
        self._actions = []
        self._leader = leader
        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 3, 10, 1)
        outer.setSpacing(1)
        self.commands = QHBoxLayout()
        self.commands.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self.commands.setContentsMargins(0, 0, 0, 0)
        outer.addLayout(self.commands, 1)
        name = QLabel(ui_label(title), self)
        name.setObjectName('QRibbonLayoutGroupName')
        name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        name.setFixedHeight(19)
        name.setToolTip(ui_label(title))
        outer.addWidget(name)
        self.setMinimumWidth(max(92, name.fontMetrics().horizontalAdvance(ui_label(title)) + 20))
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)

    def add_action(self, action):
        if action is not None and _qobject_alive(action) and action not in self._actions:
            self._actions.append(action)

    def finalize(self):
        actions = [a for a in self._actions if _qobject_alive(a)
                   and not isinstance(a, QWidgetAction) and not a.isSeparator()]
        if not actions:
            return
        lead = self._leader if self._leader in actions else actions[0]
        button = RibbonActionButton(self)
        button.setDefaultAction(lead)
        button.setFixedHeight(72)
        button.setIconSize(QSize(25, 25))
        button.setMinimumWidth(84)
        other = [a for a in actions if a is not lead]
        if other:
            # Build at popup-time; QGIS updates enabled/checked dynamically.
            menu = QMenu(self)
            def populate():
                menu.clear()
                # A leading QAction can itself own a native QMenu. Keep it
                # reachable even when the group's other actions need a menu.
                native_lead_menu = lead.menu()
                if _qobject_alive(native_lead_menu):
                    menu.addAction(native_lead_menu.menuAction())
                    menu.addSeparator()
                for action in other:
                    if not _qobject_alive(action) or not action.isVisible():
                        continue
                    child = action.menu()
                    if _qobject_alive(child):
                        menu.addAction(child.menuAction())
                    else:
                        menu.addAction(action)
                if not menu.actions():
                    placeholder = menu.addAction(tr('Nenhuma ferramenta disponível'))
                    placeholder.setEnabled(False)
            menu.aboutToShow.connect(populate)
            button.setMenu(menu)
            button.setPopupMode(QToolButton.ToolButtonPopupMode.MenuButtonPopup)
        elif _qobject_alive(lead.menu()):
            button.setMenu(lead.menu())
            button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.commands.addWidget(button)



class LayoutChrome:
    """Style only existing Layout Designer docks and vertical toolbars.

    No global QSS, QApplication.palette or dock geometry is modified.
    All stylesheets are restored exactly on detachment.
    """

    def __init__(self, window):
        self.window = window
        self.saved = []

    def apply(self):
        """Apply a single light chrome palette to native layout UI widgets.

        Do not change QApplication, QMainWindow, the layout view, page scene,
        map symbols, item properties or the QGIS project's stored settings.
        Never style a tab which belongs to our separately styled Ribbon.
        """
        for dock in self.window.findChildren(QDockWidget):
            if dock.parent() is self.window:
                self._style(dock, DOCK_LIGHT_QSS)
        for bar in self.window.findChildren(QToolBar):
            if bar.parent() is self.window and bar.objectName() != RIBBON_TOOLBAR_NAME:
                # The native Atlas controls and embedded widgets stay alive.
                self._style(bar, TOOLBAR_LIGHT_QSS)
        # QMainWindow's right-hand dock area can own the tab bar itself, rather
        # than nesting it inside a QDockWidget. Re-style only those tabs.
        for tabs in self.window.findChildren(QTabBar):
            if (tabs.parent() is self.window or
                    self._has_dock_ancestor(tabs)):
                self._style(tabs, TAB_LIGHT_QSS)
        for menu in self.window.findChildren(QMenuBar):
            if menu.parent() is self.window:
                self._style(menu, MENU_LIGHT_QSS)
        for status in self.window.findChildren(QStatusBar):
            if status.parent() is self.window:
                self._style(status, STATUS_LIGHT_QSS)
        # QgsLayoutRuler uses custom painting. Styling is best-effort: the
        # ruler may retain its native ticks/background on some QGIS builds.
        for widget in self.window.findChildren(QWidget):
            if (_qobject_alive(widget)
                    and widget.metaObject().className() == 'QgsLayoutRuler'
                    and self._belongs_to_layout(widget)):
                self._style(widget, RULER_LIGHT_QSS)

    def _belongs_to_layout(self, widget):
        current = widget
        while current is not None and _qobject_alive(current):
            if current is self.window:
                return True
            current = current.parent()
        return False

    @staticmethod
    def _has_dock_ancestor(widget):
        current = widget.parent()
        while current is not None and _qobject_alive(current):
            if isinstance(current, QDockWidget):
                return True
            if isinstance(current, QMainWindow):
                return False
            current = current.parent()
        return False

    def _style(self, widget, qss):
        if not _qobject_alive(widget):
            return
        original = widget.styleSheet()
        widget.setStyleSheet(original + "\n" + qss)
        self.saved.append((widget, original))

    def restore(self):
        for widget, original in reversed(self.saved):
            if _qobject_alive(widget):
                try:
                    widget.setStyleSheet(original)
                except RuntimeError:
                    pass
        self.saved.clear()


class LayoutSpotlight(QDialog):
    """Centered Alt+Q command search for one Layout Designer window."""

    def __init__(self, ribbon):
        super().__init__(ribbon.native_window,
                         Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        self._ribbon = ribbon
        self._matches = []
        self.setObjectName('QRibbonLayoutSpotlight')
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
        self.setStyleSheet('QDialog#QRibbonLayoutSpotlight {'
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
                row = max(0, min(self.results.count() - 1, self.results.currentRow() + delta))
                self.results.setCurrentRow(row)
                return True
        return super().eventFilter(watched, event)

    def keyPressEvent(self, event):  # noqa: N802
        if event.key() == Qt.Key.Key_Escape:
            self.close()
        else:
            super().keyPressEvent(event)

    def open_centered(self, initial_text=''):
        window = self._ribbon.native_window
        self.resize(max(280, min(660, window.width() - 48)), 340)
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
            item = QListWidgetItem(tr('Nenhum comando encontrado'), self.results)
            item.setFlags(Qt.ItemFlag.NoItemFlags)

    def _activate_selected(self):
        self._activate_item(self.results.currentItem())

    def _activate_item(self, item):
        if item is None:
            return
        index = self.results.row(item)
        if 0 <= index < len(self._matches):
            action = self._matches[index][1]
            self.close()
            if _qobject_alive(action) and action.isEnabled() and action.isVisible():
                action.trigger()


class LayoutRibbon(QWidget):
    """A self-contained Ribbon, with no QGIS menu or toolbar ownership."""

    def __init__(self, designer, exclusive_callback, parent=None, native_window=None):
        super().__init__(parent)
        self.designer = designer
        self.native_window = native_window
        self._unrepresented_native_bars = set()
        self.setObjectName("QRibbonLayoutWidget")
        self.setMinimumWidth(0)
        # Compact rows, including two-line labels, plus group captions.
        self.setFixedHeight(124)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setStyleSheet(RIBBON_LIGHT_QSS)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        tabs = QTabWidget(self)
        tabs.setObjectName("QRibbonLayoutTabs")
        tabs.setDocumentMode(True)
        tabs.setUsesScrollButtons(True)
        tabs.tabBar().setExpanding(False)
        tabs.tabBar().setDrawBase(False)
        tabs.tabBar().setElideMode(Qt.TextElideMode.ElideNone)
        self.tabs = tabs
        layout.addWidget(tabs)
        self._tab_rows = {}
        self._tab_scrolls = {}
        self._seen_actions = set()
        self._planned = {}
        for name in TAB_NAMES:
            page = QWidget(tabs)
            page.setObjectName("QRibbonLayoutPage")
            frame = QHBoxLayout(page)
            frame.setContentsMargins(1, 0, 1, 0)
            frame.setSpacing(0)
            left = QToolButton(page)
            left.setArrowType(Qt.ArrowType.LeftArrow)
            right = QToolButton(page)
            right.setArrowType(Qt.ArrowType.RightArrow)
            for arrow in (left, right):
                arrow.setFixedWidth(19)
                arrow.setToolTip(tr("Percorrer ferramentas"))
            scroll = QScrollArea(page)
            scroll.setObjectName("QRibbonLayoutScroll")
            scroll.setWidgetResizable(True)
            scroll.setFrameShape(QFrame.Shape.NoFrame)
            scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            scroll.viewport().setObjectName("QRibbonLayoutScrollViewport")
            content = QWidget()
            content.setObjectName("QRibbonLayoutScrollContent")
            row = QHBoxLayout(content)
            row.setContentsMargins(1, 0, 1, 0)
            row.setSpacing(0)
            row.setAlignment(Qt.AlignmentFlag.AlignLeft)
            scroll.setWidget(content)
            left.clicked.connect(lambda _=False, s=scroll: s.horizontalScrollBar().setValue(s.horizontalScrollBar().value()-220))
            right.clicked.connect(lambda _=False, s=scroll: s.horizontalScrollBar().setValue(s.horizontalScrollBar().value()+220))
            def sync_arrows(*_unused, s=scroll, left_button=left, right_button=right):
                sb = s.horizontalScrollBar()
                overflow = sb.maximum() > sb.minimum()
                left_button.setVisible(overflow)
                right_button.setVisible(overflow)
                left_button.setEnabled(overflow and sb.value() > sb.minimum())
                right_button.setEnabled(overflow and sb.value() < sb.maximum())
            scroll.horizontalScrollBar().rangeChanged.connect(sync_arrows)
            scroll.horizontalScrollBar().valueChanged.connect(sync_arrows)
            frame.addWidget(left)
            frame.addWidget(scroll, 1)
            frame.addWidget(right)
            tabs.addTab(page, tr(name))
            self._tab_rows[name] = row
            self._tab_scrolls[name] = scroll
            QTimer.singleShot(0, sync_arrows)
        self._build_native()
        self._build_native_toolbars_and_menus()
        self._build_controls(exclusive_callback)
        self._build_native_menu_fallback()
        self._make_search_corner()
        self._spotlight = LayoutSpotlight(self)
        self._search_shortcut = QShortcut(QKeySequence("Alt+Q"), self.native_window)
        self._search_shortcut.setContext(Qt.ShortcutContext.WindowShortcut)
        self._search_shortcut.activated.connect(self.open_spotlight)
        self._update_search_geometry()
        self.tabs.setCurrentIndex(0)

    def _make_search_corner(self):
        host = QFrame(self)
        host.setObjectName('QRibbonLayoutSearchCorner')
        frame = QHBoxLayout(host)
        frame.setContentsMargins(5, 2, 5, 2)
        frame.setSpacing(3)
        self.search = QLineEdit(host)
        self.search.setObjectName('QRibbonLayoutSearch')
        self.search.setPlaceholderText(tr('Buscar ferramenta...  Alt+Q'))
        self.search.setToolTip(tr('Abrir busca central (Alt+Q)'))
        self.search.setFixedHeight(24)
        self.search.setClearButtonEnabled(True)
        self.search.returnPressed.connect(lambda: self.open_spotlight(self.search.text()))
        from pathlib import Path
        icon = QIcon(str(Path(__file__).resolve().parent / 'resources' / 'search.svg'))
        search_action = self.search.addAction(icon, QLineEdit.ActionPosition.TrailingPosition)
        search_action.triggered.connect(
            lambda _checked=False: self.open_spotlight(self.search.text()))
        frame.addWidget(self.search)
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
        self.search_host.setGeometry(max(0, width - host_width - 5), 0, host_width, 30)
        self.tabs.tabBar().setMaximumWidth(max(100, width - host_width - 14))
        self.search_host.raise_()

    def resizeEvent(self, event):  # noqa: N802
        super().resizeEvent(event)
        self._update_search_geometry()

    def search_actions(self, text, limit=35):
        query = normalized(text)
        if len(query) < 2:
            return []
        matches, seen = [], set()
        actions = [action for group in self._planned.values() for action in group]
        actions.extend(self.native_window.findChildren(QAction))
        for action in actions:
            if (not _qobject_alive(action) or isinstance(action, QWidgetAction)
                    or id(action) in seen or action.isSeparator()
                    or not action.isEnabled() or not action.isVisible()
                    or action.menu() is not None):
                continue
            seen.add(id(action))
            title = _action_label(action)
            if title and query in normalized(title + ' ' + str(action.toolTip() or '')):
                matches.append((title, action))
                if len(matches) >= limit:
                    break
        return matches

    def open_spotlight(self, initial_text=''):
        if _qobject_alive(getattr(self, '_spotlight', None)):
            self._spotlight.open_centered(initial_text)

    def dispose_search(self):
        shortcut = getattr(self, '_search_shortcut', None)
        if _qobject_alive(shortcut):
            shortcut.setEnabled(False)
            shortcut.deleteLater()
        self._search_shortcut = None
        dialog = getattr(self, '_spotlight', None)
        if _qobject_alive(dialog):
            dialog.close()
            dialog.deleteLater()
        self._spotlight = None

    def _get_source(self, source):
        getter = getattr(self.designer, source, None)
        if not callable(getter):
            return None
        try:
            return getter()
        except (AttributeError, RuntimeError, TypeError):
            return None

    def _queue_action(self, action, source, source_title=""):
        """Assign a native action once, based on meaning rather than source order."""
        if (action is None or isinstance(action, QWidgetAction)
                or action.isSeparator() or id(action) in self._seen_actions):
            return False
        title = _action_label(action)
        if not title:
            return False
        tab, group = layout_action_placement(title, source, source_title)
        if tab not in self._tab_rows:
            return False
        key = (tab, group)
        self._planned.setdefault(key, []).append(action)
        self._seen_actions.add(id(action))
        return True

    def _queue_source(self, source, widget, title=""):
        if widget is None:
            return
        try:
            actions = (_menu_actions(widget) if isinstance(widget, QMenu)
                       else widget.actions())
        except (AttributeError, RuntimeError, TypeError):
            return
        for action in actions:
            self._queue_action(action, source, title)

    def _build_native(self):
        # Process semantically important, public sources first. A QAction also
        # present in a native menu will not appear in another Ribbon tab.
        for source in (
            "atlasToolbar", "atlasMenu", "reportMenu",
            "actionsToolbar", "editMenu", "navigationToolbar", "viewMenu",
            "itemsMenu", "layoutToolbar", "layoutMenu", "settingsMenu",
        ):
            self._queue_source(source, self._get_source(source), title_for_source(source))

    def _build_native_toolbars_and_menus(self):
        """Include all native toolbars while retaining non-clonable widgets.

        Embedded QWidgetAction widgets (notably Atlas selectors and page/zoom
        controls) remain native; detaching them would destroy state owned by
        QgsLayoutDesignerInterface. Every ordinary QAction remains eligible
        for the Ribbon, and action identity prevents duplicates.
        """
        window = self.native_window
        if window is None or not _qobject_alive(window):
            return
        for toolbar in window.findChildren(QToolBar):
            if toolbar.parent() is not window or toolbar.objectName() == RIBBON_TOOLBAR_NAME:
                continue
            try:
                actions = toolbar.actions()
                if any(isinstance(action, QWidgetAction) or not _action_label(action)
                       for action in actions if not action.isSeparator()):
                    self._unrepresented_native_bars.add(toolbar)
                title = toolbar.windowTitle() or toolbar.objectName() or tr("Ferramentas")
                for action in actions:
                    self._queue_action(action, toolbar.objectName() or title, title)
            except (AttributeError, TypeError, RuntimeError):
                self._unrepresented_native_bars.add(toolbar)
        native_menu = window.menuBar()
        if native_menu is not None:
            for menu_action in native_menu.actions():
                menu = menu_action.menu()
                if menu is not None:
                    title = menu.title().replace("&", "").strip()
                    self._queue_source(title, menu, title)
        self._render_planned_groups()

    def _append_group(self, tab, group):
        """Place a short, centered divider between complete groups.

        Dividers belong to the horizontal row, rather than stretching from
        the top to the bottom of each group's frame. The first group in a
        tab never receives a leading divider.
        """
        row = self._tab_rows[tab]
        if row.count():
            divider = QFrame(self)
            divider.setObjectName("QRibbonLayoutDivider")
            divider.setFixedSize(1, 76)
            row.addWidget(divider, 0, Qt.AlignmentFlag.AlignVCenter)
        row.addWidget(group)

    def _build_principal_groups(self):
        """Reuse existing native QActions in an ergonomic Main layout tab.

        Contextual tabs keep their complete action lists. Never duplicate or
        change QGIS QAction ownership, text, shortcuts or processing behavior.
        """
        sections = (
            ('Arquivo', (('Layout', 'Arquivo'), ('Layout', 'Projeto de layout'))),
            ('Inserir elementos', (('Inserir', 'Adicionar elementos'),
                                  ('Inserir', 'Elementos'))),
            ('Navegação', (('Exibir', 'Navegação'), ('Exibir', 'Visualização'))),
            ('Editar itens', (('Editar', 'Ferramentas de edição'), ('Editar', 'Edição'))),
            ('Organizar itens', (('Editar', 'Organizar itens'),)),
            ('Atlas', (('Atlas', 'Atlas'), ('Atlas', 'Relatório'))),
            ('Exportar', (('Exportar', 'Impressão e exportação'),)),
        )
        for title, keys in sections:
            items, seen = [], set()
            for key in keys:
                for action in self._planned.get(key, ()):
                    if id(action) not in seen:
                        items.append(action)
                        seen.add(id(action))
            if items:
                leader = _principal_preferred_action(title, items)
                group = _LayoutGroup(title, self, leader=leader)
                first = _principal_first_dropdown_action(title, items)
                if first is not None and first is not leader:
                    items = [first] + [action for action in items if action is not first]
                for action in items:
                    group.add_action(action)
                group.finalize()
                self._append_group('Principal', group)

    def _render_planned_groups(self):
        """Consistent group order independently of QGIS toolbar/menu order."""
        self._build_principal_groups()
        for tab in TAB_NAMES:
            keys = [key for key in self._planned if key[0] == tab]
            preferred = LAYOUT_GROUP_ORDER.get(tab, ())
            keys.sort(key=lambda key: (preferred.index(key[1]) if key[1] in preferred
                                       else len(preferred), key[1]))
            for _tab, group_title in keys:
                group = _LayoutGroup(tr(group_title), self)
                for action in self._planned[(tab, group_title)]:
                    group.add_action(action)
                group.finalize()
                self._append_group(tab, group)

    def _build_controls(self, on_exclusive):
        group = _LayoutGroup("QRibbonSkin", self)
        action = QAction(tr("Barras nativas"), self)
        action.setCheckable(True)
        action.setToolTip(tr("Mostrar ou ocultar as barras e menus originais do Editor de Layout"))
        action.toggled.connect(on_exclusive)
        self.exclusive_action = action
        group.add_action(action)
        group.finalize()
        self._append_group("Interface", group)


    def _build_native_menu_fallback(self):
        """Expose original Layout QMenus while its top menu bar is hidden.

        Native actions and menus keep their original owners. This covers
        QGIS-controlled submenus not independently discovered by the Ribbon.
        """
        bar = self.native_window.menuBar()
        if not _qobject_alive(bar):
            return
        original = QMenu(tr('Menus originais'), self)
        for action in bar.actions():
            if _qobject_alive(action) and not action.isSeparator() and action.menu() is not None:
                original.addAction(action)
        if not original.actions():
            return
        launch = QAction(tr('Menus originais'), self)
        launch.setToolTip(tr('Abrir os menus nativos sem exibir a barra superior'))
        launch.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_TitleBarMenuButton))
        launch.setMenu(original)
        group = _LayoutGroup('Menus do QGIS', self)
        group.add_action(launch)
        group.finalize()
        self._append_group('Interface', group)


class LayoutDesignerSession(QObject):
    """One independent controller per open QgsLayoutDesignerInterface."""

    def __init__(self, designer, parent=None):
        super().__init__(parent)
        self.designer = designer
        self.window = designer.window()
        if not isinstance(self.window, QMainWindow):
            raise TypeError(tr("O Editor de Layout não usa uma QMainWindow Qt"))
        self._original_bars = []
        self._bar_action_snapshots = []
        self._original_menu = None
        self._exclusive = False
        self._disposed = False
        self._chrome = LayoutChrome(self.window)
        # We own only this toolbar and any *new* break inserted before native
        # toolbars. The original QMainWindow toolbar arrangement is untouched.
        self._top_row_anchor = None
        self._added_native_break = False
        self.toolbar = QToolBar(tr("QRibbonSkin — Layout"), self.window)
        self.toolbar.setObjectName(RIBBON_TOOLBAR_NAME)
        self.toolbar.setMovable(False)
        self.toolbar.setFloatable(False)
        self.toolbar.setAllowedAreas(Qt.ToolBarArea.TopToolBarArea)
        self.toolbar.setMinimumWidth(0)
        self.toolbar.setSizePolicy(QSizePolicy.Policy.Expanding,
                                   QSizePolicy.Policy.Fixed)
        self.toolbar.setStyleSheet(RIBBON_TOOLBAR_QSS)
        try:
            self.widget = LayoutRibbon(designer, self.set_exclusive,
                                       native_window=self.window)
            self.toolbar.addWidget(self.widget)
            # QMainWindow.addToolBar() appends to the current row, alongside
            # QGIS's native toolbars. On wide layouts this left the Ribbon
            # squeezed into the right-hand corner. Give it its own TOP row.
            self._install_top_row()
            self.window.installEventFilter(self)
            self._chrome.apply()
            self.toolbar.show()
            # Wait until QGIS has finished constructing the layout window.
            # Restore remains available via the Interface ribbon tab.
            QTimer.singleShot(0, self._activate_if_complete)
        except Exception:
            self.dispose()
            raise

    def _install_top_row(self):
        """Place our Ribbon above the native toolbars, not beside them.

        QMainWindow controls toolbar positioning. We insert the Ribbon before
        the first native top toolbar and introduce a break before that native
        toolbar *only if one was not there already*. Native QWidgetActions,
        Atlas controls, toolbar identities and layout window content stay put.
        """
        top = Qt.ToolBarArea.TopToolBarArea
        candidates = [
            bar for bar in self.window.findChildren(QToolBar)
            if (bar.parent() is self.window and bar is not self.toolbar
                and self.window.toolBarArea(bar) == top)
        ]
        if not candidates:
            self.window.addToolBar(top, self.toolbar)
            return
        # Hidden toolbar geometry may be stale or (0, 0); first choose the
        # earliest visible native toolbar, falling back to creation order.
        visible = [bar for bar in candidates if bar.isVisible()]
        def position(bar):
            geometry = bar.geometry()
            return geometry.y(), geometry.x()
        anchor = min(visible, key=position) if visible else candidates[0]
        self._top_row_anchor = anchor
        existing_break = self.window.toolBarBreak(anchor)
        self.window.insertToolBar(anchor, self.toolbar)
        if not existing_break:
            self.window.insertToolBarBreak(anchor)
            self._added_native_break = True

    def _remove_top_row(self):
        """Remove only the toolbar break installed by this session."""
        anchor = self._top_row_anchor
        if (self._added_native_break and _qobject_alive(self.window)
                and _qobject_alive(anchor)):
            try:
                if self.window.toolBarArea(anchor) == Qt.ToolBarArea.TopToolBarArea:
                    self.window.removeToolBarBreak(anchor)
            except RuntimeError:
                pass
        self._top_row_anchor = None
        self._added_native_break = False

    def _activate_if_complete(self):
        if (self._disposed or not _qobject_alive(self.window)
                or not _qobject_alive(getattr(self, 'widget', None))):
            return
        # Never replace a sparsely populated ribbon. In that case leave
        # all native toolbars visible and provide a diagnostic instead.
        if len(self.widget._seen_actions) >= 8:
            self.set_exclusive(True)

    def _detach_redundant_actions(self, bar):
        """Remove duplicate *presentations* rather than whole native toolbars.

        Ordinary QActions whose identities occur in the Layout Ribbon may be
        detached safely: their owner, signals, checked state and submenu stay
        with QGIS. QWidgetAction objects are never detached or reparented.
        Record the complete action list BEFORE removing anything for rollback.
        """
        original = tuple(bar.actions())
        represented = self.widget._seen_actions
        removable = [action for action in original
                     if (_qobject_alive(action) and not action.isSeparator()
                         and not isinstance(action, QWidgetAction)
                         and id(action) in represented)]
        if removable:
            self._bar_action_snapshots.append((bar, original))
        for action in removable:
            bar.removeAction(action)
        # Native special controls and actions not included in the Ribbon remain
        # accessible. A toolbar with only separators must not occupy a row.
        remaining = [action for action in bar.actions()
                     if (_qobject_alive(action) and not action.isSeparator()
                         and action.isVisible())]
        # If a toolbar only survives because of QWidgetAction-based controls
        # (for example page selectors or native Qt tool buttons added as
        # widgets), it becomes a small orphan strip above the canvas. In the
        # Ribbon-exclusive mode this visual residue is more harmful than
        # useful, so hide the native bar and restore it exactly when the user
        # re-enables the original interface.
        if (not remaining or all(isinstance(action, QWidgetAction)
                                 for action in remaining)):
            bar.hide()

    def _restore_toolbar_actions(self):
        """Reinsert only detached actions in their original relative order.

        Iterate backwards, using the next surviving original action as anchor.
        This survives Qt toolbars being rebuilt, a missing action, and windows
        closed in a different order. No QGIS QAction is re-created or deleted.
        """
        snapshots, self._bar_action_snapshots = self._bar_action_snapshots, []
        for bar, original in snapshots:
            if not _qobject_alive(bar):
                continue
            anchor = None
            for action in reversed(original):
                if not _qobject_alive(action):
                    continue
                try:
                    current = bar.actions()
                    if action not in current:
                        if anchor is not None and anchor in current:
                            bar.insertAction(anchor, action)
                        else:
                            bar.addAction(action)
                    anchor = action
                except (AttributeError, RuntimeError, TypeError):
                    # Continue restoration of other native commands and bars.
                    continue

    def set_exclusive(self, enabled):
        if self._disposed or enabled == self._exclusive:
            return
        if enabled:
            try:
                menu = self.window.menuBar()
                self._original_menu = (menu, menu.isVisible())
                self._original_bars = [
                    (bar, bar.isVisible()) for bar in self.window.findChildren(QToolBar)
                    if bar.parent() is self.window and bar is not self.toolbar
                ]
                self._bar_action_snapshots = []
                for bar, was_visible in self._original_bars:
                    if not was_visible or not _qobject_alive(bar):
                        continue
                    self._detach_redundant_actions(bar)
                menu.hide()
                self._exclusive = True
                self._sync_exclusive_action(True)
            except (AttributeError, RuntimeError, TypeError):
                # A partial failure must never leave native actions detached.
                self._restore_original()
                raise
        else:
            self._restore_original()

    def _restore_original(self):
        # Restore ACTION ORDER before bar visibility to avoid flashing empty
        # toolbars or having QGIS persist a toolbar without its actions.
        if getattr(self, "_bar_action_snapshots", None):
            self._restore_toolbar_actions()
        for bar, was_visible in self._original_bars:
            if _qobject_alive(bar):
                try:
                    bar.setVisible(was_visible)
                except RuntimeError:
                    pass
        self._original_bars = []
        if self._original_menu:
            menu, was_visible = self._original_menu
            if _qobject_alive(menu):
                try:
                    menu.setVisible(was_visible)
                except RuntimeError:
                    pass
        self._original_menu = None
        self._exclusive = False
        self._sync_exclusive_action(False)

    def _sync_exclusive_action(self, enabled):
        widget = getattr(self, "widget", None)
        if widget is None or not _qobject_alive(widget):
            return
        action = widget.exclusive_action
        if _qobject_alive(action) and action.isChecked() != enabled:
            previous = action.blockSignals(True)
            action.setChecked(enabled)
            action.blockSignals(previous)

    def eventFilter(self, obj, event):  # noqa: N802
        if obj is self.window and event.type() == QEvent.Type.Close:
            # Restore visibility AND remove the temporary Ribbon before QGIS
            # persists the window state. A canceled close leaves native UI.
            self.dispose()
        return False

    def dispose(self):
        if self._disposed:
            return
        self._disposed = True
        self._restore_original()
        if _qobject_alive(getattr(self, 'widget', None)):
            self.widget.dispose_search()
        self._chrome.restore()
        if _qobject_alive(self.window):
            try:
                self.window.removeEventFilter(self)
            except RuntimeError:
                pass
        # Undo layout modifications before removing our toolbar, even if a
        # partial initialization or a QGIS window close triggered disposal.
        self._remove_top_row()
        if _qobject_alive(self.window) and _qobject_alive(self.toolbar):
            try:
                self.window.removeToolBar(self.toolbar)
            except RuntimeError:
                pass
        if _qobject_alive(self.toolbar):
            self.toolbar.hide()
            self.toolbar.deleteLater()


class LayoutDesignerManager(QObject):
    """Follow documented QgisInterface layout designer lifecycle signals."""

    def __init__(self, iface, parent=None):
        super().__init__(parent)
        self.iface = iface
        self._sessions = {}
        self._started = False
        self.last_error = None

    def start(self):
        if self._started:
            return
        connected_open = False
        try:
            self.iface.layoutDesignerOpened.connect(self._on_opened)
            connected_open = True
            self.iface.layoutDesignerWillBeClosed.connect(self._on_will_close)
        except (AttributeError, RuntimeError, TypeError):
            if connected_open:
                try:
                    self.iface.layoutDesignerOpened.disconnect(self._on_opened)
                except (RuntimeError, TypeError):
                    pass
            raise
        self._started = True
        for designer in (self.iface.openLayoutDesigners() or []):
            self._on_opened(designer)

    def _on_opened(self, designer):
        if not self._started or not _qobject_alive(designer):
            return
        key = id(designer)
        if key in self._sessions:
            return
        try:
            session = LayoutDesignerSession(designer, self)
        except (AttributeError, TypeError, RuntimeError) as exc:
            # The main QGIS Ribbon must never be disabled because a custom
            # or incompatible layout window lacks Qt's QMainWindow methods.
            self.last_error = tr("Falha na Ribbon do Editor de Layout: {error}").format(error=exc)
            try:
                from qgis.core import QgsMessageLog, Qgis
                QgsMessageLog.logMessage(self.last_error, "QRibbonSkin", Qgis.MessageLevel.Warning)
            except (ImportError, AttributeError, RuntimeError, TypeError):
                pass
            return
        self._sessions[key] = session

    def _on_will_close(self, designer):
        session = self._sessions.pop(id(designer), None)
        if session:
            session.dispose()

    def stop(self):
        if not self._started and not self._sessions:
            return
        self._started = False
        for signal, callback in ((self.iface.layoutDesignerOpened, self._on_opened),
                                 (self.iface.layoutDesignerWillBeClosed, self._on_will_close)):
            try:
                signal.disconnect(callback)
            except (RuntimeError, TypeError):
                pass
        for session in list(self._sessions.values()):
            session.dispose()
        self._sessions.clear()
