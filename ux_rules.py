"""Language-tolerant, Qt-free rules for QRibbonSkin's familiar QGIS workspace.

Only display groups change. Native QAction objects and shortcuts remain owned by
QGIS, and no project, processing algorithm or provider is modified.
"""
import re
import unicodedata


def normalized(text):
    value = unicodedata.normalize('NFKD', str(text or '').replace('&', ''))
    value = ''.join(c for c in value.casefold() if not unicodedata.combining(c))
    return ' '.join(re.findall(r'[a-z0-9]+', value))


# QRibbonSkin-owned captions use sentence case (PT-BR and EN). This rule
# never touches native QGIS QAction text, menu titles, shortcuts or routing IDs.
_PRESERVED_TECHNICAL_WORDS = {
    'qgis': 'QGIS', 'qribbonskin': 'QRibbonSkin', 'gis': 'GIS', 'sig': 'SIG',
    'python': 'Python', 'pdf': 'PDF', 'svg': 'SVG', 'rgb': 'RGB', 'kml': 'KML',
    'csv': 'CSV', 'gcp': 'GCP', 'pct': 'PCT', 'api': 'API', 'sql': 'SQL',
    'wms': 'WMS', 'wfs': 'WFS', 'wmts': 'WMTS', 'gdal': 'GDAL',
    'qt': 'Qt', 'qt6': 'Qt6', '3d': '3D', 'cbers': 'CBERS',
    'stac': 'STAC', 'gps': 'GPS', 'geotiff': 'GeoTIFF',
}


def sentence_label(text):
    """Format an *owned display caption* without changing its semantics.

    Preserve acronyms, brand spellings, CamelCase identifiers, punctuation,
    shortcuts and numbers. This function is display-only: callers keep their
    original identifiers and never run it on QGIS-owned QAction.text().
    """
    original = str(text or '')
    # Keyboard shortcuts are technical notation, not ordinary words: Alt+Q,
    # Ctrl+Shift+S, etc. Protect them before changing word capitalization.
    shortcuts = []
    def protect_shortcut(match):
        shortcuts.append(match.group(0))
        return chr(0xE000 + len(shortcuts) - 1)
    masked = re.sub(
        r'\b(?:Alt|Ctrl|Shift|Meta|Cmd)(?:\+(?:Alt|Ctrl|Shift|Meta|Cmd|[A-Za-z0-9]+))+\b',
        protect_shortcut, original, flags=re.IGNORECASE
    )
    # Preserve original whitespace and line breaks; only word case changes.
    token_pattern = re.compile(r'[^\W_]+(?:_[^\W_]+)*', re.UNICODE)
    first_word = True

    def update(match):
        nonlocal first_word
        token = match.group(0)
        was_first = first_word
        first_word = False
        low = token.casefold()
        if low in _PRESERVED_TECHNICAL_WORDS:
            return _PRESERVED_TECHNICAL_WORDS[low]
        if (token.isupper() and len(token) > 1) or '_' in token:
            return token  # unknown acronym / programmatic identifier
        if any(c.isupper() for c in token[1:]) and any(c.islower() for c in token):
            return token  # native product or CamelCase name: ArcSkin, etc.
        normalized_token = token.lower()
        return (normalized_token[:1].upper() + normalized_token[1:]
                if was_first else normalized_token)

    result = token_pattern.sub(update, masked)
    for index, shortcut in enumerate(shortcuts):
        result = result.replace(chr(0xE000 + index), shortcut)
    return result


def title_heading(text):
    """Compatibility name for the QRibbonSkin-owned group-title formatter."""
    return sentence_label(text)


def shortcut_role(text):
    value = normalized(text)
    if any(x in value for x in ('desfazer', 'undo')):
        return 'undo'
    if any(x in value for x in ('refazer', 'redo')):
        return 'redo'
    return None


def clipboard_role(text):
    v = normalized(text)
    if v in ('area de transferencia', 'clipboard'):
        return 'Área de Transferência'
    if any(w in v for w in ('copiar', 'copy', 'recortar', 'cut', 'colar', 'paste', 'exclusao', 'excluir', 'delete', 'remover feic', 'remove feature')):
        return 'Área de Transferência'
    return None


def principal_role(root, text, submenu=False):
    v = normalized(text)
    if root == 'edit':
        if any(x in v for x in ('selecionar', 'selecao', 'select feature', 'select by', 'selection')):
            return 'Selecionar'
    if root == 'view':
        if any(x in v for x in ('ver tudo', 'full extent', 'zoom to full', 'zoom full', 'zoom total', 'zoom para extensao')):
            return 'Ver Tudo'
        if any(x in v for x in ('identificar feic', 'identify features', 'identify feature')):
            return 'Identificar Feições'
        if any(x in v for x in ('caixa de ferramenta', 'caixa de ferramentas', 'processing toolbox', 'toolbox', 'tool box')):
            return 'Caixa de Ferramentas'
        if any(x in v for x in ('medir', 'medicao', 'medicoes', 'measure', 'measurement', 'ferramentas de medir')):
            return 'Medir'
        if any(x in v for x in ('navegacao do mapa', 'map navigation', 'zoom', 'pan map', 'panear', 'deslocar mapa', 'deslocar o mapa', 'mover mapa', 'move map', 'aproximar', 'afastar', 'centro do mapa', 'recenter')):
            return 'Navegação do Mapa'
    if root == 'layer':
        if any(x in v for x in ('georreferenciador', 'georeferencer', 'georreferenciar', 'georeferencing')):
            return 'Georreferenciador'
        if any(x in v for x in ('tabela de atributos', 'attribute table')):
            return 'Tabela de Atributos'
        if any(x in v for x in ('alternar edicao', 'toggle editing', 'toggle edit')):
            return 'Edição de Camadas'
        if any(x in v for x in ('criar nova camada', 'criar camada', 'create new layer', 'new layer', 'create layer', 'nova camada', 'new shapefile', 'new geopackage')):
            return 'Criar Nova Camada'
        if any(x in v for x in ('adicionar camada', 'adicionar camadas', 'adicionar', 'add layer', 'add vector', 'add raster', 'adicionar dados', 'add data')):
            return 'Adicionar Camada'
    return None


def clipboard_priority(text):
    v = normalized(text)
    if ('colar ' in v or 'paste ' in v) and (' como' in v or ' as ' in ' ' + v + ' '):
        return 5
    if 'copiar' in v or 'copy' in v:
        return 0
    if v.startswith('colar ') or v == 'colar' or v.startswith('paste ') or v == 'paste':
        return 1
    if 'recortar' in v or 'cut' in v:
        return 2
    if 'excluir' in v or 'delete' in v:
        return 3
    return 4
