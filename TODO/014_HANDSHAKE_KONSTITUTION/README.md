🧭 Arrigo ↔ Pi ↔ EXOL
Handshake, prisflöde, planer, status & UI-texter

(Definitiv referens – spara denna)

0. Grundprincip (viktigast av allt)

EXOL är MASTER.
Pi är SLAV.
Arrigo är transport.

Pi:

reagerar endast på REQ + DAY

levererar exakt det som efterfrågas

kvitterar med ACK

gör inga antaganden

EXOL:

styr flödet

tolkar status

visar begriplig UI-text

ansvarar för ALL logik

1. Centrala signaler (gemensamt språk)

Signal	Ägare	Betydelse
PI_PUSH_REQ	EXOL	“Jag väntar på data”
PI_PUSH_ACK	Pi	“Jag har just levererat”
PI_PUSH_DAY	EXOL	0=today, 1=tomorrow
TD_READY	EXOL	Dagens priser finns
TM_READY	EXOL	Morgondagens priser finns
PRICE_STAMP	Pi	Datum för leveransen
PRICE_STAMP_TD/TM	EXOL	Senast mottaget datum

2. Absolut regelbok (får ALDRIG brytas)

2.1 ACK-regeln

Pi sätter ACK = 1 exakt EN gång per leverans

EXOL nollar ACK

Pi rör aldrig ACK igen

2.2 REQ-regeln

EXOL sätter REQ

Pi läser REQ

Pi rör aldrig REQ

2.3 DAY-regeln

EXOL styr DAY

Pi tolkar DAY

Pi rör aldrig DAY

🔒 Om Pi ändrar REQ/DAY → systemet är trasigt

3. Normal dygnssekvens (priser)

3.1 Systemstart / tomt läge

Tillstånd

TD_READY = 0
TM_READY = 0
REQ = 1
DAY = 0
ACK = 0

UI-text

🔄 Begär dagens elpriser…

3.2 Leverans: TODAY

Pi gör

pushar dagens priser

sätter ACK = 1

EXOL gör

TD_READY = 1
ACK = 0
DAY = 1
REQ = 1

UI-text

✅ Dagens elpriser mottagna
🔄 Begär morgondagens elpriser…

3.3 Väntan före kl. 15

Tillstånd

TD_READY = 1
TM_READY = 0
REQ = 1
DAY = 1
ACK = 0

UI-text

⏳ Väntar på att morgondagens elpriser publiceras…

3.4 Leverans: TOMORROW

Pi gör

pushar morgondagens priser

sätter ACK = 1

EXOL gör

TM_READY = 1
ACK = 0
REQ = 0

UI-text

✅ Morgondagens elpriser mottagna
🟢 Alla prisdata tillgängliga

4. Vad händer efter kl. 15?

Ingenting. Och det är korrekt.

Efter att:

TD_READY = 1

TM_READY = 1

REQ = 0

…är systemet klart för dygnet.

🔒 REQ ska INTE stå kvar på 1.
🔒 DAY ska INTE växla.

5. Midnattsrotation (00:00)

EXOL gör

Kopierar TM → TD

Nollar TM_READY

Sätter:

REQ = 1
DAY = 1

UI-text

🔄 Nytt dygn – begär kommande elpriser…

6. UI-hjälptexter – Prisflöde (EXOL)

Grundstatus
Tillstånd	UI-text
REQ=1, DAY=0	Begär dagens elpriser
REQ=1, DAY=1, TM_READY=0	Väntar på morgondagens elpriser
TD_READY=1, TM_READY=1	Alla elpriser mottagna
TD_READY=0	Inga giltiga elpriser tillgängliga

7. Heat & VV – plantriggers (översikt)

Triggers
Trigger	Orsak
HEAT_PLAN_TRIG	Ny prisdata TD eller TM
VVP_PRICE_TRIG	Ny prisdata TD eller TM
HEAT_PLAN_CHANGED	Ny heatplan skapad
VV_PLAN_CHANGED	Ny VV-plan skapad

8. UI-hjälptexter – Heat & VV

Heat
Tillstånd	UI-text
HEAT_PLAN_TRIG=1	🔄 Värmeplan uppdateras
HEAT_PLAN_CHANGED=1	✅ Ny värmeplan beräknad
HEAT_USE_PLAN=0	⚠️ Värme körs utan plan
HEAT_USE_PLAN=1	🟢 Värme körs enligt plan

Varmvatten (VV)
Tillstånd	UI-text
VVP_PRICE_TRIG=1	🔄 VV-plan uppdateras p.g.a. nya priser
VVP_PLAN_TRIG=1	🔄 VV-plan beräknas
VVP_USE_PLAN=1	🟢 VV körs enligt plan
T_top < VV_MIN_SAFE	🚨 VV säkerhetsladdning aktiv

9. Diagnostik – samlad klartext (DIAG_PUSH)

Exempelvärden

"Begär_dagens_priser"

"Väntar_morgondagens_priser"

"Alla_priser_mottagna"

"Duplicerad_stamp_ignorerad"

"Saknar_prisdata"

🔑 DIAG_PUSH ska alltid gå att läsa högt och förstå direkt

10. Kontrollfrågor (för felsökning)

Ställ alltid dessa i ordning:

Vem satte REQ?

Vem satte ACK?

Vilken DAY gällde?

Vilken PRICE_STAMP levererades?

Matchar STAMP TD/TM?

Om något inte går att svara på → buggen är där.

11. Slutord (viktigt)

Det du beskrev i text tidigare var:

logiskt

korrekt

robust

lätt att felsöka

Det här dokumentet är nu din systemkonstitution.
Ingen kod får skrivas som bryter mot detta.

