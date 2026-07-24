"""Word——移植自 curlconverter 的 shell/Word.ts.

Word 表现得像字符串,但它是字符列表,其中某些"字符"可以是 shell 变量或表达式。
实现形如:["foobar", ShellToken(type="variable", value="baz", text="$baz"), "qux"]。
除空字符串 [""] 外,列表中不应有空字符串。

注意:JS 字符串按 UTF-16 code unit 索引,Python 按 code point 索引。仅当文本含
非 BMP 字符(如 emoji)时,length/get/slice 的下标语义会有差异;curl 命令场景
基本不会遇到,此处采用 Python 的 code point 语义。
"""

from burpr.curlconvert.errors import CCError


class ShellToken:
    """shell 变量或命令替换 token.

    type: "variable" | "command"
    value: 变量名/命令内容
    text: 原始源码文本(含 $ 等)
    syntax_node: tree-sitter 节点,用于报错定位(可为 None)
    """

    __slots__ = ("type", "value", "text", "syntax_node")

    def __init__(self, type: str, value: str, text: str, syntax_node=None):
        self.type = type
        self.value = value
        self.text = text
        self.syntax_node = syntax_node

    def __repr__(self):
        return f"ShellToken(type={self.type!r}, value={self.value!r}, text={self.text!r})"


# Token = str | ShellToken(用 isinstance(t, str) 区分)


class Word:
    """可迭代的 token 列表,行为类似字符串."""

    __slots__ = ("tokens",)

    def __init__(self, tokens=None):
        # tokens: str | list[Token] | None
        if isinstance(tokens, str):
            tokens = [tokens]
        if tokens is None or len(tokens) == 0:
            tokens = [""]

        self.tokens = []
        for t in tokens:
            if isinstance(t, str):
                if self.tokens and isinstance(self.tokens[-1], str):
                    # 连续两个字符合并
                    self.tokens[-1] += t
                elif t:
                    # 跳过空字符串
                    self.tokens.append(t)
            else:
                self.tokens.append(t)
        if not self.tokens:
            self.tokens.append("")

    @property
    def length(self) -> int:
        length = 0
        for t in self.tokens:
            length += len(t) if isinstance(t, str) else 1
        return length

    def __iter__(self):
        for t in self.tokens:
            if isinstance(t, str):
                yield from t
            else:
                yield t

    def get(self, index: int):
        i = 0
        for t in self.tokens:
            if isinstance(t, str):
                if i + len(t) > index:
                    return t[index - i]
                i += len(t)
            else:
                if i == index:
                    return t
                i += 1
        raise CCError("Index out of bounds")

    def char_at(self, index: int = 0):
        try:
            return self.get(index)
        except CCError:
            return ""

    def index_of(self, search: str, start: int = None) -> int:
        if start is None:
            start = 0
        i = 0
        for t in self.tokens:
            if isinstance(t, str):
                if i + len(t) > start:
                    index = t.find(search, start - i)
                    if index != -1:
                        return i + index
                i += len(t)
            else:
                i += 1
        return -1

    def index_of_first_char(self, search: str) -> int:
        """类似 index_of,但接受一串字符,返回其中任意字符首次出现的位置."""
        i = 0
        for t in self.tokens:
            if isinstance(t, str):
                for c in t:
                    if c in search:
                        return i
                    i += 1
            else:
                i += 1
        return -1

    def remove_first_char(self, c: str) -> "Word":
        if self.length == 0:
            return Word()
        if self.char_at(0) == c:
            return self.slice(1)
        return self.copy()

    def copy(self) -> "Word":
        return Word(list(self.tokens))

    def slice(self, index_start: int = None, index_end: int = None) -> "Word":
        if index_start is None:
            index_start = self.length
        if index_end is None:
            index_end = self.length
        if index_start >= self.length:
            return Word()
        if index_start < 0:
            index_start = max(index_start + self.length, 0)
        if index_end < 0:
            index_end = max(index_end + self.length, 0)
        if index_end <= index_start:
            return Word()

        ret = []
        i = 0
        for t in self.tokens:
            if isinstance(t, str):
                if i + len(t) > index_start:
                    if i < index_end:
                        ret.append(t[max(index_start - i, 0):index_end - i])
                i += len(t)
            else:
                if index_start <= i < index_end:
                    ret.append(t)
                i += 1
        return Word(ret)

    def includes(self, search: str, start: int = None) -> bool:
        if start is None:
            start = 0
        i = 0
        for t in self.tokens:
            if isinstance(t, str):
                if i + len(t) > start:
                    if search in t[start - i:]:
                        return True
                i += len(t)
            else:
                i += 1
        return False

    def test(self, pattern) -> bool:
        """pattern 是编译后的正则,逐字符串 token 测试."""
        for t in self.tokens:
            if isinstance(t, str) and pattern.search(t):
                return True
        return False

    def prepend(self, c: str) -> "Word":
        ret = self.copy()
        if ret.tokens and isinstance(ret.tokens[0], str):
            ret.tokens[0] = c + ret.tokens[0]
        else:
            ret.tokens.insert(0, c)
        return ret

    def append(self, c: str) -> "Word":
        ret = self.copy()
        if ret.tokens and isinstance(ret.tokens[-1], str):
            ret.tokens[-1] += c
        else:
            ret.tokens.append(c)
        return ret

    def add(self, other: "Word") -> "Word":
        """合并两个 Word."""
        return Word(self.tokens + other.tokens)

    def match(self, pattern):
        """返回首个匹配,逐字符串 token 独立搜索."""
        for t in self.tokens:
            if isinstance(t, str):
                m = pattern.search(t)
                if m:
                    return m
        return None

    def search(self, pattern) -> int:
        offset = 0
        for t in self.tokens:
            if isinstance(t, str):
                m = pattern.search(t)
                if m:
                    return offset + m.start()
                offset += len(t)
        return -1

    def replace(self, pattern, replacement: str) -> "Word":
        """逐字符串 token 替换,不会跨 shell 变量."""
        ret = []
        for t in self.tokens:
            if isinstance(t, str):
                if isinstance(pattern, str):
                    # 字符串替换:仅首个(JS 的 String.replace(string, ...))
                    ret.append(t.replace(pattern, replacement, 1))
                else:
                    # 编译正则:替换全部(JS 带 g flag)
                    ret.append(pattern.sub(replacement, t))
            else:
                ret.append(t)
        return Word(ret)

    def split(self, separator: str, limit: int = None) -> list:
        """正确切分(不像 str.split)。末段在达到 limit 时可含分隔符."""
        ret = []
        i = 0
        start = 0
        while i < self.length:
            match = True
            for j in range(len(separator)):
                if self.get(i + j) != separator[j]:
                    match = False
                    break
            if match:
                ret.append(self.slice(start, i))
                i += len(separator)
                start = i
                if limit is not None and len(ret) == limit - 1:
                    break
            else:
                i += 1
        if start <= self.length:
            ret.append(self.slice(start))
        return ret

    def to_lower_case(self) -> "Word":
        return Word([t.lower() if isinstance(t, str) else t for t in self.tokens])

    def to_upper_case(self) -> "Word":
        return Word([t.upper() if isinstance(t, str) else t for t in self.tokens])

    def trim_start(self) -> "Word":
        ret = []
        for i, t in enumerate(self.tokens):
            if isinstance(t, str):
                if i == 0:
                    t = t.lstrip()
                if t:
                    ret.append(t)
            else:
                ret.append(t)
        if not ret:
            return Word()
        return Word(ret)

    def trim_end(self) -> "Word":
        ret = []
        last = len(self.tokens) - 1
        for i, t in enumerate(self.tokens):
            if isinstance(t, str):
                if i == last:
                    t = t.rstrip()
                if t:
                    ret.append(t)
            else:
                ret.append(t)
        if not ret:
            return Word()
        return Word(ret)

    def trim(self) -> "Word":
        ret = []
        last = len(self.tokens) - 1
        for i, t in enumerate(self.tokens):
            if isinstance(t, str):
                if i == 0:
                    t = t.lstrip()
                if i == last:
                    t = t.rstrip()
                if t:
                    ret.append(t)
            else:
                ret.append(t)
        if not ret:
            return Word()
        return Word(ret)

    def is_empty(self) -> bool:
        if not self.tokens:
            return True
        if len(self.tokens) == 1 and isinstance(self.tokens[0], str):
            return len(self.tokens[0]) == 0
        return False

    def to_bool(self) -> bool:
        return not self.is_empty()

    def is_string(self) -> bool:
        """tokens 不含变量/命令则返回 True."""
        return all(isinstance(t, str) for t in self.tokens)

    def first_shell_token(self):
        for t in self.tokens:
            if not isinstance(t, str):
                return t
        return None

    def starts_with(self, prefix: str) -> bool:
        if not self.tokens:
            return False
        if isinstance(self.tokens[0], str):
            return self.tokens[0].startswith(prefix)
        return False

    def ends_with(self, suffix: str) -> bool:
        if not self.tokens:
            return False
        last = self.tokens[-1]
        if isinstance(last, str):
            return last.endswith(suffix)
        return False

    def to_string(self) -> str:
        """丢失原始 token 化信息,拼成字符串."""
        return "".join(t if isinstance(t, str) else t.text for t in self.tokens)

    def __str__(self):
        return self.to_string()

    def __repr__(self):
        return f"Word({self.to_string()!r})"


def eq(it, other) -> bool:
    """判断 Word 与 str/Word/None 是否相等(可为 None)."""
    if it is None or other is None:
        return it is other
    if isinstance(other, str):
        return (
            len(it.tokens) == 1
            and isinstance(it.tokens[0], str)
            and it.tokens[0] == other
        )
    if len(it.tokens) != len(other.tokens):
        return False
    for it_token, other_token in zip(it.tokens, other.tokens):
        if isinstance(it_token, str):
            if it_token != other_token:
                return False
        elif not isinstance(other_token, str):
            if it_token.text != other_token.text:
                return False
        else:
            return False
    return True


def first_shell_token(word):
    """word 可为 str 或 Word;str 返回 None."""
    if isinstance(word, str):
        return None
    return word.first_shell_token()


def merge_words(*words) -> Word:
    ret = []
    for w in words:
        if isinstance(w, Word):
            ret.extend(w.tokens)
        else:
            ret.append(w)
    return Word(ret)


def join_words(words, join_char: str) -> Word:
    ret = []
    for w in words:
        if ret:
            ret.append(join_char)
        ret.extend(w.tokens)
    return Word(ret)
