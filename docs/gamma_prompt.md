# Prompt per ricreare la presentazione con Gamma

## Procedura consigliata

1. In Gamma scegli **Crea con AI > Incolla testo**.
2. Seleziona una presentazione da **14 card**, formato **16:9**.
3. Incolla il prompt qui sotto.
4. Carica anche `docs/presentation_outline.md` come testo di riferimento, se
   Gamma consente di aggiungere fonti.
5. Dopo la generazione, controlla soprattutto le slide 5, 7, 9, 10, 11 e 12:
   diagrammi e flussi devono mantenere l'ordine tecnico indicato.

## Prompt

```text
Crea una presentazione professionale in italiano di 14 slide sul progetto
"Pefforza 4", destinata a una presentazione scolastica/universitaria e a un
portfolio tecnico.

OBIETTIVO
Spiegare in modo tecnico ma accessibile come il progetto collega una
scacchiera fisica di Forza 4 a computer vision, reinforcement learning,
minimax, realta aumentata e voce. Il messaggio centrale e che il valore del
progetto nasce dall'integrazione verificabile tra percezione, decisione,
interazione e affidabilita, non da un singolo algoritmo.

STILE
- moderno, pulito, energico, non corporate;
- formato 16:9;
- sfondi alternati blu notte/quasi nero e avorio caldo;
- palette ispirata al Forza 4: blu cobalto, rosso, giallo, verde menta;
- titoli grandi e conclusivi, non semplici etichette;
- poco testo visibile, massimo 3 idee per slide;
- diagrammi semplici, tabelloni 6x7 e frecce AR;
- niente loghi inventati, foto stock, robot umanoidi o icone AI generiche;
- non usare card grid ripetitive;
- usa note speaker o testo secondario per i dettagli.

DATI DA NON MODIFICARE
- Python 3.10-3.13;
- 3 modalita: CLI, GUI Pygame, assistente fisico AR;
- 5 difficolta: easy, medium, hard, impossible, neural;
- checkpoint PPO: circa 501.760 timestep;
- benchmark PPO vs minimax depth 4, 40 partite: 27,5% vittorie PPO,
  72,5% sconfitte;
- 108 test automatizzati;
- computer vision: board 6x7, warp nominale 700x600, margine ROI 20%,
  soglia fill 30%;
- visione: 1=rosso, 2=giallo;
- modello: 1=self, 2=opponent.

STRUTTURA DELLE 14 SLIDE

1. Copertina
Titolo: "Pefforza 4"
Claim: "Una scacchiera fisica diventa un sistema intelligente."
Visuale: tabellone Forza 4 con freccia AR sulla colonna 4.
Metriche: 3 modalita, 5 difficolta, 108 test.

2. La sfida
Titolo: "Il problema non e scegliere una colonna. E mantenere coerenti
quattro mondi."
Visuale a flusso: realta fisica -> percezione visiva -> regole e IA ->
feedback utente.
Rischi: rumore, latenza, credibilita tattica.

3. Evoluzione
Titolo: "In cinque mesi: da demo monolitica a sistema installabile e
verificato."
Timeline:
- 10 dicembre 2025: prototipo PPO + webcam + TTS;
- 17 dicembre 2025: board fisico, calibrazione, notebook e checkpoint;
- 19 maggio 2026: package, CI e test;
- 19 maggio 2026: minimax, safety net e watchdog;
- 25 maggio 2026: test vision e diagnostica live.

4. Prodotto
Titolo: "Un solo motore supporta tre esperienze e cinque livelli di sfida."
Mostra mockup distinti per CLI, GUI Pygame e AR fisica.
In basso: easy=random, medium=1-ply, hard=minimax depth 5,
impossible=iterative deepening, neural=PPO.

5. Architettura
Titolo: "Training e runtime restano separati, ma parlano la stessa lingua."
Diagramma a due corsie.
Runtime: webcam -> BoardDetector warp+HSV -> grid 6x7 -> agent registry ->
AR+voce.
Training: Connect4Env -> SinglePlayerWrapper -> PPO -> checkpoint.
Il checkpoint entra nell'agent registry come neural tier.

6. Core di gioco
Titolo: "La matrice 6x7 e il contratto comune di tutto il sistema."
Visuale: board numerico.
Stato: 42 celle 0/1/2.
Azione: colonna 0-6, gravita automatica.
Reward: +1 vittoria, 0 step/pareggio, -1 sconfitta nel wrapper.
Mossa illegale: -10.

7. Come ha imparato
Titolo: "Il PPO ha imparato giocando, non guardando immagini."
Ciclo: osservazione 42 valori -> azione colonna -> reward -> nuovo stato con
mossa avversaria -> update PPO.
Metriche: 501.760 timestep, rollout 2.048, batch 64, gamma 0,99.
Sottolinea che la computer vision non partecipa al training.

8. Valutazione
Titolo: "Il neurale ha appreso le basi. La ricerca classica ha vinto il
confronto."
Barra diretta 27,5% vittorie PPO contro 72,5% sconfitte.
Spiega: training contro avversario casuale; Connect 4 favorisce alpha-beta;
scelta finale di architettura ibrida.

9. Intelligenza ibrida
Titolo: "La forza finale combina strategia e garanzie deterministiche."
A sinistra scala delle difficolta.
A destra decision tree:
posso vincere ora? -> gioca vittoria;
altrimenti l'avversario vince ora? -> blocca;
altrimenti delega a random/heuristic/minimax/PPO.

10. Computer vision: calibrazione
Titolo: "Quattro click trasformano una camera inclinata in una griglia
misurabile."
Prima/dopo: quadrilatero prospettico -> matrice omografica 3x3 -> board
rettificato 700x600.
Specificare che l'ordine dei click viene canonicalizzato TL/TR/BR/BL.

11. Computer vision: classificazione
Titolo: "Ogni cella diventa una misura esplicita di colore e confidenza."
Visuale: board con una cella zoomata.
HSV: rosso H 0-12 e H 165-180; giallo H 18-45.
Margine ROI 20%, fill threshold 30%, confidence come rapporto di pixel.

12. Demo fisica
Titolo: "Dal frame alla freccia AR: sei trasformazioni controllate."
Sequenza: cattura -> vision -> swap prospettiva -> safety net/agente ->
mirror colonna -> freccia AR + voce.
Mostra vision view e agent view prima/dopo swap_perspective().

13. Qualita
Titolo: "L'affidabilita non e arrivata alla fine. E diventata una feature."
Metriche: 108 test, CI su 4 versioni Python, zero hardware nei test.
Tre casi:
- minaccia ignorata -> safety net + watchdog -> test di partite complete;
- warp ruotato -> corner sorting -> test delle permutazioni;
- animazione saltata -> clock locale -> regressione GUI.
Menziona TTS asincrono e fail-soft.

14. Roadmap e conclusione
Titolo: "Il prossimo passo parte dai limiti reali."
Roadmap:
P0 HSV adattivo;
P1 calibrazione automatica con ArUco/contorni;
P2 self-play competitivo;
P3 ONNX + OpenCV.js per web/smartphone.
Takeaway finale:
"L'intelligenza utile nasce quando percezione, algoritmi e affidabilita
vengono progettati insieme."

Non inventare metriche aggiuntive. Mantieni i diagrammi tecnicamente corretti,
con frecce nella direzione descritta e senza semplificare la distinzione tra
computer vision e training PPO.
```

## Revisione dopo la generazione

- Sostituire eventuali immagini stock con diagrammi o board 6x7.
- Controllare che Gamma non presenti `neural` come difficolta piu forte.
- Verificare che PPO riceva una matrice, non un'immagine della webcam.
- Verificare che `swap_perspective` e il mirror della colonna siano due
  trasformazioni diverse.
- Esportare in PowerPoint e controllare font, note e allineamenti.
