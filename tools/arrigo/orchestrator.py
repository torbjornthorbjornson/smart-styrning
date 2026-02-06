# --- Orchestrator state ---
last_pushed = {
    "day": None,
    "stamp": None,
}

def main():
    token = arrigo_login()
    log("🔌 Orchestrator startad (stateful, stamp-safe)")

    while True:
        try:
            vals, idx = read_vals_and_idx(token)
        except requests.HTTPError as e:
            if e.response is not None and e.response.status_code == 401:
                log("🔑 401 → relogin")
                token = arrigo_login()
                time.sleep(2)
                continue
            raise

        req  = to_int(vals.get(TA_REQ))
        ack  = to_int(vals.get(TA_ACK))
        day  = to_int(vals.get(TA_DAY))
        stamp = to_int(vals.get("Huvudcentral_C1.PRICE_STAMP"), -1)

        log(f"REQ={req} ACK={ack} DAY={day} STAMP={stamp}")

        # --- Vänta tills EXOL verkligen begär ---
        if req != 1 or ack != 0:
            time.sleep(SLEEP_SEC)
            continue

        # --- Dublettskydd: samma dag + samma stamp ---
        if last_pushed["day"] == day and last_pushed["stamp"] == stamp:
            log("⏸️ Samma DAY+STAMP redan pushad – väntar")
            time.sleep(SLEEP_SEC)
            continue

        # --- Bestäm lokalt dygn (FACIT) ---
        target_day = today_local_date() + timedelta(days=day)

        rows = db_fetch_prices_for_day(target_day)

        if len(rows) != 96:
            log(f"⏳ {target_day}: DB har {len(rows)}/96 → väntar")
            time.sleep(SLEEP_SEC)
            continue

        log(f"📤 Push dag={target_day} stamp={stamp}")

        rank, ec, ex, slot_price = build_rank_and_masks(rows)

        oat_yday = daily_avg_oat(target_day - timedelta(days=1))
        oat_tmr  = daily_avg_oat(target_day + timedelta(days=1))

        push_to_arrigo(
            rank, ec, ex,
            target_day,
            oat_yday,
            oat_tmr,
            slot_price
        )

        # --- Ack: EN gång ---
        write_ta(token, idx, TA_ACK, 1)
        log("✅ PI_PUSH_ACK=1")

        # --- Minns vad vi pushade ---
        last_pushed["day"]   = day
        last_pushed["stamp"] = stamp

        time.sleep(SLEEP_SEC)
