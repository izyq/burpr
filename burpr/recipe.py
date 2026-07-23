"""可逆编码转换管道 — 类似 CyberChef 的 recipe 模式."""
from typing import Callable, List, Tuple, Any


class EncodingRecipe:
    """可逆的编码转换管道。

    内部维护有序的 (decode_func, encode_func) 步骤对。
    解码按顺序执行，编码按逆序执行。

    Usage:
        recipe = EncodingRecipe() \
            .add_step(*RecipeSteps.url_decode()) \
            .add_step(*RecipeSteps.json_parse())
        obj = recipe.apply_decode(raw_body)
        obj['key'] = 'new_value'
        encoded = recipe.apply_encode(obj)
    """

    def __init__(self):
        self.steps: List[Tuple[Callable, Callable]] = []

    def add_step(self, decode_func: Callable, encode_func: Callable) -> 'EncodingRecipe':
        """追加一个可逆转换步骤，返回 self 支持链式调用。

        Args:
            decode_func: 解码函数
            encode_func: 编码函数（decode 的逆操作）

        Returns:
            self，支持链式调用
        """
        self.steps.append((decode_func, encode_func))
        return self

    def apply_decode(self, data: str) -> Any:
        """按顺序执行所有解码步骤。

        Args:
            data: 原始编码字符串

        Returns:
            解码后的数据，可以是 str、dict、list 或任意类型

        Raises:
            任一步骤失败时原始异常直接传播
        """
        for decode_func, _ in self.steps:
            data = decode_func(data)
        return data

    def apply_encode(self, data: Any) -> str:
        """按逆序执行所有编码步骤（反向操作）。

        Args:
            data: 解码后的数据（任意类型）

        Returns:
            编码后的字符串

        Raises:
            任一步骤失败时原始异常直接传播
        """
        for _, encode_func in reversed(self.steps):
            data = encode_func(data)
        return data

    def verify(self, data: str) -> dict:
        """解码后不修改直接编码回去，对比 round-trip 是否一致。

        Args:
            data: 原始编码字符串

        Returns:
            {'equal': bool, 'original': str, 'decoded': Any, 're_encoded': str}
        用法：

        recipe = EncodingRecipe().add_step(*RecipeSteps.form_urlencoded_parse())
        result = recipe.verify(body)
        print(result['equal'])       # True/False
        print(result['original'])    # 原始编码
        print(result['decoded'])     # 解码后的 Python 对象
        print(result['re_encoded'])  # 重新编码的字符串
        """
        decoded = self.apply_decode(data)
        re_encoded = self.apply_encode(decoded)
        return {
            'equal': data == re_encoded,
            'original': data,
            'decoded': decoded,
            're_encoded': re_encoded,
        }


class RecipeSteps:
    """预定义的可逆转换步骤工厂方法。

    每个静态方法返回 (decode_func, encode_func) 元组。
    前两个步骤（url_decode, base64_decode）是 str → str，
    后两个步骤（json_parse, form_urlencoded_parse）跨越字符串/对象边界。
    """

    @staticmethod
    def url_decode(encoding='utf-8'):
        """URL 解码步骤：str → str.

        decode: urllib.parse.unquote_plus
        encode: urllib.parse.quote_plus
        """
        import urllib.parse
        return (
            lambda s: urllib.parse.unquote_plus(s, encoding=encoding),
            lambda s: urllib.parse.quote_plus(s, encoding=encoding)
        )

    @staticmethod
    def base64_decode():
        """Base64 解码步骤：str → str.

        decode: base64.b64decode → utf-8 str
        encode: utf-8 bytes → base64.b64encode → str
        """
        import base64
        return (
            lambda s: base64.b64decode(s).decode('utf-8'),
            lambda s: base64.b64encode(s.encode('utf-8')).decode('utf-8')
        )

    @staticmethod
    def json_parse():
        """JSON 解析步骤：str → dict/list（Python 原生对象）。

        decode: json.loads → Python 对象
        encode: json.dumps（ensure_ascii=False）→ str

        这是最关键的一步——decode 返回真正的 Python 对象，
        修改 body 从字符串替换升维到精确的对象操作。
        """
        import json
        return (
            lambda s: json.loads(s),
            lambda obj: json.dumps(obj, ensure_ascii=False)
        )

    @staticmethod
    def form_urlencoded_parse():
        """表单数据解析步骤：str → dict.

        decode: parse_qsl → dict
        encode: urllib.parse.urlencode → str

        将 key1=val1&key2=val2 解析为 {'key1': 'val1', 'key2': 'val2'}。
        """
        import urllib.parse
        return (
            lambda s: dict(urllib.parse.parse_qsl(s, keep_blank_values=True)),
            lambda d: urllib.parse.urlencode(d)
        )
