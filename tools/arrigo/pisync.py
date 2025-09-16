#!/usr/bin/env python3
import os, requests, sys

LOGIN = os.environ['ARRIGO_LOGIN_URL']
URL   = os.environ['ARRIGO_GRAPHQL_URL']
USER  = os.environ['ARRIGO_USERNAME']
PWD   = os.environ['ARRIGO_PASSWORD']
PVL   = os.environ['ARRIGO_PVL_B64']
VERIFY = (os.getenv('ARRIGO_INSECURE','0') != '1')

def login():
    r = requests.post(LOGIN, json={'username':USER,'password':PWD}, timeout=20, verify=VERIFY)
    r.raise_for_status()
    tok = r.json()['authToken']
    s = requests.Session()
    s.headers.update({'Authorization':f'Bearer {tok}','Content-Type':'application/json'})
    return s

def read_vars(s):
    q = 'query($p:String!){ data(path:$p){ variables{ technicalAddress value } } }'
    r = s.post(URL, json={'query':q,'variables':{'p':PVL}}, timeout=30, verify=VERIFY)
    r.raise_for_status()
    V = r.json()['data']['data']['variables']
    idx = {v['technicalAddress']:i for i,v in enumerate(V)}
    val = {v['technicalAddress']:v['value'] for v in V}
    return idx,val

def write_idx(s, idx, value):
    m = 'mutation($v:[VariableKeyValue!]!){ writeData(variables:$v) }'
    body={'query':m,'variables':{'v':[{'key':f'{PVL}:{idx}','value':str(value)}]}}
    r = s.post(URL,json=body,timeout=20,verify=VERIFY)
    r.raise_for_status()

def main():
    s = login()
    idx,val = read_vars(s)

    ta_req = next(k for k in idx if k.endswith('.PI_PUSH_REQ'))
    ta_ack = next(k for k in idx if k.endswith('.PI_PUSH_ACK'))

    req, ack = val[ta_req], val[ta_ack]
    print(f"REQ={req} ACK={ack}")

    if str(req) not in ("1","true","True"):
        print("Ingen push begärd.")
        return

    # TODO: här ska dina parametrar pushas (PRICE_OK, RANK mm.)

    write_idx(s, idx[ta_ack], 1)
    print("ACK=1 satt → controllern ska nu nolla REQ.")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("❌ Fel:", e)
        sys.exit(1)
