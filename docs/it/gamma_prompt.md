# Prompt per ricreare la presentazione con Gamma

> 🇬🇧 [English version](../gamma_prompt.md) (genera la presentazione in inglese)

## Procedura consigliata

1. In Gamma scegli **Crea con AI > Incolla testo**.
2. Seleziona una presentazione da **14 card**, formato **16:9**.
3. Incolla il prompt qui sotto.
4. Carica anche `docs/it/presentation_outline.md` come testo di riferimento,
   se Gamma consente di aggiungere fonti.
5. Dopo la generazione, controlla soprattutto le slide 5, 7, 8, 9, 10 e 12:
   diagrammi e flussi devono mantenere l'ordine tecnico indicato.

## Prompt

```text
Crea una presentazione professionale in italiano di 14 slide sul progetto
"Pefforza 4", destinata a una presentazione scolastica/universitaria e a un
portfolio tecnico.

OBIETTIVO
Spiegare in modo tecnico ma accessibile come il progetto collega una
scacchiera fisica di Forza 4 a computer vision, un solver esatto del gioco,
una policy appresa, realta aumentata e voce. Il messaggio centrale: "perfetto"
e un'affermazione che va misurata, e il valore del progetto nasce
dall'integrazione verificabile tra percezione, decisione, interazione e
affidabilita, non da un singolo algoritmo.

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
- opening book: 533.468 posizioni fino al ply 17, 950 KiB, generato da un
  solver nativo (Pascal Pons);
- oracolo esatto: 729 posizioni con il punteggio di ogni colonna;
- mosse che conservano il valore sulle linee di gioco: impossible 100%,
  neural 96,3%, hard 90,8%, medium 77,5%, easy 65,6%;
- vecchio modello neurale (PPO contro avversario casuale): 59,7%;
- 273 test automatizzati, CI su Ubuntu (Python 3.10-3.13), Windows e macOS;
- computer vision: board 6x7, warp nominale 700x600, margine ROI 20%,
  soglia fill 30%;
- visione: 1=rosso, 2=giallo;
- agenti: 1=self, 2=avversario.

STRUTTURA DELLE 14 SLIDE

1. Copertina
Titolo: "Pefforza 4"
Claim: "Una scacchiera fisica diventa un sistema intelligente."
Visuale: tabellone Forza 4 con freccia AR sulla colonna 4.
Metriche: 3 modalita, 5 difficolta, 100% di mosse perfette.

2. La sfida
Titolo: "Il problema non e scegliere una colonna. E mantenere coerenti
quattro mondi."
Visuale a flusso: realta fisica -> percezione visiva -> regole e IA ->
feedback utente.
Rischi: rumore, latenza, credibilita tattica.

3. Evoluzione
Titolo: "Da demo monolitica a sistema installabile e misurato."
Timeline:
- dicembre 2025: prototipo PPO + webcam + TTS, poi board fisico e
  calibrazione;
- maggio 2026: package, CI, test, minimax, safety net e watchdog;
- settembre 2026: motori bitboard, validazione delle letture, solver esatto;
- ottobre 2026: opening book + oracolo, localizzazione automatica,
  adattamento alla luce, rete insegnata dal solver.

4. Prodotto
Titolo: "Un solo motore supporta tre esperienze e cinque livelli di sfida."
Mostra mockup distinti per CLI, GUI Pygame e AR fisica.
In basso: easy=random, medium=1-ply, hard=bitboard depth 8,
impossible=opening book + solver esatto, neural=CNN distillata dal solver.

5. Architettura
Titolo: "Lavoro offline e runtime restano separati, ma parlano la stessa
lingua."
Diagramma a due corsie.
Runtime: webcam -> localizzazione -> warp + HSV adattivo -> validazione ->
grid 6x7 -> agent registry -> AR + voce.
Offline: solver nativo -> opening book, oracolo, dati teacher -> CNN
distillata.
Book e CNN entrano nell'agent registry come livelli impossible e neural.

6. Core di gioco
Titolo: "La matrice 6x7 e il contratto comune di tutto il sistema."
Visuale: board numerico.
Stato: 42 celle 0/1/2.
Azione: colonna 0-6, gravita automatica.
Reward: +1 vittoria, 0 step/pareggio, -1 sconfitta nel wrapper.
Mossa illegale: -10.

7. Apertura perfetta
Titolo: "Il gioco perfetto richiede un opening book."
Visuale: albero in cui le mosse dell'IA sono fissate e solo l'avversario si
ramifica, fino al ply 17.
Metriche: 533.468 posizioni, 950 KiB; prima: solo il 4-56% delle posizioni
ai ply 8-13 dimostrabile in 3 s.
Dopo il book il solver dimostra ogni mossa in circa 3 s.

8. Misura
Titolo: "Perfetto si misura, non si dichiara."
Grafico a barre delle mosse che conservano il valore sulle linee di gioco:
impossible 100%, neural 96,3%, hard 90,8%, medium 77,5%,
easy 65,6%.
Spiega: conservare il valore = una partita vinta resta vinta, una patta
resta patta.

9. Apprendimento
Titolo: "La rete impara dal solver."
Prima/dopo: PPO contro avversario casuale 59,7% -> CNN distillata dalle
etichette del solver 96,3%.
Nota: circa 308k posizioni etichettate piu le speculari; la rete gioca
senza ricerca.

10. Computer vision: localizzazione
Titolo: "La scacchiera si trova da sola."
Prima/dopo: vista inclinata -> fori rilevati -> reticolo 6x7 ->
omografia 3x3 -> board rettificato 700x600.
Ripiego manuale: 4 click in qualsiasi ordine, canonicalizzati TL/TR/BR/BL.

11. Computer vision: classificazione
Titolo: "Ogni cella diventa una misura di colore che si adatta alla luce."
Visuale: board con una cella zoomata.
HSV: rosso in due intervalli di hue (wrap a 0/180), giallo in uno; margine
ROI 20%, fill threshold 30%.
Le letture validate riadattano le bande; le nuove soglie vengono adottate
solo se riproducono esattamente la lettura.

12. Demo fisica
Titolo: "Dal frame alla freccia AR: trasformazioni validate."
Sequenza: cattura -> vision -> validazione -> swap prospettiva ->
safety net/agente -> mirror colonna -> freccia AR + voce.
Mostra vision view e agent view prima/dopo swap_perspective().

13. Qualita
Titolo: "L'affidabilita non e arrivata alla fine. E diventata una feature."
Metriche: 273 test, CI su 3 sistemi operativi, zero hardware nei test.
Tre casi:
- minaccia ignorata -> safety net + watchdog -> test di partite complete;
- dimostrazione vincente "affamata" -> ricerca alternata alla radice -> test
  con l'oracolo;
- luce fioca -> adattamento del colore auto-verificato -> test su scene
  disegnate.
Menziona TTS asincrono e fail-soft.

14. Roadmap e conclusione
Titolo: "Il prossimo passo parte dai limiti reali."
Roadmap:
P1 foto reali della webcam nei test, rilocalizzazione automatica;
P2 copertura fuori book, vittorie piu rapide oltre il book;
P3 gioco perfetto nel browser, export ONNX.
Takeaway finale:
"L'intelligenza utile nasce quando percezione, algoritmi e affidabilita
vengono progettati insieme - e misurati."

Non inventare metriche aggiuntive. Mantieni i diagrammi tecnicamente corretti,
con frecce nella direzione descritta e senza confondere computer vision,
solver esatto e rete neurale.
```

## Revisione dopo la generazione

- Sostituire eventuali immagini stock con diagrammi o board 6x7.
- Controllare che Gamma non presenti `neural` come difficolta piu forte
  (lo e `impossible`).
- Verificare che i modelli ricevano una matrice, non un'immagine della webcam.
- Verificare che `swap_perspective` e il mirror della colonna siano due
  trasformazioni diverse.
- Esportare in PowerPoint e controllare font, note e allineamenti.
