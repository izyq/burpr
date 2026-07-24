"""警告工具——移植自 curlconverter 的 Warnings.ts.

tree-sitter 的 Python 绑定中节点没有 `.tree` 引用,无法像 JS 那样从任意节点
回到根节点取源码。这里用一个模块级的"当前解析源"引用(tokenize 时设置),
供 underlineNode 在未显式传入源码时兜底。仅影响报错/警告文本。
"""

# Warnings 是 [类型, 消息] 二元组列表
Warnings = list

# 当前正在解析的源码(tokenize 时设置)
_current_source: str = ""


def _set_source(src: str) -> None:
    global _current_source
    _current_source = src


def warnf(global_: dict, warning) -> None:
    global_["warnings"].append(warning)


def _node_span(node):
    """取节点的 (start_byte, end_byte)。兼容 tree-sitter 节点与游标."""
    return node.start_byte, node.end_byte


def _underline(start_index: int, end_index: int, curl_command: str) -> str:
    if start_index == end_index:
        end_index += 1

    line_start = start_index
    if start_index > 0:
        # 若是 -1 说明在第一行
        line_start = curl_command.rfind("\n", 0, start_index) + 1

    underline_length = end_index - start_index
    line_end = curl_command.find("\n", start_index)
    if line_end == -1:
        line_end = len(curl_command)
    elif line_end < end_index:
        # 节点跨行,行尾多补一个 ^ 表示延续
        underline_length = line_end - start_index + 1

    line = curl_command[line_start:line_end]
    underline = " " * (start_index - line_start) + "^" * underline_length
    return line + "\n" + underline


def underline_cursor(node, curl_command: str) -> str:
    start, end = _node_span(node)
    return _underline(start, end, curl_command)


def underline_node(node, curl_command: str = None) -> str:
    # 不含前导空白
    if curl_command is None:
        curl_command = _current_source
    start, end = _node_span(node)
    return _underline(start, end, curl_command)


def underline_node_end(node, curl_command: str = None) -> str:
    if curl_command is None:
        curl_command = _current_source
    start_index, end_index = _node_span(node)
    if start_index == end_index:
        end_index += 1

    line_start = start_index
    if start_index > 0:
        line_start = curl_command.rfind("\n", 0, end_index) + 1

    underline_start = max(start_index, line_start)
    underline_length = end_index - underline_start
    line_end = curl_command.find("\n", end_index)
    if line_end == -1:
        line_end = len(curl_command)

    line = curl_command[line_start:line_end]
    underline = " " * (underline_start - line_start) + "^" * underline_length
    return line + "\n" + underline


def warn_if_parts_ignored(request, warnings: Warnings, support: dict = None) -> None:
    support = support or {}
    if len(request["urls"]) > 1 and not support.get("multipleUrls"):
        warnings.append([
            "multiple-urls",
            "found "
            + str(len(request["urls"]))
            + " URLs, only the first one will be used: "
            + ", ".join(repr(u["originalUrl"].to_string()) for u in request["urls"]),
        ])
    if request.get("dataReadsFile") and not support.get("dataReadsFile"):
        warnings.append([
            "unsafe-data",
            "the generated data content is wrong, "
            + repr("@" + request["dataReadsFile"])
            + " means read the file "
            + repr(request["dataReadsFile"]),
        ])
    if request["urls"][0].get("queryReadsFile") and not support.get("queryReadsFile"):
        warnings.append([
            "unsafe-query",
            "the generated URL query string is wrong, "
            + repr("@" + request["urls"][0]["queryReadsFile"])
            + " means read the file "
            + repr(request["urls"][0]["queryReadsFile"]),
        ])
    if request.get("cookieFiles") and not support.get("cookieFiles"):
        warnings.append([
            "cookie-files",
            "passing a file for --cookie/-b is not supported: "
            + ", ".join(repr(c.to_string()) for c in request["cookieFiles"]),
        ])
