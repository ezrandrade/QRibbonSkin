"""QRibbonSkin - visual-only ribbon for QGIS 4.x.

QRibbonSkin adapts the interface-management approach documented by ArcSkin
(EnviroSolutions, GPL-2.0), while deliberately excluding map styling changes.
"""


def classFactory(iface):  # noqa: N802 - QGIS plugin API
    from .plugin import QRibbonSkinPlugin
    return QRibbonSkinPlugin(iface)
