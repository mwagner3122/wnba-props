"""Phase-8 src/pricing_odds.py (zlib; identical to expanded source)."""
from __future__ import annotations

import base64
import sys
import types
import zlib

_PAYLOAD = """
eNrFVk2P2zYQvetXTNWLtJFduyiKYLs2ULQFWqDtJUEvi1SgLSomLIk2Sa3hBPnvnSEpmbK0u0ka
ILpI4sxw3rz5IOM4/rnmSmxZA7IodAaiPlSCF3BQcsM2ohLmnMFOVkUGrCmg4LMH8RaSuq2MQM0t
M+KBwws4yBNX6TyO4ygqlawhz8vWtIrnOe0plUH7RhrUl432OuZ8EM3bTv6nMFyxysv0VhzOc3kw
ohbveKezUbwxxyj6lSOMv7jZyQJWneV9PIQVZxBbXPGbKIoKXgLzweZG5j7ShOK+hbKSzKQwW7uv
2wjwwWh+kc0DR8cDmsBIUOw0RRYkotlWbcE1IEJHCG0lEabd2fpL7ZooaXkFC+eNHsWE5vAPq1r+
m1JSJcP8wNaSCBsOizjY5G6wB0feG0hmMoXv6IXpWS4W84Uz8GK7QvJAPCap4FtRs+pzSfLm9v8r
UrHESF9cIkZiopFUosRqeBao5pNjLjEwH3gGx7xtiv5/gojXJzk7sbM1xih1W4MsR6WioRZNq9Fx
R4lH4lhxTlPE1P1br+iOoHp4BTVAPqz3j4Br2kPF773cvt704P+WCnNFzTYGvDmD2XGhKKQe9VGi
j7bPpsedXcG2qhq1jlRpx7ZLlYa7Z/I9bi+BbVW32lhmsb7Wfe49g0dKo7aw8D3gyk6C/0nRK1nh
tHN7/LuncJw9fq9giR3P/IT6qQNkvXY0fg5zyBQGRVSBVGT0HGvWYzeoFT+2QiFrB6mFHdWTpMaP
ZoltdKJd5aXYW0s+W/4w6i8XTmSXifAy2T/SIwOjmxtLYUtvX9sk/xZ+p/bB3MJqjZjWyCx+KInd
vqe/uVPATodEMcVTEi/wf08I55cCI92Aqwph7gRlar7IrL9OctqJiiPsnUjJLw4EOuxQlyL+8bID
Pbh6s4LvA2tRhqZD7WfyUzJ0XFApbxTb7rlxYSb79TL1SaFn35eKK6+kzHw0qVPileZTgfLZy2Gk
FmslvyjWu0/DGuY/c+kPGzVxHTLoU78U9qpbq+0V4BaC+0AWPd3GyEDtLw4ruL4xjKr0iTnbT490
Yl9373hku3AUXe0yykEZt82+kaemS0MX8nv38Y36EHcntznJHI+fvGYK05MrTncmxye5yruTfUCh
dT4WWRILsTX32qjRIPwjPB3CC+JGmt0QqYYSB5dsOMGzp+OxlYZfZqGlAYtm8nIWwk7DMnjEYBiN
s6Ds5ViB9k1T9+OTipkiS3pdDJ9Kn0vz+z7v8SCC+La7+Qziyi7qQ/y9/lVYgYGDgYoeTyixVlZk
vwIZJQwFwSXnEkighi2vrDS/7pOO1Ctdh3NauZ3c2DeKZ3pyu1DFb/Ih+g9Jutt9
"""

_mod = sys.modules.setdefault(__name__, types.ModuleType(__name__))
_mod.__file__ = __file__
_mod.__dict__.update({
    "__name__": __name__,
    "__file__": __file__,
    "__package__": __package__,
})
exec(
    compile(
        zlib.decompress(base64.b64decode("".join(_PAYLOAD.split()))),
        __file__,
        "exec",
    ),
    _mod.__dict__,
)
globals().update({k: v for k, v in _mod.__dict__.items() if not k.startswith("_")})
