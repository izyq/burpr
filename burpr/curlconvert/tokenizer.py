"""把 curl 命令的 Bash 源码 tokenize 成 Word——移植自 shell/tokenizer.ts.

用 tree-sitter-bash 把整条命令解析成 AST,再按节点类型提取 Word。
"""

import re

import tree_sitter_bash
from tree_sitter import Language, Parser

from burpr.curlconvert.errors import CCError
from burpr.curlconvert.warnings_ import (
    warnf,
    underline_node,
    underline_cursor,
    _set_source,
)
from burpr.curlconvert.word import (
    Word,
    ShellToken,
    eq,
    first_shell_token,
)

_parser = Parser(Language(tree_sitter_bash.language()))


def _text(node) -> str:
    return node.text.decode("utf-8")


def clip(s: str, max_length: int = 30) -> str:
    if len(s) > max_length:
        return s[: max_length - 3] + "..."
    return s


_BACKSLASHES = re.compile(r"\\.", re.DOTALL)


def _remove_backslash(m) -> str:
    return "" if m.group(0)[1] == "\n" else m.group(0)[1]


def remove_backslashes(s: str) -> str:
    return _BACKSLASHES.sub(_remove_backslash, s)


# https://www.gnu.org/software/bash/manual/bash.html#Double-Quotes
_DOUBLE_QUOTE_BACKSLASHES = re.compile(r"\\[\\$`\"\n]", re.DOTALL)


def remove_double_quote_backslashes(s: str) -> str:
    return _DOUBLE_QUOTE_BACKSLASHES.sub(_remove_backslash, s)


# ANSI-C 引号形如 $'like this'
# https://git.savannah.gnu.org/cgit/bash.git/tree/lib/sh/strtrans.c
_ANSI_BACKSLASHES = re.compile(
    r"\\(\\|a|b|e|E|f|n|r|t|v|'|\"|\?|[0-7]{1,3}|x[0-9A-Fa-f]{1,2}"
    r"|u[0-9A-Fa-f]{1,4}|U[0-9A-Fa-f]{1,8}|c.)",
    re.DOTALL,
)


def remove_ansi_c_backslashes(s: str) -> str:
    def unescape_char(m) -> str:
        g = m.group(0)
        c = g[1]
        if c == "\\":
            return "\\"
        if c == "a":
            return "\x07"
        if c == "b":
            return "\b"
        if c in ("e", "E"):
            return "\x1B"
        if c == "f":
            return "\f"
        if c == "n":
            return "\n"
        if c == "r":
            return "\r"
        if c == "t":
            return "\t"
        if c == "v":
            return "\v"
        if c == "'":
            return "'"
        if c == '"':
            return '"'
        if c == "?":
            return "?"
        if c == "c":
            if ord(g[2]) > 127:
                raise CCError(
                    'non-ASCII control character in ANSI-C quoted string: "\\u{'
                    + format(ord(g[2]), "x")
                    + '}"'
                )
            return "\x7F" if g[2] == "?" else chr(ord(g[2].upper()) & 0b00011111)
        if c in ("x", "u", "U"):
            # 十六进制字符字面量
            return chr(int(g[2:], 16))
        if c in "01234567":
            # 八进制字符字面量
            return chr(int(g[1:], 8) % 256)
        raise CCError("unhandled character in ANSI-C escape code: " + repr(g))

    return _ANSI_BACKSLASHES.sub(unescape_char, s)


def to_tokens(node, curl_command: str, warnings: list) -> list:
    """把单个参数 AST 节点转成 Token 列表(str 或 ShellToken)."""
    t = node.type
    if t == "$":
        # TODO: https://github.com/tree-sitter/tree-sitter-bash/issues/258
        return ["$"]
    if t in ("word", "number"):
        # TODO: number 可能含 ${variable}
        return [remove_backslashes(_text(node))]
    if t == "raw_string":
        return [_text(node)[1:-1]]
    if t == "ansi_c_string":
        return [remove_ansi_c_backslashes(_text(node)[2:-1])]
    if t in ("string", "translated_string"):
        # TODO: MISSING quotes,例如 curl "example.com
        vals = []
        res = ""
        for child in node.named_children:
            if child.type == "string_content":
                res += remove_double_quote_backslashes(_text(child))
            else:
                # expansion / simple_expansion / command_substitution(或 concat)
                sub_val = to_tokens(child, curl_command, warnings)
                if isinstance(sub_val, str):
                    res += sub_val
                else:
                    if res:
                        vals.append(res)
                        res = ""
                    vals.extend(sub_val)
        if res or not vals:
            vals.append(res)
        return vals
    if t == "simple_expansion":
        # '$' + variable_name 或 special_variable_name
        warnf_globals = warnings
        warnf_globals.append([
            "expansion",
            "found environment variable\n" + underline_node(node, curl_command),
        ])
        first = node.named_children[0] if node.named_children else None
        if first is not None and first.type == "special_variable_name":
            warnings.append([
                "special_variable_name",
                _text(node)
                + " is a special Bash variable\n"
                + underline_node(first, curl_command),
            ])
        txt = _text(node)
        return [ShellToken("variable", txt[1:], txt, node)]
    if t == "expansion":
        # ${like_this}
        warnings.append([
            "expansion",
            "found expansion expression\n" + underline_node(node, curl_command),
        ])
        txt = _text(node)
        return [ShellToken("variable", txt[2:-1], txt, node)]
    if t == "command_substitution":
        warnings.append([
            "expansion",
            "found command substitution expression\n"
            + underline_node(node, curl_command),
        ])
        txt = _text(node)
        return [
            ShellToken(
                "command", txt[2:-1] if txt.startswith("$(") else txt[1:-1], txt, node
            )
        ]
    if t == "concatenation":
        # item[]=1 若不处理会变成 item=1
        vals = []
        prev_end = 0
        res = ""
        for child in node.children:
            res += _text(node)[prev_end: child.start_byte - node.start_byte]
            prev_end = child.end_byte - node.start_byte

            sub_val = to_tokens(child, curl_command, warnings)
            if isinstance(sub_val, str):
                res += sub_val
            else:
                if res:
                    vals.append(res)
                    res = ""
                vals.extend(sub_val)
        res += _text(node)[prev_end:]
        if res or not vals:
            vals.append(res)
        return vals
    raise CCError(
        "unexpected syntax node type "
        + repr(t)
        + '. Must be one of "word", "number", "string", "raw_string", '
        '"ansi_c_string", "expansion", "simple_expansion", "translated_string", '
        '"command_substitution" or "concatenation"\n'
        + underline_node(node, curl_command)
    )


def to_word(node, curl_command: str, warnings: list) -> Word:
    return Word(to_tokens(node, curl_command, warnings))


def _traverse_looking_for_bad_nodes(tree):
    cursor = tree.walk()
    reached_root = False
    while not reached_root:
        if cursor.node.type == "ERROR" or cursor.node.is_missing:
            yield cursor

        if cursor.goto_first_child():
            continue
        if cursor.goto_next_sibling():
            continue

        retracing = True
        while retracing:
            if not cursor.goto_parent():
                retracing = False
                reached_root = True
            if cursor.goto_next_sibling():
                retracing = False


def warn_about_bad_nodes(ast, curl_command: str, warnings: list) -> None:
    max_shown = 3
    count = 0
    for bad_node in _traverse_looking_for_bad_nodes(ast):
        if count < max_shown:
            underlined = ""
            try:
                underlined = ":\n" + underline_cursor(bad_node.node, curl_command)
            except Exception:
                pass
            line = bad_node.node.start_point[0]
            column = bad_node.node.start_point[1]
            warnings.append([
                "bash",
                f"Bash parsing error on line {line + 1}"
                + (f", column {column + 1}" if column != 0 else "")
                + underlined,
            ])
        count += 1
    extra = count - max_shown
    if extra > 0:
        warnings.append([
            "bash",
            f"{extra} more Bash parsing error{'s' if extra > 1 else ''} omitted",
        ])


def warn_about_useless_backslash(n, curl_command_lines: list, warnings: list) -> None:
    last_command_line = curl_command_lines[n.end_point[0]]
    improper = re.search(r"\\\s+$", last_command_line)
    if improper and len(curl_command_lines) > n.end_point[0] + 1:
        warnings.append([
            "unescaped-newline",
            "The trailling '\\' on line "
            + str(n.end_point[0] + 1)
            + " is followed by whitespace, so it won't escape the newline after it:\n"
            + last_command_line
            + "\n"
            + " " * improper.start()
            + "^" * len(improper.group(0)),
        ])


def extract_redirect(node, curl_command: str, warnings: list):
    """redirected_statement → (command节点, stdin Word|None, stdinFile Word|None)."""
    if not node.named_child_count:
        raise CCError('got empty "redirected_statement" AST node')

    stdin = None
    stdin_file = None
    command = node.named_children[0]
    redirects = list(node.named_children[1:])
    if command.type != "command":
        raise CCError(
            'got "redirected_statement" AST node whose first child is not a '
            '"command", got ' + command.type + " instead\n"
            + underline_node(command, curl_command)
        )
    if node.child_count < 2:
        raise CCError(
            'got "redirected_statement" AST node with only one child - no redirect'
        )
    if len(redirects) > 1:
        warnings.append([
            "multiple-redirects",
            "found "
            + str(len(redirects))
            + " redirect nodes. Only the first one will be used:\n"
            + underline_node(redirects[1], curl_command),
        ])
    redirect = redirects[0]
    if redirect.type == "file_redirect":
        destination = redirect.child_by_field_name("destination")
        if destination is None:
            raise CCError('got "file_redirect" AST node with no "destination" child')
        stdin_file = to_word(destination, curl_command, warnings)
    elif redirect.type == "heredoc_redirect":
        bodies = _descendants_of_type(redirect, "heredoc_body")
        if not bodies:
            raise CCError('got "redirected_statement" AST node without heredoc_body')
        # TODO: heredoc 可以做变量展开等
        stdin = Word(_text(bodies[0]))
    elif redirect.type == "herestring_redirect":
        if redirect.named_child_count < 1 or not redirect.named_children:
            raise CCError('got "redirected_statement" AST node with empty herestring')
        stdin = to_word(redirect.named_children[0], curl_command, warnings)
    else:
        raise CCError(
            'got "redirected_statement" AST node whose second child is not one of '
            '"file_redirect", "heredoc_redirect" or "herestring_redirect", got '
            + command.type + " instead"
        )
    return command, stdin, stdin_file


def _descendants_of_type(node, type_: str) -> list:
    out = []

    def rec(x):
        if x.type == type_:
            out.append(x)
        for c in x.children:
            rec(c)

    rec(node)
    return out


def _find_curl_in_pipeline(node, curl_command: str, warnings: list):
    command = None
    stdin = None
    stdin_file = None
    for child in node.named_children:
        if child.type == "command":
            command_name = child.named_children[0]
            if command_name.type != "command_name":
                raise CCError(
                    'got "command" AST node whose first child is not a '
                    '"command_name", got ' + command_name.type + " instead\n"
                    + underline_node(command_name, curl_command)
                )
            command_name_word = (
                command_name.named_children[0] if command_name.named_children else None
            )
            if command_name_word is None or command_name_word.type != "word":
                raise CCError(
                    'got "command_name" AST node whose first child is not a "word", '
                    "got "
                    + (command_name_word.type if command_name_word else "none")
                    + " instead\n"
                    + underline_node(command_name_word or command_name, curl_command)
                )
            if _text(command_name_word) == "curl":
                if command is None:
                    command = child
                else:
                    warnings.append([
                        "multiple-curl-in-pipeline",
                        "found multiple curl commands in pipeline:\n"
                        + underline_node(child, curl_command),
                    ])
        elif child.type == "redirected_statement":
            redir_command, redir_stdin, redir_stdin_file = extract_redirect(
                child, curl_command, warnings
            )
            if _text(redir_command.named_children[0]) == "curl":
                if command is None:
                    command, stdin, stdin_file = (
                        redir_command,
                        redir_stdin,
                        redir_stdin_file,
                    )
                else:
                    warnings.append([
                        "multiple-curl-in-pipeline",
                        "found multiple curl commands in pipeline:\n"
                        + underline_node(redir_command, curl_command),
                    ])
        elif child.type == "pipeline":
            # 管道可以嵌套
            nested = _find_curl_in_pipeline(child, curl_command, warnings)
            if nested[0] is None:
                continue
            nested_command, nested_stdin, nested_stdin_file = nested
            if _text(nested_command.named_children[0]) == "curl":
                if command is None:
                    command, stdin, stdin_file = (
                        nested_command,
                        nested_stdin,
                        nested_stdin_file,
                    )
                else:
                    warnings.append([
                        "multiple-curl-in-pipeline",
                        "found multiple curl commands in pipeline:\n"
                        + underline_node(nested_command, curl_command),
                    ])
    return command, stdin, stdin_file


def find_curl_in_pipeline(node, curl_command: str, warnings: list):
    command, stdin, stdin_file = _find_curl_in_pipeline(
        node, curl_command, warnings
    )
    if command is None:
        raise CCError(
            "could not find curl command in pipeline\n"
            + underline_node(node, curl_command)
        )
    return command, stdin, stdin_file


def extract_command_nodes(ast, curl_command: str, warnings: list) -> list:
    """取顶层 command/redirected_statement/pipeline 节点,跳过注释."""
    if ast.root_node.type != "program":
        raise CCError(
            'expected a "program" top-level AST node, got '
            + ast.root_node.type
            + " instead"
        )
    if ast.root_node.named_child_count < 1 or not ast.root_node.named_children:
        raise CCError('empty "program" node')

    curl_command_lines = curl_command.split("\n")
    saw_comment = False
    commands = []
    for n in ast.root_node.named_children:
        if n.type == "comment":
            saw_comment = True
            continue
        if n.type == "command":
            commands.append((n, None, None))
            warn_about_useless_backslash(n, curl_command_lines, warnings)
        elif n.type == "redirected_statement":
            commands.append(extract_redirect(n, curl_command, warnings))
            warn_about_useless_backslash(n, curl_command_lines, warnings)
        elif n.type == "pipeline":
            commands.append(find_curl_in_pipeline(n, curl_command, warnings))
            warn_about_useless_backslash(n, curl_command_lines, warnings)
        elif n.type == "heredoc_body":
            continue
        elif n.type == "ERROR":
            raise CCError(
                f"Bash parsing error on line {n.start_point[0] + 1}:\n"
                + underline_node(n, curl_command)
            )
        else:
            raise CCError(
                "found "
                + repr(n.type)
                + ' AST node, only "command", "pipeline" or '
                '"redirected_statement" are supported\n'
                + underline_node(n, curl_command)
            )
    if not commands:
        raise CCError(
            'expected a "command" or "redirected_statement" AST node'
            + (', only found "comment" nodes' if saw_comment else "")
        )
    return commands


def to_name_and_argv(command, curl_command: str, warnings: list):
    if command.child_count < 1:
        raise CCError('empty "command" node\n' + underline_node(command, curl_command))

    name = command.child_by_field_name("name")
    args = command.children_by_field_name("argument")

    if name is None:
        raise CCError(
            'found "command" AST node with no "command_name" child\n'
            + underline_node(command, curl_command)
        )
    return name, args


def name_to_word(name, curl_command: str, warnings: list) -> Word:
    """检查命令名是否为 "curl"."""
    if name.child_count < 1 or name.children[0] is None:
        raise CCError(
            'found empty "command_name" AST node\n'
            + underline_node(name, curl_command)
        )
    elif name.child_count > 1:
        warnings.append([
            "extra-command_name-children",
            'expected "command_name" node to only have one child but it has '
            + str(name.child_count),
        ])

    name_node = name.children[0]
    name_word = to_word(name_node, curl_command, warnings)
    name_word_str = name_word.to_string()
    cmd_shell_token = first_shell_token(name_word)
    if cmd_shell_token:
        # 命令名含表达式,最常见原因是复制了 shell 提示符里的 $
        if name_word_str != "$curl":
            raise CCError(
                "expected command name to be a simple value but found a "
                + cmd_shell_token.type
                + "\n"
                + underline_node(cmd_shell_token.syntax_node, curl_command)
            )
    elif name_word_str.strip() != "curl":
        c = name_word_str.strip()
        if not c:
            raise CCError(
                "found command without a command_name\n"
                + underline_node(name_node, curl_command)
            )
        raise CCError(
            'command should begin with "curl" but instead begins with '
            + repr(clip(c))
            + "\n"
            + underline_node(name_node, curl_command)
        )
    return name_word


def tokenize(curl_command: str, warnings: list = None) -> list:
    """解析含 curl 命令的 Bash 源码,返回 [(argv Word列表, stdin, stdinFile), ...]."""
    if warnings is None:
        warnings = []
    _set_source(curl_command)
    ast = _parser.parse(curl_command.encode("utf-8"))
    warn_about_bad_nodes(ast, curl_command, warnings)

    command_nodes = extract_command_nodes(ast, curl_command, warnings)
    commands = []
    for command, stdin, stdin_file in command_nodes:
        name, argv = to_name_and_argv(command, curl_command, warnings)
        commands.append((
            [name_to_word(name, curl_command, warnings)]
            + [to_word(arg, curl_command, warnings) for arg in argv],
            stdin,
            stdin_file,
        ))
    return commands
