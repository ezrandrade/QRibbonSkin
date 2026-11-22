"""Qt5 (QGIS 3.44 LTR) / Qt6 (QGIS 4.x) compatibility.

QAction and QShortcut moved from QtWidgets (Qt5) to QtGui (Qt6). Everything
else QRibbonSkin uses has the same name and module in both, and enums are
always written fully scoped (Qt.AlignmentFlag.AlignTop), which PyQt5 5.15
and PyQt6 both accept.
"""

try:  # Qt6 / QGIS 4.x
    from qgis.PyQt.QtGui import QAction, QShortcut  # noqa: F401
except ImportError:  # Qt5 / QGIS 3.44 LTR
    from qgis.PyQt.QtWidgets import QAction, QShortcut  # noqa: F401

__all__ = ["QAction", "QShortcut"]
