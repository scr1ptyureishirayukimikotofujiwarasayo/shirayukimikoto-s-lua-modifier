import os
import sys
import re
from typing import List, Tuple, Optional
from dataclasses import dataclass
from enum import Enum

class TokenType(Enum):
    KEYWORD = "KEYWORD"
    IDENTIFIER = "IDENTIFIER"
    OPERATOR = "OPERATOR"
    NUMBER = "NUMBER"
    STRING = "STRING"
    COMMENT = "COMMENT"
    WHITESPACE = "WHITESPACE"
    NEWLINE = "NEWLINE"
    PUNCTUATION = "PUNCTUATION"

@dataclass
class Token:
    type: TokenType
    value: str
    line: int
    col: int

class LuaTokenizer:
    """Optimized Lua tokenizer with Roblox support."""
    
    KEYWORDS = {
        'and', 'break', 'do', 'else', 'elseif', 'end', 'false', 'for',
        'function', 'if', 'in', 'local', 'nil', 'not', 'or', 'repeat',
        'return', 'then', 'true', 'until', 'while', 'continue'  # Roblox adds continue
    }
    
    OPERATORS = {
        '+', '-', '*', '/', '%', '^', '#', '==', '~=', '<=', '>=',
        '<', '>', '=', '(', ')', '{', '}', '[', ']', ';', ':', ',',
        '.', '..', '...', '+=', '-=', '*=', '/=', '^=', '..='  # Roblox compound operators
    }
    
    def __init__(self, code: str):
        self.code = code
        self.pos = 0
        self.line = 1
        self.col = 1
        self.length = len(code)
    
    def peek(self, offset: int = 0) -> Optional[str]:
        p = self.pos + offset
        return self.code[p] if p < self.length else None
    
    def advance(self) -> Optional[str]:
        if self.pos >= self.length:
            return None
        c = self.code[self.pos]
        self.pos += 1
        if c == '\n':
            self.line += 1
            self.col = 1
        else:
            self.col += 1
        return c
    
    def tokenize(self) -> List[Token]:
        tokens = []
        while self.pos < self.length:
            c = self.peek()
            start_col = self.col
            
            # Whitespace (non-newline)
            if c in ' \t\r':
                self.advance()
                continue
            
            # Newline
            elif c == '\n':
                self.advance()
                tokens.append(Token(TokenType.NEWLINE, '\n', self.line - 1, start_col))
            
            # Comments
            elif c == '-' and self.peek(1) == '-':
                tokens.append(self._read_comment())
            
            # Strings
            elif c in '"\'':
                tokens.append(self._read_string(c))
            
            # Long strings/comments
            elif c == '[':
                if self.peek(1) in '=[':
                    level = 0
                    idx = 1
                    while self.peek(idx) == '=':
                        level += 1
                        idx += 1
                    if self.peek(idx) == '[':
                        tokens.append(self._read_long_string(level))
                        continue
                tokens.append(self._read_operator())
            
            # Numbers
            elif c.isdigit() or (c == '.' and self.peek(1) and self.peek(1).isdigit()):
                tokens.append(self._read_number())
            
            # Identifiers and keywords
            elif c.isalpha() or c == '_':
                tokens.append(self._read_identifier())
            
            # Operators
            else:
                tokens.append(self._read_operator())
        
        return tokens
    
    def _read_comment(self) -> Token:
        start_line = self.line
        start_col = self.col
        self.advance()  # -
        self.advance()  # -
        
        # Long comment
        if self.peek() == '[':
            level = 0
            self.advance()
            while self.peek() == '=':
                level += 1
                self.advance()
            if self.peek() == '[':
                self.advance()
                return self._read_long_bracket_content(level, TokenType.COMMENT, start_line, start_col, '--[' + '=' * level + '[')
        
        # Single line comment
        value = '--'
        while self.peek() and self.peek() != '\n':
            value += self.advance()
        return Token(TokenType.COMMENT, value, start_line, start_col)
    
    def _read_string(self, quote: str) -> Token:
        start_line = self.line
        start_col = self.col
        value = self.advance()  # Opening quote
        
        while True:
            c = self.peek()
            if c is None:
                break
            if c == quote:
                value += self.advance()
                break
            if c == '\\':
                value += self.advance()
                if self.peek():
                    value += self.advance()
            else:
                value += self.advance()
        
        return Token(TokenType.STRING, value, start_line, start_col)
    
    def _read_long_string(self, level: int) -> Token:
        start_line = self.line
        start_col = self.col
        prefix = '[' + '=' * level + '['
        for _ in prefix:
            self.advance()
        return self._read_long_bracket_content(level, TokenType.STRING, start_line, start_col, prefix)
    
    def _read_long_bracket_content(self, level: int, token_type: TokenType, start_line: int, start_col: int, prefix: str) -> Token:
        value = prefix
        suffix = ']' + '=' * level + ']'
        
        while True:
            c = self.peek()
            if c is None:
                break
            if c == ']':
                match_len = 1
                while match_len <= len(suffix) and self.peek(match_len - 1) == suffix[match_len - 1]:
                    match_len += 1
                if match_len > len(suffix):
                    for _ in suffix:
                        value += self.advance()
                    break
            value += self.advance()
        
        return Token(token_type, value, start_line, start_col)
    
    def _read_number(self) -> Token:
        start_line = self.line
        start_col = self.col
        value = ''
        
        # Hex
        if self.peek() == '0' and self.peek(1) in 'xX':
            value += self.advance() + self.advance()
            while self.peek() and self.peek() in '0123456789abcdefABCDEF_.':
                value += self.advance()
        else:
            # Decimal
            while self.peek() and (self.peek().isdigit() or self.peek() in '._'):
                value += self.advance()
            # Exponent
            if self.peek() in 'eE':
                value += self.advance()
                if self.peek() in '+-':
                    value += self.advance()
                while self.peek() and self.peek().isdigit():
                    value += self.advance()
        
        return Token(TokenType.NUMBER, value, start_line, start_col)
    
    def _read_identifier(self) -> Token:
        start_line = self.line
        start_col = self.col
        value = ''
        
        while self.peek() and (self.peek().isalnum() or self.peek() == '_'):
            value += self.advance()
        
        token_type = TokenType.KEYWORD if value in self.KEYWORDS else TokenType.IDENTIFIER
        return Token(token_type, value, start_line, start_col)
    
    def _read_operator(self) -> Token:
        start_line = self.line
        start_col = self.col
        
        # Try 3-char operators
        three = ''.join(self.peek(i) or '' for i in range(3))
        if three in ('...', ) or three[:2] in ('../=', ) :
            value = three if three == '...' else three[:2]
            for _ in value:
                self.advance()
            return Token(TokenType.OPERATOR, value, start_line, start_col)
        
        # Try 2-char operators
        two = ''.join(self.peek(i) or '' for i in range(2))
        if two in ('==', '~=', '<=', '>=', '..', '+=', '-=', '*=', '/=', '^='):
            for _ in two:
                self.advance()
            return Token(TokenType.OPERATOR, two, start_line, start_col)
        
        # Single char
        value = self.advance()
        return Token(TokenType.OPERATOR, value, start_line, start_col)

class LuaBeautifier:
    """Efficient Lua code beautifier with Roblox support."""
    
    def __init__(self, indent: str = "\t"):
        self.indent = indent
        self.level = 0
        self.output = []
        self.tokens = []
        self.i = 0
    
    def beautify(self, code: str) -> str:
        tokenizer = LuaTokenizer(code)
        self.tokens = [t for t in tokenizer.tokenize() if t.type != TokenType.WHITESPACE]
        self.i = 0
        self.level = 0
        self.output = []
        
        while self.i < len(self.tokens):
            self._process_token()
        
        # Clean up multiple blank lines
        result = ''.join(self.output)
        result = re.sub(r'\n{3,}', '\n\n', result)
        return result.strip() + '\n'
    
    def _peek(self, offset: int = 0) -> Optional[Token]:
        idx = self.i + offset
        return self.tokens[idx] if idx < len(self.tokens) else None
    
    def _consume(self) -> Optional[Token]:
        if self.i >= len(self.tokens):
            return None
        token = self.tokens[self.i]
        self.i += 1
        return token
    
    def _process_token(self):
        token = self._peek()
        if not token:
            return
        
        if token.type == TokenType.NEWLINE:
            self._consume()
            # Skip multiple consecutive newlines
            while self._peek() and self._peek().type == TokenType.NEWLINE:
                self._consume()
            self.output.append('\n')
            return
        
        if token.type == TokenType.COMMENT:
            self._handle_comment()
            return
        
        if token.type == TokenType.KEYWORD:
            self._handle_keyword()
            return
        
        # Default: consume and add with spacing
        self._consume()
        self.output.append(token.value)
        
        # Add space after certain tokens
        next_token = self._peek()
        if next_token and next_token.type not in (TokenType.NEWLINE, TokenType.COMMENT):
            if token.type in (TokenType.KEYWORD, TokenType.IDENTIFIER) and next_token.type in (TokenType.IDENTIFIER, TokenType.KEYWORD, TokenType.NUMBER):
                self.output.append(' ')
            elif token.value in (',', ';'):
                self.output.append(' ')
            elif token.value in ('=', '==', '~=', '<=', '>=', '<', '>', '+', '-', '*', '/', '%', '^', '..', 'and', 'or'):
                self.output.append(' ')
                
    def _handle_comment(self):
        token = self._consume()
        # Add indentation before comment if at line start
        if not self.output or self.output[-1] == '\n':
            self.output.append(self.indent * self.level)
        self.output.append(token.value)
    
    def _handle_keyword(self):
        token = self._consume()
        keyword = token.value
        
        # Dedent before certain keywords
        if keyword in ('end', 'else', 'elseif', 'until'):
            self.level = max(0, self.level - 1)
        
        # Add indentation if at start of line
        if not self.output or self.output[-1] == '\n':
            self.output.append(self.indent * self.level)
        
        self.output.append(keyword)
        
        # Add space after keyword
        next_token = self._peek()
        if next_token and next_token.type != TokenType.NEWLINE and next_token.value not in ('(', ')', '{', '}'):
            self.output.append(' ')
        
        # Indent after certain keywords
        if keyword in ('function', 'if', 'for', 'while', 'do', 'repeat', 'else', 'elseif', 'then'):
            if keyword == 'then' or keyword == 'do' or keyword == 'repeat':
                pass  # Already handled by if/for/while
            elif keyword in ('else', 'elseif'):
                self.level += 1
            else:
                # Look ahead for then/do
                temp_i = self.i
                found_then_or_do = False
                while temp_i < len(self.tokens):
                    t = self.tokens[temp_i]
                    if t.value in ('then', 'do'):
                        found_then_or_do = True
                        break
                    if t.value in ('end', 'else', 'elseif'):
                        break
                    temp_i += 1
                
                if found_then_or_do or keyword in ('function', 'repeat'):
                    self.level += 1

def beautify(code: str, indent: str = "\t") -> str:
    """Beautify Lua code."""
    beautifier = LuaBeautifier(indent)
    return beautifier.beautify(code)

def main():
    if len(sys.argv) < 2:
        print("Usage: python beautify.py <file.lua> [--spaces N]")
        print("  --spaces N: Use N spaces for indentation (default: tabs)")
        return
    
    infile = sys.argv[1]
    
    # Parse indent option
    indent = "\t"
    if "--spaces" in sys.argv:
        try:
            idx = sys.argv.index("--spaces")
            spaces = int(sys.argv[idx + 1])
            indent = " " * spaces
        except (IndexError, ValueError):
            print("Invalid --spaces argument")
            return
    
    if not os.path.isfile(infile):
        print(f"Error: '{infile}' is not a valid file.")
        return
    
    # Read input
    with open(infile, "r", encoding="utf-8") as f:
        code = f.read()
    
    # Beautify
    try:
        beautified = beautify(code, indent)
    except Exception as e:
        print(f"Error during beautification: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # Output
    out_dir = "beautified_scripts"
    os.makedirs(out_dir, exist_ok=True)
    base = os.path.basename(infile)
    name, ext = os.path.splitext(base)
    outfile = os.path.join(out_dir, name + ".beaut.lua")
    
    with open(outfile, "w", encoding="utf-8") as f:
        f.write(beautified)
    
    print(f"✓ Beautified → {outfile}")

if __name__ == "__main__":
    main()