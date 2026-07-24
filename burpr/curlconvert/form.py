"""multipart 表单解析——移植自 curlconverter 的 curl/form.ts.

-F 是个复杂的选项。https://github.com/curl/curl/blob/curl-7_88_1/src/tool_formparse.c
"""

from burpr.curlconvert.errors import CCError
from burpr.curlconvert.word import Word, eq


def _is_space(c) -> bool:
    """对应 curl 的 ISBLANK/ISSPACE 宏."""
    return isinstance(c, str) and (c in (" ", "\t") or "\n" <= c <= "\r")


def _parse_details(form_param, p: Word, ptr: int, supported: dict, warnings: list):
    while ptr < p.length and p.char_at(ptr) == ";":
        ptr += 1
        while ptr < p.length and _is_space(p.char_at(ptr)):
            ptr += 1
        if ptr >= p.length:
            return form_param

        value = p.slice(ptr)
        if value.starts_with("type="):
            form_param["contentType"], ptr = _get_param_word(p, ptr + 5, warnings)
        elif value.starts_with("filename="):
            filename, filename_end = _get_param_word(p, ptr + 9, warnings)
            ptr = filename_end
            if supported.get("filename"):
                form_param["filename"] = filename
            else:
                warnings.append([
                    "unsupported-form-detail",
                    "Field file name not allowed here: " + filename.to_string(),
                ])
        elif value.starts_with("encoder="):
            encoder, encoder_end = _get_param_word(p, ptr + 8, warnings)
            ptr = encoder_end
            if supported.get("encoder"):
                form_param["encoder"] = encoder
            else:
                warnings.append([
                    "unsupported-form-detail",
                    "Field encoder not allowed here: " + encoder.to_string(),
                ])
        elif value.starts_with("headers="):
            headers, headers_end = _get_param_word(p, ptr + 8, warnings)
            ptr = headers_end
            if supported.get("headers"):
                if headers.starts_with("@"):
                    form_param.setdefault("headerFiles", []).append(headers.slice(1))
                else:
                    form_param.setdefault("headers", []).append(headers)
            else:
                warnings.append([
                    "unsupported-form-detail",
                    "Field headers not allowed here: " + headers.to_string(),
                ])
        else:
            _, unknown_end = _get_param_word(p, ptr, warnings)
            ptr = unknown_end
            warnings.append([
                "unknown-form-detail",
                "skip unknown form field: " + value.to_string(),
            ])
    return form_param


def _get_param_word(p: Word, start: int, warnings: list):
    ptr = start
    if p.char_at(ptr) == '"':
        ptr += 1
        parts = []
        while ptr < p.length:
            cur_char = p.char_at(ptr)
            if cur_char == "\\":
                if ptr + 1 < p.length:
                    next_char = p.char_at(ptr + 1)
                    if next_char in ('"', "\\"):
                        ptr += 1
                        cur_char = p.char_at(ptr)
            elif cur_char == '"':
                ptr += 1
                trailing_data = False
                while ptr < p.length and p.char_at(ptr) != ";":
                    if not _is_space(p.char_at(ptr)):
                        trailing_data = True
                    ptr += 1
                if trailing_data:
                    warnings.append([
                        "trailing-form-data",
                        "Trailing data after quoted form parameter",
                    ])
                return Word(parts), ptr
            parts.append(cur_char)
            ptr += 1

    sep_idx = p.index_of(";", start)
    if sep_idx == -1:
        sep_idx = p.length
    return p.slice(start, sep_idx), sep_idx


def _get_param_part(form_param, p: Word, ptr: int, supported: dict, warnings: list):
    while ptr < p.length and _is_space(p.char_at(ptr)):
        ptr += 1
    content, content_end = _get_param_word(p, ptr, warnings)
    form_param["content"] = content
    _parse_details(form_param, p, content_end, supported, warnings)
    return form_param


def parse_form(form, warnings: list) -> list:
    multipart_uploads = []
    depth = 0
    for multipart_argument in form:
        is_string = multipart_argument["type"] == "string"
        value_word = multipart_argument["value"]

        if not value_word.includes("="):
            raise CCError(
                'invalid value for --form/-F, missing "=": '
                + repr(value_word.to_string())
            )
        name, value = value_word.split("=", 2)
        form_param = {"name": name}

        if not is_string and value.char_at(0) == "(":
            depth += 1
            warnings.append([
                "nested-form",
                'Nested form data with "=(" is not supported, it will be flattened',
            ])
            _get_param_part(form_param, value, 1, {"headers": True}, warnings)
        elif not is_string and name.length == 0 and eq(value, ")"):
            depth -= 1
            if depth < 0:
                raise CCError(
                    "no multipart to terminate: " + repr(value_word.to_string())
                )
        elif not is_string and value.char_at(0) == "@":
            # TODO: 可以有多个文件,逗号分隔
            _get_param_part(
                form_param, value, 1,
                {"filename": True, "encoder": True, "headers": True}, warnings,
            )
            form_param["contentFile"] = form_param.pop("content")
            if form_param.get("filename") is None:
                form_param["filename"] = form_param["contentFile"]
        elif not is_string and value.char_at(0) == "<":
            _get_param_part(
                form_param, value, 1,
                {"encoder": True, "headers": True}, warnings,
            )
            form_param["contentFile"] = form_param.pop("content")
        else:
            if is_string:
                form_param["content"] = value
            else:
                _get_param_part(
                    form_param, value, 0,
                    {"filename": True, "encoder": True, "headers": True}, warnings,
                )
        multipart_uploads.append(form_param)
    return multipart_uploads
