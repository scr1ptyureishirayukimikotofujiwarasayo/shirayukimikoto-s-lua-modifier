class LuaFormatter:
    def __init__(self, structured_tokens):
        self.tokens = structured_tokens
        self.lines = []

    def format(self):
        current_line = ""
        last_indent = 0

        for tok_type, value, indent in self.tokens:

            # New line when indentation changes
            if indent != last_indent:
                if current_line.strip():
                    self.lines.append(current_line)
                current_line = "    " * indent
                last_indent = indent

            # Comments always start a new line
            if tok_type == "comment":
                if current_line.strip():
                    self.lines.append(current_line)
                self.lines.append("    " * indent + value)
                current_line = "    " * indent
                continue

            # Strings are preserved exactly
            if tok_type == "string":
                current_line += value + " "
                continue

            # Keywords
            if tok_type == "keyword":
                # Keywords that should start a new line
                if value in ("function", "if", "for", "while", "repeat", "else", "elseif"):
                    if current_line.strip():
                        self.lines.append(current_line)
                    current_line = "    " * indent + value + " "
                else:
                    current_line += value + " "
                continue

            # Punctuation
            if tok_type == "punct":
                current_line += value
                if value in (",", ";"):
                    current_line += " "
                continue

            # Operators
            if tok_type == "operator":
                current_line += " " + value + " "
                continue

            # Identifiers / numbers
            current_line += value + " "

        # Push last line
        if current_line.strip():
            self.lines.append(current_line)

        return "\n".join(line.rstrip() for line in self.lines)
