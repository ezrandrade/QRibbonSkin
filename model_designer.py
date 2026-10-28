"""Reversible Ribbon for the native QGIS 4.x Processing Model Designer.

The model, its graphics view, docks, and Processing algorithms remain QGIS-owned.
Only existing QAction presentations are reused. No editable model data is changed.
The original chrome is restored when the window closes or the plugin unloads.
"""

from pathlib import Path

from qgis.PyQt import sip
from qgis.PyQt.QtCore import QObject, Qt, QEvent, QTimer
from qgis.PyQt.QtGui import QAction, QIcon, QKeySequence, QShortcut
from qgis.PyQt.QtWidgets import (
    QApplication, QMainWindow, QWidget, QFrame, QHBoxLayout, QVBoxLayout,
    QTabWidget, QScrollArea, QToolButton, QToolBar, QLineEdit, QMenu,
    QWidgetAction, QDockWidget, QSizePolicy,
)

from .i18n import tr, ui_label
from .georeferencer import (
    _CommandGroup, GeoreferencerSpotlight, GeoreferencerRibbon, _alive,
)

BAR_NAME = 'QRibbonSkinModelDesignerToolbar'
# These object names are declared by the native QGIS Model Designer UI.
# Never guess actions by similar translated labels when choosing a leader.
GROUPS = {
    'Arquivo': ('mActionNew', 'mActionOpen', 'mActionSave',
                'mActionSaveAs', 'mActionSaveInProject', 'mActionClose'),
    'Navegação': ('mActionZoomToItems', 'mActionPan', 'mActionZoomIn',
                  'mActionZoomOut', 'mActionZoomActual'),
    'Editar Itens': ('mActionSelectMoveItem', 'mActionSelectAll',
                     'mActionDeleteComponents', 'mActionAddGroupBox'),
    'Organizar': ('mActionReorderInputs', 'mActionReorderOutputs',
                  'mActionSnapSelected'),
    'Execução': ('mActionRun', 'mActionRunSelectedSteps', 'mActionValidate'),
    'Exportar': ('mActionExportImage', 'mActionExportPdf',
                 'mActionExportSvg', 'mActionExportPython',
                 'mActionExportAsScriptAlgorithm'),
    'Visualização': ('mActionShowComments', 'mActionShowFeatureCount',
                     'mActionSnappingEnabled', 'mActionHidePanels'),
    'Ajuda': ('mActionEditHelp',),
}

# Presentation-only labels for Model Designer export commands. Keep the
# original QGIS-owned QAction texts, object names and shortcuts unchanged.
_EXPORT_DISPLAY_TITLES = {
    'mActionExportImage': 'Exportar Imagem',
    'mActionExportPdf': 'Exportar PDF',
    'mActionExportSvg': 'Exportar SVG',
    'mActionExportPython': 'Exportar Python',
    'mActionExportAsScriptAlgorithm': 'Exportar Algoritmo Script',
}


def _export_display_title(action):
    """Return an alias for a native export action, without mutating it."""
    return ui_label(_EXPORT_DISPLAY_TITLES[action.objectName()]) if action.objectName() in _EXPORT_DISPLAY_TITLES else None

# The Model Designer intentionally uses only two tabs. All operational
# groups stay on Principal; original QGIS menus and visibility controls
# remain under Interface for reversible access to the classic window.
TABS = ('Principal', 'Interface')
MAIN_GROUPS = (
    'Arquivo', 'Navegação', 'Editar Itens', 'Organizar',
    'Visualização', 'Execução', 'Exportar',
)


def is_model_designer(window):
    """Use the native Qt class hierarchy; never match a translated title."""
    if not isinstance(window, QMainWindow) or not _alive(window):
        return False
    try:
        return bool(window.inherits('QgsModelDesignerDialog'))
    except (RuntimeError, AttributeError, TypeError):
        return False


class ModelDesignerRibbon(QWidget):
    """Compact Ribbon matching the homologated Georeferencer/print Layout."""

    # Reuse the exact same colors, fonts and tab backgrounds as Georeferencer.
    QSS = GeoreferencerRibbon.QSS + '''
    QWidget#QRibbonModelDesignerWidget { background-color: #f7f9fc; color: #24364a; }
    QFrame#QRibbonModelSearchCorner { background: transparent; border: 0; }
    QLineEdit#QRibbonModelSearch { background: #fff; color: #24364a;
        border: 1px solid #c3d0df; border-radius: 5px;
        padding: 1px 7px; font-size: 9pt; }
    QLineEdit#QRibbonModelSearch:focus { border: 1px solid #245fba; }
    '''

    def __init__(self, window, on_toggle, parent=None):
        super().__init__(parent)
        self.window = window
        self.setObjectName('QRibbonModelDesignerWidget')
        self.setMinimumWidth(0)
        self.setFixedHeight(124)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setStyleSheet(self.QSS)
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        self.tabs = QTabWidget(self)
        self.tabs.setObjectName('QRibbonGeorefTabs')
        self.tabs.setDocumentMode(True)
        self.tabs.setUsesScrollButtons(True)
        self.tabs.tabBar().setExpanding(False)
        self.tabs.tabBar().setDrawBase(False)
        self.tabs.tabBar().setElideMode(Qt.TextElideMode.ElideNone)
        root.addWidget(self.tabs)
        self.rows = {}
        self.actions_by_name = {}
        self._all_actions = []
        self._represented = set()
        self._native_menus_available = False

        for name in TABS:
            page = QWidget(self.tabs)
            page.setObjectName('QRibbonGeorefPage')
            line = QHBoxLayout(page)
            line.setContentsMargins(1, 0, 1, 0)
            line.setSpacing(0)
            left, right = QToolButton(page), QToolButton(page)
            left.setArrowType(Qt.ArrowType.LeftArrow)
            right.setArrowType(Qt.ArrowType.RightArrow)
            for button in (left, right):
                button.setFixedWidth(20)
                button.setToolTip(tr('Percorrer grupos de ferramentas'))
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

            def sync(*_args, s=scroll, lb=left, rb=right):
                sb = s.horizontalScrollBar()
                overflow = sb.maximum() > sb.minimum()
                lb.setVisible(overflow)
                rb.setVisible(overflow)
                lb.setEnabled(overflow and sb.value() > sb.minimum())
                rb.setEnabled(overflow and sb.value() < sb.maximum())
            scroll.horizontalScrollBar().rangeChanged.connect(sync)
            scroll.horizontalScrollBar().valueChanged.connect(sync)
            line.addWidget(left)
            line.addWidget(scroll, 1)
            line.addWidget(right)
            self.tabs.addTab(page, tr(name))
            self.rows[name] = row
            QTimer.singleShot(0, sync)

        self._discover_actions()
        self._build_tabs()
        self.native_action = QAction(tr('Exibir menus e barras originais'), self)
        self.native_action.setCheckable(True)
        self.native_action.toggled.connect(on_toggle)
        # Native chrome controls belong only on Interface, not in the
        # workflow-oriented Principal tab.
        self._add_group('Interface', 'Controles', (self.native_action,))
        self._make_native_menu_fallback()
        self._create_search()
        self._spotlight = GeoreferencerSpotlight(self)
        self._shortcut = QShortcut(QKeySequence('Alt+Q'), window)
        self._shortcut.setContext(Qt.ShortcutContext.WindowShortcut)
        self._shortcut.activated.connect(self.open_spotlight)
        self._place_search()

    def _discover_actions(self):
        # Native QActions are shared, never cloned or renamed globally.
        toggle_actions = set()
        for kind in (QToolBar, QDockWidget):
            for widget in self.window.findChildren(kind):
                if widget.parent() is self.window:
                    toggle_actions.add(widget.toggleViewAction())
        for action in self.window.findChildren(QAction):
            if not _alive(action) or action.isSeparator() or isinstance(action, QWidgetAction):
                continue
            if action in toggle_actions:
                continue
            name = action.objectName()
            if not name or not name.startswith('mAction'):
                continue
            if action not in self._all_actions:
                self._all_actions.append(action)
                self.actions_by_name.setdefault(name, action)
        # Export as script may live in a QToolButton inserted as a QWidgetAction.
        for bar in self.window.findChildren(QToolBar):
            if bar.parent() is not self.window:
                continue
            for action in bar.actions():
                if not isinstance(action, QWidgetAction):
                    continue
                widget = bar.widgetForAction(action)
                if _alive(widget) and isinstance(widget, QToolButton):
                    candidates = list(widget.actions())
                    default = widget.defaultAction()
                    if _alive(default):
                        candidates.append(default)
                    for child in candidates:
                        if (_alive(child) and not isinstance(child, QWidgetAction)
                                and child.objectName().startswith('mAction')
                                and child not in self._all_actions):
                            self._all_actions.append(child)
                            self.actions_by_name.setdefault(child.objectName(), child)

    def _add_group(self, tab, caption, items):
        actions = [item for item in items if _alive(item)]
        if not actions:
            return
        group = _CommandGroup(
            caption, actions, self.tabs,
            local_titles=_export_display_title if caption == 'Exportar' else None,
        )
        self.rows[tab].addWidget(group)
        self._represented.update(id(action) for action in actions)

    def _build_tabs(self):
        # The Principal tab is the single operational entry point. Group
        # ordering follows the normal model-building workflow. No QAction
        # is cloned, reparented or renamed globally.
        grouped_names = {name for names in GROUPS.values() for name in names}
        extras = [action for action in self._all_actions
                  if action.objectName() not in grouped_names]
        for name in MAIN_GROUPS:
            self._add_group('Principal', name, self._named_actions(name))
        if extras:
            self._add_group('Principal', 'Outras ferramentas', extras)
        self._add_group('Principal', 'Ajuda', self._named_actions('Ajuda'))

    def _named_actions(self, group):
        return [self.actions_by_name[name] for name in GROUPS[group]
                if name in self.actions_by_name]

    def _make_native_menu_fallback(self):
        # Original QGIS menus belong to Interface. Their QAction objects
        # remain owned and managed by the native Model Designer window.
        original = self.window.menuBar()
        if not _alive(original):
            return
        native_submenus = [item.menu() for item in original.actions()
                           if _alive(item.menu())]
        if not native_submenus:
            return
        from qgis.PyQt.QtWidgets import QLabel
        for tab in ('Interface',):
            menu = QMenu(self)
            for submenu in native_submenus:
                if _alive(submenu):
                    menu.addAction(submenu.menuAction())
            if not menu.actions():
                continue
            button = QToolButton(self)
            button.setIcon(QIcon(str(Path(__file__).resolve().parent / 'resources/icons/interface/original_menus.svg')))
            button.setToolTip(tr('Abrir os menus nativos sem exibir a barra superior'))
            button.setText(tr('Menus originais'))
            button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
            button.setIconSize(self._icon_size())
            button.setFixedHeight(72)
            button.setMinimumWidth(94)
            button.setMenu(menu)
            button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
            group = QFrame(self)
            group.setObjectName('QRibbonGeorefGroup')
            stack = QVBoxLayout(group)
            stack.setContentsMargins(8, 3, 10, 1)
            stack.setSpacing(1)
            stack.addWidget(button, 1, Qt.AlignmentFlag.AlignHCenter)
            label = QLabel(tr('Menus originais'), group)
            label.setObjectName('QRibbonGeorefGroupLabel')
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label.setFixedHeight(19)
            stack.addWidget(label)
            self.rows[tab].addWidget(group)
            self._native_menus_available = True

    @staticmethod
    def _icon_size():
        from qgis.PyQt.QtCore import QSize
        return QSize(25, 25)

    def _create_search(self):
        host = QFrame(self)
        host.setObjectName('QRibbonModelSearchCorner')
        layout = QHBoxLayout(host)
        layout.setContentsMargins(5, 2, 5, 2)
        self.search = QLineEdit(host)
        self.search.setObjectName('QRibbonModelSearch')
        self.search.setPlaceholderText(tr('Buscar ferramenta...  Alt+Q'))
        self.search.setFixedHeight(24)
        self.search.setClearButtonEnabled(True)
        self.search.returnPressed.connect(lambda: self.open_spotlight(self.search.text()))
        icon = QIcon(str(Path(__file__).resolve().parent / 'resources/search.svg'))
        action = self.search.addAction(icon, QLineEdit.ActionPosition.TrailingPosition)
        action.triggered.connect(lambda _checked=False: self.open_spotlight(self.search.text()))
        layout.addWidget(self.search)
        self.search_host = host
        host.raise_()

    def _place_search(self):
        if self.width() < 100:
            return
        width = self.width()
        search_width = 168 if width < 850 else (210 if width < 1240 else 260)
        host_width = search_width + 12
        self.search.setFixedWidth(search_width)
        self.search_host.setGeometry(max(0, width - host_width - 5), 0, host_width, 30)
        self.tabs.tabBar().setMaximumWidth(max(100, width - host_width - 14))
        self.search_host.raise_()

    def resizeEvent(self, event):  # noqa: N802
        super().resizeEvent(event)
        self._place_search()

    def search_actions(self, text, limit=35):
        query = str(text or '').casefold().strip()
        matches = []
        for action in self._all_actions:
            if not _alive(action) or not action.isEnabled() or not action.isVisible():
                continue
            caption = str(action.text() or action.toolTip() or action.objectName()).replace('&', '')
            haystack = ' '.join((caption, action.toolTip(), action.objectName())).casefold()
            if query and query not in haystack:
                continue
            matches.append((caption, action))
        return matches[:limit]

    def open_spotlight(self, initial_text=''):
        if _alive(self._spotlight):
            self._spotlight.open_centered(initial_text)

    def dispose_search(self):
        if _alive(getattr(self, '_shortcut', None)):
            self._shortcut.setEnabled(False)
            self._shortcut.deleteLater()
        if _alive(getattr(self, '_spotlight', None)):
            self._spotlight.close()
            self._spotlight.deleteLater()


class ModelDesignerSession(QObject):
    """One model window; reversible toolbar visibility, no model state edits."""

    def __init__(self, window, parent=None):
        super().__init__(parent)
        self.window = window
        self._disposed = False
        self._exclusive = False
        self._saved_bars = []
        self._saved_menu = None
        self._native_hide_scheduled = False
        self._anchor = None
        self._break_inserted = False
        self.toolbar = QToolBar(tr('QRibbonSkin — Designer de Modelos'), window)
        self.toolbar.setObjectName(BAR_NAME)
        self.toolbar.setMovable(False)
        self.toolbar.setFloatable(False)
        self.toolbar.setAllowedAreas(Qt.ToolBarArea.TopToolBarArea)
        self.toolbar.setMinimumWidth(0)
        self.toolbar.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.toolbar.setStyleSheet('QToolBar#' + BAR_NAME +
                                   ' { background: #f7f9fc; border: 0; spacing: 0; }')
        try:
            self.ribbon = ModelDesignerRibbon(window, self.set_native_visible, self.toolbar)
            self.toolbar.addWidget(self.ribbon)
            self._install_top_row()
            window.installEventFilter(self)
            self.toolbar.show()
            self.set_native_visible(False)
            # QGIS may finish showing native toolbars after its parent window
            # receives the first Show event. Recheck on the next Qt turn.
            self._schedule_native_hide()
        except Exception:
            self.dispose()
            raise

    def _install_top_row(self):
        top = Qt.ToolBarArea.TopToolBarArea
        bars = [bar for bar in self.window.findChildren(QToolBar)
                if bar.parent() is self.window and bar is not self.toolbar
                and self.window.toolBarArea(bar) == top]
        if not bars:
            self.window.addToolBar(top, self.toolbar)
            return
        visible = [bar for bar in bars if bar.isVisible()]
        anchor = min(visible, key=lambda bar: (bar.geometry().y(), bar.geometry().x())) if visible else bars[0]
        self._anchor = anchor
        had_break = self.window.toolBarBreak(anchor)
        self.window.insertToolBar(anchor, self.toolbar)
        if not had_break:
            self.window.insertToolBarBreak(anchor)
            self._break_inserted = True

    def _native_toolbars(self):
        """Return native top-level toolbars without touching nested widgets."""
        if not _alive(self.window):
            return []
        return [bar for bar in self.window.findChildren(QToolBar)
                if (_alive(bar) and bar.parent() is self.window
                    and bar is not self.toolbar)]

    def _hide_native_bars(self):
        """Hide QGIS chrome as a unit; leave every QAction/widget untouched.

        The previous implementation required *all* toolbar actions to appear
        in the Ribbon. Model Designer has extra and QWidgetAction commands,
        so its standard toolbar stayed visible directly beneath the Ribbon.
        Hiding the parent QToolBar (rather than removing any QActions) avoids
        duplicates and allows a lossless visibility restoration on exit.
        """
        if self._disposed or not self._exclusive or not _alive(self.window):
            return
        for bar in self._native_toolbars():
            if not any(old is bar for old, _visible in self._saved_bars):
                # Include bars dynamically added after the Model Designer
                # first opens. Save their initial visibility exactly once.
                self._saved_bars.append((bar, bar.isVisible()))
                bar.installEventFilter(self)
            if bar.isVisible():
                bar.hide()

    def _schedule_native_hide(self):
        if (self._disposed or not self._exclusive
                or self._native_hide_scheduled):
            return
        self._native_hide_scheduled = True
        QTimer.singleShot(0, self._deferred_native_hide)

    def _deferred_native_hide(self):
        self._native_hide_scheduled = False
        self._hide_native_bars()

    def set_native_visible(self, visible):
        if self._disposed:
            return
        if not visible and not self._exclusive:
            bar = self.window.menuBar()
            if self.ribbon._native_menus_available and _alive(bar):
                self._saved_menu = (bar, bar.isVisible())
                bar.hide()
            self._saved_bars = []
            self._exclusive = True
            self._hide_native_bars()
            self._schedule_native_hide()
        elif visible and self._exclusive:
            self._restore_native()

    def _restore_native(self):
        # Disable interception before Qt sends Show events while restoring.
        self._exclusive = False
        saved, self._saved_bars = self._saved_bars, []
        for bar, originally_visible in saved:
            if _alive(bar):
                bar.removeEventFilter(self)
                bar.setVisible(originally_visible)
        if self._saved_menu:
            bar, was_visible = self._saved_menu
            if _alive(bar):
                bar.setVisible(was_visible)
        self._saved_menu = None

    def eventFilter(self, watched, event):  # noqa: N802
        if watched is self.window:
            if event.type() == QEvent.Type.Close:
                self.dispose()
            elif event.type() == QEvent.Type.ChildAdded and self._exclusive:
                # Third-party tools or QGIS may add toolbars after opening.
                self._schedule_native_hide()
        elif (self._exclusive and _alive(watched)
              and isinstance(watched, QToolBar)
              and event.type() == QEvent.Type.Show):
            # Native actions may re-show their toolbar. Keep the Ribbon-only
            # presentation, unless the user enabled the original interface.
            self._schedule_native_hide()
        return False

    def dispose(self):
        if self._disposed:
            return
        self._disposed = True
        ribbon = getattr(self, 'ribbon', None)
        if _alive(ribbon):
            ribbon.dispose_search()
        self._restore_native()
        if _alive(self.window):
            self.window.removeEventFilter(self)
            if self._break_inserted and _alive(self._anchor):
                self.window.removeToolBarBreak(self._anchor)
            if _alive(self.toolbar):
                self.window.removeToolBar(self.toolbar)
        if _alive(self.toolbar):
            self.toolbar.hide()
            self.toolbar.deleteLater()


class ModelDesignerManager(QObject):
    """Watch QGIS' native Processing Model Designer dialog Show events."""

    def __init__(self, iface, parent=None):
        super().__init__(parent)
        self.iface = iface
        self._active = False
        self._sessions = {}
        self._scheduled = False
        self.last_error = None

    def start(self):
        if self._active:
            return
        app = QApplication.instance()
        if app is None:
            return
        self._active = True
        app.installEventFilter(self)
        self._scan()

    def _schedule(self):
        if self._active and not self._scheduled:
            self._scheduled = True
            QTimer.singleShot(0, self._scan)

    def _scan(self):
        self._scheduled = False
        if not self._active:
            return
        app = QApplication.instance()
        if app is None:
            return
        for window in app.topLevelWidgets():
            if not is_model_designer(window):
                continue
            try:
                if not window.isVisible():
                    continue
                key = id(window)
                previous = self._sessions.get(key)
                if previous is not None and not previous._disposed:
                    continue
                # QGIS may still be constructing the dialog at Show time.
                if not window.findChildren(QAction) or not window.findChildren(QToolBar):
                    continue
                self._sessions[key] = ModelDesignerSession(window, self)
            except (RuntimeError, AttributeError, TypeError, ValueError) as exc:
                self.last_error = str(exc)
                from qgis.core import QgsMessageLog, Qgis
                QgsMessageLog.logMessage(
                    'Model Designer Ribbon: ' + self.last_error,
                    'QRibbonSkin', Qgis.MessageLevel.Warning)

    def eventFilter(self, watched, event):  # noqa: N802
        if self._active and event.type() == QEvent.Type.Show and isinstance(watched, QMainWindow):
            if is_model_designer(watched):
                self._schedule()
        return False

    def stop(self):
        self._active = False
        app = QApplication.instance()
        if app is not None:
            app.removeEventFilter(self)
        for session in list(self._sessions.values()):
            session.dispose()
        self._sessions.clear()
