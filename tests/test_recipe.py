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
        """URL 解码 + 编码 round-trip——quote_plus 对除了字母数字和 `_.-~` 外的所有字符编码."""
        original = "hello world"
        encoded = "hello+world"
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
        """完整流程：解码 → 修改 dict → 编码——% 会被 quote_plus 编码为 %25."""
        encoded = "cjsj=2026-07-22+00%3A00%3A00&dqbm=1218"
        recipe = EncodingRecipe() \
            .add_step(*RecipeSteps.url_decode()) \
            .add_step(*RecipeSteps.form_urlencoded_parse())
        decoded = recipe.apply_decode(encoded)
        decoded["dqbm"] = "%CITY_CODE%"
        result = recipe.apply_encode(decoded)
        # % 被 quote_plus 编码为 %25，= 被编码为 %3D
        assert "dqbm%3D%2525CITY_CODE%2525" in result

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

        # 验证发出的 data 是编码后的 JSON 字符串（bytes）
        call_kwargs = mock_requests.Request.call_args[1]
        assert call_kwargs["data"] == b'{"dqbm": "4401"}'

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
        # data 是 bytes（latin-1 编码），验证包含修改后的值
        data_str = call_kwargs["data"].decode('latin-1') if isinstance(call_kwargs["data"], bytes) else call_kwargs["data"]
        assert "2026-08-01" in data_str
        # 验证 dataWrap 字段被正确编码（= 被 quote_plus 编码为 %3D）
        assert "dataWrap%3D" in data_str
