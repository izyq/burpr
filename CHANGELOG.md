# Changelog

All notable changes to burpr will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.4.0] - 2026-07-23

### Added
- `EncodingRecipe` 可逆编码转换管道 — 类似 CyberChef 的 recipe 模式
  - 支持链式添加解码/编码步骤对，解码后 body 变为 Python 原生对象（dict、list 等）
  - 修改对象后发送时自动逆编码回原始格式
- `RecipeSteps` 预定义步骤工厂方法：
  - `url_decode()` — URL 解码/编码（str ⇄ str）
  - `base64_decode()` — Base64 解码/编码（str ⇄ str）
  - `json_parse()` — JSON 解析/序列化（str ⇄ dict/list）
  - `form_urlencoded_parse()` — 表单解析/序列化（str ⇄ dict）
- Recipe 可独立于 BurpRequest 使用：`apply_decode` / `apply_encode` 方法直接调用
- `BurpRequest.verify()` — 解码再编码对比原始 body，验证 recipe round-trip 是否正确
- `BurpRequest.body` 改为 property，支持 str 和 dict/list 等任意类型
- `BurpRequest._recipe` 属性 — 关联的 EncodingRecipe，发送时自动逆编码
- `BurpRequest._get_send_body()` — 获取发送用 body，有 recipe 则自动 `apply_encode`
- `from_curl()` 新增 `recipe` 参数 — 解析时自动解码 body
- `prepare()` 适配 dict body — 通过 `_get_send_body()` 计算正确的 Content-Length

### Changed
- `BurpRequest.__init__` — body 存储为 `_body`，通过 property 访问
- `to_request()` / `make_request()` / `make_httpx_request()` — 发送前自动调用 `_get_send_body()`
- `burpr.__init__` — 导出 `EncodingRecipe` 和 `RecipeSteps`

## [0.3.0] - 2025-01-27

### Added
- `auto_prepare` parameter to `to_request()`, `make_request()`, and `make_httpx_request()` methods
  - Allows disabling automatic Content-Length calculation for security testing (e.g., desync attacks)
  - Defaults to `True` for convenience

### Changed
- Made `from_requests_prepared()` private (`_from_requests_prepared()`) as it's only used internally
- BurpRequest now uses direct attribute access instead of getter/setter methods

### Removed
- Redundant getter/setter methods from BurpRequest:
  - `get_headers()`, `set_headers()`, `get_body()`, `get_header()`, `remove_header()`
  - `set_host()`, `set_path()`, `set_method()`, `set_protocol()`, `set_transport()`
- Users should now directly access/modify attributes: `req.host`, `req.headers`, etc.

## [0.2.0] - 2025-01-27

### Added
- Full Latin-1 encoding support for fuzzing-friendly operations
- Support for bytes input in `parse_string()`, `set_body()`, and `set_header()`
- Preservation of null bytes and all control characters (0x00-0xFF)
- Proper Content-Length calculation based on Latin-1 byte length

### Changed
- File parsing now uses Latin-1 encoding instead of UTF-8
- Header parsing preserves exact header values (only strips single leading space after colon)
- Body content is stored as string but preserves all byte values via Latin-1

### Fixed
- Content-Length now correctly calculated based on byte length, not character count

## [0.1.0] - 2025-01-27

### Added
- Initial release of burpr library
- Parse Burp Suite HTTP requests from strings and files
- Parse curl commands with full argument support
- Parse HTTP/2 requests with pseudo-headers
- Parse from Python requests library objects
- Placeholder system using %VARIABLE% format for dynamic values
- `.bind()` method for replacing placeholders with actual values
- Direct request execution with `.make_request()` and `.make_httpx_request()`
- Convert to requests.PreparedRequest with `.to_request()`
- Utility functions: clone(), prepare(), to_burp_format()
- Comprehensive error handling with BurpParseError
- Support for all HTTP methods (GET, POST, PUT, DELETE, PATCH, OPTIONS, etc.)
- Support for various content types (JSON, XML, form data, multipart)
- HTTP/HTTPS transport detection based on port and scheme
- Method chaining support for bind() operations
- Comprehensive test suite with 47+ tests

### Security
- Added warnings against malicious code generation
- Secure placeholder handling to prevent injection attacks

### Dependencies
- requests >= 2.25.0
- httpx[http2] >= 0.23.0