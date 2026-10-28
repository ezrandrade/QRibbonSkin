"""Native-menu-oriented, non-invasive Ribbon built from QGIS's existing actions.

No processing function or map algorithm is reimplemented here. Modified/new
implementation informed by ArcSkin (EnviroSolutions, GPL-2.0), 2026-10-23.
"""

from itertools import combinations
import configparser
import os
from pathlib import Path

from qgis.PyQt.QtCore import Qt, QSize, QEvent, QPoint, QRect, QTimer
from qgis.core import QgsMessageLog, Qgis
from qgis.PyQt.QtGui import QAction, QIcon, QKeySequence, QFontMetrics, QPalette, QPainter, QPen, QColor
from qgis.PyQt.QtWidgets import (
    QApplication, QDialog, QDockWidget, QFrame, QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem, QMenu, QLayout,
    QScrollArea, QSizePolicy, QStyle, QStyleOptionToolButton, QStylePainter, QWidgetAction, QComboBox, QCheckBox,
    QTabBar, QTabWidget, QToolBar, QToolButton, QVBoxLayout, QWidget,
)

from .i18n import tr, ui_label
from .native_menus import (iter_native_menus, native_menu_sections, native_caption,
                           inline_limit_for_group, native_action_group_heading,
                           unique_native_group_heading)
from .icon_mapping import display_icon, fallback_icon, icon_name_for_caption
from .theme import light_palette, light_stylesheet
from .presentation import (suitable_two_line_width, two_line_caption,
                           full_caption_width, complete_caption_lines)
from .project_page import ProjectDashboard
from .ux_rules import (normalized, title_heading, shortcut_role, clipboard_role,
                       principal_role, clipboard_priority)


# The native QGIS QMenuBar/QMenu/QAction hierarchy is the source of truth.
# No fixed list of processing commands or translated menu names is maintained.




def split_caption(text, metrics, available_width, max_lines=3):
    """Fit every word into 1–3 centered lines without inserting ellipses.

    A native QToolButton often elides captions in `TextUnderIcon` mode.
    Breaking words *for display only* avoids changing any native QAction.
    The function is pure and can be tested without Qt by passing a fake
    font metrics object exposing ``horizontalAdvance``.
    """
    words = " ".join(text.replace("&", "").split()).split(" ")
    if not words or words == [""]:
        return ""
    if len(words) == 1:
        return words[0]
    for lines_count in range(1, min(max_lines, len(words)) + 1):
        candidates = []
        for cuts in combinations(range(1, len(words)), lines_count - 1):
            bounds = (0, *cuts, len(words))
            lines = [" ".join(words[bounds[i]:bounds[i + 1]])
                     for i in range(len(bounds) - 1)]
            widths = [metrics.horizontalAdvance(line) for line in lines]
            if max(widths) <= available_width:
                # Equalize line lengths while minimizing very short last lines.
                score = max(widths) - min(widths)
                candidates.append((score, max(widths), lines))
        if candidates:
            _, _, best_lines = min(candidates, key=lambda item: item[:2])
            return "\n".join(best_lines)
    # No clipping: preserve every word even if three lines are insufficient.
    return "\n".join(words)


class RibbonActionButton(QToolButton):
    """QAction-backed button with guaranteed multiline captions.

    Only the painting of the button is overridden.  Checked/disabled state,
    icon, tooltip, native QAction triggering and popup menus remain Qt's.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("QRibbonSkinTool")
        self.setAutoRaise(True)
        self.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        self._compact = False
        self._display_caption_override = None
        self._caption_color = QColor(light_palette()["text"])
        font = self.font()
        font.setPointSizeF(8.5)
        self.setFont(font)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.set_compact(False)

    def set_display_caption(self, caption):
        """Override only the painted Ribbon caption, never the native QAction."""
        self._display_caption_override = ui_label(caption)
        self._update_width()

    def _visible_caption(self):
        return (self._display_caption_override if self._display_caption_override is not None
                else native_caption(self.text()))

    def set_caption_color(self, color):
        """Use the same foreground color in Qt custom painting and QSS."""
        self._caption_color = QColor(color)
        self.update()

    def set_compact(self, compact):
        self._compact = bool(compact)
        self.setIconSize(QSize(16, 16) if compact else QSize(19, 19))
        self.setFixedHeight(55 if compact else 63)
        self._update_width()
        self.update()

    def setDefaultAction(self, action):  # noqa: N802
        super().setDefaultAction(action)
        self.setToolTip(action.toolTip() or action.text().replace("&", ""))
        self._presentation_icon = display_icon(action.icon(), action.text())
        self.setIcon(self._presentation_icon)  # QAction icon remains untouched.
        action.changed.connect(self._sync_action_presentation)
        self._update_width()

    def _sync_action_presentation(self):
        action = self.defaultAction()
        if action is not None:
            self._presentation_icon = display_icon(action.icon(), action.text())
            self.setIcon(self._presentation_icon)
        self._update_width()

    def setMenu(self, menu):  # noqa: N802
        super().setMenu(menu)
        self._update_width()

    def _update_width(self):
        metrics = QFontMetrics(self.font())
        caption = self._visible_caption()
        # Unlike a native QToolButton, neither long translations nor words
        # containing spaces should be reduced to an ellipsis.
        padding = 22 if self.menu() else 10
        minimum = 70 if self._compact else 76
        self.setFixedWidth(full_caption_width(
            caption, metrics.horizontalAdvance, padding, minimum, max_lines=3
        ))
        self.updateGeometry()
        self.update()

    def paintEvent(self, _event):  # noqa: N802
        opt = QStyleOptionToolButton()
        self.initStyleOption(opt)
        # Draw native QToolButton background and menu indicator, but suppress
        # Qt's single-line/elided label and render our own multiline caption.
        opt.text = ""
        opt.icon = QIcon()
        painter = QStylePainter(self)
        painter.drawComplexControl(QStyle.ComplexControl.CC_ToolButton, opt)

        available_width = self.width() - (15 if self.menu() else 6)
        original = self._visible_caption()
        if not original:
            painter.end()
            return
        metrics = QFontMetrics(self.font())
        caption = complete_caption_lines(original, metrics.horizontalAdvance,
                                         available_width, max_lines=3)
        lines_count = caption.count("\n") + 1
        text_height = lines_count * metrics.lineSpacing()
        has_icon = not self.icon().isNull()
        icon_size = self.iconSize().height() if has_icon else 0
        gap = 1 if has_icon else 0
        # An unusually long translated action may need three lines. Prefer
        # complete legible text rather than allowing an icon to clip it.
        if icon_size + gap + text_height > self.height() - 2:
            icon_size = max(0, self.height() - text_height - 3)
            has_icon = icon_size >= 10
            if not has_icon:
                icon_size = 0
                gap = 0
        content_height = icon_size + gap + text_height
        start_y = max(1, (self.height() - content_height) // 2)
        content_width = self.width() - (10 if self.menu() else 0)
        if has_icon:
            x = (content_width - icon_size) // 2
            icon_rect = QRect(x, start_y, icon_size, icon_size)
            mode = QIcon.Mode.Normal if self.isEnabled() else QIcon.Mode.Disabled
            state = QIcon.State.On if self.isChecked() else QIcon.State.Off
            self.icon().paint(painter, icon_rect, Qt.AlignmentFlag.AlignCenter, mode, state)
        text_rect = QRect(1, start_y + icon_size + gap,
                          max(1, content_width - 2), text_height + 1)
        group = (QPalette.ColorGroup.Normal if self.isEnabled()
                 else QPalette.ColorGroup.Disabled)
        # Qt styles may supply an outdated palette for custom painted labels.
        # Use our Ribbon-only text color, preserving the disabled state.
        pen_color = QColor(self._caption_color)
        if group == QPalette.ColorGroup.Disabled:
            pen_color.setAlpha(115)
        painter.setPen(pen_color)
        painter.drawText(text_rect,
                         Qt.AlignmentFlag.AlignCenter, caption)
        painter.end()


def separator_geometry(width, height):
    """Full-height group divider; shares the same boundary as the tab baseline.

    Keep geometry independent of Qt for a deterministic regression test.
    """
    x = max(0, width - 1)
    return x, 0, x, max(0, height - 1)



class RibbonStackButton(QToolButton):
    """QGIS action with a measured, two-line caption and full native tooltip.

    The widget never changes the source QAction.  Long captions acquire extra
    width, subject to a ceiling; a genuinely unfit caption is elided only in
    the visual widget and is always available in the tooltip and source menu.
    """

    MIN_WIDTH = 164
    MAX_WIDTH = 234
    BUTTON_HEIGHT = 30

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("QRibbonSkinStackTool")
        self.setAutoRaise(True)
        self.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.setIconSize(QSize(16, 16))
        self.setFixedHeight(self.BUTTON_HEIGHT)
        self.setFixedWidth(self.MIN_WIDTH)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self._label_color = QColor(light_palette()["text"])
        self._presentation_icon = QIcon()
        font = self.font()
        font.setPointSizeF(8.1)
        self.setFont(font)

    def setDefaultAction(self, action):  # noqa: N802
        super().setDefaultAction(action)
        caption = native_caption(action.text())
        self.setToolTip(action.toolTip() or caption)
        self._presentation_icon = self._context_icon(action.icon(), caption)
        self.setIcon(self._presentation_icon)
        action.changed.connect(self._sync)
        self._measure_width()

    @staticmethod
    def _context_icon(native, caption):
        if native is not None and not native.isNull():
            return native
        if icon_name_for_caption(caption) == "command":
            return QIcon()
        return fallback_icon(caption)

    def _measure_width(self):
        caption = native_caption(self.text())
        metrics = QFontMetrics(self.font())
        has_icon = not self.icon().isNull()
        padding = 36 if has_icon else 15
        # A one- or two-line caption should use a consistent, not excessive,
        # width; only the actual translated caption controls extra space.
        measure = metrics.horizontalAdvance
        target = full_caption_width(caption, measure, padding, self.MIN_WIDTH, max_lines=2)
        self.setFixedWidth(target)
        self.updateGeometry()

    def _sync(self):
        action = self.defaultAction()
        if action is not None:
            self.setIcon(self._context_icon(action.icon(), action.text()))
            self.setToolTip(action.toolTip() or native_caption(action.text()))
        self._measure_width()
        self.update()

    def paintEvent(self, _event):  # noqa: N802
        opt = QStyleOptionToolButton()
        self.initStyleOption(opt)
        opt.text = ""
        opt.icon = QIcon()
        painter = QStylePainter(self)
        painter.drawComplexControl(QStyle.ComplexControl.CC_ToolButton, opt)
        icon = self.icon()
        has_icon = not icon.isNull()
        if has_icon:
            mode = QIcon.Mode.Normal if self.isEnabled() else QIcon.Mode.Disabled
            state = QIcon.State.On if self.isChecked() else QIcon.State.Off
            icon.paint(painter, QRect(4, (self.height()-16)//2, 16, 16),
                       Qt.AlignmentFlag.AlignCenter, mode, state)
        text_x = 24 if has_icon else 7
        available = max(15, self.width() - text_x - (15 if self.menu() else 7))
        metrics = QFontMetrics(self.font())
        caption = native_caption(self.text())
        rect = QRect(text_x, 1, available, self.height() - 2)
        color = QColor(self._label_color)
        if not self.isEnabled():
            color.setAlpha(120)
        painter.setPen(color)
        painter.drawText(rect,
                         Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                         caption)
        painter.end()


class RibbonCompactActionButton(QToolButton):
    """Compact secondary command with complete, two-line painted labels.

    Never changes or reparents the QAction. Uses a little extra width for
    rare long names, instead of Qt's automatic middle/end ellipsis.
    """

    MIN_WIDTH = 102

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("QRibbonSkinCompactTool")
        self.setAutoRaise(True)
        self.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.setIconSize(QSize(16, 16))
        self.setFixedHeight(23)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self._label_color = QColor(light_palette()["text"])
        font = self.font()
        font.setPointSizeF(8.2)
        self.setFont(font)

    def setDefaultAction(self, action):  # noqa: N802
        super().setDefaultAction(action)
        self.setToolTip(action.toolTip() or native_caption(action.text()))
        self.setIcon(RibbonStackButton._context_icon(action.icon(), action.text()))
        action.changed.connect(self._sync)
        self._measure_width()

    def _sync(self):
        action = self.defaultAction()
        if action is not None:
            self.setIcon(RibbonStackButton._context_icon(action.icon(), action.text()))
            self.setToolTip(action.toolTip() or native_caption(action.text()))
        self._measure_width()
        self.update()

    def setMenu(self, menu):  # noqa: N802
        super().setMenu(menu)
        self._measure_width()

    def _measure_width(self):
        metrics = QFontMetrics(self.font())
        text = native_caption(self.text())
        padding = (31 if not self.icon().isNull() else 14)
        if self.menu():
            padding += 14
        # Allocate for the FULL caption.  A single-line stack entry is
        # preferable to a two-line caption clipped by narrow fixed columns.
        # Extra spacing compensates for Qt/Windows font scaling and menu arrows.
        self.setFixedWidth(max(self.MIN_WIDTH, metrics.horizontalAdvance(text) + padding + 12))
        self.updateGeometry()

    def paintEvent(self, _event):  # noqa: N802
        opt = QStyleOptionToolButton()
        self.initStyleOption(opt)
        opt.text = ""
        opt.icon = QIcon()
        painter = QStylePainter(self)
        painter.drawComplexControl(QStyle.ComplexControl.CC_ToolButton, opt)
        icon = self.icon()
        has_icon = not icon.isNull()
        icon_dim = 16
        if has_icon:
            mode = QIcon.Mode.Normal if self.isEnabled() else QIcon.Mode.Disabled
            state = QIcon.State.On if self.isChecked() else QIcon.State.Off
            icon.paint(painter, QRect(3, (self.height()-icon_dim)//2,
                                     icon_dim, icon_dim),
                       Qt.AlignmentFlag.AlignCenter, mode, state)
        text_x = 23 if has_icon else 4
        available = max(1, self.width() - text_x - (14 if self.menu() else 4))
        metrics = QFontMetrics(self.font())
        caption = native_caption(self.text())
        text_height = metrics.lineSpacing()
        text_y = max(0, (self.height()-text_height)//2)
        color = QColor(self._label_color)
        if not self.isEnabled():
            color.setAlpha(120)
        painter.setPen(color)
        painter.drawText(QRect(text_x, text_y, available, text_height+1),
                         Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                         caption)
        painter.end()


class RibbonTaskGroup(QFrame):
    """RustGIS-inspired semantic group: lead action + compact action stack.

    A bottom heading and a thin, full-height section divider visually
    distinguish adjacent groups. Group contents use existing QGIS QActions.
    """

    def __init__(self, heading, parent=None):
        super().__init__(parent)
        self.setObjectName("QRibbonSkinTaskGroup")
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        self._divider_color = QColor(light_palette()["divider"])
        self._heading = ('Complementos' if normalized(heading) in ('gerenciar e instalar complementos', 'manage and install plugins', 'manage and install plugins') else heading)
        heading = self._heading
        self._lead = None
        self._secondaries = []
        self._stack_columns = []
        self._original_item_count = 0
        self._inline_limit = None
        self._overflow_items = []
        self._overflow_menu = None
        self._overflow_button = None
        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 3, 10, 1)
        lay.setSpacing(1)
        self.content = QHBoxLayout()
        self.content.setContentsMargins(0, 0, 0, 0)
        self.content.setSpacing(5)
        self.content.setAlignment(Qt.AlignmentFlag.AlignLeft)
        lay.addLayout(self.content, 1)
        # Render only the QRibbon-owned group caption. Preserve the original
        # heading in self._heading for routing/group identity.
        display_heading = (heading if normalized(heading) == 'rth agriculture mapping tools'
                           else ui_label(heading))
        label = QLabel(display_heading, self)
        label.setObjectName("QRibbonSkinGroupLabel")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setFixedHeight(19)
        label.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        label.setWordWrap(False)
        label.setToolTip(display_heading)
        # Group labels must influence layout width, rather than be painted
        # inside a button-sized fixed section where half the text gets cut.
        self.setMinimumWidth(max(88, label.fontMetrics().horizontalAdvance(display_heading) + 20))
        lay.addWidget(label)

    @property
    def count(self):
        # Count the QGIS source entries, not presentation-only popup buttons.
        return self._original_item_count

    def configure_overflow(self, expected_count):
        """Keep small groups direct; place dense groups in a live QMenu.

        The threshold depends on the native menu contents, not caption
        language or a hard-coded menu title. Called before adding actions.
        """
        if self._original_item_count:
            raise RuntimeError("Overflow must be configured before adding tools")
        self._inline_limit = inline_limit_for_group(expected_count)

    def _ensure_overflow_menu(self):
        if self._overflow_menu is not None:
            return
        self._overflow_menu = QMenu(tr("Outras ferramentas"), self)
        self._overflow_menu.aboutToShow.connect(self._populate_overflow_menu)
        button = RibbonCompactActionButton(self)
        button.setText(tr("Outras ferramentas"))
        button.setToolTip(tr("Mostrar comandos adicionais deste grupo"))
        button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_ArrowDown))
        button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        button.setMenu(self._overflow_menu)
        button._measure_width()
        self._overflow_button = button
        self._append(button)

    def _populate_overflow_menu(self):
        """Populate on opening: current QAction text, state and submenu remain native."""
        menu = self._overflow_menu
        if menu is None:
            return
        menu.clear()
        for kind, item in self._overflow_items:
            if kind == "action":
                if item.isVisible():
                    menu.addAction(item)
            else:
                # Reuse the original QMenu and its own menuAction. A lazy
                # QGIS/plugin submenu can still populate on aboutToShow.
                native_menu = item
                if native_menu.menuAction().isVisible():
                    menu.addMenu(native_menu)
        if not menu.actions():
            placeholder = menu.addAction(tr("Nenhuma ferramenta disponível"))
            placeholder.setEnabled(False)

    def _add_to_overflow(self, kind, item):
        self._overflow_items.append((kind, item))
        self._ensure_overflow_menu()

    def _use_overflow(self):
        return (self._inline_limit is not None
                and self._original_item_count > self._inline_limit)

    def _recalculate_group_width(self):
        """Measure actual complete stack widths after insertion or title changes.

        Qt can shrink nested layouts inside a QScrollArea even when their
        toolbuttons have fixed widths. Explicitly reserve the summed width
        of each column plus the lead and layout spacing/margins.
        """
        lead_width = self._lead.width() if self._lead is not None else 0
        columns = [max((button.width() for button in buttons), default=0)
                   for _layout, buttons in self._stack_columns]
        columns.extend(button.width() for button in getattr(self, '_peer_buttons', ()))
        n = (1 if self._lead is not None else 0) + len(columns)
        content_width = lead_width + sum(columns) + max(0, n - 1) * self.content.spacing()
        margins = self.layout().contentsMargins()
        heading_width = self.findChild(QLabel, 'QRibbonSkinGroupLabel')
        label_width = (heading_width.fontMetrics().horizontalAdvance(heading_width.text()) + 20
                       if heading_width is not None else 0)
        target = max(88, label_width, content_width + margins.left() + margins.right() + 4)
        self.setMinimumWidth(target)
        self.updateGeometry()
        parent = self.parentWidget()
        if parent is not None and parent.layout() is not None:
            parent.layout().invalidate()

    def _new_stack(self):
        """Add an independent three-row column rather than hiding actions."""
        stack = QVBoxLayout()
        stack.setContentsMargins(0, 0, 0, 0)
        stack.setSpacing(1)
        stack.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        self.content.addLayout(stack)
        self._stack_columns.append((stack, []))

    def _append(self, btn):
        if self._lead is None:
            btn.setObjectName("QRibbonSkinLeadTool")
            btn.setFixedHeight(72)
            btn.setIconSize(QSize(25, 25))
            btn.setMinimumWidth(84)
            self.content.addWidget(btn, 0, Qt.AlignmentFlag.AlignVCenter)
            self._lead = btn
        else:
            if not self._stack_columns or len(self._stack_columns[-1][1]) >= 3:
                self._new_stack()
            stack, column_buttons = self._stack_columns[-1]
            stack.addWidget(btn)
            column_buttons.append(btn)
            self._secondaries.append(btn)
            # Never lock widths here: QAction titles and menus may change
            # after buttons are inserted (translations and lazy submenus).
            # The QVBoxLayout computes its widest natural child dynamically.
            for item in column_buttons:
                item.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        # Center lone commands within the section instead of leaving them
        # pinned to the left edge of a heading-sized group.
        if self._lead is not None and not self._secondaries:
            self.content.setAlignment(Qt.AlignmentFlag.AlignHCenter)
            if normalized(self._heading) in ('camadas e grupos', 'incorporar camadas e grupos'):
                if isinstance(self._lead, RibbonActionButton):
                    self._lead.set_display_caption('Incorporar')
        self._recalculate_group_width()

    def add_peer_action(self, action):
        """Place a second large button alongside the group leader."""
        button = RibbonActionButton(self)
        button.setDefaultAction(action)
        button.set_caption_color(QColor(light_palette()["text"]))
        button.setFixedHeight(72)
        button.setIconSize(QSize(25, 25))
        button.setMinimumWidth(84)
        self.content.addWidget(button, 0, Qt.AlignmentFlag.AlignVCenter)
        self._original_item_count += 1
        self._secondaries.append(button)
        if not hasattr(self, '_peer_buttons'):
            self._peer_buttons = []
        self._peer_buttons.append(button)
        self._recalculate_group_width()

    def add_primary_dropdown(self, primary, choices, label=None, menu_caption_overrides=None):
        """A principal QGIS action plus an arrow exposing related native actions.

        Native QActions remain owned by QGIS. Optional menu-only caption aliases
        forward activation to their original action and never rename it globally.
        The main part triggers primary; the arrow opens a full menu.
        """
        if primary is None:
            return
        menu = QMenu(label or native_caption(primary.text()), self)
        seen = set()
        aliases = []
        for action in choices:
            if action is None or action.isSeparator() or id(action) in seen:
                continue
            seen.add(id(action))
            if action.menu() is not None:
                # Preserve the native submenu rather than silently losing its tools.
                menu.addMenu(action.menu())
            elif menu_caption_overrides and id(action) in menu_caption_overrides:
                # Presentation alias: show "Linha" in the measurement dropdown
                # while the native "Medir Linha" QAction/shortcut stays intact.
                proxy = QAction(action.icon(), ui_label(menu_caption_overrides[id(action)]), menu)
                proxy.setToolTip(action.toolTip())
                proxy.triggered.connect(
                    lambda _checked=False, native=action: native.trigger())
                menu.addAction(proxy)
                aliases.append((action, proxy))
            else:
                menu.addAction(action)
        if aliases:
            def refresh_aliases():
                # Read QGIS state when opening; do not duplicate action state.
                for native, proxy in aliases:
                    proxy.setEnabled(native.isEnabled())
                    proxy.setVisible(native.isVisible())
                    proxy.setCheckable(native.isCheckable())
                    if native.isCheckable():
                        proxy.setChecked(native.isChecked())
                    proxy.setIcon(native.icon())
            menu.aboutToShow.connect(refresh_aliases)
            refresh_aliases()
        button = RibbonActionButton(self)
        button.setDefaultAction(primary)
        button.setMenu(menu)
        button.setPopupMode(QToolButton.ToolButtonPopupMode.MenuButtonPopup)
        button.set_caption_color(QColor(light_palette()["text"]))
        self._original_item_count += 1
        self._append(button)
        # For a consolidated one-button group, center the main control.
        self.content.setAlignment(Qt.AlignmentFlag.AlignHCenter)

    def add_action(self, action):
        self._original_item_count += 1
        if self._use_overflow():
            self._add_to_overflow("action", action)
            return
        if self._lead is None:
            btn = RibbonActionButton(self)
            btn.setDefaultAction(action)
            btn.set_caption_color(QColor(light_palette()["text"]))
        else:
            btn = RibbonCompactActionButton(self)
            btn.setDefaultAction(action)
        self._append(btn)

    def add_menu(self, title, menu, icon=None):
        self._original_item_count += 1
        if self._use_overflow():
            self._add_to_overflow("menu", menu)
            return
        if self._lead is None:
            btn = RibbonActionButton(self)
            btn.setText(title)
            btn.setIcon(display_icon(icon, title))
            btn.set_caption_color(QColor(light_palette()["text"]))
        else:
            btn = RibbonCompactActionButton(self)
            btn.setText(title)
            btn.setIcon(RibbonStackButton._context_icon(icon, title))
        btn.setToolTip(title)
        btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        btn.setMenu(menu)
        if isinstance(btn, RibbonCompactActionButton):
            btn._measure_width()
        self._append(btn)

    def set_compact(self, compact):
        # Native-menu groups retain the same layout in compact and expanded
        # ribbon modes; only available vertical space changes.
        return

    def paintEvent(self, event):  # noqa: N802
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setPen(QPen(self._divider_color, 1))
        x = max(0, self.width() - 1)
        painter.drawLine(x, 8, x, max(8, self.height() - 20))
        painter.end()


class RibbonGroup(QFrame):
    """Aligned group with divider painted in one pass across its full height."""

    def __init__(self, heading, parent=None):
        super().__init__(parent)
        self.setObjectName("QRibbonSkinGroup")
        colors = light_palette()
        self._divider_color = QColor(colors["divider"])
        self._caption_color = QColor(colors["text"])
        # QSS frame borders can be segmented by native style/layout geometry.
        # A divider painted at the full group's edge has consistent continuity.
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(5, 1, 5, 1)
        lay.setSpacing(0)
        self._buttons = []
        self.tools = QHBoxLayout()
        self.tools.setContentsMargins(0, 0, 0, 0)
        self.tools.setSpacing(1)
        lay.addLayout(self.tools, 1)
        heading_label = QLabel(heading, self)
        heading_label.setObjectName("QRibbonSkinGroupLabel")
        heading_label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        # Native menu action titles are already visible on the buttons.
        # Do not create opaque captions such as "Comandos" / "Submenus".
        heading_label.setVisible(bool(heading))
        heading_label.setFixedHeight(15 if heading else 0)
        heading_label.setToolTip(heading)
        if heading:
            self.setMinimumWidth(max(88, heading_label.fontMetrics().horizontalAdvance(heading) + 20))
        lay.addWidget(heading_label)
        self._heading_label = heading_label
        self._recalculate_group_width()

    def _recalculate_group_width(self):
        """Reserve the summed widths of ALL buttons, not just the heading.

        The Interface page uses multiple horizontally arranged RibbonActionButton
        widgets, unlike native RibbonTaskGroup. Its old width based on heading
        alone allowed Qt to squeeze children until their captions overlapped.
        """
        margins = self.layout().contentsMargins()
        buttons_width = sum(button.width() for button in self._buttons)
        spacing = self.tools.spacing() * max(0, len(self._buttons) - 1)
        caption_width = (self._heading_label.fontMetrics().horizontalAdvance(
            self._heading_label.text()) + 20) if self._heading_label.text() else 0
        required = max(88, caption_width, buttons_width + spacing +
                       margins.left() + margins.right())
        self.setFixedWidth(required)
        self.tools.invalidate()
        self.layout().invalidate()
        self.updateGeometry()

    def add_action(self, action):
        btn = RibbonActionButton(self)
        btn.setDefaultAction(action)  # The existing QGIS QAction is never modified.
        btn.set_caption_color(self._caption_color)
        self.tools.addWidget(btn, 0, Qt.AlignmentFlag.AlignVCenter)
        self._buttons.append(btn)
        self._recalculate_group_width()

    def add_menu(self, title, menu, icon=None):
        btn = RibbonActionButton(self)
        btn.setObjectName("QRibbonSkinMenuTool")
        btn.setText(title)
        btn.setToolTip(title)
        btn.setIcon(display_icon(icon, title))
        btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        btn.setMenu(menu)
        btn.set_caption_color(self._caption_color)
        self.tools.addWidget(btn, 0, Qt.AlignmentFlag.AlignVCenter)
        self._buttons.append(btn)
        self._recalculate_group_width()

    def set_compact(self, compact):
        for btn in self._buttons:
            btn.set_compact(compact)
        self._recalculate_group_width()

    def paintEvent(self, event):  # noqa: N802
        super().paintEvent(event)
        # Consistent 1 px end-to-end divider, not a native QFrame border.
        # A flat, unboxed group like RustGIS: spacing provides separation.
        # Avoid drawing vertical rails around each group.



class RibbonHorizontalScroll(QScrollArea):
    """Use wheel/trackpad input to navigate horizontally when groups overflow."""

    def wheelEvent(self, event):  # noqa: N802
        bar = self.horizontalScrollBar()
        if bar.maximum() <= bar.minimum():
            super().wheelEvent(event)
            return
        pixels = event.pixelDelta()
        distance = pixels.x() if pixels.x() else pixels.y()
        if not distance:
            angles = event.angleDelta()
            steps = angles.x() if angles.x() else angles.y()
            distance = round(steps / 120.0 * max(48, self.viewport().width() // 4))
        if distance:
            bar.setValue(bar.value() - distance)
            event.accept()
        else:
            super().wheelEvent(event)


class RibbonOverflowArrow(QToolButton):
    """Divider-height, 20 px wide arrow: click to jump or hover to scroll.

    Timers are owned by the arrow; leaving, hiding or disabling it stops both
    timers immediately. Only the horizontal QScrollBar position is changed.
    """

    def __init__(self, direction, on_hover_scroll, parent=None):
        super().__init__(parent)
        self._direction = direction
        self._on_hover_scroll = on_hover_scroll
        self.setObjectName("QRibbonSkinOverflowArrow")
        self.setAutoRaise(True)
        # Match the approximately 83 px group-divider height without
        # intruding into the bottom group caption or tab header.
        self.setFixedSize(20, 83)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self._hover_delay = QTimer(self)
        self._hover_delay.setSingleShot(True)
        self._hover_delay.setInterval(320)
        self._hover_delay.timeout.connect(self._begin_hover_scroll)
        self._hover_timer = QTimer(self)
        self._hover_timer.setInterval(65)
        self._hover_timer.timeout.connect(self._hover_tick)

    def _stop_hover(self):
        self._hover_delay.stop()
        self._hover_timer.stop()

    def _hover_tick(self):
        if not self.isVisible() or not self.isEnabled() or not self.underMouse():
            self._stop_hover()
            return
        self._on_hover_scroll(self._direction)

    def _begin_hover_scroll(self):
        if self.isVisible() and self.isEnabled() and self.underMouse():
            self._hover_tick()
            if self.isEnabled():
                self._hover_timer.start()

    def enterEvent(self, event):  # noqa: N802
        super().enterEvent(event)
        if self.isEnabled():
            self._hover_delay.start()

    def leaveEvent(self, event):  # noqa: N802
        self._stop_hover()
        super().leaveEvent(event)

    def hideEvent(self, event):  # noqa: N802
        self._stop_hover()
        super().hideEvent(event)

    def changeEvent(self, event):  # noqa: N802
        if event.type() == QEvent.Type.EnabledChange and not self.isEnabled():
            self._stop_hover()
        super().changeEvent(event)


class RibbonScrollPage(QWidget):
    """Horizontal ribbon navigation without a scrollbar covering labels.

    The scroll area remains fully keyboard/wheel-scrollable. For mouse users,
    compact chevrons appear *beside* the ribbon only when content overflows.
    Neither a native scrollbar nor chevrons consume vertical caption space.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("QRibbonSkinPage")
        self._syncing = False
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(0)
        self.left = self._arrow(QStyle.StandardPixmap.SP_ArrowLeft, tr("Voltar nos grupos"), -1)
        self.right = self._arrow(QStyle.StandardPixmap.SP_ArrowRight, tr("Avançar nos grupos"), 1)
        self.scroll = RibbonHorizontalScroll(self)
        self.scroll.setObjectName("QRibbonSkinScroll")
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setWidgetResizable(False)  # Keep the full natural width of every group
        self.scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.scroll.setMinimumWidth(0)
        self.content = QWidget(self.scroll)
        self.content.setObjectName("QRibbonSkinTabContent")
        self.content_row = QHBoxLayout(self.content)
        self.content_row.setContentsMargins(3, 0, 5, 0)
        self.content_row.setSpacing(0)
        self.content_row.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self.content_row.setSizeConstraint(QLayout.SizeConstraint.SetMinAndMaxSize)
        self.scroll.setWidget(self.content)
        self.content_row.invalidate()
        row.addWidget(self.left, 0, Qt.AlignmentFlag.AlignVCenter)
        row.addWidget(self.scroll, 1)
        row.addWidget(self.right, 0, Qt.AlignmentFlag.AlignVCenter)
        self.left.clicked.connect(lambda: self._step(-1))
        self.right.clicked.connect(lambda: self._step(1))
        scrollbar = self.scroll.horizontalScrollBar()
        scrollbar.rangeChanged.connect(self._update_arrows)
        scrollbar.valueChanged.connect(self._update_arrows)
        self._update_arrows()
        QTimer.singleShot(0, self._update_arrows)
        # The original bottom border was painted by the content widget,
        # which may be narrower than the visible page. This 1px overlay
        # follows the page width, including empty space to the right.
        self._bottom_rule = QFrame(self)
        self._bottom_rule.setObjectName('QRibbonSkinFullWidthBottomRule')
        self._bottom_rule.setStyleSheet(
            'QFrame#QRibbonSkinFullWidthBottomRule { background-color: %s; border: 0; }'
            % light_palette()['divider'])
        self._bottom_rule.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self._bottom_rule.setGeometry(0, max(0, self.height()-1), self.width(), 1)
        self._bottom_rule.raise_()

    def resizeEvent(self, event):  # noqa: N802
        super().resizeEvent(event)
        if hasattr(self, '_bottom_rule'):
            self._bottom_rule.setGeometry(0, max(0, self.height()-1), self.width(), 1)
            self._bottom_rule.raise_()

    def _arrow(self, standard_icon, title, direction):
        button = RibbonOverflowArrow(direction, self._hover_step, self)
        button.setIcon(self.style().standardIcon(standard_icon))
        button.setToolTip(title)
        button.setVisible(False)
        return button

    def consolidate_geometry(self):
        """Finalize content's actual minimum width after native menus are built."""
        row = self.content_row
        row.invalidate()
        row.activate()
        required = max(1, row.sizeHint().width(), row.minimumSize().width())
        self.content.setMinimumWidth(required)
        self.content.resize(required, max(self.scroll.viewport().height(), self.content.sizeHint().height()))
        self.scroll.widget().updateGeometry()
        QTimer.singleShot(0, self._update_arrows)

    def _hover_step(self, direction):
        bar = self.scroll.horizontalScrollBar()
        # Small, regular increments create continuous scrolling rather than
        # repeated 65%-viewport jumps while hovering.
        delta = max(12, min(30, self.scroll.viewport().width() // 38))
        bar.setValue(bar.value() + direction * delta)

    def _step(self, direction):
        scrollbar = self.scroll.horizontalScrollBar()
        distance = max(100, int(self.scroll.viewport().width() * 0.65))
        scrollbar.setValue(scrollbar.value() + direction * distance)

    def _update_arrows(self, *_args):
        if self._syncing:
            return
        self._syncing = True
        try:
            bar = self.scroll.horizontalScrollBar()
            overflow = bar.maximum() > bar.minimum()
            self.left.setVisible(overflow)
            self.right.setVisible(overflow)
            self.left.setEnabled(overflow and bar.value() > bar.minimum())
            self.right.setEnabled(overflow and bar.value() < bar.maximum())
        finally:
            self._syncing = False


class RibbonSpotlight(QDialog):
    """Search palette showing existing QGIS QActions without owning or cloning them."""

    def __init__(self, ribbon):
        super().__init__(ribbon.iface.mainWindow(),
                         Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        self.setObjectName("QRibbonSkinSpotlight")
        self.setModal(False)
        self._ribbon = ribbon
        self._matches = []
        self.setMinimumWidth(420)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        frame = QVBoxLayout(self)
        frame.setContentsMargins(16, 14, 16, 12)
        frame.setSpacing(8)
        heading = QLabel(tr("Buscar ferramentas"), self)
        heading.setStyleSheet("font-size: 15px; font-weight: 600;")
        frame.addWidget(heading)
        self.query = QLineEdit(self)
        self.query.setObjectName("QRibbonSkinSpotlightInput")
        self.query.setPlaceholderText(tr("Digite para buscar ferramentas"))
        self.query.setClearButtonEnabled(True)
        self.query.setMinimumHeight(36)
        self.query.textChanged.connect(self._populate)
        self.query.returnPressed.connect(self._activate_selected)
        self.query.installEventFilter(self)
        frame.addWidget(self.query)
        self.results = QListWidget(self)
        self.results.setObjectName("QRibbonSkinSpotlightResults")
        self.results.setIconSize(QSize(20, 20))
        self.results.setMinimumHeight(220)
        self.results.itemActivated.connect(self._activate_item)
        self.results.itemClicked.connect(self._activate_item)
        frame.addWidget(self.results)
        footer = QLabel(tr("Enter: executar  ·  Esc: fechar"), self)
        footer.setStyleSheet("font-size: 11px;")
        frame.addWidget(footer)
        palette = self.palette()
        base = palette.color(QPalette.ColorRole.Window).name()
        text = palette.color(QPalette.ColorRole.WindowText).name()
        border = palette.color(QPalette.ColorRole.Mid).name()
        self.setStyleSheet(
            "QDialog#QRibbonSkinSpotlight { background: %s; color: %s; border: 1px solid %s; "
            "border-radius: 12px; }" % (base, text, border)
        )

    def eventFilter(self, watched, event):  # noqa: N802
        if watched is self.query and event.type() == QEvent.Type.KeyPress:
            if event.key() == Qt.Key.Key_Escape:
                self.close()
                return True
            if event.key() == Qt.Key.Key_Down:
                index = self.results.currentRow()
                self.results.setCurrentRow(min(self.results.count() - 1, index + 1))
                return True
            if event.key() == Qt.Key.Key_Up:
                self.results.setCurrentRow(max(0, self.results.currentRow() - 1))
                return True
        return super().eventFilter(watched, event)

    def keyPressEvent(self, event):  # noqa: N802
        if event.key() == Qt.Key.Key_Escape:
            self.close()
        else:
            super().keyPressEvent(event)

    def open_centered(self, initial_text=""):
        window = self._ribbon.iface.mainWindow()
        # Constrain palette to the QGIS main window, not other applications.
        width = min(660, max(420, window.width() - 64))
        self.resize(width, 360)
        center = window.mapToGlobal(window.rect().center())
        self.move(center.x() - width // 2, center.y() - self.height() // 2)
        self.query.setText(initial_text)
        self._populate(initial_text)
        self.show()
        self.raise_()
        self.activateWindow()
        self.query.setFocus()
        self.query.selectAll()

    def _populate(self, text):
        self.results.clear()
        self._matches = self._ribbon._search_actions(text, limit=35)
        for name, action in self._matches:
            item = QListWidgetItem(action.icon(), name, self.results)
            item.setToolTip(action.toolTip() or name)
        if self.results.count():
            self.results.setCurrentRow(0)
        else:
            item = QListWidgetItem(tr("Nenhum comando encontrado"), self.results)
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
            if action.isEnabled() and action.isVisible():
                action.trigger()


class RibbonWidget(QWidget):
    """QTabWidget in a QToolBar; horizontal scrolling avoids monitor overflow."""

    def __init__(self, iface, restore_action, focus_action,
                 restore_panels_action, parent=None):
        super().__init__(parent)
        self.iface = iface
        self._groups = []
        self._native_groups = []
        self._native_pages = []
        self._task_menus = []
        self._view_interface_actions = []
        self._project_page = None
        self._principal_page = None
        self._moved_action_ids = set()
        self._quick_actions = {}
        self._compact = False
        self._search_menu = QMenu(self)
        # The plugin owns the QToolBar.  The Ribbon only requests that its
        # container be hidden while the Project backstage is open.
        self._project_chrome_callback = None
        # Own temporary actions: repeated activation must not leak QActions.
        for action in (restore_action, focus_action, restore_panels_action):
            action.setParent(self)
        restore_panels_action.triggered.connect(
            lambda _checked=False: focus_action.setChecked(False)
        )
        self.setObjectName("QRibbonSkinWidget")
        self.setMinimumWidth(0)
        self.setFixedHeight(124)  # Vertical density restored from v0.9.26
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setStyleSheet(light_stylesheet())
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        tabs = QTabWidget(self)
        tabs.setObjectName("QRibbonSkinTabs")
        tabs.setDocumentMode(True)
        tabs.setUsesScrollButtons(True)
        tabs.setMinimumWidth(0)
        tabs.tabBar().setExpanding(False)
        tabs.tabBar().setDrawBase(False)  # Avoid a second tab-strip baseline.
        tabs.tabBar().setElideMode(Qt.TextElideMode.ElideNone)
        tabs.setMinimumHeight(90)
        self.tabs = tabs
        outer.addWidget(tabs)

        self._build_native_tabs()
        self._make_extra_tabs(restore_action, focus_action, restore_panels_action)
        self._make_quick_access()
        self._make_search_corner()
        self._spotlight = RibbonSpotlight(self)
        self._suspended_quit_shortcut = None
        # Global event filter is active only while the main QGIS window is
        # foreground.  It prevents the normal Alt+Q QAction from being fired
        # during an active Ribbon session; other QGIS windows are unaffected.
        app = QApplication.instance()
        if app is not None:
            app.installEventFilter(self)
        # Automatic Main tab selection on reading a QGIS project.
        try:
            self.iface.projectRead.connect(self._on_project_read)
            self.destroyed.connect(self._disconnect_project_read)
        except (AttributeError, RuntimeError, TypeError):
            pass
        # Backstage overlays the canvas non-destructively. QGIS map widget,
        # project, layer tree, main window and toolbars remain untouched.
        self._project_dashboard = ProjectDashboard(iface)
        self._project_dashboard.set_on_close(self._return_from_project)
        self.destroyed.connect(self._project_dashboard.dispose)
        self.tabs.currentChanged.connect(self._on_tab_changed)
        # Start at the first non-Project native menu: keep the map visible.
        start = self.tabs.indexOf(self._principal_page)
        if start < 0:
            start = next((i for i in range(self.tabs.count())
                          if self.tabs.widget(i) is not self._project_page), 0)
        self.tabs.setCurrentIndex(start)
        self._on_tab_changed(self.tabs.currentIndex())

        self.compact_action = QAction(tr("Modo compacto"), self)
        self.compact_action.setCheckable(True)
        self.compact_action.toggled.connect(self._on_manual_compact)
        self.auto_action = QAction(tr("Ajuste automático à janela"), self)
        self.auto_action.setCheckable(True)
        # Auto-layout is opt-in. It must never silently expand the ribbon
        # on large displays when the user's desired default is compact.
        self.auto_action.setChecked(False)
        self.auto_action.toggled.connect(self._on_auto_toggle)
        self._display_group.add_action(self.compact_action)
        self._display_group.add_action(self.auto_action)
        self.iface.mainWindow().installEventFilter(self)
        self._set_compact(True)
        self._update_expand_button()
        self._update_search_width()
        self._claim_search_shortcut()  # after all other constructor work succeeds
        self._last_menu_fingerprint = self._native_menu_fingerprint()
        self._raster_source_high_water = self._diagnostic_raster_actions()
        self._log_raster_diagnostic('Inicialização')
        # Changes made by QGIS or third-party plugins are checked independently
        # of tab navigation. A steady snapshot must be observed twice before
        # a refresh; short-lived empty menus cannot replace a complete Ribbon.
        self._pending_menu_fingerprint = None
        self._pending_menu_observations = 0
        self._menu_watch = QTimer(self)
        self._menu_watch.setInterval(3000)
        self._menu_watch.timeout.connect(self._refresh_if_menu_changed)
        self._menu_watch.start()
        QTimer.singleShot(1800, self._refresh_if_menu_changed)

    def eventFilter(self, watched, event):  # noqa: N802
        if event.type() in (QEvent.Type.ShortcutOverride, QEvent.Type.KeyPress):
            if (event.key() == Qt.Key.Key_Q
                    and event.modifiers() == Qt.KeyboardModifier.AltModifier
                    and QApplication.activeWindow() is self.iface.mainWindow()):
                if event.type() == QEvent.Type.ShortcutOverride:
                    event.accept()
                    return True
                self.open_spotlight()
                event.accept()
                return True
        if watched is self.iface.mainWindow() and event.type() == QEvent.Type.Resize:
            # Search remains responsive even when size-driven Ribbon layout
            # is disabled (the default).
            self._update_search_width()
            if self.auto_action.isChecked():
                self._apply_auto_layout()
        return super().eventFilter(watched, event)

    def _position_quick_access(self):
        """Keep quick actions outside all tabs, with no shared hover region."""
        if not hasattr(self, 'quick_host'):
            return
        host = self.quick_host
        # QTabWidget reserves a true corner for this widget. In particular,
        # Project's first tab no longer contains/owns the quick buttons.
        if self.tabs.cornerWidget(Qt.Corner.TopLeftCorner) is not host:
            self.tabs.setCornerWidget(host, Qt.Corner.TopLeftCorner)
        host.show()

    def _update_search_width(self):
        if not hasattr(self, "search"):
            return
        width = max(400, self.width() if self.width() > 500
                    else self.iface.mainWindow().width())
        search_width = 168 if width < 850 else (210 if width < 1240 else 260)
        host_width = search_width + 12
        self.search.setFixedWidth(search_width)
        self.search_host.setGeometry(max(0, width - host_width - 5),
                                     0, host_width, 30)
        # Tab names scroll independently if the window is too narrow;
        # never put the search on a second row or over the tab labels.
        self._position_quick_access()
        self.tabs.tabBar().setMaximumWidth(max(100, width - host_width - 14))
        self.search_host.raise_()

    def _apply_auto_layout(self):
        window = self.iface.mainWindow()
        self._update_search_width()
        self._set_compact(window.width() < 1450 or window.height() < 850)

    def _on_manual_compact(self, compact):
        self.auto_action.blockSignals(True)
        self.auto_action.setChecked(False)
        self.auto_action.blockSignals(False)
        self._set_compact(compact)

    def _on_auto_toggle(self, enabled):
        if enabled:
            self._apply_auto_layout()

    def _set_compact(self, compact):
        if self._compact == compact:
            return
        self._compact = bool(compact)
        self.setFixedHeight(124 if compact else 132)
        self.compact_action.blockSignals(True)
        self.compact_action.setChecked(compact)
        self.compact_action.blockSignals(False)
        for group in self._groups:
            group.set_compact(compact)
        self._update_expand_button()
        self.updateGeometry()

    def _update_expand_button(self):
        if hasattr(self, "expand_button"):
            self.expand_button.setText("▾" if self._compact else "▴")
            self.expand_button.setToolTip("Expandir faixa Ribbon" if self._compact else "Recolher faixa Ribbon")

    def _toggle_expand_button(self):
        self._on_manual_compact(not self._compact)

    def _add_group(self, row, label):
        # Interface-only groups use the same dense, measured lead/stack layout
        # as QGIS-native tabs.  RibbonGroup's independent large buttons led to
        # horizontal collisions when action captions changed after insertion.
        group = RibbonTaskGroup(title_heading(tr(label)), self)
        self._groups.append(group)
        row.addWidget(group)
        return group

    def _make_search_corner(self):
        """Overlay a fixed-height, right-aligned search in the TAB HEADER.

        QTabWidget.setCornerWidget used to give a broken baseline/stray
        search field on some Qt6/QGIS builds. A sibling header child and a
        reserved tab-bar width keep the control geometrically anchored.
        """
        host = QFrame(self)
        host.setObjectName("QRibbonSkinSearchCorner")
        layout = QHBoxLayout(host)
        layout.setContentsMargins(5, 2, 5, 2)
        layout.setSpacing(3)
        # No expand/collapse arrow: manual controls live in Interface -> Exibição.
        self.search = QLineEdit(host)
        self.search.setObjectName("QRibbonSkinSearch")
        self.search.setPlaceholderText(tr("Buscar ferramenta...  Alt+Q"))
        self.search.setToolTip(tr("Abrir busca central (Alt+Q)"))
        self.search.setFixedHeight(24)
        self.search.setClearButtonEnabled(True)
        self.search.returnPressed.connect(lambda: self.open_spotlight(self.search.text()))
        search_icon = QIcon(str(Path(__file__).resolve().parent /
                                "resources" / "search.svg"))
        search_action = self.search.addAction(
            search_icon, QLineEdit.ActionPosition.TrailingPosition
        )
        search_action.triggered.connect(lambda _checked=False: self.open_spotlight(self.search.text()))
        layout.addWidget(self.search)
        self.search_host = host
        self.search_host.raise_()
        self._update_search_width()

    def resizeEvent(self, event):  # noqa: N802
        super().resizeEvent(event)
        if hasattr(self, "search_host"):
            self._update_search_width()

    def set_project_chrome_callback(self, callback):
        """Request visibility changes only for QRibbonSkin's own toolbar.

        Native QGIS toolbars, menu bar, layouts and settings are never touched
        by backstage transitions.  The dashboard itself manages dock widgets.
        """
        self._project_chrome_callback = callback

    def _on_tab_changed(self, index):
        if hasattr(self, '_last_menu_fingerprint') and not getattr(self, '_rebuilding_menus', False):
            # Switching tabs is purely a UI operation and must not trigger a
            # full Ribbon rebuild. The independent watcher handles new plugins.
            # Raster plugins sometimes fill pre-existing menus lazily, leaving
            # QAction identity fingerprints unchanged. Refresh once upon entry,
            # without making the user press Interface > Atualizar menus.
            current_name = normalized(self.tabs.tabText(index)) if index >= 0 else ''
            if current_name == 'raster':
                if not getattr(self, '_raster_entry_refreshed', False):
                    self._raster_entry_refreshed = True
                    QTimer.singleShot(250, self._refresh_raster_on_entry)
                    QTimer.singleShot(1250, self._refresh_raster_on_entry)
            else:
                self._raster_entry_refreshed = False
        if not hasattr(self, "_project_dashboard"):
            return
        show = (self._project_page is not None
                and self.tabs.widget(index) is self._project_page)
        if show:
            # Cover the canvas first, then reclaim the full Ribbon height.
            self._project_dashboard.set_active(True)
            if self._project_chrome_callback is not None:
                self._project_chrome_callback(True)
        else:
            # Restore the Ribbon before uncovering the map and the dock panels.
            if self._project_chrome_callback is not None:
                self._project_chrome_callback(False)
            self._project_dashboard.set_active(False)

    def _disconnect_project_read(self, *_args):
        try:
            self.iface.projectRead.disconnect(self._on_project_read)
        except (AttributeError, RuntimeError, TypeError):
            pass

    def _on_project_read(self):
        QTimer.singleShot(0, self._select_principal)

    def _select_principal(self):
        try:
            from qgis.PyQt import sip
            if sip.isdeleted(self.tabs):
                return
            index = self.tabs.indexOf(self._principal_page)
            if index >= 0:
                self.tabs.setCurrentIndex(index)
        except (RuntimeError, TypeError, AttributeError):
            pass

    def _return_from_project(self):
        """Guard against delayed native QAction signals after Qt teardown."""
        tabs = getattr(self, "tabs", None)
        if tabs is not None:
            try:
                from qgis.PyQt import sip
                if not sip.isdeleted(tabs):
                    index = tabs.indexOf(getattr(self, '_principal_page', None)) if hasattr(tabs, 'indexOf') else -1
                    if index < 0:
                        index = next((i for i in range(tabs.count())
                                      if tabs.widget(i) is not self._project_page), -1)
                    if index >= 0:
                        tabs.setCurrentIndex(index)
                        return
            except (RuntimeError, TypeError, AttributeError, ImportError):
                pass
        dashboard = getattr(self, "_project_dashboard", None)
        if dashboard is not None:
            try:
                dashboard.set_active(False)
            except RuntimeError:
                dashboard._dock_guard.restore()

    def release_project_dashboard(self):
        """Restore application shortcuts/panels before removing the Ribbon."""
        self._release_search_shortcut()
        if hasattr(self, '_spotlight'):
            self._spotlight.close()
            self._spotlight.deleteLater()
        self._disconnect_project_read()
        app = QApplication.instance()
        if app is not None:
            app.removeEventFilter(self)
        if hasattr(self, "_project_dashboard"):
            self._project_dashboard.set_on_close(None)
            self._project_dashboard.dispose()

    def _search_actions(self, text, limit=35):
        query = normalized(text)
        if len(query) < 2:
            return []
        win = self.iface.mainWindow()
        candidates = list(win.findChildren(QAction))
        for toolbar in win.findChildren(QToolBar):
            candidates.extend(toolbar.actions())
        for top_menu in win.menuBar().actions():
            candidates.extend(self._recursive_menu_actions(top_menu.menu()))
        matches = []
        unique = set()
        for action in candidates:
            if (id(action) in unique or action in (self.compact_action, self.auto_action)
                    or not action.isEnabled() or not action.isVisible()
                    or action.isSeparator() or action.menu() is not None):
                continue
            name = native_caption(action.text())
            if not name:
                continue
            unique.add(id(action))
            caption = normalized(name)
            if query in caption:
                matches.append((name, action))
        return sorted(matches, key=lambda p: (not normalized(p[0]).startswith(query),
                                               len(p[0]), p[0].casefold()))[:limit]

    def open_spotlight(self, text=""):
        if hasattr(self, "_spotlight"):
            self._spotlight.open_centered(text)

    def _show_search_results(self):
        # Compatibility entry-point retained for existing integrations.
        self.open_spotlight(self.search.text())

    def _recursive_menu_actions(self, root):
        if root is None:
            return []
        visited = set()
        result = []
        def visit(menu):
            if id(menu) in visited:
                return
            visited.add(id(menu))
            for act in menu.actions():
                result.append(act)
                if act.menu() is not None:
                    visit(act.menu())
        visit(root)
        return result

    def _flatten_actions(self, menu):
        """Iterate nested native QAction entries safely (compatibility helper)."""
        return self._recursive_menu_actions(menu)

    def _new_tab(self, name, native=False):
        page = RibbonScrollPage(self)
        if native and hasattr(self, "_interface_page"):
            # A refresh inserts native tabs before the persistent Interface tab.
            index = self.tabs.indexOf(self._interface_page)
            if index >= 0:
                self.tabs.insertTab(index, page, tr(name))
            else:
                self.tabs.addTab(page, tr(name))
        else:
            self.tabs.addTab(page, tr(name))
        if native:
            self._native_pages.append(page)
        return page.content_row


    def _is_raster_root(self, root_menu, root_title=""):
        """Recognize Raster by the real menu-bar QAction, not an optional iface getter."""
        native = self._safe_iface('rasterMenu')
        if native is not None and root_menu is native:
            return True
        if normalized(root_title) == 'raster':
            return True
        try:
            return normalized(root_menu.title()) == 'raster'
        except (AttributeError, RuntimeError, TypeError):
            return False

    def _safe_iface(self, name):
        """Optional public PyQGIS getter; custom QGIS builds may omit one."""
        try:
            method = getattr(self.iface, name, None)
            return method() if callable(method) else None
        except (AttributeError, RuntimeError, TypeError):
            return None

    def _create_task_popup(self, label, actions):
        """Retain legacy helper without changing native QAction ownership."""
        menu = QMenu(label, self)
        for action in actions:
            if action.isSeparator():
                menu.addSeparator()
            else:
                menu.addAction(action)
        self._task_menus.append(menu)
        return menu

    def _add_task_group(self, row, label):
        group = RibbonTaskGroup(label, self)
        self._groups.append(group)
        self._native_groups.append(group)
        row.addWidget(group)
        return group

    @staticmethod
    def _is_native_command(action):
        return (not action.isSeparator() and action.isVisible()
                and action.objectName() not in ('QRibbonSkinToggle', 'QRibbonSkinRecoverToolbars')
                and not isinstance(action, QWidgetAction)
                and bool(native_caption(action.text())))

    def _claim_search_shortcut(self):
        """Alt+Q is handled by the active-window event filter.

        The QGIS Quit shortcut (Ctrl+Q) remains completely untouched.
        """
        self._suspended_quit_shortcut = None

    def _release_search_shortcut(self):
        """No native QGIS shortcuts were changed."""
        self._suspended_quit_shortcut = None

    def _make_quick_access(self):
        """Five native commands next to Project, without recreating QGIS shortcuts."""
        host = QFrame(self.tabs)
        host.setObjectName("QRibbonSkinQuickAccess")
        lay = QHBoxLayout(host)
        lay.setContentsMargins(2, 0, 5, 0)
        lay.setSpacing(1)
        for role in ('new', 'open', 'save', 'undo', 'redo'):
            action = self._quick_actions.get(role)
            btn = QToolButton(host)
            btn.setObjectName('QRibbonSkinQuick' + role.capitalize())
            btn.setAutoRaise(True)
            btn.setFixedSize(23, 22)
            btn.setIconSize(QSize(16, 16))
            if action is not None:
                btn.setDefaultAction(action)
                btn.setIcon(display_icon(action.icon(), action.text()))
                btn.setToolTip(native_caption(action.text()))
            else:
                # Keep the requested five-button geometry stable. Never
                # synthesize a command that is not backed by a QGIS QAction.
                btn.setEnabled(False)
                btn.setText(ui_label({'new': 'Novo Projeto', 'open': 'Abrir Projeto',
                             'save': 'Salvar Projeto', 'undo': 'Desfazer',
                             'redo': 'Refazer'}[role]))
                btn.setToolTip(btn.text() + ' (ação nativa indisponível)')
            btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
            lay.addWidget(btn)
        self.quick_host = host
        # Let QTabBar reserve the width rather than overlaying tab labels.
        self._position_quick_access()

    def _collect_workspace(self, roots):
        """Collect only user-requested native items for the Principal tab.

        A moved QMenu is still QGIS-owned.  Only its presentation reference is
        removed from its old Ribbon section, never from the original menu.
        """
        self._moved_action_ids = set()
        self._quick_actions = {}
        bins = {}
        clipboard = []
        edit_menu = self._safe_iface('editMenu')
        project_menu = self._safe_iface('projectMenu')
        view_menu = self._safe_iface('viewMenu')
        layer_menu = self._safe_iface('layerMenu')
        for role, accessor, caption in (
                ('new', 'actionNewProject', ('novo projeto', 'new project')),
                ('open', 'actionOpenProject', ('abrir projeto', 'open project')),
                ('save', 'actionSaveProject', ('salvar projeto', 'save project')),
                ('undo', 'actionUndo', ('desfazer', 'undo')),
                ('redo', 'actionRedo', ('refazer', 'redo'))):
            action = self._safe_iface(accessor)
            if action is not None and not isinstance(action, QAction):
                action = None
            if action is None:
                for _, menu in roots:
                    if menu not in (edit_menu, project_menu):
                        continue
                    action = next((a for a in menu.actions() if a.menu() is None and
                                   normalized(a.text()) in caption), None)
                    if action is not None:
                        break
            if action is None:
                # Undo/redo in QGIS can be nested or exposed under object names
                # such as mActionUndo instead of actionUndo. Search actions
                # without modifying their ownership or shortcut.
                candidates = self.iface.mainWindow().findChildren(QAction)
                tokens = {
                    'new': ('newproject', 'novoprojeto'),
                    'open': ('openproject', 'abrirprojeto'),
                    'save': ('saveproject', 'salvarprojeto'),
                    'undo': ('undo', 'desfazer'),
                    'redo': ('redo', 'refazer'),
                }[role]
                for candidate in candidates:
                    obj = normalized(candidate.objectName()).replace(' ', '')
                    name = normalized(candidate.text())
                    if candidate.isSeparator() or candidate.menu() is not None:
                        continue
                    if (any(token in obj for token in tokens) or
                            any(name == token or name.startswith(token + ' ')
                                for token in ('undo', 'redo', 'desfazer', 'refazer')
                                if role in ('undo', 'redo') and token in tokens)):
                        action = candidate
                        break
            if action is None:
                # Undo/Redo often reside in the Edit toolbar or layer-edit
                # toolbar, not as direct children of the Edit menu.
                role_terms = {
                    'new': ('newproject', 'novoprojeto'),
                    'open': ('openproject', 'abrirprojeto'),
                    'save': ('saveproject', 'salvarprojeto'),
                    'undo': ('undo', 'desfazer'),
                    'redo': ('redo', 'refazer'),
                }[role]
                candidates = self.iface.mainWindow().findChildren(QAction)
                action = next((a for a in candidates
                               if not a.isSeparator() and a.menu() is None
                               and any(term in normalized(a.objectName()).replace(' ', '')
                                       for term in role_terms)), None)
                if action is None:
                    action = next((a for a in candidates
                                   if not a.isSeparator() and a.menu() is None
                                   and normalized(a.text()) in caption), None)
            if action is not None:
                self._quick_actions[role] = action
        for root_title, root_menu in roots:
            if root_menu is view_menu:
                root_role = 'view'
            elif root_menu is layer_menu:
                root_role = 'layer'
            elif root_menu is edit_menu:
                root_role = 'edit'
            elif normalized(root_title) in ('raster', 'processing', 'processamento'):
                root_role = 'raster'
            else:
                root_role = ''
            if not root_role:
                continue
            sections = list(native_menu_sections(root_menu))
            if root_menu is self._safe_iface('rasterMenu'):
                sections = self._ordered_raster_sections(sections)
            for section_type, title, payload in sections:
                    if section_type == 'submenu':
                        action = payload.menuAction()
                        if root_role == 'edit' and principal_role('edit', title, submenu=True) == 'Selecionar':
                            bins.setdefault('Selecionar', []).append(('menu', payload, title))
                            self._moved_action_ids.add(id(action))
                        elif root_role == 'edit' and (clipboard_role(title) or normalized(title) in ('area de transferencia', 'clipboard', 'colar feicoes como', 'paste features as', 'exclusao de feicoes', 'delete features')):
                            clipboard.append(('menu', payload, title))
                            self._moved_action_ids.add(id(action))
                        else:
                            dest = principal_role(root_role, title, submenu=True)
                            if dest:
                                bins.setdefault(dest, []).append(('menu', payload, title))
                                self._moved_action_ids.add(id(action))
                            else:
                                # Some QGIS installations expose Georeferencer in
                                # a deeper Raster/Layer submenu rather than the
                                # menu root. Search one additional native level.
                                for child in payload.actions():
                                    if not child.isSeparator() and child.isVisible() and (
                                            'georrefer' in normalized(child.text()) or
                                            'georefer' in normalized(child.text())):
                                        bins.setdefault('Georreferenciador', []).append(
                                            ('menu' if child.menu() else 'action',
                                             child.menu() or child,
                                             native_caption(child.text())))
                                        self._moved_action_ids.add(id(child))
                        continue
                    section_destination = principal_role(root_role, title, submenu=True) if root_role in ('view', 'layer') else None
                    section_clipboard = root_role == 'edit' and bool(clipboard_role(title))
                    section_selection = root_role == 'edit' and principal_role('edit', title, submenu=True) == 'Selecionar'
                    for action in payload:
                        if not self._is_native_command(action):
                            continue
                        if root_role == 'edit':
                            if principal_role('edit', action.text()) == 'Selecionar' or section_selection:
                                bins.setdefault('Selecionar', []).append(('action', action, native_caption(action.text())))
                                self._moved_action_ids.add(id(action))
                            elif shortcut_role(action.text()):
                                role = shortcut_role(action.text())
                                if role not in self._quick_actions:
                                    self._quick_actions[role] = action
                                if self._quick_actions.get(role) is action:
                                    self._moved_action_ids.add(id(action))
                            elif clipboard_role(action.text()) or section_clipboard:
                                clipboard.append(('action', action, native_caption(action.text())))
                                self._moved_action_ids.add(id(action))
                        else:
                            dest = principal_role(root_role, action.text()) or section_destination
                            if not dest and root_role == 'raster' and (
                                    'georrefer' in normalized(action.text()) or
                                    'georefer' in normalized(action.text())):
                                dest = 'Georreferenciador'
                            if dest:
                                bins.setdefault(dest, []).append(('action', action, native_caption(action.text())))
                                self._moved_action_ids.add(id(action))
        # Public QgisInterface getters are a stable fallback when a QGIS
        # build/plugin has moved a tool out of its historical menu section.
        # Only fill missing groups: never duplicate a command already found.
        public_fallbacks = (
            ('Navegação do Mapa', 'actionPan'),
            ('Ver Tudo', 'actionZoomFullExtent'),
            ('Medir', 'actionMeasure'),
            ('Identificar Feições', 'actionIdentify'),
            ('Tabela de Atributos', 'actionOpenTable'),
            ('Edição de Camadas', 'actionToggleEditing'),
        )
        for heading, accessor in public_fallbacks:
            action = self._safe_iface(accessor)
            if isinstance(action, QAction):
                if not any(kind == 'action' and item is action for kind, item, _ in bins.get(heading, ())):
                    bins.setdefault(heading, []).insert(0, ('action', action, native_caption(action.text())))
                self._moved_action_ids.add(id(action))
        # Selection is commonly hosted in the Edit toolbar and may not be a
        # populated submenu during startup. Retrieve the original QGIS actions.
        selection_getters = (
            'actionSelect', 'actionSelectFeatures', 'actionSelectRectangle',
            'actionSelectPolygon', 'actionSelectFreehand', 'actionSelectRadius',
            'actionSelectByExpression', 'actionSelectByForm',
            'actionSelectAll', 'actionInvertSelection', 'actionDeselectAll',
        )
        for accessor in selection_getters:
            action = self._safe_iface(accessor)
            if isinstance(action, QAction) and self._is_native_command(action):
                entries = bins.setdefault('Selecionar', [])
                if not any(entry[1] is action for entry in entries):
                    entries.append(('action', action, native_caption(action.text())))
                self._moved_action_ids.add(id(action))
        if not bins.get('Selecionar'):
            # Fallback is restricted to selection-specific QAction names.
            for action in self.iface.mainWindow().findChildren(QAction):
                if (self._is_native_command(action) and action.menu() is None and
                        principal_role('edit', action.text()) == 'Selecionar'):
                    bins.setdefault('Selecionar', []).append(
                        ('action', action, native_caption(action.text())))
                    self._moved_action_ids.add(id(action))
        # QGIS may expose Processing Toolbox as an action on the Processing menu
        # rather than as a View action.
        if not bins.get('Caixa de Ferramentas'):
            for action in self.iface.mainWindow().findChildren(QAction):
                if self._is_native_command(action) and principal_role('view', action.text()) == 'Caixa de Ferramentas':
                    bins['Caixa de Ferramentas'] = [('action', action, native_caption(action.text()))]
                    self._moved_action_ids.add(id(action))
                    break
        for heading, accessor in (
                ('Criar Nova Camada', 'newLayerMenu'),
                ('Adicionar Camada', 'addLayerMenu')):
            if bins.get(heading):
                continue
            native_menu = self._safe_iface(accessor)
            if isinstance(native_menu, QMenu):
                bins[heading] = [('menu', native_menu, native_caption(native_menu.title()))]
                self._moved_action_ids.add(id(native_menu.menuAction()))
        if not bins.get('Georreferenciador'):
            for action in self.iface.mainWindow().findChildren(QAction):
                label = normalized(action.text())
                if (action.menu() is None and action.isVisible() and
                        ('georefer' in label or 'georrefer' in label)):
                    bins['Georreferenciador'] = [('action', action, native_caption(action.text()))]
                    self._moved_action_ids.add(id(action))
                    break
        # Edit shortcuts may be elsewhere but are still native QActions.
        for role in ('undo', 'redo'):
            action = self._quick_actions.get(role)
            if action is not None:
                self._moved_action_ids.add(id(action))
        # Deduplicate menu/action entries without changing QGIS-owned objects.
        unique_clipboard = {}
        for entry in clipboard:
            unique_clipboard.setdefault(id(entry[1]), entry)
        self._clipboard_items = sorted(
            unique_clipboard.values(), key=lambda row: clipboard_priority(row[2])
        )
        # Defensive exclusion of nested native menu actions: prevents a moved
        # command from resurfacing under its original Exibir/Camada section.
        for _, menu in roots:
            if menu not in (view_menu, layer_menu):
                continue
            role = 'view' if menu is view_menu else 'layer'
            for action in self._flatten_actions(menu):
                destination = principal_role(role, action.text(), submenu=bool(action.menu()))
                if not destination:
                    continue
                if not any(entry[1] is action or (action.menu() is not None and entry[1] is action.menu())
                           for entry in bins.get(destination, ())):
                    bins.setdefault(destination, []).append(
                        ('menu' if action.menu() else 'action', action.menu() or action,
                         native_caption(action.text())))
                self._moved_action_ids.add(id(action))
        # Print layouts: obtain live QGIS actions; preserve their ownership and
        # shortcuts.  Do not assume both methods exist in every QGIS release.
        layout_actions = []
        for accessor in ('actionNewPrintLayout', 'actionShowLayoutManager',
                         'actionLayoutManager'):
            action = self._safe_iface(accessor)
            if isinstance(action, QAction) and not any(a is action for a in layout_actions):
                layout_actions.append(action)
        if len(layout_actions) < 2:
            native_project = self._safe_iface('projectMenu')
            candidates = (self._recursive_menu_actions(native_project)
                          if isinstance(native_project, QMenu) else [])
            for action in candidates:
                if not isinstance(action, QAction) or action.isSeparator() or action.menu():
                    continue
                caption = normalized(action.text())
                is_new = (('novo' in caption or 'new' in caption)
                          and ('layout' in caption or 'compositor' in caption))
                is_manager = (('gerenciador' in caption or 'manager' in caption)
                              and ('layout' in caption or 'compositor' in caption))
                if (is_new or is_manager) and not any(a is action for a in layout_actions):
                    layout_actions.append(action)
        if layout_actions:
            def layout_order(action):
                caption = normalized(action.text())
                return 0 if ('novo' in caption or 'new' in caption) else 1
            layout_actions.sort(key=layout_order)
            bins['Layout de Impressão'] = [
                ('action', action, native_caption(action.text()))
                for action in layout_actions
            ]
        self._principal_bins = bins

    def _plain_native_actions(self, items):
        """Flatten native references for drop-downs, retaining QAction identity."""
        actions, seen = [], set()
        for kind, item, _caption in items:
            candidates = self._recursive_menu_actions(item) if kind == 'menu' else [item]
            for action in candidates:
                if (action is None or action.isSeparator() or action.menu() is not None
                        or id(action) in seen):
                    continue
                seen.add(id(action))
                actions.append(action)
        return actions

    def _edit_primary_group(self, row, heading, actions, primary_words):
        """Make one direct action with dropdown, never an overflow control."""
        if not actions:
            return False
        group = self._add_task_group(row, title_heading(tr(heading)))
        def score(action):
            caption = normalized(action.text())
            for index, phrase in enumerate(primary_words):
                if caption == phrase:
                    return index
            for index, phrase in enumerate(primary_words):
                if caption.startswith(phrase + ' '):
                    return len(primary_words) + index
            return 999
        primary = min(actions, key=score)
        group.add_primary_dropdown(primary, actions, heading)
        # Presentation-only caption: keep the QGIS QAction, its native text,
        # shortcut, tooltip and trigger unchanged in both locales.
        if heading == 'Editar Atributos' and group._lead is not None:
            group._lead.set_display_caption('Feições Selecionadas')
        return True

    def _edit_geometry_dropdown(self, row, heading, actions):
        """Compact Edit Geometry with the original Move Features QAction as lead."""
        if normalized(heading) not in ('editar geometria', 'edit geometry'):
            return False
        candidates = [a for a in actions if isinstance(a, QAction)
                      and not a.isSeparator() and not isinstance(a, QWidgetAction)]
        def is_move_features(action):
            name = action.objectName().lower()
            caption = normalized(action.text())
            return (name in ('mactionmovefeature', 'mactionmovefeatures',
                             'actionmovefeature', 'actionmovefeatures') or
                    caption in ('mover feicoes', 'mover feicao',
                                'move feature', 'move features'))
        primary = next((a for a in candidates if is_move_features(a)), None)
        if primary is None:
            primary = self._safe_iface('actionMoveFeature')
        if not isinstance(primary, QAction):
            return False  # Do not replace the native section with the wrong lead.
        ordered = [primary] + [a for a in candidates if a is not primary]
        group = self._add_task_group(row, title_heading(tr('Editar Geometria')))
        group.add_primary_dropdown(primary, ordered, 'Editar Geometria')
        if group._lead is not None:
            group._lead.set_display_caption('Mover Feições')
        return True

    def _edit_special_section(self, heading, actions):
        """Resolve the four requested edit sections, regardless of case/locale."""
        label = normalized(heading)
        titles = [normalized(a.text()) for a in actions]
        if ('adicionar anotacao' in label or 'add annotation' in label
                or ('anotacao de formulario' in ' '.join(titles) and 'html' in ' '.join(titles))):
            return ('Adicionar Anotação', ('anotacao de formulario', 'form annotation'))
        if ('editar atributos' in label or 'edit attributes' in label):
            return ('Editar Atributos', ('modificar atributos', 'modify attributes'))
        if ('simbologia de pontos' in label or 'point symbology' in label):
            return ('Simbologia de Pontos', ('rotacionar simbolos de pontos', 'rotate point symbols'))
        return None

    def _settings_special_section(self, row, heading, actions, native_menu=None):
        """Configurações only: compact profiles and equal-size paired actions.

        The source QAction/QMenu objects are reused; this alters presentation
        only and does not modify native menu behavior or shortcuts.
        """
        title = normalized(heading)
        if not actions:
            return False
        def captions(action):
            return normalized(action.text())
        if any(k in title for k in ('perfis de usuarios', 'user profiles', 'profiles')):
            primary = next((a for a in actions if captions(a) == 'default'), None)
            if primary is None:
                return False
            group = self._add_task_group(row, title_heading(tr('Perfis de Usuários')))
            # A native QGIS profiles submenu may populate on aboutToShow.
            # Keep that original submenu when available.
            if native_menu is not None:
                group.add_menu('Default', native_menu, primary.icon())
            else:
                group.add_primary_dropdown(primary, actions, 'Default')
                group._lead.set_display_caption('Default')
            group.content.setAlignment(Qt.AlignmentFlag.AlignHCenter)
            return True
        if any(k in title for k in ('gerenciador de estilos', 'style manager')):
            # The QGIS native menu combines unrelated tools. Present them as
            # TWO neighboring visual groups without moving/modifying QActions.
            manager_terms = ('gerenciador de estilos', 'style manager')
            projection_terms = ('personalizar projecoes', 'custom projections')
            manager = next((a for a in actions if any(k in captions(a) for k in manager_terms)), None)
            projection = next((a for a in actions if any(k in captions(a) for k in projection_terms)), None)
            if manager is None or projection is None:
                return False  # Do not discard unknown translated QGIS commands.
            manager_group = self._add_task_group(row, 'Gerenciador de Estilos')
            manager_group.add_action(manager)
            manager_group._lead.set_display_caption('Gerenciar')
            manager_group.content.setAlignment(Qt.AlignmentFlag.AlignHCenter)
            projection_group = self._add_task_group(row, 'Projeções')
            projection_group.add_action(projection)
            projection_group._lead.set_display_caption('Personalizar')
            projection_group.content.setAlignment(Qt.AlignmentFlag.AlignHCenter)
            # Preserve any additional native actions in the original section.
            for extra in actions:
                if extra is not manager and extra is not projection:
                    manager_group.add_action(extra)
            return True
        elif any(k in title for k in ('atalhos de teclado', 'keyboard shortcuts')):
            preferred = ('atalhos de teclado', 'keyboard shortcuts')
            secondary = ('personalizacao da interface', 'interface customization', 'customization')
            section = 'Atalhos de Teclado'
        else:
            return False
        first = next((a for a in actions if any(k in captions(a) for k in preferred)), None)
        second = next((a for a in actions if any(k in captions(a) for k in secondary)), None)
        if first is None:
            return False
        group = self._add_task_group(row, title_heading(tr(section)))
        group.add_action(first)
        if second is not None:
            self._settings_interface_action = second
        for action in actions:
            if action is not first and action is not second:
                group.add_action(action)
        group.content.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        return True

    def _view_visibility_dropdown(self, row, heading, actions):
        """Keep layer visibility commands in one native QAction-backed dropdown."""
        captions = [normalized(a.text()) for a in actions]
        title = normalized(heading)
        visibility_group = ('visibilidade da camada' in title or
                            'layer visibility' in title or
                            'visibility of layer' in title)
        if not visibility_group:
            return False
        def is_show_all(action):
            caption = normalized(action.text())
            return (caption in ('mostrar todas as camadas', 'show all layers') or
                    caption.startswith('mostrar todas as camadas ') or
                    caption.startswith('show all layers '))
        primary = next((a for a in actions if is_show_all(a)), None)
        if primary is None:
            # Do not create an unrelated leading action if QGIS changes its menu.
            return False
        group = self._add_task_group(row, title_heading(tr('Visibilidade da Camada')))
        group.add_primary_dropdown(primary, actions, 'Mostrar Todas as Camadas')
        return True

    def _view_consolidated_dropdown(self, row, heading, actions):
        """One primary split button for preview and filtering groups.

        Some QGIS translations call the temporal navigation section
        'Filtragem de Dados' rather than 'Temporal Controller'.
        """
        title = normalized(heading)
        if 'decoracoes' in title or 'decorations' in title:
            display_heading, key = 'Decorações', None
            names = ('malha', 'grid')
        elif any(term in title for term in ('modo de pre visualizacao',
                  'modo de previsualizacao', 'preview mode', 'preview modes')):
            display_heading, key = 'Modo de Pré-Visualização', 'preview'
            names = ('normal', 'normal mode', 'normal preview')
        elif any(term in title for term in ('filtragem de dados', 'data filtering',
                                           'temporal navigation')):
            display_heading, key = 'Filtragem de Dados', None
            names = ('controlador temporal', 'temporal controller')
        else:
            return False
        primary = next((a for a in actions
                        if normalized(a.text()) in names), None)
        if primary is None:
            return False
        extras = self._view_related_actions.get(key, ()) if key else ()
        group = self._add_task_group(row, title_heading(tr(display_heading)))
        group.add_primary_dropdown(primary, list(dict.fromkeys([*actions, *extras])),
                                   native_caption(primary.text()))
        self._moved_action_ids.update(id(a) for a in extras if a is not primary)
        return True

    def _view_requested_section(self, row, heading, actions):
        """Requested View-only consolidation; never changes native QAction text.

        Returns True only when the exact native primary action can be located.
        This avoids silently wiring a different command after translation changes.
        """
        title = normalized(heading)
        if not actions:
            return False

        def matches(action, words):
            caption = normalized(action.text())
            return any(caption == word or caption.startswith(word + ' ') for word in words)

        def primary_named(words):
            return next((a for a in actions if matches(a, words)), None)

        def dropdown(section_name, words, caption=None):
            primary = primary_named(words)
            if primary is None:
                return False
            group = self._add_task_group(row, title_heading(tr(section_name)))
            extras_key = {'Visualização': 'ultima', 'Dicas do Mapa': 'dicas',
                          'Visualização de Mapa 3D': '3d',
                          'Modo de Pré-Visualização': 'preview'}.get(section_name)
            additions = self._view_related_actions.get(extras_key, ()) if extras_key else ()
            all_actions = list(dict.fromkeys([*actions, *additions]))
            group.add_primary_dropdown(primary, all_actions, section_name)
            self._moved_action_ids.update(id(a) for a in additions if a is not primary)
            if caption is not None:
                group._lead.set_display_caption(caption)  # never modify QAction
            return True

        if title in ('nova visualizacao de mapa', 'new map view', 'vista de mapa'):
            primary = primary_named(('nova visualizacao de mapa', 'new map view'))
            if primary is None:
                return False
            group = self._add_task_group(row, title_heading(tr('Vista de Mapa')))
            group.add_action(primary)
            group._lead.set_display_caption('Novo')
            return True
        if ('visualizacao de mapa 3d' in title or '3d map view' in title
                or '3d map views' in title or 'visualizacoes de mapa 3d' in title):
            return dropdown('Visualização de Mapa 3D',
                            ('nova vista 3d', 'nova vista do mapa 3d', 'nova visualizacao do mapa 3d',
                             'new 3d map view', 'new 3d map'), 'Nova Vista 3D')
        if title in ('ultima visualizacao', 'last view', 'last zoom'):
            return dropdown('Visualização', ('ultima visualizacao', 'last view', 'zoom last'))
        if title in ('mostrar dicas do mapa', 'show map tips', 'map tips'):
            return dropdown('Dicas do Mapa', ('mostrar dicas do mapa', 'show map tips'))
        if title in ('paineis', 'panels', 'painels'):
            return dropdown('Painéis', ('camadas', 'layers'))
        if title in ('barra de ferramentas', 'barras de ferramentas',
                     'toolbars', 'toolbar'):
            return dropdown('Barras de Ferramentas', ('ajuda', 'help'))
        return False

    @staticmethod
    def _is_view_interface_section(heading, actions):
        title = normalized(heading)
        if 'ativar interface qribbonskin' in title or 'activate qribbonskin' in title:
            return True
        return any(normalized(a.text()) in ('ativar interface qribbonskin',
                    'activate qribbonskin interface') for a in actions)

    def _add_workspace_group(self, row, heading, items, prioritize=False):
        if not items:
            return
        group = self._add_task_group(row, title_heading(tr(heading)))
        # Four frequent clipboard commands remain directly accessible, other
        # (potentially provider-added) commands use the native live popup.
        if prioritize and len(items) > 4:
            group._inline_limit = 4
        else:
            group.configure_overflow(len(items))
        for kind, item, caption in items:
            if kind == 'menu':
                group.add_menu(caption, item, item.menuAction().icon())
            else:
                group.add_action(item)

    def _workspace_command_entries(self, items):
        """Flatten QGIS menu entries for presentation, without cloning QActions."""
        result = []
        seen = set()
        def visit(action):
            if action is None or action.isSeparator() or id(action) in seen:
                return
            seen.add(id(action))
            submenu = action.menu()
            if submenu is not None:
                # Keep the original submenu in the popup and inspect its actions
                # to locate the requested leader/secondary commands.
                for child in submenu.actions():
                    visit(child)
            else:
                result.append(action)
        for kind, item, _caption in items:
            if kind == 'menu':
                for action in item.actions():
                    visit(action)
            else:
                visit(item)
        return result

    def _add_principal_ergonomic_group(self, row, heading, items):
        """User-approved five-group layout; all commands remain QGIS-owned."""
        if not items:
            return
        group = self._add_task_group(row, title_heading(tr(heading)))
        actions = self._workspace_command_entries(items)
        if not actions:
            # Lazy native submenus remain available even before population.
            for kind, item, caption in items:
                if kind == 'menu':
                    group.add_menu(caption, item, item.menuAction().icon())
                else:
                    group.add_action(item)
            return
        labels = {
            'Navegação do Mapa': (('deslocar mapa', 'pan map', 'pan'),
                                  (('aproximar', 'zoom in'), ('afastar', 'zoom out'))),
            'Medir': (('medir area', 'measure area', 'area'), ()),
            'Criar Nova Camada': (('criar nova camada', 'new layer', 'nova camada'), ()),
            'Adicionar Camada': (('adicionar camada vetorial', 'add vector layer', 'camada vetorial', 'vector layer'), ()),
            'Tabela de Atributos': (('abrir tabela de atributos', 'open attribute table', 'attribute table'), ()),
            'Selecionar': (('selecionar feicao', 'selecionar feicoes', 'select feature', 'select features'), ()),
            'Layout de Impressão': (('novo layout', 'novo compositor', 'new print layout', 'new layout'), ()),
        }
        primary_words, secondaries = labels[heading]
        def caption(action):
            return normalized(native_caption(action.text()))
        def find_action(words, candidates):
            for word in words:
                for action in candidates:
                    if caption(action) == word:
                        return action
            for word in words:
                for action in candidates:
                    if word in caption(action):
                        return action
            return None
        # QGIS has several "Select..." commands with similar translated
        # captions.  String matching can accidentally select "By Expression"
        # as the Ribbon default.  Resolve the actual QGIS select-features
        # QAction instead of guessing from captions or toolbar ordering.
        if heading == 'Selecionar':
            leader = self._safe_iface('actionSelect')
            if not isinstance(leader, QAction):
                # Exact native objectName (QGIS 4.x): mActionSelectFeatures.
                # Account for a menu that was not yet populated at startup.
                candidates = actions + self.iface.mainWindow().findChildren(QAction)
                leader = next((action for action in candidates
                               if action.objectName() == 'mActionSelectFeatures'), None)
            if leader is None:
                # Strict exact-text compatibility fallback: never promote
                # Select by Expression/Value to the main button.
                leader = next((action for action in actions
                               if caption(action) in ('selecionar feicao',
                                                      'selecionar feicoes',
                                                      'selecionar feicao(s)',
                                                      'select feature',
                                                      'select features',
                                                      'feicao(s)')), None)
            if leader is not None and all(action is not leader for action in actions):
                actions.insert(0, leader)
        elif heading == 'Medir':
            # Match Area exactly first (not azimuth, angle or line). The
            # public QgisInterface action is a fallback for menu variations.
            leader = find_action(('area', 'medir area', 'measure area'), actions)
            if leader is None:
                native_area = self._safe_iface('actionMeasureArea')
                if isinstance(native_area, QAction):
                    leader = native_area
                    actions.append(native_area)
        else:
            leader = find_action(primary_words, actions)
        if leader is None:
            # A submenu may be registered but not populated yet; retain full
            # original UI rather than silently dropping its commands.
            for kind, item, caption_text in items:
                if kind == 'menu':
                    group.add_menu(caption_text, item, item.menuAction().icon())
                else:
                    group.add_action(item)
            return
        if not secondaries:
            if heading == 'Medir':
                # The Area button invokes the native QGIS measurement action;
                # all other commands live in its dropdown, including Line.
                other_actions = [action for action in actions if action is not leader]
                aliases = {}
                line = find_action(('medir linha', 'measure line',
                                    'medir distancia', 'measure distance',
                                    'linha', 'line'), other_actions)
                if line is not None:
                    aliases[id(line)] = 'Linha'
                group.add_primary_dropdown(leader, other_actions,
                                           menu_caption_overrides=aliases)
            elif heading == 'Selecionar':
                # The lead is exclusively Select Features; the arrow exposes
                # the remaining selection methods without duplicating it.
                group.add_primary_dropdown(
                    leader, [action for action in actions if action is not leader])
            else:
                group.add_primary_dropdown(leader, actions)
            if heading == 'Adicionar Camada' and group._lead is not None:
                group._lead.set_display_caption('Camada Vetorial')
            elif heading == 'Selecionar' and group._lead is not None:
                group._lead.set_display_caption('Feição(s)')
            elif heading == 'Medir' and group._lead is not None:
                group._lead.set_display_caption('Área')
            elif heading == 'Layout de Impressão' and group._lead is not None:
                group._lead.set_display_caption('Novo Layout')
            return
        group.add_action(leader)
        if heading == 'Medir' and group._lead is not None:
            group._lead.set_display_caption('Medir Linha')
        chosen = {id(leader)}
        for words in secondaries:
            action = find_action(words, [a for a in actions if id(a) not in chosen])
            if action is not None:
                group.add_action(action)
                chosen.add(id(action))
        # Explicit overflow even for small groups, as specified by the user.
        remainder = [a for a in actions if id(a) not in chosen]
        if remainder:
            group._overflow_items = [('action', action) for action in remainder]
            group._ensure_overflow_menu()
        group._recalculate_group_width()

    def _build_principal_page(self):
        row = self._new_tab('Principal', native=True)
        self._principal_page = self._native_pages[-1]
        order = ('Criar Nova Camada', 'Adicionar Camada',
                 'Navegação do Mapa', 'Ver Tudo', 'Edição de Camadas',
                 'Vetorização', 'Selecionar', 'Medir', 'Identificar Feições',
                 'Tabela de Atributos', 'Georreferenciador',
                 'Caixa de Ferramentas', 'Layout de Impressão')
        # Explicitly unique headings prevent repeated tool sections.
        order = tuple(dict.fromkeys(order))
        for heading in order:
            if heading == 'Vetorização':
                # Present the same native QGIS actions in Principal and Editar.
                # QActions may have multiple presentation widgets; their
                # ownership, shortcuts and enabled/checked state stay native.
                self._add_edit_digitizing_toolbars(row, only_heading='Vetorização')
                continue
            if heading in ('Navegação do Mapa', 'Medir', 'Selecionar', 'Criar Nova Camada',
                           'Adicionar Camada', 'Tabela de Atributos',
                           'Layout de Impressão'):
                self._add_principal_ergonomic_group(row, heading, self._principal_bins.get(heading, ()))
            else:
                items = self._principal_bins.get(heading, ())
                if heading == 'Edição de Camadas':
                    # Prevent duplicate Toggle Editing within Principal: it is
                    # now presented by the separate Vetorização group.
                    toggle = self._safe_iface('actionToggleEditing')
                    items = [(kind, action, caption) for kind, action, caption in items
                             if action is not toggle and not (
                                 kind == 'action' and normalized(action.text()) in
                                 ('alternar edicao', 'toggle editing'))]
                self._add_workspace_group(row, heading, items)
        row.addStretch(1)

    @staticmethod
    def _layer_heading_kind(heading):
        value = normalized(heading)
        if value in ('gerenciador de fonte de dados', 'gerenciador de fontes de dados',
                     'data source manager', 'data source manager toolbar'):
            return 'source'
        if value in ('incorporar camadas e grupos', 'embed layers and groups',
                     'embed layers groups'):
            return 'embed'
        if value in ('area de transferencia', 'clipboard', 'copiar camada',
                     'copy layer', 'copiar camadas', 'copy layers'):
            return 'clipboard'
        if value in ('edicoes atuais', 'current edits', 'current edits toolbar'):
            return 'edits'
        return None

    def _layer_save_all_action(self, candidates):
        """Find QGIS Save All Edits, not Save Selected Layer Edits.

        QGIS may translate QAction captions; prefer its public iface accessor
        and then stable QObject names instead of relying on caption alone.
        """
        for accessor in ('actionSaveAllEdits', 'actionSaveAllLayerEdits'):
            candidate = self._safe_iface(accessor)
            if isinstance(candidate, QAction):
                return candidate
        for action in candidates:
            key = normalized(action.objectName())
            if ('savealledits' in key.replace(' ', '') or
                    'savealllayeredits' in key.replace(' ', '')):
                return action
        for action in candidates:
            caption = normalized(action.text())
            if (('salvar' in caption and 'todas' in caption and 'camad' in caption)
                    or ('save' in caption and 'all' in caption and
                        ('edit' in caption or 'layer' in caption))):
                return action
        return None

    def _layer_single_group(self, row, label, action, menu_actions=None, button_label=None):
        group = self._add_task_group(row, label)
        if menu_actions:
            group.add_primary_dropdown(action, menu_actions, button_label)
        else:
            group.add_action(action)
            group.content.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        if button_label and not menu_actions:
            group._lead.set_display_caption(button_label)
        return group

    @staticmethod
    def _vector_section_config(heading):
        """Presentation-only names and primary action for Vector groups."""
        value = normalized(heading)
        configs = (
            (('geometry shapes', 'formas de geometria'), 'Formas de Geometria', 'Desenhar Retângulo', ('draw rectangle', 'desenhar retangulo', 'rectangle')),
            (('kml tools',), 'KML Tools', 'Import KML/KMZ', ('import kml/kmz', 'import kml', 'importar kml')),
            (('ferramentas de analise', 'analysis tools'), 'Ferramentas de Análise', 'Estatísticas Básicas', ('estatisticas basicas', 'basic statistics', 'basic statistics for fields')),
            (('ferramentas de geoprocessamento', 'geoprocessing tools'), 'Ferramentas de Geoprocessamento', 'Buffer', ('buffer',)),
            (('ferramentas de geometria', 'geometry tools'), 'Ferramentas de Geometria', 'Centroides', ('centroides', 'centroids')),
            (('ferramentas de investigacao', 'research tools'), 'Ferramentas de Investigação', 'Criar Grade', ('criar grade', 'create grid', 'vector grid')),
            (('ferramentas de gestao de dados', 'data management tools'), 'Ferramentas de Gestão de Dados', 'Criar Índices Espaciais', ('criar indices espaciais', 'create spatial index', 'spatial indexes')),
        )
        for aliases, title, caption, primary_aliases in configs:
            if any(alias in value for alias in aliases):
                return title, caption, primary_aliases
        return None

    def _vector_compact_group(self, row, heading, actions):
        """Show only one centered button with all original QGIS actions in its popup."""
        config = self._vector_section_config(heading)
        if not config or not actions:
            return False
        title, caption, aliases = config
        candidates = [a for a in actions if a is not None and not a.isSeparator()]
        if not candidates:
            return False
        def score(action):
            value = normalized(action.text())
            for i, alias in enumerate(aliases):
                if value == alias:
                    return i
            for i, alias in enumerate(aliases):
                if alias in value:
                    return len(aliases) + i
            return 999
        primary = min(candidates, key=score)
        # If a plugin changes translations, do not silently select an unrelated action.
        if score(primary) == 999:
            return False
        group = self._add_task_group(row, title)
        group.add_primary_dropdown(primary, candidates, caption)
        if group._lead is not None:
            group._lead.set_display_caption(caption)
        return True

    @staticmethod
    def _raster_section_config(heading):
        value = normalized(heading)
        definitions = (
            (('analise', 'analysis'), 'Declividade', ('declividade', 'slope')),
            (('projecoes', 'projecao', 'projections', 'projection'), 'Definir Projeção', ('definir projecao', 'assign projection', 'define projection')),
            (('miscelanea', 'miscellaneous'), 'Mosaico', ('mosaico', 'merge', 'mesclar', 'merge raster', 'merge rasters')),
            (('extracao', 'extraction'), 'Contorno', ('contorno', 'contour')),
            (('conversao', 'conversion'), 'PCT para RGB', ('pct para rgb', 'pct to rgb')),
            (('alinhar raster', 'alinhar rasters', 'align raster', 'align rasters', 'raster alignment'), 'Alinhar', ('alinhar rasters', 'align rasters', 'align raster')),
        )
        for titles, caption, aliases in definitions:
            if value in titles or any(value.startswith(name + ' ') for name in titles):
                return caption, aliases
        return None

    def _raster_compact_group(self, row, heading, actions):
        config = self._raster_section_config(heading)
        if not config or not actions:
            return False
        caption, aliases = config
        choices = [action for action in actions if action is not None and not action.isSeparator()]
        candidates = [action for action in choices if action.menu() is None]
        def rank(action):
            label = normalized(action.text())
            for index, alias in enumerate(aliases):
                if label == alias:
                    return index
            for index, alias in enumerate(aliases):
                if alias in label:
                    return index + len(aliases)
            return 999
        primary = min(candidates, key=rank) if candidates else None
        if primary is None or rank(primary) == 999:
            return False
        group = self._add_task_group(row, heading)
        if len(choices) > 1:
            group.add_primary_dropdown(primary, choices, caption)
        else:
            group.add_action(primary)
            group.content.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        if group._lead is not None:
            group._lead.set_display_caption(caption)
        return True

    @staticmethod
    def _raster_plugin_install_time(title):
        """Best-effort directory timestamp for a confidently identified installed plugin.

        Directory times are not guaranteed install times after upgrades or copies;
        unmatched sections retain menu order rather than receiving invented dates.
        """
        try:
            from qgis.core import QgsApplication
            roots = QgsApplication.pluginPath().split(os.pathsep)
            user_plugins = os.path.join(QgsApplication.qgisSettingsDirPath(), 'python', 'plugins')
            if user_plugins not in roots:
                roots.append(user_plugins)
        except Exception:
            return None
        target = normalized(title)
        for root in roots:
            if not os.path.isdir(root):
                continue
            for entry in os.scandir(root):
                if not entry.is_dir():
                    continue
                metadata = os.path.join(entry.path, 'metadata.txt')
                if not os.path.isfile(metadata):
                    continue
                parser = configparser.ConfigParser(interpolation=None)
                try:
                    parser.read(metadata, encoding='utf-8')
                    name = parser.get('general', 'name', fallback='')
                    if normalized(name) == target or normalized(entry.name) == target:
                        return os.stat(entry.path).st_ctime
                except (OSError, ValueError, configparser.Error):
                    continue
        return None

    @staticmethod
    def _raster_order_role(title):
        """Identify only the seven explicitly requested native Raster groups."""
        value = normalized(title)
        names = (
            ('calculadora raster', 'raster calculator'),
            ('analise', 'analysis'),
            ('projecoes', 'projecao', 'projections', 'projection'),
            ('miscelanea', 'miscellaneous'),
            ('extracao', 'extraction'),
            ('conversao', 'conversion'),
            ('alinhar raster', 'alinhar rasters', 'align rasters', 'raster alignment'),
        )
        for rank, aliases in enumerate(names):
            if value in aliases or any(value.startswith(alias + ' ') for alias in aliases):
                return rank
        return None

    def _ordered_raster_sections(self, sections):
        """Explicit user order first, with every other section kept in source order.

        This must be called while *rendering*, not only when scanning menus.
        """
        indexed = list(enumerate(sections))
        def key(item):
            index, (_, title, _) = item
            role = self._raster_order_role(title)
            return (0, role, index) if role is not None else (1, index, index)
        return [section for _, section in sorted(indexed, key=key)]

    def _reorder_rendered_raster_groups(self, row):
        """Arrange actual group widgets after QGIS menus/plugins have been rendered.

        Unlike sorting menu-section input, this also covers commands which QGIS
        exposes as late submenus or dynamically added plugin actions. Existing
        group widgets and QAction ownership remain unchanged.
        """
        widgets = []
        for index in range(row.count()):
            item = row.itemAt(index)
            widget = item.widget() if item is not None else None
            if isinstance(widget, RibbonTaskGroup):
                widgets.append(widget)
        if not widgets:
            return
        def order(item):
            index, group = item
            title = getattr(group, '_heading', '')
            role = self._raster_order_role(title)
            return (0, role, index) if role is not None else (1, index, index)
        desired = [group for _, group in sorted(enumerate(widgets), key=order)]
        if widgets == desired:
            return
        for group in widgets:
            row.removeWidget(group)
        for position, group in enumerate(desired):
            row.insertWidget(position, group)

    def _add_snapping_widget_proxy(self, group, source):
        """Mirror toolbar widgets without moving QGIS-owned controls.

        QToolButton menus stay native and live. Checkboxes and comboboxes
        use small synchronized proxies because Qt widgets have one parent.
        Unrecognized widget types are not rendered as empty menu rows.
        """
        if isinstance(source, QToolButton):
            native_action = source.defaultAction()
            native_menu = source.menu()
            if native_menu is None and isinstance(native_action, QAction):
                native_menu = native_action.menu()
            if native_menu is not None:
                caption = (native_caption(source.text()) or
                           native_caption(native_action.text()) if native_action is not None
                           else native_caption(source.text()))
                group.add_menu(caption or native_caption(native_menu.title()) or
                               'Ferramentas de Aderência', native_menu, source.icon())
            elif isinstance(native_action, QAction):
                group.add_action(native_action)
            return
        if isinstance(source, QComboBox):
            proxy = QComboBox(group)
            proxy.setToolTip(source.toolTip())
            proxy.setMinimumWidth(max(105, min(185, source.sizeHint().width())))
            def refill():
                proxy.blockSignals(True)
                proxy.clear()
                for index in range(source.count()):
                    proxy.addItem(source.itemIcon(index), source.itemText(index),
                                  source.itemData(index))
                    proxy.setItemData(index, source.itemData(index, Qt.ItemDataRole.ToolTipRole),
                                      Qt.ItemDataRole.ToolTipRole)
                proxy.setCurrentIndex(source.currentIndex())
                proxy.setEnabled(source.isEnabled())
                proxy.blockSignals(False)
            refill()
            proxy.currentIndexChanged.connect(source.setCurrentIndex)
            source.currentIndexChanged.connect(proxy.setCurrentIndex)
            source.model().rowsInserted.connect(lambda *_args: refill())
            source.model().rowsRemoved.connect(lambda *_args: refill())
            source.model().modelReset.connect(refill)
            group.content.addWidget(proxy)
            group._recalculate_group_width()
            return
        if isinstance(source, QCheckBox):
            proxy = QCheckBox(source.text(), group)
            proxy.setToolTip(source.toolTip())
            proxy.setChecked(source.isChecked())
            proxy.toggled.connect(source.setChecked)
            source.toggled.connect(proxy.setChecked)
            group.content.addWidget(proxy)
            group._recalculate_group_width()
            return
        # QGIS versions may introduce other specialized toolbar widgets.
        # Do not misrepresent them with an inert control or steal ownership.
        QgsMessageLog.logMessage(
            'Unsupported Snapping toolbar widget: ' + type(source).__name__,
            'QRibbonSkin', Qgis.MessageLevel.Warning)

    def _snapping_menu_label(self, action=None, widget=None, native_menu=None):
        """Provide a readable caption without changing QGIS-owned actions."""
        candidates = []
        if action is not None:
            candidates.extend((action.text(), action.toolTip(), action.statusTip()))
        if widget is not None:
            candidates.extend((widget.toolTip(), widget.whatsThis(), widget.objectName()))
        if native_menu is not None:
            candidates.extend((native_menu.title(), native_menu.toolTip()))
        for candidate in candidates:
            caption = native_caption(candidate or '').strip()
            if caption:
                return caption
        return 'Opções de Aderência'

    def _append_snapping_menu_control(self, menu, source):
        """Mirror QGIS-owned toolbar controls as proper selectable menu actions.

        Embedding QComboBox via QWidgetAction inside QMenu loses keyboard/mouse
        interaction in certain QGIS/Qt6 configurations. Build a real submenu
        of checkable actions instead, refreshed each time it opens.
        """
        if isinstance(source, QToolButton):
            native_menu = source.menu()
            native_action = source.defaultAction()
            if native_menu is None and isinstance(native_action, QAction):
                native_menu = native_action.menu()
            if native_menu is not None:
                link = QAction(self._snapping_menu_label(native_action, source, native_menu), menu)
                link.setIcon(source.icon())
                link.setMenu(native_menu)
                menu.addAction(link)
                return True
            if isinstance(native_action, QAction):
                if native_caption(native_action.text()):
                    menu.addAction(native_action)
                    return True
        if isinstance(source, QComboBox):
            caption = self._snapping_menu_label(widget=source)
            if caption == 'Opções de Aderência' and any(
                    source.itemText(i).strip().lower() in ('px', 'pixels', 'm', 'metros', 'meters')
                    for i in range(source.count())):
                caption = 'Unidades de aderência'
            submenu = QMenu(caption, menu)
            def populate():
                submenu.clear()
                for index in range(source.count()):
                    label = source.itemText(index).strip()
                    if not label:
                        label = source.itemData(index, Qt.ItemDataRole.ToolTipRole) or f'Opção {index + 1}'
                    item = QAction(source.itemIcon(index), str(label), submenu)
                    item.setCheckable(True)
                    item.setChecked(index == source.currentIndex())
                    item.setEnabled(source.isEnabled())
                    item.triggered.connect(lambda _checked=False, selected=index: source.setCurrentIndex(selected))
                    submenu.addAction(item)
                if submenu.isEmpty():
                    empty = submenu.addAction('Nenhuma opção disponível')
                    empty.setEnabled(False)
            submenu.aboutToShow.connect(populate)
            menu.addMenu(submenu)
            return True
        if isinstance(source, QCheckBox):
            action = QAction(self._snapping_menu_label(widget=source), menu)
            action.setCheckable(True)
            action.setChecked(source.isChecked())
            action.setEnabled(source.isEnabled())
            action.toggled.connect(source.setChecked)
            source.toggled.connect(action.setChecked)
            menu.addAction(action)
            return True
        return False

    def _add_edit_digitizing_toolbars(self, row, only_heading=None):
        """Expose native QGIS digitizing toolbar actions in Ribbon groups.

        With ``only_heading='Vetorização'``, reuse the exact same native
        QActions in Principal while retaining the full set in Editar.
        Toolbars and QActions remain owned by QGIS; no actions are cloned.
        """
        toolbars = self.iface.mainWindow().findChildren(QToolBar)
        roles = (
            ('Vetorização', ('mdigitizetoolbar', 'digitizetoolbar'),
             ('digitizing', 'digitalizacao', 'digitalização', 'vetorizacao', 'vetorização')),
            ('Vetorização Avançada', ('madvanceddigitizetoolbar', 'advanceddigitizetoolbar'),
             ('advanced digitizing', 'digitalizacao avancada', 'digitalização avançada',
              'vetorizacao avancada', 'vetorização avançada')),
            ('Aderência', ('msnappingtoolbar', 'snappingtoolbar'),
             ('snapping', 'aderencia', 'aderência')),
        )
        taken = set()
        for heading, object_names, captions in roles:
            if only_heading is not None and heading != only_heading:
                continue
            selected = None
            for toolbar in toolbars:
                if id(toolbar) in taken:
                    continue
                name = toolbar.objectName().lower()
                title = normalized(toolbar.windowTitle())
                if (name in object_names or
                    any(label in title for label in captions)):
                    # Plain digitizing should not capture Advanced Digitizing.
                    if heading == 'Vetorização' and ('advanced' in name or 'advanced' in title
                                                     or 'avancad' in title):
                        continue
                    selected = toolbar
                    break
            if selected is None:
                continue
            taken.add(id(selected))
            # Native QToolBar actions include QMenu-bearing dropdowns and
            # QWidgetAction controls.  Dropping either kind loses QGIS snapping
            # tools, even though the toolbar itself is correctly discovered.
            # Preserve them for the Snapping group while keeping the existing
            # consolidated presentations of the two digitizing groups.
            toolbar_actions = [action for action in selected.actions()
                               if isinstance(action, QAction) and not action.isSeparator()]
            actions = [action for action in toolbar_actions
                       if not isinstance(action, QWidgetAction)
                       and action.menu() is None and bool(native_caption(action.text()))]
            if heading == 'Aderência':
                # Compact layout: one main native toggle with a single popup.
                # QWidgetAction contents need menu-local proxies, not the
                # toolbar-owned widgets themselves (which yield blank rows).
                toggle = self._safe_iface('actionSnapping')
                if not isinstance(toggle, QAction):
                    toggle = next((action for action in toolbar_actions
                                   if not isinstance(action, QWidgetAction)
                                   and ('snapping' in normalized(action.text())
                                        or 'aderencia' in normalized(action.text()))
                                   and ('toggle' in normalized(action.text())
                                        or 'alternar' in normalized(action.text()))), None)
                if not isinstance(toggle, QAction):
                    toggle = next((action for action in toolbar_actions
                                   if not isinstance(action, QWidgetAction)
                                   and action.isCheckable() and action.menu() is None), None)
                group = self._add_task_group(row, title_heading(tr(heading)))
                popup = QMenu('Aderência', group)
                seen = set()
                if isinstance(toggle, QAction):
                    popup.addAction(toggle)
                    seen.add(id(toggle))
                for action in toolbar_actions:
                    if id(action) in seen:
                        continue
                    seen.add(id(action))
                    native_widget = selected.widgetForAction(action)
                    if isinstance(action, QWidgetAction):
                        if native_widget is None:
                            native_widget = action.defaultWidget()
                        if native_widget is not None:
                            self._append_snapping_menu_control(popup, native_widget)
                        continue
                    submenu = action.menu()
                    if submenu is None and isinstance(native_widget, QToolButton):
                        submenu = native_widget.menu()
                    if submenu is not None:
                        # QAction text can be empty even when its native QMenu
                        # is functional. Never add an unlabeled row to Ribbon.
                        label = self._snapping_menu_label(action, native_widget, submenu)
                        if native_caption(action.text()).strip():
                            popup.addAction(action)
                        else:
                            link = QAction(label, popup)
                            link.setIcon(action.icon())
                            link.setMenu(submenu)
                            popup.addAction(link)
                    elif native_caption(action.text()):
                        popup.addAction(action)
                if isinstance(toggle, QAction):
                    # A menu-button has a direct native action plus arrow.
                    button = RibbonActionButton(group)
                    button.setDefaultAction(toggle)
                    button.setMenu(popup)
                    button.setPopupMode(QToolButton.ToolButtonPopupMode.MenuButtonPopup)
                    button.set_caption_color(QColor(light_palette()['text']))
                    group._original_item_count += 1
                    group._append(button)
                    button.set_display_caption('Alternar Aderência')
                    group.content.setAlignment(Qt.AlignmentFlag.AlignHCenter)
                elif not popup.isEmpty():
                    group.add_menu('Aderência', popup)
                continue
            if heading == 'Vetorização':
                # Prefer the official QgisInterface action; locate by label as a
                # fallback for builds with translated or reorganized toolbars.
                toggle = self._safe_iface('actionToggleEditing')
                if not isinstance(toggle, QAction):
                    toggle = next((action for action in actions if
                                   normalized(action.text()) in
                                   ('alternar edicao', 'toggle editing')), None)
                if isinstance(toggle, QAction):
                    choices = [toggle] + [action for action in actions if action is not toggle]
                    group = self._add_task_group(row, title_heading(tr(heading)))
                    group.add_primary_dropdown(toggle, choices)
                    if group._lead is not None:
                        group._lead.set_display_caption('Alternar Edição')
                    continue
            if heading == 'Vetorização Avançada' and actions:
                # Use the original QGIS Split Features QAction for the main control.
                # Prefer the official interface method, then objectName and
                # translated text, as QGIS versions may expose it differently.
                split = self._safe_iface('actionSplitFeatures')
                if not isinstance(split, QAction):
                    split = next((action for action in actions
                                  if action.objectName().lower() in
                                  ('mactionsplitfeatures', 'actionsplitfeatures')), None)
                if not isinstance(split, QAction):
                    split = next((action for action in actions
                                  if normalized(action.text()) in
                                  ('quebrar feicoes', 'dividir feicoes', 'split features')), None)
                if not isinstance(split, QAction):
                    split = next((action for action in
                                  self.iface.mainWindow().findChildren(QAction)
                                  if action.objectName().lower() == 'mactionsplitfeatures'), None)
                if isinstance(split, QAction):
                    choices = [split] + [action for action in actions if action is not split]
                    group = self._add_task_group(row, title_heading(tr(heading)))
                    group.add_primary_dropdown(split, choices)
                    if group._lead is not None:
                        group._lead.set_display_caption('Quebrar Feições')
                    continue
            if actions:
                self._add_workspace_group(
                    row, heading,
                    [('action', action, native_caption(action.text())) for action in actions])

    def _append_native_menu(self, row, root_title, root_menu, seen):
        """Render native submenu hierarchy without moving QGIS actions.

        Root separators become semantically labeled action sections;
        first-level QMenus retain their titles unless duplicated; deeper
        menus remain live dropdowns. Widget-based or
        initially empty menus stay available through their original popup.
        The original QMenuBar determines placement and translated captions.
        """
        is_raster_root = self._is_raster_root(root_menu, root_title)
        is_edit_root = root_menu is self._safe_iface('editMenu')
        is_plugins_root = (root_menu is self._safe_iface('pluginMenu')
                           or normalized(root_title) in ('complementos', 'plugins'))
        digitizing_inserted = False
        populated = False
        # Keep the plugin manager visible even if QGIS briefly rearranges its
        # native menu while plugins register actions. This is QGIS's own QAction,
        # not a proxy command, and is added only once per native tab rebuild.
        manage_plugins = self._safe_iface('actionManagePlugins') if is_plugins_root else None
        if isinstance(manage_plugins, QAction):
            manager = self._add_task_group(row, 'Complementos')
            manager.add_action(manage_plugins)
            if manager._lead is not None:
                manager._lead.set_display_caption('Gerenciar e Instalar')
            seen.add(id(manage_plugins))
            populated = True
        used_headings = set()
        is_layer_root = root_menu is self._safe_iface('layerMenu')
        layer_clipboard = []
        layer_clipboard_ids = set()
        if is_layer_root:
            # Collect both native clipboard sections before rendering either.
            # No native QAction is modified or moved from QGIS menus.
            for kind, section_title, section_payload in native_menu_sections(root_menu):
                if self._layer_heading_kind(section_title) != 'clipboard':
                    continue
                source_actions = (section_payload if kind == 'actions'
                                  else self._recursive_menu_actions(section_payload))
                for candidate in source_actions:
                    if (self._is_native_command(candidate)
                            and id(candidate) not in layer_clipboard_ids):
                        layer_clipboard.append(candidate)
                        layer_clipboard_ids.add(id(candidate))
        layer_clipboard_added = False

        def add_layer_clipboard():
            nonlocal populated, layer_clipboard_added
            if layer_clipboard_added or not layer_clipboard:
                return
            paste = next((a for a in layer_clipboard if normalized(a.text())
                          in ('colar', 'paste', 'colar feicoes', 'paste features')), None)
            if paste is None:
                paste = next((a for a in layer_clipboard if normalized(a.text()).startswith(('colar', 'paste'))), None)
            if paste is None:
                # Preserve commands rather than presenting a non-functional paste.
                self._add_workspace_group(row, 'Área de Transferência',
                    [('action', a, native_caption(a.text())) for a in layer_clipboard])
            else:
                ordered = [paste] + [a for a in layer_clipboard if a is not paste]
                self._layer_single_group(row, 'Área de Transferência', paste,
                                         ordered, 'Colar')
            seen.update(layer_clipboard_ids)
            populated = True
            layer_clipboard_added = True
        if root_menu is self._safe_iface('editMenu') and self._clipboard_items:
            actions = self._plain_native_actions(self._clipboard_items)
            def clipboard_order(action):
                caption = normalized(action.text())
                if caption in ('colar feicoes', 'paste features', 'colar', 'paste'):
                    return -20
                if caption.startswith(('recortar', 'cut')):
                    return 0
                if caption.startswith(('copiar caminho', 'copy path')):
                    return 2
                if caption.startswith(('copiar', 'copy')):
                    return 1
                return 10
            actions.sort(key=clipboard_order)
            paste = next((a for a in actions if normalized(a.text()) in
                          ('colar feicoes', 'paste features', 'colar', 'paste')), None)
            if paste is not None:
                group = self._add_task_group(row, title_heading(tr('Área de Transferência')))
                group.add_primary_dropdown(paste, actions, 'Colar Feições')
                # Only the three secondary shortcuts of the supplied visual
                # reference are shown next to the main Paste dropdown.
                for role in ('recortar', 'copiar', 'copiar caminho'):
                    match = next((a for a in actions if
                                  (normalized(a.text()).startswith(role) if role != 'copiar' else
                                   normalized(a.text()) in ('copiar', 'copy', 'copiar feicoes', 'copy features'))), None)
                    if match is not None and match is not paste:
                        group.add_action(match)
            else:
                self._add_workspace_group(row, 'Área de Transferência',
                                          self._clipboard_items, prioritize=True)
            populated = True
            used_headings.add(title_heading(tr('Área de Transferência')))
        sections_for_display = list(native_menu_sections(root_menu))
        if is_raster_root:
            sections_for_display = self._ordered_raster_sections(sections_for_display)
        for section_type, title, payload in sections_for_display:
            # Suppress only the redundant native manager submenu. Other plugin
            # categories retain their own menus, including lazy placeholders.
            if (is_plugins_root and isinstance(manage_plugins, QAction)
                    and normalized(title) in ('gerenciar e instalar complementos',
                                              'manage and install plugins',
                                              'manage plugins', 'gerenciar complementos')):
                source_actions = (payload if section_type == 'actions'
                                  else self._recursive_menu_actions(payload))
                if not source_actions or all(a is manage_plugins for a in source_actions):
                    continue
            if is_edit_root and not digitizing_inserted:
                section_label = normalized(title)
                section_actions = (payload if section_type == 'actions'
                                   else self._recursive_menu_actions(payload))
                is_attributes = ('editar atributos' in section_label or
                                 'edit attributes' in section_label or
                                 any(self._edit_special_section(title, [a]) is not None and
                                     self._edit_special_section(title, [a])[0] == 'Editar Atributos'
                                     for a in section_actions if isinstance(a, QAction)))
                if is_attributes:
                    self._add_edit_digitizing_toolbars(row)
                    digitizing_inserted = True
            if section_type == "actions":
                actions = [a for a in payload
                           if self._is_native_command(a) and id(a) not in seen
                           and id(a) not in self._moved_action_ids]
                if not actions:
                    continue
                heading = title_heading(tr(native_action_group_heading(
                    actions, used_headings, root_title, translate=tr)))
                if (is_raster_root and
                        self._raster_compact_group(row, heading, actions)):
                    seen.update(id(a) for a in actions)
                    used_headings.add(heading)
                    populated = True
                    continue
                if (root_menu is self._safe_iface('vectorMenu') and
                        self._vector_compact_group(row, heading, actions)):
                    seen.update(id(a) for a in actions)
                    used_headings.add(heading)
                    populated = True
                    continue
                if (root_menu is self._safe_iface('settingsMenu') and
                        self._settings_special_section(row, heading, actions)):
                    seen.update(id(a) for a in actions)
                    populated = True
                    continue
                if is_layer_root:
                    kind = self._layer_heading_kind(heading)
                    if kind == 'clipboard':
                        add_layer_clipboard()
                        seen.update(id(a) for a in actions)
                        continue
                    if kind in ('source', 'embed'):
                        self._layer_single_group(row,
                            'Fonte de Dados' if kind == 'source' else 'Camadas e Grupos',
                            actions[0])
                        seen.update(id(a) for a in actions)
                        populated = True
                        continue
                    if kind == 'edits':
                        save = self._layer_save_all_action(actions)
                        if save is not None:
                            group = self._add_task_group(row, heading)
                            group.add_action(save)
                            for a in actions:
                                if a is not save:
                                    group.add_action(a)
                            seen.update(id(a) for a in actions)
                            seen.add(id(save))
                            populated = True
                            continue
                # Titles label the native section, never the parent tab.
                # Track final translated captions so duplicates are avoided.
                if (root_menu is self._safe_iface('viewMenu') and
                        self._is_view_interface_section(heading, actions)):
                    self._view_interface_actions.extend(a for a in actions if a not in self._view_interface_actions)
                    seen.update(id(a) for a in actions)
                    populated = True
                    continue
                if (root_menu is self._safe_iface('viewMenu') and
                        (self._view_visibility_dropdown(row, heading, actions) or
                         self._view_consolidated_dropdown(row, heading, actions) or
                         self._view_requested_section(row, heading, actions))):
                    used_headings.add(heading)
                    for action in actions:
                        seen.add(id(action))
                    populated = True
                    continue
                if (root_menu is self._safe_iface('editMenu') and
                        self._edit_geometry_dropdown(row, heading, actions)):
                    seen.update(id(a) for a in actions)
                    used_headings.add(heading)
                    populated = True
                    continue
                special = (self._edit_special_section(heading, actions)
                           if root_menu is self._safe_iface('editMenu') else None)
                if special:
                    self._edit_primary_group(row, special[0], actions, special[1])
                    used_headings.add(heading)
                    for action in actions:
                        seen.add(id(action))
                    populated = True
                    continue
                # Plugin-specific visual labels only; retain the QAction itself.
                is_rth = (normalized(root_title) in ('complementos', 'plugins')
                          and normalized(heading) == 'rth agriculture mapping tools')
                if is_rth:
                    heading = 'RTH Agriculture Mapping Tools'
                group = self._add_task_group(row, heading)
                used_headings.add(heading)
                if hasattr(group, "configure_overflow"):
                    group.configure_overflow(len(actions))
                for action in actions:
                    group.add_action(action)
                    seen.add(id(action))
                # Plugins tab: shorten only the painted label, preserving the
                # original QAction, tooltip, icon and trigger.
                if (normalized(root_title) in ('complementos', 'plugins')
                        and normalized(heading) in ('complementos', 'gerenciar e instalar complementos', 'manage and install plugins')
                        and group._lead is not None):
                    group._lead.set_display_caption('Gerenciar e Instalar')
                if is_rth and group._lead is not None:
                    group._lead.set_display_caption('Catálogo de Cenas')
                populated = True
                continue

            submenu = payload
            # Colar Feições Como integra o menu suspenso de Colar Feições;
            # não apresentar uma segunda seção independente na guia Editar.
            # O menu QAction original permanece intacto no QGIS.
            if (root_menu is self._safe_iface('editMenu')
                    and self._clipboard_items
                    and normalized(title) in ('colar feicoes como', 'paste features as')):
                continue
            if root_menu is self._safe_iface('editMenu') and principal_role('edit', title, submenu=True) == 'Selecionar':
                continue
            if root_menu is self._safe_iface('viewMenu') and principal_role('view', title, submenu=True):
                continue
            if root_menu is self._safe_iface('layerMenu') and principal_role('layer', title, submenu=True):
                continue
            if id(submenu.menuAction()) in self._moved_action_ids:
                continue
            native_actions = [a for a in submenu.actions()
                              if a.isVisible() and not a.isSeparator()]
            actions = [a for a in native_actions
                       if id(a) not in seen and id(a) not in self._moved_action_ids]
            # An empty or widget-backed QMenu may be populated lazily by QGIS
            # when opened. Never replace or move any custom Qt widget.
            needs_native_popup = (not native_actions or
                                  any(isinstance(a, QWidgetAction) for a in native_actions))
            if not actions and not needs_native_popup:
                continue
            heading = unique_native_group_heading(
                title, actions, used_headings, root_title, translate=tr)
            # The native submenu title remains preferred when distinct.
            heading = title_heading(tr(heading) if heading != title else heading)
            if normalized(heading) in ('gerenciar e instalar complementos', 'manage and install plugins'):
                heading = 'Complementos'
            if is_raster_root:
                raster_actions = self._recursive_menu_actions(submenu)
                if self._raster_compact_group(row, heading, raster_actions):
                    used_headings.add(heading)
                    seen.update(id(a) for a in actions)
                    populated = True
                    continue
            if root_menu is self._safe_iface('vectorMenu'):
                vector_actions = self._recursive_menu_actions(submenu)
                if self._vector_compact_group(row, title, vector_actions):
                    used_headings.add(title)
                    seen.update(id(a) for a in actions)
                    populated = True
                    continue
            if root_menu is self._safe_iface('settingsMenu'):
                settings_actions = self._plain_native_actions([('menu', submenu, title)])
                if self._settings_special_section(row, heading, settings_actions, submenu):
                    used_headings.add(heading)
                    seen.update(id(a) for a in actions)
                    populated = True
                    continue
            if root_menu is self._safe_iface('viewMenu'):
                visibility_actions = self._plain_native_actions([('menu', submenu, title)])
                if self._is_view_interface_section(heading, visibility_actions):
                    self._view_interface_actions.extend(a for a in visibility_actions if a not in self._view_interface_actions)
                    seen.update(id(a) for a in actions)
                    populated = True
                    continue
                if (self._view_visibility_dropdown(row, heading, visibility_actions) or
                        self._view_consolidated_dropdown(row, heading, visibility_actions) or
                        self._view_requested_section(row, heading, visibility_actions)):
                    used_headings.add(heading)
                    for action in actions:
                        seen.add(id(action))
                    populated = True
                    continue
            if (root_menu is self._safe_iface('editMenu') and not needs_native_popup
                    and self._edit_geometry_dropdown(row, heading, actions)):
                seen.update(id(a) for a in actions)
                used_headings.add(heading)
                populated = True
                continue
            special = (self._edit_special_section(heading, actions)
                       if root_menu is self._safe_iface('editMenu') else None)
            if special and not needs_native_popup:
                plain = [a for a in actions if a.menu() is None and self._is_native_command(a)]
                if plain:
                    self._edit_primary_group(row, special[0], plain, special[1])
                    used_headings.add(heading)
                    for action in actions:
                        seen.add(id(action))
                    populated = True
                    continue
            if is_layer_root:
                kind = self._layer_heading_kind(heading) or self._layer_heading_kind(title)
                if kind == 'edits' and not needs_native_popup:
                    editable = [a for a in actions if self._is_native_command(a) and a.menu() is None]
                    save = self._layer_save_all_action(editable)
                    if save is not None:
                        group = self._add_task_group(row, heading)
                        group.add_action(save)
                        for a in editable:
                            if a is not save:
                                group.add_action(a)
                        seen.update(id(a) for a in actions)
                        seen.add(id(save))
                        populated = True
                        continue
                if kind == 'clipboard':
                    add_layer_clipboard()
                    seen.update(id(a) for a in actions)
                    populated = True
                    continue
                if kind in ('source', 'embed'):
                    label = 'Fonte de Dados' if kind == 'source' else 'Camadas e Grupos'
                    # Retain the original QAction and native popup for submenu entries.
                    group = self._add_task_group(row, label)
                    group.add_menu('Incorporar' if kind == 'embed' else title,
                                   submenu, submenu.menuAction().icon())
                    group.content.setAlignment(Qt.AlignmentFlag.AlignHCenter)
                    used_headings.add(label)
                    seen.update(id(a) for a in actions)
                    populated = True
                    continue
            is_rth = (normalized(root_title) in ('complementos', 'plugins')
                      and normalized(heading) == 'rth agriculture mapping tools')
            if is_rth:
                heading = 'RTH Agriculture Mapping Tools'
            group = self._add_task_group(row, heading)
            used_headings.add(heading)
            if hasattr(group, "configure_overflow"):
                group.configure_overflow(len(actions) if not needs_native_popup else 1)
            if needs_native_popup:
                group.add_menu(title, submenu)
            else:
                for action in actions:
                    child = action.menu()
                    if child is not None:
                        group.add_menu(native_caption(action.text()) or
                                       native_caption(child.title()), child, action.icon())
                    elif self._is_native_command(action):
                        group.add_action(action)
                    else:
                        # An unsupported action must remain accessible inside
                        # the native submenu rather than being silently lost.
                        group.add_menu(title, submenu)
                        break
            for action in actions:
                seen.add(id(action))
            # Same visual-only override when QGIS presents the command as a submenu.
            if (normalized(root_title) in ('complementos', 'plugins')
                    and normalized(heading) in ('complementos', 'gerenciar e instalar complementos', 'manage and install plugins')
                    and group._lead is not None):
                group._lead.set_display_caption('Gerenciar e Instalar')
            if is_rth and group._lead is not None:
                group._lead.set_display_caption('Catálogo de Cenas')
            populated = True

        if is_edit_root and not digitizing_inserted:
            self._add_edit_digitizing_toolbars(row)

        if is_layer_root and layer_clipboard and not layer_clipboard_added:
            add_layer_clipboard()

        if not populated:
            # Plugin menus can start empty and populate on aboutToShow.
            heading = tr("Ferramentas")
            group = self._add_task_group(row, heading)
            group.add_menu(root_title, root_menu)

    def _build_native_tabs(self):
        """Preserve native menu sequence with one familiar Principal workspace."""
        self._project_page = None
        self._principal_page = None
        project_menu = self._safe_iface('projectMenu')
        roots = list(iter_native_menus(self.iface.mainWindow().menuBar()))
        self._collect_workspace(roots)
        self._view_interface_actions = []
        self._settings_interface_action = None
        view = self._safe_iface('viewMenu')
        self._view_related_actions = {'dicas': [], 'ultima': [], '3d': [], 'preview': []}
        if view is not None:
            for action in self._recursive_menu_actions(view):
                if not self._is_native_command(action) or action.menu() is not None:
                    continue
                label = normalized(action.text())
                category = None
                if label in ('atualizar', 'refresh', 'atualizar f5', 'refresh f5') or 'favorito espacial' in label or 'spatial bookmark' in label:
                    category = 'dicas'
                elif label in ('proxima visualizacao', 'next view', 'zoom next'):
                    category = 'ultima'
                elif 'visualizac' in label and '3d' in label or '3d map view' in label:
                    category = '3d'
                elif label.startswith(('simular monoc', 'simulate monoch', 'simular daltonismo', 'simulate color blindness', 'simulate colour blindness')):
                    category = 'preview'
                if category:
                    self._view_related_actions[category].append(action)
        seen = set()
        inserted_main = False
        for title, root in roots:
            row = self._new_tab(title, native=True)
            if project_menu is not None and root == project_menu:
                self._project_page = self._native_pages[-1]
                row.addStretch(1)
                self._build_principal_page()
                inserted_main = True
                continue
            self._append_native_menu(row, title, root, seen)
            if self._is_raster_root(root, title):
                self._reorder_rendered_raster_groups(row)
            row.addStretch(1)
        if not inserted_main:
            self._build_principal_page()
        for page in self._native_pages:
            page.consolidate_geometry()

    def _diagnostic_raster_actions(self):
        """Record how many live Raster actions can currently be found.

        No QMenu is opened or triggered, so this measurement cannot change
        the behavior of lazy third-party menus.
        """
        try:
            roots = iter_native_menus(self.iface.mainWindow().menuBar())
            for title, menu in roots:
                if self._is_raster_root(menu, title):
                    actions = self._recursive_menu_actions(menu)
                    return (len(actions), sum(bool(a.isVisible()) for a in actions))
        except (RuntimeError, AttributeError, TypeError):
            pass
        return (0, 0)

    def _log_raster_diagnostic(self, event, detail=""):
        try:
            count, visible = self._diagnostic_raster_actions()
            QgsMessageLog.logMessage(
                f"{event}: ações={count}, visíveis={visible}; {detail}",
                "QRibbonSkin Raster", Qgis.MessageLevel.Info)
        except (RuntimeError, AttributeError, TypeError):
            pass

    def _refresh_raster_on_entry(self):
        """Refresh Raster only if the source menu has gained visible actions.

        The older implementation forcibly rebuilt on each entry, allowing a
        transiently incomplete QGIS menu to replace a complete Ribbon page.
        Explicit manual refresh still rebuilds unconditionally.
        """
        if getattr(self, '_rebuilding_menus', False) or not self.isVisible():
            return
        index = self.tabs.currentIndex()
        if index < 0 or normalized(self.tabs.tabText(index)) != 'raster':
            return
        current = self._diagnostic_raster_actions()
        prior = getattr(self, '_raster_source_high_water', (0, 0))
        self._log_raster_diagnostic('Entrada na guia', f'anterior={prior}')
        if current[0] > prior[0] or current[1] > prior[1]:
            self._log_raster_diagnostic('Novas ações detectadas; aguardando estabilidade')
            self._refresh_if_menu_changed()
        self._raster_source_high_water = tuple(max(a, b) for a, b in zip(prior, current))

    def _native_menu_fingerprint(self):
        """Snapshot registered native action identities, without triggering menus."""
        signature = []
        try:
            roots = iter_native_menus(self.iface.mainWindow().menuBar())
            for title, menu in roots:
                signature.append((str(title), tuple(id(a) for a in self._recursive_menu_actions(menu))))
        except (RuntimeError, AttributeError, TypeError):
            return ()
        return tuple(signature)

    def _startup_force_refresh(self):
        """Compatibility hook: request a stable refresh, never force a rebuild."""
        self._refresh_if_menu_changed()

    def _refresh_if_menu_changed(self):
        """Update only after a native menu change is observed twice unchanged.

        Never rebuild merely because the user switched tabs. Avoid refreshing
        during native popup use, when QGIS may be populating actions lazily.
        The Interface > Atualizar menus command still allows an immediate
        explicit refresh when a plugin changes menus in an unusual way.
        """
        if (getattr(self, '_rebuilding_menus', False)
                or not self.isVisible()
                or QApplication.activePopupWidget() is not None):
            return
        current = self._native_menu_fingerprint()
        if not current:
            return
        if current == getattr(self, '_last_menu_fingerprint', None):
            self._pending_menu_fingerprint = None
            self._pending_menu_observations = 0
            return
        if current != getattr(self, '_pending_menu_fingerprint', None):
            self._pending_menu_fingerprint = current
            self._pending_menu_observations = 1
            return
        self._pending_menu_observations += 1
        if self._pending_menu_observations >= 2:
            self._log_raster_diagnostic('Árvore de menus alterada e estabilizada')
            self._refresh_native_tabs()

    def _refresh_native_tabs(self):
        """Rebuild after a stable external change, without intermediate paints.

        Qt normally repaints each removed/inserted QTabWidget page, causing
        the visible 'piscadas'. Block those updates and tab-change signals
        for the entire transaction, then notify the dashboard just once.
        """
        if getattr(self, '_rebuilding_menus', False):
            return
        self._rebuilding_menus = True
        selected_label = self.tabs.tabText(self.tabs.currentIndex())
        previous_block = self.tabs.blockSignals(True)
        self.tabs.setUpdatesEnabled(False)
        try:
            self.tabs.setCurrentWidget(self._interface_page)
            for page in self._native_pages:
                ix = self.tabs.indexOf(page)
                if ix >= 0:
                    self.tabs.removeTab(ix)
                page.deleteLater()
            self._native_pages.clear()
            self._groups = [g for g in self._groups if g not in self._native_groups]
            self._native_groups.clear()
            # These menus belong to deleted native pages, never to QGIS.
            for menu in self._task_menus:
                menu.deleteLater()
            self._task_menus.clear()
            self._build_native_tabs()
            if hasattr(self, 'quick_host'):
                old_quick = self.quick_host
                old_quick.hide()
                old_quick.deleteLater()
                self._make_quick_access()
            for ix in range(self.tabs.count()):
                if self.tabs.tabText(ix) == selected_label:
                    self.tabs.setCurrentIndex(ix)
                    break
            else:
                self._select_principal()
            for group in self._native_groups:
                group.set_compact(self._compact)
            self._last_menu_fingerprint = self._native_menu_fingerprint()
            self._pending_menu_fingerprint = None
            self._pending_menu_observations = 0
            raster_now = self._diagnostic_raster_actions()
            previous_high = getattr(self, '_raster_source_high_water', (0, 0))
            self._raster_source_high_water = tuple(
                max(a, b) for a, b in zip(previous_high, raster_now))
            self._log_raster_diagnostic('Reconstrução concluída',
                                        f'anterior={previous_high}')
        finally:
            self.tabs.blockSignals(previous_block)
            self.tabs.setUpdatesEnabled(True)
            self.tabs.update()
            self._rebuilding_menus = False
        # Only one post-transaction notification; no transient Interface tab.
        self._on_tab_changed(self.tabs.currentIndex())

    def _make_extra_tabs(self, restore_action, focus_action, restore_panels_action):
        row = self._new_tab("Interface")
        self._interface_page = self.tabs.widget(self.tabs.count() - 1)
        # Keep classic interface access in the Interface tab only.
        # The original QAction is not removed from the QGIS View menu.
        restore_action.setIcon(self._interface_icon("classic_interface"))
        classic_group = self._add_group(row, tr("Restaurar"))
        classic_group.add_action(restore_action)
        panel_group = self._add_group(row, tr("Painéis"))
        focus_action.setIcon(self._interface_icon("focus_map"))
        restore_panels_action.setIcon(self._interface_icon("restore_panels"))
        panel_group.add_action(focus_action)
        panel_group.add_action(restore_panels_action)
        # Settings provides the native QGIS Interface Customization action;
        # show it only on the QRibbonSkin Interface tab.
        customization = getattr(self, '_settings_interface_action', None)
        if customization is not None:
            customization_group = self._add_group(row, 'Personalização')
            customization_group.add_action(customization)
            self._customization_group = customization_group
        self._display_group = self._add_group(row, tr("Exibição"))
        self.refresh_action = QAction(tr("Atualizar menus"), self)
        self.refresh_action.setToolTip(tr("Atualizar a Ribbon após instalar ou remover complementos"))
        self.refresh_action.triggered.connect(self._refresh_native_tabs)
        self.refresh_action.setIcon(self._interface_icon("refresh_menus"))
        self._display_group.add_action(self.refresh_action)
        # Only plugin-toolbar actions without menu entries need a fallback.
        extras = self._add_group(row, tr("Ações adicionais"))
        extras.add_menu(tr("Barras de plugins"), self._toolbar_actions_menu(),
                        self._interface_icon("plugin_toolbars"))
        extras.add_menu(tr("Menus originais"), self._main_menu(),
                        self._interface_icon("original_menus"))
        row.addStretch(1)
        # The Interface page is assembled from independent fixed-width groups.
        # Recalculate AFTER all tools are inserted and before first rendering.
        for group in (classic_group, panel_group, self._display_group, extras):
            group.updateGeometry()
        if customization is not None:
            customization_group.updateGeometry()
        self._interface_page.consolidate_geometry()
        QTimer.singleShot(0, self._interface_page.consolidate_geometry)

    def _interface_icon(self, name):
        """Load only QRibbonSkin Interface-page icons; no global QGIS theme changes."""
        path = Path(__file__).resolve().parent / "resources" / "icons" / "interface" / (name + ".svg")
        return QIcon(str(path)) if path.is_file() else self._std_icon()

    def _std_icon(self):
        # Reuse a generic icon from QGIS/Qt; no external resource write.
        from qgis.PyQt.QtWidgets import QApplication, QStyle
        app = QApplication.instance()
        return app.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogDetailedView)

    def _populate_views(self, menu, klass):
        menu.clear()
        widgets = self.iface.mainWindow().findChildren(klass)
        unique = set()
        for widget in sorted(widgets, key=lambda x: x.windowTitle().lower()):
            if not widget.windowTitle() or widget.objectName() == "QRibbonSkinToolbar":
                continue
            if widget.parent() is not self.iface.mainWindow():
                continue
            action = widget.toggleViewAction()
            if action is None or id(action) in unique:
                continue
            unique.add(id(action))
            menu.addAction(action)
        if not menu.actions():
            empty = menu.addAction(tr("Nenhum painel disponível"))
            empty.setEnabled(False)

    def _toolbar_actions_menu(self):
        menu = QMenu(self)
        menu.aboutToShow.connect(lambda: self._populate_toolbar_actions(menu))
        return menu

    def _populate_toolbar_actions(self, menu):
        menu.clear()
        bars = self.iface.mainWindow().findChildren(QToolBar)
        for bar in sorted(bars, key=lambda b: b.windowTitle().casefold()):
            if (bar.parent() is not self.iface.mainWindow()
                    or bar.objectName() == "QRibbonSkinToolbar"):
                continue
            actions = [a for a in bar.actions() if not a.isSeparator()]
            if not actions:
                continue
            submenu = menu.addMenu(bar.windowTitle() or bar.objectName() or tr("Ferramentas"))
            # The QGIS-owned QActions remain in place and keep their state.
            for action in actions:
                submenu.addAction(action)
        if not menu.actions():
            item = menu.addAction(tr("Nenhuma barra de ferramentas encontrada"))
            item.setEnabled(False)

    def _main_menu(self):
        popup = QMenu(self)
        popup.aboutToShow.connect(lambda: self._populate_menus(popup, plugins_only=False))
        return popup

    def _plugin_menu(self):
        popup = QMenu(self)
        popup.aboutToShow.connect(lambda: self._populate_menus(popup, plugins_only=True))
        return popup

    def _populate_menus(self, popup, plugins_only):
        popup.clear()
        menu_bar = self.iface.mainWindow().menuBar()
        for action in menu_bar.actions():
            if action.menu() is None:
                continue
            text = action.text().replace("&", "").lower()
            if plugins_only and not any(p in text for p in ("plugin", "complement", "extension", "extens")):
                continue
            # addAction of the existing QMenu.menuAction does not copy or move
            # the real QGIS commands; they remain live in the native menu bar.
            popup.addAction(action)
        if not popup.actions() and plugins_only:
            try:
                plugin_menu = self.iface.pluginMenu()
                if plugin_menu is not None:
                    popup.addAction(plugin_menu.menuAction())
            except (AttributeError, RuntimeError, TypeError):
                pass
        if not popup.actions():
            info = popup.addAction(tr("Menu indisponível"))
            info.setEnabled(False)
