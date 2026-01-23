import os
import sys
import re

# -----------------------------
# File helpers
# -----------------------------

def read_file(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

def write_file(path, content):
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)

# -----------------------------
# Roblox known identifiers
# -----------------------------

ROBLOX_SERVICES = {
    "Players","ReplicatedStorage","ServerScriptService","ServerStorage",
    "StarterGui","StarterPlayer","StarterPack","Lighting","TweenService",
    "UserInputService","RunService","Workspace","Debris","SoundService",
    "TeleportService","HttpService","PathfindingService","CollectionService"
}

ROBLOX_PROPERTIES = {
    "LocalPlayer","Character","Humanoid","HumanoidRootPart","MoveDirection",
    "Parent","Name","Position","Velocity","CFrame","Anchored","Size"
}

ROBLOX_CLASSES = {
    "Vector3","CFrame","Color3","UDim2","RaycastParams","BrickColor",
    "BodyGyro","BodyVelocity","Part","Model","Folder"
}

ROBLOX_GLOBALS = {
    "game","workspace","script","Enum","Vector3","CFrame","UDim2","Color3",
    "Instance","RaycastParams","BrickColor","tick","time","spawn","delay",
    "task","math","string","table","os","coroutine"
}

# -----------------------------
# Levenshtein distance
# -----------------------------

def levenshtein(a, b):
    if len(a) < len(b):
        return levenshtein(b, a)
    if len(b) == 0:
        return len(a)
    prev = range(len(b) + 1)
    for i, c1 in enumerate(a):
        curr = [i + 1]
        for j, c2 in enumerate(b):
            insert = prev[j + 1] + 1
            delete = curr[j] + 1
            replace = prev[j] + (c1 != c2)
            curr.append(min(insert, delete, replace))
        prev = curr
    return prev[-1]

# -----------------------------
# Typo correction
# -----------------------------

def correct_typos(code):
    def replace_identifier(match):
        word = match.group(0)

        if word in ROBLOX_CLASSES:
            return word
        if word in ROBLOX_GLOBALS:
            return word

        for svc in ROBLOX_SERVICES:
            if levenshtein(word, svc) <= 2:
                return svc

        for prop in ROBLOX_PROPERTIES:
            if levenshtein(word, prop) <= 2:
                return prop

        for cls in ROBLOX_CLASSES:
            if levenshtein(word, cls) <= 2:
                return cls

        return word

    return re.sub(r"\b[A-Za-z_][A-Za-z0-9_]*\b", replace_identifier, code)

# -----------------------------
# Semantic Fixes v3 (Smart Mode)
# -----------------------------

def semantic_fixes(code):
    # 1) Fix "local Players = Players.LocalPlayer" -> "local player = Players.LocalPlayer"
    code = re.sub(
        r"\blocal\s+Players\s*=\s*Players\.LocalPlayer\b",
        "local player = Players.LocalPlayer",
        code
    )

    # Detect if "player" exists after that
    has_player = bool(re.search(r"\blocal\s+player\b", code))

    # 2) If player exists, rewrite Players.Character / Players.CharacterAdded to player.*
    if has_player:
        code = re.sub(r"\bPlayers\.CharacterAdded\b", "player.CharacterAdded", code)
        code = re.sub(r"\bPlayers\.Character\b", "player.Character", code)

    # 3) Character loading: x.Character -> x.Character or x.CharacterAdded:Wait()
    # Avoid double-wrapping if already contains CharacterAdded:Wait
    def char_load_repl(m):
        var = m.group(1)
        full = m.group(0)
        if "CharacterAdded:Wait" in full:
            return full
        return f"{var}.Character or {var}.CharacterAdded:Wait()"

    code = re.sub(r"\b(\w+)\.Character\b", char_load_repl, code)

    # 4) HumanoidRootPart loading: x.HumanoidRootPart -> x:WaitForChild("HumanoidRootPart")
    code = re.sub(
        r"\b(\w+)\.HumanoidRootPart\b",
        r'\1:WaitForChild("HumanoidRootPart")',
        code
    )

    # 5) RunService misuse: RenderStepped( -> RenderStepped:Connect(
    code = re.sub(
        r"RunService\.RenderStepped\s*\(",
        "RunService.RenderStepped:Connect(",
        code
    )

    # 6) Uppercase variable misuse (BodyGyro/BodyVelocity vars, not classes)
    # Only change bare identifiers, not inside strings
    code = re.sub(r"\bBodyGyro\b", "bodyGyro", code)
    code = re.sub(r"\bBodyVelocity\b", "bodyVel", code)

    # 7) Ensure Instance.new class names are correct
    code = re.sub(
        r'Instance\.new\("bodyGyro"',
        'Instance.new("BodyGyro"',
        code
    )
    code = re.sub(
        r'Instance\.new\("bodyVel"',
        'Instance.new("BodyVelocity"',
        code
    )

    # 8) Ensure char/hrp are locals when assigned
    code = re.sub(r"\bchar\s*=", "local char =", code)
    code = re.sub(r"\bhrp\s*=", "local hrp =", code)

    # 9) MoveDirection: prefer using char if available
    # If we have local char, rewrite player.Character...MoveDirection to char.Humanoid.MoveDirection
    has_char = bool(re.search(r"\blocal\s+char\b", code))
    if has_char:
        code = re.sub(
            r"\bplayer\.Character(?:\s+or\s+player\.CharacterAdded:Wait\(\))?\.Humanoid\.MoveDirection\b",
            "char.Humanoid.MoveDirection",
            code
        )
        code = re.sub(
            r"\bPlayers\.Character(?:\s+or\s+Players\.CharacterAdded:Wait\(\))?\.Humanoid\.MoveDirection\b",
            "char.Humanoid.MoveDirection",
            code
        )

    return code

# -----------------------------
# 1. Basic syntax fixes
# -----------------------------

def fix_unterminated_strings(code):
    lines = code.split("\n")
    fixed = []
    for line in lines:
        if line.count('"') % 2 == 1:
            line += '"'
        if line.count("'") % 2 == 1:
            line += "'"
        fixed.append(line)
    return "\n".join(fixed)

def fix_missing_end(code):
    opens = len(re.findall(r"\b(do|then|function)\b", code))
    closes = len(re.findall(r"\bend\b", code))
    missing = opens - closes
    if missing > 0:
        code += "\n" + ("end\n" * missing)
    return code

def fix_missing_parentheses(code):
    return re.sub(r"\bif\s+([A-Za-z0-9_\.]+)\s+then", r"if (\1) then", code)

# -----------------------------
# 2. Correct undefined variable detector
# -----------------------------

def declare_undefined_variables(code):
    code_no_comments = re.sub(r"--.*", "", code)
    code_no_strings = re.sub(r"(['\"])(?:\\.|(?!\1).)*\1", "", code_no_comments)

    tokens = re.findall(r"\b([A-Za-z_][A-Za-z0-9_]*)\b", code_no_strings)
    declared = set(re.findall(r"\blocal\s+([A-Za-z_][A-Za-z0-9_]*)", code_no_strings))
    func_defs = set(re.findall(r"\bfunction\s+([A-Za-z_][A-Za-z0-9_]*)", code_no_strings))
    properties = set(re.findall(r"\b[A-Za-z_][A-Za-z0-9_]*\.([A-Za-z_][A-Za-z0-9_]*)", code_no_strings))
    methods = set(re.findall(r"\b[A-Za-z_][A-Za-z0-9_]*:([A-Za-z_][A-Za-z0-9_]*)", code_no_strings))
    enum_values = set(re.findall(r"Enum\.[A-Za-z_][A-Za-z0-9_]*\.([A-Za-z_][A-Za-z0-9_]*)", code_no_strings))
    uppercase = {t for t in tokens if t[0].isupper()}

    exclude = (
        declared | func_defs | properties | methods |
        enum_values | uppercase | ROBLOX_GLOBALS |
        ROBLOX_SERVICES | ROBLOX_PROPERTIES | ROBLOX_CLASSES
    )

    reserved = {
        "and","break","do","else","elseif","end","false","for","function","goto",
        "if","in","local","nil","not","or","repeat","return","then","true","until","while"
    }

    undefined = [
        t for t in tokens
        if t not in exclude and t not in reserved and not t.isdigit()
    ]

    if undefined:
        decls = "\n".join(f"local {name} = nil" for name in sorted(set(undefined)))
        code = decls + "\n\n" + code

    return code

# -----------------------------
# 3. Corrected nil-check logic
# -----------------------------

def add_safe_nil_checks(code):
    def repl(match):
        full = match.group(0)
        var = match.group(1)
        field = match.group(2)

        if var[0].isupper():
            return full
        if var == "Enum":
            return full
        if field[0].isupper():
            return full
        if re.search(rf"{re.escape(full)}\s*=", code):
            return full

        return f"({var} and {var}.{field})"

    return re.sub(r"\b([a-z_][A-Za-z0-9_]*)\.([a-z_][A-Za-z0-9_]*)", repl, code)

# -----------------------------
# 4. Main fix pipeline
# -----------------------------

def fix_lua_code(code):
    code = correct_typos(code)
    code = semantic_fixes(code)
    code = fix_unterminated_strings(code)
    code = fix_missing_end(code)
    code = fix_missing_parentheses(code)
    code = declare_undefined_variables(code)
    code = add_safe_nil_checks(code)
    return code

# -----------------------------
# 5. File processing
# -----------------------------

def fix_file(infile):
    code = read_file(infile)
    fixed = fix_lua_code(code)

    out_dir = "fixed scripts"
    os.makedirs(out_dir, exist_ok=True)

    base = os.path.basename(infile)
    outfile = os.path.join(out_dir, base.replace(".lua", ".fixed.lua"))

    write_file(outfile, fixed)
    print(f"Fixed script saved to {outfile}")

# -----------------------------
# CLI
# -----------------------------

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python fixer.py yourscript.lua")
        sys.exit(1)

    fix_file(sys.argv[1])
