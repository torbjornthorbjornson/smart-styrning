#!/usr/bin/env python3
import os, json, requests, sys

LOGIN  = os.environ['ARRIGO_LOGIN_URL']
GQL    = os.environ['ARRIGO_GRAPHQL_URL']
USER   = os.environ.get('ARRIGO_USER','APIUser')
PASS   = os.environ.get('ARRIGO_PASS','API_S#are')
PVL_B64= os.environ['ARRIGO_PVL_PATH']
VERIFY = False if os.environ.get('ARRIGO_INSECURE')=='1' else True

REF_PREFIX = 'Huvudcentral_C1'

def gql(query, variables=None, token=None):
    h = {'Content-Type':'application/json'}
    if token: h['Authorization'] = f'Bearer {token}'
    r = requests.post(GQL, json={'query':query,'variables':variables or {}}, headers=h, verify=VERIFY, timeout=30)
    r.raise_for_status()
    j = r.json()
    if 'errors' in j:
        raise SystemExit('GraphQL-fel: '+json.dumps(j['errors'], ensure_ascii=False))
    return j['data']

def login():
    r = requests.post(LOGIN, json={'username':USER,'password':PASS}, verify=VERIFY, timeout=15)
    r.raise_for_status()
    tok = r.json().get('authToken')
    if not tok: raise SystemExit('Inget authToken i svar.')
    return tok

def get_index_map(token):
    q = 'query($p:String!){ data(path:$p){ variables{ technicalAddress } } }'
    d = gql(q, {'p': PVL_B64}, token)
    vars_ = d['data']['variables'] or []
    return { v['technicalAddress']: i for i,v in enumerate(vars_) }

def write_items(token, items):
    mut = 'mutation ($variables:[VariableKeyValue!]!){ writeData(variables:$variables) }'
    # skicka i chunkar om många
    CH=40
    out=[]
    for i in range(0,len(items),CH):
        part = items[i:i+CH]
        d = gql(mut, {'variables': part}, token)
        out += d['writeData']
    return out

def read_back(token):
    q = 'query($p:String!){ data(path:$p){ variables{ technicalAddress value } } }'
    d = gql(q, {'p': PVL_B64}, token)
    return d['data']['variables']

def main():
    tok = login()
    idx = get_index_map(tok)
    if not idx: raise SystemExit('Tom PVL eller fel path.')

    # bygg writes
    items=[]

    # 1) PRICE_OK = 0
    ok_ta = f'{REF_PREFIX}.PRICE_OK'
    if ok_ta in idx:
        items.append({'key': f'{PVL_B64}:{idx[ok_ta]}', 'value': '0'})

    # 2) Försök läsa /tmp/payload.json (om den finns) för ranks + mask + stamp
    price_rank=None; ec=None; ex=None; stamp=None
    if os.path.exists('/tmp/payload.json'):
        try:
            with open('/tmp/payload.json','r',encoding='utf-8') as f:
                p = json.load(f)
            # prova vanliga nycklar
            price_rank = p.get('price_rank') or p.get('rank') or p.get('PRICE_RANK')
            if isinstance(price_rank, list) and len(price_rank)==24:
                for h,val in enumerate(price_rank):
                    for ta in (f'{REF_PREFIX}.PRICE_RANK_{h:02d}', f'{REF_PREFIX}.PRICE_RANK({h})'):
                        if ta in idx:
                            items.append({'key': f'{PVL_B64}:{idx[ta]}', 'value': str(val)})
            # masker
            masks = p.get('masks') or {}
            EC = masks.get('EC') or {}
            EX = masks.get('EX') or {}
            extras = [
                (f'{REF_PREFIX}.EC_MASK_L', EC.get('L')),
                (f'{REF_PREFIX}.EC_MASK_H', EC.get('H')),
                (f'{REF_PREFIX}.EX_MASK_L', EX.get('L')),
                (f'{REF_PREFIX}.EX_MASK_H', EX.get('H')),
                (f'{REF_PREFIX}.PRICE_STAMP', p.get('price_stamp') or p.get('PRICE_STAMP')),
            ]
            for ta,val in extras:
                if val is not None and ta in idx:
                    items.append({'key': f'{PVL_B64}:{idx[ta]}', 'value': str(val)})
        except Exception as e:
            print('⚠️ Ignorerar payload.json:', e, file=sys.stderr)

    # 3) PRICE_OK = 1 sist
    if ok_ta in idx:
        items.append({'key': f'{PVL_B64}:{idx[ok_ta]}', 'value': '1'})

    # skriv
    res = write_items(tok, items)
    print(f'✅ Push skickad ({len(items)} nycklar). Svar: {res}')

    # verifiera
    vars_ = read_back(tok)
    for v in vars_:
        ta=v['technicalAddress']
        if ta.startswith(f'{REF_PREFIX}.PRICE_RANK_0') or ta.endswith('PRICE_OK'):
            print(f'{ta} = {v["value"]}')

if __name__=='__main__':
    main()
