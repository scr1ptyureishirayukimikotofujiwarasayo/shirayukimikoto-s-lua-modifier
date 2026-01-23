class BlockEngine:
    def __init__(self, tokens):
        self.tokens = tokens
        self.index = 0
        self.indent = 0
        self.mode = "normal"  # can be "normal" or "safe"
        self.output = []

    def current(self):
        if self.index < len(self.tokens):
            return self.tokens[self.index]
        return None

    def next(self):
        self.index += 1
        return self.current()

    def switch_to_safe(self, reason):
        # Switch only once unless code becomes clean again
        if self.mode != "safe":
            self.mode = "safe"

    def switch_to_normal(self):
        if self.mode != "normal":
            self.mode = "normal"

    def process(self):
        while self.index < len(self.tokens):
            tok = self.current()

            # Unknown tokens → suspicious → safe mode
            if tok.type == "UNKNOWN":
                self.switch_to_safe("unknown token")

            # Comments are preserved exactly
            if tok.type == "COMMENT":
                self.output.append(("comment", tok.value, self.indent))
                self.next()
                continue

            # Strings are preserved exactly
            if tok.type == "STRING":
                self.output.append(("string", tok.value, self.indent))
                self.next()
                continue

            # Keywords drive indentation
            if tok.type == "KEYWORD":
                kw = tok.value

                if kw in ("function", "do", "then"):
                    self.output.append(("keyword", kw, self.indent))
                    self.indent += 1
                    self.next()
                    continue

                if kw in ("else", "elseif"):
                    self.indent = max(0, self.indent - 1)
                    self.output.append(("keyword", kw, self.indent))
                    self.indent += 1
                    self.next()
                    continue

                if kw in ("end", "until"):
                    self.indent = max(0, self.indent - 1)
                    self.output.append(("keyword", kw, self.indent))
                    self.next()
                    continue

                # Other keywords
                self.output.append(("keyword", kw, self.indent))
                self.next()
                continue

            # Identifiers, numbers, operators, punctuation
            self.output.append((tok.type.lower(), tok.value, self.indent))
            self.next()

        return self.output
