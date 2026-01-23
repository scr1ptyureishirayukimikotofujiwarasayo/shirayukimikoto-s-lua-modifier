import re

TOKEN_TYPES = [
    "KEYWORD", "IDENTIFIER", "NUMBER", "STRING",
    "COMMENT", "OPERATOR", "PUNCT", "WHITESPACE",
    "UNKNOWN"
]

KEYWORDS = {
    "and","break","do","else","elseif","end","false","for","function",
    "if","in","local","nil","not","or","repeat","return","then","true",
    "until","while",

    # Roblox Luau extras
    "continue","typeof","export","import"
}

OPERATORS = {
    "+","-","*","/","%","^","#","==","~=","<=",">=","<",">","=",
    "(",")","{","}","[","]",";",":",",",".","..","...","..=","+=","-=","*=","/="
}

class Token:
    def __init__(self, type_, value, line, col):
        self.type = type_
        self.value = value
        self.line = line
        self.col = col

    def __repr__(self):
        return f"{self.type}({self.value!r}) at {self.line}:{self.col}"

class LuaTokenizer:
    def __init__(self, text):
        self.text = text
        self.i = 0
        self.line = 1
        self.col = 1
        self.tokens = []

    def peek(self, n=1):
        if self.i + n > len(self.text):
            return ""
        return self.text[self.i:self.i+n]

    def advance(self, n=1):
        for _ in range(n):
            if self.i >= len(self.text):
                return
            if self.text[self.i] == "\n":
                self.line += 1
                self.col = 1
            else:
                self.col += 1
            self.i += 1

    def add(self, type_, value):
        self.tokens.append(Token(type_, value, self.line, self.col))

    def tokenize(self):
        while self.i < len(self.text):
            ch = self.text[self.i]

            # Whitespace
            if ch.isspace():
                start = self.i
                while self.i < len(self.text) and self.text[self.i].isspace():
                    self.advance()
                self.add("WHITESPACE", self.text[start:self.i])
                continue

            # Comments
            if self.peek(2) == "--":
                if self.peek(4) == "--[[":
                    # Long comment
                    start = self.i
                    self.advance(4)
                    while self.i < len(self.text) and self.peek(2) != "]]":
                        self.advance()
                    self.advance(2)
                    self.add("COMMENT", self.text[start:self.i])
                else:
                    # Line comment
                    start = self.i
                    while self.i < len(self.text) and self.text[self.i] != "\n":
                        self.advance()
                    self.add("COMMENT", self.text[start:self.i])
                continue

            # Long strings [[ ... ]]
            if self.peek(2) == "[[":
                start = self.i
                self.advance(2)
                while self.i < len(self.text) and self.peek(2) != "]]":
                    self.advance()
                self.advance(2)
                self.add("STRING", self.text[start:self.i])
                continue

            # Normal strings
            if ch in "\"'":
                quote = ch
                start = self.i
                self.advance()
                while self.i < len(self.text):
                    if self.text[self.i] == "\\":
                        self.advance(2)
                        continue
                    if self.text[self.i] == quote:
                        self.advance()
                        break
                    self.advance()
                self.add("STRING", self.text[start:self.i])
                continue

            # Numbers
            if ch.isdigit():
                start = self.i
                while self.i < len(self.text) and re.match(r"[0-9A-Fa-fxX\.]", self.text[self.i]):
                    self.advance()
                self.add("NUMBER", self.text[start:self.i])
                continue

            # Identifiers / keywords
            if ch.isalpha() or ch == "_":
                start = self.i
                while self.i < len(self.text) and (self.text[self.i].isalnum() or self.text[self.i] == "_"):
                    self.advance()
                value = self.text[start:self.i]
                if value in KEYWORDS:
                    self.add("KEYWORD", value)
                else:
                    self.add("IDENTIFIER", value)
                continue

            # Operators / punctuation
            matched = False
            for op in sorted(OPERATORS, key=len, reverse=True):
                if self.peek(len(op)) == op:
                    self.add("OPERATOR" if op not in "(){}[];:,. " else "PUNCT", op)
                    self.advance(len(op))
                    matched = True
                    break
            if matched:
                continue

            # Unknown token (obfuscator garbage)
            self.add("UNKNOWN", ch)
            self.advance()

        return self.tokens
