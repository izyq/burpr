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
