"""Pure action classification and labels for the native QGIS georeferencer.

QRibbonSkin v1.1.15 - this file imports no Qt/QGIS modules so that routing
rules can be audited and tested separately from the live application.
"""
import unicodedata

TABS = ("Principal", "Interface")
GROUP_ORDER = {
    "Principal": ("Abrir dados", "Pontos de controle", "Navegação", "Sincronização",
                  "Transformação", "Histograma", "Aderência"),
    "Arquivo": ("Abrir dados", "Sessão", "Arquivos"),
    "Pontos de controle": ("Editar PCT", "Arquivos PCT", "Aderência", "Pontos de controle"),
    "Navegar": ("Visualização", "Sincronização", "Navegação"),
    "Transformar": ("Executar", "Configurações", "Transformação"),
    "Exibir": ("Painéis", "Visualização", "Preferências", "Ajuda"),
    "Interface": ("QRibbonSkin",),
}

def canonical(text):
    text = str(text or "").replace("&", "").replace("\n", " ").strip().lower()
    text = unicodedata.normalize('NFKD', text)
    return ''.join(c for c in text if not unicodedata.combining(c))


def is_georeferencer_class(qt_classname, object_name=""):
    """Require known native georeferencer Qt class, never identify by title."""
    names = ("QgsGeoreferencerMainWindow", "QgsGeorefPluginGui")
    return str(qt_classname) in names or str(object_name) in names


def route_action(text, tooltip="", object_name="", source=""):
    """Return (tab, group) based on native action semantics in PT/EN.

    Object name, tooltip and source are hints; no action is reimplemented.
    Unknown actions remain reachable in a labelled source group.
    """
    key = canonical(" ".join((text, tooltip, object_name)))
    src = canonical(source)
    def anyof(*phrases):
        return any(canonical(p) in key for p in phrases)

    if anyof('reset georeferenc', 'resetar georreferenc', 'limpar georreferenc',
             'clear georeferenc', 'close georeferenc', 'fechar georreferenc'):
        return 'Arquivo', 'Sessão'

    if anyof('start georeferenc', 'iniciar georreferenc', 'georeference layer',
             'georeferenciar camada', 'executar georreferenc', 'run georeferenc',
             'do georeference', 'gerar script gdal', 'generate gdal script',
             'transformation settings', 'configuracoes de transformacao',
             'configuracao de transformacao', 'transformation type',
             'metodo de transformacao', 'transform settings'):
        if anyof('settings', 'configura', 'metodo', 'type'):
            return 'Transformar', 'Configurações'
        return 'Transformar', 'Executar'

    if anyof('load gcp', 'save gcp', 'pontos de controle do arquivo',
             'carregar pontos', 'salvar pontos', 'gcp point file',
             'open gcp', 'export gcp', 'import gcp'):
        return 'Pontos de controle', 'Arquivos PCT'

    if anyof('add gcp', 'add point', 'adicionar ponto', 'adicionar pct',
             'delete gcp', 'delete point', 'remover ponto', 'excluir ponto',
             'move gcp', 'move point', 'mover ponto', 'edit gcp', 'editar ponto',
             'snapping', 'aderencia', 'digitizacao avancada', 'advanced digitizing'):
        if anyof('snapping', 'aderencia', 'digitizacao avancada', 'advanced digitizing'):
            return 'Pontos de controle', 'Aderência'
        return 'Pontos de controle', 'Editar PCT'

    if anyof('link qgis', 'link georef', 'sincroniz', 'vincular qgis',
             'vincular georreferenciador', 'link canvas', 'vincular visualiz'):
        return 'Navegar', 'Sincronização'

    if anyof('pan ', 'panning', 'panear', 'deslocar', 'aproximar', 'afastar',
             'zoom', 'extent', 'extensao total', 'zoom to layer', 'previous view',
             'next view', 'visualizacao anterior', 'visualizacao seguinte',
             'last view'):
        return 'Navegar', 'Visualização'

    if anyof('histogram', 'histograma', 'contrast', 'contraste', 'stretch',
             'esticar histograma', 'source properties', 'propriedades da origem',
             'table of gcps', 'tabela de pct', 'gcp table', 'painel', 'panel'):
        return 'Exibir', 'Painéis'

    if anyof('configure georeferencer', 'configurar georreferenciador',
             'georeferencer settings', 'preferencias georreferenc',
             'configuration'):
        return 'Exibir', 'Preferências'

    if anyof('open raster', 'open vector', 'abrir raster', 'abrir vetor',
             'abrir camada', 'open source', 'source layer', 'camada de origem',
             'carregar raster', 'carregar vetor', 'abrir arquivo'):
        return 'Arquivo', 'Abrir dados'

    if anyof('save', 'salvar', 'load', 'carregar'):
        return 'Arquivo', 'Arquivos'

    if anyof('help', 'ajuda', 'about', 'sobre'):
        return 'Exibir', 'Ajuda'

    if ('gcp' in src or 'ponto' in src or 'edit' in src or 'editar' in src):
        return 'Pontos de controle', 'Pontos de controle'
    if 'transform' in src or 'georreferenc' in src or 'georeferenc' in src:
        return 'Transformar', 'Transformação'
    if 'view' in src or 'exibir' in src or 'navigation' in src or 'navega' in src:
        return 'Navegar', 'Navegação'
    if 'setting' in src or 'configura' in src:
        return 'Exibir', 'Preferências'
    if 'file' in src or 'arquivo' in src:
        return 'Arquivo', 'Arquivos'
    return 'Exibir', 'Outras ferramentas'




# Explicit, PT-BR/EN-aware priorities for the primary button in each section.
# Fallback is the first original native QAction; no command is fabricated.
LEADER_KEYWORDS = {
    'Abrir dados': ('open raster', 'abrir raster', 'abrir imagem', 'open vector',
                    'abrir vetor', 'abrir camada'),
    'Histograma': ('full histogram', 'histograma completo',
                   'ampliacao completa', 'ampliacao total'),
    'Pontos de Controle': ('add gcp', 'add point', 'adicionar ponto',
                           'adicionar pct', 'adicionar ponto de controle'),
    'Editar PCT': ('add gcp', 'add point', 'adicionar ponto', 'adicionar pct',
                   'adicionar ponto de controle'),
    'Pontos de controle': ('add gcp', 'add point', 'adicionar ponto',
                          'adicionar pct', 'adicionar ponto de controle'),
    'Arquivos PCT': ('save gcp', 'salvar pontos', 'salvar pct',
                     'load gcp', 'carregar pontos'),
    'Visualização': ('zoom to layer', 'zoom para camada', 'zoom camada',
                      'full histogram', 'histograma'),
    # Prioritize the native Zoom-to-Layer QAction, not the generic Zoom In or
    # Pan commands. The caller additionally resolves the concrete QAction.
    'Navegação': ('aproximar para camada', 'aproximar para a camada',
                  'zoom to layer', 'zoom to layer extent',
                  'zoom para camada', 'zoom a camada', 'aproximar a camada'),
    'Conectar': ('conectar o qgis ao georreferenciador',
                 'conectar qgis ao georreferenciador',
                 'link qgis to georeferencer', 'connect qgis to georeferencer'),
    'Sincronização': ('link qgis', 'vincular qgis', 'link georeferencer',
                      'vincular georreferenciador'),
    'Transformação': ('start georeferenc', 'iniciar georreferenc',
                      'executar georreferenc', 'georeference layer',
                      'georreferenciar camada'),
    'Executar': ('start georeferenc', 'iniciar georreferenc',
                 'executar georreferenc', 'georeference layer'),
    'Configurações': ('transformation settings', 'configuracoes de transformacao',
                      'configuracao de transformacao'),
    'Painéis': ('full histogram', 'histograma', 'gcp table', 'tabela de pct'),
    'Aderência': ('snapping', 'aderencia'),
}


def preferred_action_index(group, captions):
    """Choose a native primary action without mistaking another command.

    Search all exact normalized captions before substring matches. Operates on
    strings only, allowing regression tests without a running QGIS instance.
    """
    if not captions:
        return None
    normalized = [canonical(caption) for caption in captions]
    choices = tuple(canonical(word) for word in LEADER_KEYWORDS.get(group, ()))
    for word in choices:
        for i, caption in enumerate(normalized):
            if caption == word:
                return i
    for word in choices:
        for i, caption in enumerate(normalized):
            if word in caption:
                return i
    return 0



def is_native_zoom_to_layer_action(caption, object_name=''):
    """Recognize QGIS' real Zoom-to-Layer action, not arbitrary zoom tools.

    Avoid selecting Zoom In or Full Extent just because it contains "zoom".
    The action stays QGIS-owned; callers may display an independent caption.
    """
    label = canonical(caption)
    obj = canonical(object_name).replace('_', '')
    exact_captions = (
        'aproximar para camada', 'aproximar para a camada',
        'aproximar a camada', 'aproximar camada',
        'zoom a camada', 'zoom para camada', 'zoom a camada ativa',
        'zoom to layer', 'zoom to the layer', 'zoom to layer extent',
        'zoom layer', 'zoom to source layer',
    )
    if label in exact_captions:
        return True
    if obj in ('mactionzoomtolayer', 'actionzoomtolayer',
               'mactionzoomlayer', 'actionzoomlayer'):
        return True
    # Some translated versions add an ellipsis or a trailing explanation.
    # Both semantic components (zoom + layer) must be present.
    return (('camada' in label or 'layer' in label)
            and ('zoom' in label or 'aproximar' in label)
            and not any(word in label for word in ('todas as camadas',
                                                     'all layers', 'layer properties',
                                                     'propriedades da camada')))


def is_native_pan_action(caption, object_name=''):
    """Match the Georeferencer's original map-move tool (PT/EN).

    Do not infer a map pan command from an unrelated 'Move GCP' / 'Mover PCT'
    QAction. QGIS version differences are accounted for by objectName.
    """
    label = canonical(caption)
    obj = canonical(object_name).replace('_', '')
    return (label in ('movimentar', 'movimentar mapa', 'mover', 'pan',
                      'deslocar', 'mover mapa', 'pan map', 'move map',
                      'deslocar mapa', 'pan canvas', 'pan image')
            or obj in ('mactionpan', 'actionpan', 'actionpanmap',
                       'mactionpanmap'))


def connection_display_caption(native_caption):
    """Display-only labels for QGIS Georeferencer link commands.

    The real QActions, tooltips, shortcut and menu ownership are unchanged.
    Matching is anchored to the command text to avoid shortening unrelated
    tools grouped under the original Exibir > Outras ferramentas section.
    """
    name = canonical(native_caption)
    georef_to_qgis = (
        'conectar georreferenciador ao qgis',
        'conectar o georreferenciador ao qgis',
        'link georeferencer to qgis',
        'connect georeferencer to qgis',
    )
    qgis_to_georef = (
        'conectar o qgis ao georreferenciador',
        'conectar qgis ao georreferenciador',
        'link qgis to georeferencer',
        'connect qgis to georeferencer',
    )
    if name in georef_to_qgis:
        return 'Georreferenciador ao QGIS'
    if name in qgis_to_georef:
        return 'QGIS ao Georreferenciador'
    return None


def georeferencer_display_caption(section, native_caption):
    """PT-BR-only labels for known Georeferencer QActions.

    Return None for unknown commands, so a new QGIS action retains its
    original label. This is presentation only and never changes QAction.text.
    """
    label = canonical(native_caption)
    if section == 'Histograma':
        if (('histogram' in label or 'histograma' in label)
                and any(token in label for token in ('full', 'complet', 'total', 'global'))):
            return 'Completa Ampliação'
        if (('histogram' in label or 'histograma' in label)
                and any(token in label for token in ('local', 'extensao local'))):
            return 'Extensão Local'
    if section == 'Aderência':
        if ('advanced digitizing' in label or 'digitalizacao avancada' in label
                or 'digitalisation avancee' in label):
            return 'Digitalização Avançada'
    if section == 'Pontos de Controle':
        if (label.startswith(('add gcp', 'add point', 'adicionar ponto',
                              'adicionar pct', 'inserir ponto'))):
            return 'Adicionar Ponto'
        if (label.startswith(('delete gcp', 'delete point', 'remove gcp',
                              'remove point', 'remover ponto', 'excluir ponto'))):
            return 'Remover Ponto'
        if (label.startswith(('move gcp', 'move point', 'mover ponto',
                              'movimentar ponto'))):
            return 'Mover Ponto'
    return None
