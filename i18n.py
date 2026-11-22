"""QRibbonSkin UI translations (PT-BR/EN), independent of native QAction labels.

Translate only the plugin's own display text. Internal task identifiers, QGIS
QActions, objectNames and settings keys must never be translated. This avoids
changes to QGIS algorithms, routing, project files or toolbar restoration.

A QGIS language override takes precedence over the OS locale. Locale is
resolved at initialization; QGIS ordinarily applies UI language changes after
restart. English is the fallback for locales without a QRibbonSkin catalog.
"""

import re

# Explicit catalog so a QGIS4 Flatpak/Windows installation does not require
# Qt Linguist, external translation tools or separately compiled .qm files.
EN = {
    # General / main Ribbon tabs
    'Principal':'Main', 'Projeto':'Project', 'Início':'Home', 'Dados':'Data', 'Estilo':'Style',
    'Editar':'Edit', 'Análise':'Analysis', 'Exibir':'View', 'Publicar':'Publish',
    'Plugins':'Plugins', 'Configurações':'Settings', 'Ajuda':'Help',
    'Interface':'Interface', 'Arquivo':'File', 'Inserir':'Insert',
    'QRibbonSkin — Layout':'QRibbonSkin — Layout Designer',
    'QRibbonSkin — Georreferenciador':'QRibbonSkin — Georeferencer',
    'QRibbonSkin — Designer de Modelos':'QRibbonSkin — Model Designer',
    'Designer de Modelos':'Model Designer', 'Editar Itens':'Edit Items',
    'Execução':'Execution', 'Organizar':'Arrange',
    'Atlas':'Atlas', 'Exportar':'Export', 'Pontos de controle':'Control points',
    'Navegar':'Navigate', 'Transformar':'Transform', 'Layout':'Layout',
    # Main Ribbon groups
    'Projetos':'Projects', 'Navegação':'Navigation', 'Camadas':'Layers',
    'Selecionar':'Select', 'Adicionar dados':'Add data', 'Banco de dados':'Database',
    'Rótulos':'Labels', 'Atributos':'Attributes', 'Edição':'Editing',
    'Edição avançada':'Advanced editing', 'Vetor':'Vector', 'Vetores':'Vectors',
    'Rasters':'Rasters', 'Visualização':'Visualization',
    'Exportação e impressão':'Export and print',
    'Ferramentas de publicação':'Publishing tools', 'Complementos':'Plugins',
    'Barras de plugins':'Plugin toolbars', 'Preferências':'Preferences',
    'Documentação':'Documentation', 'Restaurar':'Restore', 'Painéis':'Panels',
    'Exibição':'Display', 'Ações adicionais':'Additional actions',
    'Modo compacto':'Compact mode', 'Ajuste automático à janela':'Fit to window automatically',
    'Atualizar menus':'Refresh menus', 'Atualizar a Ribbon após instalar ou remover complementos':'Refresh the Ribbon after installing or removing plugins',
    'Buscar ferramenta...':'Search tools...',
    'Pesquisa comandos existentes do QGIS e dos plugins':'Search existing QGIS and plugin commands',
    'Digite pelo menos 2 caracteres':'Enter at least 2 characters',
    'Nenhum comando encontrado':'No commands found',
    'Nenhum painel disponível':'No panels available',
    'Nenhuma barra de ferramentas encontrada':'No toolbars found',
    'Menu indisponível':'Menu unavailable', 'Ferramentas':'Tools',
    'Voltar nos grupos':'Previous tool groups', 'Avançar nos grupos':'Next tool groups',
    'Percorrer ferramentas':'Browse tools', 'Percorrer grupos de ferramentas':'Browse tool groups',
    'Recuperar barras do QGIS':'Recover QGIS toolbars',
    'Recuperar as barras anteriormente visíveis; sem registro, mostrar as barras essenciais do QGIS':'Restore previously visible toolbars; if no record exists, show essential QGIS toolbars',
    'Ativar interface QRibbonSkin':'Enable QRibbonSkin',
    'Restaurar interface clássica do QGIS':'Restore classic QGIS interface',
    'Interface clássica':'Classic interface',
    'Desativar QRibbonSkin e restaurar as barras do QGIS':'Disable QRibbonSkin and restore QGIS toolbars',
    'Alternar a Ribbon sem alterar mapas ou dados. Atalho de recuperação: {shortcut}':'Toggle Ribbon without changing maps or data. Recovery shortcut: {shortcut}',
    'Mapa em foco':'Focus on map',
    'Ocultar temporariamente os painéis; sem alterar o projeto':'Temporarily hide panels without changing the project',
    'Restaurar painéis iniciais':'Restore original panels',
    'Restaurar visibilidade dos painéis anterior à Ribbon':'Restore panel visibility from before the Ribbon',
    # Project backstage
    '←   Voltar ao mapa':'←   Back to map', 'Novo':'New', 'Abrir':'Open',
    'Salvar':'Save', 'Salvar como':'Save as', 'Sobre o QGIS':'About QGIS',
    'Bem-vindo ao QGIS':'Welcome to QGIS',
    'Crie um projeto, abra um arquivo existente ou continue seu trabalho.':'Create a project, open an existing file, or continue your work.',
    'Novo mapa':'New map', 'Abrir projeto':'Open project',
    'Projetos recentes':'Recent projects', 'Projeto atual':'Current project',
    'Comando não disponível nesta instalação do QGIS':'Command unavailable in this QGIS installation',
    'Ainda não salvo':'Not saved yet', 'Projeto sem título':'Untitled project',
    'Nome: {name}\nLocalização: {location}\nCamadas: {layers}':'Name: {name}\nLocation: {location}\nLayers: {layers}',
    # Layout Designer
    'Projeto de layout':'Layout project', 'Inserir elementos':'Insert items',
    'Organizar':'Arrange', 'Ferramentas de edição':'Editing tools',
    'Elementos':'Items', 'Adicionar elementos':'Add items', 'Histórico':'History',
    'Organizar itens':'Arrange items', 'Impressão e exportação':'Print and export',
    'Navegação':'Navigation', 'Percorrer atlas':'Browse atlas', 'Relatório':'Report',
    'Ferramentas':'Tools', 'Arquivo':'File',
    'Barras nativas':'Native toolbars',
    'Mostrar ou ocultar as barras e menus originais do Editor de Layout':'Show or hide the original Layout Designer toolbars and menus',
    'O Editor de Layout não usa uma QMainWindow Qt':'Layout Designer does not use a Qt QMainWindow',
    'Falha na Ribbon do Editor de Layout: {error}':'Layout Designer Ribbon error: {error}',
    # Sentence-case labels and captions controlled by QRibbonSkin.
    # Key casing is retained for compatibility with legacy routing sources.
    'Editar Geometria': 'Edit geometry',
    'Visibilidade da Camada': 'Layer visibility',
    'Feições Selecionadas': 'Selected features',
    'Mover Feições': 'Move features',
    'Camada Vetorial': 'Vector layer',
    'Feição(s)': 'Feature(s)',
    'Medir Linha': 'Measure line',
    'Novo Layout': 'New layout',
    'Gerenciar e Instalar': 'Manage and install',
    'Catálogo de Cenas': 'Scene catalog',
    'Alternar Aderência': 'Toggle snapping',
    'Alternar Edição': 'Toggle editing',
    'Quebrar Feições': 'Split features',
    'Vista de Mapa': 'Map view',
    'Perfis de Usuários': 'User profiles',
    'Atalhos de Teclado': 'Keyboard shortcuts',
    'Simbologia de Pontos': 'Point symbology',
    'Nova Camada': 'New layer',
    'Layout de Impressão': 'Print layout',
    'Selecionar/Mover Item': 'Select/move item',
    'Exportar Imagem': 'Export image',
    'Exportar PDF': 'Export PDF',
    'Exportar SVG': 'Export SVG',
    'Exportar Python': 'Export Python',
    'Exportar Algoritmo Script': 'Export script algorithm',
    'Conectar': 'Connect',
    'QGIS ao Georreferenciador': 'QGIS to georeferencer',
    'Georreferenciador ao QGIS': 'Georeferencer to QGIS',
    # Additional presentation-only aliases used by native-action wrappers.
    'Novo Projeto': 'New project',
    'Abrir Projeto': 'Open project',
    'Salvar Projeto': 'Save project',
    'Desfazer': 'Undo',
    'Refazer': 'Redo',
    'Linha': 'Line',
    'Área': 'Area',
    'Gerenciador de Estilos': 'Style manager',
    'Projeções': 'Projections',
    'Modo de Pré-Visualização': 'Preview mode',
    'Filtragem de Dados': 'Data filtering',
    'Visualização de Mapa 3D': '3D map view',
    'Dicas do Mapa': 'Map tips',
    'Decorações': 'Decorations',
    'Nova Vista 3D': 'New 3D view',
    'Mostrar Todas as Camadas': 'Show all layers',
    'Fonte de Dados': 'Data source',
    'Camadas e Grupos': 'Layers and groups',
    'Definir Projeção': 'Assign projection',
    'Incorporar': 'Embed',
    'Gerenciar': 'Manage',
    'Personalizar': 'Customize',
    'Expandir faixa Ribbon': 'Expand Ribbon',
    'Recolher faixa Ribbon': 'Collapse Ribbon',
    # Georeferencer
    'Abrir dados':'Open data', 'Sessão':'Session', 'Arquivos':'Files',
    'Editar PCT':'Edit GCPs', 'Arquivos PCT':'GCP files',
    'Aderência':'Snapping', 'Digitalização':'Digitizing',
    'Pontos de Controle':'Control Points', 'Histograma':'Histogram',
    'Completa Ampliação':'Full Histogram Stretch',
    'Extensão Local':'Local Histogram Stretch',
    'Digitalização Avançada':'Advanced Digitizing',
    'Adicionar Ponto':'Add Point', 'Remover Ponto':'Remove Point',
    'Mover Ponto':'Move Point',
    'Zoom à Camada':'Zoom to Layer',
    'Sincronização':'Synchronization', 'Executar':'Run',
    'Transformação':'Transformation', 'Controles':'Controls',
    'Histórico de edição':'Edit history',
    'Área de Transferência':'Clipboard', 'Criar Nova Camada':'Create New Layer',
    'Adicionar Camada':'Add Layer', 'Ver Tudo':'Full Extent',
    'Caixa de Ferramentas':'Toolbox', 'Medir':'Measure',
    'Identificar Feições':'Identify Features', 'Tabela de Atributos':'Attribute Table',
    'Edição de Camadas':'Layer Editing', 'Georreferenciador':'Georeferencer',
    'Navegação do Mapa':'Map Navigation', 'Buscar ferramentas':'Search tools',
    'Pesquisar comandos do QGIS':'Search QGIS commands',
    'Buscar ferramenta...  Alt+Q':'Search tools...  Alt+Q',
    'Abrir busca central (Alt+Q)':'Open central search (Alt+Q)',
    'Digite para buscar ferramentas':'Type to search for tools',
    'Enter: executar  ·  Esc: fechar':'Enter: run  ·  Esc: close',
    'Área de transferência':'Clipboard',
    'Exclusão de feições':'Delete features',
    'Simbologia de pontos':'Point symbols',
    'Criação de feições':'Create features',
    'Navegação do mapa':'Map navigation',
    'Seleção':'Selection',
    'Outras ferramentas':'Other tools',
    'Mostrar comandos adicionais deste grupo':'Show additional commands in this group',
    'Nenhuma ferramenta disponível':'No tools available',
    'Menus do QGIS':'QGIS menus',
    'Exibir menus e barras originais':'Show original menus and toolbars',
    'Restaurar temporariamente os controles nativos; ao desmarcar, a Ribbon volta ao modo exclusivo':'Temporarily restore native controls; uncheck to return to Ribbon-only mode',
    'Menus originais':'Original menus',
    'Abrir os menus nativos sem exibir a barra superior':'Open native menus without displaying the original menu bar',
    'Ativar aderência e escolher o tipo':'Enable snapping and choose its type',
    'Outras ferramentas':'Other tools',
}

_language = 'pt_BR'


def choose_language(override, user_locale, system_locale):
    """Select PT-BR or EN based on QGIS UI locale, not on number formatting."""
    requested = str(user_locale if override and str(user_locale or '').strip() else system_locale or '')
    requested = re.split(r'[.@]', requested)[0].replace('-', '_').strip().lower()
    return 'pt_BR' if requested in ('pt_br', 'pt') else 'en'


def configure_language(override=None, user_locale=None, system_locale=None):
    """Read QGIS language settings; safe without locale keys on custom builds."""
    global _language
    if override is None or system_locale is None:
        from qgis.PyQt.QtCore import QLocale
        from qgis.core import QgsSettings
        settings = QgsSettings()
        if override is None:
            flag = settings.value('locale/overrideFlag', False)
            override = flag is True or str(flag).strip().lower() in ('true', '1', 'yes')
        if user_locale is None:
            user_locale = settings.value('locale/userLocale', '')
        if system_locale is None:
            system_locale = QLocale.system().name()
    _language = choose_language(override, user_locale, system_locale)
    return _language


def language():
    return _language


def tr(text):
    """Translate a *QRibbonSkin-owned* user-visible string; leave native text intact."""
    if not isinstance(text, str) or _language == 'pt_BR':
        return text
    return EN.get(text, text)


def ui_label(text):
    """Translate and sentence-case only labels created by QRibbonSkin.

    QGIS-owned QAction titles and menus must use their original strings, not
    this function. Internal routing keys are intentionally left untouched.
    """
    from .ux_rules import sentence_label
    return sentence_label(tr(text))


# QRibbonSkin 1.2 main Ribbon (RustGIS layout). English captions follow the
# RustGIS ribbon wording wherever a control has a RustGIS counterpart.
EN.update({
    '3D': '3D', 'API C++': 'C++ API', 'API PyQGIS': 'PyQGIS API',
    'Abrir, salvar e criar projetos': 'Open, save and create projects',
    'Adicionar': 'Add', 'Adicionar\ndados': 'Add\nData', 'Afastar': 'Zoom Out',
    'Ajuda de\ncomplementos': 'Plugin\nHelp',
    'Algoritmo indisponível: {alg}': 'Algorithm unavailable: {alg}',
    'Alterar rótulo': 'Change Label', 'Analisar': 'Analyze', 'Anotação': 'Annotation',
    'Anotações': 'Annotations', 'Anterior': 'Previous', 'Aparar/estender': 'Trim/Extend',
    'Aprender': 'Learn', 'Aproximar': 'Zoom In', 'Armazenamento': 'Storage',
    'Atalhos de\nteclado': 'Keyboard\nShortcuts', 'Atualizar': 'Refresh', 'Ação': 'Action',
    'Banco de\ndados': 'Database', 'Barras': 'Toolbars',
    'Barras de\ncomplementos': 'Plugin\nToolbars', 'Barras de\nferramentas': 'Toolbars',
    'Brilho e contraste': 'Brightness and Contrast', 'Buscar\ncomandos': 'Command\nSearch',
    'Buscar comandos': 'Command Search',
    'Buscar e executar qualquer comando do QGIS (Alt+Q)': 'Find and run any QGIS command (Alt+Q)',
    'Caixa de\nFerramentas': 'Tools', 'Calculadora\nraster': 'Raster\nCalculator',
    'Calculadora de malha': 'Mesh Calculator', 'Calculadora raster': 'Raster Calculator',
    'Calcular': 'Calculate', 'Camada': 'Layer', 'Camada da\nseleção': 'Layer From\nSelection',
    'Campos': 'Fields', 'Centralizar seleção': 'Pan to Selection', 'Colar': 'Paste',
    'Colar estilo': 'Paste Style',
    'Comandos das barras de ferramentas de complementos instalados': 'Commands from the toolbars of installed plugins',
    'Comunidade': 'Community', 'Console Python': 'Python Console',
    'Consulta de\ndefinição': 'Definition\nQuery', 'Conteúdo\nda ajuda': 'Help\nContents',
    'Controle\ntemporal': 'Time\nSlider', 'Copiar': 'Copy', 'Copiar estilo': 'Copy Style',
    'Corte cumulativo local': 'Local Cumulative Cut', 'Corte cumulativo total': 'Full Cumulative Cut',
    'Criar': 'Create',
    'Criar uma camada com as feições selecionadas (algoritmo nativo do QGIS)': 'Create a layer from the selected features (native QGIS algorithm)',
    'Dados\nweb': 'Web\nData', 'Definir SRC': 'Set CRS', 'Definição de camada': 'Layer Definition',
    'Desenho': 'Drawing', 'Designer de\nmodelos': 'Model\nBuilder', 'Deslocar curva': 'Offset Curve',
    'Destacar fixados': 'Highlight Pinned', 'Diagramas': 'Diagrams', 'Dicas de mapa': 'Map Tips',
    'Digitalização avançada': 'Advanced Digitizing', 'Dividir feições': 'Split Features',
    'Dividir partes': 'Split Parts', 'Doar': 'Donate', 'Duplicar': 'Duplicate',
    'Editar\nvértices': 'Edit\nVertices', 'Editar atributos': 'Edit Attributes',
    'Editar no local': 'Edit In-Place', 'Edições': 'Edits', 'Efeitos': 'Effects',
    'Elevação': 'Elevation', 'Escala\nvisível': 'Visible\nScale', 'Escala visível': 'Visible Scale',
    'Estatísticas': 'Statistics', 'Estilos': 'Styles', 'Estrutura de dados': 'Data Design',
    'Excluir': 'Delete', 'Expandir a Ribbon': 'Expand the ribbon', 'Exportar\nPDF': 'Export\nPDF',
    'Exportar\ncamada': 'Export\nLayer', 'Exportar\nfeições': 'Export\nFeatures',
    'Exportar\nmapa': 'Export\nMap', 'Exportar DXF': 'Export DXF', 'Exportar dados': 'Export Data',
    'Extensão total': 'Full Extent', 'Favoritos': 'Bookmarks', 'Feições': 'Features',
    'Ferramentas\nde edição': 'Editor\nTools', 'Filtro': 'Definition Query', 'Fixar': 'Pin',
    'Fonte de dados': 'Data Source', 'Fontes de\ndados': 'Data\nSources',
    'Geoprocessamento': 'Geoprocessing', 'Georreferen-\nciador': 'Geo-\nreferencer',
    'Gerenciador\nde estilos': 'Style\nManager', 'Gerenciador\nde layouts': 'Layout\nManager',
    'Gerenciar\ncomplementos': 'Plugin\nManager', 'Gerenciar edições': 'Manage Edits',
    'Girar rótulo': 'Rotate Label', 'Histograma local': 'Local Histogram',
    'Histograma total': 'Full Histogram', 'Histórico SQL': 'SQL History', 'Identificar': 'Identify',
    'Importar DWG/DXF': 'Import DWG/DXF', 'Incorporar camadas': 'Embed Layers',
    'Informações': 'Information', 'Informações\ndo raster': 'Raster\nInformation',
    'Inspecionar': 'Inspect', 'Interface\nclássica': 'Classic\nInterface',
    'Intervalo de visibilidade': 'Visibility Range', 'Inverter': 'Switch', 'Janelas': 'Windows',
    'Layouts': 'Layouts', 'Limpar': 'Clear', 'Mais': 'More', 'Mais brilho': 'More Brightness',
    'Mais contraste': 'More Contrast', 'Mais gama': 'More Gamma', 'Malha': 'Mesh',
    'Mapa\nbase': 'Basemap', 'Mapa em\nfoco': 'Focus on\nMap', 'Membros mantenedores': 'Sustaining Members',
    'Menos brilho': 'Less Brightness', 'Menos contraste': 'Less Contrast', 'Menos gama': 'Less Gamma',
    'Mensagens': 'Messages', 'Menus de complementos': 'Plugin Menus',
    'Mesclar atributos': 'Merge Attributes', 'Mesclar feições': 'Merge Features',
    'Modificar': 'Modify', 'Mostrar/ocultar': 'Show/Hide', 'Mover\nmapa': 'Pan',
    'Mover\nrótulo': 'Move\nLabel', 'Mundo': 'World', 'Navegador': 'Browser\nPane',
    'Nenhuma barra de complementos': 'No plugin toolbars', 'Nova\ncamada': 'New\nLayer',
    'Nova vista\n2D': 'New 2D\nView', 'Nova vista\nde mapa': 'New\nMap', 'Novo\nlayout': 'New\nLayout',
    'Novo\nrelatório': 'New\nReport', 'Opções': 'Options', 'Ordem das camadas': 'Layer Order',
    'Painel de\nferramentas': 'Tools\nPane', 'Painéis visíveis': 'Panel Visibility',
    'Participar': 'Get Involved', 'Perfil': 'Profile', 'Perfis': 'Profiles',
    'Perfis de\nusuário': 'User\nProfiles', 'Por\natributos': 'By\nAttributes',
    'Por\nlocalização': 'By\nLocation', 'Posicionamento': 'Label Placement',
    'Processamento': 'Processing', 'Projeções\npersonalizadas': 'Custom\nProjections',
    'Propriedades': 'Properties', 'Propriedades do projeto': 'Project Properties',
    'Próxima': 'Next', 'Python': 'Python', 'Página do\nQGIS': 'QGIS\nHome Page',
    'QRibbonSkin': 'QRibbonSkin', 'Raster': 'Raster', 'Realce': 'Enhancement',
    'Recarregar': 'Reload', 'Recolher a Ribbon': 'Collapse the ribbon', 'Recortar': 'Cut',
    'Relatar problema': 'Report an Issue', 'Remodelar': 'Reshape', 'Remover': 'Remove',
    'Resolução nativa': 'Native Resolution', 'Restaurar painéis': 'Restore Panels',
    'Rolar a Ribbon para a direita': 'Scroll the ribbon right',
    'Rolar a Ribbon para a esquerda': 'Scroll the ribbon left', 'Rotulagem': 'Labeling',
    'Rotulagem do mapa': 'Map Labeling', 'SRC do projeto': 'Project CRS',
    'Salvar definição': 'Save Definition', 'Saída': 'Output',
    'Selecionar feições pela relação espacial com outra camada (algoritmo nativo do QGIS)': 'Select features by their spatial relationship with another layer (native QGIS algorithm)',
    'Selecionar por\natributos': 'Select By\nAttributes', 'Selecionar por\nlocalização': 'Select By\nLocation',
    'Selecione uma camada no painel Camadas para definir seu estilo.': 'Select a layer in Layers to style it.',
    'Selecione uma camada no painel Camadas para ver suas ferramentas de dados.': 'Select a layer in Layers to see its data tools.',
    'Selecione uma camada vetorial no painel Camadas para rotulá-la.': 'Select a feature layer in Layers to label it.',
    'Simbologia': 'Symbology', 'Simplificar': 'Simplify', 'Sistemas de referência': 'Coordinate Systems',
    'Sobre': 'About', 'Status': 'Status', 'Tabela': 'Table', 'Tabela de\natributos': 'Attribute\nTable',
    'Tabela de atributos': 'Attribute Table', 'Tela cheia': 'Full Screen', 'Tempo': 'Time',
    'Traçado': 'Tracing', 'Tudo': 'All', 'Ver não\nposicionados': 'View\nUnplaced',
    'Verificar\nversão': 'Check for\nUpdates', 'Vista': 'View', 'Visão de\ncores': 'Color\nVision',
    'Visão geral': 'Overview', 'Visível': 'Visible', 'Web': 'Web', 'Zoom na\ncamada': 'Zoom To\nLayer',
    'Zoom na camada': 'Zoom To Layer', 'Zoom na seleção': 'Zoom To Selection',
    'Início': 'Home', 'Dados': 'Data', 'Estilo': 'Style', 'Editar': 'Edit', 'Exibir': 'View',
    'Publicar': 'Publish', 'Complementos': 'Plugins', 'Configurações': 'Settings', 'Ajuda': 'Help',
    'Projeto': 'Project', 'Navegar': 'Navigate', 'Seleção': 'Selection', 'Ferramentas': 'Tools',
    'Histórico': 'History', 'Exibição': 'Display', 'Navegação': 'Navigation', 'Interface': 'Interface',
    'Relatório': 'Report', 'Rótulos': 'Labels', 'Aderência': 'Snapping', 'Painéis': 'Panels',
    'Área de transferência': 'Clipboard', 'Salvar': 'Save', 'Salvar como': 'Save As',
    'Desfazer': 'Undo', 'Refazer': 'Redo', 'Medir': 'Measure', 'Selecionar': 'Select',
    'Camadas': 'Layers', 'Layout': 'Layout', 'Vetor': 'Vector', 'Personalizar': 'Customize',
    'Ajuda': 'Help', 'Decorações': 'Decorations',
})

# QRibbonSkin 1.2.1: Project page in the Ribbon.
EN.update({
    'Recentes e modelos': 'Recent and Templates', 'Projetos\nrecentes': 'Recent\nProjects',
    'Novo a partir\nde modelo': 'New From\nTemplate', 'Abrir de': 'Open From',
    'Salvar em': 'Save To', 'Importar e exportar': 'Import and Export',
    'Importar/\nexportar': 'Import/\nExport', 'Projeto atual': 'Current Project',
    'Reverter': 'Revert', 'Fechar': 'Close', 'Sair do QGIS': 'Exit QGIS',
    'Novo': 'New', 'Abrir': 'Open', 'Salvar\ncomo': 'Save\nAs',
})
