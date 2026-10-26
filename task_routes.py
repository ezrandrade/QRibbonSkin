"""Qt-free routing of third-party QGIS root menus into task tabs.

Only labels of *root menus* are classified; individual tool algorithms are never
reimplemented or renamed. Every source QAction remains owned by QGIS/plugins.
"""
import unicodedata


def canonical(text):
    text = unicodedata.normalize('NFKD', str(text or '').replace('&', '').casefold())
    return ' '.join(''.join(c for c in text if not unicodedata.combining(c)).split())


def extra_menu_task(title):
    name = canonical(title)
    if name in ('processamento', 'processing', 'analysis', 'analise', 'vetor', 'vector', 'raster', 'malha', 'mesh'):
        return 'Análise'
    if name in ('web', 'internet', 'database', 'banco de dados'):
        return 'Dados'
    if name in ('layouts', 'layout', 'impressao', 'print'):
        return 'Publicar'
    return 'Plugins'
