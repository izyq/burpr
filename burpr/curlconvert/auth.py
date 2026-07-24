"""认证类型——移植自 curlconverter 的 curl/auth.ts."""

CURLAUTH_BASIC = 1 << 0
CURLAUTH_DIGEST = 1 << 1
CURLAUTH_NEGOTIATE = 1 << 2
CURLAUTH_NTLM = 1 << 3
CURLAUTH_DIGEST_IE = 1 << 4
CURLAUTH_NTLM_WB = 1 << 5
CURLAUTH_BEARER = 1 << 6
CURLAUTH_AWS_SIGV4 = 1 << 7
CURLAUTH_ANY = ~CURLAUTH_DIGEST_IE


def pick_auth(mask: int) -> str:
    """对应 https://github.com/curl/curl/blob/curl-7_86_0/lib/http.c#L455."""
    if mask == CURLAUTH_ANY:
        return "basic"

    auths = [
        (CURLAUTH_NEGOTIATE, "negotiate"),
        (CURLAUTH_BEARER, "bearer"),
        (CURLAUTH_DIGEST, "digest"),
        (CURLAUTH_NTLM, "ntlm"),
        (CURLAUTH_NTLM_WB, "ntlm-wb"),
        (CURLAUTH_BASIC, "basic"),
        # 该检查在函数外进行,因为显然不需要 --no-basic 来使用 aws-sigv4
        (CURLAUTH_AWS_SIGV4, "aws-sigv4"),
    ]
    for auth, auth_name in auths:
        if mask & auth:
            return auth_name
    return "none"
