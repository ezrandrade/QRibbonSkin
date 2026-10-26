"""Pure caption layout helpers for the QRibbonSkin task Ribbon.

These helpers change only the drawn label of an original QAction. They do not
modify action names, tooltips, menu structure or the QGIS project.
"""


def _clean(text):
    return " ".join(str(text or "").replace("\n", " ").split())


def _splits(text, measure, available):
    words = _clean(text).split()
    if not words:
        return []
    full = " ".join(words)
    if measure(full) <= available:
        return [(0, [full])]
    candidates = []
    for index in range(1, len(words)):
        left, right = " ".join(words[:index]), " ".join(words[index:])
        widths = (measure(left), measure(right))
        if max(widths) <= available:
            # Prefer even lines without a very short orphan.
            candidates.append((max(widths) - min(widths), [left, right]))
    return sorted(candidates, key=lambda x: x[0])


def suitable_two_line_width(text, measure, padding, minimum=164, maximum=234):
    """Smallest reasonable width that fits up to 2 text lines."""
    if maximum < minimum:
        raise ValueError("maximum must be >= minimum")
    for width in range(minimum, maximum + 1, 2):
        if _splits(text, measure, max(1, width-padding)):
            return width
    return maximum


def two_line_caption(text, measure, available):
    """Prefer 1 or 2 complete lines; ellipsis only if physically impossible."""
    caption = _clean(text)
    if not caption:
        return ""
    found = _splits(caption, measure, max(1, available))
    if found:
        return "\n".join(found[0][1])
    # Impossibly long words/captions: never paint text outside the button.
    # The complete native action title is available in the tooltip/menu.
    words = caption.split()
    if len(words) > 1:
        # Choose the most balanced of all two-line arrangements, then elide.
        splits = [(" ".join(words[:i]), " ".join(words[i:]))
                  for i in range(1, len(words))]
        first, second = min(splits, key=lambda parts:
                            max(measure(parts[0]), measure(parts[1])))
        return "\n".join(_ellipsize(line, measure, available)
                         for line in (first, second))
    return _ellipsize(caption, measure, available)


def _ellipsize(text, measure, available):
    if measure(text) <= available:
        return text
    ellipsis = "…"
    if measure(ellipsis) > available:
        return ""
    trimmed = text
    while trimmed and measure(trimmed + ellipsis) > available:
        trimmed = trimmed[:-1]
    return trimmed.rstrip() + ellipsis


def full_caption_width(text, measure, padding, minimum=104, max_lines=2):
    """Minimum widget width that displays *all* words without ellipses.

    Most captions fit in the compact minimum. Only long translations receive
    additional width. QGIS QAction captions are not modified. We allow an
    unusually long word to widen the button rather than clip it.
    """
    words = _clean(text).split()
    if not words:
        return minimum
    if max_lines < 1:
        raise ValueError("max_lines must be positive")
    # Each partition is a full word (or a line of full words). Dynamic
    # programming avoids exponential splitting for unusually long captions.
    n = len(words)
    widths = [[0] * (n + 1) for _ in range(n)]
    for i in range(n):
        for j in range(i + 1, n + 1):
            widths[i][j] = measure(" ".join(words[i:j]))
    cache = {}
    def min_width(start, lines):
        key = (start, lines)
        if key in cache:
            return cache[key]
        if lines == 1:
            result = widths[start][n]
        else:
            result = min(
                max(widths[start][cut], min_width(cut, lines - 1))
                for cut in range(start + 1, n - lines + 2)
            )
        cache[key] = result
        return result
    bound = min(max_lines, n)
    min_text_width = min(min_width(0, lines) for lines in range(1, bound + 1))
    return max(minimum, int(min_text_width + padding + 0.999))


def complete_caption_lines(text, measure, available_width, max_lines=2):
    """Return a balanced complete caption; never insert an ellipsis.

    Callers first allocate full_caption_width. A defensive fallback still
    preserves text if the font changes after measuring.
    """
    words = _clean(text).split()
    if not words:
        return ""
    caption = " ".join(words)
    if measure(caption) <= available_width:
        return caption
    if max_lines < 2 or len(words) == 1:
        return caption
    candidates = []
    for cut in range(1, len(words)):
        lines = (" ".join(words[:cut]), " ".join(words[cut:]))
        widths = [measure(line) for line in lines]
        candidates.append((max(widths), max(widths) - min(widths), lines))
    fitted = [item for item in candidates if item[0] <= available_width]
    _, _, best = min(fitted or candidates, key=lambda item: item[:2])
    return "\n".join(best)
