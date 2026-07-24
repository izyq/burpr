"""URL 解析——移植自 curlconverter 的 curl/url.ts(对应 curl 的 parseurl)."""

import re

from burpr.curlconvert.word import Word, eq
from burpr.curlconvert.warnings_ import warnf

# https://github.com/curl/curl/blob/curl-7_88_1/src/tool_urlglob.c#L327
_MAX_IP6LEN = 128


def _is_ipv6(glob: str) -> bool:
    if len(glob) > _MAX_IP6LEN:
        return False
    # TODO: curl 会尝试把 glob 解析为主机名
    return "-" not in glob


def _warn_about_globs(global_, url: str) -> None:
    """找出 URL 中的 glob 表达式并告警."""
    prev = ""
    i = 0
    while i < len(url):
        cur = url[i]
        if cur == "[" and prev != "\\":
            j = i + 1
            while j < len(url) and url[j] != "]":
                j += 1
            if j < len(url) and url[j] == "]":
                glob = url[i:j + 1]
                # 可能是 ipv6 地址
                if not _is_ipv6(glob):
                    warnf(global_, [
                        "glob-in-url",
                        "globs in the URL are not supported:\n"
                        + url + "\n" + " " * i + "^" * len(glob),
                    ])
                prev = ""
            else:
                warnf(global_, [
                    "unbalanced-glob",
                    "bracket doesn't have a closing bracket:\n"
                    + url + "\n" + " " * i + "^",
                ])
                return
        elif cur == "{" and prev != "\\":
            j = i + 1
            while j < len(url) and url[j] != "}":
                j += 1
            if j < len(url) and url[j] == "}":
                glob = url[i:j + 1]
                warnf(global_, [
                    "glob-in-url",
                    "globs in the URL are not supported:\n"
                    + url + "\n" + " " * i + "^" * len(glob),
                ])
                prev = ""
            else:
                warnf(global_, [
                    "unbalanced-glob",
                    "bracket doesn't have a closing bracket:\n"
                    + url + "\n" + " " * i + "^",
                ])
                return
        prev = cur
        i += 1


def parseurl(global_, config, url: Word) -> dict:
    """对应 curl 的 parseurl(),但接受所有 URL(进一步校验在 curl_url_get)."""
    u = {
        "scheme": Word(),
        "host": Word(),
        "port": Word(),
        "path": Word(),  # 带前导 '/'
        "query": Word(),  # 带前导 '?'
        "fragment": Word(),  # 带前导 '#'
    }

    # 去掉 url glob 转义
    if not config.get("globoff"):
        if url.is_string():
            _warn_about_globs(global_, url.to_string())
        url = url.replace(_GLOB_ESCAPES, r"\1")

    # scheme 缺失时补 "http"/"https"
    scheme_match = None
    if url.tokens and isinstance(url.tokens[0], str):
        scheme_match = _SCHEME_RE.match(url.tokens[0])
    if scheme_match:
        scheme_and_slashes = scheme_match.group(0)
        scheme = scheme_match.group(1)
        u["scheme"] = Word(scheme.lower())
        url = url.slice(len(scheme_and_slashes))
    else:
        # curl 默认 https://;我们不,因为多数库不会像 curl 那样从 https 降级到 http
        u["scheme"] = config.get("proto-default", Word("http"))
    if not eq(u["scheme"], "http") and not eq(u["scheme"], "https"):
        warnf(global_, ["bad-scheme", f'Protocol "{u["scheme"]}" not supported'])

    host_match = url.index_of_first_char("/?#")
    if host_match != -1:
        u["host"] = url.slice(0, host_match)
        u["path"] = url.slice(host_match)  # path 保留前导 '/'
        fragment_index = u["path"].index_of("#")
        query_index = u["path"].index_of("?")
        if fragment_index != -1:
            u["fragment"] = u["path"].slice(fragment_index)
            if query_index != -1 and query_index < fragment_index:
                u["query"] = u["path"].slice(query_index, fragment_index)
                u["path"] = u["path"].slice(0, query_index)
            else:
                u["path"] = u["path"].slice(0, fragment_index)
        elif query_index != -1:
            u["query"] = u["path"].slice(query_index)
            u["path"] = u["path"].slice(0, query_index)
    else:
        u["host"] = url

    # 解析 username:password@hostname
    auth_match = u["host"].index_of("@")
    if auth_match != -1:
        auth = u["host"].slice(0, auth_match)
        u["host"] = u["host"].slice(auth_match + 1)  # 丢弃 '@'
        if not config.get("disallow-username-in-url"):
            u["auth"] = auth
            if auth.includes(":"):
                u["user"], u["password"] = auth.split(":", 2)
            else:
                u["user"] = auth
                u["password"] = Word()  # 没有 ':' 时 curl 会补一个
        else:
            # curl 此时会退出,我们只是从 URL 移除
            warnf(global_, [
                "login-denied",
                "Found auth in URL but --disallow-username-in-url was passed: "
                + auth.to_string(),
            ])

    return u


_GLOB_ESCAPES = re.compile(r"\\([\[\]{}])")
_SCHEME_RE = re.compile(r"^([a-zA-Z0-9+-.]*):\/\/*")
