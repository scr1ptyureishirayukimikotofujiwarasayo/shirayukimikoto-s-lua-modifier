import re
from lua_tokenizer import LuaTokenizer
from lua_block_engine import BlockEngine

RESERVED = {
    "and","break","do","else","elseif","end","false","for","function","goto",
    "if","in","local","nil","not","or","repeat","return","then","true","until","while"
}

STRING_PATTERN = re.compile(r'"([^"\\]|\\.)*"|\'([^\'\\]|\\.)*\'')

def validate_for_obfuscation(code: str):
    warnings = []
    errors = []

    # 1. Syntax / block structure check
    try:
        tokenizer = LuaTokenizer(code)
        tokens = tokenizer.tokenize()
        engine = BlockEngine(tokens)
        engine.process()
    except Exception as e:
        errors.append(f"[Syntax] Block structure error: {str(e)}")

    # 2. Identifiers appearing inside string literals (rename risk)
    for match in STRING_PATTERN.finditer(code):
        literal = match.group(0)
        words = re.findall(r"[A-Za-z_][A-Za-z0-9_]*", literal)
        for w in words:
            if w not in RESERVED:
                warnings.append(
                    f"[Rename Risk] Identifier '{w}' appears inside a string literal; "
                    f"ensure renaming does not break logic."
                )

    # 3. Roblox API literal checks
    if re.search(r"GetService\s*\([^\"']", code):
        warnings.append("[API] GetService called without a literal string; obfuscation may break this call.")

    if re.search(r"WaitForChild\s*\([^\"']", code):
        warnings.append("[API] WaitForChild called without a literal string; obfuscation may break this call.")

    if re.search(r"Instance\.new\s*\([^\"']", code):
        warnings.append("[API] Instance.new called without a literal class name; obfuscation may break this call.")

    return warnings, errors
