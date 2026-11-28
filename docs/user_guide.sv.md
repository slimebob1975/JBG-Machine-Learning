# JBG Machine Learning

Programmet tränar maskininlärningsmodeller som sorterar rader i en tabell i
klasser. Det lär sig av rader som redan har en klass och kan sedan föreslå
klass för rader som saknar en. Data kommer antingen från en tabell i SQL
Server eller från en CSV-fil.

Vid träningen jämför programmet flera algoritmer och kombinationer av
förbehandling, utvärderar dem på data som hållits utanför träningen och
sparar den bästa modellen. Modellen kan sedan användas för prediktion, det
vill säga för att klassificera nya rader.

## Arbetsgången

Flikarna följer arbetsgången från vänster till höger:

1. **Projekt**: skapa eller öppna ett projekt.
2. **Dataset**: lägg till data, ange kolumnroller och validera.
3. **Konfiguration**: välj inställningar för maskininlärningen.
4. **Träning**: starta en träningskörning och följ den.
5. **Resultat**: granska hur bra modellen blev.
6. **Modeller**: välj den modell som ska användas.
7. **Prediktion**: klassificera rader som saknar klass.

Raden under rubriken visar det pågående arbetet: öppet projekt, aktivt
träningsdataset, konfigurationen som är vald för körning och vald modell.
Programmet öppnas på fliken Översikt, och rubriken ”JBG Machine Learning”
leder dit.
Språket väljs under fliken Inställningar längst till höger.

Knappar som utför en åtgärd är gröna när de kan användas och röda, nedtonade,
när det ännu inte finns något att göra, till exempel **Spara** innan något
har ändrats. Håll muspekaren över en röd knapp för att se varför. Orange
knappar kan användas men går inte att ångra, till exempel **Ta bort**. På långa
sidor finns sidans huvudknapp både överst och längst ned. Långa listor i
vänsterpanelen visar sju rader åt gången (Körhistorik tio), de senaste först,
med **Föregående** och **Nästa** nere till höger.

En vy med data, konfigurationsinställningar eller resultat har knappen
**Exportera** under tabellerna, till höger. Listorna i vänsterpanelen
exporteras inte. Knappen ger vyns tabeller med alla rader, även de som visas en sida i taget, i formatet som
väljs under Inställningar: Excel med en flik per tabell, eller CSV med
tabellerna efter varandra under sina rubriker (semikolon och decimalkomma, som
svenska Excel läser). Vyn Mörkertal ger hela beräkningen: inställningar,
skattningar, tillväxt, beräkningstabellen och förväxlingsmatriserna.

## Översikt

Överst alla dina projekt: träningskörningar, bearbetade rader, jämförda
modeller och modeller i bruk, var och en med hur många som finns i det öppna
projektet. Dessutom körningar per vecka (lyckade och misslyckade) och
bearbetade rader per projekt, med det öppna projektet markerat. Bearbetade
rader och jämförda modeller registreras när en körning blir klar, så
körningar från före den här versionen räknas som noll.

Nedanför det öppna projektet: aktivt träningsdataset, vald konfiguration,
senaste körningar och projektets modeller, med länkar till flikarna där de
ändras. Modellkvalitet per träningskörning (konfigurationens mått) med medel
av de tre senaste, bearbetade rader per vecka och de senaste körningarna med
länkar till deras resultat. Utan öppet projekt visas bara den övre delen.

## Projekt

Allt arbete hör till ett projekt. Ange namn och källa (SQL eller CSV) och
välj **Skapa projekt**. Källan kan inte ändras efteråt. Markera projektet i
listan och välj **Öppna projekt** för att arbeta med det. Krysset vid
projektnamnet i raden under rubriken stänger projektet.

**Ta bort projektet…** tar bort projektet med allt i det: dataset,
konfigurationer, körningar med resultat och prediktioner, och modeller. Skriv
projektets namn för att bekräfta. Knappen **Ta bort** blir orange när namnet
stämmer. Tabeller i SQL Server berörs inte.

**Gallra körningar** finns för det öppna projektet. Ange hur många av de
senaste körningarna som ska behållas och hur gamla körningar som alltid får
stå kvar (20 körningar och 30 dagar som förslag). En körning tas bara bort om
den bryter mot båda reglerna, och tas då bort helt: logg, resultat och posten i
Körhistorik. Körningar som tränade en modell i fliken Modeller finns kvar,
liksom köade och pågående körningar. **Visa vad som skulle gallras** visar
listan, och inget tas bort förrän du väljer **Gallra nu**.

## Dataset

Ett projekt kan ha flera dataset. Varje dataset har en roll: Träning,
Prediktion eller Blandad.

- **CSV-projekt**: välj en fil (högst 25 MB, med rubrikrad – avgränsaren
  och teckenkodningen, UTF-8 eller Windows-1252 som Excel sparar, känns igen
  automatiskt), ange namn och roll och välj **Ladda upp**. Med **Lägg till
  från Excel** väljer du en arbetsbok (.xlsx), och i nästa steg de flikar som
  ska bli dataset, vart och ett med namn och roll (till exempel en flik för
  träning och en för prediktion). Flikens första rad är rubrikrad, formler ger
  de värden Excel senast räknade fram och tomma rader utelämnas. Varje flik
  läggs till som ett CSV-dataset. Äldre .xls-filer behöver sparas som .xlsx.
- **SQL-projekt**: logga in med användarnamn och lösenord eller med
  Windows-autentisering. Välj katalog och roll, **Visa tabeller**, välj
  tabell, ange namn och välj **Registrera**. Inloggningen finns bara i
  serverns minne, så efter en omstart av servern loggar du in igen.

Namnet fylls i med filens namn utan ”.csv” eller tabellens namn utan schema.
Det kan ändras, och det följer valet av fil eller tabell tills du skriver ett
eget namn.

Välj **Aktivera för träning** på det dataset som modellen ska tränas på.
Ett tränings- eller blandat dataset kan byta till den andra rollen med **Byt
roll till …**. Kolumnrollerna och valideringen behålls. Träningen använder
bara rader med klass, och ett blandat dataset kan också predikteras på fliken
Prediktion. Prediktionsdataset kan inte byta roll.
Under datasetet finns vyerna Förhandsgranskning, Profil, Klasser,
Kolumnroller och Visualisering.

I vyn Profil ger **Exportera specifikation för fejkdata (JSON)** en beskrivning
av datasetet som en generator kan skapa liknande data från, utan riktiga rader:
fördelningen för varje kolumn och för varje klass, och korrelationerna mellan
de numeriska kolumnerna. Värden som finns på färre än 0,1 % av raderna slås
ihop till Övrigt, tal anges som kvantiler från 0,1 till 99,9 % i stället för
exakta min och max, och fritext beskrivs bara med längder. Typen tas från
kolumnrollerna om de finns. Stora SQL-tabeller beskrivs från ett slumpvis
urval på 100 000 rader.

**Visualisering** ritar ett urval av datasetets rader i två dimensioner. Välj
metod (PCA, t-SNE eller MDS), antal kluster för K-means (eller inga), antal
rader i urvalet (100 till 3000, 1000 som standard, MDS högst 2000) och hur
urvalet dras: slumpvis med samma andel av varje klass (standard), slumpvis,
eller de första raderna. Välj sedan **Rita**. Bilden använder de numeriska
och kategoriska kolumnerna från kolumnrollerna, så de behöver vara angivna.
K-means grupperar raderna på alla dessa kolumner, inte på bilden, så klustren
är desamma oavsett metod. Färgen visar klassen och formen klustret, eller
tvärtom med **Färgen visar**. Varje klassvärde, även saknad klass, får en egen
form. Rader utan klass är grå när färgen visar klassen. **Punktstorlek** gör
punkterna större eller mindre. Håll muspekaren över en
punkt för att se radens värden, även fritext- och datumkolumner som inte
används i beräkningen. Samma inställningar ger samma bild. Bilden och dess
inställningar finns kvar när du byter vy och kommer tillbaka, för varje dataset.

**Avvikelser** markerar de mest ovanliga raderna med en röd ring, den andel
som anges (2 % som standard, 0,5 till 10 %). Isolation Forest mäter hur lätt
en rad skiljs från de andra, och Local Outlier Factor hur mycket glesare det
är runt raden än runt dess grannar. Båda räknas på alla förberedda kolumner,
och avvikelsepoängen visas när muspekaren hålls över punkten. **Linjer mellan
klustren** ritar streckade linjer där bildens K-means-kluster möts. Linjerna
räknas fram i bilden, inte i data, så med t-SNE och MDS, där avstånden är
förvrängda, är de en illustration.

Panelen **Byt namn på datasetet** under listan ger det valda datasetet ett
nytt namn med **Byt namn**. Bara namnet ändras: filen eller tabellen,
kolumnrollerna och körningarna finns kvar, och körningarna visar det nya
namnet. Namnet får inte redan finnas i projektet, oavsett stora och små
bokstäver.

**Ta bort datasetet…** tar bort datasetet med dess kolumnroller, alla
versioner av dess CSV-fil (även korrigerade), träningskörningarna på det,
modellerna som tränats på det och prediktionerna som gjorts på det eller med
de modellerna. Konfigurationerna finns kvar: de hör inte till något dataset.

### Kolumnroller

Kolumnrollerna hör till träningsdatasetet och gäller alla körningar med det.
Exakt en kolumn ska vara ID-kolumn och exakt en klasskolumn, och minst en
kolumn ska vara en variabel: numerisk variabel, textvariabel eller
kategorisk variabel. Kolumner som ignoreras används inte.

I SQL-dataset måste ID-kolumnen vara en heltalskolumn (int, bigint, smallint
eller tinyint), till exempel inte uniqueidentifier eller text. Annars visas en
varning under **Behandlas som**, valideringen underkänner ID-kolumnen och en
körning startar inte. I CSV-dataset kan ID-kolumnen innehålla vad som helst,
men den måste vara ifylld och unik på varje rad.

Har ett CSV-dataset ingen sådan kolumn säger uppladdningen det, och
Kolumnroller erbjuder **Lägg till en ID-kolumn**. Den lägger till kolumnen
JBG_RadId, numrerad 1, 2, 3 och så vidare, först i filen, som en ny version av
filen. Tidigare versioner finns kvar. JBG_RadId föreslås sedan som ID-kolumn.
En prediktionsfil som saknar JBG_RadId får kolumnen när den laddas upp, numrerad
på samma sätt, om träningsdatasetets ID-kolumn är JBG_RadId.
SQL-tabeller ändras aldrig, så där måste ID-kolumnen finnas i tabellen.

En datumkolumn kan få rollen **Datumvariabel**. Den blir då år (som tal),
månad och veckodag (som punkter på en cirkel, så att december ligger nära
januari) samt en markering för saknat datum. Datum föreslås aldrig
automatiskt: en datumkolumn föreslås som ignorerad, och **Behandlas som**
visar att den kan bli datumvariabel. Datum ska vara i formatet ÅÅÅÅ-MM-DD,
gärna med klockslag. I SQL-tabeller räknas typerna date, datetime, datetime2
och smalldatetime. Tänk på att året bara beskriver tiden modellen tränats
på. För nya år får modellen ett värde den inte har sett.

Högst en kolumn kan vara **Gruppkolumn**, till exempel en persons
identitet. Den håller ihop sina rader när data delas upp, så att samma grupp
inte hamnar både i träning och test, men den används inte som variabel.
Den behövs när konfigurationen håller grupper isär. Prediktionsdataset måste
också innehålla gruppkolumnen.

Har datasetet inga sparade kolumnroller fylls formuläret i med förslag: den
första kolumnen som är ifylld och har olika värden på alla rader blir
ID-kolumn, tal blir numeriska variabler, text med högst så många olika
värden som gränsen för kategorisering blir kategoriska variabler och annan
text textvariabler. Tomma kolumner och kolumner med ett enda värde
ignoreras, liksom till exempel datumkolumner i SQL-tabeller. Klasskolumnen
föreslås inte: välj den i formuläret, eller visa en kolumns fördelning i
vyn Klasser, så blir den klasskolumn i förslaget. Förslaget sparas inte
förrän du väljer **Spara kolumnroller**.

**Gräns för kategorisering** (standard 30, tillåtet 2–1000): textkolumner med
högst så många olika värden behandlas som kategorier, andra textkolumner som
fritext. Kategoriska variabler kategoriseras alltid. Kolumnen ”Behandlas
som” visar resultatet.

Spara med **Spara kolumnroller** och validera sedan datasetet igen med
**Validera dataset** längst ned.

Har projektet redan ett dataset med samma kolumner, välj det under
**Kopiera kolumnroller från** och **Fyll i**. Rollerna fylls i men sparas
inte förrän du sparar. Kolumner som saknas eller inte är tal sägs till.
En konfiguration kan användas med alla dataset i projektet.

## Konfiguration

En konfiguration innehåller inställningarna för maskininlärningen. **Skapa
konfiguration** börjar med standardinställningarna.

Avsnitten kommer i den ordning som stegen körs: Körningstyp, Textbehandling,
Variabelurval, Uppdelning, Skalning, Översampling, Undersampling,
Dimensionsreduktion, Algoritmer, Beslut, Utvärdering, Mörkertal och, i
SQL-projekt, Prediktioner, sist Avancerat. Skalning, sampling,
dimensionsreduktion och algoritmen prövas tillsammans i korsvalidering. Alla
avsnitt är stängda när sidan öppnas. Klicka på ett avsnitts rubrik för att
öppna eller stänga det. Avsnitt som var öppna när du sparade är öppna även
efter sparandet. Ovanligare inställningar finns under **Avancerade
inställningar** i respektive avsnitt.

**Algoritmer**: algoritmerna visas i grupper (linjära, icke-linjära, grannar,
naive Bayes, träd, ensembler, obalanserade data, robusta mot felmärkning,
neurala nätverk, särskilda), sorterade efter namn inom varje grupp. **välj
alla** och **rensa** gäller en grupp.

**Variabelurval**: variablerna som en modell använder väljs med kolumnrollerna
på fliken Dataset. En kolumn med rollen Ignoreras används inte. Inställningarna
i avsnittet används av variabelundersökningen (se Träning). Quick, Standard
och Extended bestämmer sökningens omfattning, Custom använder värdena i
avsnittet.

Till vänster, under listan, visar **Pipeline** stegen för den öppnade
konfigurationen i den ordning de körs. Ett grönt steg används, ett lila
jämför flera alternativ och ett streckat används inte. De steg som prövas
tillsammans i korsvalidering står inom en streckad ram med antalet
kombinationer. Klicka på ett steg för att öppna dess avsnitt. Bilden visar den
sparade versionen.

I **Uppdelning** väljer du om grupper ska hållas isär vid korsvalidering
eller vid uppdelningen av testdata. Gruppkolumnen anges inte här utan som
kolumnroll på fliken Dataset, och avsnittet visar vilken kolumn som används.
Grupper isär vid uppdelningen av testdata kräver två klasser. I **Översampling** och **Undersampling** kryssar
du i de metoder som ska prövas. Är inget ikryssat används ingen sampling.

**Andelsreglagen.** Varje samplingsavsnitt har ett reglage. I Översampling
anger det minsta klassens andel av raderna efter samplingen, och i
Undersampling största klassens andel. Reglaget börjar på klassens nuvarande
andel i det aktiva träningsdatasetet och går bara mot 50 %. Är en metod
ikryssad men reglaget orört, sparas inte konfigurationen. Flytta då reglaget,
avmarkera metoderna eller välj **Använd standardvärden**: minsta klassen höjs
till andelen för nästa större klass, och största klassen sänks till andelen
för nästa mindre klass, aldrig förbi 50 %. Med två klasser blir det balanserat.
Samma andel gäller alla ikryssade metoder som kan använda den. De rensande
undersamplingsmetoderna (till exempel Tomek Links) följer sina egna regler, och
körningens logg säger det, liksom när en klass redan har nått sin andel. De
tidigare förvalen för undersampling (högst 2, 5, 10 eller 20 gånger minsta
klassen) har ersatts av reglaget. En sparad konfiguration med dem får slumpvis
undersampling med motsvarande andel.

I **Mörkertal** väljs **Målklass** bland klasserna i det aktiva
träningsdatasetets klasskolumn, eller **Alla klasser**. Klasserna läses när
avsnittet öppnas (i SQL-projekt behövs inloggning). Under fälten visas
formeln för vald metod och alpha, med målklass och reservmetod. Den följer
dina val direkt, och alpha ”Separated” går bara att välja med metoden
”Linear”.

- Rutan **Alla** i en lista markerar alla val. Den markeras också när sista
  valet markeras, och den avmarkeras när ett val avmarkeras.
- **Spara konfiguration** skapar en ny version, och tidigare versioner sparas.
  En ny konfiguration är version 0, så den första ändringen ger version 1.
  Listan visar den senast skapade eller ändrade konfigurationen först.
- Panelen **Byt namn på konfigurationen** under listan ger den valda
  konfigurationen ett nytt namn utan att skapa en ny version. Körningarna som
  gjorts med den visar det nya namnet, och den hamnar först i listan.
  Modellerna behåller namnet de fick när de tränades.
- **Välj för körning** gör konfigurationen till den som används vid
  träning. Den är röd när konfigurationen redan är vald.
- **Ta bort konfigurationen…** tar bort den med alla versioner, de
  träningskörningar som gjorts med den, deras modeller och prediktionerna
  som gjorts med de modellerna (se Ta bort nedan).
- CSV-körningar tränar bara. Nya konfigurationer i CSV-projekt har därför
  ”Prediktera rader utan klass” avmarkerat.

## Träning

Listan **Före körningen** visar om allt som behövs finns: aktivt
träningsdataset med kolumnroller, vald konfiguration och, för SQL, inloggning.
Vid en punkt som inte är uppfylld leder **Åtgärda** dit den rättas till.
**Starta träning** startar körningen med det aktiva datasetet och den valda
konfigurationen.

Medan en körning i projektet står i kö eller pågår går det inte att välja
**Starta träning** eller **Undersök variabler** (eller **Starta prediktion**
på fliken Prediktion) förrän den är klar.

En avslutad körning kan tas bort med **Ta bort körningen…** (även på flikarna
Prediktion och Resultat).

**Undersök variabler** startar en variabelundersökning med samma dataset och
konfiguration. Den söker i träningsdelen efter en mindre uppsättning variabler
som förutsäger lika bra som alla eller bättre, med nästlad korsvalidering, och
sparar ingen modell. Med fler än två klasser undersöks Mörkertalens målklass
(annars den minsta klassen) mot de övriga klasserna. Undersökningen kan ännu
inte hålla isär grupper och erbjuds därför inte för ett dataset med
gruppkolumn. När den är klar visar körningen rekommendationen: hur många
variabler, och MCC med dem och med alla variabler.

Förloppet uppdateras av sig självt. När modellerna tränas och jämförs visar
en tunnare stapel hur många algoritmkombinationer som är klara, till exempel
”12 av 40”. Sedan visar den slutträningen av den vinnande pipelinen. Med
parametersökning rör sig stapeln med tiden mot en uppskattning, till exempel
”2 min av cirka 4 min”, och väntar strax före slutet tills sökningen är klar.
Uppskattningen ökar om sökningen tar längre tid. Körningen fortsätter även om
du stänger webbläsaren och kan avbrytas med **Avbryt körningen**. **Visa
logg** visar körningens logg.

**Avbryt körningen** ber körningen att stanna: den stannar efter steget den
arbetar med, till exempel algoritmkombinationen som prövas. Ett långt steg
kan ta en stund. När du har avbrutit avslutar **Stoppa nu** körningen direkt.
Steget som pågår går förlorat, vilket inte spelar någon roll för en avbruten
körning. Om programmet på servern stoppas eller avslutas oväntat markeras
dess körningar som avbrutna: direkt när servern märker det, annars efter fem
minuter.

Om konfigurationen också predikterar rader utan klass men träningsdatasetet
saknar sådana rader, tränar körningen bara och hoppar över prediktionen.
Loggen säger det.

När körningen är klar visas utvärderingen på testdata, förväxlingsmatrisen
och de viktigaste variablerna.

## Resultat

Projektets avslutade träningskörningar. För en vald körning finns vyerna
Översikt, Modelljämförelse, Felklassificeringar, Variabelbetydelse och
Mörkertal. Klassnamn och radvärden visas bara för den som startade
körningen. Äldre körningar kan sakna en del detaljer.

En avslutad **variabelundersökning** visar sin rekommendation: de
rekommenderade variablerna och de utelämnade, och MCC med dem och med alla
variabler (nästlad korsvalidering på träningsdelen). **Använd
rekommendationen** öppnar datasetets kolumnroller med de utelämnade
kolumnerna satta till Ignoreras (en datumkolumn bara om alla dess delar
utelämnades). Inget sparas förrän du väljer **Spara kolumnroller**. Den kan
inte användas om kolumnrollerna har ändrats sedan undersökningen, eller om
rekommendationen behåller alla variabler.

**Mörkertal** visar, när konfigurationen skattar mörkertal, den skattade
andelen dolda fall för varje målklass. Fyra skattningar görs: med den
slutliga modellen och med den korstränade modellen på alla data, en
kombinerad och med den korstränade modellen på testdata. De visas sorterade
från lägst till högst, var och en märkt med sin modellvariant, och bildar
tillsammans ett intervall med delintervall. Därunder finns beräkningarna och
förväxlingsmatriserna.

Mörkertalet är en skattning, inte en statistiskt säkerställd andel. Den
bygger på modellens fel och på antaganden som inte kan prövas med de egna
data. Använd den för att jämföra storleksordningar och följa förändringar över
tid, inte som ett exakt antal. Vyn säger det också.

En skattning kan vara **Odefinierad**. Det händer när den del av data som den
görs på saknar rader av målklassen eller av de övriga klasserna, eller när
korrektionsfaktorn c inte kunde skattas eller ligger utanför intervallet från
1 till den övre gränsen i konfigurationen (20 som standard). Det betyder att
pipelinen eller datasetet inte passar för att skatta mörkertal för den
målklassen.

En varning visas när modellen lär sig en del av de avsiktligt felaktiga
etiketterna utantill: c är över varningsnivån i konfigurationen (10 som
standard), eller så passar modellen sina träningsrader tydligt bättre än
rader den inte sett. c korrigerar för det, men med osäkerhet, och en pipeline
som lär sig mindre utantill ger ett mer tillförlitligt mörkertal.

### Mörkertal i detalj (JBG 1.3)

**Vad som skattas.** För en målklass T skattar mörkertalet D den dolda
andelen: av raderna som är registrerade som en annan klass, andelen som
egentligen hör till T. Multiplicerat med antalet rader registrerade som en
annan klass ger det det skattade antalet dolda fall. Det beräknas för varje
målklass för sig, målklassen mot alla de övriga.

**Ekvationen** (linjär metod, separerad alfa, standardvalet):
`D = min(c · α_FP · (1 − TN_r) · (1 + α_FN · (1 − TP_r)), 1)`

- `1 − TN_r = FP / (FP + TN)`: andelen av raderna registrerade som en annan
  klass som modellen förutsäger som T. Det är kandidaterna till dolda fall.
  Utan de andra faktorerna är `min((1 − TN_r) · (2 − TP_r), 1)` den
  grundläggande skattningen av den dolda andelen.
- `1 − TP_r = FN / (TP + FN)`: andelen av T:s egna rader som modellen missar.
  En modell som missar kända fall missar också dolda, så kandidaterna skalas
  upp med 1 plus den andelen. Det är en försiktig variant av att dela med
  TP_r: lika för bra modeller, mer återhållsam för svaga.
- `α_FP`: medelsannolikheten för T på de falska positiva. Alla falska
  positiva är inte dolda fall, en del är vanliga modellfel. En säker falsk
  positiv räknas nästan fullt, en osäker lite (mjuk räkning).
- `α_FN`: medelsannolikheten för att inte vara T på de falska negativa. Den
  väger bara missarna, så utan missar är skalfaktorn 1.
- `c`: korrektionsfaktorn för överträning, från ommärkningstestet. En andel av
  T:s rader får avsiktligt en annan klass (20 % som standard, fördelat på de
  övriga klasserna efter deras storlek) och en kopia av modellen tränas, i 4
  delar och 2 upprepningar (standard). Delarna är desamma på alla datorer,
  oavsett antalet processorkärnor, så c blir detsamma. Varje kopia får
  frågor om två sorters rader: de ommärkta rader den tränats på (den känner igen en andel
  `r_i` av dem som T) och T:s rader i den del den inte sett (en andel
  `r_osedd`). `c = r_osedd / r_i`, minst 1. En modell som lär sig felaktiga
  etiketter utantill känner igen mycket färre av raderna den tränats på, så
  `c` blir stort. En modell som inte övertränar känner igen båda sorterna
  ungefär lika ofta, så `c` blir ungefär 1. Modellens vanliga missar påverkar
  båda andelarna lika och tar ut varandra i kvoten. De räknas en gång, av den
  andra faktorn. Från 1.3 (2026-11-19): `c` var `1 / r_i`, som också innehöll
  de vanliga missarna och därför räknade dem två gånger. Beräkningstabellen
  visar `c` med ett 90 %-intervall och en kvalitet, och de två faktorerna den
  består av.
- Resultatet begränsas till 100 %. Ett värde över det betyder att
  skattningen har brutit samman för den målklassen, och vyn säger det.

**Två läsarter.** Ett val överst i vyn Mörkertal visar antingen andelen
bland de övriga klasserna (som ovan) eller målklassens tillväxt: hur mycket
den skulle växa om de dolda fallen lades till, `g = D · N_övriga / N_mål`,
där N_övriga och N_mål är raderna registrerade som en annan klass och som
målklassen i samma skattning. Tillväxten visas i procent och som faktor, med
det skattade antalet dolda fall, de registrerade fallen och andelen av alla
verkliga fall som saknades i registret, `g / (1 + g)`. Liksom D förutsätter
den att raderna registrerade som målklassen hör dit. Med en sällsynt
målklass ger små ändringar i D stora ändringar i tillväxten.

**De fyra skattningarna** görs med den korstränade modellen på testdelen,
med den korstränade modellen på alla data, med den slutliga modellen på alla
data och kombinerat. Testdelen är ny för modellen, så `c` används inte där.
De tre andra innehåller rader som modellen tränats på och korrigeras med `c`.
De fyra modellvarianterna visas sorterade från lägst till högst och bildar
tillsammans ett intervall med delintervall. Det finns ingen förväntad
ordning mellan dem.

**Odefinierade skattningar.** En skattning är odefinierad när den del av
data som den görs på saknar rader av T eller av de övriga klasserna, eller
när `c` inte kunde skattas eller ligger utanför intervallet från 1 till den
övre gränsen (20 som standard). Det betyder att pipelinen eller datasetet inte
passar problemet för den målklassen. Utan falska positiva är mörkertalet 0
oavsett `c`.

**Varningar.** När `c` är över varningsnivån (10 som standard) lär sig
modellen en del av de avsiktligt felaktiga etiketterna utantill. `c`
korrigerar för det, med osäkerhet. Beräkningstabellen anger det för varje
skattning.

**Inställningar.** Konfigurationens avsnitt Mörkertal anger, utöver
ommärkningsandelen och samplingen, upprepningarna i ommärkningstestet (2 som
standard, varje upprepning ger 4 modellanpassningar till och smalnar av
intervallet för `c`, användbart med en sällsynt målklass), den övre gränsen
för `c` (20) och varningsnivån (10). Värdena som användes visas med ekvationen
och sparas med resultatet.

**Logistisk regression när c inte kan användas.** Är `c` över den övre
gränsen eller inte skattbar för någon målklass, görs hela beräkningen om med
logistisk regression i stället för pipelinens algoritm. Övriga steg i
pipelinen behålls. Det är påslaget som standard och stängs av med rutan
**Använd logistisk regression när c inte kan användas** i avsnittet
Mörkertal. Vyn Mörkertal säger alltid när det har hänt, för vilka målklasser
och vilken algoritm som ersattes.

**Andra former.** Utan alfa använder D `(2 − TP_r)` utan vikter. Formerna med
en alfa och de icke-linjära formerna är oförändrade, med samma begränsning
och samma användning av `c`.

**Sampling i korrektionstestet.** Konfigurationens avsnitt Mörkertal väljer
hur testet bakom c samplar data. "Som pipelinen" (standard) använder den
vinnande pipelinens egen över- och undersampling, som tidigare. När
målklassen är majoritetsklassen och pipelinen använder SMOTE blir de
avsiktligt ommärkta raderna den klass som SMOTE förstärker, vilket kan göra c
för stor. Vyn Mörkertal varnar då. "Ingen", "SMOTE", "SMOTE från ej
ommärkta rader" (syntetiska rader bara från rader som inte märktes om) och
"Undersampling (1 : 1)" ersätter pipelinens sampling enbart i testet. Den
vanliga träningen påverkas inte.

**c:s delar.** Beräkningstabellen visar bredvid c de två faktorer den består
av: "c i träningsraderna" (`1 / r_i`, korrektionsfaktorn före 1.3) och "c på
osedd del" (`1 / r_osedd`), och c:s 90 %-intervall och kvalitet
(tillförlitlig, osäker, ej skattbar). Ett osäkert c används, men vyn säger
det. Valideringsstudien (i `docs/dark_numbers/`) visade att detta c gör
skattningarna på alla data lika nära sanningen som skattningen på testdelen,
där det tidigare c ungefär fördubblade felet.

**Version och inställningar.** Ekvationsavsnittet anger metodens version och
inställningarna som användes (ommärkningsandel, delar och upprepningar,
gränserna för c, regeln för memorering och slumpfrö). Körningar gjorda före
version 1.2 saknar sådana uppgifter. Deras värden visas som de sparades, med
en anmärkning.

**Vad som kommer.** Mätningen på rader som modellen inte tränats på och
intervallet för `c`, som tidigare planerades till version 2, finns sedan 1.3
(se c:s delar ovan). Kvar i planen är metoder som skattar den dolda andelen
direkt, med intervall. Planen finns i `docs/dark_numbers/` i repositoriet.

I **Felklassificeringar** för en SQL-körning kan du rätta klasser som är
fel i källdata. Välj **Rätt klass** för raderna och sedan **Granska
korrigeringarna**. En sida visar ändringarna, och först när du väljer **Skriv
korrigeringarna** skrivs de till källtabellen med din SQL-inloggning, alla på
en gång eller ingen. Inloggningen måste få ändra tabellen. Rättade rader
markeras, och under tabellen listas korrigeringarna. **Ångra** skriver
tillbaka den gamla klassen. Nästa träning använder de rättade klasserna.

För en CSV-körning fungerar det likadant, men korrigeringarna sparas i en ny
version av datasetets fil, som alla senare körningar läser, och den uppladdade
filen behålls. Datasetet behöver valideras igen. **Hämta CSV** under fliken
Dataset hämtar filen med de rättade klasserna.

I **Mörkertal** visas varje skattning också i procent, med en stapel på
målklassens skala, och under tabellen intervallet från minsta till största
skattning.

Breda tabeller har en rullningslist både under och ovanför tabellen.

## Modeller

Modellerna som träningskörningarna har skapat, med var de kommer ifrån och
deras nyckeltal, och modellens kvarvarande körningar. **Välj modell** gör en
tillgänglig modell till den som används vid prediktion. **Ta bort modellen…**
tar bort den med dess filer och de prediktionskörningar som gjorts med den.

## Prediktion

Prediktion använder modellen som är vald under fliken Modeller.

- **SQL-projekt**: prediktera träningsdatasetets rader utan klass eller ett
  registrerat prediktionsdataset som passar ihop med träningsdatasetet.
  Prediktionerna skrivs till prediktionstabellen i SQL Server. En tabell
  utan klasskolumn predikteras i sin helhet.
- **CSV-projekt**: prediktera träningsdatasetets rader utan klass eller ett
  prediktionsdataset (eller blandat dataset) med samma kolumner. Raderna
  utan klass predikteras, och en fil utan klasskolumn predikteras i sin helhet.
  Passar filen inte modellen, eller har alla rader redan en klass, säger
  fliken det innan något startar.

När körningen är klar visas prediktionerna sida för sida, och de kan laddas
ned som en fil med **Ladda ned prediktionerna**.
I CSV-projekt hämtar **Hämta med originalkolumnerna** prediktionerna
tillsammans med de predikterade radernas alla kolumner, från den fil som
prediktionen läste.

## Körhistorik

Fliken visar alla körningar i projektet i en lista: träningskörningar,
prediktionskörningar och variabelundersökningar, de senaste 1000. Finns fler
säger fliken det. Listan kan filtreras på typ,
status, dataset och konfiguration.

En vald körning visar vad som kördes, dess tid och dess resultat: den vinnande
pipelinen, utvärderingen på testdata och, om mörkertal beräknades, intervallet
för varje målklass. Därunder visas de inställningar där körningen skiljer sig
från konfigurationens nuvarande version, och de kolumnroller där den skiljer
sig från datasetets nuvarande roller. Inställningarna kommer från den
konfigurationsversion körningen använde, och kolumnrollerna från körningen
själv.

**Kör igen** startar en träningskörning eller variabelundersökning på nytt med
samma konfigurationsversion och dataset. Datasetets nuvarande data och
kolumnroller används, och fliken Träning visar förloppet. Det går inte medan en
annan körning pågår i projektet. Prediktionskörningar körs inte igen här.

Markera två körningar och välj **Jämför** för att se dem sida vid sida:
resultaten först, sedan varje inställning och kolumnroll där de skiljer sig.

## Inställningar

Fliken längst till höger har inställningar för den här webbläsaren:

- **Språk**: svenska eller engelska.
- **Exportformat**: Excel eller CSV, för knappen **Exportera** i varje vy.

Välj **Spara**. Fler inställningar kommer att samlas här.

## Bra att veta

- Loggar och prediktioner kan innehålla värden ur dina data och visas bara
  för den som startade körningen.
- Varje körning sparar sina resultat i en egen mapp på servern.
- **Ta bort**: det som äger något tar det med sig. En körning tar med sig sin
  logg och sina resultatfiler, en modell sina filer och sina
  prediktionskörningar, en konfiguration sina versioner, sina
  träningskörningar och deras modeller, ett dataset sina filversioner,
  körningarna på det och modellerna som tränats på det, ett projekt allt i
  det. Versioner av CSV-filer som inget längre använder städas bort när ett
  dataset tas bort. En sida visar först exakt vad som tas
  bort och vad som finns kvar. **Ta bort** (orange) genomför det och kan inte
  ångras. Inget tas bort medan en körning som skulle tas bort står i kö eller
  pågår. När en träningskörning tas bort men dess modell finns kvar sparas
  bara körningens inställningar för modellen, dolda. Tabeller i SQL Server
  ändras aldrig: prediktioner och korrigeringar som redan skrivits finns
  kvar.
- Den här fliken visar programmets version.
