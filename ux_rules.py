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


def title_heading(text):
    """Consistent typographic title style, retaining acronyms and PT particles."""
    original = str(text or '').strip()
    small = {'de', 'da', 'do', 'das', 'dos', 'e', 'em', 'para', 'por', 'as', 'os', 'of', 'and', 'the', 'for', 'to'}
    acronyms = {'qgis', 'gps', 'wms', 'wfs', 'sql', 'api', 'stac', 'gdal', 'gis', 'rgb', '3d', 'pdf', 'csv', 'svg', 'wmts'}
    pieces = re.split(r'(\s+)', original)
    result = []
    ordinal = 0
    for piece in pieces:
        if not piece or piece.isspace():
            result.append(piece)
            continue
        match = re.match(r'^([^\w]*)([\w-]+)(.*)$', piece, flags=re.UNICODE)
        if not match:
            result.append(piece)
            continue
        prefix, word, suffix = match.groups()
        low = word.casefold()
        if low in acronyms:
            word = low.upper()
        elif ordinal and low in small:
            word = low
        else:
            word = word[:1].upper() + word[1:].lower()
        result.append(prefix + word + suffix)
        ordinal += 1
    return ''.join(result)


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
