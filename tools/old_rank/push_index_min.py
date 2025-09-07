#!/usr/bin/env python3
import os, sys, json, re, requests
VERIFY = (os.environ.get('ARRIGO_INSECURE')!='1')
LOGIN  = os.environ['ARRIGO_LOGIN_URL']
GQL    = os.environ['ARRIGO_GRAPHQL_URL']
USER   = os.environ.get('ARRIGO_USER','APIUser')
PASS   = os.environ.get('ARRIGO_PASS','API_S#are')
PVL_B64= os.environ['ARRIGO_PVL_PATH']

# ----- hämta token -----
tok = requests.post(LOGIN, json={'username':USER,'password':PASS},
                    verify=VERIFY, timeout=30).json()['authToken']
hdr = {'Authorization':f'Bearer {tok}','Content-Type':'application/json'}

# ----- läs alla variabler (ordningen = index) -----
q = 'query($p:String!){ data(path:$p){ variables{ technicalAddress type value } } }'
j = requests.post(GQL, headers=hdr,
                  json={'query':q,'variables':{'p':PVL_B64}},
                  verify=VERIFY, timeout=30).json()
vars_ = j['data']['data']['variables']

# ----- dina 24 timranks (ERSÄTT om du hämtar från DB i annat steg) -----
rank = [14,13,15,11,12,10,16,23,2,3,4,5,6,0,1,7,8,22,17,9,21,18,20,19]

items = []
match_re = re.compile(r'(?:PRICE|Price)[_ ]?RANK[_\(]?(\d{1,2})\)?$')

for i, v in enumerate(vars_):
    ta = v['technicalAddress']
    typ = str(v.get('type',''))
    if typ.lower() == 'response':   # skriv inte till read-only
        continue
    m = match_re.search(ta)
    if not m:
        continue
    h = int(m.group(1))
    if 0 <= h <= 23:
        items.append({'key': f'{PVL_B64}:{i}', 'value': str(rank[h])})

# PRICE_OK (om den är skrivbar)
for i, v in enumerate(vars_):
    if v['technicalAddress'].endswith('PRICE_OK') and str(v.get('type','')).lower()!='response':
        items.append({'key': f'{PVL_B64}:{i}', 'value': '1'})

# PRICE_STAMP (om den finns & inte Response)
from datetime import datetime
stamp = datetime.now().strftime('%Y%m%d')
for i, v in enumerate(vars_):
    if v['technicalAddress'].endswith('PRICE_STAMP') and str(v.get('type','')).lower()!='response':
        items.append({'key': f'{PVL_B64}:{i}', 'value': stamp})

# ----- skriv -----
mut = 'mutation ($variables:[VariableKeyValue!]!){ writeData(variables:$variables) }'
r = requests.post(GQL, headers=hdr,
                  json={'query':mut, 'variables':{'variables':items}},
                  verify=VERIFY, timeout=30).json()['data']['writeData']

# rapportera ev. False
bad = [i for i,x in enumerate(r) if str(x)!='True']
if bad:
    print("❌ False på:", [items[i]['key'] for i in bad])
else:
    print("✅ Allt True (", len(items), "nycklar )")

# visa ett urval för bekräftelse
print("Exempelvärden efter push:")
q2='query($p:String!){ data(path:$p){ variables{ technicalAddress value } } }'
j2=requests.post(GQL, headers=hdr,
                 json={'query':q2,'variables':{'p':PVL_B64}},
                 verify=VERIFY, timeout=30).json()
vals = {v['technicalAddress']:v['value'] for v in j2['data']['data']['variables']}
for h in range(10):  # 0..9
    for pat in (f'PRICE_RANK_{h:02d}', f'Price_Rank_{h}'):
        for k in vals:
            if k.endswith(pat):
                print(k, '=', vals[k])
