from pathlib import Path
import re
p = Path(__file__).resolve().parent.parent / 'src/main.cpp'
s = p.read_text()
if 'struct App {' in s:
    start = s.index('struct App {')
    end = s.index('\nvoid style()', start)
    s = s[:start] + '#include "manager_ui.h"\n' + s[end:]
s = s.replace('!app.inspection.valid()', '!app.task.valid()')
s = s.replace('L"DLSS Runtime Loader"', 'L"Universal DLSS 5 Loader"')
s = re.sub(r'\bcontext\b', 'd3dContext', s)
p.write_text(s)
print('Manager UI installed; old loader interface removed.')
