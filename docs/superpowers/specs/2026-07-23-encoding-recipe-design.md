# EncodingRecipe 设计规格

日期：2026-07-23
状态：已确认

---

## 一、目标

为 burpr 新增 `EncodingRecipe` 模块，实现可逆的编码转换管道。将请求 body 从纯字符串解码为 Python 原生对象，用户修改对象后，发送时自动逆编码回原始格式。

核心价值：body 修改从"字符串拼接/替换"升维到"对象精确操作"。

---

## 二、新增文件

### 2.1 `burpr/recipe.py`

#### `EncodingRecipe` 类

维护有序的 `(decode_func, encode_func)` 步骤对，支持链式添加和正逆执行。

```
属性：
  steps: List[Tuple[Callable, Callable]]  — (decode, encode) 对

方法：
  add_step(decode_func: Callable, encode_func: Callable) -> Self
      追加一个步骤，返回 self 支持链式调用
  
  apply_decode(data: str) -> Any
      按顺序执行所有 decode 函数，最终返回类型可以是 str/dict/list/任意
  
  apply_encode(data: Any) -> str
      按逆序执行所有 encode 函数，返回编码后的原始格式字符串
```

#### `RecipeSteps` 类（纯静态工厂方法）

| 方法 | decode | encode | 返回 |
|:-----|:-------|:-------|:-----|
| `url_decode(encoding='utf-8')` | `urllib.parse.unquote_plus` | `urllib.parse.quote_plus` | `str → str` |
| `base64_decode()` | `base64.b64decode` + `.decode('utf-8')` | `base64.b64encode` + `.decode('utf-8')` | `str → str` |
| `json_parse()` | `json.loads` | `json.dumps(ensure_ascii=False)` | `str → dict/list` |
| `form_urlencoded_parse()` | `parse_qsl` → dict | `urllib.parse.urlencode` | `str → dict` |

关键区分：`json_parse` 和 `form_urlencoded_parse` 跨越了字符串/对象边界——decode 端返回 Python 对象，encode 端接受 Python 对象。

#### 错误处理

不吞异常。任何步骤失败时原始异常直接传播（`json.JSONDecodeError`、`binascii.Error` 等）。不做 fallback 或降级。

---

## 三、修改现有文件

### 3.1 `burpr/models/BurpRequest.py`

#### body 改为 property（双态）

```
class BurpRequest:
    def __init__(self, ..., body=""):
        self._body: Any = body          # str | dict | list | 任意
        self._recipe: Optional[EncodingRecipe] = None
    
    @property
    def body(self) -> Any:
        return self._body
    
    @body.setter
    def body(self, value: Any):
        self._body = value
```

`set_body()` 方法保持兼容（调用 `self.body = body`）。

#### to_request() — 发送前自动编码

在构造 `requests.Request` 前，若有 `_recipe`，调用 `apply_encode(self._body)` 将对象还原为 str：

```python
def to_request(self, session=None, auto_prepare=True):
    body = self._body
    if self._recipe:
        body = self._recipe.apply_encode(self._body)
    # 原有逻辑：body.encode('latin-1') ...
```

`make_request` / `make_httpx_request` 通过 `to_request` 间接获得编码能力，无需额外修改。

### 3.2 `burpr/burpr.py`

#### `from_curl()` 增加 `recipe` 参数

```python
def from_curl(curl_command: str, recipe: Optional[EncodingRecipe] = None) -> BurpRequest:
    # ... 现有解析逻辑 ...
    if recipe and body:
        body = recipe.apply_decode(body)
    request = BurpRequest(...)
    request._recipe = recipe
    return request
```

`recipe=None`（默认）时行为完全不变——解码步骤被跳过。

### 3.3 `burpr/__init__.py`

导出新增符号：

```python
from .recipe import EncodingRecipe, RecipeSteps

__all__ = [
    ...,
    'EncodingRecipe',
    'RecipeSteps',
]
```

---

## 四、不变的部分

- `bind()` — 不改动，保持仅对 str body 做 `.replace()`
- `prepare()` — 不改动，保持 latin-1 长度计算
- `to_burp_format()` — 不改动
- `parse_string()` / `parse_file()` — 不改动
- `from_requests()` / `from_http2()` — 不改动（后续可扩展，YAGNI）
- 现有所有测试 — 必须全部通过

---

## 五、测试

新增 `tests/test_recipe.py`。

### 5.1 EncodingRecipe 单元测试

```
test_empty_recipe                     空步骤链，apply_decode / apply_encode 原样返回
test_url_decode_roundtrip             url_decode 解码+编码 round-trip
test_base64_decode_roundtrip          base64_decode 解码+编码 round-trip
test_json_parse_roundtrip             json_parse 解码+编码 round-trip
test_form_urlencoded_roundtrip        form_urlencoded_parse 解码+编码 round-trip
test_chained_recipe                   链式组合：url_decode + form_urlencoded_parse → dict → 编码
test_apply_decode_returns_dict        json_parse 后返回 dict 而非 str
test_decode_error_propagates          非法 JSON 抛出 json.JSONDecodeError
test_encode_error_propagates          类型不匹配抛出异常
```

### 5.2 BurpRequest 集成测试

```
test_from_curl_with_recipe_json      from_curl + json_parse → body 是 dict
test_from_curl_with_recipe_form      from_curl + form_urlencoded_parse → body 是 dict
test_from_curl_without_recipe        from_curl 不传 recipe → body 保持 str（回归）
test_to_request_encodes_body         有 recipe 的请求 to_request 时 body 被编码
test_to_request_no_recipe            无 recipe 时 to_request 行为不变
test_bind_still_works_without_recipe bind 在无 recipe 时正常工作（回归）
```

### 5.3 端到端

```
test_e2e_curl_to_modified_request    curl 导入 → recipe 解码 → 修改 dict → to_request → 验证编码 body
```

### 不做

- 不 mock requests 模块做实时 HTTP 调用
- 不做 fake server 集成测试
- 不测试步骤工厂方法的内部实现（它们是 stdlib 的薄封装）

---

## 六、依赖

零新增。所有步骤实现仅使用 Python stdlib：`urllib.parse`、`base64`、`json`、`typing`。
