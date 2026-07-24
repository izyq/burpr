"""入口——移植自 curlconverter 的 parse.ts."""

from burpr.curlconvert.errors import CCError
from burpr.curlconvert.word import Word
from burpr.curlconvert.tokenizer import tokenize, clip
from burpr.curlconvert.opts import (
    parse_args,
    curlLongOpts,
    curlLongOptsShortened,
    curlShortOpts,
)
from burpr.curlconvert.request import build_requests

__all__ = ["parse", "clip"]


def _find_commands(curl_command, warnings):
    if isinstance(curl_command, str):
        return tokenize(curl_command, warnings)

    if len(curl_command) == 0:
        raise CCError("no arguments provided")
    if curl_command[0].strip() != "curl":
        raise CCError(
            'command should begin with "curl" but instead begins with '
            + repr(clip(curl_command[0]))
        )
    return [([Word(arg) for arg in curl_command], None, None)]


def parse(command, supported_args=None, warnings=None):
    """接受一段 Bash 代码或已 tokenize 的 argv 数组,返回解析出的 Request 列表.

    command: 含至少一条 curl 命令的 Bash 字符串,或 shell 参数 token 数组。
    """
    if warnings is None:
        warnings = []
    requests = []
    curl_commands = _find_commands(command, warnings)
    for argv, stdin, stdin_file in curl_commands:
        global_, _ = parse_args(
            argv,
            curlLongOpts,
            curlLongOptsShortened,
            curlShortOpts,
            supported_args,
            warnings,
        )
        requests = requests + build_requests(global_, stdin, stdin_file)
    return requests
