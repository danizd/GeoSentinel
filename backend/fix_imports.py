"""Script para actualizar imports relativos de api/models/ingestors/etc a backend.api/backend.models/etc."""
import re
from pathlib import Path

BACKEND_DIR = Path(__file__).parent
patterns = [
    (r'^from api\.', 'from backend.api.'),
    (r'^from models\.', 'from backend.models.'),
    (r'^from ingestors\.', 'from backend.ingestors.'),
    (r'^from jobs\.', 'from backend.jobs.'),
    (r'^from normalizers\.', 'from backend.normalizers.'),
    (r'^from schemas\.', 'from backend.schemas.'),
    (r'^from validation\.', 'from backend.validation.'),
]

for py_file in BACKEND_DIR.rglob('*.py'):
    try:
        content = py_file.read_text(encoding='utf-8')
    except UnicodeDecodeError:
        try:
            content = py_file.read_text(encoding='latin-1')
        except Exception:
            print(f'Skipping (encoding error): {py_file.name}')
            continue

    new_content = content
    for pattern, replacement in patterns:
        new_content = re.sub(pattern, replacement, new_content, flags=re.MULTILINE)

    if new_content != content:
        py_file.write_text(new_content, encoding='utf-8')
        print(f'Updated: {py_file.relative_to(BACKEND_DIR.parent)}')

print('Done!')
