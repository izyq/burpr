# EncodingRecipe 实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 为 burpr 新增 EncodingRecipe 可逆编码转换管道，让 body 从字符串解码为 Python 原生对象，修改后发送时自动逆编码。

**架构：** 新增 `burpr/recipe.py`（EncodingRecipe + RecipeSteps），修改 `BurpRequest` 支持 `_recipe` 属性和 body property（双态），修改 `from_curl` 接受 recipe 参数，`to_request` 发送前自动编码。

**技术栈：** Python 3.7+, stdlib only（urllib.parse, base64, json, typing）, pytest

---

### 任务 1：创建 `burpr/recipe.py` — EncodingRecipe 类

**文件：**
- 创建：`burpr/recipe.py`

- [ ] **步骤 1：创建文件并实现 EncodingRecipe**

```python
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
```

- [ ] **步骤 2：立刻 commit**

```bash
git add burpr/recipe.py
git commit -m "feat: add EncodingRecipe class"
```

---

### 任务 2：添加 RecipeSteps 工厂方法

**文件：**
- 修改：`burpr/recipe.py`（追加内容）

- [ ] **步骤 1：在 EncodingRecipe 类之后追加 RecipeSteps**

```python
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
```

- [ ] **步骤 2：立刻 commit**

```bash
git add burpr/recipe.py
git commit -m "feat: add RecipeSteps factory methods"
```

---

### 任务 3：编写 EncodingRecipe + RecipeSteps 单元测试

**文件：**
- 创建：`tests/test_recipe.py`

- [ ] **步骤 1：编写失败测试（先建文件，还没实现导出路径）**

```python
"""EncodingRecipe 和 RecipeSteps 单元测试."""
import pytest
import json
import base64
from burpr.recipe import EncodingRecipe, RecipeSteps


class TestEncodingRecipe:
    """EncodingRecipe 核心逻辑测试."""

    def test_empty_recipe(self):
        """空步骤链，apply_decode / apply_encode 原样返回."""
        recipe = EncodingRecipe()
        assert recipe.apply_decode("hello") == "hello"
        assert recipe.apply_encode("hello") == "hello"

    def test_empty_recipe_with_dict(self):
        """空步骤链接受 dict 也原样返回."""
        recipe = EncodingRecipe()
        data = {"key": "value"}
        assert recipe.apply_decode(data) == data
        assert recipe.apply_encode(data) == data

    def test_add_step_returns_self(self):
        """add_step 返回 self 支持链式调用."""
        r1 = EncodingRecipe()
        r2 = r1.add_step(lambda s: s, lambda s: s)
        assert r1 is r2

    def test_decode_error_propagates(self):
        """非法 JSON 时异常直接传播，不做 fallback."""
        recipe = EncodingRecipe().add_step(*RecipeSteps.json_parse())
        with pytest.raises(json.JSONDecodeError):
            recipe.apply_decode("not valid json")

    def test_encode_error_propagates(self):
        """encode 端遇到不兼容的类型时异常直接传播."""
        recipe = EncodingRecipe().add_step(*RecipeSteps.json_parse())
        # json.dumps 对不可序列化对象会抛 TypeError
        with pytest.raises(TypeError):
            recipe.apply_encode(object())


class TestRecipeStepsRoundtrip:
    """每个步骤的 round-trip 测试：encode(decode(x)) == x."""

    def test_url_decode_roundtrip(self):
        """URL 解码 + 编码 round-trip."""
        original = "cjsj=2026-07-22 00:00:00&dataWrap={\"query\":{\"dqbm\":\"1218\"}}"
        encoded = "cjsj=2026-07-22+00%3A00%3A00&dataWrap=%7B%22query%22%3A%7B%22dqbm%22%3A%221218%22%7D%7D"
        recipe = EncodingRecipe().add_step(*RecipeSteps.url_decode())
        decoded = recipe.apply_decode(encoded)
        assert decoded == original
        assert recipe.apply_encode(decoded) == encoded

    def test_base64_decode_roundtrip(self):
        """Base64 解码 + 编码 round-trip."""
        original = "hello world"
        encoded = base64.b64encode(original.encode('utf-8')).decode('utf-8')
        recipe = EncodingRecipe().add_step(*RecipeSteps.base64_decode())
        decoded = recipe.apply_decode(encoded)
        assert decoded == original
        assert recipe.apply_encode(decoded) == encoded

    def test_json_parse_roundtrip(self):
        """JSON 解析 + 编码 round-trip."""
        original = {"dqbm": "1218", "year": "2026"}
        encoded = json.dumps(original, ensure_ascii=False)
        recipe = EncodingRecipe().add_step(*RecipeSteps.json_parse())
        decoded = recipe.apply_decode(encoded)
        assert decoded == original
        assert isinstance(decoded, dict)
        assert recipe.apply_encode(decoded) == encoded

    def test_json_parse_returns_dict(self):
        """json_parse 的 decode 返回 dict 而非 str."""
        recipe = EncodingRecipe().add_step(*RecipeSteps.json_parse())
        result = recipe.apply_decode('{"key": "value"}')
        assert isinstance(result, dict)
        assert result == {"key": "value"}

    def test_json_parse_returns_list(self):
        """json_parse 对数组返回 list."""
        recipe = EncodingRecipe().add_step(*RecipeSteps.json_parse())
        result = recipe.apply_decode('[1, 2, 3]')
        assert isinstance(result, list)
        assert result == [1, 2, 3]

    def test_form_urlencoded_roundtrip(self):
        """表单解析 + 编码 round-trip."""
        original = {"cjsj": "2026-07-22 00:00:00", "dqbm": "1218"}
        encoded = "cjsj=2026-07-22+00%3A00%3A00&dqbm=1218"
        recipe = EncodingRecipe().add_step(*RecipeSteps.form_urlencoded_parse())
        decoded = recipe.apply_decode(encoded)
        assert decoded == original
        assert isinstance(decoded, dict)
        assert recipe.apply_encode(decoded) == encoded

    def test_form_urlencoded_returns_dict(self):
        """form_urlencoded_parse 的 decode 返回 dict."""
        recipe = EncodingRecipe().add_step(*RecipeSteps.form_urlencoded_parse())
        result = recipe.apply_decode("key=value&foo=bar")
        assert isinstance(result, dict)
        assert result == {"key": "value", "foo": "bar"}


class TestChainedRecipe:
    """链式组合测试."""

    def test_url_decode_then_form_parse(self):
        """URL 解码 → 表单解析 → dict."""
        encoded = "cjsj=2026-07-22+00%3A00%3A00&dqbm=1218"
        recipe = EncodingRecipe() \
            .add_step(*RecipeSteps.url_decode()) \
            .add_step(*RecipeSteps.form_urlencoded_parse())
        decoded = recipe.apply_decode(encoded)
        assert isinstance(decoded, dict)
        assert decoded == {"cjsj": "2026-07-22 00:00:00", "dqbm": "1218"}

    def test_url_decode_form_parse_modify_encode(self):
        """完整流程：解码 → 修改 dict → 编码."""
        encoded = "cjsj=2026-07-22+00%3A00%3A00&dqbm=1218"
        recipe = EncodingRecipe() \
            .add_step(*RecipeSteps.url_decode()) \
            .add_step(*RecipeSteps.form_urlencoded_parse())
        decoded = recipe.apply_decode(encoded)
        decoded["dqbm"] = "%CITY_CODE%"
        result = recipe.apply_encode(decoded)
        assert "dqbm=%25CITY_CODE%25" in result

    def test_url_decode_then_json_parse(self):
        """URL 解码 → JSON 解析 → dict（对 URL 编码的 JSON body）."""
        import json
        payload = json.dumps({"dqbm": "1218"}, ensure_ascii=False)
        import urllib.parse
        encoded = "data=" + urllib.parse.quote_plus(payload)
        recipe = EncodingRecipe() \
            .add_step(*RecipeSteps.url_decode())
        decoded = recipe.apply_decode(encoded)
        assert decoded == "data=" + payload
```

- [ ] **步骤 2：运行测试验证通过**

```bash
python -m pytest tests/test_recipe.py -v
```
预期：所有测试 PASS

- [ ] **步骤 3：Commit**

```bash
git add tests/test_recipe.py
git commit -m "test: add EncodingRecipe and RecipeSteps unit tests"
```

---

### 任务 4：修改 BurpRequest — body 改为 property + _recipe 接入

**文件：**
- 修改：`burpr/models/BurpRequest.py`

- [ ] **步骤 1：将 body 从普通属性改为 property，_recipe 初始化为 None**

将 `__init__` 中的：
```python
self.body = body
```
改为：
```python
self._body = body
self._recipe = None
```

添加 property：
```python
@property
def body(self):
    """读取 body——解码后的对象或字符串."""
    return self._body

@body.setter
def body(self, value):
    """设置 body——接受 str、dict、list 等任意类型."""
    self._body = value
```

- [ ] **步骤 2：更新 set_body() 方法**

将 `set_body` 实现改为使用 property：
```python
def set_body(self, body):
    # Convert bytes to string using latin-1 if needed
    if isinstance(body, bytes):
        body = body.decode('latin-1')
    self.body = body
```

- [ ] **步骤 3：修改 to_request() — 发送前自动编码**

在 `to_request` 方法中，构造 `requests.Request` 之前，对 body 做 recipe 编码：

将：
```python
data=self.body.encode('latin-1') if self.body else None
```
改为：
```python
data=self._get_send_body().encode('latin-1') if self._get_send_body() else None
```

添加辅助方法：
```python
def _get_send_body(self):
    """获取发送时应使用的 body——若有 recipe 则自动逆编码."""
    if self._recipe:
        return self._recipe.apply_encode(self._body)
    return self._body
```

同时修改 `to_request` 中其他引用 `self.body` 的地方为 `self._get_send_body()`。

- [ ] **步骤 4：确认 make_request / make_httpx_request 无需修改**

`make_request` 和 `make_httpx_request` 都通过 `to_request` 构造请求，自动获得编码能力。但 `make_httpx_request` 直接使用 `self.body` 构造 content，需要改为 `self._get_send_body()`：

将：
```python
content=self.body.encode('latin-1') if self.body else None,
```
改为：
```python
content=self._get_send_body().encode('latin-1') if self._get_send_body() else None,
```

- [ ] **步骤 5：运行现有测试确认回归**

```bash
python -m pytest tests/test_burpr.py -v
```
预期：所有现有测试 PASS

- [ ] **步骤 6：Commit**

```bash
git add burpr/models/BurpRequest.py
git commit -m "feat: add _recipe support and body property to BurpRequest"
```

---

### 任务 5：修改 from_curl — 接受 recipe 参数

**文件：**
- 修改：`burpr/burpr.py`

- [ ] **步骤 1：在 from_curl 签名中增加 recipe 参数，解析 body 后应用解码**

在函数签名增加参数：
```python
def from_curl(curl_command: str, recipe: Optional[EncodingRecipe] = None) -> BurpRequest:
```

在文件顶部添加 import：
```python
from typing import Optional
```

在 body 提取完成后、创建 BurpRequest 之前，应用解码：
```python
if recipe and body:
    body = recipe.apply_decode(body)
```

创建 BurpRequest 之后，挂载 recipe：
```python
request = BurpRequest(
    host=protocol_host,
    path=path,
    protocol=ProtocolEnum.HTTP1_1,
    method=method,
    headers=headers,
    body=body,
    transport=transport
)
request._recipe = recipe
return request
```

注意：`BurpRequest.__init__` 中 `body=""` 是默认值，类型注解可能提示 str。实际传入时 body 已经是 `str | dict | list`，Python 是动态类型，不会报错。

- [ ] **步骤 2：运行现有 curl 测试确认回归**

```bash
python -m pytest tests/test_burpr.py -v -k "TestCurlParsing"
```
预期：所有 curl 测试 PASS（recipe=None 时行为完全不变）

- [ ] **步骤 3：Commit**

```bash
git add burpr/burpr.py
git commit -m "feat: add recipe parameter to from_curl"
```

---

### 任务 6：更新 __init__.py 导出

**文件：**
- 修改：`burpr/__init__.py`

- [ ] **步骤 1：添加 EncodingRecipe 和 RecipeSteps 导出**

```python
from .recipe import EncodingRecipe, RecipeSteps
```

更新 `__all__`：
```python
__all__ = [
    'parse_string',
    'parse_file',
    'clone',
    'prepare',
    'to_burp_format',
    'from_curl',
    'from_requests_response',
    'from_requests',
    'from_http2',
    'BurpRequest',
    'BurpParseError',
    'protocols',
    'transports',
    'EncodingRecipe',
    'RecipeSteps',
]
```

- [ ] **步骤 2：验证导入**

```bash
python -c "from burpr import EncodingRecipe, RecipeSteps; print('OK')"
```
预期：OK

- [ ] **步骤 3：运行全量测试确认无回归**

```bash
python -m pytest tests/ -v
```
预期：所有现有测试 PASS

- [ ] **步骤 4：Commit**

```bash
git add burpr/__init__.py
git commit -m "feat: export EncodingRecipe and RecipeSteps"
```

---

### 任务 7：编写 BurpRequest + Recipe 集成测试

**文件：**
- 修改：`tests/test_recipe.py`（追加内容）

- [ ] **步骤 1：追加 BurpRequest 集成测试类**

```python
class TestBurpRequestWithRecipe:
    """BurpRequest 与 Recipe 集成测试."""

    def test_from_curl_with_recipe_json_body_is_dict(self):
        """from_curl + json_parse → body 是 dict."""
        import burpr
        recipe = EncodingRecipe().add_step(*RecipeSteps.json_parse())
        curl = "curl -X POST https://api.com/query -H \"Content-Type: application/json\" -d '{\"dqbm\":\"1218\",\"year\":\"2026\"}'"
        req = burpr.from_curl(curl, recipe=recipe)
        assert isinstance(req.body, dict)
        assert req.body == {"dqbm": "1218", "year": "2026"}

    def test_from_curl_with_recipe_form_body_is_dict(self):
        """from_curl + form_urlencoded_parse → body 是 dict."""
        import burpr
        recipe = EncodingRecipe().add_step(*RecipeSteps.form_urlencoded_parse())
        curl = 'curl -X POST https://api.com/login -d "username=admin&password=secret"'
        req = burpr.from_curl(curl, recipe=recipe)
        assert isinstance(req.body, dict)
        assert req.body == {"username": "admin", "password": "secret"}

    def test_from_curl_without_recipe_body_is_str(self):
        """from_curl 不传 recipe → body 保持 str（回归）."""
        import burpr
        curl = 'curl -X POST https://api.com/login -d "username=%USER%&password=%PASS%"'
        req = burpr.from_curl(curl)
        assert isinstance(req.body, str)
        assert req.body == "username=%USER%&password=%PASS%"

    def test_to_request_encodes_body_with_recipe(self):
        """有 recipe 时 to_request 将 body 编码回 str."""
        import burpr
        from unittest.mock import MagicMock
        import sys

        recipe = EncodingRecipe().add_step(*RecipeSteps.json_parse())
        curl = 'curl -X POST https://api.com/query -H "Content-Type: application/json" -d \'{"dqbm":"1218"}\''
        req = burpr.from_curl(curl, recipe=recipe)

        # 修改 body dict
        req.body["dqbm"] = "4401"

        mock_requests = MagicMock()
        mock_request = MagicMock()
        mock_prepared = MagicMock()
        mock_request.prepare.return_value = mock_prepared
        mock_requests.Request.return_value = mock_request
        sys.modules['requests'] = mock_requests

        req.to_request()

        # 验证发出的 data 是编码后的 JSON 字符串
        call_kwargs = mock_requests.Request.call_args[1]
        assert call_kwargs["data"] == '{"dqbm": "4401"}'

    def test_to_request_no_recipe_unchanged(self):
        """无 recipe 时 to_request 行为不变."""
        import burpr
        from unittest.mock import MagicMock
        import sys

        curl = 'curl -X POST https://api.com/login -d "username=%USER%"'
        req = burpr.from_curl(curl)

        mock_requests = MagicMock()
        mock_request = MagicMock()
        mock_prepared = MagicMock()
        mock_request.prepare.return_value = mock_prepared
        mock_requests.Request.return_value = mock_request
        sys.modules['requests'] = mock_requests

        req.to_request()

        call_kwargs = mock_requests.Request.call_args[1]
        assert call_kwargs["data"] == b"username=%USER%"

    def test_bind_still_works_without_recipe(self):
        """bind 在无 recipe 时正常工作（回归）."""
        import burpr
        curl = 'curl -X POST https://api.com/login -d "username=%USER%&password=%PASS%"'
        req = burpr.from_curl(curl)
        req.bind("%USER%", "admin").bind("%PASS%", "secret")
        assert req.body == "username=admin&password=secret"


class TestE2ERecipe:
    """端到端测试."""

    def test_e2e_curl_form_parse_modify_to_request(self):
        """curl 导入 → 表单解析 → 修改 dict → to_request → 验证编码 body."""
        import burpr
        from unittest.mock import MagicMock
        import sys

        recipe = EncodingRecipe() \
            .add_step(*RecipeSteps.url_decode()) \
            .add_step(*RecipeSteps.form_urlencoded_parse())

        curl = '''curl -X POST https://api.com/data \
          -H "Content-Type: application/x-www-form-urlencoded" \
          --data-raw 'cjsj=2026-07-22+00%3A00%3A00&dataWrap=%7B%22query%22%3A%7B%22dqbm%22%3A%221218%22%7D%7D'
        '''
        req = burpr.from_curl(curl, recipe=recipe)

        # body 是 dict，精确修改
        assert isinstance(req.body, dict)
        req.body["cjsj"] = "2026-08-01 00:00:00"

        mock_requests = MagicMock()
        mock_request = MagicMock()
        mock_prepared = MagicMock()
        mock_request.prepare.return_value = mock_prepared
        mock_requests.Request.return_value = mock_request
        sys.modules['requests'] = mock_requests

        req.to_request()

        call_kwargs = mock_requests.Request.call_args[1]
        # 验证编码后的 data 包含修改后的值
        assert "2026-08-01" in call_kwargs["data"]
        # 验证 dataWrap 字段被正确编码回去
        assert "dataWrap=" in call_kwargs["data"]
```

- [ ] **步骤 2：运行集成测试**

```bash
python -m pytest tests/test_recipe.py::TestBurpRequestWithRecipe tests/test_recipe.py::TestE2ERecipe -v
```
预期：所有集成测试 PASS

- [ ] **步骤 3：全量回归测试**

```bash
python -m pytest tests/ -v
```
预期：所有测试 PASS，无回归

- [ ] **步骤 4：Commit**

```bash
git add tests/test_recipe.py
git commit -m "test: add BurpRequest + Recipe integration and E2E tests"
```

---

### 任务 8：在 from_curl 的文件顶部添加 Optional import

**文件：**
- 修改：`burpr/burpr.py`

- [ ] **步骤 1：确保 typing.Optional 已导入**

在 `burpr/burpr.py` 顶部已有 `import re`，确认 `from typing import Optional` 已添加（任务 5 中应已添加）。如果不是，现在添加。

- [ ] **步骤 2：最终全量回归**

```bash
python -m pytest tests/ -v
python -c "from burpr import EncodingRecipe, RecipeSteps, BurpRequest, from_curl; print('All imports OK')"
```
预期：全部通过

- [ ] **步骤 3：Commit（如有改动）**

```bash
git add burpr/burpr.py
git commit -m "fix: ensure Optional import in burpr.py"
```
