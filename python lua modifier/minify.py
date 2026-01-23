import sys
import os
import re
from typing import List, Set, Dict, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

# ========================================
# TOKENIZER
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

class LuaTokenizer:
    """Fast Lua tokenizer for minification."""
    
    KEYWORDS = {
        'and', 'break', 'do', 'else', 'elseif', 'end', 'false', 'for',
        'function', 'if', 'in', 'local', 'nil', 'not', 'or', 'repeat',
        'return', 'then', 'true', 'until', 'while', 'continue'
    }
    
    def __init__(self, code: str):
        self.code = code
        self.pos = 0
        self.length = len(code)
    
    def peek(self, offset: int = 0) -> Optional[str]:
        p = self.pos + offset
        return self.code[p] if p < self.length else None
    
    def advance(self) -> Optional[str]:
        if self.pos >= self.length:
            return None
        c = self.code[self.pos]
        self.pos += 1
        return c
    
    def tokenize(self) -> List[Token]:
        tokens = []
        while self.pos < self.length:
            c = self.peek()
            
            # Whitespace
            if c in ' \t\r\n':
                val = ''
                while self.peek() in ' \t\r\n':
                    val += self.advance()
                tokens.append(Token(TokenType.WHITESPACE, val))
            
            # Comments
            elif c == '-' and self.peek(1) == '-':
                tokens.append(self._read_comment())
            
            # Strings
            elif c in '"\'':
                tokens.append(self._read_string(c))
            
            # Long strings
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
                tokens.append(Token(TokenType.OPERATOR, self.advance()))
            
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
        val = self.advance() + self.advance()  # --
        
        # Long comment
        if self.peek() == '[':
            level = 0
            self.advance()
            while self.peek() == '=':
                level += 1
                self.advance()
            if self.peek() == '[':
                self.advance()
                suffix = ']' + '=' * level + ']'
                while True:
                    c = self.peek()
                    if c is None:
                        break
                    val += self.advance()
                    if val.endswith(suffix):
                        break
                return Token(TokenType.COMMENT, val)
        
        # Single line
        while self.peek() and self.peek() not in '\r\n':
            val += self.advance()
        return Token(TokenType.COMMENT, val)
    
    def _read_string(self, quote: str) -> Token:
        val = self.advance()  # Opening quote
        while True:
            c = self.peek()
            if c is None:
                break
            if c == quote:
                val += self.advance()
                break
            if c == '\\':
                val += self.advance()
                if self.peek():
                    val += self.advance()
            else:
                val += self.advance()
        return Token(TokenType.STRING, val)
    
    def _read_long_string(self, level: int) -> Token:
        prefix = '[' + '=' * level + '['
        for _ in prefix:
            self.advance()
        val = prefix
        suffix = ']' + '=' * level + ']'
        
        while True:
            c = self.peek()
            if c is None:
                break
            val += self.advance()
            if val.endswith(suffix):
                break
        
        return Token(TokenType.STRING, val)
    
    def _read_number(self) -> Token:
        val = ''
        
        # Hex
        if self.peek() == '0' and self.peek(1) in 'xX':
            val += self.advance() + self.advance()
            while self.peek() and self.peek() in '0123456789abcdefABCDEF_.':
                val += self.advance()
        else:
            # Decimal
            while self.peek() and (self.peek().isdigit() or self.peek() in '._'):
                val += self.advance()
            # Exponent
            if self.peek() in 'eE':
                val += self.advance()
                if self.peek() in '+-':
                    val += self.advance()
                while self.peek() and self.peek().isdigit():
                    val += self.advance()
        
        return Token(TokenType.NUMBER, val)
    
    def _read_identifier(self) -> Token:
        val = ''
        while self.peek() and (self.peek().isalnum() or self.peek() == '_'):
            val += self.advance()
        
        ttype = TokenType.KEYWORD if val in self.KEYWORDS else TokenType.IDENTIFIER
        return Token(ttype, val)
    
    def _read_operator(self) -> Token:
        # Try 3-char
        three = ''.join(self.peek(i) or '' for i in range(3))
        if three == '...':
            for _ in range(3):
                self.advance()
            return Token(TokenType.OPERATOR, '...')
        
        # Try 2-char
        two = ''.join(self.peek(i) or '' for i in range(2))
        if two in ('==', '~=', '<=', '>=', '..', '//', '+=', '-=', '*=', '/=', '^='):
            self.advance()
            self.advance()
            return Token(TokenType.OPERATOR, two)
        
        # Single char
        return Token(TokenType.OPERATOR, self.advance())

# ========================================
# VARIABLE RENAMER
# ========================================

class VariableRenamer:
    """Rename local variables to shortest possible names."""
    
    # Reserved Roblox globals to never rename
    ROBLOX_GLOBALS = {
        'game', 'workspace', 'script', 'Instance', 'Vector3', 'CFrame', 
        'UDim2', 'Color3', 'BrickColor', 'Enum', 'wait', 'warn', 'print',
        'tick', 'time', 'elapsedTime', 'spawn', 'delay', 'tick', 'typeof',
        'spawn', 'delay', 'tick', 'typeof', 'Random', 'NumberSequence',
        'ColorSequence', 'NumberRange', 'Region3', 'Faces', 'Axes',
        'PhysicalProperties', 'Ray', 'Rect', 'TweenInfo', 'PathWaypoint',
        'RunService', 'Players', 'ReplicatedStorage', 'ServerStorage',
        'StarterGui', 'StarterPlayer', 'Lighting', 'SoundService',
        'UserInputService', 'ContextActionService', 'TweenService',
        'HttpService', 'MarketplaceService', 'DataStoreService',
        'MessagingService', 'TeleportService', 'BadgeService',
        'pairs', 'ipairs', 'next', 'select', 'unpack', 'table', 'string',
        'math', 'coroutine', 'debug', 'os', 'io', 'tonumber', 'tostring',
        'type', 'assert', 'error', 'pcall', 'xpcall', 'getmetatable',
        'setmetatable', 'rawget', 'rawset', 'rawequal', 'collectgarbage',
        'newproxy', 'gcinfo', 'getfenv', 'setfenv', 'loadstring', 'require',
        '_G', '_VERSION', 'shared'
    }
    
    @staticmethod
    def generate_short_names() -> List[str]:
        """Generate shortest possible variable names."""
        names = []
        
        # Single letters (excluding keywords like 'a' in 'and')
        valid_singles = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ'
        for c in valid_singles:
            names.append(c)
        
        # Two characters: letter + (letter|digit|_)
        for c1 in valid_singles:
            for c2 in valid_singles + '0123456789_':
                name = c1 + c2
                if name not in LuaTokenizer.KEYWORDS:
                    names.append(name)
        
        # Three characters
        for c1 in valid_singles:
            for c2 in valid_singles + '0123456789_':
                for c3 in valid_singles + '0123456789_':
                    name = c1 + c2 + c3
                    if name not in LuaTokenizer.KEYWORDS:
                        names.append(name)
        
        return names
    
    @staticmethod
    def analyze_scope(tokens: List[Token]) -> Dict[str, Set[str]]:
        """Analyze scopes to identify local variables."""
        scopes = [set()]  # Global scope
        local_vars = {}
        
        i = 0
        while i < len(tokens):
            tok = tokens[i]
            
            # Track scope entry
            if tok.type == TokenType.KEYWORD and tok.value in ('function', 'do', 'if', 'for', 'while', 'repeat'):
                scopes.append(set())
            
            # Track scope exit
            elif tok.type == TokenType.KEYWORD and tok.value in ('end', 'until'):
                if len(scopes) > 1:
                    scope_vars = scopes.pop()
                    # Merge to parent scope
                    if scopes:
                        scopes[-1].update(scope_vars)
            
            # Track local declarations
            elif tok.type == TokenType.KEYWORD and tok.value == 'local':
                # Find the identifier(s)
                j = i + 1
                while j < len(tokens):
                    if tokens[j].type == TokenType.WHITESPACE:
                        j += 1
                        continue
                    if tokens[j].type == TokenType.IDENTIFIER:
                        var_name = tokens[j].value
                        if var_name not in VariableRenamer.ROBLOX_GLOBALS:
                            scopes[-1].add(var_name)
                        j += 1
                        # Skip to next identifier or break
                        while j < len(tokens) and tokens[j].type == TokenType.WHITESPACE:
                            j += 1
                        if j < len(tokens) and tokens[j].value == ',':
                            j += 1
                            continue
                    break
            
            i += 1
        
        # Collect all local variables
        all_locals = set()
        for scope in scopes:
            all_locals.update(scope)
        
        return all_locals
    
    @staticmethod
    def rename(tokens: List[Token]) -> List[Token]:
        """Rename local variables to shortest names."""
        local_vars = VariableRenamer.analyze_scope(tokens)
        
        if not local_vars:
            return tokens
        
        # Generate short names
        short_names = VariableRenamer.generate_short_names()
        
        # Create mapping
        var_map = {}
        name_idx = 0
        for var in sorted(local_vars):  # Sort for consistency
            if name_idx < len(short_names):
                var_map[var] = short_names[name_idx]
                name_idx += 1
            else:
                # Fallback to numbered vars if we run out
                var_map[var] = f"v{name_idx}"
                name_idx += 1
        
        # Apply renaming
        result = []
        for tok in tokens:
            if tok.type == TokenType.IDENTIFIER and tok.value in var_map:
                result.append(Token(TokenType.IDENTIFIER, var_map[tok.value]))
            else:
                result.append(tok)
        
        return result

# ========================================
# MINIFIER
# ========================================

class LuaMinifier:
    """Advanced Lua minifier with aggressive optimizations."""
    
    @staticmethod
    def needs_space(prev: Token, curr: Token) -> bool:
        """Determine if space is needed between two tokens."""
        # Always need space between two keywords
        if prev.type == TokenType.KEYWORD and curr.type == TokenType.KEYWORD:
            return True
        
        # Always need space between two identifiers
        if prev.type == TokenType.IDENTIFIER and curr.type == TokenType.IDENTIFIER:
            return True
        
        # Always need space between identifier and keyword
        if prev.type == TokenType.IDENTIFIER and curr.type == TokenType.KEYWORD:
            return True
        if prev.type == TokenType.KEYWORD and curr.type == TokenType.IDENTIFIER:
            return True
        
        # Always need space between keyword and number
        if prev.type == TokenType.KEYWORD and curr.type == TokenType.NUMBER:
            return True
        
        # Always need space between identifier and number
        if prev.type == TokenType.IDENTIFIER and curr.type == TokenType.NUMBER:
            return True
        
        # Always need space between number and identifier
        if prev.type == TokenType.NUMBER and curr.type == TokenType.IDENTIFIER:
            return True
        
        # Always need space between number and keyword
        if prev.type == TokenType.NUMBER and curr.type == TokenType.KEYWORD:
            return True
        
        # Operators: check for specific cases
        if prev.type == TokenType.OPERATOR or curr.type == TokenType.OPERATOR:
            # Handle .. operator specially
            if prev.value == '.' and curr.value == '.':
                return False
            if prev.value == '..' or curr.value == '..':
                # Need space if adjacent to number or identifier
                if curr.type in (TokenType.NUMBER, TokenType.IDENTIFIER):
                    return True
                if prev.type in (TokenType.NUMBER, TokenType.IDENTIFIER):
                    return True
            # - and - can't be adjacent (would become comment)
            if prev.value == '-' and curr.value == '-':
                return True
            # No space needed for most operators
            return False
        
        return False
    
    @staticmethod
    def optimize_numbers(tokens: List[Token]) -> List[Token]:
        """Optimize number representations."""
        result = []
        for tok in tokens:
            if tok.type == TokenType.NUMBER:
                val = tok.value
                
                # Remove unnecessary trailing zeros after decimal
                if '.' in val and 'e' not in val.lower():
                    val = val.rstrip('0').rstrip('.')
                
                # Convert 0.5 to .5
                if val.startswith('0.'):
                    val = val[1:]
                
                # Remove underscores (Lua 5.3+)
                val = val.replace('_', '')
                
                result.append(Token(TokenType.NUMBER, val))
            else:
                result.append(tok)
        return result
    
    @staticmethod
    def optimize_strings(tokens: List[Token]) -> List[Token]:
        """Optimize string representations."""
        result = []
        for tok in tokens:
            if tok.type == TokenType.STRING:
                val = tok.value
                
                # Skip long strings
                if val.startswith('['):
                    result.append(tok)
                    continue
                
                # Try to use the shorter quote style
                if val.startswith('"') and "'" not in val[1:-1]:
                    # Can use single quotes
                    inner = val[1:-1]
                    if len(inner) < len(val) - 2 or '\\' in inner:
                        result.append(tok)
                        continue
                    val = "'" + inner + "'"
                elif val.startswith("'") and '"' not in val[1:-1]:
                    # Can use double quotes
                    inner = val[1:-1]
                    if len(inner) < len(val) - 2 or '\\' in inner:
                        result.append(tok)
                        continue
                    val = '"' + inner + '"'
                
                result.append(Token(TokenType.STRING, val))
            else:
                result.append(tok)
        return result
    
    @staticmethod
    def remove_unnecessary_semicolons(tokens: List[Token]) -> List[Token]:
        """Remove unnecessary semicolons."""
        result = []
        for i, tok in enumerate(tokens):
            if tok.type == TokenType.OPERATOR and tok.value == ';':
                # Check if it's necessary
                # Semicolons are rarely necessary in Lua
                # Skip them unless between certain constructs
                if i + 1 < len(tokens) and tokens[i + 1].type == TokenType.KEYWORD:
                    # Might be needed before keywords in some cases
                    result.append(tok)
                # Otherwise skip
            else:
                result.append(tok)
        return result
    
    @staticmethod
    def minify(code: str, rename_vars: bool = True, aggressive: bool = True) -> str:
        """Minify Lua code."""
        # Tokenize
        tokenizer = LuaTokenizer(code)
        tokens = tokenizer.tokenize()
        
        # Remove comments
        tokens = [t for t in tokens if t.type != TokenType.COMMENT]
        
        # Optimize numbers
        if aggressive:
            tokens = LuaMinifier.optimize_numbers(tokens)
            tokens = LuaMinifier.optimize_strings(tokens)
            tokens = LuaMinifier.remove_unnecessary_semicolons(tokens)
        
        # Rename variables
        if rename_vars:
            tokens = VariableRenamer.rename(tokens)
        
        # Remove whitespace and reconstruct
        result = []
        prev_tok = None
        
        for tok in tokens:
            if tok.type == TokenType.WHITESPACE:
                continue
            
            # Add space if needed
            if prev_tok and LuaMinifier.needs_space(prev_tok, tok):
                result.append(' ')
            
            result.append(tok.value)
            prev_tok = tok
        
        minified = ''.join(result)
        
        # Final cleanup
        if aggressive:
            # Remove spaces around certain operators
            minified = re.sub(r'\s*([+\-*/%^#=<>~,;:.(){}[\]])\s*', r'\1', minified)
            # But preserve necessary spaces
            minified = re.sub(r'([a-zA-Z0-9_])(and|or|not|in)([a-zA-Z0-9_])', r'\1 \2 \3', minified)
            minified = re.sub(r'(and|or|not|in)([a-zA-Z0-9_])', r'\1 \2', minified)
            minified = re.sub(r'([a-zA-Z0-9_])(and|or|not|in)', r'\1 \2', minified)
            # Fix .. operator
            minified = re.sub(r'\.\.([a-zA-Z0-9_])', r'.. \1', minified)
            minified = re.sub(r'([a-zA-Z0-9_])\.\.', r'\1 ..', minified)
            # Fix -- (prevent comment)
            minified = re.sub(r'--', r'- -', minified)
        
        return minified.strip()

# ========================================
# ENTRY POINT
# ========================================

def main():
    if len(sys.argv) < 2:
        print("Usage: python minify.py <file.lua> [options]")
        print("Options:")
        print("  --no-rename    Don't rename variables")
        print("  --basic        Use basic minification (less aggressive)")
        print("  --stats        Show compression statistics")
        return
    
    infile = sys.argv[1]
    rename_vars = '--no-rename' not in sys.argv
    aggressive = '--basic' not in sys.argv
    show_stats = '--stats' in sys.argv
    
    if not os.path.isfile(infile):
        print(f"Error: '{infile}' is not a valid file.")
        return
    
    # Read input
    with open(infile, "r", encoding="utf-8", errors='ignore') as f:
        code = f.read()
    
    original_size = len(code)
    original_lines = code.count('\n') + 1
    
    # Minify
    try:
        minified = LuaMinifier.minify(code, rename_vars, aggressive)
    except Exception as e:
        print(f"Error during minification: {e}")
        import traceback
        traceback.print_exc()
        return
    
    minified_size = len(minified)
    
    # Output
    out_dir = "minified_scripts"
    os.makedirs(out_dir, exist_ok=True)
    base = os.path.basename(infile)
    name, ext = os.path.splitext(base)
    outfile = os.path.join(out_dir, name + ".min.lua")
    
    with open(outfile, "w", encoding="utf-8") as f:
        f.write(minified)
    
    print(f"✓ Minified → {outfile}")
    
    if show_stats:
        reduction = ((original_size - minified_size) / original_size * 100) if original_size > 0 else 0
        print(f"\nStatistics:")
        print(f"  Original:  {original_size:,} bytes ({original_lines:,} lines)")
        print(f"  Minified:  {minified_size:,} bytes (1 line)")
        print(f"  Reduction: {reduction:.1f}%")
        print(f"  Saved:     {original_size - minified_size:,} bytes")

if __name__ == "__main__":
    main()