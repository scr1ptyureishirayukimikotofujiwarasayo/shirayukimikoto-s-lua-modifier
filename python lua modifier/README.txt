The Lua Modifier is a Python‑based toolchain designed to transform Lua scripts used in Roblox Luau. It handles deobfuscation, beautification, obfuscation, and minification using a custom tokenizer, block engine, and formatter built specifically for messy or heavily obfuscated code.

It automatically decodes escape sequences, simplifies expressions, propagates constants, and reconstructs readable structure. Even scripts that are compressed, escaped, or wrapped in loadstring calls can be restored into clean, editable Lua.

Beautification restores indentation and formatting without changing logic. Minification removes whitespace and comments to produce compact scripts. Both processes are reversible because they only affect formatting, not behavior.

Using the tool is simple. Place any .lua file in the same directory as the Python scripts. Then run the command that matches what you want to do.

Running python deobfuscate.py yourscript.lua fully deobfuscates and beautifies the file, saving the result in the deobsfucated scripts folder. This should only be done once per script.

Running python beautify.py yourscript.lua formats an already readable or minified script and saves it in beautified scripts. Running python minify.py yourscript.lua compresses a script and saves it in minified scripts.

Running python obfuscate.py yourscript.lua applies identifier obfuscation, string encoding, and minification, saving the final result in obfuscated scripts.

Running python luafixer.py yourscript.lua attemps to fix your luascript(especially if its a roblox script tested in studio) as well

While typing commands, pressing Tab helps auto‑complete filenames and arguments. This makes running the tool faster and prevents mistakes when working with long or complex file names.

This workflow makes it easy to clean, inspect, modify, obfuscate, or compress Lua scripts while keeping everything organized and predictable.