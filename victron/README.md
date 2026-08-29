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

## Arkitektur – låt DESS vara hjärnan

Grundtanken för den fortsatta utvecklingen är att **inte bygga ett eget Dynamic ESS**. Victron DESS får fortsätta göra det svåra prognosarbetet: elpris, solprognos, förbrukningsprognos, framtida SOC-mål samt när energi bör laddas eller säljas.

Vårt system ska i stället göra det som DESS inte känner till: låta två externa batterisystem uppträda som extra distribuerad batterikapacitet bakom TT.

Principen blir:

1. **DESS bestämmer när energi är värdefull och vilket energiläge TT bör ha.**
2. **TT är master och referens för riktning, effekt och SOC.**
3. **244 och Katharina följer TT och förstorar i praktiken batteriet som DESS styr.**
4. **Followernas bidrag anpassas efter kapacitet, eget SOC, batterihälsa och säkerhetsgränser.**

En möjlig framtida test är att ange en något större batterikapacitet till DESS än TT:s verkliga cirka 80 kWh, exempelvis stegvis mot den sammanlagda användbara kapaciteten. Follower-systemen får då uppgiften att göra den virtuella extra kapaciteten verklig. Detta ska testas kontrollerat och är ännu inte infört.

## SOC-synkronisering – central designprincip

Follower-systemen bör inte tillåtas driva långt från master-SOC under normal drift. DESS har en prognostiserad tanke bakom TT:s SOC-mål och därför bör follower-systemens energiläge i möjligaste mån följa samma plan.

Rå SOC kan dock inte jämföras direkt eftersom systemen ska ha olika tillåtna min-SOC. Exempel på tänkt konfiguration:

- TT: min SOC cirka **14 %**
- 244: min SOC cirka **20 %**
- Katharina: min SOC cirka **24 %**

Dessa nivåer ska på sikt vara konfigurerbara i GUI och ska inte behöva hårdkodas i followerfunktionen.

### Normaliserad SOC

Varje batteris SOC översätts till hur långt batteriet befinner sig genom sitt **användbara SOC-område**:

```text
SOC_rel = (SOC - SOC_min) / (100 - SOC_min)
```

Därmed betyder:

- `SOC_rel = 0` = respektive batteris tillåtna botten
- `SOC_rel = 1` = fullt batteri

Exempel med min-SOC TT=14 %, 244=20 %, Katharina=24 %:

Om TT står på 50 % blir dess relativa SOC:

```text
(50 - 14) / (100 - 14) = 0,419
```

Motsvarande relativa energiläge blir då ungefär:

```text
TT          50,0 %
244         53,5 %
Katharina   55,8 %
```

Vid respektive botten motsvarar:

```text
TT 14 %  <=>  244 20 %  <=>  Katharina 24 %
```

Detta är bättre än ett fast SOC-offset eftersom hela det användbara området skalas proportionellt.

## Relationsbaserad followerreglering

Nuvarande funktioner använder fasta SOC-intervall och fasta effektfaktorer. Det är en fungerande och försiktig första version, men slutmodellen bör bli mer relationsbaserad.

Grundprincip:

```text
follower_target = TT_power × masterfaktor × SOC_korrigering
```

- **masterfaktor** beskriver followerns normala andel av TT:s effekt/kapacitet.
- **SOC-korrigering** modifierar denna andel kontinuerligt utifrån skillnaden mellan followerns och TT:s normaliserade SOC.

Exempel:

- follower ligger relativt **för högt** i SOC och TT urladdar → followern urladdar mer än normal andel
- follower ligger relativt **för lågt** i SOC och TT urladdar → followern urladdar mindre
- follower ligger relativt **för lågt** och TT laddar → followern laddar mer
- follower ligger relativt **för högt** och TT laddar → followern laddar mindre

Korrigeringen bör vara mjuk/proportionell i stället för att hoppa mellan fasta trappsteg vid exempelvis 40, 60 eller 80 % SOC.

### Asymmetrisk SOC-korrigering

För låg SOC ska betraktas som mer akut än för hög SOC.

Om en follower halkar ned under önskat relativt energiläge bör systemet snabbare:

- minska/blockera dess urladdning
- förstärka dess andel av kommande laddning

Om followern ligger för högt i SOC är det normalt mindre akut. Den ska återföras mot masterläget, men lugnare eftersom ett tillfälligt energiöverskott normalt inte innebär samma risk för cellerna.

Utöver normal proportionalreglering bör det finnas en **katastrof-/återhämtningszon** vid stor SOC-avvikelse eller när en follower närmar sig sin säkerhetsgräns.

## Framtida GUI-parametrar

Målet är att styrningen inte ska behöva ändras genom redigering av JavaScript. Parametrar ska på sikt kunna justeras från GUI.

Tänkbara parametrar per batterisystem:

- min SOC
- grund-/masterfaktor
- styrka på SOC-korrigering vid för låg SOC
- styrka på SOC-korrigering vid för hög SOC
- maximal laddningseffekt
- maximal urladdningseffekt
- katastrof-/återhämtningsgräns
- eventuell tillfällig boost/reducering av followerbidrag

Det gör det möjligt att exempelvis tillfälligt låta 244 bära en större del av TT:s effekt utan att koppla bort övriga skydd och SOC-regler.

## När master når sitt ändläge

Ett särskilt framtida fall är när TT når sin fysiska min-SOC och därför inte längre kan urladda trots att DESS ekonomiska plan i princip skulle kunna motivera fortsatt urladdning ur den samlade batteriparken.

Followerregleringen behöver därför på sikt kunna skilja mellan:

- TT:s momentana fysiska möjlighet att lämna effekt
- DESS övergripande intention för det virtuella större batteriet

Detta kan kräva en särskild `master saturated`-logik där follower-systemen under kontrollerade former kan bära mer av den återstående virtuella batterikapaciteten när TT själv ligger vid sin gräns.

## Balanseringsladdning – använd DESS i stället för egen algoritm

En viktig arkitekturvinst är att vi sannolikt **inte behöver skapa en separat balanseringsladdningsalgoritm** för den distribuerade batteriparken.

När DESS planerar ett högt SOC-mål/balanseringsläge för TT bör follower-systemen, genom den normaliserade SOC-regleringen, automatiskt följa med upp mot motsvarande relativa laddningstillstånd.

Därmed kan Victrons befintliga planering även ge follower-systemen möjlighet till hög SOC och balansering, samtidigt som varje batteris egna BMS/balancer sköter cellnivån.

Detta ska verifieras i verklig drift innan det betraktas som färdig funktion.

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

Den virtuella elmätaren är inte återkopplingen i den nuvarande followerregulatorn. Followerns effektbörvärde skapas från TT-data och lokal SOC/PV-logik och skrivs direkt till External control-börvärdet.

## Follower-systemens olika batterier

### Håltorp 244

24 V-system med två 12 V SBL-batterier i serie. Batterierna har relativt få cykler men har fått en obalans mellan de två 12 V-batterierna. Followerregleringen kan därför vara relativt tillåtande, men låg SOC skyddas.

### Katharina

48 V-system med äldre reparerat Fronius/Murata-batteri. Flera cellgrupper har historiskt varit problematiska och ett paket har fått omfattande cellgruppsbyte. Regleringen ska därför vara försiktigare, framför allt vid urladdning och låg SOC.

## Observationsfas 2026-08-28

Innan relationsregleringen införs ska nuvarande followerkod få arbeta ostört i ungefär **1–2 dygn** så att verkligt beteende kan observeras.

Utgångsläget på kvällen 2026-08-28 var ungefär:

```text
TT          14,8 %   (min cirka 14 %)
244         80,8 %
Katharina   60 %
```

Den stora SOC-spridningen är inte ett önskat framtida normaltillstånd, men är värdefull som test av hur den nuvarande första versionen beter sig över flera pris-, ladd- och urladdningscykler.

Vi ska därför inte optimera bort observationsdata genom att ändra algoritmen för tidigt.

## Nästa steg

1. Låt nuvarande followerfunktioner gå 1–2 dygn och observera SOC-utvecklingen.
2. Spara/logga TT, 244 och Katharinas SOC så att även normaliserad SOC kan jämföras över tid.
3. Ersätt därefter fasta SOC-trappsteg med en relationsbaserad och proportionell SOC-korrigering.
4. Flytta min-SOC, grundfaktor, korrigeringsstyrka och effektgränser till konfigurerbara variabler/GUI.
5. Testa kontrollerat om DESS kan ges en något större virtuell batterikapacitet än TT:s verkliga cirka 80 kWh.
6. Utveckla logik för när TT når fysisk min/max-SOC men follower-systemen fortfarande har användbar kapacitet.
7. Verifiera att DESS höga SOC-/balanseringsplaner ger önskad balanseringsmöjlighet även för follower-systemen.
8. Behåll Git-historiken som facit för varje ändring i styrningen.
