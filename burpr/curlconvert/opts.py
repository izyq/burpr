"""curl 选项解析——移植自 curlconverter 的 curl/opts.ts."""

from burpr.curlconvert.errors import CCError, has
from burpr.curlconvert.warnings_ import warnf, underline_node
from burpr.curlconvert.word import eq, first_shell_token
from burpr.curlconvert.auth import (
    CURLAUTH_BASIC,
    CURLAUTH_DIGEST,
    CURLAUTH_NEGOTIATE,
    CURLAUTH_NTLM,
    CURLAUTH_NTLM_WB,
    CURLAUTH_BEARER,
    CURLAUTH_AWS_SIGV4,
    CURLAUTH_ANY,
)


def _s(name, removed=None, expand=None):
    d = {"type": "string", "name": name}
    if removed is not None:
        d["removed"] = removed
    if expand is not None:
        d["expand"] = expand
    return d


def _b(name, removed=None, expand=None):
    d = {"type": "bool", "name": name}
    if removed is not None:
        d["removed"] = removed
    if expand is not None:
        d["expand"] = expand
    return d


# prettier-ignore
curlLongOpts = {
    # BEGIN EXTRACTED OPTIONS
    "url": _s("url"),
    "dns-ipv4-addr": _s("dns-ipv4-addr"),
    "dns-ipv6-addr": _s("dns-ipv6-addr"),
    "random-file": _s("random-file"),
    "egd-file": _s("egd-file"),
    "oauth2-bearer": _s("oauth2-bearer"),
    "connect-timeout": _s("connect-timeout"),
    "doh-url": _s("doh-url"),
    "ciphers": _s("ciphers"),
    "dns-interface": _s("dns-interface"),
    "disable-epsv": _b("disable-epsv"),
    "no-disable-epsv": _b("disable-epsv", expand=False),
    "disallow-username-in-url": _b("disallow-username-in-url"),
    "no-disallow-username-in-url": _b("disallow-username-in-url", expand=False),
    "epsv": _b("epsv"),
    "no-epsv": _b("epsv", expand=False),
    "dns-servers": _s("dns-servers"),
    "trace": _s("trace"),
    "npn": _b("npn"),
    "no-npn": _b("npn", expand=False),
    "trace-ascii": _s("trace-ascii"),
    "alpn": _b("alpn"),
    "no-alpn": _b("alpn", expand=False),
    "limit-rate": _s("limit-rate"),
    "rate": _s("rate"),
    "compressed": _b("compressed"),
    "no-compressed": _b("compressed", expand=False),
    "tr-encoding": _b("tr-encoding"),
    "no-tr-encoding": _b("tr-encoding", expand=False),
    "digest": _b("digest"),
    "no-digest": _b("digest", expand=False),
    "negotiate": _b("negotiate"),
    "no-negotiate": _b("negotiate", expand=False),
    "ntlm": _b("ntlm"),
    "no-ntlm": _b("ntlm", expand=False),
    "ntlm-wb": _b("ntlm-wb"),
    "no-ntlm-wb": _b("ntlm-wb", expand=False),
    "basic": _b("basic"),
    "no-basic": _b("basic", expand=False),
    "anyauth": _b("anyauth"),
    "no-anyauth": _b("anyauth", expand=False),
    "wdebug": _b("wdebug"),
    "no-wdebug": _b("wdebug", expand=False),
    "ftp-create-dirs": _b("ftp-create-dirs"),
    "no-ftp-create-dirs": _b("ftp-create-dirs", expand=False),
    "create-dirs": _b("create-dirs"),
    "no-create-dirs": _b("create-dirs", expand=False),
    "create-file-mode": _s("create-file-mode"),
    "max-redirs": _s("max-redirs"),
    "proxy-ntlm": _b("proxy-ntlm"),
    "no-proxy-ntlm": _b("proxy-ntlm", expand=False),
    "crlf": _b("crlf"),
    "no-crlf": _b("crlf", expand=False),
    "stderr": _s("stderr"),
    "aws-sigv4": _s("aws-sigv4"),
    "interface": _s("interface"),
    "krb": _s("krb"),
    "krb4": _s("krb"),
    "haproxy-protocol": _b("haproxy-protocol"),
    "no-haproxy-protocol": _b("haproxy-protocol", expand=False),
    "haproxy-clientip": _s("haproxy-clientip"),
    "max-filesize": _s("max-filesize"),
    "disable-eprt": _b("disable-eprt"),
    "no-disable-eprt": _b("disable-eprt", expand=False),
    "eprt": _b("eprt"),
    "no-eprt": _b("eprt", expand=False),
    "xattr": _b("xattr"),
    "no-xattr": _b("xattr", expand=False),
    "ftp-ssl": _b("ssl"),
    "no-ftp-ssl": _b("ssl", expand=False),
    "ssl": _b("ssl"),
    "no-ssl": _b("ssl", expand=False),
    "ftp-pasv": _b("ftp-pasv"),
    "no-ftp-pasv": _b("ftp-pasv", expand=False),
    "socks5": _s("socks5"),
    "tcp-nodelay": _b("tcp-nodelay"),
    "no-tcp-nodelay": _b("tcp-nodelay", expand=False),
    "proxy-digest": _b("proxy-digest"),
    "no-proxy-digest": _b("proxy-digest", expand=False),
    "proxy-basic": _b("proxy-basic"),
    "no-proxy-basic": _b("proxy-basic", expand=False),
    "retry": _s("retry"),
    "retry-connrefused": _b("retry-connrefused"),
    "no-retry-connrefused": _b("retry-connrefused", expand=False),
    "retry-delay": _s("retry-delay"),
    "retry-max-time": _s("retry-max-time"),
    "proxy-negotiate": _b("proxy-negotiate"),
    "no-proxy-negotiate": _b("proxy-negotiate", expand=False),
    "form-escape": _b("form-escape"),
    "no-form-escape": _b("form-escape", expand=False),
    "ftp-account": _s("ftp-account"),
    "proxy-anyauth": _b("proxy-anyauth"),
    "no-proxy-anyauth": _b("proxy-anyauth", expand=False),
    "trace-time": _b("trace-time"),
    "no-trace-time": _b("trace-time", expand=False),
    "ignore-content-length": _b("ignore-content-length"),
    "no-ignore-content-length": _b("ignore-content-length", expand=False),
    "ftp-skip-pasv-ip": _b("ftp-skip-pasv-ip"),
    "no-ftp-skip-pasv-ip": _b("ftp-skip-pasv-ip", expand=False),
    "ftp-method": _s("ftp-method"),
    "local-port": _s("local-port"),
    "socks4": _s("socks4"),
    "socks4a": _s("socks4a"),
    "ftp-alternative-to-user": _s("ftp-alternative-to-user"),
    "ftp-ssl-reqd": _b("ssl-reqd"),
    "no-ftp-ssl-reqd": _b("ssl-reqd", expand=False),
    "ssl-reqd": _b("ssl-reqd"),
    "no-ssl-reqd": _b("ssl-reqd", expand=False),
    "sessionid": _b("sessionid"),
    "no-sessionid": _b("sessionid", expand=False),
    "ftp-ssl-control": _b("ftp-ssl-control"),
    "no-ftp-ssl-control": _b("ftp-ssl-control", expand=False),
    "ftp-ssl-ccc": _b("ftp-ssl-ccc"),
    "no-ftp-ssl-ccc": _b("ftp-ssl-ccc", expand=False),
    "ftp-ssl-ccc-mode": _s("ftp-ssl-ccc-mode"),
    "libcurl": _s("libcurl"),
    "raw": _b("raw"),
    "no-raw": _b("raw", expand=False),
    "post301": _b("post301"),
    "no-post301": _b("post301", expand=False),
    "keepalive": _b("keepalive"),
    "no-keepalive": _b("keepalive", expand=False),
    "socks5-hostname": _s("socks5-hostname"),
    "keepalive-time": _s("keepalive-time"),
    "post302": _b("post302"),
    "no-post302": _b("post302", expand=False),
    "noproxy": _s("noproxy"),
    "socks5-gssapi-nec": _b("socks5-gssapi-nec"),
    "no-socks5-gssapi-nec": _b("socks5-gssapi-nec", expand=False),
    "proxy1.0": _s("proxy1.0"),
    "tftp-blksize": _s("tftp-blksize"),
    "mail-from": _s("mail-from"),
    "mail-rcpt": _s("mail-rcpt"),
    "ftp-pret": _b("ftp-pret"),
    "no-ftp-pret": _b("ftp-pret", expand=False),
    "proto": _s("proto"),
    "proto-redir": _s("proto-redir"),
    "resolve": _s("resolve"),
    "delegation": _s("delegation"),
    "mail-auth": _s("mail-auth"),
    "post303": _b("post303"),
    "no-post303": _b("post303", expand=False),
    "metalink": _b("metalink"),
    "no-metalink": _b("metalink", expand=False),
    "sasl-authzid": _s("sasl-authzid"),
    "sasl-ir": _b("sasl-ir"),
    "no-sasl-ir": _b("sasl-ir", expand=False),
    "test-event": _b("test-event"),
    "no-test-event": _b("test-event", expand=False),
    "unix-socket": _s("unix-socket"),
    "path-as-is": _b("path-as-is"),
    "no-path-as-is": _b("path-as-is", expand=False),
    "socks5-gssapi-service": _s("proxy-service-name"),
    "proxy-service-name": _s("proxy-service-name"),
    "service-name": _s("service-name"),
    "proto-default": _s("proto-default"),
    "expect100-timeout": _s("expect100-timeout"),
    "tftp-no-options": _b("tftp-no-options"),
    "no-tftp-no-options": _b("tftp-no-options", expand=False),
    "connect-to": _s("connect-to"),
    "abstract-unix-socket": _s("abstract-unix-socket"),
    "tls-max": _s("tls-max"),
    "suppress-connect-headers": _b("suppress-connect-headers"),
    "no-suppress-connect-headers": _b("suppress-connect-headers", expand=False),
    "compressed-ssh": _b("compressed-ssh"),
    "no-compressed-ssh": _b("compressed-ssh", expand=False),
    "happy-eyeballs-timeout-ms": _s("happy-eyeballs-timeout-ms"),
    "retry-all-errors": _b("retry-all-errors"),
    "no-retry-all-errors": _b("retry-all-errors", expand=False),
    "trace-ids": _b("trace-ids"),
    "no-trace-ids": _b("trace-ids", expand=False),
    "http1.0": _b("http1.0"),
    "http1.1": _b("http1.1"),
    "http2": _b("http2"),
    "http2-prior-knowledge": _b("http2-prior-knowledge"),
    "http3": _b("http3"),
    "http3-only": _b("http3-only"),
    "http0.9": _b("http0.9"),
    "no-http0.9": _b("http0.9", expand=False),
    "proxy-http2": _b("proxy-http2"),
    "no-proxy-http2": _b("proxy-http2", expand=False),
    "tlsv1": _b("tlsv1"),
    "tlsv1.0": _b("tlsv1.0"),
    "tlsv1.1": _b("tlsv1.1"),
    "tlsv1.2": _b("tlsv1.2"),
    "tlsv1.3": _b("tlsv1.3"),
    "tls13-ciphers": _s("tls13-ciphers"),
    "proxy-tls13-ciphers": _s("proxy-tls13-ciphers"),
    "sslv2": _b("sslv2"),
    "sslv3": _b("sslv3"),
    "ipv4": _b("ipv4"),
    "ipv6": _b("ipv6"),
    "append": _b("append"),
    "no-append": _b("append", expand=False),
    "user-agent": _s("user-agent"),
    "cookie": _s("cookie"),
    "alt-svc": _s("alt-svc"),
    "hsts": _s("hsts"),
    "use-ascii": _b("use-ascii"),
    "no-use-ascii": _b("use-ascii", expand=False),
    "cookie-jar": _s("cookie-jar"),
    "continue-at": _s("continue-at"),
    "data": _s("data"),
    "data-raw": _s("data-raw"),
    "data-ascii": _s("data-ascii"),
    "data-binary": _s("data-binary"),
    "data-urlencode": _s("data-urlencode"),
    "json": _s("json"),
    "url-query": _s("url-query"),
    "dump-header": _s("dump-header"),
    "referer": _s("referer"),
    "cert": _s("cert"),
    "cacert": _s("cacert"),
    "cert-type": _s("cert-type"),
    "key": _s("key"),
    "key-type": _s("key-type"),
    "pass": _s("pass"),
    "engine": _s("engine"),
    "ca-native": _b("ca-native"),
    "no-ca-native": _b("ca-native", expand=False),
    "proxy-ca-native": _b("proxy-ca-native"),
    "no-proxy-ca-native": _b("proxy-ca-native", expand=False),
    "capath": _s("capath"),
    "pubkey": _s("pubkey"),
    "hostpubmd5": _s("hostpubmd5"),
    "hostpubsha256": _s("hostpubsha256"),
    "crlfile": _s("crlfile"),
    "tlsuser": _s("tlsuser"),
    "tlspassword": _s("tlspassword"),
    "tlsauthtype": _s("tlsauthtype"),
    "ssl-allow-beast": _b("ssl-allow-beast"),
    "no-ssl-allow-beast": _b("ssl-allow-beast", expand=False),
    "ssl-auto-client-cert": _b("ssl-auto-client-cert"),
    "no-ssl-auto-client-cert": _b("ssl-auto-client-cert", expand=False),
    "proxy-ssl-auto-client-cert": _b("proxy-ssl-auto-client-cert"),
    "no-proxy-ssl-auto-client-cert": _b("proxy-ssl-auto-client-cert", expand=False),
    "pinnedpubkey": _s("pinnedpubkey"),
    "proxy-pinnedpubkey": _s("proxy-pinnedpubkey"),
    "cert-status": _b("cert-status"),
    "no-cert-status": _b("cert-status", expand=False),
    "doh-cert-status": _b("doh-cert-status"),
    "no-doh-cert-status": _b("doh-cert-status", expand=False),
    "false-start": _b("false-start"),
    "no-false-start": _b("false-start", expand=False),
    "ssl-no-revoke": _b("ssl-no-revoke"),
    "no-ssl-no-revoke": _b("ssl-no-revoke", expand=False),
    "ssl-revoke-best-effort": _b("ssl-revoke-best-effort"),
    "no-ssl-revoke-best-effort": _b("ssl-revoke-best-effort", expand=False),
    "tcp-fastopen": _b("tcp-fastopen"),
    "no-tcp-fastopen": _b("tcp-fastopen", expand=False),
    "proxy-tlsuser": _s("proxy-tlsuser"),
    "proxy-tlspassword": _s("proxy-tlspassword"),
    "proxy-tlsauthtype": _s("proxy-tlsauthtype"),
    "proxy-cert": _s("proxy-cert"),
    "proxy-cert-type": _s("proxy-cert-type"),
    "proxy-key": _s("proxy-key"),
    "proxy-key-type": _s("proxy-key-type"),
    "proxy-pass": _s("proxy-pass"),
    "proxy-ciphers": _s("proxy-ciphers"),
    "proxy-crlfile": _s("proxy-crlfile"),
    "proxy-ssl-allow-beast": _b("proxy-ssl-allow-beast"),
    "no-proxy-ssl-allow-beast": _b("proxy-ssl-allow-beast", expand=False),
    "login-options": _s("login-options"),
    "proxy-cacert": _s("proxy-cacert"),
    "proxy-capath": _s("proxy-capath"),
    "proxy-insecure": _b("proxy-insecure"),
    "no-proxy-insecure": _b("proxy-insecure", expand=False),
    "proxy-tlsv1": _b("proxy-tlsv1"),
    "socks5-basic": _b("socks5-basic"),
    "no-socks5-basic": _b("socks5-basic", expand=False),
    "socks5-gssapi": _b("socks5-gssapi"),
    "no-socks5-gssapi": _b("socks5-gssapi", expand=False),
    "etag-save": _s("etag-save"),
    "etag-compare": _s("etag-compare"),
    "curves": _s("curves"),
    "fail": _b("fail"),
    "no-fail": _b("fail", expand=False),
    "fail-early": _b("fail-early"),
    "no-fail-early": _b("fail-early", expand=False),
    "styled-output": _b("styled-output"),
    "no-styled-output": _b("styled-output", expand=False),
    "mail-rcpt-allowfails": _b("mail-rcpt-allowfails"),
    "no-mail-rcpt-allowfails": _b("mail-rcpt-allowfails", expand=False),
    "fail-with-body": _b("fail-with-body"),
    "no-fail-with-body": _b("fail-with-body", expand=False),
    "remove-on-error": _b("remove-on-error"),
    "no-remove-on-error": _b("remove-on-error", expand=False),
    "form": _s("form"),
    "form-string": _s("form-string"),
    "globoff": _b("globoff"),
    "no-globoff": _b("globoff", expand=False),
    "get": _b("get"),
    "no-get": _b("get", expand=False),
    "request-target": _s("request-target"),
    "help": _b("help"),
    "no-help": _b("help", expand=False),
    "header": _s("header"),
    "proxy-header": _s("proxy-header"),
    "include": _b("include"),
    "no-include": _b("include", expand=False),
    "head": _b("head"),
    "no-head": _b("head", expand=False),
    "junk-session-cookies": _b("junk-session-cookies"),
    "no-junk-session-cookies": _b("junk-session-cookies", expand=False),
    "remote-header-name": _b("remote-header-name"),
    "no-remote-header-name": _b("remote-header-name", expand=False),
    "insecure": _b("insecure"),
    "no-insecure": _b("insecure", expand=False),
    "doh-insecure": _b("doh-insecure"),
    "no-doh-insecure": _b("doh-insecure", expand=False),
    "config": _s("config"),
    "list-only": _b("list-only"),
    "no-list-only": _b("list-only", expand=False),
    "location": _b("location"),
    "no-location": _b("location", expand=False),
    "location-trusted": _b("location-trusted"),
    "no-location-trusted": _b("location-trusted", expand=False),
    "max-time": _s("max-time"),
    "manual": _b("manual"),
    "no-manual": _b("manual", expand=False),
    "netrc": _b("netrc"),
    "no-netrc": _b("netrc", expand=False),
    "netrc-optional": _b("netrc-optional"),
    "no-netrc-optional": _b("netrc-optional", expand=False),
    "netrc-file": _s("netrc-file"),
    "buffer": _b("buffer"),
    "no-buffer": _b("buffer", expand=False),
    "output": _s("output"),
    "remote-name": _b("remote-name"),
    "no-remote-name": _b("remote-name", expand=False),
    "remote-name-all": _b("remote-name-all"),
    "no-remote-name-all": _b("remote-name-all", expand=False),
    "output-dir": _s("output-dir"),
    "clobber": _b("clobber"),
    "no-clobber": _b("clobber", expand=False),
    "proxytunnel": _b("proxytunnel"),
    "no-proxytunnel": _b("proxytunnel", expand=False),
    "ftp-port": _s("ftp-port"),
    "disable": _b("disable"),
    "no-disable": _b("disable", expand=False),
    "quote": _s("quote"),
    "range": _s("range"),
    "remote-time": _b("remote-time"),
    "no-remote-time": _b("remote-time", expand=False),
    "silent": _b("silent"),
    "no-silent": _b("silent", expand=False),
    "show-error": _b("show-error"),
    "no-show-error": _b("show-error", expand=False),
    "telnet-option": _s("telnet-option"),
    "upload-file": _s("upload-file"),
    "user": _s("user"),
    "proxy-user": _s("proxy-user"),
    "verbose": _b("verbose"),
    "no-verbose": _b("verbose", expand=False),
    "version": _b("version"),
    "no-version": _b("version", expand=False),
    "write-out": _s("write-out"),
    "proxy": _s("proxy"),
    "preproxy": _s("preproxy"),
    "request": _s("request"),
    "speed-limit": _s("speed-limit"),
    "speed-time": _s("speed-time"),
    "time-cond": _s("time-cond"),
    "parallel": _b("parallel"),
    "no-parallel": _b("parallel", expand=False),
    "parallel-max": _s("parallel-max"),
    "parallel-immediate": _b("parallel-immediate"),
    "no-parallel-immediate": _b("parallel-immediate", expand=False),
    "progress-bar": _b("progress-bar"),
    "no-progress-bar": _b("progress-bar", expand=False),
    "progress-meter": _b("progress-meter"),
    "no-progress-meter": _b("progress-meter", expand=False),
    "next": _b("next"),
    # END EXTRACTED OPTIONS

    # 这些是 curl 曾经有过的选项。不与现有选项冲突的被 curlconverter 支持。
    "port": _s("port", removed="7.3"),
    "ftp-ascii": _b("use-ascii", removed="7.10.7"),
    "3p-url": _s("3p-url", removed="7.16.0"),
    "3p-user": _s("3p-user", removed="7.16.0"),
    "3p-quote": _s("3p-quote", removed="7.16.0"),
    "http2.0": _b("http2", removed="7.36.0"),
    "no-http2.0": _b("http2", removed="7.36.0"),
    "telnet-options": _s("telnet-option", removed="7.49.0"),
    "http-request": _s("request", removed="7.49.0"),
    "capath ": _s("capath", removed="7.49.0"),  # 尾随空格
    "ftpport": _s("ftp-port", removed="7.49.0"),
    "environment": _b("environment", removed="7.54.1"),
    # 这些从未有过效果
    "no-tlsv1": _b("tlsv1", removed="7.54.1"),
    "no-tlsv1.2": _b("tlsv1.2", removed="7.54.1"),
    "no-http2-prior-knowledge": _b("http2-prior-knowledge", removed="7.54.1"),
    "no-ipv6": _b("ipv6", removed="7.54.1"),
    "no-ipv4": _b("ipv4", removed="7.54.1"),
    "no-sslv2": _b("sslv2", removed="7.54.1"),
    "no-tlsv1.0": _b("tlsv1.0", removed="7.54.1"),
    "no-tlsv1.1": _b("tlsv1.1", removed="7.54.1"),
    "no-sslv3": _b("sslv3", removed="7.54.1"),
    "no-http1.0": _b("http1.0", removed="7.54.1"),
    "no-next": _b("next", removed="7.54.1"),
    "no-tlsv1.3": _b("tlsv1.3", removed="7.54.1"),
    "no-environment": _b("environment", removed="7.54.1"),
    "no-http1.1": _b("http1.1", removed="7.54.1"),
    "no-proxy-tlsv1": _b("proxy-tlsv1", removed="7.54.1"),
    "no-http2": _b("http2", removed="7.54.1"),
}


def _build_shortened():
    # curl 允许不敲完整参数,只要不歧义。--sil 可以,--s 不行。
    shortened = {}
    for opt, val in curlLongOpts.items():
        expand = val.get("expand", True)
        removed = val.get("removed", False)
        if expand and not removed:
            for i in range(1, len(opt)):
                shortened_opt = opt[:i]
                if shortened_opt not in shortened:
                    if shortened_opt not in curlLongOpts:
                        shortened[shortened_opt] = val
                else:
                    # 多个选项缩到同一个前缀 → 歧义
                    shortened[shortened_opt] = None
    return shortened


curlLongOptsShortened = _build_shortened()

# 所有 generator 都支持的参数,因为容易实现,或由上游代码处理。
COMMON_SUPPORTED_ARGS = [
    "url",
    "proto-default",
    # 控制反斜杠转义的 [] {} 是否会去掉反斜杠
    "globoff",
    # URL 中若含认证信息 curl 会退出,我们从 URL 移除并告警
    "disallow-username-in-url",
    # Method
    "request",
    "get",
    "head",
    "no-head",
    # Headers
    "header",
    "user-agent",
    "referer",
    "range",
    "time-cond",
    "cookie",
    "oauth2-bearer",
    # Basic Auth
    "user",
    "basic",
    "no-basic",
    # Data
    "data",
    "data-raw",
    "data-ascii",
    "data-binary",
    "data-urlencode",
    "json",
    "url-query",
]


def to_boolean(opt: str) -> bool:
    if opt.startswith("no-disable-"):
        return True
    if opt.startswith("disable-") or opt.startswith("no-"):
        return False
    return True


# prettier-ignore
curlShortOpts = {
    # BEGIN EXTRACTED SHORT OPTIONS
    "0": "http1.0",
    "1": "tlsv1",
    "2": "sslv2",
    "3": "sslv3",
    "4": "ipv4",
    "6": "ipv6",
    "a": "append",
    "A": "user-agent",
    "b": "cookie",
    "B": "use-ascii",
    "c": "cookie-jar",
    "C": "continue-at",
    "d": "data",
    "D": "dump-header",
    "e": "referer",
    "E": "cert",
    "f": "fail",
    "F": "form",
    "g": "globoff",
    "G": "get",
    "h": "help",
    "H": "header",
    "i": "include",
    "I": "head",
    "j": "junk-session-cookies",
    "J": "remote-header-name",
    "k": "insecure",
    "K": "config",
    "l": "list-only",
    "L": "location",
    "m": "max-time",
    "M": "manual",
    "n": "netrc",
    "N": "no-buffer",
    "o": "output",
    "O": "remote-name",
    "p": "proxytunnel",
    "P": "ftp-port",
    "q": "disable",
    "Q": "quote",
    "r": "range",
    "R": "remote-time",
    "s": "silent",
    "S": "show-error",
    "t": "telnet-option",
    "T": "upload-file",
    "u": "user",
    "U": "proxy-user",
    "v": "verbose",
    "V": "version",
    "w": "write-out",
    "x": "proxy",
    "X": "request",
    "Y": "speed-limit",
    "y": "speed-time",
    "z": "time-cond",
    "Z": "parallel",
    "#": "progress-bar",
    ":": "next",
    # END EXTRACTED SHORT OPTIONS
}

changedShortOpts = {
    "p": "used to be short for --port <port> (a since-deleted flag) until curl 7.3",
    "t": "used to be short for --upload (a since-deleted boolean flag) until curl 7.7",
    "c": "used to be short for --continue (a since-deleted boolean flag) until curl 7.9",
    "@": "used to be short for --create-dirs until curl 7.10.7",
    "Z": "used to be short for --max-redirs <num> until curl 7.10.7",
    "9": "used to be short for --crlf until curl 7.10.8",
    "8": "used to be short for --stderr <file> until curl 7.10.8",
    "7": "used to be short for --interface <name> until curl 7.10.8",
    "6": "used to be short for --krb <level> (which itself used to be --krb4 <level>) until curl 7.10.8",
    "5": "used to be another way to specify the url until curl 7.10.8",
    "*": "used to be another way to specify the url until curl 7.49.0",
    "~": "used to be short for --xattr until curl 7.49.0",
}

# 这些选项可以指定多次,总是以列表返回。
# 其它选项若指定多次,curl 用最后一个。
canBeList = {
    "connect-to",
    "cookie",
    "data",
    "form",
    "header",
    "hsts",
    "mail-rcpt",
    "output",
    "proxy-header",
    "quote",
    "resolve",
    "telnet-option",
    "upload-file",
    "url-query",
    "url",
}


def check_supported(global_, lookup, long_arg, supported_opts=None):
    if supported_opts is not None and long_arg["name"] not in supported_opts:
        warnf(global_, [
            long_arg["name"],
            lookup
            + " is not a supported option"
            + (", it was removed in curl " + long_arg["removed"]
               if long_arg.get("removed") else ""),
        ])


def push_prop(obj, prop, value):
    if prop not in obj:
        obj[prop] = []
    obj[prop].append(value)
    return obj


def push_arg_value(global_, config, arg_name, value):
    if arg_name in ("data", "data-ascii"):
        return push_prop(config, "data", ["data", value])
    if arg_name == "data-binary":
        # 除非是文件,--data-binary 与 --data 行为相同
        return push_prop(config, "data", [
            "binary" if value.starts_with("@") else "data", value])
    if arg_name == "data-raw":
        # 除非是文件,--data-raw 与 --data 行为相同
        return push_prop(config, "data", [
            "raw" if value.starts_with("@") else "data", value])
    if arg_name == "data-urlencode":
        return push_prop(config, "data", ["urlencode", value])
    if arg_name == "json":
        config["json"] = True
        return push_prop(config, "data", ["json", value])
    if arg_name == "url-query":
        if value.starts_with("+"):
            return push_prop(config, "url-query", ["raw", value.slice(1)])
        return push_prop(config, "url-query", ["urlencode", value])
    if arg_name == "form":
        return push_prop(config, "form", {"value": value, "type": "form"})
    if arg_name == "form-string":
        return push_prop(config, "form", {"value": value, "type": "string"})
    if arg_name == "aws-sigv4":
        config["authtype"] |= CURLAUTH_AWS_SIGV4
    elif arg_name == "oauth2-bearer":
        config["authtype"] |= CURLAUTH_BEARER
    elif arg_name in ("unix-socket", "abstract-unix-socket"):
        # 忽略区别
        push_prop(config, "unix-socket", value)
    elif arg_name in ("trace", "trace-ascii", "stderr", "libcurl", "config",
                      "parallel-max"):
        global_[arg_name] = value
    elif arg_name == "language":  # --language 是 curlconverter 特有选项
        global_[arg_name] = value.to_string()
        return config

    return push_prop(config, arg_name, value)


def set_arg_value(global_, config, arg_name, toggle):
    if arg_name == "digest":
        config["authtype"] = (config["authtype"] | CURLAUTH_DIGEST) if toggle \
            else (config["authtype"] & ~CURLAUTH_DIGEST)
    elif arg_name == "proxy-digest":
        config["proxyauthtype"] = (config["proxyauthtype"] | CURLAUTH_DIGEST) \
            if toggle else (config["proxyauthtype"] & ~CURLAUTH_DIGEST)
    elif arg_name == "negotiate":
        config["authtype"] = (config["authtype"] | CURLAUTH_NEGOTIATE) if toggle \
            else (config["authtype"] & ~CURLAUTH_NEGOTIATE)
    elif arg_name == "proxy-negotiate":
        config["proxyauthtype"] = (config["proxyauthtype"] | CURLAUTH_NEGOTIATE) \
            if toggle else (config["proxyauthtype"] & ~CURLAUTH_NEGOTIATE)
    elif arg_name == "ntlm":
        config["authtype"] = (config["authtype"] | CURLAUTH_NTLM) if toggle \
            else (config["authtype"] & ~CURLAUTH_NTLM)
    elif arg_name == "proxy-ntlm":
        config["proxyauthtype"] = (config["proxyauthtype"] | CURLAUTH_NTLM) \
            if toggle else (config["proxyauthtype"] & ~CURLAUTH_NTLM)
    elif arg_name == "ntlm-wb":
        config["authtype"] = (config["authtype"] | CURLAUTH_NTLM_WB) if toggle \
            else (config["authtype"] & ~CURLAUTH_NTLM_WB)
    elif arg_name == "basic":
        config["authtype"] = (config["authtype"] | CURLAUTH_BASIC) if toggle \
            else (config["authtype"] & ~CURLAUTH_BASIC)
    elif arg_name == "proxy-basic":
        config["proxyauthtype"] = (config["proxyauthtype"] | CURLAUTH_BASIC) \
            if toggle else (config["proxyauthtype"] & ~CURLAUTH_BASIC)
    elif arg_name == "anyauth":
        if toggle:
            config["authtype"] = CURLAUTH_ANY
    elif arg_name == "proxy-anyauth":
        if toggle:
            config["proxyauthtype"] = CURLAUTH_ANY
    elif arg_name == "location":
        config["location"] = toggle
    elif arg_name == "location-trusted":
        config["location"] = toggle
        config["location-trusted"] = toggle
    elif arg_name == "http1.0":
        config["httpVersion"] = "1.0"
    elif arg_name == "http1.1":
        config["httpVersion"] = "1.1"
    elif arg_name == "http2":
        config["httpVersion"] = "2"
    elif arg_name == "http2-prior-knowledge":
        config["httpVersion"] = "2-prior-knowledge"
    elif arg_name == "http3":
        config["httpVersion"] = "3"
    elif arg_name == "http3-only":
        config["httpVersion"] = "3-only"
    elif arg_name == "tlsv1":
        config["tlsVersion"] = "1"
    elif arg_name == "tlsv1.0":
        config["tlsVersion"] = "1.0"
    elif arg_name == "tlsv1.1":
        config["tlsVersion"] = "1.1"
    elif arg_name == "tlsv1.2":
        config["tlsVersion"] = "1.2"
    elif arg_name == "tlsv1.3":
        config["tlsVersion"] = "1.3"
    elif arg_name in ("verbose", "version", "trace-time", "test-event",
                      "progress-bar", "progress-meter", "fail-early",
                      "styled-output", "help", "silent", "show-error",
                      "parallel", "parallel-immediate", "stdin"):
        global_[arg_name] = toggle
    elif arg_name == "next":
        # 若最后一个 url 节点没有 url,curl 会忽略 --next
        if (toggle and config.get("url") and len(config["url"]) > 0
                and len(config["url"]) >= len(config.get("upload-file", []))
                and len(config["url"]) >= len(config.get("output", []))):
            config = {"authtype": CURLAUTH_BASIC, "proxyauthtype": CURLAUTH_BASIC}
            global_["configs"].append(config)
    else:
        config[arg_name] = toggle
    return config


def parse_args(args, long_opts=None, shortened_long_opts=None, short_opts=None,
               supported_opts=None, warnings=None):
    if long_opts is None:
        long_opts = curlLongOpts
    if shortened_long_opts is None:
        shortened_long_opts = curlLongOptsShortened
    if short_opts is None:
        short_opts = curlShortOpts
    if warnings is None:
        warnings = []

    config = {"authtype": CURLAUTH_BASIC, "proxyauthtype": CURLAUTH_BASIC}
    global_ = {"configs": [config], "warnings": warnings}
    seen = []

    i = 1
    stillflags = True
    while i < len(args):
        arg = args[i]
        if stillflags and arg.starts_with("-"):
            if eq(arg, "--"):
                # 表示 flags 结束,后续(URL)参数可以 - 开头
                stillflags = False
            elif arg.starts_with("--"):
                shell_token = first_shell_token(arg)
                if shell_token:
                    raise CCError(
                        "this "
                        + shell_token.type
                        + " could "
                        + ("return" if shell_token.type == "command" else "be")
                        + " anything\n"
                        + underline_node(shell_token.syntax_node)
                    )
                arg_str = arg.to_string()
                lookup = arg_str[2:]
                long_arg = shortened_long_opts.get(lookup, "undefined")
                if long_arg == "undefined":
                    long_arg = long_opts.get(lookup, "undefined")

                if long_arg is None:
                    raise CCError("option " + arg_str + ": is ambiguous")
                if long_arg == "undefined":
                    raise CCError("option " + arg_str + ": is unknown")

                if long_arg["type"] == "string":
                    i += 1
                    if i >= len(args):
                        raise CCError("option " + arg_str + ": requires parameter")
                    push_arg_value(global_, config, long_arg["name"], args[i])
                else:
                    config = set_arg_value(
                        global_, config, long_arg["name"], to_boolean(arg_str[2:])
                    )
                check_supported(global_, arg_str, long_arg, supported_opts)
                seen.append([long_arg["name"], arg_str])
            else:
                # 短选项。形如:
                # -X POST    -> {request: 'POST'}
                # -XPOST     -> {request: 'POST'}
                # -ABCX POST -> {A: true, B: true, C: true, request: 'POST'}
                # -ABCXPOST  -> {A: true, ..., request: 'POST'}

                # "-" 作为参数传给 curl 会报错;curlconverter 命令行用它读 stdin
                if arg.length == 1:
                    if has(short_opts, ""):
                        short_for = short_opts[""]
                        long_arg = long_opts[short_for]
                        if long_arg is None:
                            raise CCError("option -: is unknown")
                        config = set_arg_value(
                            global_, config, long_arg["name"], to_boolean(short_for)
                        )
                        seen.append([long_arg["name"], "-"])
                    else:
                        raise CCError("option -: is unknown")

                j = 1
                while j < arg.length:
                    jth_char = arg.get(j)
                    if not isinstance(jth_char, str):
                        # 短选项中间的 bash 变量
                        raise CCError(
                            "this "
                            + jth_char.type
                            + " could "
                            + ("return" if jth_char.type == "command" else "be")
                            + " anything\n"
                            + underline_node(jth_char.syntax_node)
                        )
                    if not has(short_opts, jth_char):
                        if has(changedShortOpts, jth_char):
                            raise CCError(
                                "option " + arg.to_string() + ": "
                                + changedShortOpts[jth_char]
                            )
                        raise CCError("option " + arg.to_string() + ": is unknown")
                    lookup = jth_char
                    short_for = short_opts[lookup]
                    long_arg = long_opts[short_for]
                    if long_arg is None:
                        raise CCError("ambiguous short option -" + jth_char)
                    if long_arg["type"] == "string":
                        if j + 1 < arg.length:
                            # -XPOST 视为 -X POST
                            val = arg.slice(j + 1)
                            j = arg.length
                        elif i + 1 < len(args):
                            i += 1
                            val = args[i]
                        else:
                            raise CCError(
                                "option " + arg.to_string() + ": requires parameter"
                            )
                        push_arg_value(global_, config, long_arg["name"], val)
                    else:
                        # 用 shortFor,因为 -N 是 --no-buffer 的缩写,
                        # 我们要得到 {buffer: false}
                        config = set_arg_value(
                            global_, config, long_arg["name"], to_boolean(short_for)
                        )
                    if lookup:
                        check_supported(global_, "-" + lookup, long_arg, supported_opts)
                        seen.append([long_arg["name"], "-" + lookup])
                    j += 1
        else:
            if (not isinstance(arg, str) and arg.tokens
                    and not isinstance(arg.tokens[0], str)):
                is_or_begins = "is" if len(arg.tokens) == 1 else "begins with"
                warnings.append([
                    "ambiguous argument",
                    "argument "
                    + is_or_begins
                    + " a "
                    + arg.tokens[0].type
                    + ", assuming it's a URL\n"
                    + underline_node(arg.tokens[0].syntax_node),
                ])
            push_arg_value(global_, config, "url", arg)
            seen.append(["url", "--url"])
        i += 1

    for cfg in global_["configs"]:
        for arg_name in list(cfg.keys()):
            values = cfg[arg_name]
            if isinstance(values, list) and arg_name not in canBeList:
                cfg[arg_name] = values[-1]
    return global_, seen
