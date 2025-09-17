#!/usr/bin/env python3
import os, sys, subprocess, requests
from pathlib import Path

# --- fallback: ladda ~/.arrigo.env manuellt om env saknas ---
envf = Path.home() / ".arrigo.env"
if envf.exists():
    for line in envf.read_text().splitlines():
        line=line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k,v = line.split("=",1)
        v = v.strip().strip('"').strip("'")
        os.environ.setdefault(k.strip(), v)

def need(*names):
    """Hämta första env-variabel som finns"""
    for n in names:
        v = os.getenv(n)
        if v:
            return v
    print(f"❌ Saknar någon av {names}")
    sys.exit(1)

LOGIN = need('ARRIGO_LOGIN_URL')
URL   = need('ARRIGO_GRAPHQL_URL')
USER  = need('ARRIGO_USERNAME','ARRIGO_USER')
PWD   = need('ARRIGO_PASSWORD','ARRIGO_PASS')
PVL   = need('ARRIGO_PVL_B64','ARRIGO_PVL_PATH')
VERIFY = (os.getenv('ARRIGO_INSECURE','0') != '1')

def login():
    r = requests.post(LOGIN, json={'username':USER,'password':PWD}, timeout=20, verify=VERIFY)
    r.raise_for_status()
    j = r.json()
    tok = j.get('authToken') or j.get('token') or j.get('access_token')
    if not tok:
        sys.exit(f"❌ Login svarade utan token: {j}")
    s = requests.Session()
    s.headers.update({'Authorization':f'Bearer {tok}','Content-Type':'application/json'})
    return s

Q_READ = 'query($p:String!){ data(path:$p){ variables{ technicalAddress value } } }'
M_WRITE= 'mutation($v:[VariableKeyValue!]!){ writeData(variables:$v) }'

def read_vars(s):
    r = s.post(URL, json={'query':Q_READ,'variables':{'p':PVL}}, timeout=30, verify=VERIFY)
    r.raise_for_status()
    V = r.json()['data']['data']['variables']
    idx = {v['technicalAddress']: i for i,v in enumerate(V)}
    val = {v['technicalAddress']: v.get('value') for v in V}
    return V, idx, val

def write_idx(s, idx, value):
    body={'query':M_WRITE,'variables':{'v':[{'key':f'{PVL}:{idx}','value':str(value)}]}}
    r = s.post(URL, json=body, timeout=20, verify=VERIFY)
    r.raise_for_status()

def pbool(x):
    return str(x).strip().lower() in ('1','true','on','yes')

def run_push_from_db():
    """Kör push_from_db.py i samma venv"""
    base = Path(__file__).resolve().parent
    script = base / "push_from_db.py"
    python = Path(sys.executable)
    print(f"▶️  Kör {script} ...")
    res = subprocess.run([python, str(script)], capture_output=True, text=True)
    print(f"↩️  Exit code: {res.returncode}")
    if res.stdout:
        print("STDOUT:\n", res.stdout.strip())
    if res.stderr:
        print("STDERR:\n", res.stderr.strip())

def main():
    print("🔄 Startar PiSync...")
    s = login()
    V,IDX,VAL = read_vars(s)

    try:
        ta_req = next(v['technicalAddress'] for v in V if v['technicalAddress'].endswith('.PI_PUSH_REQ'))
        ta_ack = next(v['technicalAddress'] for v in V if v['technicalAddress'].endswith('.PI_PUSH_ACK'))
    except StopIteration:
        print("❌ Hittar inte .PI_PUSH_REQ/.PI_PUSH_ACK i PVL.")
        for v in V[:10]:
            print("Exempel-TA:", v['technicalAddress'])
        sys.exit(1)

    i_req, i_ack = IDX[ta_req], IDX[ta_ack]
    req, ack = pbool(VAL[ta_req]), pbool(VAL[ta_ack])
    print(f"📊 Status före → REQ={req} ACK={ack}")

    if not req:
        print("ℹ️ Ingen push begärd (REQ=0). Klart.")
        return

    # --- kör riktiga pushen ---
    run_push_from_db()

    # --- kvittera ---
    write_idx(s, i_ack, 1)
    print("✅ ACK=1 satt. Controllern ska nu nolla REQ.")

    _,_,VAL2 = read_vars(s)
    print(f"📊 Status efter → REQ={pbool(VAL2[ta_req])} ACK={pbool(VAL2[ta_ack])}")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("❌ Fel:", e)
        sys.exit(1)
