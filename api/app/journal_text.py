"""Reading a journal page's blocks (BlockNote JSON): its words and what it @mentions.

Blocks look like {"type": "paragraph", "props": {...}, "content": [inline...], "children": [blocks]}.
Inline content is text ({"type": "text", "text": ...}), links (with their own content), our
mentions ({"type": "mention", "props": {"kind": "model", "ref": "3", "label": "Sherman"}}), or,
for tables, {"type": "tableContent", "rows": [{"cells": [...]}]}.
"""
KINDS = ("model", "supply", "page", "game", "gear")   # game = a board game


def inline_text(content) -> str:
    """The words in a block's inline content: text, links, mentions and table cells."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(inline_text(item) for item in content)
    if isinstance(content, dict):
        if content.get("type") == "mention":
            return "@" + str(content.get("props", {}).get("label", ""))
        if content.get("type") == "tableContent":
            return " ".join(inline_text(cell) for row in content.get("rows", []) for cell in row.get("cells", []))
        if isinstance(content.get("text"), str):
            return content["text"]
        return inline_text(content.get("content", ""))     # a link or a table cell
    return ""


def plain_text(blocks) -> str:
    """Every word in the blocks, one block per line (nested blocks included)."""
    lines = []
    for block in blocks or []:
        if not isinstance(block, dict):
            continue
        line = inline_text(block.get("content")).strip()
        if line:
            lines.append(line)
        nested = plain_text(block.get("children"))
        if nested:
            lines.append(nested)
    return "\n".join(lines)


def mentions(node) -> set[tuple[str, int]]:
    """Every (kind, id) the blocks @mention."""
    found_ = set()

    def walk(n):
        if isinstance(n, list):
            for item in n:
                walk(item)
        elif isinstance(n, dict):
            if n.get("type") == "mention":
                props = n.get("props", {})
                kind, ref = props.get("kind"), str(props.get("ref", ""))
                if kind in KINDS and ref.isdigit():
                    found_.add((kind, int(ref)))
            for value in n.values():
                if isinstance(value, (list, dict)):
                    walk(value)

    walk(node)
    return found_
