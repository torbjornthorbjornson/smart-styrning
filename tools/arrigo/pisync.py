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

    # --- Här skulle du normalt pusha PRICE_OK, RANK, masker mm. ---
    write_idx(s, i_ack, 1)
    print("✅ ACK=1 satt. Controllern ska nu nolla REQ.")

    # Läs tillbaka för att verifiera
    _,_,VAL2 = read_vars(s)
    print(f"📊 Status efter → REQ={pbool(VAL2[ta_req])} ACK={pbool(VAL2[ta_ack])}")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("❌ Fel:", e)
        sys.exit(1)
