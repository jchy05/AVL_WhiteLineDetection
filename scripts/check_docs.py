"""Check local Markdown links without network access or interpreting document text."""
from pathlib import Path
import re
from urllib.parse import unquote
ROOT=Path(__file__).resolve().parents[1]
errors=[]; checked=0
for file in ROOT.rglob('*.md'):
    if any(p in ('.git','.venv','.pytest_cache','build','dist') or p.endswith('.egg-info') for p in file.relative_to(ROOT).parts):continue
    for raw in re.findall(r'!?\[[^\]]*\]\(([^)]+)\)',file.read_text(encoding='utf-8')):
        target=raw.strip().strip('<>').split('#',1)[0]
        if not target or re.match(r'^[a-zA-Z][a-zA-Z0-9+.-]*:',target):continue
        target=unquote(target.split(' "',1)[0])
        checked+=1
        if not (file.parent/target).exists():errors.append(str(file.relative_to(ROOT))+': '+raw)
if errors:raise SystemExit('Broken local links:\n'+'\n'.join(errors))
print(f'Local documentation links checked: {checked}')
