#!/usr/bin/env python3
import os, re, requests
from datetime import datetime

# --- env ---
VERIFY  = (os.environ.get('ARRIGO_INSECURE')!='1')
LOGIN   = os.environ['ARRIGO_LOGIN_URL']
GQL     = os.environ['ARRIGO_GRAPHQL_URL']
USER    = os.environ.get('ARRIGO_USER','APIUser')
PASS    = os.environ.get('ARRIGO_PASS','API_S#are')
PVL_B64 = os.environ['ARRIGO_PVL_PATH']

# --- token ---
tok = requests.post(LOGIN, json={'username':USER,'password':PASS},
                    verify=VERIFY, timeout=30).json()['authToken']
hdr = {'Authorization':f'Bearer {tok}','Content-Type':'application/json'}

# --- läs alla variabler (ordningen = index) ---
q = 'query($p:String!){ data(path:$p){ variables{ technicalAddress type value } } }'
j = requests.post(GQL, headers=hdr, json={'query':q,'variables':{'p':PVL_B64}},
                  verify=VERIFY, timeout=30).json()
vars_ = j['data']['data']['variables']

# --- dina 24 rangtal (byt källa vid behov) ---
rank = [14,13,15,11,12,10,16,23,2,3,4,5,6,0,1,7,8,22,17,9,21,18,20,19]

# --- matcha alla tre namnstilarna, case-insensitivt ---
#  PRICE_RANK_00 .. _23
#  Price_Rank_0 .. _23
#  PRICE_RANK(0) .. (23)
re_rank = re.compile(r'(?:price)[_ ]?rank(?:_| ?|\()(\d{1,2})\)?$', re.I)

items = []
for i, v in enumerate(vars_):
    ta  = v['technicalAddress']
    # hoppa över mask-variabler (read-only i din miljö)
    if ta.endswith(('EC_MASK_L','EC_MASK_H','EX_MASK_L','EX_MASK_H')):
        continue
    m = re_rank.search(ta)
    if m:
        h = int(m.group(1))
        if 0 <= h <= 23:
            items.append({'key': f'{PVL_B64}:{i}', 'value': str(rank[h])})
            continue
    if ta.endswith('PRICE_OK'):
        items.append({'key': f'{PVL_B64}:{i}', 'value': '1'})
    if ta.endswith('PRICE_STAMP'):
        items.append({'key': f'{PVL_B64}:{i}', 'value': datetime.now().strftime('%Y%m%d')})

# --- skriv ---
if items:
    mut = 'mutation ($variables:[VariableKeyValue!]!){ writeData(variables:$variables) }'
    r = requests.post(GQL, headers=hdr, json={'query':mut,'variables':{'variables':items}},
                      verify=VERIFY, timeout=30).json()['data']['writeData']
    bad = [i for i,x in enumerate(r) if str(x)!='True']
    if bad:
        print("❌ False på:", [items[i]['key'] for i in bad])
    else:
        print(f"✅ Allt True ( {len(items)} nycklar )")
else:
    print("✅ Allt True ( 0 nycklar )")

# --- visa bekräftelse för 0..9 över alla stilar ---
q2='query($p:String!){ data(path:$p){ variables{ technicalAddress value } } }'
j2=requests.post(GQL, headers=hdr, json={'query':q2,'variables':{'p':PVL_B64}},
                 verify=VERIFY, timeout=30).json()
vals = {v['technicalAddress']:v['value'] for v in j2['data']['data']['variables']}
for h in range(10):
    for pat in (f'PRICE_RANK_{h:02d}', f'Price_Rank_{h}', f'PRICE_RANK({h})'):
        for k in vals:
            if k.endswith(pat):
                print(k, '=', vals[k])
