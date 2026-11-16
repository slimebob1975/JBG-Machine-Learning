# JBG Dark Number Analysis 2.0

**Metodspecifikation och stegvis implementeringsplan**
**Datum:** 2026-11-16
**Status:** Förslag för granskning – ingen ändring av produktionskod beslutad
**Omfattning:** JBG Machine Learning; förbättrad befintlig JBG-metod och kompletterande mörkertalsestimatorer

---

## 1. Syfte och beslutade utgångspunkter

Målet är att vidareutveckla JBG:s mörkertalsanalys utan att ta bort den befintliga metoden. Projektet ska samtidigt:

1. **Bevara original-JBG** som reproducerbar referens.
2. **Utveckla JBG v2** med stabilare korrigeringsfaktor `c`, adaptiv etikettperturbation och särskild, klassbalansmedveten samplingspolicy.
3. **Införa alternativa mörkertalsmetoder** som har tydligt definierade statistiska målstorheter, särskilt felmärkningsmodeller, känslighetsintervall och en stegvis utforskning av Positive–Unlabeled (PU) learning.
4. **Skilja mörkertalsestimation från vanlig klassificering:** ordinarie modellträning och dess vinnande pipeline ska inte ändras av experimentella regler för mörkertalsanalys.
5. **Validera före produktionspatch:** utveckla och pröva metoderna separat, först på syntetiska data med känt facit och sedan försiktigt på verkliga data där facit normalt saknas.
6. **Bevara över- och undersampling som centrala designval**, inte som detaljer som försvinner när vi inför nya estimatorer.
7. **Redovisa begränsningar öppet:** en stabil eller låg korrigeringsfaktor är inte automatiskt en korrekt skattning av verkligt mörkertal.

**Styrande beslut:** Ingen produktionskod ska patchas förrän metodspecifikation, experiment och acceptanskriterier har granskats och ger tillräckligt stöd för en kontrollerad produktionspilot.

---

## 2. Bakgrund: ursprungsproblemet

Felsökningen utlöstes av en körning mot en SQL-tabell i produktion (namnet utelämnat), där beräkningen gav en extrem korrigeringsfaktor omkring **`c = 8237`**. Målklassen var **`Ja`**, vilket i detta fall är **majoritetsklassen**, till skillnad från tidigare användningsfall med en mindre målklass.

### 2.1 Datamaterial och körinställningar

| Egenskap | Värde |
|---|---|
| SQL-tabell | (namnet utelämnat) |
| Antal rader i hela tabellen | 498 915 |
| Antal kolumner | 71 |
| Registrerade `Ja` | 427 508 (85,69 %) |
| Registrerade `Nej` | 71 407 (14,31 %) |
| Modellkörningens debug-urval | 10 000 rader |
| `Ja` i körningens urval | 8 582 (85,82 %) |
| `Nej` i körningens urval | 1 418 (14,18 %) |
| Vinnande klassificerare | `FUTV` (soft-votingensemble med MLP, Random Forest och AdaBoost enligt kodgranskning i tidigare undersökning) |
| Vinnande pipeline | `SME | NUG | MAX | PCA | FUTV` |
| `SME` | SMOTE |
| `NUG` | Ingen undersampling |
| Mörkertalsmål | `Ja` |
| Mörkertalsmetod | `LINEAR` |
| Alpha-inställning | `SEPARATED` |
| Flip-andel | 20 % |
| Testandel | 20 % |
| Scoring | `f1_micro` |
| Gruppbaserad CV | Avaktiverad |

Källan hade flera identifierarliknande prediktorer med hög kardinalitet, korrelerade fält, konstanta fält och kolumner där exempelvis `-1` kan beteckna saknade uppgifter. Dessa är relevanta för modellens generalisering och ska ingå i syntetiska regressionstester. De faktiska enskilda observationerna har inte delats.

### 2.2 Varför `c` exploderade

Den undersökta implementeringen använder konceptuellt

\[
 c_{\mathrm{JBG}}=\frac{1}{r},
\]

med `r` som genomsnittlig *recovery* vid artificiell felmärkning. `c ≈ 8237` betyder `r ≈ 0,0001214`, dvs. ungefär **0,012 %**.

Den tidigare kodgenomgången fann att en del av målklassens etiketter flippas inom varje CV-träningsdel; modellen tränas med dessa felaktiga etiketter och utvärderas därefter på **samma flippade träningsrader**. Korsvalidering skapar olika träningsurval, men själva recovery-mätningen är alltså *in-sample* med avseende på de flippade raderna. Det kan gynna memorering av felaktiga etiketter snarare än mätning av verkliga dolda fall.

I skärmbildens tidigare förväxlingsmatriser hade den korstränade modellen inga fel på de 8 000 träningsraderna. Den observationen stärker överanpassningshypotesen, men ensam bevisar den inte att alla extremvärden orsakas av memorering.

### 2.3 Varför majoritetsmål och SMOTE kräver särskild hantering

Vid 85,69 % `Ja` ger 20 % flip från `Ja` till `Nej`, på en tänkt population om 10 000:

- Ursprungligen cirka 8 569 `Ja` och 1 431 `Nej`.
- Cirka 1 714 `Ja` märks om till `Nej`.
- Efter flip: cirka 6 855 `Ja` och 3 145 registrerade `Nej`.
- Cirka **54,5 % av den nya `Nej`-klassen** består då av artificiellt felmärkta `Ja`.

När SMOTE balanserar den nya minoritetsklassen kan dessa artificiellt felmärkta rader bli underlag för syntetiska `Nej`-punkter. Detta är en **kontamineringsrisk** i recovery-experimentet. När målklassen i stället är minoritet och flippas till majoritet, uppstår inte samma direkta SMOTE-förstärkning av just de flippade raderna i normal automatisk minoritetsöversampling.

---

## 3. Vad de tidigare försöken visade – och inte visade

Fristående syntetiska försök har jämfört Random Forest, logistisk regression (LR), multilayer perceptron (MLP), hård och sannolikhetsbaserad recovery, olika flip-nivåer och samplingstrategier. Huvudobservationerna är:

| Observation | Tolkning / begränsning |
|---|---|
| Random Forest gav ofta mycket hög eller oändlig `c` i perturbationsförsök. | Förenligt med memorering av flippade träningsetiketter; skäl att prioritera LR/MLP för nästa korrigeringsstudier. |
| LR och MLP gav ofta numeriskt lägre `c`. | Låg `c` kan också bero på att modellen nästan alltid predikterar majoritetsklassen; inte ett sanningsbevis. |
| SMOTE kunde förstärka perturbationsbrus för majoritetsmål. | SMOTE är inte generellt dåligt för vanlig modellträning; skilj de två användningarna. |
| Undersampling minskade inte konsekvent problemet. | Behåll som experimentell policy, inte som tvingande regel. |
| Sannolikhetsbaserad recovery kunde undvika noll-recovery och oändlig `c`. | Kräver kalibrering och ändrar delvis definitionen av recovery. |
| `CLEAN_SMOTE` förbättrade i vissa syntetiska MLP-försök AUC för upptäckt av verkligt dolda fall. | Lovande men resultatet bygger på begränsade syntetiska scenarier, inte en validerad mörkertalsskattning. |
| Det befintliga `D` kunde bli tydligt positivt även när det syntetiska facit var noll mörkertal. | Klassificeringsfel kan uppkomma utan felregistrerade klasser; metodens målstorhet behöver preciseras. |
| Felmärkningsmatris och kalibrerade sannolikheter fungerade bättre när en separat kontrollmängd innehöll sanna etiketter. | Den kontrollinformationen finns **normalt inte** i produktion. Dessa tester visar metodernas potential under ett starkare informationsantagande. |

**Viktigt:** De tidigare försöken är explorativa och har varierande populationsstorlek, frön och CV-konfiguration. Resultaten får inte behandlas som en slutlig jämförande benchmark eller som bevis för produktionsprestanda.

---

## 4. Statistiska målstorheter och notation

Vi behöver kunna skilja observerade klassandelar från sanna, normalt okända, klassandelar. Alla formler nedan är binära och uttrycks relativt en vald målklass `T` (kan vara majoritet eller minoritet).

| Symbol | Betydelse |
|---|---|
| `X` | Features |
| `Y` | Sann klass (i verkligheten vanligen okänd) |
| `S` | Observerad/registrerad klass |
| `T` | Klass vars mörkertal analyseras |
| `q = P(S=T)` | Observerad målklassandel |
| `π = P(Y=T)` | Sann målklassandel |
| `α = P(S≠T \| Y=T)` | Andelen sanna målklassfall som registreras i motsatt klass |
| `β = P(S=T \| Y≠T)` | Andelen sanna icke-målklassfall som registreras som målklass |
| `H = P(Y=T \| S≠T)` | Dold målklassandel bland registrerade icke-målklassfall |
| `U = P(S≠T \| Y=T)` | Andel av samtliga sanna målklassfall som inte registrerats som målklass; `U=α` i modellen ovan |
| `N` | Totalt antal observerade rader |
| `N_hidden = N(1-q)H` | Antal dolda målklassfall bland registrerade icke-målklassfall, om `H` är identifierad/skattad |
| `r` | Recovery i artificiellt perturbationstest |
| `c_JBG = 1/r` | Den befintliga JBG-faktorn |
| `D_JBG` | Befintlig JBG-storhet; **inte automatiskt samma sak som** `H` eller `U` |

**Prioriterad jämförbar målstorhet för alternativa metoder:** `H`, tillsammans med skattat antal `N_hidden`, `U` och `π` när de går att härleda. Original-JBG redovisas separat som `D_JBG` tills en statistiskt motiverad översättning har validerats.

### 4.1 Identifiabilitet i produktionsdata

Det normala produktionsfallet har **okänt sant mörkertal**. Vi ska **inte** kräva facit för att köra JBG. Syntetiska experiment med känt facit används för metodvalidering; verkliga data används för diagnostik, antagandekänslighet och robusthetsanalys.

Utan ytterligare antaganden eller information kan `P(Y|X,S)` i allmänhet **inte** identifieras entydigt från enbart `P(X,S)`. Två metoder som ger liknande resultat på produktionsdata bevisar därför inte att båda har rätt. Varje ny estimator ska deklarera sitt identifikationsantagande och kunna returnera **ej identifierbar** i stället för en obefogat exakt punktuppskattning.

---

## 5. Estimator A: Original-JBG och förbättrad JBG v2

### 5.1 Originalformel

Den tidigare undersökta `LINEAR + SEPARATED`-formeln uttrycks som

\[
D_{\mathrm{JBG}}
= c_{\mathrm{JBG}}\,\alpha_{FP}\,FPR\,\alpha_{FN}(2-TPR).
\]

Här är `FPR` och `TPR` vanliga felklassificeringsmått; `α_FP` och `α_FN` är **JBG:s befintliga viktnings-/säkerhetstermer** och ska inte blandas ihop med felmärkningssannolikheterna `α` och `β` ovan. Exakta implementationer av viktningarna ska låsas mot koden i DN-01.

JBG v1 förblir en **oförändrad reproducerbar baseline**. JBG v2 förbättrar diagnostik, perturbation och samplingshantering men behåller formeln initialt, så att komponenternas effekt kan mätas separat.

### 5.2 Två recovery-mått

Låt `F` vara de artificiellt flippade observationerna och `m=|F|`.

**Hård recovery**:

\[
r_{hard}=\frac{1}{m}\sum_{i\in F}\mathbf 1\{\widehat S_i=T\}.
\]

**Sannolikhetsbaserad recovery**:

\[
r_{prob}=\frac{1}{m}\sum_{i\in F}\widehat P(S=T\mid X_i).
\]

Sannolikhetsmåttet är i detta sammanhang modellens sannolikhet för den **observerade/predikterade klassen** under perturbation; det ska inte okritiskt tolkas som `P(Y=T|X)`. Båda måtten samlas i forskningsläget. Ett val av standardmått görs först efter facitvalidering och kalibreringsstudie.

### 5.3 Osäkerhet och numerisk stabilitet

Vid recovery-intervall `[r_L, r_U]`, där `r_L>0`, kan faktorintervallet härledas som

\[
c_{\mathrm{JBG}}\in[1/r_U,\,1/r_L].
\]

Om `r_L=0` saknas ändlig övre gräns för `c`; returnera **otillräckligt underlag**/öppen övre gräns, inte en godtyckligt klippt faktor. Resampling måste hantera beroende mellan CV-folds och återanvända observationer; ett naivt binomialintervall över alla prediktioner är inte tillräckligt.

Föreslagna resultatstatusar: `estimated`, `unstable`, `zero_recovery`, `insufficient_events`, `degenerate_classifier`, `not_identifiable`, `failed`.

### 5.4 Adaptiv flip

| Målklassens status i ursprungliga data | Försöksordning |
|---|---|
| Majoritet | 2 % → 5 % → 10 % → 20 % |
| Minoritet | 20 % → 10 % → 5 % → 2 % |

Om klasserna är lika stora ska en deterministisk och dokumenterad regel gälla; alternativt utvärderas båda riktningarna i diagnostikläge.

**Princip för stopp:** `c ≤ 20` räcker inte som ensamt villkor. Kräv dessutom minimalt effektivt antal återidentifieringar, icke-degenererad modell, acceptabel osäkerhet och stabilitet över upprepningar. Trösklar förhandsregistreras i metodtester. Eftersom stopp vid första gynnsamma `c` kan introducera selektionsbias ska **alla fyra nivåer alltid utvärderas i benchmarkläge**, innan vi tillåter tidigt stopp i ett snabbare produktionsläge.

**Förslag till pseudokod**:

```text
estimate_jbg_v2(data, target, estimator_family, sampling_policy, seeds):
    baseline = evaluate_unperturbed_classifier_with_oof_metrics(data)
    order = [0.02, 0.05, 0.10, 0.20] if target_is_majority else reverse(...)
    results = []
    for flip_fraction in order:
        for (seed, split) in reproducible_cv_splits:
            train, validation = split(data)   # split före fit av samplers/transforms
            flipped_train, flip_mask = perturb_target_labels(train, flip_fraction)
            fitted = fit_perturbation_pipeline(flipped_train, flip_mask, sampling_policy)
            recovery = evaluate_explicit_recovery_protocol(fitted, flip_mask, train, validation)
            metrics = evaluate_independent_quality_metrics(fitted, validation)
            results.append({flip_fraction, recovery, metrics, diagnostics})
        precision_and_stability = estimate_uncertainty(results_at_flip)
        if production_early_stop_enabled and predefined_acceptance_rule_passes(...):
            break
    return full_diagnostics_and_c_status(results, baseline)
```

**Forskningsfråga om recovery-protokollet:** Nuvarande in-sample-protokoll och en variant med separerad utvärdering måste jämföras utan att blanda ihop deras målstorheter. Att bara flytta flippade rader till CV-test ändrar frågan: då mäter vi i högre grad modellens vanliga återidentifiering, inte motstånd mot label-noise i träning. Båda kan undersökas, men deras `c` får inte bytas ut utan metodvalidering.

### 5.5 Diagnostik för varje flippnivå

Spara minst: målklass, ursprunglig klassbalans, flip-andel, antal flippade, återidentifierade antal, `r_hard`, `r_prob`, intervall för `r` och `c`, samplingspolicy, antal syntetiska rader, fold-frön, CV-kvalitetsmått per klass, kalibreringsmått och eventuella degenereringsflaggor.

---

## 6. Samplingsmotor för mörkertalsanalysen

**Grundregel:** Ordinarie klassificering får behålla sin vinnande pipeline (exempelvis `SME | NUG | MAX | PCA | FUTV`). Korrigeringsanalysen använder en separat, dokumenterad policy. Ingen sampler får passa på valideringsdata; skalning och PCA ska också anpassas endast till aktuell träningsdel.

### 6.1 Policies

| Namn | Beteende | Viktig risk/nytta |
|---|---|---|
| `NONE` | Ingen över- eller undersampling | Neutral referens; kan ge trivial majoritetsklassprediktion |
| `SMOTE` | Vanlig SMOTE på perturberad träningsdata | Kan förstärka artificiellt felmärkta rader |
| `CLEAN_SMOTE` | SMOTE-generering endast från icke-artificiellt-flippade behöriga rader | Begränsar *skapad* kontaminering, men kan inte identifiera verkliga felmärkningar |
| `UNDER` | Kontrollerad undersampling av klassen som är majoritet **efter perturbation**, om policy definieras så | Kan minska informationsmängd och försämra vissa modeller |

`NUG` i den analyserade pipelinekonfigurationen betyder **ingen undersampling**; `UNDER` är ett nytt explicit diagnostiskt samplingsval, inte en tyst omtolkning av `NUG`.

### 6.2 CLEAN_SMOTE – föreslagen konstruktion

1. Dela upp data i CV-träning och oberoende validering.
2. Spara ursprungsetikett och `flip_mask` inom träningsdelen.
3. Perturbera valda träningsetiketter.
4. Bestäm vilken klass som ska översamplas enligt samplingspolicyn.
5. Välj SMOTE-behöriga observationer från den klassen där `flip_mask = false`.
6. Generera syntetiska rader **enbart** från de behöriga raderna (både föräldrar och grannar); dokumentera k-neighbor-krav och fallback om för få behöriga rader finns.
7. Kombinera genererade rader med hela originalträningsdelen inklusive artificiellt flippade observationer (som inte får skapa syntetiska exempel).
8. Träna LR/MLP och beräkna mått enligt valt, explicit recovery-protokoll.

Detta är en experimentell metod, inte en standard-SMOTE-inställning. Att utesluta flippade rader från generering påverkar effektiv klassbalans och estimand; det behöver valideras. Implementationen bör också logga syntetiska datapunkters härkomst och säkerställa att inga test- eller valideringsobservationer förekommer i genereringsunderlaget.

### 6.3 Preliminära huvudkandidater

- **Majoritetsmål:** `CLEAN_SMOTE` som första hypotes, mot `NONE`, `SMOTE`, `UNDER`.
- **Minoritetsmål:** `SMOTE` som första hypotes, mot `NONE`, `CLEAN_SMOTE`, `UNDER`.
- **LR:** `NONE` som viktig referens.
- **MLP:** alla policies testas; tidigare försök visade stor känslighet för undersampling.

Ingen av dessa är ännu fastställd som produktionsstandard. En samplingspolicy som ger högre AUC för att hitta dolda fall behöver inte ge lägre **skattningsbias** för mängden dolda fall.

---

## 7. Estimator B: Felmärkningsmatris

Antag klassberoende felregistrering med

\[
q=(1-\alpha)\pi+\beta(1-\pi).
\]

Om `1-α-β ≠ 0` och parametrarna är identifierade:

\[
\pi=\frac{q-\beta}{1-\alpha-\beta},
\qquad
H=\frac{\alpha\pi}{1-q}.
\]

Fysiska giltighetsvillkor: `0≤α,β,π,q≤1`, `0≤H≤1`, samt konsistens mellan antagna parametrar och observerad fördelning. När `1-α-β` ligger nära noll blir inversionen instabil och ska flaggas.

### 7.1 Ensidig felregistrering

Om det finns sakligt stöd för att registrerade målklassfall är korrekta (`β=0`):

\[
\pi=\frac{q}{1-\alpha},
\qquad
H=\frac{\alpha q}{(1-\alpha)(1-q)}.
\]

Här måste `α≤1-q` för att `π≤1` när `β=0`. Antagandet om ensidighet får inte sättas automatiskt för alla datakällor.

### 7.2 Vad krävs för att beräkna `α` och `β`?

Felmärkningsparametrarna kan komma från oberoende verifierad kontrollinformation, extern sakkunskap eller antagandebaserade intervall. En vanlig klassificerings-confusion matrix mot **observerade** etiketter är **inte** samma sak som en felmärkningsmatris för `Y` kontra `S` och får inte användas som sådan.

Om externa sanna etiketter saknas kan vi inte presentera matrisinversionen som datadriven identifiering utan extra antaganden.

---

## 8. Estimator C: Kalibrerad sannolikhet för dolda fall

Den önskade individbaserade storheten är

\[
h(x)=P(Y=T\mid X=x, S\ne T).
\]

Om `h(x)` är identifierbar och rätt kalibrerad:

\[
\widehat H=\frac{1}{N_0}\sum_{i:S_i\ne T}\widehat h(X_i),
\qquad N_0=\sum_i\mathbf 1\{S_i\ne T\}.
\]

Detta är inte samma sak som vanlig `predict_proba` för **registrerad** målklass. En modell som tränats på `S` skattar i första hand `P(S=T|X)`; att tolka den som `P(Y=T|X,S≠T)` utan felmärkningsmodell eller kontrollinformation är ett kategorifel.

**Implementationsplan:** först en kontrollinformationsstödd referensvariant för syntetiskt facit, sedan en explicit härledning från en vald label-noise- eller PU-modell som kan användas när sanna etiketter saknas. Kalibrering och sampling måste utvärderas separat; SMOTE kan förändra klasspriorer och kräva särskild sannolikhetskorrektion.

---

## 9. Estimator D: Positive–Unlabeled learning

PU är intressant när registrerade målklassfall kan antas vara tillförlitliga positiva, medan övriga rader är **unlabeled**, alltså inte garanterat negativa.

### 9.1 SCAR (Selected Completely At Random)

Under antagandet att varje verkligt målklassfall registreras med samma sannolikhet `e`, oberoende av `X`, och att det inte finns falskt positiva registrerade målklassfall:

\[
P(S=T\mid X=x)=e\,P(Y=T\mid X=x).
\]

Om `e` kan identifieras:

\[
P(Y=T\mid X=x)=\frac{P(S=T\mid X=x)}{e}.
\]

Sannolikheten måste vara inom `[0,1]`; värden över 1 efter division tyder på skattnings-/kalibreringsproblem eller felaktiga antaganden och ska inte tyst döljas.

**Avgörande begränsning:** `e` kan inte generellt skattas enbart genom att passa en vanlig klassificerare på `S`. Den behöver extra antaganden, exempelvis ankarmängd, positiv-subklassfördelning eller annan identifierande information. Vi ska inte förutsätta att `e` alltid går att lära från varje produktionsdataset.

### 9.2 SAR (Selected At Random)

En senare kandidat tillåter `e(x)=P(S=T|Y=T,X=x)`. Den kräver en explicit selektionsmodell och starkare identifikationsvillkor. Bör inte implementeras innan SCAR-varianterna validerats.

**Namngivning:** Använd `e` för PU-registreringssannolikhet. Använd **inte** PU-litteraturens vanliga `c` för denna sannolikhet eftersom `c_JBG` redan betyder invers recovery.

---

## 10. Estimator E: Antagandebaserad känslighetsanalys

När `α` och `β` inte är identifierade kan användaren ange sakligt motiverade intervall:

\[
\alpha\in[a_L,a_U],\qquad \beta\in[b_L,b_U].
\]

Beräkna minsta och största tillåtna `H` över alla parameterkombinationer som uppfyller constraints, med samma observerade `q`:

\[
\mathcal I_H
=\left[\min_{\alpha,\beta\text{ giltiga}} H(\alpha,\beta;q),\;
\max_{\alpha,\beta\text{ giltiga}} H(\alpha,\beta;q)\right].
\]

Detta är ett **identifierings-/känslighetsintervall beroende på antaganden**, inte ett statistiskt 95-procentigt konfidensintervall. Separat bootstrap eller annan osäkerhetsberäkning kan hantera stickprovsosäkerhet inom varje antagandescenario.

Prioritera detta som tidig alternativ funktionalitet eftersom det är transparent, analytiskt testbart och inte låtsas identifiera ett okänt mörkertal från data utan antaganden.

---

## 11. Föreslagen arkitektur och gränssnitt

```text
Existing JBG training/evaluation engine
    |
    +-- Unchanged original JBG v1 (reproducible baseline)
    |
    +-- Dark Number Analysis 2.0
           |
           +-- Data/target specification and common notation
           +-- Split and leakage-safe preprocessing
           +-- Perturbation/recovery service
           |      +-- Adaptive flip schedule
           |      +-- Logistic Regression / MLP
           |      +-- NONE / SMOTE / CLEAN_SMOTE / UNDER
           |      +-- Hard/probabilistic recovery + uncertainty
           |
           +-- Estimators
           |      +-- JBG v2
           |      +-- Misclassification/noise matrix
           |      +-- Calibrated hidden-probability model
           |      +-- PU-SCAR (later PU-SAR)
           |      +-- Sensitivity interval
           |
           +-- Validation & benchmarking
           +-- Diagnostics/result contracts
           +-- FastAPI adapter (later)
```

**Resultatkontrakt per estimator** bör innehålla minst:

```yaml
method_id: jbg_v1 | jbg_v2 | noise_matrix | calibrated_hidden | pu_scar | sensitivity
method_version: string
target_class: string
estimand: D_JBG | H | U | pi | N_hidden
point_estimate: number | null
interval: {lower: number | null, upper: number | null, kind: confidence | identification | none}
status: estimated | unstable | zero_recovery | insufficient_events | degenerate_classifier | not_identifiable | failed
assumptions: [string]
sampling_policy: NONE | SMOTE | CLEAN_SMOTE | UNDER | null
flip_schedule: [number] | null
selected_flip: number | null
quality_metrics: object
provenance: {seed: number | null, folds: number | null, data_version: string | null}
diagnostics: object
```

`estimand` måste alltid följa med jämförelser och export så att `D_JBG` inte misstas för `H`.

**Konfigurationshantering:** inför nya nycklar med uttryckliga defaultvärden och schema-versionering. Befintliga SQL-/CSV-projekt och deras `dark_number_*`-inställningar får inte omtolkas tyst. Original-JBG ska kunna köras med gamla inställningar.

---

## 12. Teststrategi och acceptanskriterier

### 12.1 Gemensam syntetisk testmatris

| Dimension | Föreslagna nivåer |
|---|---|
| Sant mörkertal | 0 %, 2 %, 5 %, 10 %, 20 % |
| Sann målklassandel | 15 %, 50 %, 85 % |
| Klass-separation | Svag, medel, stark |
| Felmärkningsmekanism | Ensidig, dubbelsidig, featureberoende |
| Modell | LR och MLP i korrigeringsspåret |
| Sampling | NONE, SMOTE, CLEAN_SMOTE, UNDER |
| Flip | 2 %, 5 %, 10 %, 20 % |
| Upprepningar | Flera oberoende populationer, seeds och folds; antal fastställs före benchmark |
| Referensdata | Bland annat en syntetisk analog till produktionstabellen med identifierarliknande features, konstanta fält och klassobalans |

### 12.2 Mått som ska utvärderas

- **För målstorheter med känt facit:** bias, MAE, RMSE, fel i antal dolda fall.
- **För intervall:** empirisk täckning, intervallbredd, hur ofta metoden avstår från skattning.
- **För klassificerare:** precision, recall, balanced accuracy, PR-AUC/ROC-AUC där de är meningsfulla, kalibreringsmått; redovisa per klass.
- **För perturbation:** recoveryfördelning, effektiva eventantal, fold-/seed-variation, `c`-intervall, omfattning av SMOTE-kontaminering och antal syntetiska rader.
- **För drift:** beräkningstid, minne, reproducerbarhet och bakåtkompatibilitet.

### 12.3 Krav innan en metod kan föreslås för pilot

1. Nollmörkertal får inte **systematiskt** ge stora positiva skattningar utan adekvat varning.
2. Rimlig noggrannhet i syntetiska scenarier som **uppfyller metodens egna antaganden**.
3. Tydlig försämring/varning när antaganden bryts, exempelvis SAR-data analyserade som SCAR.
4. Stabilitet eller korrekt osäkerhetsredovisning över slumpfrön, folds och samplingsalternativ.
5. Ingen dataläckageväg genom SMOTE, scaler, PCA, calibration eller hyperparameterinställning.
6. Befintlig ordinarie ML-träning och original-JBG ger oförändrade regressionstestresultat.
7. Numeriska gränser för godkännande bestäms **före** slutlig benchmark, inte i efterhand.

Verkliga produktionsdata kan användas för robusthets-, rimlighets- och känslighetstester men **inte** för att beräkna ett facitbaserat skattningsfel när det sanna mörkertalet saknas.

---

## 13. Revisionsplan – stegvis införande

| Revision | Leverans | Definition av klart |
|---|---|---|
| **DN-01 – Metodkontrakt och baseline** | Lås nuvarande JBG-formler/kodvägar, notation, estimands, existerande testsvar, SQL-/CSV-beteende och krav. | V1 reproduceras och all statistik har definierad målstorhet. |
| **DN-02 – Separat samplingmotor** | NONE, SMOTE, CLEAN_SMOTE, UNDER; korrekt CV-isolering, provenance och kontamineringstest. | Alla policies fungerar isolerat utan dataläckage och utan påverkan på ordinarie pipeline. |
| **DN-03 – Adaptiv recovery och stabil `c`** | LR/MLP, två recovery-varianter, klassberoende flipordning, osäkerhet, kvalitetsstatusar, noggrant testad stoppregel. | Extremvärden och osäkra estimatorer hanteras begripligt; inte genom godtycklig klippning. |
| **DN-04 – Felmärknings- och känslighetsanalys** | Matrisformler, ensidiga/dubbelsidiga antaganden och intervall över `α,β`. | Analytiska facit, constraints och randfall klaras utan kontrollmängd för intervallalternativet. |
| **DN-05 – PU-SCAR / kalibrerad probabilistisk metod** | PU-SCAR med tydligt identifikationsantagande, LR/MLP, kalibrering och eventuellt kontrollinformationsstödd referens. | Godkända syntetiska scenarier och tydliga `not_identifiable`-utfall när antaganden inte räcker. |
| **DN-06 – Gemensam benchmark och metodgranskning** | Jämför alla estimatorer över förregistrerad facitmatris, med samplings- och flipablationer. | Bias, fel, täckning, robusthet och beräkningskostnad dokumenterade; beslut inför pilot. |
| **DN-07 – FastAPI/API/GUI-integration** | Metodval, inställningar, osäkerhet, antaganden, projektpersistens och export. | Gamla projekt kan återläsas och originalfunktioner fungerar utan regressioner. |
| **DN-08 – Kontrollerad produktionspilot** | Realdataförsök utan känt facit; diagnostik, känslighetsanalys och jämförelser. | Resultat och begränsningar kan redovisas sakligt; inga osäkra punktskattningar presenteras som fakta. |

**Föreslagen kvalitetsgrind:** Efter DN-01–DN-06 tas ett separat beslut om vilka delar som får gå vidare till DN-07/DN-08. Original-JBG v1 ska alltid förbli åtkomlig.

---

## 14. Praktisk arbetsordning för DN-01

1. Kontrollera aktuell git-revision/zip och hitta alla kodvägar där `c`, alpha-vikter, `D`, sampling och CV beräknas.
2. Dokumentera exakta matematiska uttryck och eventuella avvikelser mellan kod och tidigare metodbeskrivningar.
3. Etablera reproducerbara baseline-fall för majoritets- och minoritetsmål; använd syntetiska dataset utan produktionsuppgifter.
4. Frys resultatformat, begreppsdefinitioner och schema-versioner.
5. Skriv en separat testdesign för in-sample-recovery jämfört med oberoende validering så att vi inte oavsiktligt byter estimand.
6. Specificera CLEAN_SMOTE och under-sampling tillräckligt exakt för att implementeringarna ska bli reproducerbara.
7. Förhandsbestäm benchmarkmått och beslutskriterier för att undvika att välja metod utifrån gynnsamma utfall i efterhand.
8. Granska DN-01-specifikationen tillsammans **innan** en patch av produktionsmotorn påbörjas.

### Föreslagna acceptanstester på kodnivå

- Dataset där målklass är majoritet och minst 85 %.
- Dataset där målklass är minoritet och färre än 15 %.
- `r=0`, mycket litet positivt `r`, och `r≈1`.
- Fold med alltför få behöriga SMOTE-grannar.
- Osamplad respektive översamplad träningsdel: ingen leakage in i valideringsdelen.
- Identifierarliknande och konstanta variabler.
- Gamla sparade projektkonfigurationer med `LINEAR`, `SEPARATED`, 20 % flip och vinnande klassificerare.
- Numeriska randfall vid `α+β≈1`, `q≈0` eller `q≈1` i matrisbaserade estimatorer.

---

## 15. Öppna beslut och vetenskapliga risker

| Fråga | Nuvarande hållning |
|---|---|
| Ska in-sample-recovery ersättas? | **Inte beslutat.** Utvärdera vad alternativa protokoll faktiskt skattar. |
| Ska `c≤20` vara stoppregel? | **Nej, inte ensamt.** Först stabilitet, osäkerhet, minimalt antal event och kvalitetskontroll. |
| Ska `CLEAN_SMOTE` alltid användas för majoritetsmål? | **Inte beslutat.** Huvudkandidat för benchmark, inte tvingande standard. |
| Ska undersampling krävas i majoritetsfall? | **Nej.** Tidigare experiment visade att det kan försämra MLP. Behåll som explicit alternativ. |
| Är logistisk regression alltid bättre än MLP? | **Nej.** LR är referensmodell; MLP kan vinna på SMOTE och icke-linjära samband. |
| Ska JBG:s `D` kallas procent mörkertal? | **Nej**, inte före en försvarbar koppling till `H` eller `U` demonstrerats. |
| Kan vi bestämma det sanna mörkertalet från enbart produktionsdata? | **Generellt inte entydigt.** Extra antaganden behövs och ska dokumenteras. |
| Är PU automatiskt identifierbart? | **Nej.** SCAR och annan struktur är villkor, inte garanti. |
| Ska formler med kontrollmängd användas utan sådan data? | **Nej.** Kontrollmängdsstödda estimatorer är referensmetoder eller produktionsalternativ endast om kontrollinformation finns. |
| Ska nya estimatorer jämföras genom lika numeriska värden? | **Endast om de skattar samma målstorhet.** JBG-`D` hålls separat tills dess tolkning validerats. |

---

## 16. Samlad rekommendation

Det lämpligaste nästa steget är att genomföra **DN-01**, med ordentligt versionsfryst baseline och full matematisk/kodmässig metodspecifikation. Därefter kan DN-02 och DN-03 utveckla den förbättrade JBG-komponenten med adaptiv flip och explicit sampling. Parallellt, men i egna moduler, byggs antagandebaserade alternativ i DN-04 och DN-05. DN-06 jämför **faktisk skattningsförmåga mot syntetiskt facit** där en sådan jämförelse överhuvudtaget är möjlig.

Vi behåller därmed projektets ursprungliga idé — att skatta okända mörkertal utan att känna facit i verkliga tillämpningar — samtidigt som vi gör gränsen mellan **observerade data**, **metodantaganden**, **klassificeringsdiagnostik** och **identifierbara mörkertal** tydligare.

**Ingen produktionspatch föreslås innan dessa metodgrindar har passerats.**

---

## 17. Historik och referensunderlag inom projektet

Detta dokument sammanfattar arbetsdiskussionen och de experiment som tidigare redovisats i konversationen. Relevanta arbetsfiler som omnämnts där inkluderar bland annat:

- `JBGautoclass-jupyter-dev (15).zip` – kodbasen vid ursprungsfelsökningen.
- `autoclassconfig_sanktioner_robert.granat_train(1).json` – körkonfiguration.
- SQL-profil av produktionstabellen och klassuppdelade sammanfattningsmått.
- Ett syntetiskt tabellunderlag (10 000 rader, version 2).
- `darknumber_lr_mlp_adaptive_results.csv` – LR/MLP och adaptiv perturbation.
- `darknumber_known_truth_results.csv` – första facitscenarier.
- `darknumber_probability_population_summary.csv` – hård och sannolikhetsbaserad recovery.
- `darknumber_sampling_truth_summary.csv` – klassberoende sampling och dold-falls-AUC.
- `darknumber_clean_smote_summary.csv` – kontamineringsmedveten SMOTE.
- `jbg_formula_study/formula_experiment_summary.csv` – alternativa formler under kontrollinformation.

Arbetsfilerna är experimentunderlag, **inte en formellt granskad vetenskaplig validering**. En del metodbeskrivningar och konfigurationsvärden härrör från tidigare granskning; DN-01 ska verifiera dem igen mot den faktiska revision som väljs som baseline.
