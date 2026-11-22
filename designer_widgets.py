"""Multiline QAction button shared by the Layout Designer, Georeferencer and
Model Designer Ribbons (moved unchanged from the former ribbon.py).

The main-window Ribbon uses ribbon.py; only the auxiliary editors use this.
"""

from itertools import combinations

from qgis.PyQt.QtCore import Qt, QSize, QRect
from qgis.PyQt.QtGui import QIcon, QFontMetrics, QPalette, QColor
from qgis.PyQt.QtWidgets import (QSizePolicy, QStyle, QStyleOptionToolButton,
                                 QStylePainter, QToolButton)

from .i18n import ui_label
from .native_menus import native_caption
from .icon_mapping import display_icon
from .theme import light_palette
from .presentation import full_caption_width, complete_caption_lines

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
