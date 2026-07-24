import re
from typing import Optional
from burpr.models.BurpRequest import BurpRequest
from burpr.enums.TransportEnum import TransportEnum
from burpr.enums.ProtocolEnum import ProtocolEnum


class BurpParseError(Exception):
    pass


def parse_string(string: str | bytes) -> BurpRequest:
    """Parse a Burp Suite HTTP request string into a BurpRequest object."""
    # Convert bytes to string using latin-1 if needed
    if isinstance(string, bytes):
        string = string.decode('latin-1')
    
    if not string.strip():
        raise BurpParseError("Empty request string")
    
    lines = string.replace('\r\n', '\n').split('\n')
    if not lines:
        raise BurpParseError("Invalid request format")
    
    parts = lines[0].split(" ", 2)
    
    if len(parts) < 3:
      raise BurpParseError(f"Invalid request line: {lines[0]}")
    
    method, full_path, protocol = parts[0], parts[1], parts[2]
    
    full_path = re.sub(r"\s+", "%20", full_path)
    
    # Convert protocol string to enum
    protocol_enum = ProtocolEnum.HTTP1_1  # Default
    if protocol == "HTTP/2":
        protocol_enum = ProtocolEnum.HTTP2
    elif protocol == "HTTP/1.0":
        protocol_enum = ProtocolEnum.HTTP1_0
    
    # Parse headers
    headers = {}
    body_start_idx = len(lines)
    
    for idx, line in enumerate(lines[1:], 1):
        if line == "":
            body_start_idx = idx + 1
            break
        
        # Handle headers with or without space after colon
        header_match = re.match(r'^([^:]+):(.*)$', line)
        if header_match:
            # Strip only one leading space if present (common in HTTP)
            value = header_match.group(2)
            if value.startswith(' '):
                value = value[1:]
            headers[header_match.group(1)] = value
        else:
            raise BurpParseError(f"Invalid header format: {line}")
    
    # Determine transport based on Host header and common patterns
    host = headers.get("Host", "")
    transport = TransportEnum.HTTPS  # Default to HTTPS
    
    # Check for explicit port 80 or common HTTP patterns
    if ":80" in host or (headers.get("Referer", "").startswith("http://") and 
                        not headers.get("Referer", "").startswith("https://")):
        transport = TransportEnum.HTTP
    
    # Get raw body content as string
    body = ""
    if body_start_idx < len(lines):
        body_lines = lines[body_start_idx:]
        body = '\n'.join(body_lines)
    
    if "Host" not in headers:
        raise BurpParseError("Missing required Host header")
    
    return BurpRequest(
        headers["Host"],
        full_path,
        protocol_enum,
        method,
        headers,
        body,
        transport
    )
  
def parse_file(file: str) -> BurpRequest:
    """Parse a Burp Suite HTTP request from a file."""
    with open(file, "rb") as f:
        # Read as bytes and decode with latin-1 to preserve all byte values
        return parse_string(f.read().decode('latin-1'))


def clone(req: BurpRequest) -> BurpRequest:
    """Create a deep copy of a BurpRequest object."""
    import copy
    return BurpRequest(
        req.host,
        req.path,
        req.protocol,
        req.method,
        copy.deepcopy(req.headers),
        copy.deepcopy(req.body),
        req.transport
    )


def prepare(req: BurpRequest) -> None:
    """Prepare request by setting appropriate headers."""
    # Set Content-Length based on body bytes (latin-1 encoding)
    body = req._get_send_body()
    if body:
        req.set_header("Content-Length", str(len(body.encode('latin-1'))))
    else:
        req.set_header("Content-Length", "0")


def to_burp_format(req: BurpRequest) -> str:
    """Convert a BurpRequest back to Burp Suite format string."""
    lines = []
    
    # Request line
    lines.append(f"{req.method} {req.path} {req.protocol}")
    
    # Headers
    for key, value in req.headers.items():
        lines.append(f"{key}: {value}")
    
    # Empty line between headers and body
    lines.append("")
    
    # Body
    if req.body:
        lines.append(req.body)
    
    return "\n".join(lines)


def from_curl(curl_command: str, recipe: Optional['EncodingRecipe'] = None) -> BurpRequest:
    """Convert a curl command to BurpRequest.

    解析委托给 burpr.curlconvert(完整移植自 curlconverter):
    tree-sitter-bash AST → argv → 选项表 → Request,再映射成 BurpRequest。

    Args:
        curl_command: curl command string
        recipe: Optional EncodingRecipe to decode the body

    Returns:
        BurpRequest object
    """
    from burpr.curlconvert import parse, get_first

    warnings = []
    requests = parse(curl_command, warnings=warnings)
    request = get_first(requests, warnings)

    url = request["urls"][0]
    url_obj = url["urlObj"]

    host = url_obj["host"].to_string()
    if not host:
        raise BurpParseError("Invalid URL format")

    # path 带前导 '/',query 带前导 '?'
    path = url_obj["path"].to_string() or '/'
    path += url_obj["query"].to_string()

    scheme = url_obj["scheme"].to_string()
    transport = TransportEnum.HTTPS if scheme == 'https' else TransportEnum.HTTP

    method = url["method"].to_string()

    # 头:Host 取自 URL;显式 -H 'Host: x' 覆盖。值为 None 表示显式禁用,跳过。
    headers = {"Host": host}
    for name, value in request["headers"]:
        if value is None:
            continue
        headers[name.to_string()] = value.to_string()

    # body:curlconverter 已把多个 -d 按 curl 语义用 & 拼好
    body = request["data"].to_string() if request.get("data") else ""

    raw_body = None
    if recipe and body:
        raw_body = body
        body = recipe.apply_decode(body)

    burp_request = BurpRequest(
        host=host,
        path=path,
        protocol=ProtocolEnum.HTTP1_1,
        method=method,
        headers=headers,
        body=body,
        transport=transport
    )
    burp_request._recipe = recipe
    burp_request._raw_body = raw_body
    return burp_request


def from_requests_response(response) -> BurpRequest:
    """Convert a requests.Response object to BurpRequest.
    
    Extracts the request that generated this response.
    
    Args:
        response: requests.Response object
        
    Returns:
        BurpRequest object
    """
    return _from_requests_prepared(response.request)


def _from_requests_prepared(prepared_request) -> BurpRequest:
    """Convert a requests.PreparedRequest to BurpRequest.
    
    Args:
        prepared_request: requests.PreparedRequest object
        
    Returns:
        BurpRequest object
    """
    # Parse URL to get components
    from urllib.parse import urlparse
    parsed = urlparse(prepared_request.url)
    
    # Determine transport
    transport = TransportEnum.HTTPS if parsed.scheme == "https" else TransportEnum.HTTP
    
    # Build path with query string
    path = parsed.path or "/"
    if parsed.query:
        path = f"{path}?{parsed.query}"
    
    # Get host from URL
    host = parsed.netloc
    
    # Convert headers - requests uses CaseInsensitiveDict
    headers = dict(prepared_request.headers)
    
    # Get body
    body = ""
    if prepared_request.body:
        if isinstance(prepared_request.body, bytes):
            body = prepared_request.body.decode('latin-1')
        else:
            body = str(prepared_request.body)
    
    return BurpRequest(
        host=host,
        path=path,
        protocol=ProtocolEnum.HTTP1_1,  # requests library typically uses HTTP/1.1
        method=prepared_request.method or "GET",
        headers=headers,
        body=body,
        transport=transport
    )


def from_requests(method: str, url: str, **kwargs) -> BurpRequest:
    """Create a BurpRequest from requests-style arguments.
    
    Args:
        method: HTTP method (GET, POST, etc.)
        url: Target URL
        **kwargs: Additional arguments like headers, data, json, params
        
    Returns:
        BurpRequest object
        
    Example:
        req = from_requests("POST", "https://api.example.com/users",
                          json={"name": "John"},
                          headers={"Authorization": "Bearer $TOKEN$"})
    """
    from urllib.parse import urlparse
    import json
    
    # Parse URL
    parsed = urlparse(url)
    transport = TransportEnum.HTTPS if parsed.scheme == "https" else TransportEnum.HTTP
    
    # Build path
    path = parsed.path or "/"
    
    # Handle query parameters
    params = kwargs.get("params", {})
    if params:
        # Build query string without encoding $ characters (for placeholders)
        query_parts = []
        for key, value in params.items():
            query_parts.append(f"{key}={value}")
        query_str = "&".join(query_parts)
        path = f"{path}?{query_str}"
    elif parsed.query:
        path = f"{path}?{parsed.query}"
    
    # Handle headers
    headers = kwargs.get("headers", {}).copy()
    headers["Host"] = parsed.netloc
    
    # Handle body
    body = ""
    if "json" in kwargs:
        headers["Content-Type"] = "application/json"
        body = json.dumps(kwargs["json"])
    elif "data" in kwargs:
        data = kwargs["data"]
        if isinstance(data, dict):
            headers["Content-Type"] = "application/x-www-form-urlencoded"
            # Build form data without encoding $ characters (for placeholders)
            body_parts = []
            for key, value in data.items():
                body_parts.append(f"{key}={value}")
            body = "&".join(body_parts)
        else:
            body = str(data)
    
    return BurpRequest(
        host=parsed.netloc,
        path=path,
        protocol=ProtocolEnum.HTTP1_1,
        method=method.upper(),
        headers=headers,
        body=body,
        transport=transport
    )


def from_http2(headers_dict: dict, body: str = "") -> BurpRequest:
    """Convert HTTP/2 pseudo-headers and headers to BurpRequest.
    
    Args:
        headers_dict: Dictionary containing HTTP/2 pseudo-headers and regular headers
                     Pseudo-headers start with ':' (e.g., ':method', ':path', ':authority')
        body: Request body as string
        
    Returns:
        BurpRequest object
        
    Example:
        headers = {
            ":method": "POST",
            ":path": "/api/users",
            ":authority": "example.com",
            ":scheme": "https",
            "content-type": "application/json",
            "authorization": "Bearer $TOKEN$"
        }
        req = from_http2(headers, '{"name": "$NAME$"}')
    """
    # Extract HTTP/2 pseudo-headers
    method = headers_dict.get(":method", "GET")
    path = headers_dict.get(":path", "/")
    authority = headers_dict.get(":authority", "")
    scheme = headers_dict.get(":scheme", "https")
    
    # Convert to transport enum
    transport = TransportEnum.HTTPS if scheme == "https" else TransportEnum.HTTP
    
    # Extract regular headers (non-pseudo headers)
    regular_headers = {}
    for key, value in headers_dict.items():
        if not key.startswith(":"):
            regular_headers[key] = value
    
    # Add Host header from authority
    if authority and "host" not in regular_headers:
        regular_headers["Host"] = authority
    
    return BurpRequest(
        host=authority,
        path=path,
        protocol=ProtocolEnum.HTTP2,
        method=method,
        headers=regular_headers,
        body=body,
        transport=transport
    )



