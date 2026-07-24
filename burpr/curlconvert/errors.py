"""基础工具——移植自 curlconverter 的 utils.ts.

CCError 继承 burpr.BurpParseError,使现有 `pytest.raises(BurpParseError)` 仍通过。
"""

import base64

from burpr.burpr import BurpParseError


class CCError(BurpParseError):
    """curlconverter 解析错误."""

    pass


def has(obj: dict, prop) -> bool:
    """等价于 JS 的 Object.prototype.hasOwnProperty."""
    return prop in obj


def btoa(s: str) -> str:
    """等价于 JS 的 btoa(按 UTF-8 编码后 base64)."""
    return base64.b64encode(s.encode("utf-8")).decode("ascii")


def is_int(s: str) -> bool:
    """等价于 JS 的 /^\\s*[+-]?\\d+$/.test(s)."""
    s = s.strip()
    if not s:
        return False
    if s[0] in "+-":
        s = s[1:]
    return s.isdigit() and len(s) > 0
