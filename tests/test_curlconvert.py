"""curlconverter 完整移植的集成测试——验证与 golden fixtures 的等价性."""

import json
import os
import pytest

from burpr.curlconvert import parse, Word
from burpr.curlconvert.headers import Headers

FIX = "/Users/z/Documents/Proj/claude/burpr/curlconverter-master/test/fixtures"


def _serialize(obj):
    """与 JS stringifyWords + JSON.stringify 对齐的序列化."""
    if isinstance(obj, Word):
        return obj.to_string()
    if isinstance(obj, Headers):
        return {
            "lowercase": obj.lowercase,
            "headers": [[_serialize(n),
                         (_serialize(v) if v is not None else None)]
                        for n, v in obj.headers],
        }
    if isinstance(obj, list):
        return [_serialize(x) for x in obj]
    if isinstance(obj, dict):
        return {_serialize(k): _serialize(v) for k, v in obj.items()}
    return obj


class TestGoldenFixtures:
    """比对 parser fixtures 金标准."""

    @pytest.fixture(autouse=True)
    def _skip_if_no_fixtures(self):
        if not os.path.isdir(FIX):
            pytest.skip("curlconverter fixtures not found")

    @pytest.mark.parametrize("name", sorted(
        fn[:-5] for fn in os.listdir(os.path.join(FIX, "parser"))))
    def test_golden(self, name):
        cmd_file = os.path.join(FIX, "curl_commands", name + ".sh")
        with open(cmd_file) as f:
            cmd = f.read()
        golden_file = os.path.join(FIX, "parser", name + ".json")
        with open(golden_file) as f:
            expected = json.load(f)
        actual = _serialize(parse(cmd))
        assert actual == expected


class TestAllCommandsSmoke:
    """108 条 curl 命令冒烟(不崩溃 + 结构合理)."""

    @pytest.fixture(autouse=True)
    def _skip_if_no_fixtures(self):
        cmd_dir = os.path.join(FIX, "curl_commands")
        if not os.path.isdir(cmd_dir) or not os.listdir(cmd_dir):
            pytest.skip("curlconverter fixtures not found")

    def _files(self):
        cmd_dir = os.path.join(FIX, "curl_commands")
        return sorted(fn for fn in os.listdir(cmd_dir) if fn.endswith(".sh"))

    def test_all_parse_without_crash(self):
        cmd_dir = os.path.join(FIX, "curl_commands")
        passed = 0
        for fn in self._files():
            with open(os.path.join(cmd_dir, fn)) as f:
                cmd = f.read()
            try:
                r = parse(cmd)
                assert r and r[0]["urls"], "empty"
                passed += 1
            except Exception:
                pass
        assert passed == 108, f"expected 108, got {passed}"

    def test_method_uppercase(self):
        cmd_dir = os.path.join(FIX, "curl_commands")
        for fn in self._files():
            with open(os.path.join(cmd_dir, fn)) as f:
                cmd = f.read()
            r = parse(cmd)
            m = r[0]["urls"][0]["method"].to_string()
            assert m and m == m.upper(), f"{fn}: method={m}"

    def test_host_not_empty(self):
        cmd_dir = os.path.join(FIX, "curl_commands")
        for fn in self._files():
            with open(os.path.join(cmd_dir, fn)) as f:
                cmd = f.read()
            r = parse(cmd)
            h = r[0]["urls"][0]["urlObj"]["host"].to_string()
            assert h, f"{fn}: host empty"


class TestPlaceholderSurvival:
    """占位符 $VAR / %X% 通过 toString() 存活,支持 bind."""

    def test_dollar_var_in_header(self):
        r = parse('curl -H "Authorization: Bearer $DO_API_TOKEN" https://a.com')[0]
        val = r["headers"].get("authorization")
        assert val is not None
        assert "$DO_API_TOKEN" in val.to_string()

    def test_percent_in_body(self):
        r = parse("""curl -d '{"name": "%NAME%"}' https://a.com""")[0]
        assert r["data"].to_string() == '{"name": "%NAME%"}'

    def test_dollar_var_in_single_quotes(self):
        """单引号内 $ 是字面量."""
        r = parse("curl -d '$2FA_CODE$' https://a.com")[0]
        assert "$2FA_CODE$" in r["data"].to_string()
