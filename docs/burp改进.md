https://github.com/krystianbajno/burpr

我觉得应该做这样一个辅助函数，像CyberChef一样，有一个recipe记录解码的步骤，将编码进行解码，然后既保证了我写代码的时候对请求体的可读性，又方便进行参数的替换，解码后完成参数的替换，再按照recipe记录的解码的步骤反向编码回去



你的想法非常出色！它超越了简单的自动解码，而是将“解码-修改-编码”这一常见模式抽象为一个**可逆的转换管道（Recipe）**，类似于 CyberChef 的“配方”。这既能保证开发时请求体的可读性，又能无缝支持占位符替换，最终发送时自动恢复原始编码。这正是生产级工具应有的设计。

下面我为你设计一套完整、可落地的优化方案，包括核心组件、与 `burpr` 的集成方式、使用示例以及注意事项。

---

## 一、核心组件：`EncodingRecipe` 类

我们设计一个 `EncodingRecipe` 类，它内部维护一个**有序的操作步骤列表**，每个步骤都是一个**可逆的转换函数对**：`decode` 和 `encode`。

### 1.1 基本结构

```python
from typing import Callable, List, Tuple, Any
import urllib.parse
import base64
import json

class EncodingRecipe:
    def __init__(self):
        self.steps: List[Tuple[Callable, Callable]] = []  # (decode_func, encode_func)

    def add_step(self, decode_func: Callable, encode_func: Callable) -> 'EncodingRecipe':
        """添加一个可逆转换步骤，返回自身以支持链式调用"""
        self.steps.append((decode_func, encode_func))
        return self

    def apply_decode(self, data: str) -> Any:
        """按顺序执行所有解码步骤，返回可能是 str、dict 或其他 Python 原生对象"""
        for decode_func, _ in self.steps:
            data = decode_func(data)
        return data

    def apply_encode(self, data: Any) -> str:
        """按逆序执行所有编码步骤（反向操作），从 Python 对象还原为原始格式字符串"""
        for decode_func, encode_func in reversed(self.steps):
            data = encode_func(data)
        return data
```

关键设计：**`apply_decode` 返回 `Any`，`apply_encode` 接受 `Any`**。解码链条的终点可以是 Python 原生对象（dict、list 等），而不仅是美化后的字符串。这样修改 body 从字符串拼接/替换升维到对象操作。

### 1.2 预定义常用步骤（工厂方法）

Recipe 的威力在于**链式组合**——每一步都剥开一层编码，最终抵达 Python 原生对象。修改后，反向链条自动把对象"打包"回原始格式。

```python
class RecipeSteps:
    @staticmethod
    def url_decode(encoding='utf-8'):
        """URL 解码步骤：str → str"""
        return lambda s: urllib.parse.unquote_plus(s, encoding=encoding), \
               lambda s: urllib.parse.quote_plus(s, encoding=encoding)

    @staticmethod
    def base64_decode():
        """Base64 解码步骤：str → str"""
        return lambda s: base64.b64decode(s).decode('utf-8'), \
               lambda s: base64.b64encode(s.encode('utf-8')).decode('utf-8')

    @staticmethod
    def json_parse():
        """JSON 解析步骤：str → dict/list（Python 原生对象）
        
        这是最关键的一步——decode 返回真正的 Python 对象，不再是字符串。
        修改 body 从字符串拼接/替换升维到精确的对象操作。

        注意：encode 使用 json.dumps(obj, ensure_ascii=False) 避免中文被转 \uXXXX。
        """
        return lambda s: json.loads(s), \
               lambda obj: json.dumps(obj, ensure_ascii=False)

    @staticmethod
    def form_urlencoded_parse():
        """表单数据解析步骤：str → dict
        
        将 key1=val1&key2=val2&nested=%7B%22x%22%3A1%7D 解析为
        {'key1': 'val1', 'key2': 'val2', 'nested': '{"x":1}'}
        可以与 json_parse 嵌套使用（对特定字段再解析）。
        """
        return lambda s: dict(urllib.parse.parse_qsl(s, keep_blank_values=True)), \
               lambda d: urllib.parse.urlencode(d)

    # 可以继续添加：gzip解压、hex解码、XML解析等
```

**关键区分**：`json_parse()` 和 `form_urlencoded_parse()` 的 decode 端返回 Python 对象，encode 端接受 Python 对象——不再是纯字符串管道。

### 1.3 链式组合：从乱码到对象

**关键区分**：`form_urlencoded_parse` 内部的 `parse_qsl` **自带 URL 解码**。因此对 `application/x-www-form-urlencoded` 类型的 body，**直接用 `form_urlencoded_parse` 即可**——不要在前面加 `url_decode`，否则会双重编码/解码，`=` 和 `&` 被过度转义。

```python
# ✅ 正确：表单格式 body → 直接用 form_urlencoded_parse
# 原始：cjsj=2026-07-22+00%3A00%3A00&dataWrap=%7B%22query%22%3A%7B%22dqbm%22%3A%221218%22%7D%7D
recipe = EncodingRecipe() \
    .add_step(*RecipeSteps.form_urlencoded_parse())

decoded = recipe.apply_decode(original_body)
# decoded = {
#     'cjsj': '2026-07-22 00:00:00',
#     'dataWrap': '{"query":{"dqbm":"1218"}}'
# }

# 修改后编码回去，格式与原始一致
encoded = recipe.apply_encode(decoded)
# → cjsj=2026-07-22+00%3A00%3A00&dataWrap=%7B%22query%22%3A%7B%22dqbm%22%3A%221218%22%7D%7D
```

```python
# ❌ 错误：多加了 url_decode 导致双重编码
recipe = EncodingRecipe() \
    .add_step(*RecipeSteps.url_decode()) \        # ← 多余！
    .add_step(*RecipeSteps.form_urlencoded_parse())
# encode 时会 quote_plus 编码 = 和 &，服务器收到错误格式
```

`url_decode + form_urlencoded_parse` 的链式组合**仅适用于**"整个 body 本身又是一个 URL 编码字符串"的罕见场景：

```python
# 仅此场景需要 url_decode：body 是纯 URL 编码字符串，不含 key=value 结构
# 原始：hello+world%21 → 解码：hello world!
recipe = EncodingRecipe().add_step(*RecipeSteps.url_decode())
```

如果 dataWrap 内部还需要结构化修改：

```python
# 第一步：表单 → dict
body_dict = recipe.apply_decode(original_body)
# 第二步：手动解析嵌套 JSON 字段（中文用 ensure_ascii=False 避免 \uXXXX 转义）
import json
body_dict['dataWrap'] = json.loads(body_dict['dataWrap'])
body_dict['dataWrap']['query']['dqbm'] = '%CITY_CODE%'     # 精确修改！
body_dict['dataWrap'] = json.dumps(body_dict['dataWrap'], ensure_ascii=False)  # 还原为 JSON 字符串
# 第三步：发送前自动编码回表单格式
encoded = recipe.apply_encode(body_dict)
```

---

## 二、与 `burpr` 的集成

### 2.1 `BurpRequest.body` 的双态设计

Recipe 解码后，`body` 不再是纯字符串——它可以是 **Python 原生对象**（dict、list 等）。`BurpRequest` 需要接受两种 body 形态：

```python
class BurpRequest:
    def __init__(self, ..., body=""):
        self._body = body          # 内部始终存储"当前状态"
        self._recipe = None        # 关联的 recipe，用于发送时逆编码

    @property
    def body(self):
        """读取 body——解码后的对象或字符串"""
        return self._body

    @body.setter
    def body(self, value):
        """设置 body——接受 str、dict、list 等任意类型"""
        self._body = value

    def make_request(self):
        body_to_send = self._body
        if self._recipe:
            # recipe.apply_encode 接受任意类型，返回编码后的 str
            body_to_send = self._recipe.apply_encode(self._body)
            # 用 latin-1 编码为 bytes 发送
        # ...
```

### 2.2 在 `from_curl` 中增加 `recipe` 参数

```python
def from_curl(curl_cmd: str, recipe: Optional[EncodingRecipe] = None) -> BurpRequest:
    # ... 现有解析逻辑提取 method, url, headers, body ...
    if recipe and body:
        body = recipe.apply_decode(body)   # → 可能变成 dict/list
    request = BurpRequest(
        host=...,
        path=...,
        protocol=...,
        method=...,
        headers=...,
        body=body,                         # 解码后的对象
        transport=...
    )
    request._recipe = recipe               # 保存 recipe 用于发送时逆编码
    return request
```

### 2.3 发送时自动编码

`to_request` / `make_request` 中检查 `_recipe`，有则调用 `apply_encode` 还原：

```python
def to_request(self, session=None, auto_prepare=True):
    body = self._body
    if self._recipe:
        body = self._recipe.apply_encode(self._body)  # 任意类型 → str
    # 构造 requests.Request，body 编码为 latin-1 bytes
    req = requests.Request(
        method=self.method,
        url=self.url,
        headers=self.headers.copy(),
        data=body.encode('latin-1') if body else None
    )
    # ...
```

---

## 三、使用示例（完整流程）

### 3.1 字符串级别 → 对象级别：质变

**之前（纯字符串操作——脆弱）：**

```python
# 盲替换：URL 编码后字符串中可能匹配到不该替换的地方
req.body = req.body.replace("1218", "%CITY_CODE%")
```

**之后（Recipe + 对象操作——精确）：**

```python
import burpr
from burpr.recipe import EncodingRecipe, RecipeSteps

# 1. 定义 recipe：表单解析为 dict（form_urlencoded_parse 自带 URL 解码）
recipe = EncodingRecipe() \
    .add_step(*RecipeSteps.form_urlencoded_parse())

# 2. 导入 curl 命令
curl_cmd = '''
curl -X POST https://api.com/data \
  -H "Content-Type: application/x-www-form-urlencoded" \
  --data-raw 'cjsj=2026-07-22+00%3A00%3A00&dataWrap=%7B%22query%22%3A%7B%22dqbm%22%3A%221218%22%7D%7D'
'''

req = burpr.from_curl(curl_cmd, recipe=recipe)

# 3. 此时 req.body 是 Python dict，可以用代码精确操作
print(req.body)
# → {'cjsj': '2026-07-22 00:00:00', 'dataWrap': '{"query":{"dqbm":"1218"}}'}

# 修改表单字段——字典的 key 访问，不会误伤其他字段
req.body['cjsj'] = '2026-08-01 00:00:00'

# 需要深入修改 JSON 嵌套字段？手动解析再改：
import json
dw = json.loads(req.body['dataWrap'])
dw['query']['dqbm'] = '%CITY_CODE%'   # 精确命中 'dqbm'，不会误改
# 用 ensure_ascii=False 避免中文变成 \uXXXX
req.body['dataWrap'] = json.dumps(dw, ensure_ascii=False)

# 4. 发送请求（自动逆编码：dict → urlencode → str）
response = req.make_request()
# 实际发送：cjsj=2026-08-01+00%3A00%3A00&dataWrap=%7B%22query%22%3A%7B%22dqbm%22%3A%22%25CITY_CODE%25%22%7D%7D
```

### 3.2 纯 JSON body 场景（更简单）

```python
recipe = EncodingRecipe() \
    .add_step(*RecipeSteps.json_parse())

req = burpr.from_curl('curl -X POST https://api.com/query -H "Content-Type: application/json" -d \'{"dqbm":"1218","year":"2026"}\'', recipe=recipe)

# req.body 是 dict！
req.body['dqbm'] = '%CITY_CODE%'     # 精确修改
req.body['year'] = '%YEAR%'          # 添加占位符
del req.body['extra_field']          # 删除不需要的字段

response = req.make_request()        # 自动 json.dumps 回去
```

### 3.3 与 `bind()` 协同

`bind()` 方法天然兼容两种 body 形态——它始终对 `body` 做字符串替换；如果 body 是 dict，`str(dict)` 也能工作。但**推荐在对象级别做完具体修改，`bind()` 只做最后的占位符填充**：

```python
# 解码后：对象级修改做"数据整形"
req.body['dataWrap'] = modify_datawrap(req.body['dataWrap'])

# bind()：做最后的占位符值替换
req.bind('%CITY_CODE%', '4401')
req.bind('%YEAR%', '2026')
```

---

## 四、高级设计考量

### 4.1 为什么必须是对象而不是美化字符串？

Recipe 之前的草案让 `json_parse` 返回美化字符串（`json.dumps(..., indent=2)`），表面上看"可读"了，但本质上仍然是字符串——修改仍然靠 `.replace()` 或正则，容易误伤、难以做条件逻辑。

Recipe 真正要做的是 **把 body 变成 Python 原生对象**：

| 操作 | 字符串方式 | 对象方式 |
|:-----|:---------|:--------|
| 读取字段 `dqbm` | `re.search(r'"dqbm":"([^"]+)"', body)` | `body['dqbm']` 或 `body['query']['dqbm']` |
| 修改字段值 | `body.replace(old_val, new_val)` 可能误伤 | `body['dqbm'] = new_val` 精确 |
| 删除字段 | 正则删除键值对，处理逗号/嵌套 | `del body['dqbm']` |
| 添加字段 | 拼接 JSON 字符串 | `body['new_key'] = 'new_val'` |
| 条件修改 | if/else 用正则匹配？不可维护 | 标准 Python 条件语句 |

**结论：解码的终点应该是 Python 对象，不是字符串。**

### 4.2 与占位符系统的协同

`burpr` 的占位符（如 `%VALUE%`）应该在对象修改完成后再填写——这清晰分离了两层操作：

1. **对象级修改**（需要理解数据结构的操作）：增删改字段、嵌套结构调整
2. **占位符填写**（简单的值替换）：`bind('%CITY_CODE%', '4401')`

流程天然支持：
1. `from_curl` 解码 body → Python 对象
2. 用户对对象做结构修改
3. `.bind()` 替换占位符 → 此时对象中的占位符字符串被替换
4. 发送前编码 → 从对象逆编码为原始字符串格式

### 4.3 错误处理与回退

解码可能失败（如非法的 URL 编码），建议在 `apply_decode` 中捕获异常，并**保留原始 body**，同时发出警告，确保程序不会崩溃。

### 4.4 性能考量

Recipe 的操作通常是轻量级的（字符串处理），对性能影响极小。但若涉及压缩/解压（如 gzip），需考虑内存占用，可提供异步或流式选项（暂不展开）。

### 4.5 扩展性：支持动态参数

某些步骤可能需要参数（如编码字符集），可以在 `add_step` 时固化，或允许在 `apply_decode` 时传入上下文（如当前请求头中的 `Content-Type`），实现更智能的自动选择。

---

## 五、优势总结

| 方面         | 传统方案（手动解码）                | Recipe（字符串→字符串）     | Recipe（字符串→对象）              |
|:-------------|:-----------------------------------|:---------------------------|:-----------------------------------|
| **可读性**   | 请求体是乱码，难以修改              | 解码后清晰可读             | **解码后是 Python 对象，IDE 可补全** |
| **参数修改** | 在编码字符串中小心替换，易出错      | `.replace()` 盲替换        | **`body['key'] = val` 精确命中**    |
| **删除字段** | 正则处理，不可靠                    | 正则处理，不可靠           | **`del body['key']`**              |
| **嵌套访问** | 多层正则/字符串查找                 | 多层正则/字符串查找        | **`body['a']['b']` 标准访问**      |
| **自动化**   | 需手动编码后再发送，繁琐            | 自动逆编码                 | **自动逆编码，str/dict 均可**      |
| **可组合性** | 无法处理多重编码（如 Base64 + URL） | 支持任意链式组合           | **链式组合直到对象层**             |
| **维护性**   | 逻辑分散在用户代码中                | 集中在 Recipe 中           | **集中在 Recipe + 标准 Python**    |

---

## 六、后续可能的扩展

1. **自动检测 Content-Type**：内置常用 recipe，根据 `Content-Type` 自动选择（如 `application/x-www-form-urlencoded` 自动 URL 解码+表单解析，`application/json` 自动 JSON 解析）。
2. **可视化 Recipe 编辑器**：提供 GUI 或 DSL 来定义 recipe，方便非编程用户。
3. **与 `burpr` 的交互式模式结合**：在交互式调试中，实时查看解码后的 body（Python 对象形式），支持 REPL 式修改。
4. **自动识别嵌套编码**：如 `dataWrap` 字段内容是 JSON 字符串，自动检测并递归解析。实现方式：
   ```python
   def auto_recipe(content_type: str) -> EncodingRecipe:
       """根据 Content-Type 自动构建 recipe"""
       recipe = EncodingRecipe()
       if 'urlencoded' in content_type:
           recipe.add_step(*RecipeSteps.url_decode())
           recipe.add_step(*RecipeSteps.form_urlencoded_parse())
       elif 'json' in content_type:
           recipe.add_step(*RecipeSteps.json_parse())
       return recipe
   ```

---

这个方案不仅解决了你提出的问题，更将 `burpr` 提升为一个**面向可读性、可调试性、可逆转换的 HTTP 工具集**。如果你愿意，我可以进一步提供完整的代码实现草案，包括单元测试和文档示例。你是否希望我继续细化实现细节？或者你更关注如何向项目提交 PR 的建议？