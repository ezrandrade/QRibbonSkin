"""Menu introspection helpers; Qt-free to enable deterministic offline tests.

Native QMenu / QAction objects are never cloned, reparented or moved. Only
references and display metadata are used to build QRibbonSkin widgets.
"""


def native_caption(text):
    """Remove Qt menu mnemonics while retaining literal ampersands."""
    # QGIS localized menus use & as a mnemonic; && is a literal ampersand.
    return str(text or "").replace("&&", "\u0000").replace("&", "").replace("\u0000", "&").split("\t")[0].strip()


def iter_native_menus(menu_bar):
    """Yield (translated title, QMenu) for all visible native root menus."""
    if menu_bar is None:
        return
    for action in menu_bar.actions():
        menu = action.menu()
        if menu is None or not action.isVisible() or action.isSeparator():
            continue
        title = native_caption(action.text()) or native_caption(menu.title())
        if title:
            yield title, menu


def group_menu_actions(menu, max_actions=3):
    """Group original QActions, preserving order, separators and menu nesting.

    Returns tuples of ("menus"|"actions", [QAction,...]). QMenus are kept as
    live submenus rather than being cloned, so lazy plugin content still works.
    """
    groups = []
    pending = []
    pending_kind = None

    def flush():
        nonlocal pending, pending_kind
        if pending:
            groups.append((pending_kind, pending))
        pending, pending_kind = [], None

    for action in menu.actions():
        if action.isSeparator():
            flush()
            continue
        # QAction for a dynamically populated QMenu must be kept, even if the
        # QMenu is currently empty. QAction::trigger is managed by QGIS.
        kind = "menus" if action.menu() is not None else "actions"
        if not native_caption(action.text()) and action.menu() is None:
            continue
        if pending and (pending_kind != kind or len(pending) >= max_actions):
            flush()
        pending_kind = kind
        pending.append(action)
    flush()
    return groups


def native_menu_sections(menu):
    """Yield sections from a native QMenu in native action order.

    A plain-action section ends at a separator or submenu. A submenu is an
    independent section, but still references the QGIS-owned QMenu; that
    makes deep and dynamic submenus accessible without cloning any action.
    The helper is deliberately independent of Qt for offline verification.
    """
    actions = []

    def flush():
        if actions:
            result = ("actions", native_caption(menu.title()), tuple(actions))
            actions.clear()
            return result
        return None

    for action in menu.actions():
        if not action.isVisible():
            continue
        if action.isSeparator():
            section = flush()
            if section:
                yield section
            continue
        submenu = action.menu()
        if submenu is not None:
            section = flush()
            if section:
                yield section
            caption = native_caption(action.text()) or native_caption(submenu.title())
            if caption:
                yield "submenu", caption, submenu
        elif native_caption(action.text()):
            actions.append(action)
    section = flush()
    if section:
        yield section


def inline_limit_for_group(expected_count, threshold=4, retained=3):
    """Limit crowded QGIS menu sections without discarding native actions.

    Sections with up to `threshold` actions remain direct. Larger sections
    retain `retained` commands in the Ribbon; the rest go into a native,
    dynamically populated menu. Pure function independent of Qt/language.
    """
    if not isinstance(expected_count, int) or expected_count < 0:
        raise ValueError("expected_count must be a non-negative integer")
    if not (1 <= retained <= threshold):
        raise ValueError("invalid group overflow thresholds")
    return retained if expected_count > threshold else None


# Display-only labels for native action sections. Never rename or duplicate QGIS
# QActions or use menu-language assumptions to route commands.
def native_action_group_heading(actions, used_titles=(), root_title="", translate=None):
    """Give each consecutive native-action section a useful, distinct caption.

    QGIS separators split root menus into independent sections. Using the root
    menu title for every section creates meaningless repeated captions such as
    Edit / Edit / Edit. This helper looks at the *actual actions* in each section
    and chooses a short semantic title for common groups. Unrecognized QGIS or
    plugin commands retain a native QAction caption as a safe, multilingual
    fallback. The returned heading is a display-only string; ``actions`` are
    never mutated. Portuguese semantic labels can be translated by the caller.
    """
    import re
    import unicodedata

    def canonical(value):
        plain = unicodedata.normalize("NFKD", str(value or ""))
        plain = "".join(c for c in plain if not unicodedata.combining(c))
        return " ".join(re.sub(r"[^\w]+", " ", plain.casefold()).split())

    captions = [native_caption(a.text()) for a in actions]
    captions = [caption for caption in captions if caption]
    if not captions:
        return root_title or "Ferramentas"

    normalized = [canonical(caption) for caption in captions]
    words = " ".join(normalized)
    tokens = set(words.split())

    def any_token(*values):
        return bool(tokens.intersection(values))

    # Recognize familiar native menu sections in Brazilian Portuguese and
    # English. The fallback works in any native QGIS locale or plugin language.
    semantic = None
    if any_token("desfazer", "refazer", "undo", "redo"):
        semantic = "Histórico de edição"
    elif any_token("recortar", "copiar", "colar", "cut", "copy", "paste"):
        semantic = "Área de transferência"
    elif any_token("excluir", "eliminar", "delete", "deletar"):
        semantic = "Exclusão de feições"
    elif (any_token("rotacionar", "deslocamento", "rotate", "offset")
          and any_token("simbolos", "simbolo", "symbol", "symbols", "pontos", "points")):
        semantic = "Simbologia de pontos"
    elif (any_token("poligono", "poligonos", "polygon", "polygons", "feicao", "feicoes", "feature", "features")
          and any_token("adicionar", "criar", "add", "create", "desenhar", "draw")):
        semantic = "Criação de feições"
    elif any_token("zoom", "aproximar", "afastar", "pan", "enquadrar"):
        semantic = "Navegação do mapa"
    elif any_token("selecionar", "selecao", "select", "selection"):
        semantic = "Seleção"

    translate = translate or (lambda value: value)
    used = {canonical(value) for value in used_titles}
    root = canonical(root_title)

    def is_new(value):
        return (bool(value) and canonical(translate(value)) not in used
                and canonical(translate(value)) != root)

    # Preference order: meaningful semantic heading, native action, then a
    # short combination of native captions. Never call a section by tab name.
    candidates = ([semantic] if semantic else [])
    candidates.extend(captions)
    if len(captions) >= 2:
        candidates.extend((captions[0] + " / " + name for name in captions[1:]))
    for candidate in candidates:
        if candidate and is_new(candidate):
            return candidate

    # Identical actions can appear in separate native sections. Uniqueness is
    # still preferable to repeating the tab caption or mislabeling their tools.
    base = semantic or captions[0]
    index = 2
    while not is_new(f"{base} ({index})"):
        index += 1
    return f"{base} ({index})"


def unique_native_group_heading(preferred, actions, used_titles=(), root_title="", translate=None):
    """Keep native submenu labels unless they collide with another group."""
    import unicodedata

    def key(value):
        text = unicodedata.normalize("NFKD", str(value or "")).casefold()
        return "".join(c for c in text if not unicodedata.combining(c)).strip()

    translate = translate or (lambda value: value)
    if (preferred and key(preferred) != key(root_title)
            and key(translate(preferred)) not in {key(item) for item in used_titles}):
        return preferred
    return native_action_group_heading(actions, used_titles, root_title, translate=translate)
