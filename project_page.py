"""Non-destructive RustGIS-inspired QGIS Project backstage (QRibbonSkin 0.9.4).

Shows native project actions in a temporary canvas overlay. It does NOT
reparent or replace the QGIS canvas, status bar, dock widgets or map layers.
"""

from pathlib import Path

from .i18n import tr
from qgis.core import QgsProject
from qgis.PyQt.QtCore import Qt, QEvent, QSize
from qgis.PyQt.QtGui import QAction, QIcon
from qgis.PyQt.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QMenu, QPushButton, QScrollArea,
    QSizePolicy, QToolButton, QVBoxLayout, QWidget, QDockWidget,
)


class ProjectDockGuard:
    """Hide native dock panels only while the Project backstage is visible.

    Snapshot the CURRENT dock visibility at entry, rather than the state at
    plugin activation. No positions, dock areas or settings are changed.
    An idempotent restore permits tab switches, plugin shutdown and failures.
    """

    def __init__(self, main_window):
        self._window = main_window
        self._snapshot = None

    def hide(self):
        if self._snapshot is not None:
            return  # Redundant signals must not overwrite the original state.
        docks = []
        try:
            for dock in self._window.findChildren(QDockWidget):
                if dock.parent() is self._window:
                    docks.append((dock, bool(dock.isVisible())))
        except RuntimeError:
            return
        self._snapshot = docks
        for dock, _visible in docks:
            try:
                dock.hide()
            except RuntimeError:
                # A third-party dock can disappear during the transition.
                continue

    def restore(self):
        snapshot = self._snapshot
        self._snapshot = None  # Never replay a stale snapshot twice.
        if snapshot is None:
            return
        for dock, was_visible in snapshot:
            try:
                dock.setVisible(was_visible)
            except RuntimeError:
                continue


class ProjectDashboard(QFrame):
    """Temporary Project landing page overlaid on the QGIS map canvas."""

    def __init__(self, iface):
        self.iface = iface
        self.canvas = iface.mapCanvas()
        super().__init__(self.canvas)
        self.setObjectName('QRibbonSkinProjectDashboard')
        # Use the palette currently supplied by QGIS/Qt, not a hard-coded
        # color accent. palette(...) follows the active widget palette, which
        # may differ between Windows, Linux and the QGIS application theme.
        # The stylesheet only belongs to this temporary dashboard and never
        # changes QApplication or the native QGIS main window palette.
        self.setStyleSheet('''
            QFrame#QRibbonSkinProjectDashboard { background: palette(base); }
            QFrame#QRibbonSkinProjectSidebar {
                background: palette(window); border-right: 1px solid palette(midlight);
            }
            QLabel#QRibbonSkinProjectSidebarTitle {
                color: palette(window-text); font-size: 12pt; font-weight: 600;
            }
            QToolButton#QRibbonSkinProjectNav {
                color: palette(window-text); text-align: left; border: 0;
                padding: 7px 12px; background: transparent;
            }
            QToolButton#QRibbonSkinProjectNav:hover { background: palette(alternate-base); }
            QPushButton#QRibbonSkinProjectBack {
                color: palette(window-text); background: transparent; border: 0;
                text-align: left; font-size: 12pt; padding: 8px 12px;
            }
            QPushButton#QRibbonSkinProjectBack:hover { background: palette(alternate-base); }
            QScrollArea#QRibbonSkinProjectScroll, QWidget#QRibbonSkinProjectContent {
                background: palette(base); border: 0;
            }
            QLabel#QRibbonSkinProjectTitle {
                font-size: 19pt; color: palette(text); font-weight: 600;
            }
            QLabel#QRibbonSkinProjectSubtitle, QLabel#QRibbonSkinProjectValue {
                color: palette(text);
            }
            QLabel#QRibbonSkinProjectSection {
                color: palette(text); font-size: 11pt; font-weight: 600;
            }
            QToolButton#QRibbonSkinProjectCard {
                background: palette(alternate-base);
                border: 1px solid palette(midlight); color: palette(text);
                border-radius: 7px; padding: 8px; text-align: center;
            }
            QToolButton#QRibbonSkinProjectCard:hover {
                border-color: palette(highlight); background: palette(window);
            }
        ''')
        self._on_close = None
        self._disposed = False
        self._recent_menu_signal = None
        self._dock_guard = ProjectDockGuard(iface.mainWindow())
        self._action_lookup = self._native_actions()
        self._make_ui()
        self.canvas.installEventFilter(self)
        self.resize(self.canvas.size())
        self.hide()

    def set_on_close(self, callback):
        self._on_close = callback

    def _native_actions(self):
        """Resolve native commands without creating duplicate processing code."""
        lookup = {}
        methods = {
            'new': ('actionNewProject', ('novo projeto', 'new project', 'novo')),
            'open': ('actionOpenProject', ('abrir', 'open project', 'open')),
            'save': ('actionSaveProject', ('salvar', 'save project', 'save')),
            'save_as': ('actionSaveProjectAs', ('salvar como', 'save as')),
            'about': ('actionAbout', ('sobre', 'about')),
        }
        for key, (getter, phrases) in methods.items():
            method = getattr(self.iface, getter, None)
            if callable(method):
                try:
                    action = method()
                    if isinstance(action, QAction):
                        lookup[key] = action
                        continue
                except (RuntimeError, TypeError, AttributeError):
                    pass
            menu_getter = getattr(self.iface,
                                  'helpMenu' if key == 'about' else 'projectMenu',
                                  None)
            menu = menu_getter() if callable(menu_getter) else None
            if menu is not None:
                for action in menu.actions():
                    title = action.text().replace('&', '').strip().lower()
                    if action.menu() is None and any(title.startswith(q) for q in phrases):
                        lookup[key] = action
                        break
        project_menu = self.iface.projectMenu()
        for action in project_menu.actions():
            text = action.text().replace('&', '').strip().casefold()
            if action.menu() is not None and ('recent' in text or 'recente' in text):
                lookup['recent'] = action
                break
        return lookup

    def _make_ui(self):
        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        sidebar = QFrame(self)
        sidebar.setObjectName('QRibbonSkinProjectSidebar')
        sidebar.setFixedWidth(194)
        side = QVBoxLayout(sidebar)
        side.setContentsMargins(0, 12, 0, 10)
        side.setSpacing(2)
        back = QPushButton(tr('←   Voltar ao mapa'), sidebar)
        back.setObjectName('QRibbonSkinProjectBack')
        back.clicked.connect(self._close)
        side.addWidget(back)
        title = QLabel(tr('Projeto'), sidebar)
        title.setObjectName('QRibbonSkinProjectSidebarTitle')
        title.setContentsMargins(15, 12, 0, 6)
        side.addWidget(title)
        for key, caption in (('new', 'Novo'), ('open', 'Abrir'),
                             ('save', 'Salvar'), ('save_as', 'Salvar como')):
            action = self._action_lookup.get(key)
            if action is None:
                continue
            button = QToolButton(sidebar)
            button.setObjectName('QRibbonSkinProjectNav')
            button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
            button.setDefaultAction(action)
            button.setText(tr(caption))
            button.setMinimumHeight(37)
            button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            side.addWidget(button)
        side.addStretch(1)
        about_action = self._action_lookup.get('about')
        if about_action is not None:
            about_button = QToolButton(sidebar)
            about_button.setObjectName('QRibbonSkinProjectNav')
            about_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
            about_button.setDefaultAction(about_action)
            about_button.setText(tr('Sobre o QGIS'))
            about_button.setMinimumHeight(37)
            side.addWidget(about_button)
        outer.addWidget(sidebar)

        scrolling = QScrollArea(self)
        scrolling.setObjectName('QRibbonSkinProjectScroll')
        scrolling.setFrameShape(QFrame.Shape.NoFrame)
        scrolling.setWidgetResizable(True)
        scrolling.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        panel = QWidget(scrolling)
        panel.setObjectName('QRibbonSkinProjectContent')
        body = QVBoxLayout(panel)
        body.setContentsMargins(26, 22, 25, 20)
        body.setSpacing(14)
        heading = QLabel(tr('Bem-vindo ao QGIS'), panel)
        heading.setObjectName('QRibbonSkinProjectTitle')
        body.addWidget(heading)
        subtitle = QLabel(tr('Crie um projeto, abra um arquivo existente ou continue seu trabalho.'), panel)
        subtitle.setObjectName('QRibbonSkinProjectSubtitle')
        subtitle.setWordWrap(True)
        body.addWidget(subtitle)
        section = QLabel(tr('Projetos'), panel)
        section.setObjectName('QRibbonSkinProjectSection')
        body.addWidget(section)

        cards = QHBoxLayout()
        cards.setSpacing(12)
        for key, caption in (('new', 'Novo mapa'), ('open', 'Abrir projeto'),
                             ('recent', 'Projetos recentes')):
            action = self._action_lookup.get(key)
            button = QToolButton(panel)
            button.setObjectName('QRibbonSkinProjectCard')
            button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
            button.setIconSize(QSize(42, 42))
            button.setText(tr(caption))
            button.setToolTip(tr(caption))
            # Compact card, comparable to RustGIS: never stretch all three
            # cards across the width of a maximized QGIS window.
            button.setFixedSize(205, 142)
            button.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
            if key in ('new', 'open') and action is not None:
                button.clicked.connect(self._close)
            if key == 'recent' and action is not None and action.menu() is not None:
                button.setIcon(action.icon())
                button.setMenu(action.menu())
                button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
                # QGIS owns the native recent-project menu. Never attach an
                # anonymous callback which outlives this Project dashboard.
                menu = action.menu()
                menu.triggered.connect(self._recent_project_triggered)
                self._recent_menu_signal = menu
            elif action is not None:
                button.setDefaultAction(action)
                button.setText(tr(caption))
            else:
                button.setEnabled(False)
                button.setToolTip(tr('Comando não disponível nesta instalação do QGIS'))
            cards.addWidget(button)
        cards.addStretch(1)  # Align the compact cards to the left.
        body.addLayout(cards)

        info = QLabel(tr('Projeto atual'), panel)
        info.setObjectName('QRibbonSkinProjectSection')
        body.addWidget(info)
        self.project_info = QLabel('', panel)
        self.project_info.setObjectName('QRibbonSkinProjectValue')
        self.project_info.setWordWrap(True)
        self.project_info.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        body.addWidget(self.project_info)
        body.addStretch(1)
        scrolling.setWidget(panel)
        outer.addWidget(scrolling, 1)

    def _recent_project_triggered(self, _action):
        if not self._disposed:
            self._close()

    def _close(self):
        if self._disposed:
            return
        callback = self._on_close
        if callback is not None:
            try:
                callback()
                return
            except RuntimeError:
                # Qt may already have deleted the C++ QTabWidget while QGIS
                # delivers a queued signal from its long-lived project menu.
                pass
        try:
            self.set_active(False)  # Restore the map and native dock panels.
        except RuntimeError:
            # Even the dashboard wrapper may already be scheduled for Qt
            # deletion: release our independent visibility snapshot anyway.
            self._dock_guard.restore()

    def _refresh_project_info(self):
        project = QgsProject.instance()
        path = project.fileName() or tr('Ainda não salvo')
        title = project.title() or Path(project.fileName()).stem or tr('Projeto sem título')
        self.project_info.setText(
            tr('Nome: {name}\nLocalização: {location}\nCamadas: {layers}').format(name=title, location=path, layers=len(project.mapLayers()))
        )

    def set_active(self, enabled):
        if self._disposed:
            return
        if enabled:
            # With docks hidden QGIS expands the central canvas. The overlay
            # is resized afterwards to occupy that whole available area.
            self._dock_guard.hide()
            self.resize(self.canvas.size())
            self._refresh_project_info()
            self.show()
            self.raise_()
        else:
            self.hide()
            self._dock_guard.restore()

    def eventFilter(self, watched, event):  # noqa: N802
        if watched is self.canvas and event.type() == QEvent.Type.Resize:
            self.resize(self.canvas.size())
        return super().eventFilter(watched, event)

    def dispose(self, *_args):
        if self._disposed:
            return
        self._disposed = True
        self._on_close = None
        menu = self._recent_menu_signal
        self._recent_menu_signal = None
        if menu is not None:
            try:
                menu.triggered.disconnect(self._recent_project_triggered)
            except (TypeError, RuntimeError):
                pass
        # An unload or Qt deferred deletion while on the Project tab must
        # NEVER leave the QGIS panels hidden in the classic interface.
        self._dock_guard.restore()
        try:
            self.canvas.removeEventFilter(self)
            self.hide()
            self.deleteLater()
        except RuntimeError:
            pass
