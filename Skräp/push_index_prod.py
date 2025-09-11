#!/usr/bin/env python3
import os, json, sys, requests
from datetime import datetime

LOGIN   = os.environ['ARRIGO_LOGIN_URL']
GRAPHQL = os.environ['ARRIGO_GRAPHQL_URL']
USER    = os.environ.get('ARRIGO_USER','APIUser')
PASS    = os.environ.get('ARRIGO_PASS','API_S#are')
PVL_B64 = os.environ['ARRIGO_PVL_PATH']
REF_PRE = os.environ.get('ARRIGO_REF_PREFIX','Huvudcentral_C1')

# TLS: prod = True; dev = env ARRIGO_INSECURE=1 => False; eller CA-bundle
VERIFY = True
if os.environ.get('ARRIGO_INSECURE') == '1':
    VERIFY = False
elif os.environ.get('ARRIGO_CA_BUNDLE'):
    VERIFY = os.environ['ARRIGO_CA_BUNDLE']

def post(query, variables=None, token=None):
    h = {'Content-Type':'application/json'}
    if token: h['Authorization'] = f'Bearer {token}'
    r = requests.post(GRAPHQL, json={'query':query,'variables':variables or {}}, headers=h, verify=VERIFY, timeout=30)
    r.raise_for_status()
    data = r.json()
    if 'errors' in data and data['errors']:
        raise RuntimeError(json.dumps(data['errors'], ensure_ascii=False))
    return data['data']

def login():
    r = requests.post(LOGIN, json={'username':USER,'password':PASS}, verify=VERIFY, timeout=30)
    r.raise_for_status()
    return r.json()['authToken']

def get_index_map(tok:str, pvl_b64:str)->dict[str,int]:
    q = """query($p:String!){ data(path:$p){ variables{ technicalAddress } } }"""
    d = post(q, {'p':pvl_b64}, tok)['data']['variables']
    return { v['technicalAddress']: i for i,v in enumerate(d) }

def normalize_payload(payload)->dict[str,str]:
    """
    Accepterar några vanliga format och normaliserar till:
      { "<TA (t.ex. Huvudcentral_C1.PRICE_RANK_00)>": "<value as string>", ... }
    """
    out = {}
    if isinstance(payload, dict):
        # a) redan “nyckel: värde”
        hits = [k for k in payload.keys() if isinstance(k, str) and k.startswith(REF_PRE+'.')]
        if hits:
            for k in hits:
                out[k] = str(payload[k])
            return out
        # b) {"variables":[{"key": "...", "value":"..."}]} eller {"variables":[{"technicalAddress": "...", "value":"..."}]}
        if 'variables' in payload and isinstance(payload['variables'], list):
            for it in payload['variables']:
                key = it.get('technicalAddress') or it.get('key')
                val = it.get('value')
                if key and isinstance(key, str) and key.startswith(REF_PRE+'.'):
                    out[key] = str(val)
            if out: return out
    if isinstance(payload, list):
        # c) lista av {technicalAddress,value}
        for it in payload:
            if isinstance(it, dict):
                key = it.get('technicalAddress') or it.get('key')
                val = it.get('value')
                if key and isinstance(key, str) and key.startswith(REF_PRE+'.'):
                    out[key] = str(val)
        if out: return out
    raise ValueError("Okänt payloadformat. Förväntar t.ex. {variables:[{technicalAddress|key, value}]} eller { '<TA>': <value> }")

def build_items_by_index(pvl_b64:str, idx:dict[str,int], kv:dict[str,str])->list[dict]:
    items=[]
    # Sätt PRICE_OK=0 först om den finns
    ok_ta = f"{REF_PRE}.PRICE_OK"
    if ok_ta in idx: items.append({'key': f"{pvl_b64}:{idx[ok_ta]}", 'value': '0'})
    # Lägg alla andra
    for ta,val in kv.items():
        if ta in idx:
            items.append({'key': f"{pvl_b64}:{idx[ta]}", 'value': str(val)})
    # Sätt PRICE_OK=1 sist om den finns
    if ok_ta in idx: items.append({'key': f"{pvl_b64}:{idx[ok_ta]}", 'value': '1'})
    return items

def write_items(tok:str, items:list[dict])->list:
    q = 'mutation ($variables:[VariableKeyValue!]!){ writeData(variables:$variables) }'
    d = post(q, {'variables': items}, tok)
    return d['writeData']

def verify_read(tok:str, pvl_b64:str, filter_prefix:str):
    q = 'query($p:String!){ data(path:$p){ variables{ technicalAddress value } } }'
    d = post(q, {'p':pvl_b64}, tok)['data']['variables']
    keep = [v for v in d if v['technicalAddress'].startswith(filter_prefix) and
            (v['technicalAddress'].endswith('PRICE_OK') or 'PRICE_RANK_0' in v['technicalAddress'])]
    for v in sorted(keep, key=lambda x:x['technicalAddress']):
        print(f"{v['technicalAddress']} = {v['value']}")

def main():
    payload_path = '/tmp/payload.json'
    if not os.path.exists(payload_path):
        print(f"❌ Hittar inte {payload_path}. Kör exo_price_rank.py först med --out - > {payload_path}", file=sys.stderr)
        sys.exit(2)
    with open(payload_path, 'r', encoding='utf-8') as f:
        raw = json.load(f)
    try:
        kv = normalize_payload(raw)
    except Exception as e:
        print(f"❌ Payload kunde inte normaliseras: {e}", file=sys.stderr); sys.exit(3)

    tok = login()
    idx = get_index_map(tok, PVL_B64)
    items = build_items_by_index(PVL_B64, idx, kv)
    res = write_items(tok, items)

    # Ev. felsökning: visa vilken nyckel som gav False
    bad = [(i,items[i]['key']) for i,x in enumerate(res) if str(x)!='True']
    ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"✅ [{ts}] Push skickad ({len(items)} nycklar). Antal FEL: {len(bad)}")
    if bad:
        for i,k in bad[:10]:
            print(f"   ⚠️  index {i} key={k} -> False")

    # Läs tillbaka ett urval
    verify_read(tok, PVL_B64, REF_PRE)

if __name__ == '__main__':
    main()
