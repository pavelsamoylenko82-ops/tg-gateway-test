import os

EXCLUDE_DIRS = {'.git', '__pycache__', '.venv', 'venv', '.idea', '.vscode'}
EXCLUDE_EXTS = {'.pyc', '.png', '.jpg', '.tar', '.zip'}
OUTPUT_FILE = 'project_dump.txt'

with open(OUTPUT_FILE, 'w', encoding='utf-8') as outfile:
    for root, dirs, files in os.walk('.'):
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
        for file in files:
            if any(file.endswith(ext) for ext in EXCLUDE_EXTS) or file == OUTPUT_FILE:
                continue
            filepath = os.path.join(root, file)
            outfile.write(f"\n{'='*40}\nFILE: {filepath}\n{'='*40}\n")
            try:
                with open(filepath, 'r', encoding='utf-8') as infile:
                    outfile.write(infile.read())
            except Exception as e:
                outfile.write(f"[Error reading file: {e}]\n")

print(f"Дамп сохранён в {OUTPUT_FILE}")