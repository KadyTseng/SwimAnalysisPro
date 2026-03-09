
import os
import sys

input_file = 'requirements.txt'
output_file = 'requirements_cleaned.txt'

print(f"Reading from {input_file}...", flush=True)

# Try reading
content = ""
# We know it's likely UTF-16
try:
    with open(input_file, 'r', encoding='utf-16') as f:
        content = f.read()
    print("Read as UTF-16", flush=True)
except UnicodeError:
    try:
        with open(input_file, 'r', encoding='utf-16le') as f:
            content = f.read()
        print("Read as UTF-16LE", flush=True)
    except UnicodeError:
        with open(input_file, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        print("Read as UTF-8/Fallback", flush=True)

lines = content.splitlines()
cleaned_lines = []

for line in lines:
    line = line.strip()
    if not line:
        continue
    
    # Logic to clean lines
    if 'pywin' in line or 'PyQt5-Qt5' in line:
        continue
        
    if ' @ file:' in line:
        parts = line.split(' @ ')
        line = parts[0]
        
    if line.startswith('torch') or line.startswith('torchvision') or line.startswith('torchaudio'):
        continue

    cleaned_lines.append(line)

# Write as UTF-8
with open(output_file, 'w', encoding='utf-8') as f:
    f.write('\n'.join(cleaned_lines))

print(f"Cleaned requirements saved to {output_file} (UTF-8). Total lines: {len(cleaned_lines)}", flush=True)
