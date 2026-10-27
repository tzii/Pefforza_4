# Pefforza 4 - Presentation Outline

> 🇬🇧 [English version](../presentation_outline.md)

## Pubblico target

- Docenti, compagni di corso e commissioni scolastiche/universitarie.
- Persone con basi di programmazione, ma non necessariamente esperte di
  reinforcement learning o computer vision.
- Recruiter o visitatori del portfolio interessati a capire sia il risultato
  sia il processo ingegneristico.

## Messaggio principale

Pefforza 4 non è solo un modello che sceglie una colonna: è un sistema
completo che collega una scacchiera fisica a percezione visiva, logica di
gioco, un solver esatto, una policy appresa, realtà aumentata e feedback
vocale. L'evoluzione del progetto insegna anche una lezione importante:
"perfetto" è un'affermazione che va misurata. Una rete neurale può imparare
una strategia, ma un prodotto affidabile nasce dall'integrazione tra
apprendimento, algoritmi esatti, test e strumenti di diagnosi - e dal
controllo di ogni mossa contro un oracolo.

## Tono e durata

- Durata consigliata: 12-16 minuti, più 3-5 minuti di demo.
- Linguaggio: tecnico ma accessibile, con i termini specialistici spiegati
  al primo uso.
- Ritmo: una tesi chiara per slide, visuale dominante e dettagli nelle note
  speaker.

## Scaletta slide per slide

### 1. Pefforza 4

**Claim:** una scacchiera fisica diventa un sistema intelligente.

**Visuale:** title slide con tabellone Forza 4, freccia AR e metriche
sintetiche.

**Note speaker:**
- Presentare il progetto come integrazione di IA, computer vision e
  interaction design.
- Anticipare le tre modalità: terminale, GUI Pygame e assistente fisico AR.
- Chiarire che la presentazione mostrerà sia il risultato sia l'evoluzione
  tecnica.

### 2. La vera sfida è mantenere coerenti quattro mondi

**Claim:** il problema non è solo scegliere una mossa, ma collegare realtà,
percezione, regole e feedback senza perdere affidabilità.

**Visuale:** flusso a quattro blocchi con i rischi principali: prospettiva,
illuminazione, latenza e credibilità tattica.

**Note speaker:**
- Il Forza 4 digitale è semplice da rappresentare; il mondo fisico introduce
  rumore.
- Una singola incoerenza tra colori, ID giocatori o coordinate produce una
  mossa sbagliata.
- La modularità nasce dalla necessità di isolare e verificare ogni passaggio.

### 3. Dal prototipo al prodotto verificato

**Claim:** il progetto passa da demo monolitica a package installabile,
diagnosticabile e misurato.

**Visuale:** timeline da dicembre 2025 a ottobre 2026.

**Note speaker:**
- Dicembre: primo prototipo con PPO, webcam e voce; poi modalità fisica,
  calibrazione e notebook di sperimentazione.
- Maggio: refactor del package, minimax, safety net, watchdog, test vision e
  CI.
- Settembre: motori bitboard, validazione delle letture, solver esatto.
- Ottobre: opening book e oracolo esatto (gioco perfetto), localizzazione
  automatica della scacchiera e adattamento alla luce, rete neurale
  insegnata dal solver.

### 4. Un motore, tre esperienze, cinque livelli

**Claim:** lo stesso core supporta modalità e difficoltà diverse senza
duplicare la logica.

**Visuale:** tre mockup per CLI, GUI e AR; barra delle difficoltà.

**Note speaker:**
- CLI per il debugging rapido, GUI per l'esperienza digitale, AR per la demo
  fisica.
- easy, medium, hard, impossible e neural condividono lo stesso contratto
  Agent.
- Il registro delle difficoltà rende le estensioni locali e riusabili.

### 5. Percezione, stato, decisione, interazione

**Claim:** l'architettura separa la generazione offline dei dati e
l'addestramento dalla pipeline runtime, collegandoli con la stessa matrice
6x7.

**Visuale:** architettura a due corsie: runtime fisico e corsia offline
(solver nativo -> opening book / oracolo / dati teacher -> CNN distillata).

**Note speaker:**
- OpenCV produce una griglia discreta; i modelli non vedono mai immagini
  della camera.
- rules.py e Connect4Env definiscono il significato dello stato.
- Book, oracolo e rete sono generati offline e distribuiti come file.

### 6. La matrice 6x7 è il contratto comune

**Claim:** regole, test, agenti e visione comunicano attraverso una
rappresentazione minima e verificabile.

**Visuale:** tabellone numerico con schema stato-azione-ricompensa.

**Note speaker:**
- Stato: array NumPy int8 con valori 0, 1 e 2.
- Azione: una colonna tra 0 e 6; la gravità determina la riga.
- Ricompense: +1 vittoria, 0 transizione/pareggio, -10 mossa illegale; il
  wrapper di addestramento traduce una vittoria avversaria in -1.

### 7. Il gioco perfetto richiede un opening book

**Claim:** una ricerca in Python puro non dimostra l'apertura in tempo,
quindi le risposte si calcolano una volta, offline, e si consultano.

**Visuale:** albero di gioco in cui le mosse dell'IA sono fissate e solo
l'avversario si ramifica, fino al ply 17; dimensione: 533k posizioni in
950 KiB.

**Note speaker:**
- Misurato: con 3 s si dimostrava solo il 4-56% delle posizioni ai ply 8-13.
- Un solver nativo (Pascal Pons) calcola la mossa fortemente ottimale per
  ogni posizione che l'IA può raggiungere fino al ply 17, per entrambi i
  colori.
- Dopo il book il solver Python dimostra ogni mossa; le dimostrazioni
  alternate alla radice lo tengono sotto il budget di 3 s.

### 8. "Perfetto" si misura, non si dichiara

**Claim:** un oracolo esatto valuta ogni mossa di ogni livello.

**Visuale:** grafico a barre delle mosse che conservano il valore sulle
linee di gioco: impossible 100%, neural 96,3%, hard 90,8%,
medium 77,5%, easy 65,6%.

**Note speaker:**
- 729 posizioni con il punteggio esatto di ogni colonna.
- Conservare il valore: una partita vinta resta vinta, una patta resta
  patta.
- Battere avversari deboli dimostra poco; l'oracolo mostra dove sbaglia ogni
  motore.

### 9. La rete impara dal solver

**Claim:** distillare etichette esatte ha trasformato il livello più debole
in uno forte, e il percorso di apprendimento è la lezione.

**Visuale:** prima/dopo: PPO contro avversario casuale (59,7%) contro CNN
distillata dalle etichette del solver (96,3% di mosse che
conservano il valore sulle linee di gioco).

**Note speaker:**
- La vecchia policy giocava sempre per prima, contro mosse casuali.
- La nuova: una piccola CNN su piani self/avversario/vuoto, addestrata su
  ~308k posizioni etichettate dal solver (più le loro speculari).
- Gioca secondo il proprio giudizio, senza ricerca né safety net.

### 10. La scacchiera si trova da sola

**Claim:** il reticolo dei fori trasforma una camera inclinata in una
griglia misurabile, senza click.

**Visuale:** camera inclinata, fori rilevati, reticolo 6x7, omografia,
tabellone raddrizzato 700x600.

**Note speaker:**
- I fori sono le macchie non blu dentro la cornice blu; i quattro fori
  d'angolo definiscono il reticolo.
- Il reticolo deve prevedere i fori rilevati, altrimenti l'utente clicca i
  quattro angoli (in qualsiasi ordine).
- Il warp rende le 42 celle regolari e confrontabili.

### 11. Ogni cella diventa una misura di colore che si adatta

**Claim:** bande HSV, ROI interne e soglie esplicite rendono il
riconoscimento facile da spiegare - e ogni lettura validata lo riadatta
alla luce.

**Visuale:** tabellone 6x7, zoom su una cella, bande HSV che si spostano tra
luce forte e fioca, barra del fill ratio.

**Note speaker:**
- Il rosso richiede due intervalli di hue per il wrap a 0/180; il giallo uno.
- La ROI esclude il 20% dei bordi; una cella è occupata quando il 30% dei
  pixel appartiene a un colore.
- Le nuove soglie vengono adottate solo se riproducono esattamente la
  lettura validata.

### 12. Dal frame alla freccia AR

**Claim:** una mossa fisica attraversa trasformazioni controllate e
validate prima di tornare all'utente.

**Visuale:** webcam -> griglia -> validazione -> swap -> agente -> specchio
-> overlay/voce.

**Note speaker:**
- Il validatore scarta le letture impossibili (una mano, una pedina a metà
  caduta).
- La visione usa 1=rosso e 2=giallo; gli agenti 1=self e 2=avversario;
  swap_perspective traduce.
- Il feed è specchiato, quindi la colonna pronunciata viene tradotta sulla
  scacchiera fisica.

### 13. L'affidabilità è una feature

**Claim:** test, CI, oracolo, watchdog e componenti fail-soft trasformano i
bug osservati in regressioni automatizzate.

**Visuale:** metriche di qualità e tre casi problema -> soluzione -> prova.

**Note speaker:**
- 273 test headless, senza webcam, audio o modello obbligatorio; i cicli
  di CLI, GUI e AR sono testati end to end.
- CI su Python 3.10-3.13 più Windows e macOS, con Ruff, Mypy, una soglia di
  copertura e uno smoke test della wheel.
- Esempi: minaccia ignorata (safety net + watchdog), dimostrazione vincente
  "affamata" (ricerca alternata), luce fioca (adattamento del colore
  auto-verificato).

### 14. La prossima evoluzione parte dai limiti reali

**Claim:** Pefforza gioca già in modo perfetto; la roadmap riguarda il mondo
reale.

**Visuale:** roadmap in quattro tappe e takeaway finale.

**Note speaker:**
- Foto reali della webcam come test di regressione; rilocalizzazione
  automatica quando la camera si sposta.
- Copertura fuori book per le partite iniziate da altri; vittorie più rapide
  oltre il book.
- Gioco perfetto nella demo del sito; export ONNX della rete.
- Chiusura: il valore principale è l'integrazione verificabile, non un
  singolo algoritmo.
