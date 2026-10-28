"""QRibbonSkin plugin entry point.

Modified/new implementation inspired by ArcSkin's reversible-UI architecture.
QRibbonSkin project, 2026-10-23. GPL-2.0.

The plugin changes only QMainWindow menu and toolbar presentation, and saves
its own activation preference and a crash-recovery visibility snapshot under
qribbonskin/* in QgsSettings. No project, map, renderer or Processing changes.
"""

from pathlib import Path
import json
import unicodedata

from qgis.core import QgsSettings, QgsMessageLog, Qgis

from qgis.PyQt.QtCore import Qt, QEvent, QObject, QTimer
from qgis.PyQt.QtGui import QAction, QIcon, QKeySequence, QShortcut
from qgis.PyQt.QtWidgets import QApplication, QToolBar, QDockWidget

from .i18n import configure_language, tr
from .ribbon import RibbonWidget
from .panel_style import PanelLightTheme
from .layout_designer import LayoutDesignerManager
from .georeferencer import GeoreferencerManager
from .model_designer import ModelDesignerManager


ROOT = Path(__file__).resolve().parent
PLUGIN_MENU = "&QRibbonSkin"  # Emergency fallback on unsupported QGIS builds.
RECOVERY_SHORTCUT = "Ctrl+Alt+Shift+R"
PREFERENCE_KEY = "qribbonskin/activate_at_startup"
RECOVERY_KEY = "qribbonskin/hidden_native_ui_snapshot_v1"
LAST_GOOD_TOOLBARS_KEY = "qribbonskin/last_good_native_toolbar_visibility_v1"
# Only QGIS-owned essentials. Never turn on all third-party/plugin toolbars.
CORE_TOOLBAR_ACCESSORS = ("fileToolBar", "mapNavToolToolBar", "layerToolBar",
                          "attributesToolBar", "digitizeToolBar")


def setting_is_true(value):
    """Interpret boolean values even with older QVariant/QSettings backends."""
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in ("1", "true", "yes", "on")


def normalized_caption(caption):
    """Normalize translated menu labels and strip Qt keyboard mnemonics."""
    caption = unicodedata.normalize("NFKD", caption.replace("&", "").casefold())
    return "".join(ch for ch in caption if not unicodedata.combining(ch)).strip()


def view_menu_insertion_point(actions):
    """Place the switch after the last Panels / Toolbars entry (or append)."""
    markers = ("paineis", "panels", "barras de ferramentas", "toolbars",
               "barra de ferramentas", "toolbar")
    indexes = [i for i, action in enumerate(actions)
               if any(marker in normalized_caption(action.text()) for marker in markers)]
    return (max(indexes) + 1) if indexes else len(actions)


class QRibbonSkinPlugin(QObject):
    """Reversible ribbon with a persistent startup preference and recovery."""

    def __init__(self, iface):
        super().__init__(iface.mainWindow())
        self.iface = iface
        configure_language()
        self._settings = QgsSettings()
        self._window = iface.mainWindow()
        self._closing = False
        self._unloaded = False
        self._startup_completed = False
        self._startup_timer_pending = False
        self._initialization_reported = False
        self._connected_startup = False
        self._quit_connected = False
        self._switch = None
        self._recover_toolbars_action = None
        self._restore_epoch = 0
        self._ribbon_bar = None
        self._toolbar_visibility = []
        self._toolbar_monitor = QTimer(self)
        self._toolbar_monitor.setInterval(1200)
        self._toolbar_monitor.timeout.connect(self._sync_native_toolbars)
        self._dock_visibility = []
        self._focus_map = False
        self._is_active = False
        self._changing = False
        self._previous_menu_bar_visibility = None
        self._native_menu_bar = None
        self._view_menu = None
        self._shortcut = None
        self._legacy_plugin_menu = False
        self._panel_light_theme = PanelLightTheme(iface)
        self._layout_manager = LayoutDesignerManager(iface, self)
        self._georeferencer_manager = GeoreferencerManager(iface, self)
        self._model_designer_manager = ModelDesignerManager(iface, self)

    def initGui(self):  # noqa: N802
        win = self.iface.mainWindow()
        icon = QIcon(str(ROOT / "resources" / "qribbonskin_toolbar.svg"))
        self._switch = QAction(icon, tr("Ativar interface QRibbonSkin"), win)
        self._switch.setCheckable(True)
        self._switch.setChecked(False)
        self._switch.setObjectName("QRibbonSkinToggle")
        self._switch.setToolTip(
            tr("Alternar a Ribbon sem alterar mapas ou dados. Atalho de recuperação: {shortcut}").format(shortcut=RECOVERY_SHORTCUT)
        )
        self._switch.toggled.connect(self.set_enabled)
        # QgisInterface.viewMenu() is the native, translated View/Exibir menu.
        # Insert adjacent to Panels/Toolbars, preserving existing QAction items.
        try:
            view = self.iface.viewMenu()
            if view is None:
                raise AttributeError("QGIS View menu is unavailable")
            existing = view.actions()
            index = view_menu_insertion_point(existing)
            if index < len(existing):
                view.insertAction(existing[index], self._switch)
            else:
                view.addAction(self._switch)
            self._view_menu = view
        except (AttributeError, RuntimeError, TypeError):
            # Exceptionally old/customized interfaces: keep the switch reachable.
            self.iface.addPluginToMenu(PLUGIN_MENU, self._switch)
            self._legacy_plugin_menu = True
        # Recovery is deliberately available in the classic View menu, too.
        # Previous QGIS sessions may already have persisted an all-hidden
        # toolbar layout. In that situation a simple replay of the captured
        # visibility cannot reconstruct toolbars which were hidden *before*
        # QRibbonSkin was enabled. Do not silently enable all toolbars: the
        # user explicitly opts in to this fallback recovery command.
        self._recover_toolbars_action = QAction(
            tr("Recuperar barras do QGIS"), win
        )
        self._recover_toolbars_action.setObjectName("QRibbonSkinRecoverToolbars")
        self._recover_toolbars_action.setToolTip(
            tr("Recuperar as barras anteriormente visíveis; sem registro, mostrar as barras essenciais do QGIS")
        )
        self._recover_toolbars_action.triggered.connect(
            self._recover_native_toolbars_on_request
        )
        if self._view_menu is not None:
            actions = self._view_menu.actions()
            position = actions.index(self._switch) + 1
            if position < len(actions):
                self._view_menu.insertAction(actions[position], self._recover_toolbars_action)
            else:
                self._view_menu.addAction(self._recover_toolbars_action)
        else:
            self.iface.addPluginToMenu(PLUGIN_MENU, self._recover_toolbars_action)
        # The hidden menu bar makes the native switch inaccessible by mouse.
        # A direct main-window shortcut is a secondary, persistent escape hatch.
        self._shortcut = QShortcut(QKeySequence(RECOVERY_SHORTCUT), win)
        self._shortcut.setContext(Qt.ShortcutContext.ApplicationShortcut)
        self._shortcut.activated.connect(self._toggle_from_shortcut)
        # Protect the native QGIS state before QgisApp.closeEvent saves it.
        # On restart, wait for native toolbars and plugin actions to exist.
        win.installEventFilter(self)
        application = QApplication.instance()
        if application is not None:
            application.aboutToQuit.connect(self._on_about_to_quit)
            self._quit_connected = True
        if win.isVisible():
            # Plugin installed from a running QGIS session.
            self._initialization_reported = True
            self._schedule_startup()
        else:
            try:
                self.iface.initializationCompleted.connect(self._on_qgis_initialized)
                self._connected_startup = True
            except (AttributeError, RuntimeError, TypeError):
                # If the signal is not exposed, QEvent.Show is the fallback.
                self._initialization_reported = True

    def _on_qgis_initialized(self):
        self._initialization_reported = True
        self._schedule_startup()

    def eventFilter(self, watched, event):  # noqa: N802
        if watched is self._window and not self._unloaded:
            if event.type() == QEvent.Type.Close:
                # This runs BEFORE QGIS's QMainWindow.closeEvent/saveState.
                # Keep the user's start-with-Ribbon preference for next launch.
                self._closing = True
                if self._is_active or self._ribbon_bar is not None:
                    try:
                        self._disable()
                    except Exception as exc:
                        # Do not interrupt QGIS shutdown; report restoration errors.
                        QgsMessageLog.logMessage(
                            f"Falha ao desativar a Ribbon no fechamento: {exc}",
                            "QRibbonSkin", Qgis.MessageLevel.Warning)
                    finally:
                        self._is_active = False
                        self._set_switch_without_signal(False)
            elif (event.type() == QEvent.Type.Show
                  and self._initialization_reported
                  and not self._startup_completed):
                self._schedule_startup()
        return False

    def _schedule_startup(self):
        if (self._unloaded or self._startup_completed
                or not self._initialization_reported or self._startup_timer_pending):
            return
        self._startup_timer_pending = True
        QTimer.singleShot(0, self._startup_after_qgis)

    def _startup_after_qgis(self):
        self._startup_timer_pending = False
        if self._unloaded or self._startup_completed or not self._window.isVisible():
            return
        self._startup_completed = True
        if self._is_active:
            # A user may have enabled the skin just after loading the plugin,
            # before this zero-delay startup callback had a chance to run.
            # In that case, our OWN snapshot is not an orphan to restore.
            return
        # Recover a snapshot left after a previous abnormal shutdown BEFORE
        # taking a new snapshot (otherwise all the hidden toolbars stay hidden).
        self._recover_previous_session()
        # QGIS may have saved toolbar visibility while Ribbon was active in
        # an earlier version. Restore the last positively recorded state
        # before creating another Ribbon snapshot.
        # Only a profile which is due to start with Ribbon may need an
        # automatic fallback; an intentionally toolbar-free classic QGIS
        # profile is left untouched. No snapshot => a minimal QGIS-owned set.
        restore_on_ribbon_start = setting_is_true(
            self._settings.value(PREFERENCE_KEY, False)
        )
        self._restore_known_good_toolbars(
            allow_core_fallback=restore_on_ribbon_start
        )
        if restore_on_ribbon_start:
            self._switch.setChecked(True)

    def _set_switch_without_signal(self, value):
        if self._switch is not None:
            previous = self._switch.blockSignals(True)
            self._switch.setChecked(value)
            self._switch.blockSignals(previous)
            self._switch.setText(
                tr("Restaurar interface clássica do QGIS") if value
                else tr("Ativar interface QRibbonSkin")
            )

    def _on_about_to_quit(self):
        if not self._closing:
            # Fallback for quit paths that bypass a main-window Close event.
            # Keep the recovery snapshot: QGIS might have already saved its UI.
            self._closing = True
            if self._is_active or self._ribbon_bar is not None:
                try:
                    self._disable(clear_recovery=False)
                except Exception as exc:
                    QgsMessageLog.logMessage(
                        f"Falha ao desativar a Ribbon ao sair: {exc}",
                        "QRibbonSkin", Qgis.MessageLevel.Warning)
                finally:
                    self._is_active = False
                    self._set_switch_without_signal(False)

    def _capture_recovery_snapshot(self):
        """Persist native visibility BEFORE hiding widgets; never saveState()."""
        toolbars = {
            bar.objectName(): bool(visible)
            for bar, visible in self._toolbar_visibility
            if bar.objectName()
        }
        docks = {
            dock.objectName(): bool(visible)
            for dock, visible in self._dock_visibility
            if dock.objectName()
        }
        record = {
            "format": 1, "toolbars": toolbars, "docks": docks,
            "menu_visible": bool(self._previous_menu_bar_visibility),
        }
        self._settings.setValue(RECOVERY_KEY, json.dumps(record))
        self._settings.sync()

    def _native_toolbars(self):
        win = self._window
        return [bar for bar in win.findChildren(QToolBar)
                if bar.parent() is win
                and bar.objectName() != "QRibbonSkinToolbar"]

    def _sync_native_toolbars(self):
        """Track QGIS/plugin toolbars created after Ribbon activation.

        Preserve their visibility at discovery, so switching back to classic
        restores these toolbars too. Never fabricate or trigger QAction objects.
        Existing bars are not touched: this prevents fighting explicit user
        changes and avoids modifying third-party toolbar state repeatedly.
        """
        if (not self._is_active or self._ribbon_bar is None
                or self._closing or self._unloaded):
            return
        known = {id(bar) for bar, _ in self._toolbar_visibility}
        discovered = []
        for bar in self._native_toolbars():
            if id(bar) in known:
                continue
            try:
                visible = bool(bar.isVisible())
                discovered.append((bar, visible))
                # Ribbon occupies the toolbar area. Restore the original
                # visibility at the next switch back to classic QGIS.
                bar.hide()
            except RuntimeError:
                continue
        if discovered:
            self._toolbar_visibility.extend(discovered)
            self._remember_known_good_toolbars(self._toolbar_visibility)
            self._capture_recovery_snapshot()

    def _remember_known_good_toolbars(self, states):
        """Save last visible native toolbars independently from crash recovery.

        Never replace a usable snapshot with the all-hidden state produced by
        QGIS loading an already-affected layout. No global QMainWindow state
        or layout geometry is touched.
        """
        named = {bar.objectName(): bool(visible) for bar, visible in states
                 if bar.objectName()}
        if not any(named.values()):
            return
        record = {"format": 1, "toolbars": named}
        self._settings.setValue(LAST_GOOD_TOOLBARS_KEY, json.dumps(record))
        self._settings.sync()

    def _read_last_good_toolbars(self):
        try:
            data = json.loads(self._settings.value(LAST_GOOD_TOOLBARS_KEY, "") or "{}")
            if data.get("format") != 1 or not isinstance(data.get("toolbars"), dict):
                return {}
            return {str(k): bool(v) for k, v in data["toolbars"].items()}
        except (TypeError, ValueError, AttributeError):
            return {}

    def _core_toolbars(self):
        """Find QGIS-owned essential toolbars by public QgisInterface accessors.

        Object names are stable but can differ across QGIS versions/plugins.
        We avoid guessing toolbar labels translated into PT-BR/English.
        """
        present = self._native_toolbars()
        result = []
        for name in CORE_TOOLBAR_ACCESSORS:
            accessor = getattr(self.iface, name, None)
            if not callable(accessor):
                continue
            try:
                bar = accessor()
                if bar is not None and bar in present and bar not in result:
                    result.append(bar)
            except (RuntimeError, AttributeError, TypeError):
                continue
        return result

    def _show_core_toolbars(self):
        """Last-resort repair of an all-hidden QGIS profile without history.

        Only QGIS's File, Navigation, Layers, Attributes, Digitizing toolbars
        are shown. Third-party plugin toolbars keep their current visibility.
        This fallback is only used at an explicit classic switch/recovery or
        when starting a *requested* Ribbon session with an empty baseline.
        """
        restored = False
        for bar in self._core_toolbars():
            try:
                bar.setVisible(True)
                restored = bar.isVisible() or restored
            except RuntimeError:
                continue
        return restored

    def _restore_known_good_toolbars(self, allow_core_fallback=False):
        """Restore an all-hidden native profile, never replay an empty state.

        A positive saved record wins; if the record cannot restore any
        present toolbar, fall back to QGIS core ones only when requested.
        """
        bars = self._native_toolbars()
        if not bars or any(bar.isVisible() for bar in bars):
            return False
        saved = self._read_last_good_toolbars()
        restored = False
        for bar in bars:
            if saved.get(bar.objectName(), False):
                try:
                    bar.setVisible(True)
                    restored = bar.isVisible() or restored
                except RuntimeError:
                    pass
        if not restored and allow_core_fallback:
            restored = self._show_core_toolbars()
        if restored:
            self._remember_known_good_toolbars(
                [(bar, bar.isVisible()) for bar in bars]
            )
        return restored

    def _recover_native_toolbars_on_request(self, _checked=False):
        """Repair a QGIS profile whose original toolbar state is already lost.

        Preferred recovery replays the last known good visibility snapshot. If
        there is no usable snapshot (e.g. upgrading from a previous release),
        this explicit user-triggered action shows the native toolbars which
        currently exist. Their positions and QAction bindings remain native.
        """
        if self._is_active and self._switch is not None:
            self._switch.setChecked(False)
        # A user-initiated recovery must take precedence over a deferred
        # restoration from the immediately preceding Ribbon teardown.
        self._restore_epoch += 1
        bars = self._native_toolbars()
        saved = self._read_last_good_toolbars()
        matching_positive = any(saved.get(bar.objectName(), False) for bar in bars)
        if matching_positive:
            for bar in bars:
                if bar.objectName() in saved:
                    try:
                        bar.setVisible(saved[bar.objectName()])
                    except RuntimeError:
                        pass
        else:
            self._show_core_toolbars()
        expected = [(bar, bar.isVisible()) for bar in bars]
        self._remember_known_good_toolbars(expected)
        # Unlike the earlier implementation, finish an explicit recovery
        # with a second pass after Qt updates QMainWindow's toolbar rows.
        epoch = self._restore_epoch
        QTimer.singleShot(0, lambda states=expected, e=epoch:
                          self._deferred_native_toolbar_restore(states, e))

    def _deferred_native_toolbar_restore(self, expected, epoch):
        """Reapply native visibility after Qt finishes deleting Ribbon widgets.

        A queued rebuild of the QMainWindow toolbars can otherwise undo the
        synchronous restoration. Never run after the Ribbon has been enabled
        again or when the QGIS window is closing.
        """
        if (epoch != self._restore_epoch or self._closing or self._unloaded
                or self._is_active or self._ribbon_bar is not None):
            return
        for bar, visible in expected:
            try:
                if bar.parent() is self._window:
                    bar.setVisible(visible)
            except RuntimeError:
                continue

    def _clear_recovery_snapshot(self):
        self._settings.remove(RECOVERY_KEY)
        self._settings.sync()

    def _recover_previous_session(self):
        raw = self._settings.value(RECOVERY_KEY, "")
        if not raw:
            return
        try:
            record = json.loads(raw)
            if record.get("format") != 1:
                return
            win = self._window
            toolbar_states = record.get("toolbars", {})
            dock_states = record.get("docks", {})
            for bar in win.findChildren(QToolBar):
                if bar.parent() is win and bar.objectName() in toolbar_states:
                    bar.setVisible(bool(toolbar_states[bar.objectName()]))
            for dock in win.findChildren(QDockWidget):
                if dock.parent() is win and dock.objectName() in dock_states:
                    dock.setVisible(bool(dock_states[dock.objectName()]))
            if "menu_visible" in record:
                win.menuBar().setVisible(bool(record["menu_visible"]))
            self._clear_recovery_snapshot()
        except (ValueError, TypeError, AttributeError, RuntimeError):
            # Keep the recovery record for a future attempt; never guess.
            return

    def _toggle_from_shortcut(self):
        if self._switch is not None and not self._changing:
            self._switch.setChecked(not self._switch.isChecked())

    def set_enabled(self, enabled):
        if self._changing or enabled == self._is_active:
            return
        self._changing = True
        try:
            if enabled:
                self._enable()
            else:
                self._disable()
            self._is_active = enabled
            if not self._closing:
                self._settings.setValue(PREFERENCE_KEY, bool(enabled))
                self._settings.sync()
            if self._switch is not None:
                self._switch.setText(
                    tr("Restaurar interface clássica do QGIS") if enabled
                    else tr("Ativar interface QRibbonSkin")
                )
        except Exception:
            # If partially created, attempt restoration and retain the
            # original failure so that QGIS reports what went wrong.
            try:
                self._disable()
            except Exception as recovery_exc:
                QgsMessageLog.logMessage(
                    f"Falha ao restaurar interface após erro de ativação: {recovery_exc}",
                    "QRibbonSkin", Qgis.MessageLevel.Warning)
            finally:
                self._is_active = False
                if not self._closing:
                    # An invalid installation must not retry and fail on each
                    # subsequent launch without user action.
                    self._settings.setValue(PREFERENCE_KEY, False)
                    self._settings.sync()
                if self._switch is not None:
                    self._switch.blockSignals(True)
                    self._switch.setChecked(False)
                    self._switch.blockSignals(False)
            raise
        finally:
            self._changing = False

    def _enable(self):
        win = self.iface.mainWindow()
        self._restore_epoch += 1  # Cancel any previous queued restoration.
        # A non-invasive skin must not snapshot/replay the complete QMainWindow
        # layout: restoreState() may restore an already corrupted toolbar state.
        # We only record visibility for the objects this plugin actually hides.
        self._native_menu_bar = win.menuBar()
        self._previous_menu_bar_visibility = self._native_menu_bar.isVisible()
        self._toolbar_visibility = [
            (bar, bar.isVisible())
            for bar in win.findChildren(QToolBar)
            if bar.parent() is win and bar.objectName() != "QRibbonSkinToolbar"
        ]
        self._dock_visibility = [
            (dock, dock.isVisible())
            for dock in win.findChildren(QDockWidget)
            if dock.parent() is win
        ]
        self._focus_map = False
        # Repair an all-hidden baseline *before* creating any snapshot, but
        # only if the user has explicitly activated the Ribbon. With no
        # usable history, prefer five QGIS-owned core toolbars.
        if (self._toolbar_visibility
                and not any(visible for _, visible in self._toolbar_visibility)):
            self._restore_known_good_toolbars(allow_core_fallback=True)
            self._toolbar_visibility = [
                (bar, bar.isVisible()) for bar, _ in self._toolbar_visibility
            ]
        # Store a positive native snapshot separately: an already-hidden
        # QGIS startup must not become the next original state.
        self._remember_known_good_toolbars(self._toolbar_visibility)
        # Snapshot is durable even if QGIS or the operating system crashes.
        self._capture_recovery_snapshot()
        bar = QToolBar("QRibbonSkin", win)
        bar.setObjectName("QRibbonSkinToolbar")
        bar.setMovable(False)
        bar.setFloatable(False)
        bar.setAllowedAreas(Qt.ToolBarArea.TopToolBarArea)
        bar.setContentsMargins(0, 0, 0, 0)
        bar.setStyleSheet(
            "QToolBar#QRibbonSkinToolbar { "
            "background-color: #f7f9fc; border: none; padding: 0; margin: 0; spacing: 0; }"
            " QToolBar#QRibbonSkinToolbar::handle { width: 0px; height: 0px; border: none; }"
            " QToolBar#QRibbonSkinToolbar::separator { width: 0px; border: none; }"
        )
        self._ribbon_bar = bar
        ribbon = RibbonWidget(
            self.iface,
            self._restore_action(),
            self._focus_action(),
            self._restore_panels_action(),
        )
        bar.addWidget(ribbon)
        # Hide the entire QRibbonSkin command strip in the Project backstage,
        # including its tabs and search. The backstage back button switches
        # to Inicio even while this toolbar is hidden.
        ribbon.set_project_chrome_callback(self._set_project_chrome_hidden)
        # Insert into the existing first toolbar row instead of appending a
        # separate row, which Qt6 may preserve as a blank strip above tabs.
        anchor = next((candidate for candidate, _ in self._toolbar_visibility
                       if candidate.parent() is win), None)
        if anchor is not None:
            win.insertToolBar(anchor, bar)
        else:
            win.addToolBar(Qt.ToolBarArea.TopToolBarArea, bar)
        if win.toolBarBreak(bar):
            win.removeToolBarBreak(bar)
        # Hide only native top-level toolbars; docks and canvas are unchanged.
        for native_bar, _was_visible in self._toolbar_visibility:
            try:
                native_bar.hide()
            except RuntimeError:
                # Another plugin might have deleted a toolbar.
                pass
        bar.show()
        # Only after the complete Ribbon (including Interface -> classic QGIS)
        # exists may the native menu bar be hidden.
        self._native_menu_bar.hide()
        self._toolbar_monitor.start()
        # Changing styles can make QGIS re-show a dock (notably Browser).
        # Keep precisely the user's panel visibility snapshot from activation.
        self._preserve_initial_docks()
        # Decoration only; never move or change native dock content.
        self._panel_light_theme.start()
        self._preserve_initial_docks()
        # Optional subwindow integration; native main QGIS remains independent.
        try:
            self._layout_manager.start()
        except (AttributeError, RuntimeError, TypeError):
            self._layout_manager.stop()
        # Observe the native standalone Georeferencer QMainWindow via Qt Show
        # events; its Ribbon is optional and original controls stay visible.
        try:
            self._georeferencer_manager.start()
        except (AttributeError, RuntimeError, TypeError):
            self._georeferencer_manager.stop()
        # The QGIS Processing Model Designer is also a native QMainWindow.
        # Its optional Ribbon reuses QGIS-owned actions and stays reversible.
        try:
            self._model_designer_manager.start()
        except (AttributeError, RuntimeError, TypeError):
            self._model_designer_manager.stop()
        # Workspace tabs remain deferred to QRibbonSkin 2.0. All editors
        # keep their own QGIS-owned windows and native processing functions.

    def _preserve_initial_docks(self):
        """Do not open Browser or close Processing Toolbox on activation.

        Only restore visibility of pre-existing native panels. Their dock area,
        tab arrangement and current focus are deliberately left untouched.
        """
        for dock, was_visible in self._dock_visibility:
            try:
                if dock.isVisible() != was_visible:
                    dock.setVisible(was_visible)
            except RuntimeError:
                continue

    def _set_project_chrome_hidden(self, hidden):
        """Reclaim the full backstage height without touching native QGIS UI.

        Qt removes a hidden toolbar from the QMainWindow toolbar layout.  The
        Ribbon QWidget and its tab index remain alive, so the sidebar's
        'Voltar ao mapa' action can show exactly the same toolbar again.
        """
        bar = self._ribbon_bar
        if bar is None:
            return
        try:
            bar.setVisible(not hidden)
        except RuntimeError:
            # A partially destroyed Qt object must not block dock restoration.
            pass

    def _restore_action(self):
        act = QAction(tr("Interface clássica"), None)
        act.setToolTip(tr("Desativar QRibbonSkin e restaurar as barras do QGIS"))
        act.triggered.connect(lambda _checked=False: self._switch.setChecked(False))
        return act

    def _focus_action(self):
        action = QAction(tr("Mapa em foco"), None)
        action.setCheckable(True)
        action.setToolTip(tr("Ocultar temporariamente os painéis; sem alterar o projeto"))
        action.toggled.connect(self._set_map_focus)
        return action

    def _restore_panels_action(self):
        action = QAction(tr("Restaurar painéis iniciais"), None)
        action.setToolTip(tr("Restaurar visibilidade dos painéis anterior à Ribbon"))
        action.triggered.connect(lambda _checked=False: self._restore_dock_visibility())
        return action

    def _set_map_focus(self, focus):
        # Do not change dock areas or QGIS project information. Visibility
        # is restored from the captured pre-Ribbon snapshot.
        if self._ribbon_bar is None:
            return
        self._focus_map = bool(focus)
        if focus:
            for dock, _visible in self._dock_visibility:
                try:
                    dock.hide()
                except RuntimeError:
                    pass
        else:
            self._restore_dock_visibility()

    def _restore_dock_visibility(self):
        for dock, visible in self._dock_visibility:
            try:
                dock.setVisible(visible)
            except RuntimeError:
                pass
        self._focus_map = False

    def _restore_menu_bar(self):
        """Restore precisely the prior menu-bar visibility, also on failures."""
        bar = self._native_menu_bar
        visible = self._previous_menu_bar_visibility
        self._native_menu_bar = None
        self._previous_menu_bar_visibility = None
        if bar is not None and visible is not None:
            try:
                bar.setVisible(visible)
                return True
            except RuntimeError:
                # QGIS may have replaced the bar while another plugin unloaded.
                return False
        return True

    def _disable(self, clear_recovery=True):
        """Best-effort rollback of only the UI objects this plugin touched.

        Never restore the whole QMainWindow state here. Every step is isolated,
        so a toolbar destroyed by another plugin does not block the others.
        """
        win = self.iface.mainWindow()
        # Capture bars added since the last monitor tick before restoring UI.
        self._sync_native_toolbars()
        self._toolbar_monitor.stop()
        # Restore every auxiliary native editor before the main QGIS toolbar.
        try:
            self._georeferencer_manager.stop()
        except (RuntimeError, TypeError, AttributeError):
            pass
        # Restore native Model Designer toolbars before QGIS saves window state.
        try:
            self._model_designer_manager.stop()
        except (RuntimeError, TypeError, AttributeError):
            pass
        # Restore each Layout Designer first, including if it is still open.
        try:
            self._layout_manager.stop()
        except (RuntimeError, TypeError, AttributeError):
            pass
        # Stop panel decoration first, even when Ribbon teardown is partial.
        try:
            self._panel_light_theme.stop()
        except (RuntimeError, TypeError):
            pass
        bar = self._ribbon_bar
        self._ribbon_bar = None
        # Project backstage temporarily hides docks. Restore its own snapshot
        # NOW, before the regular native-UI rollback; Qt deleteLater is async.
        if bar is not None:
            try:
                ribbon = bar.findChild(RibbonWidget)
                if ribbon is not None:
                    ribbon.release_project_dashboard()
            except (RuntimeError, AttributeError):
                # Also tolerate partially constructed third-party Qt wrappers.
                pass
        restored = True
        try:
            if bar is not None:
                try:
                    win.removeToolBar(bar)
                except RuntimeError:
                    pass
                try:
                    bar.hide()
                    bar.deleteLater()
                except RuntimeError:
                    pass
        finally:
            try:
                # Capture an immutable list before clearing the per-Ribbon
                # snapshots. A queued pass handles Qt's deferred re-layout.
                expected_bars = list(self._toolbar_visibility)
                for native_bar, was_visible in expected_bars:
                    try:
                        native_bar.setVisible(was_visible)
                    except RuntimeError:
                        # One destroyed native toolbar cannot block the rest.
                        restored = False
            finally:
                self._toolbar_visibility = []
                # If QGIS opened this profile with every native toolbar
                # already hidden, there is no positive state to replay.
                # Recover a previously recorded visible state, if any.
                if (not self._closing and not any(visible for _, visible in expected_bars)
                        and self._restore_known_good_toolbars(allow_core_fallback=True)):
                    expected_bars = [(bar, bar.isVisible()) for bar, _ in expected_bars]
                try:
                    self._restore_dock_visibility()
                finally:
                    self._dock_visibility = []
                    # Always restore the native QGIS menu on partial failure.
                    if not self._restore_menu_bar():
                        restored = False
                    # If the last QGIS save occurred before restoration, the
                    # persistent record can recover native bars on next launch.
                    if clear_recovery and restored:
                        self._clear_recovery_snapshot()
                    if not self._closing and not self._unloaded and restored:
                        epoch = self._restore_epoch
                        QTimer.singleShot(0, lambda bars=expected_bars, e=epoch:
                                          self._deferred_native_toolbar_restore(bars, e))

    def unload(self):
        # QGIS may unload plugins before, during, or after window shutdown.
        # An unload must NOT be mistaken for a user-requested switch to the
        # classic interface; that preference is changed only by the toggle.
        try:
            if self._is_active or self._ribbon_bar is not None:
                # Retain recovery snapshot in case QGIS already saved its UI
                # while the native toolbars were hidden.
                self._disable(clear_recovery=False)
                self._is_active = False
                self._set_switch_without_signal(False)
        finally:
            try:
                self._layout_manager.stop()
            except (RuntimeError, TypeError, AttributeError):
                pass
            self._toolbar_monitor.stop()
            self._unloaded = True
            try:
                self._window.removeEventFilter(self)
            except RuntimeError:
                pass
            if self._connected_startup:
                try:
                    self.iface.initializationCompleted.disconnect(self._on_qgis_initialized)
                except (RuntimeError, TypeError):
                    pass
                self._connected_startup = False
            if self._quit_connected:
                application = QApplication.instance()
                if application is not None:
                    try:
                        application.aboutToQuit.disconnect(self._on_about_to_quit)
                    except (RuntimeError, TypeError):
                        pass
                self._quit_connected = False
            if self._shortcut is not None:
                self._shortcut.setEnabled(False)
                self._shortcut.deleteLater()
                self._shortcut = None
            if self._recover_toolbars_action is not None:
                if self._view_menu is not None:
                    try:
                        self._view_menu.removeAction(self._recover_toolbars_action)
                    except RuntimeError:
                        pass
                else:
                    self.iface.removePluginMenu(PLUGIN_MENU, self._recover_toolbars_action)
                self._recover_toolbars_action.deleteLater()
                self._recover_toolbars_action = None
            if self._switch is not None:
                if self._view_menu is not None:
                    try:
                        self._view_menu.removeAction(self._switch)
                    except RuntimeError:
                        pass
                    self._view_menu = None
                if self._legacy_plugin_menu:
                    self.iface.removePluginMenu(PLUGIN_MENU, self._switch)
                    self._legacy_plugin_menu = False
                self._switch.deleteLater()
                self._switch = None
