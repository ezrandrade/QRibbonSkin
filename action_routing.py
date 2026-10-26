"""Deterministic, Qt-independent ownership rules for QRibbonSkin task tabs.

These rules influence *only* where references to native QAction objects are
presented. No QGIS action is cloned, renamed, disconnected, or reparented.

A command has one primary Ribbon location. The source native QGIS menus and
QGIS locator remain unmodified and available through the original mechanisms.
"""

import re
import unicodedata


def normalize_caption(text):
    """Canonical caption for routing, independent of case, mnemonics, accents."""
    text = str(text or "").replace("&&", "\u0000").replace("&", "").replace("\u0000", "&")
    text = unicodedata.normalize("NFKD", text.casefold())
    return " ".join("".join(ch for ch in text if not unicodedata.combining(ch)).split())


# Route only affirmative, meaning-specific UI commands, not generic "Save" or
# "Open". English stems also recognize untranslated upstream Qt object names.
_PUBLICATION = re.compile(
    r"(?:layout|impress|imprim|print|export|exportar|pdf|atlas|relator|report|"
    r"save(?:map|canvas|image|pdf)|imagem|image|publication|publica)",
    re.IGNORECASE,
)

# Imports (e.g. 'Importar/Exportar') can contain both publication and data
# management operations. Keep that whole native submenu in Project, instead of
# duplicating/moving unrelated imports into Publish.
_MIXED_IMPORT_EXPORT = re.compile(
    r"(?:importar\s*/\s*exportar|import\s*/\s*export|import\s+(?:and|e)\s+export)",
    re.IGNORECASE,
)

_STYLE = re.compile(
    r"(?:simbolog|symbolog|simbologia|style|estilo|rotul|label|diagram|"
    r"graduad|categori|propriedad|properties|render|simbol)",
    re.IGNORECASE,
)


def action_identity(action):
    """Unique runtime identity: labels can legitimately be repeated."""
    return id(action)


def is_publication_action(action):
    """Identify publication/printing/export controls from native metadata."""
    name = ""
    if hasattr(action, "objectName"):
        try:
            name = action.objectName() or ""
        except (RuntimeError, TypeError):
            name = ""
    caption = normalize_caption(action.text())
    if _MIXED_IMPORT_EXPORT.search(caption):
        return False
    return bool(_PUBLICATION.search(normalize_caption(name)) or _PUBLICATION.search(caption))


def tab_owns_action(action, tab, accessor):
    """Ensure shared QGIS sources have a single, meaningful task owner."""
    if accessor in ("projectMenu", "fileToolBar"):
        publish = is_publication_action(action)
        if tab == "Projeto":
            return not publish
        if tab == "Publicar":
            return publish
    if accessor == "layerMenu":
        is_style = bool(_STYLE.search(normalize_caption(action.text())))
        if tab == "Dados":
            return not is_style
        if tab == "Estilo":
            return is_style
    return True


def distinct_native_actions(actions, used=None):
    """Stable, identity-based deduplication; never merge by caption."""
    seen = used if used is not None else set()
    distinct = []
    for action in actions:
        identity = action_identity(action)
        if identity not in seen:
            distinct.append(action)
            seen.add(identity)
    return distinct
