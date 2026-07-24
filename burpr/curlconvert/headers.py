"""HTTP 头处理——移植自 curlconverter 的 Headers.ts."""

from burpr.curlconvert.word import Word, eq, join_words

# https://en.wikipedia.org/wiki/List_of_HTTP_header_fields#Standard_request_fields
_COMMA_SEPARATED = {h.lower() for h in [
    "A-IM", "Accept", "Accept-Charset", "Accept-Encoding", "Accept-Language",
    "Access-Control-Request-Headers", "Cache-Control", "Connection",
    "Content-Encoding", "Expect", "Forwarded", "If-Match", "If-None-Match",
    "Range", "TE", "Trailer", "Transfer-Encoding", "Upgrade", "Via", "Warning",
]}
_SEMICOLON_SEPARATED = {h.lower() for h in ["Content-Type", "Cookie", "Prefer"]}


class Headers:
    """有序头列表;值为 None 表示该头被显式禁用(如 -H 'Host:')."""

    def __init__(self, header_args=None, warnings=None, arg_name="--header/H"):
        if warnings is None:
            warnings = []
        headers = []

        if header_args:
            for header in header_args:
                if header.starts_with("@"):
                    warnings.append([
                        "header-file",
                        "passing a file for "
                        + arg_name
                        + " is not supported: "
                        + repr(header.to_string()),
                    ])
                    continue

                if header.includes(":"):
                    name, value = header.split(":", 2)
                    # -H 'Header-Name:' 禁用发送该头。
                    # 冒号后只有空格则忽略,除非 -H 'Host: '
                    # https://github.com/curl/curl/issues/12782
                    has_value = bool(
                        value and (value if eq(name, "Host") else value.trim()).to_bool()
                    )
                    header_value = value.remove_first_char(" ") if has_value else None
                    headers.append([name, header_value])
                elif header.includes(";"):
                    name = header.split(";", 2)[0]
                    headers.append([name, Word()])
                # else: 忽略无冒号无分号的头

        self.lowercase = bool(headers) and all(
            eq(h[0], h[0].to_lower_case()) for h in headers
        )

        # 处理重复头:Cookie/Accept 合并,其它告警
        unique_headers = {}
        for name, value in headers:
            lower_name = name.to_lower_case().to_string()
            unique_headers.setdefault(lower_name, []).append([name, value])

        merged_headers = []
        for lower_name, repeated in unique_headers.items():
            if len(repeated) == 1:
                merged_headers.append(repeated[0])
                continue
            # 全为 None → 用第一个
            if all(h[1] is None for h in repeated):
                last_repeat = repeated[-1]
                if len({h[0].to_string() for h in repeated}) > 1:
                    warnings.append([
                        "repeated-header",
                        f'"{last_repeat[0]}" header unset {len(repeated)} times',
                    ])
                merged_headers.append(last_repeat)
                continue
            # 至少一个非 None 值,忽略 None
            non_empty = [h for h in repeated if h[1] is not None]
            if len(non_empty) == 1:
                merged_headers.append(non_empty[0])
                continue
            merge_char = ""
            if lower_name in _COMMA_SEPARATED:
                merge_char = ", "
            elif lower_name in _SEMICOLON_SEPARATED:
                merge_char = "; "
            if merge_char:
                merged = join_words([h[1] for h in non_empty], merge_char)
                warnings.append([
                    "repeated-header",
                    f'merged {len(non_empty)} "{non_empty[-1][0]}" headers '
                    f'together with "{merge_char.strip()}"',
                ])
                merged_headers.append([non_empty[0][0], merged])
                continue

            warnings.append([
                "repeated-header",
                f'found {len(non_empty)} "{non_empty[-1][0]}" headers, '
                "only the last one will be sent",
            ])
            merged_headers.extend(non_empty)

        self.headers = merged_headers

    def __len__(self):
        return len(self.headers)

    def __iter__(self):
        return iter(self.headers)

    def get(self, header: str):
        """取第一个匹配(大小写不敏感)的头;无则 None,显式禁用也是 None."""
        lookup = header.lower()
        for h, v in self.headers:
            if h.to_lower_case().to_string() == lookup:
                return v
        return None

    def get_content_type(self):
        ct = self.get("content-type")
        if ct is None:
            return ct
        return ct.split(";")[0].trim().to_string()

    def has(self, header) -> bool:
        lookup = header.to_lower_case() if isinstance(header, Word) else header.lower()
        for h in self.headers:
            if eq(h[0].to_lower_case(), lookup):
                return True
        return False

    def set_if_missing(self, header, value) -> bool:
        """不覆盖已有头."""
        if self.has(header):
            return False
        if self.lowercase:
            header = header.lower()
        k = Word(header) if isinstance(header, str) else header
        v = Word(value) if isinstance(value, str) else value
        self.headers.append([k, v])
        return True

    def prepend_if_missing(self, header, value):
        if self.has(header):
            return False
        if self.lowercase:
            header = header.lower()
        k = Word(header) if isinstance(header, str) else header
        v = Word(value) if isinstance(value, str) else value
        self.headers.insert(0, [k, v])
        return True

    def set(self, header, value):
        if self.lowercase:
            header = header.lower()
        k = Word(header) if isinstance(header, str) else header
        v = Word(value) if isinstance(value, str) else value

        search = k.to_lower_case().to_string()
        for pair in self.headers:
            if eq(pair[0].to_lower_case(), search):
                pair[1] = v
                return
        self.headers.append([k, v])

    def delete(self, header: str):
        lookup = header.lower()
        for i in range(len(self.headers) - 1, -1, -1):
            if self.headers[i][0].to_lower_case().to_string() == lookup:
                del self.headers[i]

    def clear_nulls(self):
        for i in range(len(self.headers) - 1, -1, -1):
            if self.headers[i][1] is None:
                del self.headers[i]

    def count(self, header: str) -> int:
        lookup = header.lower()
        return sum(
            1 for h in self.headers
            if h[0].to_lower_case().to_string() == lookup
        )

    def to_bool(self) -> bool:
        return bool(self.headers) and any(h[1] is not None for h in self.headers)


def parse_cookies(cookie_string: Word):
    """Cookie 是一种头。解析 'a=1; b=2' → [(name, value), ...] 或 None."""
    cookies = []
    for cookie in cookie_string.split(";"):
        cookie = cookie.replace(_LEADING_SPACE, "")
        parts = cookie.split("=", 2)
        if len(parts) < 2:
            return None
        cookies.append([parts[0], parts[1]])
    if len({c[0].to_string() for c in cookies}) != len(cookies):
        return None
    return cookies


import re
_LEADING_SPACE = re.compile(r"^ ")
