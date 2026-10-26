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
    # Georeferencer
    'Abrir dados':'Open data', 'Sessão':'Session', 'Arquivos':'Files',
    'Editar PCT':'Edit GCPs', 'Arquivos PCT':'GCP files',
    'Aderência':'Snapping', 'Digitalização':'Digitizing',
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
