"""查询串处理——移植自 curlconverter 的 Query.ts."""

from urllib.parse import unquote

from burpr.curlconvert.word import Word, eq


def _percent_encode(s: str) -> str:
    """匹配 Python urllib.parse.quote() 的行为(按 UTF-8 字节编码非 ASCII)."""
    out = []
    for b in s.encode("utf-8"):
        if (
            (0x41 <= b <= 0x5A)  # A-Z
            or (0x61 <= b <= 0x7A)  # a-z
            or (0x30 <= b <= 0x39)  # 0-9
            or b in (0x2D, 0x2E, 0x5F, 0x7E)  # -._~
        ):
            out.append(chr(b))
        else:
            out.append("%" + format(b, "02X"))
    return "".join(out)


def percent_encode(s: Word) -> Word:
    return Word([
        _percent_encode(t) if isinstance(t, str) else t for t in s.tokens
    ])


def percent_encode_plus(s: Word) -> Word:
    import re
    return Word([
        re.sub(r"%20", "+", _percent_encode(t)) if isinstance(t, str) else t
        for t in s.tokens
    ])


class _URIError(Exception):
    """模拟 JS 的 URIError(decodeURIComponent 遇到非法 % 转义时抛出)."""


def _decode_uri_component(s: str) -> str:
    """重实现 decodeURIComponent。非法百分号编码抛 _URIError(对齐 JS 行为)."""
    # 先校验:每个 % 后必须跟两个十六进制数字,且能解码成合法 UTF-8
    i = 0
    while i < len(s):
        if s[i] == "%":
            if i + 2 >= len(s) or not _is_hex(s[i + 1]) or not _is_hex(s[i + 2]):
                raise _URIError("URI malformed")
            i += 3
        else:
            i += 1
    try:
        # unquote 默认按 UTF-8,errors='strict' 遇非法序列抛 UnicodeDecodeError
        return unquote(s, encoding="utf-8", errors="strict")
    except (UnicodeDecodeError, ValueError) as e:
        raise _URIError("URI malformed") from e


def _is_hex(c: str) -> bool:
    return c in "0123456789abcdefABCDEF"


def word_decode_uri_component(s: Word) -> Word:
    return Word([
        _decode_uri_component(t) if isinstance(t, str) else t for t in s.tokens
    ])


def parse_query_string(s):
    """解析 ?a=1&b=2 → (QueryList, QueryDict) 或 (None, None).

    s 为空或 None → (None, None)。s 不含前导 '?'。
    """
    if s is None or s.is_empty():
        return [None, None]

    as_list = []
    for param in s.split("&"):
        # 多数库无法区分 a=&b= 和 a&b,遇到 a&b 型就放弃
        if not param.includes("="):
            return [None, None]

        key, val = param.split("=", 2)
        try:
            # 推荐解码前把 + 换成空格
            decoded_key = word_decode_uri_component(key.replace(_PLUS, " "))
            decoded_val = word_decode_uri_component(val.replace(_PLUS, " "))
        except _URIError:
            # 含非法百分号编码,无法正确转换
            return [None, None]
        # 若查询串无法往返(round-trip),无法正确转换
        round_trip_key = percent_encode(decoded_key)
        round_trip_val = percent_encode(decoded_val)
        if (
            (not eq(round_trip_key, key)
             and not eq(round_trip_key.replace(_PCT20, "+"), key))
            or (not eq(round_trip_val, val)
                and not eq(round_trip_val.replace(_PCT20, "+"), val))
        ):
            return [None, None]
        as_list.append([decoded_key, decoded_val])

    # 分组键
    key_words = {}
    unique_keys = {}
    prev_key = None
    for key, val in as_list:
        key_str = key.to_string()
        if prev_key == key_str:
            unique_keys[key_str].append(val)
        elif key_str not in unique_keys:
            unique_keys[key_str] = [val]
            key_words[key_str] = key
        else:
            # 重复键之间夹了别的键 → 无法表示为 dict
            return [as_list, None]
        prev_key = key_str

    # 单元素列表还原为元素
    as_dict = []
    for key_str, val in unique_keys.items():
        as_dict.append([key_words[key_str], val[0] if len(val) == 1 else val])

    return [as_list, as_dict]


import re
_PLUS = re.compile(r"\+")
_PCT20 = re.compile(r"%20")
