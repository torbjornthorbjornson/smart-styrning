# Victron – samkörning av TT, Håltorp 244 och Katharina

Senast uppdaterad: 2026-08-28

## Syfte

Detta bibliotek dokumenterar samkörningen av tre Victron-system med Node-RED och MQTT.

- **TT** – masteranläggning. Har den verkliga mätningen och publicerar styrdata.
- **Håltorp 244** – follower, MultiPlus-II 24/3000/70-32.
- **Katharina** – follower, MultiPlus-II 48/5000/70-50.

Målet är att 244 och Katharina ska följa TT:s laddning/urladdning med en SOC-anpassad andel av TT:s effekt.

## Styrprincip

TT publicerar momentan inverter-/batterieffekt via MQTT:

```text
stenhus/energy/TT/inverter_power
```

Follower-systemen tar emot värdet i Node-RED och beräknar ett lokalt effektbörvärde utifrån bland annat:

- lokal SOC
- laddning eller urladdning
- dag/natt baserat på PV-effekt
- dödband
- tidsfilter vid riktningsbyte
- olika effektfaktorer beroende på SOC

Konvention:

- TT-effekt **positiv** = TT laddar
- TT-effekt **negativ** = TT urladdar
- followerns effektbörvärde använder samma tecken

## Victron External control

Follower-systemen kör **External control**.

Node-RED-noden som visas som:

```text
ESS power setpoint phase L1 (W)
```

skriver till Victrons DBus-objekt:

```text
/Hub4/L1/AcPowerSetpoint
```

I denna installation, där inget är anslutet på AC-out, används detta i praktiken som effektkommando till Multi på AC-in-sidan.

- negativt värde = invertera/mata ut effekt på AC-in
- positivt värde = ta effekt från AC-in/ladda

Benämningen "ESS power setpoint" i Node-RED är därför lätt att misstolka när systemet kör External control.

## Viktig driftupptäckt 2026-08-28

Followern kan få korrekt effektbörvärde utan att Multi faktiskt laddar eller urladdar.

Orsaken som konstaterades var att följande tillstånd behöver hållas på `0`:

```text
Disable charge = 0
Disable feed-in = 0
```

När dessa manuellt injicerades med värdet `0` började styrningen fungera igen.

Nuvarande lösning är att Node-RED periodiskt återinjicerar `0` till båda objekten. Detta fungerar som watchdog och säkerställer att laddning och feed-in fortsätter vara tillåtna.

Detta är också ett möjligt framtida styrmedel:

| Önskat läge | Disable charge | Disable feed-in |
| --- | ---: | ---: |
| Normal follower | 0 | 0 |
| Blockera laddning | 1 | 0 |
| Blockera urladdning/feed-in | 0 | 1 |
| Blockera båda riktningar | 1 | 1 |

Vid framtida vidareutveckling bör watchdoggen skriva ett **önskat tillstånd från variabler** i stället för att alltid skriva `0`. Då kan samma mekanism användas för att avsiktligt aktivera/inaktivera laddning och urladdning.

## Virtuell elmätare

244 och Katharina använder virtuella elmätare. Dessa simulerar nätvärden men sitter inte i fastighetens verkliga inmatningspunkt.

Därför ska VRM:s summerade värden för exempelvis konsumtion, från nät och till nät **inte användas som en fullständig fysisk energibalans för fastigheten**. Den virtuella mätaren har inte kännedom om allt som sker i TT eller i övriga delar av installationen.

## Follower-systemens olika batterier

### Håltorp 244

24 V-system med två 12 V SBL-batterier i serie. Batterierna har relativt få cykler men har fått en obalans mellan de två 12 V-batterierna. Followerregleringen kan därför vara relativt tillåtande, men låg SOC skyddas.

### Katharina

48 V-system med äldre reparerat Fronius/Murata-batteri. Flera cellgrupper har historiskt varit problematiska och ett paket har fått omfattande cellgruppsbyte. Regleringen ska därför vara försiktigare, framför allt vid urladdning och låg SOC.

## Nästa steg

1. Spara aktuella Node-RED-exporter för TT, 244 och Katharina i detta bibliotek.
2. Dokumentera MQTT-topics separat.
3. Dokumentera followerfunktionerna och deras SOC-faktorer.
4. Bygga variabelstyrning för `Disable charge` och `Disable feed-in` när den nuvarande watchdoglösningen har verifierats stabil över tid.
5. Använd Git-historiken som facit för ändringar i styrningen.
