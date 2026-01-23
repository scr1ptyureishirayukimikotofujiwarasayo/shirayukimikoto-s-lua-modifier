import os
import sys
import re
import random
import string
from minify import minify_lua
from obfuscator_linter import validate_for_obfuscation

RESERVED = {
    "and","break","do","else","elseif","end","false","for","function","goto",
    "if","in","local","nil","not","or","repeat","return","then","true","until","while"
}

STRING_PATTERN = re.compile(r'"([^"\\]|\\.)*"|\'([^\'\\]|\\.)*\'')

def random_name(length=8):
    return ''.join(random.choice(string.ascii_letters) for _ in range(length))

# -----------------------------
# String protection for renaming
# -----------------------------

def extract_strings(code):
    strings = []

    def repl(m):
        idx = len(strings)
        strings.append(m.group(0))
        return f"__STR_PLACEHOLDER_{idx}__"

    code = STRING_PATTERN.sub(repl, code)
    return code, strings

def restore_strings(code, strings):
    for idx, s in enumerate(strings):
        code = code.replace(f"__STR_PLACEHOLDER_{idx}__", s)
    return code

# -----------------------------
# Identifier collection / renaming
# -----------------------------

def collect_identifiers(code):
    identifiers = set()

    for var in re.findall(r"\blocal\s+([A-Za-z_][A-Za-z0-9_]*)", code):
        if var not in RESERVED:
            identifiers.add(var)

    for fn in re.findall(r"\blocal\s+function\s+([A-Za-z_][A-Za-z0-9_]*)", code):
        if fn not in RESERVED:
            identifiers.add(fn)

    for fn in re.findall(r"\bfunction\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(", code):
        if fn not in RESERVED:
            identifiers.add(fn)

    return identifiers

def build_rename_map(identifiers):
    rename_map = {}
    for name in identifiers:
        rename_map[name] = random_name()
    return rename_map

def apply_renaming(code, rename_map):
    for old, new in rename_map.items():
        code = re.sub(rf"\b{old}\b", new, code)
    return code

# -----------------------------
# String encoding
# -----------------------------

def encode_strings(code):
    def encode_match(m):
        text = m.group(0)
        try:
            val = eval(text)
        except Exception:
            return text
        encoded = "".join(f"\\{ord(c)}" for c in val)
        return '"' + encoded + '"'
    return STRING_PATTERN.sub(encode_match, code)

# -----------------------------
# Main pipeline
# -----------------------------

def obfuscate_and_minify(infile):
    with open(infile, "r", encoding="utf-8") as f:
        code = f.read()

    # 1) Lint / validate before obfuscation
    warnings, errors = validate_for_obfuscation(code)

    for w in warnings:
        print(w)

    if errors:
        print("Obfuscation aborted due to syntax errors:")
        for e in errors:
            print(e)
        return

    # 2) Protect strings
    code_no_strings, strings = extract_strings(code)

    # 3) Collect and rename identifiers on code without strings
    identifiers = collect_identifiers(code_no_strings)
    rename_map = build_rename_map(identifiers)
    code_no_strings = apply_renaming(code_no_strings, rename_map)

    # 4) Restore original strings
    code = restore_strings(code_no_strings, strings)

    # 5) Encode strings
    code = encode_strings(code)

    # 6) Minify
    code = minify_lua(code)

    # 7) Output
    out_dir = "obfuscated scripts"
    os.makedirs(out_dir, exist_ok=True)

    base = os.path.basename(infile)
    outfile = os.path.join(out_dir, base.replace(".lua", ".ob.lua"))

    with open(outfile, "w", encoding="utf-8") as f:
        f.write(code)

    print(f"Obfuscated + minified → {outfile}")

# -----------------------------
# CLI
# -----------------------------

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python obfuscate.py <file.lua>")
        sys.exit(1)

    obfuscate_and_minify(sys.argv[1])
