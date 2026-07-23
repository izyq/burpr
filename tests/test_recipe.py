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
