"""curl 命令解析——完整移植自 curlconverter 的解析管线.

公开 API 与 curlconverter 对齐:parse() 返回 Request(dict)列表,
get_first() 取第一个并汇总被忽略部分的警告。
"""

from burpr.curlconvert.errors import CCError
from burpr.curlconvert.word import Word, ShellToken
from burpr.curlconvert.parse import parse, clip
from burpr.curlconvert.request import get_first, build_requests
from burpr.curlconvert.opts import COMMON_SUPPORTED_ARGS

__all__ = [
    "parse",
    "get_first",
    "build_requests",
    "clip",
    "COMMON_SUPPORTED_ARGS",
    "Word",
    "ShellToken",
    "CCError",
]
