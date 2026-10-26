"""Pure, Qt-free visual hierarchy for the task-based ribbon.

The original QAction objects, menus, action order inside QGIS and Processing
algorithms remain untouched.  Only the visually prominent button is selected.

QRibbonSkin 0.9.3 — experimental; 2026-10-24.
"""
import unicodedata


def normalize(text):
    value = unicodedata.normalize("NFKD", str(text or "").replace("&", "").casefold())
    return " ".join("".join(ch for ch in value if not unicodedata.combining(ch)).split())


LEAD_TOKENS = {
    "Projeto": ("novo", "new", "abrir", "open", "salvar", "save"),
    "Início": ("mover", "pan", "aproximar", "zoom", "adicionar", "add"),
    "Dados": ("adicionar", "add", "camada", "layer", "tabela", "table"),
    "Estilo": ("simbologia", "symbology", "estilo", "style", "rotulo", "label"),
    "Editar": ("alternar edicao", "toggle editing", "editar", "edit", "vertice", "vertex"),
    "Análise": ("processamento", "processing", "vetor", "vector", "raster", "buffer"),
    "Exibir": ("camadas", "layers", "painel", "panel", "atualizar", "refresh"),
    "Publicar": ("layout", "imprimir", "print", "exportar", "export"),
    "Plugins": ("gerenciar", "manage", "plugins", "complementos"),
    "Configurações": ("opcoes", "options", "configuracoes", "settings"),
    "Ajuda": ("ajuda", "help", "documentacao", "documentation"),
}


def prioritized_actions(tab, actions):
    """Return visual order with one semantic lead; preserve all other positions.

    Does not deduplicate actions (the owning ribbon does that by QAction id).
    A preference that is not present simply preserves upstream QGIS order.
    """
    source = list(actions)
    if len(source) < 2:
        return source
    tokens = LEAD_TOKENS.get(tab, ())
    for token in tokens:
        for i, action in enumerate(source):
            name = normalize(action.text())
            if token in name:
                return [source[i], *source[:i], *source[i + 1:]]
    return source


def menu_caption(group_label):
    """An explicit, contextual fallback label rather than generic 'Mais'."""
    label = " ".join(str(group_label or "Ferramentas").split())
    return f"Mais em {label}"
