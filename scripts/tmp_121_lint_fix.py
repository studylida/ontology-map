from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

for relative, old, new in (
    (
        "server/src/ontology_map/db/review_fixture.py",
        "    for index, (key, name, _kind) in enumerate(definitions):\n",
        "    for key, name, _kind in definitions:\n",
    ),
    (
        "server/src/ontology_map/db/panel_fixture.py",
        "    for index, (key, node_id) in enumerate(ids.items()):\n",
        "    for key, node_id in ids.items():\n",
    ),
):
    path = ROOT / relative
    text = path.read_text(encoding="utf-8")
    if old not in text:
        raise RuntimeError(f"expected loop not found: {relative}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")
