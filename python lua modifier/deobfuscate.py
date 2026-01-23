import os
import sys
import re
import ast
from typing import Dict, List, Set, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

# ========================================
# TOKENIZER (from beautifier)
# ========================================

class TokenType(Enum):
    KEYWORD = "KEYWORD"
    IDENTIFIER = "IDENTIFIER"
    OPERATOR = "OPERATOR"
    NUMBER = "NUMBER"
    STRING = "STRING"
    COMMENT = "COMMENT"
    WHITESPACE = "WHITESPACE"
    NEWLINE = "NEWLINE"

@dataclass
class Token:
    type: TokenType
    value: str
    line: int = 0
    col: int = 0

class LuaTokenizer:
    KEYWORDS = {
        'and', 'break', 'do', 'else', 'elseif', 'end', 'false', 'for',
        'function', 'if', 'in', 'local', 'nil', 'not', 'or', 'repeat',
        'return', 'then', 'true', 'until', 'while', 'continue'
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
            start_line, start_col = self.line, self.col
            
            if c in ' \t\r':
                val = ''
                while self.peek() in ' \t\r':
                    val += self.advance()
                tokens.append(Token(TokenType.WHITESPACE, val, start_line, start_col))
            elif c == '\n':
                self.advance()
                tokens.append(Token(TokenType.NEWLINE, '\n', start_line, start_col))
            elif c == '-' and self.peek(1) == '-':
                tokens.append(self._read_comment())
            elif c in '"\'':
                tokens.append(self._read_string(c))
            elif c == '[' and self.peek(1) in '=[':
                tokens.append(self._read_long_string())
            elif c.isdigit() or (c == '.' and self.peek(1) and self.peek(1).isdigit()):
                tokens.append(self._read_number())
            elif c.isalpha() or c == '_':
                tokens.append(self._read_identifier())
            else:
                tokens.append(self._read_operator())
        return tokens
    
    def _read_comment(self) -> Token:
        start_line, start_col = self.line, self.col
        val = self.advance() + self.advance()
        while self.peek() and self.peek() != '\n':
            val += self.advance()
        return Token(TokenType.COMMENT, val, start_line, start_col)
    
    def _read_string(self, quote: str) -> Token:
        start_line, start_col = self.line, self.col
        val = self.advance()
        while True:
            c = self.peek()
            if c is None or c == quote:
                if c:
                    val += self.advance()
                break
            if c == '\\':
                val += self.advance()
                if self.peek():
                    val += self.advance()
            else:
                val += self.advance()
        return Token(TokenType.STRING, val, start_line, start_col)
    
    def _read_long_string(self) -> Token:
        start_line, start_col = self.line, self.col
        val = self.advance()
        level = 0
        while self.peek() == '=':
            val += self.advance()
            level += 1
        if self.peek() == '[':
            val += self.advance()
        suffix = ']' + '=' * level + ']'
        while True:
            c = self.peek()
            if c is None:
                break
            if c == ']':
                match = True
                for i, sc in enumerate(suffix):
                    if self.peek(i) != sc:
                        match = False
                        break
                if match:
                    for _ in suffix:
                        val += self.advance()
                    break
            val += self.advance()
        return Token(TokenType.STRING, val, start_line, start_col)
    
    def _read_number(self) -> Token:
        start_line, start_col = self.line, self.col
        val = ''
        if self.peek() == '0' and self.peek(1) in 'xX':
            val += self.advance() + self.advance()
            while self.peek() and self.peek() in '0123456789abcdefABCDEF_.':
                val += self.advance()
        else:
            while self.peek() and (self.peek().isdigit() or self.peek() in '._'):
                val += self.advance()
            if self.peek() in 'eE':
                val += self.advance()
                if self.peek() in '+-':
                    val += self.advance()
                while self.peek() and self.peek().isdigit():
                    val += self.advance()
        return Token(TokenType.NUMBER, val, start_line, start_col)
    
    def _read_identifier(self) -> Token:
        start_line, start_col = self.line, self.col
        val = ''
        while self.peek() and (self.peek().isalnum() or self.peek() == '_'):
            val += self.advance()
        ttype = TokenType.KEYWORD if val in self.KEYWORDS else TokenType.IDENTIFIER
        return Token(ttype, val, start_line, start_col)
    
    def _read_operator(self) -> Token:
        start_line, start_col = self.line, self.col
        two = ''.join(self.peek(i) or '' for i in range(2))
        if two in ('==', '~=', '<=', '>=', '..', '+=', '-=', '*=', '/=', '^='):
            val = two
            self.advance()
            self.advance()
        elif two[:3] == '...':
            val = '...'
            self.advance()
            self.advance()
            self.advance()
        else:
            val = self.advance()
        return Token(TokenType.OPERATOR, val, start_line, start_col)

# ========================================
# STRING DECODING
# ========================================

class StringDecoder:
    """Efficient string decoding with multiple encoding support."""
    
    @staticmethod
    def decode_char_codes(nums_str: str) -> Optional[str]:
        """Decode string.char(N1, N2, ...) to literal string."""
        nums = [n.strip() for n in nums_str.split(',')]
        chars = []
        for n in nums:
            if not n:
                continue
            try:
                # Handle hex numbers
                if n.startswith('0x') or n.startswith('0X'):
                    chars.append(chr(int(n, 16)))
                else:
                    chars.append(chr(int(n)))
            except (ValueError, OverflowError):
                return None
        return ''.join(chars)
    
    @staticmethod
    def decode_byte_codes(code: str) -> str:
        """Decode string.byte patterns."""
        # Pattern: string.byte("X") or ("X"):byte()
        pattern = r'string\.byte\s*\(\s*["\'](.)["\']\s*\)|["\'](.)["\']:byte\(\)'
        def repl(m):
            char = m.group(1) or m.group(2)
            return str(ord(char))
        return re.sub(pattern, repl, code)
    
    @staticmethod
    def decode_escapes(s: str) -> str:
        """Decode various escape sequences."""
        # Hex escapes: \xHH
        s = re.sub(r'\\x([0-9A-Fa-f]{2})', lambda m: chr(int(m.group(1), 16)), s)
        # Decimal escapes: \DDD
        s = re.sub(r'\\(\d{1,3})', lambda m: chr(int(m.group(1), 10)), s)
        # Unicode escapes: \u{XXXX}
        s = re.sub(r'\\u\{([0-9A-Fa-f]+)\}', lambda m: chr(int(m.group(1), 16)), s)
        return s
    
    @staticmethod
    def process_string_literals(code: str) -> str:
        """Process and decode all string literals in code."""
        def decode_literal(match):
            s = match.group(0)
            try:
                val = ast.literal_eval(s)
                decoded = StringDecoder.decode_escapes(val)
                return repr(decoded)
            except:
                return s
        
        # Match strings, excluding long strings
        pattern = r'"(?:[^"\\]|\\.)*"|\'(?:[^\'\\]|\\.)*\''
        return re.sub(pattern, decode_literal, code)

# ========================================
# EXPRESSION EVALUATION
# ========================================

class ExpressionEvaluator:
    """Safe expression evaluation for constant folding."""
    
    ALLOWED_OPS = {
        '+', '-', '*', '/', '%', '^', '//', 
        '(', ')', '.', ' ', '\t', '\n'
    }
    
    @staticmethod
    def is_safe_numeric(expr: str) -> bool:
        """Check if expression only contains safe numeric operations."""
        return all(c.isdigit() or c in ExpressionEvaluator.ALLOWED_OPS for c in expr)
    
    @staticmethod
    def evaluate_numeric(expr: str) -> Optional[str]:
        """Safely evaluate numeric expression."""
        expr = expr.strip()
        if not ExpressionEvaluator.is_safe_numeric(expr):
            return None
        try:
            # Replace Lua ^ with Python **
            py_expr = expr.replace('^', '**')
            result = eval(py_expr, {"__builtins__": {}})
            # Format result nicely
            if isinstance(result, float) and result.is_integer():
                return str(int(result))
            return str(result)
        except:
            return None
    
    @staticmethod
    def fold_constants(code: str) -> str:
        """Fold constant numeric expressions."""
        # Fold parenthesized expressions
        def fold_paren(m):
            inner = m.group(1)
            result = ExpressionEvaluator.evaluate_numeric(inner)
            return result if result else m.group(0)
        
        code = re.sub(r'\(([\d\+\-\*\/\^\.\s]+)\)', fold_paren, code)
        
        # Fold simple assignments
        def fold_assign(m):
            left = m.group(1)
            expr = m.group(2)
            result = ExpressionEvaluator.evaluate_numeric(expr)
            return f"{left} = {result}" if result else m.group(0)
        
        code = re.sub(r'(\b[a-zA-Z_]\w*)\s*=\s*([\d\+\-\*\/\^\.\s]+)', fold_assign, code)
        
        return code

# ========================================
# STRING CONCATENATION SIMPLIFIER
# ========================================

class ConcatSimplifier:
    """Simplify string concatenations."""
    
    @staticmethod
    def merge_string_concat(code: str) -> str:
        """Merge consecutive string literal concatenations."""
        pattern = re.compile(
            r'("(?:[^"\\]|\\.)*"|\'(?:[^\'\\]|\\.)*\')\s*\.\.\s*("(?:[^"\\]|\\.)*"|\'(?:[^\'\\]|\\.)*\')'
        )
        
        def merge_pair(m):
            s1, s2 = m.group(1), m.group(2)
            try:
                v1 = ast.literal_eval(s1)
                v2 = ast.literal_eval(s2)
                return repr(v1 + v2)
            except:
                return m.group(0)
        
        prev = None
        iterations = 0
        while prev != code and iterations < 100:
            prev = code
            code = pattern.sub(merge_pair, code)
            iterations += 1
        
        return code
    
    @staticmethod
    def simplify_table_concat(code: str) -> str:
        """Simplify table.concat with literal arrays."""
        pattern = r'table\.concat\s*\(\s*\{([^}]+)\}\s*(?:,\s*(["\'].*?["\']))?\s*\)'
        
        def simplify(m):
            items = m.group(1)
            sep = m.group(2)
            
            try:
                # Parse items
                item_list = [i.strip() for i in items.split(',')]
                values = [ast.literal_eval(i) for i in item_list]
                separator = ast.literal_eval(sep) if sep else ''
                result = separator.join(str(v) for v in values)
                return repr(result)
            except:
                return m.group(0)
        
        return re.sub(pattern, simplify, code)

# ========================================
# LOADSTRING INLINER
# ========================================

class LoadstringInliner:
    """Inline loadstring/load calls with literal payloads."""
    
    PATTERN = re.compile(
        r'(loadstring|load)\s*\(\s*("(?:[^"\\]|\\.)*"|\'(?:[^\'\\]|\\.)*\')\s*\)',
        re.DOTALL
    )
    
    @staticmethod
    def inline(code: str, max_depth: int = 3) -> str:
        """Recursively inline loadstring calls."""
        if max_depth <= 0:
            return code
        
        def replace_loadstring(match):
            func_name = match.group(1)
            raw_string = match.group(2)
            
            try:
                payload = ast.literal_eval(raw_string)
                payload = StringDecoder.decode_escapes(payload)
                
                # Recursively deobfuscate the payload
                deob_payload = Deobfuscator.deobfuscate_internal(payload, max_depth - 1)
                
                # Wrap in function
                return f"(function()\n{deob_payload}\nend)"
            except:
                return match.group(0)
        
        return LoadstringInliner.PATTERN.sub(replace_loadstring, code)

# ========================================
# CONSTANT PROPAGATION
# ========================================

class ConstantPropagator:
    """Advanced constant propagation with data flow analysis."""
    
    @staticmethod
    def propagate(tokens: List[Token]) -> List[Token]:
        """Propagate constants throughout the code."""
        constants: Dict[str, str] = {}
        assignments: Dict[str, int] = {}  # Track assignment count
        result = []
        
        i = 0
        while i < len(tokens):
            # Detect: local NAME = LITERAL
            if (i + 3 < len(tokens) and
                tokens[i].type == TokenType.KEYWORD and tokens[i].value == 'local'):
                
                # Skip whitespace
                j = i + 1
                while j < len(tokens) and tokens[j].type == TokenType.WHITESPACE:
                    j += 1
                
                if (j + 2 < len(tokens) and
                    tokens[j].type == TokenType.IDENTIFIER):
                    name = tokens[j].value
                    
                    # Skip whitespace
                    k = j + 1
                    while k < len(tokens) and tokens[k].type == TokenType.WHITESPACE:
                        k += 1
                    
                    if (k + 1 < len(tokens) and
                        tokens[k].type == TokenType.OPERATOR and tokens[k].value == '='):
                        
                        # Skip whitespace
                        m = k + 1
                        while m < len(tokens) and tokens[m].type == TokenType.WHITESPACE:
                            m += 1
                        
                        if (m < len(tokens) and
                            tokens[m].type in (TokenType.NUMBER, TokenType.STRING)):
                            # Store constant
                            constants[name] = tokens[m].value
                            assignments[name] = 1
            
            # Detect reassignment: NAME = ...
            if (tokens[i].type == TokenType.IDENTIFIER and
                i + 1 < len(tokens)):
                name = tokens[i].value
                
                j = i + 1
                while j < len(tokens) and tokens[j].type == TokenType.WHITESPACE:
                    j += 1
                
                if (j < len(tokens) and
                    tokens[j].type == TokenType.OPERATOR and tokens[j].value == '='):
                    # Variable is reassigned, remove from constants
                    if name in constants:
                        del constants[name]
            
            # Replace identifier with constant if safe
            if (tokens[i].type == TokenType.IDENTIFIER and
                tokens[i].value in constants):
                # Check context - don't replace in assignments
                is_assignment = False
                j = i + 1
                while j < len(tokens) and tokens[j].type == TokenType.WHITESPACE:
                    j += 1
                if (j < len(tokens) and
                    tokens[j].type == TokenType.OPERATOR and tokens[j].value == '='):
                    is_assignment = True
                
                if not is_assignment:
                    # Safe to replace
                    result.append(Token(TokenType.STRING if constants[tokens[i].value].startswith('"') or constants[tokens[i].value].startswith("'") else TokenType.NUMBER,
                                       constants[tokens[i].value],
                                       tokens[i].line, tokens[i].col))
                    i += 1
                    continue
            
            result.append(tokens[i])
            i += 1
        
        return result

# ========================================
# VARIABLE RENAMER
# ========================================

class VariableRenamer:
    """Rename obfuscated variables to readable names."""
    
    @staticmethod
    def is_obfuscated(name: str) -> bool:
        """Check if variable name looks obfuscated."""
        # Single letter or underscore combinations
        if len(name) == 1:
            return True
        # All underscores
        if all(c == '_' for c in name):
            return True
        # Hex-like patterns
        if re.match(r'^[lI1O0_]{3,}$', name):
            return True
        # Long random-looking strings
        if len(name) > 15 and not re.search(r'[aeiou]', name, re.I):
            return True
        return False
    
    @staticmethod
    def rename(code: str, rename_all: bool = False) -> str:
        """Rename variables to more readable names."""
        tokenizer = LuaTokenizer(code)
        tokens = tokenizer.tokenize()
        
        var_map: Dict[str, str] = {}
        counter = {'var': 1, 'func': 1}
        
        for i, tok in enumerate(tokens):
            if tok.type == TokenType.IDENTIFIER:
                name = tok.value
                
                # Skip if already mapped
                if name in var_map:
                    continue
                
                # Check if should rename
                if rename_all or VariableRenamer.is_obfuscated(name):
                    # Determine if it's a function
                    is_func = False
                    if i > 0:
                        j = i - 1
                        while j >= 0 and tokens[j].type == TokenType.WHITESPACE:
                            j -= 1
                        if (j >= 0 and tokens[j].type == TokenType.KEYWORD and 
                            tokens[j].value == 'function'):
                            is_func = True
                    
                    # Generate new name
                    if is_func:
                        var_map[name] = f"func_{counter['func']}"
                        counter['func'] += 1
                    else:
                        var_map[name] = f"var_{counter['var']}"
                        counter['var'] += 1
        
        # Apply renaming
        result = []
        for tok in tokens:
            if tok.type == TokenType.IDENTIFIER and tok.value in var_map:
                result.append(var_map[tok.value])
            else:
                result.append(tok.value)
        
        return ''.join(result)

# ========================================
# BEAUTIFIER
# ========================================

class LuaBeautifier:
    """Format Lua code with proper indentation."""
    
    def __init__(self, indent: str = "\t"):
        self.indent = indent
        self.level = 0
    
    def beautify(self, code: str) -> str:
        tokenizer = LuaTokenizer(code)
        tokens = [t for t in tokenizer.tokenize() 
                  if t.type not in (TokenType.WHITESPACE, TokenType.NEWLINE)]
        
        output = []
        i = 0
        
        while i < len(tokens):
            tok = tokens[i]
            
            # Handle keywords that affect indentation
            if tok.type == TokenType.KEYWORD:
                if tok.value in ('end', 'else', 'elseif', 'until'):
                    self.level = max(0, self.level - 1)
                
                # Add indentation at line start
                if not output or output[-1] == '\n':
                    output.append(self.indent * self.level)
                
                output.append(tok.value)
                
                # Indent after block start
                if tok.value in ('function', 'if', 'for', 'while', 'do', 'repeat', 'then', 'else'):
                    if tok.value in ('then', 'do', 'repeat', 'else'):
                        self.level += 1
                        output.append('\n')
                    else:
                        # Check for then/do ahead
                        self.level += 1
            
            elif tok.type == TokenType.COMMENT:
                if not output or output[-1] == '\n':
                    output.append(self.indent * self.level)
                output.append(tok.value)
                output.append('\n')
            
            else:
                # Regular token
                if not output or output[-1] == '\n':
                    output.append(self.indent * self.level)
                
                output.append(tok.value)
                
                # Add spacing
                if i + 1 < len(tokens):
                    next_tok = tokens[i + 1]
                    if tok.value in (',', ';'):
                        output.append(' ')
                    elif tok.type in (TokenType.KEYWORD, TokenType.IDENTIFIER):
                        if next_tok.type in (TokenType.IDENTIFIER, TokenType.KEYWORD, TokenType.NUMBER):
                            output.append(' ')
            
            i += 1
        
        result = ''.join(output)
        result = re.sub(r'\n{3,}', '\n\n', result)
        return result.strip() + '\n'

# ========================================
# MAIN DEOBFUSCATOR
# ========================================

class Deobfuscator:
    """Main deobfuscation pipeline."""
    
    @staticmethod
    def deobfuscate_internal(code: str, max_depth: int = 3) -> str:
        """Internal deobfuscation with recursion control."""
        
        # Phase 1: Decode string.char(...) patterns
        code = re.sub(
            r'string\.char\s*\(([^)]+)\)',
            lambda m: f'"{StringDecoder.decode_char_codes(m.group(1))}"' 
                     if StringDecoder.decode_char_codes(m.group(1)) else m.group(0),
            code
        )
        
        # Phase 2: Decode string.byte patterns
        code = StringDecoder.decode_byte_codes(code)
        
        # Phase 3: Process string literals (escape sequences)
        code = StringDecoder.process_string_literals(code)
        
        # Phase 4: Inline loadstring/load calls
        code = LoadstringInliner.inline(code, max_depth)
        
        # Phase 5: Fold constant expressions
        code = ExpressionEvaluator.fold_constants(code)
        
        # Phase 6: Simplify string concatenations
        code = ConcatSimplifier.merge_string_concat(code)
        code = ConcatSimplifier.simplify_table_concat(code)
        
        # Phase 7: Constant propagation
        tokenizer = LuaTokenizer(code)
        tokens = tokenizer.tokenize()
        tokens = ConstantPropagator.propagate(tokens)
        code = ''.join(t.value for t in tokens)
        
        # Phase 8: Remove redundant parentheses
        code = re.sub(r'\(\s*("(?:[^"\\]|\\.)*"|\'(?:[^\'\\]|\\.)*\')\s*\)', r'\1', code)
        
        # Phase 9: Clean up
        code = re.sub(r';{2,}', ';', code)
        code = re.sub(r'[ \t]+', ' ', code)
        code = re.sub(r'\n{3,}', '\n\n', code)
        
        return code.strip()
    
    @staticmethod
    def deobfuscate(code: str, rename_vars: bool = False) -> str:
        """Main deobfuscation entry point."""
        code = Deobfuscator.deobfuscate_internal(code, max_depth=3)
        
        # Optional: rename obfuscated variables
        if rename_vars:
            code = VariableRenamer.rename(code)
        
        return code

# ========================================
# ENTRY POINT
# ========================================

def main():
    if len(sys.argv) < 2:
        print("Usage: python deobfuscate.py <file.lua> [--rename] [--spaces N]")
        print("  --rename: Rename obfuscated variables")
        print("  --spaces N: Use N spaces for indentation (default: tabs)")
        return
    
    infile = sys.argv[1]
    rename_vars = '--rename' in sys.argv
    
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
    print(f"Reading {infile}...")
    with open(infile, "r", encoding="utf-8", errors='ignore') as f:
        code = f.read()
    
    # Deobfuscate
    print("Deobfuscating...")
    try:
        deob = Deobfuscator.deobfuscate(code, rename_vars)
    except Exception as e:
        print(f"Error during deobfuscation: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # Beautify
    print("Beautifying...")
    try:
        beautifier = LuaBeautifier(indent)
        beautified = beautifier.beautify(deob)
    except Exception as e:
        print(f"Error during beautification: {e}")
        beautified = deob
    
    # Output
    out_dir = "deobfuscated_scripts"
    os.makedirs(out_dir, exist_ok=True)
    base = os.path.basename(infile)
    name, ext = os.path.splitext(base)
    outfile = os.path.join(out_dir, name + ".deob.lua")
    
    with open(outfile, "w", encoding="utf-8") as f:
        f.write(beautified)
    
    print(f"✓ Deobfuscated + Beautified → {outfile}")
    print(f"   Original size: {len(code)} bytes")
    print(f"   Output size: {len(beautified)} bytes")

if __name__ == "__main__":
    main()