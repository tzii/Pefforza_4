# Pefforza 4 - Presentation Outline

## Pubblico target

- Docenti, compagni di corso e commissioni scolastiche/universitarie.
- Persone con basi di programmazione, ma non necessariamente esperte di reinforcement learning o computer vision.
- Recruiter o visitatori portfolio interessati a capire sia il risultato sia il processo ingegneristico.

## Messaggio principale

Pefforza 4 non e solo un modello che sceglie una colonna: e un sistema completo
che collega una scacchiera fisica a percezione visiva, logica di gioco,
reinforcement learning, ricerca classica, realta aumentata e feedback vocale.
L'evoluzione del progetto mostra anche una lezione importante: un modello
neurale puo apprendere una strategia, ma un prodotto affidabile nasce
dall'integrazione tra apprendimento, algoritmi deterministici, test e strumenti
di diagnosi.

## Tono e durata

- Durata consigliata: 12-16 minuti, piu 3-5 minuti di demo.
- Linguaggio: tecnico ma accessibile, con i termini specialistici spiegati al primo uso.
- Ritmo: una tesi chiara per slide, visuale dominante e dettaglio affidato alle note speaker.

## Scaletta slide-by-slide

### 1. Pefforza 4

**Claim:** una scacchiera fisica diventa un sistema intelligente.

**Visuale:** title slide con tabellone Forza 4, freccia AR e metriche sintetiche.

**Note speaker:**
- Presentare il progetto come integrazione di AI, computer vision e interaction design.
- Anticipare le tre modalita: terminale, GUI Pygame e assistente fisico AR.
- Chiarire che la presentazione mostrera sia il risultato sia l'evoluzione tecnica.

### 2. La vera sfida e mantenere coerenti quattro mondi

**Claim:** il problema non e solo scegliere una mossa, ma collegare realta,
percezione, regole e feedback senza perdere affidabilita.

**Visuale:** flusso a quattro blocchi con i rischi principali: prospettiva,
illuminazione, latenza e credibilita tattica.

**Note speaker:**
- Il Forza 4 digitale e semplice da rappresentare; il mondo fisico introduce rumore.
- Una singola incoerenza tra colori, ID giocatori o coordinate produce una mossa sbagliata.
- La modularita nasce dalla necessita di isolare e verificare ogni passaggio.

### 3. Dal prototipo al prodotto testato

**Claim:** in cinque mesi il progetto passa da demo monolitica a package
installabile, diagnostico e verificato.

**Visuale:** timeline dicembre 2025 - maggio 2026.

**Note speaker:**
- 10 dicembre: primo prototipo con PPO, webcam e voce.
- 17 dicembre: modalita fisica, calibrazione e notebook di sperimentazione.
- Maggio: refactor del package, minimax, safety net, watchdog, test vision e CI.

### 4. Un motore, tre esperienze, cinque livelli

**Claim:** lo stesso core supporta modalita e difficolta diverse senza duplicare
la logica.

**Visuale:** tre mockup editabili per CLI, GUI e AR; barra delle difficolta.

**Note speaker:**
- CLI per debugging rapido, GUI per esperienza digitale, AR per la demo fisica.
- Easy, medium, hard, impossible e neural condividono lo stesso contratto Agent.
- Il registro delle difficolta rende l'estensione locale e riusabile.

### 5. Percezione, stato, decisione, interazione

**Claim:** l'architettura separa il training dalla pipeline runtime, collegandoli
attraverso la stessa matrice 6x7.

**Visuale:** architettura a due corsie: runtime fisico e training PPO.

**Note speaker:**
- OpenCV produce una griglia discreta, non immagini in ingresso al modello.
- rules.py e Connect4Env definiscono il significato dello stato.
- Il checkpoint PPO e solo uno dei possibili motori decisionali.

### 6. La matrice 6x7 e il contratto comune

**Claim:** regole, test, agenti e visione comunicano attraverso una
rappresentazione minima e verificabile.

**Visuale:** tabellone numerico con schema stato-azione-ricompensa.

**Note speaker:**
- Stato: array NumPy int8 con valori 0, 1 e 2.
- Azione: una colonna tra 0 e 6; la gravita determina la riga.
- Ricompense: +1 vittoria, 0 transizione/pareggio, -10 mossa illegale; il wrapper traduce una vittoria avversaria in -1.

### 7. Ha imparato giocando, non guardando immagini

**Claim:** PPO apprende in simulazione tramite tentativi, ricompense e
aggiornamenti iterativi della policy.

**Visuale:** ciclo osservazione -> policy -> azione -> ricompensa -> update.

**Note speaker:**
- La policy MLP riceve 42 valori e restituisce una delle sette colonne.
- SinglePlayerWrapper esegue automaticamente la mossa dell'avversario casuale.
- Il checkpoint incluso registra circa 501.760 timestep di training.

### 8. Il neurale apprende, ma la ricerca classica e piu forte

**Claim:** la valutazione ha trasformato un limite del PPO in una scelta
architetturale consapevole.

**Visuale:** confronto PPO contro minimax depth 4 e sintesi dei limiti del training.

**Note speaker:**
- Benchmark registrato nella cronologia: 27,5% vittorie e 72,5% sconfitte su 40 partite.
- L'avversario casuale insegna le basi ma non prepara a tattiche profonde.
- Da qui nasce l'approccio ibrido: neural per sperimentazione, minimax per forza reale.

### 9. Strategia piu garanzie deterministiche

**Claim:** ogni difficolta sceglie una strategia, mentre la safety net impedisce
gli errori tattici immediati.

**Visuale:** scala delle difficolta e decision tree win -> block -> delegate.

**Note speaker:**
- Hard usa Negamax con alpha-beta e ordinamento center-first.
- Impossible usa iterative deepening con budget temporale.
- La safety net controlla prima vittorie e minacce a un ply, anche se l'agente sottostante e debole.

### 10. Quattro click rendono misurabile una camera inclinata

**Claim:** la calibrazione prospettica trasforma un quadrilatero reale in un
tabellone rettificato 700x600.

**Visuale:** camera inclinata, quattro corner, omografia e board normalizzata.

**Note speaker:**
- L'utente puo cliccare gli angoli in qualunque ordine.
- Il detector li ordina in TL, TR, BR, BL e calcola una matrice 3x3.
- Il warp rende le 42 celle regolari e quindi confrontabili.

### 11. Ogni cella diventa una misura di colore

**Claim:** HSV, ROI interne e soglie esplicite rendono il riconoscimento
semplice da spiegare e testare.

**Visuale:** board 6x7, zoom su una cella, bande HSV e barra di fill ratio.

**Note speaker:**
- Il rosso richiede due intervalli hue per il wrap a 0/180; il giallo uno.
- Una ROI esclude il 20% dei bordi per ignorare la plastica della griglia.
- Una cella e occupata quando almeno il 30% dei pixel appartiene a un colore; la confidence aiuta la diagnosi.

### 12. Dal frame alla freccia AR

**Claim:** una mossa fisica attraversa sei trasformazioni controllate prima di
tornare all'utente.

**Visuale:** sequenza webcam -> grid -> swap -> agent -> mirror -> overlay/voice.

**Note speaker:**
- La visione usa 1=rosso e 2=giallo; il modello usa 1=self e 2=opponent.
- swap_perspective evita di addestrare un modello separato per ciascun colore.
- Poiche il feed e specchiato, la colonna viene rimappata prima di disegnare la freccia.

### 13. L'affidabilita e una feature

**Claim:** test, CI, watchdog e componenti fail-soft trasformano bug osservati
in regressioni automatizzate.

**Visuale:** metriche di qualita e tre casi problema -> soluzione -> prova.

**Note speaker:**
- 108 test headless, senza webcam, audio o modello obbligatorio.
- CI su Python 3.10-3.13 con Ruff, formattazione, Mypy e Pytest con coverage.
- Esempi: minacce ignorate, warp ruotato e animazione saltata dopo il tempo di calcolo dell'AI.

### 14. La prossima evoluzione parte dai limiti reali

**Claim:** Pefforza e gia una piattaforma estendibile; la roadmap migliora
robustezza visiva, apprendimento e accessibilita.

**Visuale:** roadmap in quattro tappe e takeaway finale.

**Note speaker:**
- HSV adattivo e rilevamento automatico eliminerebbero gran parte della calibrazione manuale.
- Self-play competitivo o avversari curricolari renderebbero il PPO piu forte.
- Un export ONNX/OpenCV.js potrebbe portare l'assistente su browser e smartphone.
- Chiusura: il valore principale e l'integrazione verificabile, non un singolo algoritmo.
