"""Request 构建——移植自 curlconverter 的 Request.ts."""

import re

from burpr.curlconvert.errors import CCError, has, is_int
from burpr.curlconvert.warnings_ import warnf, warn_if_parts_ignored
from burpr.curlconvert.word import Word, eq, merge_words, join_words
from burpr.curlconvert.headers import Headers, parse_cookies
from burpr.curlconvert.auth import pick_auth
from burpr.curlconvert.curl_url import parseurl
from burpr.curlconvert.query import parse_query_string, percent_encode_plus
from burpr.curlconvert.form import parse_form


def _parse_float(s: str) -> float:
    """JS parseFloat:吃数字前缀,无法解析返回 NaN."""
    m = re.match(r"^[\t\n\v\f\r ]*[+-]?(\d+\.?\d*|\.\d+)([eE][+-]?\d+)?", s)
    if not m:
        return float("nan")
    return float(m.group(0))


def _is_nan(x: float) -> bool:
    return x != x


def build_url(global_, config, url, upload_file=None, output_file=None,
              stdin=None, stdin_file=None):
    original_url = url
    u = parseurl(global_, config, url)

    # https://github.com/curl/curl/blob/curl-7_85_0/src/tool_operate.c#L1124
    if upload_file:
        if u["path"].is_empty():
            u["path"] = upload_file.prepend("/")
        elif u["path"].ends_with("/"):
            u["path"] = u["path"].add(upload_file)

        if config.get("get"):
            warnf(global_, [
                "data-ignored",
                "curl doesn't let you pass --get and --upload-file together",
            ])

    url_with_original_query = merge_words(
        u["scheme"], "://", u["host"], u["path"], u["query"], u["fragment"]
    )

    url_query_array = None
    query_array = None
    query_str_reads_file = None
    if u["query"].to_bool() or config.get("url-query"):
        query_str = None

        query_parts = []
        if u["query"].to_bool():
            # 去掉前导 '?'
            query_parts.append(["raw", u["query"].slice(1)])
            query_array, query_str, query_str_reads_file = build_data(
                query_parts, stdin, stdin_file
            )
            url_query_array = query_array
        if config.get("url-query"):
            query_parts = query_parts + config["url-query"]
            query_array, query_str, query_str_reads_file = build_data(
                query_parts, stdin, stdin_file
            )

        u["query"] = Word()
        if query_str and query_str.to_bool():
            u["query"] = query_str.prepend("?")

    url_without_query_array = merge_words(
        u["scheme"], "://", u["host"], u["path"], u["fragment"]
    )
    url = merge_words(
        u["scheme"], "://", u["host"], u["path"], u["query"], u["fragment"]
    )
    url_without_query_list = url
    query_list, query_dict = parse_query_string(
        u["query"].slice(1) if u["query"].to_bool() else Word()
    )
    if query_list and len(query_list):
        url_without_query_list = merge_words(
            u["scheme"], "://", u["host"], u["path"], u["fragment"]
        )
    else:
        query_list = None
        query_dict = None

    # curl 期望方法总是大写。这里是最后确定方法的地方:
    method = Word("GET")
    if config.get("request") and not eq(config["request"], "null"):
        method = config["request"]
    elif config.get("head"):
        method = Word("HEAD")
    elif upload_file and upload_file.to_bool():
        # --upload-file '' 什么也不做
        method = Word("PUT")
    elif not config.get("get") and (has(config, "data") or has(config, "form")):
        method = Word("POST")

    request_url = {
        "originalUrl": original_url,
        "urlWithoutQueryList": url_without_query_list,
        "url": url,
        "urlObj": u,
        "urlWithOriginalQuery": url_with_original_query,
        "urlWithoutQueryArray": url_without_query_array,
        "method": method,
    }
    if query_str_reads_file:
        request_url["queryReadsFile"] = query_str_reads_file
    if query_list:
        request_url["queryList"] = query_list
        if query_dict:
            request_url["queryDict"] = query_dict
    if query_array:
        request_url["queryArray"] = query_array
    if url_query_array:
        request_url["urlQueryArray"] = url_query_array
    if upload_file:
        if eq(upload_file, "-") or eq(upload_file, "."):
            if stdin_file:
                request_url["uploadFile"] = stdin_file
            elif stdin:
                warnf(global_, [
                    "upload-file-with-stdin-content",
                    "--upload-file with stdin content is not supported",
                ])
                request_url["uploadFile"] = upload_file
            else:
                request_url["uploadFile"] = upload_file
        else:
            request_url["uploadFile"] = upload_file
    if output_file:
        request_url["output"] = output_file

    # --user 优先于 URL 中的认证
    auth = config.get("user", u.get("auth"))
    if auth:
        user, pass_ = (auth.split(":", 2) + [None])[:2]
        request_url["auth"] = [user, pass_ if pass_ is not None else Word()]

    return request_url


def build_data(config_data, stdin=None, stdin_file=None):
    data = []
    data_str_state = Word()
    for i, x in enumerate(config_data):
        type_ = x[0]
        value = x[1]
        name = None

        if i > 0 and type_ != "json":
            data_str_state = data_str_state.append("&")

        if type_ == "urlencode":
            # curl 先查 = 再查 @
            split_on = "=" if (value.includes("=") or not value.includes("@")) else "@"
            if value.includes("@") or value.includes("="):
                name, value = value.split(split_on, 2)

            if split_on == "=":
                if name and name.to_bool():
                    data_str_state = data_str_state.add(name).append("=")
                # curl 的 --data-urlencode 把空格编成 "+"
                data_str_state = data_str_state.add(percent_encode_plus(value))
                continue

            name = name if (name and name.to_bool()) else None
            value = value.prepend("@")

        filename = None

        if type_ != "raw" and value.starts_with("@"):
            filename = value.slice(1)
            if eq(filename, "-"):
                if stdin is not None:
                    if type_ in ("binary", "json"):
                        value = stdin
                    elif type_ == "urlencode":
                        value = merge_words(
                            name.append("=") if (name and name.length) else Word(),
                            percent_encode_plus(stdin),
                        )
                    else:
                        value = stdin.replace(_NEWLINES, "")
                    filename = None
                elif stdin_file is not None:
                    filename = stdin_file
                # else: stdin 被读两次第二次会空

        if filename is not None:
            if data_str_state.to_bool():
                data.append(data_str_state)
                data_str_state = Word()
            data_param = {"filetype": type_, "filename": filename}
            if name:
                data_param["name"] = name
            data.append(data_param)
        else:
            data_str_state = data_str_state.add(value)

    if data_str_state.to_bool():
        data.append(data_str_state)

    data_str_reads_file = None
    parts = []
    for d in data:
        if not isinstance(d, Word):
            if data_str_reads_file is None:
                data_str_reads_file = d["filename"].to_string()
            if d.get("name"):
                parts.append(merge_words(d["name"], "=@", d["filename"]))
            else:
                parts.append(d["filename"].prepend("@"))
        else:
            parts.append(d)
    data_str = merge_words(*parts)

    return data, data_str, data_str_reads_file


def _parse_content_type(string: str):
    """把 Content-Type 头解析成类型 + 参数列表."""
    if ";" not in string:
        return [string, []]
    semi = string.index(";")
    type_ = string[:semi]
    rest = string[semi:]

    params = _CT_PARAM_RE.findall(rest)
    if rest.strip() and not params:
        return None
    parsed_params = []
    for param in _CT_PARAM_RE.finditer(rest):
        name = param.group(1)
        value = param.group(3) or param.group(2)[1:-1]
        parsed_params.append([name, value])
    return [type_, parsed_params]


def _parse_boundary(string: str):
    header = _parse_content_type(string)
    if not header:
        return None
    for name, value in header[1]:
        if name == "boundary":
            return value
    return None


def _parse_raw_form(data: str, boundary: str):
    end_boundary = "\r\n--" + boundary + "--\r\n"
    if not data.endswith(end_boundary):
        return None
    data = data[: -len(end_boundary)]

    boundary = "--" + boundary + "\r\n"
    if data and not data.startswith(boundary):
        return None
    data = data[len(boundary):]
    parts = data.split("\r\n" + boundary)
    form = []
    roundtrips = True
    for part in parts:
        lines = part.split("\r\n")
        if len(lines) < 2:
            return None

        form_param = {"name": Word(), "content": Word()}
        seen_content_disposition = False
        headers = []
        i = 0
        while i < len(lines):
            if len(lines[i]) == 0:
                break
            name, value = (lines[i].split(": ", 1) + [None])[:2]
            if name is None or value is None:
                return None
            if name.lower() == "content-disposition":
                if seen_content_disposition:
                    return None
                content_disposition = _parse_content_type(value)
                if not content_disposition:
                    return None
                type_, params = content_disposition
                if type_ != "form-data":
                    return None
                extra = 0
                for param_name, param_value in params:
                    if param_name == "name":
                        form_param["name"] = Word(param_value)
                    elif param_name == "filename":
                        form_param["filename"] = Word(param_value)
                    else:
                        extra += 1
                if extra:
                    roundtrips = False
                seen_content_disposition = True
            elif name.lower() == "content-type":
                form_param["contentType"] = Word(value)
            else:
                headers.append(Word(lines[i]))
            i += 1
        if headers:
            form_param["headers"] = headers

        if not seen_content_disposition:
            return None
        if i == len(lines):
            return None
        if form_param["name"].is_empty():
            return None
        form_param["content"] = Word("\n".join(lines[i + 1:]))
        form.append(form_param)
    return form, roundtrips


def build_request(global_, config, stdin=None, stdin_file=None):
    if not config.get("url"):
        raise CCError("no URL specified!")

    headers = Headers(config.get("header"), global_["warnings"])
    proxy_headers = Headers(
        config.get("proxy-header"), global_["warnings"], "--proxy-header"
    )

    cookies = None
    cookie_files = []
    cookie_header = headers.get("cookie")
    if cookie_header:
        parsed_cookies = parse_cookies(cookie_header)
        if parsed_cookies:
            cookies = parsed_cookies
    elif cookie_header is None and config.get("cookie"):
        # 有 Cookie 头时,--cookie 被忽略
        cookie_strings = []
        for c in config["cookie"]:
            # 不含 = 的 --cookie 视为文件名
            if c.includes("="):
                cookie_strings.append(c)
            else:
                cookie_files.append(c)
        if cookie_strings:
            cookie_string = join_words(config["cookie"], "; ")
            headers.set_if_missing("Cookie", cookie_string)
            parsed_cookies = parse_cookies(cookie_string)
            if parsed_cookies:
                cookies = parsed_cookies

    referer_auto = False
    if config.get("user-agent"):
        headers.set_if_missing("User-Agent", config["user-agent"])
    if config.get("referer"):
        if config["referer"].includes(";auto"):
            referer_auto = True
        referer = config["referer"].replace(_AUTO_SUFFIX, "")
        if referer.length:
            headers.set_if_missing("Referer", referer)
    if config.get("range"):
        range_ = config["range"].prepend("bytes=")
        if not range_.includes("-"):
            range_ = range_.append("-")
        headers.set_if_missing("Range", range_)
    if config.get("time-cond"):
        timecond = config["time-cond"]
        header = "If-Modified-Since"
        first = timecond.char_at(0)
        if first == "+":
            timecond = timecond.slice(1)
        elif first == "-":
            timecond = timecond.slice(1)
            header = "If-Unmodified-Since"
        elif first == "=":
            timecond = timecond.slice(1)
            header = "Last-Modified"
        headers.set_if_missing(header, timecond)

    data = None
    data_str = None
    data_str_reads_file = None
    query_array = None
    if config.get("data"):
        if config.get("get"):
            # --get --data 会覆盖 --url-query
            config["url-query"] = config["data"]
            del config["data"]
        else:
            data, data_str, data_str_reads_file = build_data(
                config["data"], stdin, stdin_file
            )
    if config.get("url-query"):
        query_array, _, _ = build_data(config["url-query"], stdin, stdin_file)

    urls = []
    upload_files = config.get("upload-file", [])
    output_files = config.get("output", [])
    for i, url in enumerate(config["url"]):
        urls.append(build_url(
            global_, config, url,
            upload_files[i] if i < len(upload_files) else None,
            output_files[i] if i < len(output_files) else None,
            stdin, stdin_file,
        ))
    # --get 把 --data 移进 URL 查询串
    if config.get("get") and config.get("data"):
        del config["data"]

    if len(config.get("upload-file", [])) > len(config["url"]):
        warnf(global_, [
            "too-many-upload-files",
            "Got more --upload-file/-T options than URLs: "
            + ", ".join(repr(f.to_string()) for f in config["upload-file"]),
        ])
    if len(config.get("output", [])) > len(config["url"]):
        warnf(global_, [
            "too-many-output-files",
            "Got more --output/-o options than URLs: "
            + ", ".join(repr(f.to_string()) for f in config["output"]),
        ])

    request = {
        "urls": urls,
        "authType": pick_auth(config["authtype"]),
        "proxyAuthType": pick_auth(config["proxyauthtype"]),
        "headers": headers,
        "proxyHeaders": proxy_headers,
    }
    if stdin:
        request["stdin"] = stdin
    if stdin_file:
        request["stdinFile"] = stdin_file

    if has(config, "globoff"):
        request["globoff"] = config["globoff"]
    if has(config, "disallow-username-in-url"):
        request["disallowUsernameInUrl"] = config["disallow-username-in-url"]
    if has(config, "path-as-is"):
        request["pathAsIs"] = config["path-as-is"]

    if referer_auto:
        request["refererAuto"] = True

    if cookies:
        request["cookies"] = cookies
    if cookie_files:
        request["cookieFiles"] = cookie_files
    if config.get("cookie-jar"):
        request["cookieJar"] = config["cookie-jar"]
    if has(config, "junk-session-cookies"):
        request["junkSessionCookies"] = config["junk-session-cookies"]

    if has(config, "compressed"):
        request["compressed"] = config["compressed"]
    if has(config, "tr-encoding"):
        request["transferEncoding"] = config["tr-encoding"]

    if config.get("include"):
        request["include"] = True

    if config.get("json"):
        headers.set_if_missing("Content-Type", "application/json")
        headers.set_if_missing("Accept", "application/json")
    elif config.get("data"):
        headers.set_if_missing("Content-Type", "application/x-www-form-urlencoded")
    elif config.get("form"):
        request["multipartUploads"] = parse_form(config["form"], global_["warnings"])

    content_type = headers.get_content_type()
    exact_content_type = headers.get("Content-Type")
    if (
        config.get("data")
        and not data_str_reads_file
        and data_str
        and data_str.is_string()
        and not config.get("form")
        and not request.get("multipartUploads")
        and content_type == "multipart/form-data"
        and exact_content_type
        and exact_content_type.is_string()
    ):
        boundary = _parse_boundary(exact_content_type.to_string())
        if boundary:
            form = _parse_raw_form(data_str.to_string(), boundary)
            if form:
                parsed_form, roundtrip = form
                request["multipartUploads"] = parsed_form
                if not roundtrip:
                    request["multipartUploadsDoesntRoundtrip"] = True

    if has(config, "form-escape"):
        request["formEscape"] = config["form-escape"]

    if config.get("aws-sigv4"):
        request["authType"] = "aws-sigv4"
        request["awsSigV4"] = config["aws-sigv4"]
    if request["authType"] == "bearer" and config.get("oauth2-bearer"):
        bearer = config["oauth2-bearer"].prepend("Bearer ")
        headers.set_if_missing("Authorization", bearer)
        request["oauth2Bearer"] = config["oauth2-bearer"]
    if config.get("delegation"):
        request["delegation"] = config["delegation"]
    if config.get("krb"):
        request["krb"] = config["krb"]
    if config.get("sasl-authzid"):
        request["saslAuthzid"] = config["sasl-authzid"]
    if has(config, "sasl-ir"):
        request["saslIr"] = config["sasl-ir"]
    if config.get("negotiate"):
        request["authType"] = "negotiate"
    if config.get("service-name"):
        request["serviceName"] = config["service-name"]

    headers.clear_nulls()

    if config.get("data"):
        request["data"] = data_str
        if data_str_reads_file:
            request["dataReadsFile"] = data_str_reads_file
        request["dataArray"] = data
        request["isDataRaw"] = False
        request["isDataBinary"] = any(
            not isinstance(d, Word) and d["filetype"] == "binary" for d in (data or [])
        )
    if query_array:
        request["queryArray"] = query_array

    if has(config, "ipv4"):
        request["ipv4"] = config["ipv4"]
    if has(config, "ipv6"):
        request["ipv6"] = config["ipv6"]

    if config.get("proto"):
        request["proto"] = config["proto"]
    if config.get("proto-redir"):
        request["protoRedir"] = config["proto-redir"]
    if config.get("proto-default"):
        request["protoDefault"] = config["proto-default"]

    if config.get("tcp-fastopen"):
        request["tcpFastopen"] = config["tcp-fastopen"]

    if config.get("local-port"):
        parts = config["local-port"].split("-", 1)
        start = parts[0]
        end = parts[1] if len(parts) > 1 else None
        if end and end.to_bool():
            request["localPort"] = [start, end]
        else:
            request["localPort"] = [config["local-port"], None]

    if has(config, "ignore-content-length"):
        request["ignoreContentLength"] = config["ignore-content-length"]

    if config.get("interface"):
        request["interface"] = config["interface"]

    if config.get("ciphers"):
        request["ciphers"] = config["ciphers"]
    if config.get("curves"):
        request["curves"] = config["curves"]
    if config.get("insecure"):
        request["insecure"] = True
    if has(config, "cert-status"):
        request["certStatus"] = config["cert-status"]
    if config.get("cert"):
        if config["cert"].starts_with("pkcs11:") or not config["cert"].match(_CERT_RE):
            request["cert"] = [config["cert"], None]
        else:
            try:
                colon = config["cert"].search(_CERT_COLON_RE)
            except Exception:
                colon = config["cert"].search(_COLON_RE)
            if colon == -1:
                request["cert"] = [config["cert"], None]
            else:
                cert = config["cert"].slice(0, colon)
                password = config["cert"].slice(colon + 1)
                request["cert"] = [cert, password if password.to_bool() else None]
    if config.get("cert-type"):
        cert_type = config["cert-type"]
        request["certType"] = cert_type
        if cert_type.is_string() and cert_type.to_string().upper() not in (
            "PEM", "DER", "ENG", "P12"
        ):
            warnf(global_, [
                "cert-type-unknown",
                "not supported file type "
                + repr(cert_type.to_string())
                + " for certificate",
            ])
    if config.get("key"):
        request["key"] = config["key"]
    if config.get("key-type"):
        request["keyType"] = config["key-type"]
    if config.get("pass"):
        request["pass"] = config["pass"]
    if config.get("cacert"):
        request["cacert"] = config["cacert"]
    if has(config, "ca-native"):
        request["caNative"] = config["ca-native"]
    if has(config, "ssl-allow-beast"):
        request["sslAllowBeast"] = config["ssl-allow-beast"]
    if config.get("capath"):
        request["capath"] = config["capath"]
    if config.get("crlfile"):
        request["crlfile"] = config["crlfile"]
    if config.get("pinnedpubkey"):
        request["pinnedpubkey"] = config["pinnedpubkey"]
    if config.get("random-file"):
        request["randomFile"] = config["random-file"]
    if config.get("egd-file"):
        request["egdFile"] = config["egd-file"]
    if config.get("hsts"):
        request["hsts"] = config["hsts"]
    if has(config, "alpn"):
        request["alpn"] = config["alpn"]

    if config.get("tlsVersion"):
        request["tlsVersion"] = config["tlsVersion"]
    if config.get("tls-max"):
        request["tlsMax"] = config["tls-max"]
    if config.get("tls13-ciphers"):
        request["tls13Ciphers"] = config["tls13-ciphers"]
    if config.get("tlsauthtype"):
        request["tlsauthtype"] = config["tlsauthtype"]
    if config.get("tlspassword"):
        request["tlspassword"] = config["tlspassword"]
    if config.get("tlsuser"):
        request["tlsuser"] = config["tlsuser"]
    if has(config, "ssl-allow-beast"):
        request["sslAllowBeast"] = config["ssl-allow-beast"]
    if has(config, "ssl-auto-client-cert"):
        request["sslAutoClientCert"] = config["ssl-auto-client-cert"]
    if has(config, "ssl-no-revoke"):
        request["sslNoRevoke"] = config["ssl-no-revoke"]
    if has(config, "ssl-reqd"):
        request["sslReqd"] = config["ssl-reqd"]
    if has(config, "ssl-revoke-best-effort"):
        request["sslRevokeBestEffort"] = config["ssl-revoke-best-effort"]
    if has(config, "ssl"):
        request["ssl"] = config["ssl"]
    if has(config, "sslv2"):
        request["sslv2"] = config["sslv2"]
    if has(config, "sslv3"):
        request["sslv3"] = config["sslv3"]

    if config.get("doh-url"):
        request["dohUrl"] = config["doh-url"]
    if has(config, "doh-insecure"):
        request["dohInsecure"] = config["doh-insecure"]
    if has(config, "doh-cert-status"):
        request["dohCertStatus"] = config["doh-cert-status"]

    if config.get("proxy"):
        request["proxy"] = config["proxy"]
        if request.get("proxyType") and request["proxyType"] != "http2":
            del request["proxyType"]
        if config.get("proxy-user"):
            request["proxyAuth"] = config["proxy-user"]
    if has(config, "proxytunnel"):
        request["proxytunnel"] = config["proxytunnel"]
    if config.get("noproxy"):
        request["noproxy"] = config["noproxy"]
    if config.get("preproxy"):
        request["preproxy"] = config["preproxy"]
    if has(config, "proxy-anyauth"):
        request["proxyAnyauth"] = config["proxy-anyauth"]
    if has(config, "proxy-basic"):
        request["proxyBasic"] = config["proxy-basic"]
    if has(config, "proxy-digest"):
        request["proxyDigest"] = config["proxy-digest"]
    if has(config, "proxy-negotiate"):
        request["proxyNegotiate"] = config["proxy-negotiate"]
    if has(config, "proxy-ntlm"):
        request["proxyNtlm"] = config["proxy-ntlm"]
    if has(config, "proxy-ca-native"):
        request["proxyCaNative"] = config["proxy-ca-native"]
    if config.get("proxy-cacert"):
        request["proxyCacert"] = config["proxy-cacert"]
    if config.get("proxy-capath"):
        request["proxyCapath"] = config["proxy-capath"]
    if config.get("proxy-cert-type"):
        request["proxyCertType"] = config["proxy-cert-type"]
    if config.get("proxy-cert"):
        request["proxyCert"] = config["proxy-cert"]
    if config.get("proxy-ciphers"):
        request["proxyCiphers"] = config["proxy-ciphers"]
    if config.get("proxy-crlfile"):
        request["proxyCrlfile"] = config["proxy-crlfile"]
    if config.get("proxy-http2"):
        request["proxyType"] = "http2"
    if config.get("proxy1.0"):
        request["proxy"] = config["proxy1.0"]
        request["proxyType"] = "http1"
    if has(config, "proxy-insecure"):
        request["proxyInsecure"] = config["proxy-insecure"]
    if config.get("proxy-key"):
        request["proxyKey"] = config["proxy-key"]
    if config.get("proxy-key-type"):
        request["proxyKeyType"] = config["proxy-key-type"]
    if config.get("proxy-pass"):
        request["proxyPass"] = config["proxy-pass"]
    if config.get("proxy-pinnedpubkey"):
        request["proxyPinnedpubkey"] = config["proxy-pinnedpubkey"]
    if config.get("proxy-service-name"):
        request["proxyServiceName"] = config["proxy-service-name"]
    if has(config, "proxy-ssl-allow-beast"):
        request["proxySslAllowBeast"] = config["proxy-ssl-allow-beast"]
    if has(config, "proxy-ssl-auto-client-cert"):
        request["proxySslAutoClientCert"] = config["proxy-ssl-auto-client-cert"]
    if config.get("proxy-tls13-ciphers"):
        request["proxyTls13Ciphers"] = config["proxy-tls13-ciphers"]
    if config.get("proxy-tlsauthtype"):
        request["proxyTlsauthtype"] = config["proxy-tlsauthtype"]
        if request["proxyTlsauthtype"].is_string() and not eq(
            request["proxyTlsauthtype"], "SRP"
        ):
            warnf(global_, [
                "proxy-tlsauthtype",
                "proxy-tlsauthtype is not supported: "
                + request["proxyTlsauthtype"].to_string(),
            ])
    if config.get("proxy-tlspassword"):
        request["proxyTlspassword"] = config["proxy-tlspassword"]
    if config.get("proxy-tlsuser"):
        request["proxyTlsuser"] = config["proxy-tlsuser"]
    if has(config, "proxy-tlsv1"):
        request["proxyTlsv1"] = config["proxy-tlsv1"]
    if config.get("proxy-user"):
        request["proxyUser"] = config["proxy-user"]

    if config.get("socks4"):
        request["proxy"] = config["socks4"]
        request["proxyType"] = "socks4"
    if config.get("socks4a"):
        request["proxy"] = config["socks4a"]
        request["proxyType"] = "socks4a"
    if config.get("socks5"):
        request["proxy"] = config["socks5"]
        request["proxyType"] = "socks5"
    if config.get("socks5-hostname"):
        request["proxy"] = config["socks5-hostname"]
        request["proxyType"] = "socks5-hostname"
    if has(config, "socks5-basic"):
        request["socks5Basic"] = config["socks5-basic"]
    if has(config, "socks5-gssapi-nec"):
        request["socks5GssapiNec"] = config["socks5-gssapi-nec"]
    if config.get("socks5-gssapi-service"):
        request["socks5GssapiService"] = config["socks5-gssapi-service"]
    if has(config, "socks5-gssapi"):
        request["socks5Gssapi"] = config["socks5-gssapi"]

    if config.get("haproxy-clientip"):
        request["haproxyClientIp"] = config["haproxy-clientip"]
    if has(config, "haproxy-protocol"):
        request["haproxyProtocol"] = config["haproxy-protocol"]

    if config.get("max-time"):
        request["timeout"] = config["max-time"]
        if config["max-time"].is_string() and _is_nan(
            _parse_float(config["max-time"].to_string())
        ):
            warnf(global_, [
                "max-time-not-number",
                "option --max-time: expected a proper numerical parameter: "
                + repr(config["max-time"].to_string()),
            ])
    if config.get("connect-timeout"):
        request["connectTimeout"] = config["connect-timeout"]
        if config["connect-timeout"].is_string() and _is_nan(
            _parse_float(config["connect-timeout"].to_string())
        ):
            warnf(global_, [
                "connect-timeout-not-number",
                "option --connect-timeout: expected a proper numerical parameter: "
                + repr(config["connect-timeout"].to_string()),
            ])
    if config.get("expect100-timeout"):
        request["expect100Timeout"] = config["expect100-timeout"]
        if config["expect100-timeout"].is_string() and _is_nan(
            _parse_float(config["expect100-timeout"].to_string())
        ):
            warnf(global_, [
                "expect100-timeout-not-number",
                "option --expect100-timeout: expected a proper numerical parameter: "
                + repr(config["expect100-timeout"].to_string()),
            ])
    if config.get("happy-eyeballs-timeout-ms"):
        request["happyEyeballsTimeoutMs"] = config["happy-eyeballs-timeout-ms"]
    if config.get("speed-limit"):
        request["speedLimit"] = config["speed-limit"]
    if config.get("speed-time"):
        request["speedTime"] = config["speed-time"]
    if config.get("limit-rate"):
        request["limitRate"] = config["limit-rate"]
    if config.get("max-filesize"):
        request["maxFilesize"] = config["max-filesize"]

    if has(config, "keepalive"):
        request["keepAlive"] = config["keepalive"]
    if config.get("keepalive-time"):
        request["keepAliveTime"] = config["keepalive-time"]

    if config.get("alt-svc"):
        request["altSvc"] = config["alt-svc"]

    if has(config, "location"):
        request["followRedirects"] = config["location"]
    if config.get("location-trusted"):
        request["followRedirectsTrusted"] = config["location-trusted"]
    if config.get("max-redirs"):
        request["maxRedirects"] = config["max-redirs"].trim()
        if config["max-redirs"].is_string() and not is_int(
            config["max-redirs"].to_string()
        ):
            warnf(global_, [
                "max-redirs-not-int",
                "option --max-redirs: expected a proper numerical parameter: "
                + repr(config["max-redirs"].to_string()),
            ])
    if has(config, "post301"):
        request["post301"] = config["post301"]
    if has(config, "post302"):
        request["post302"] = config["post302"]
    if has(config, "post303"):
        request["post303"] = config["post303"]

    if config.get("fail"):
        request["fail"] = config["fail"]

    if config.get("retry"):
        request["retry"] = config["retry"]
    if config.get("retry-max-time"):
        request["retryMaxTime"] = config["retry-max-time"]

    if has(config, "ftp-skip-pasv-ip"):
        request["ftpSkipPasvIp"] = config["ftp-skip-pasv-ip"]

    if config.get("httpVersion"):
        if config["httpVersion"] in ("2", "2-prior-knowledge"):
            request["http2"] = True
        if config["httpVersion"] in ("3", "3-only"):
            request["http3"] = True
        request["httpVersion"] = config["httpVersion"]
    if has(config, "http0.9"):
        request["http0_9"] = config["http0.9"]

    if config.get("resolve"):
        request["resolve"] = config["resolve"]
    if config.get("connect-to"):
        request["connectTo"] = config["connect-to"]

    if config.get("unix-socket"):
        request["unixSocket"] = config["unix-socket"]
    if config.get("abstract-unix-socket"):
        request["abstractUnixSocket"] = config["abstract-unix-socket"]

    if config.get("netrc-optional"):
        request["netrc"] = "optional"
    elif config.get("netrc") or config.get("netrc-file"):
        request["netrc"] = "required"
    elif config.get("netrc") is False:
        request["netrc"] = "ignored"
    if config.get("netrc-file"):
        request["netrcFile"] = config["netrc-file"]

    if config.get("use-ascii"):
        request["useAscii"] = config["use-ascii"]

    if config.get("continue-at"):
        request["continueAt"] = config["continue-at"]

    if has(config, "crlf"):
        request["crlf"] = config["crlf"]

    if has(config, "clobber"):
        request["clobber"] = config["clobber"]
    if has(config, "remote-time"):
        request["remoteTime"] = config["remote-time"]

    # 全局选项
    if has(global_, "verbose"):
        request["verbose"] = global_["verbose"]
    if has(global_, "silent"):
        request["silent"] = global_["silent"]

    return request


def build_requests(global_, stdin=None, stdin_file=None):
    if not global_["configs"]:
        warnf(global_, ["no-configs", "got empty config object"])
    return [
        build_request(global_, config, stdin, stdin_file)
        for config in global_["configs"]
    ]


def get_first(requests, warnings, support=None):
    if len(requests) > 1:
        warnings.append([
            "next",
            "got "
            + str(len(requests))
            + " curl requests, only converting the first one",
        ])
    request = requests[0]
    warn_if_parts_ignored(request, warnings, support)
    return request


_NEWLINES = re.compile(r"[\n\r]")
_AUTO_SUFFIX = re.compile(r";auto$")
_CT_PARAM_RE = re.compile(r';\s*([^;=]+)=(?:("[^"]*")|([^()<>@,;:\\"/[\]?.=]*))')
_CERT_RE = re.compile(r"[:\\]")
_CERT_COLON_RE = re.compile(r"(?<!\\)(?:\\\\)*:")
_COLON_RE = re.compile(r":")
