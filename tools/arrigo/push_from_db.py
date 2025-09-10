#!/usr/bin/env python3
import os, pymysql, requests
from datetime import datetime, timedelta, time
import pytz

UTC=pytz.UTC
STHLM=pytz.timezone("Europe/Stockholm")

def local_day_to_utc_window(d):
    lm = STHLM.localize(datetime.combine(d, time(0,0)))
    return lm.astimezone(UTC).replace(tzinfo=None), (lm+timedelta(days=1)).astimezone(UTC).replace(tzinfo=None)

def get_prices_for(local_day):
    u0,u1 = local_day_to_utc_window(local_day)
    conn = pymysql.connect(read_default_file="/home/runerova/.my.cnf",
                           database="smart_styrning",
                           cursorclass=pymysql.cursors.DictCursor)
    prices=[None]*24
    with conn, conn.cursor() as cur:
        cur.execute("""SELECT datetime, price FROM electricity_prices
                       WHERE datetime >= %s AND datetime < %s
                       ORDER BY datetime""", (u0,u1))
        for r in cur.fetchall():
            h=r["datetime"].replace(tzinfo=UTC).astimezone(STHLM).hour
            prices[h]=float(r["price"])
    if any(v is None for v in prices):
        raise SystemExit("Ofullständiga DB-priser (saknar timmar)")
    return prices

def ranks_from(prices):
    order = sorted(range(24), key=lambda h: (prices[h], h))
    rank=[None]*24
    for r,h in enumerate(order): rank[h]=r
    return rank

# --- dagval ---
when=os.getenv("RANK_WHEN","today").lower()
today_local = datetime.now(UTC).astimezone(STHLM).date()
day = today_local if not when.startswith("tom") else (today_local + timedelta(days=1))

prices = get_prices_for(day)
rank   = ranks_from(prices)

# --- Arrigo ---
VERIFY=(os.environ.get('ARRIGO_INSECURE')!='1')
LOGIN=os.environ['ARRIGO_LOGIN_URL']
GQL  =os.environ['ARRIGO_GRAPHQL_URL']
USER =os.environ['ARRIGO_USER']
PASS =os.environ['ARRIGO_PASS']
PVL  =os.environ['ARRIGO_PVL_PATH']  # base64
REF  =os.getenv('ARRIGO_REF_PREFIX','Huvudcentral_C1')

tok=requests.post(LOGIN,json={'username':USER,'password':PASS},
                  verify=VERIFY,timeout=30).json()['authToken']
hdr={'Authorization':f'Bearer {tok}','Content-Type':'application/json'}

# Hämta index-karta
qidx='query($p:String!){ data(path:$p){ variables{ technicalAddress } } }'
vars_=requests.post(GQL,headers=hdr,json={'query':qidx,'variables':{'p':PVL}},
                    verify=VERIFY,timeout=30).json()['data']['data']['variables']
index={v['technicalAddress']:i for i,v in enumerate(vars_)}

def key_for(ta):
    i=index.get(ta)
    return f"{PVL}:{i}" if i is not None else None

items=[]

# Gate av
k_ok=key_for(f"{REF}.PRICE_OK")
if k_ok: items.append({'key':k_ok,'value':"0"})

# Rank -> båda formerna som finns
for h,val in enumerate(rank):
    for ta in (f"{REF}.PRICE_RANK_{h:02d}", f"{REF}.PRICE_RANK({h:02d})"):
        k=key_for(ta)
        if k: items.append({'key':k,'value':str(val)})

# Stämpel & area (om variablerna finns i PVL)
for ta,val in ((f"{REF}.Price_Stamp", day.strftime("%Y-%m-%d")),
               (f"{REF}.Price_Area",  "SE3")):
    k=key_for(ta)
    if k: items.append({'key':k,'value':val})

# Skriv batch
mut='mutation ($variables:[VariableKeyValue!]!){ writeData(variables:$variables) }'
r=requests.post(GQL,headers=hdr,json={'query':mut,'variables':{'variables':items}},
                verify=VERIFY,timeout=60).json()
res=r['data']['writeData']
bad=[items[i]['key'] for i,x in enumerate(res) if str(x)!='True']
print("✅ Allt True ("+str(len(res))+" nycklar)") if not bad else print("❌ False:",bad)

# Gate på
if k_ok:
    requests.post(GQL,headers=hdr,json={'query':mut,'variables':{'variables':[{'key':k_ok,'value':"1"}]}},
                  verify=VERIFY,timeout=30)
