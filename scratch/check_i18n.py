with open('index.html', encoding='utf-8') as f:
    c = f.read()

import re
matches = [m.start() for m in re.finditer(r'market_title', c)]
print('Matches for market_title:', len(matches))
for pos in matches:
    print('--- match at', pos, '---')
    print(c[pos-20:pos+150].encode('ascii', errors='replace').decode('ascii'))
