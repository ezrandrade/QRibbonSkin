"""Pure action classification and labels for the native QGIS georeferencer.

QRibbonSkin v0.9.18 - this file imports no Qt/QGIS modules so that routing
rules can be audited and tested separately from the live application.
"""
import unicodedata

TABS = ("Arquivo", "Pontos de controle", "Navegar", "Transformar", "Exibir", "Interface")
GROUP_ORDER = {
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


