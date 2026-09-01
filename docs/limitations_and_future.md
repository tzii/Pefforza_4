# Prestazioni, Limiti, Miglioramenti Futuri e Glossario

Questo modulo riassume le considerazioni prestazionali riscontrate nel codice di Pefforza, i limiti strutturali attuali e la roadmap di miglioramento, concludendo con un glossario dei termini specifici utilizzati.

---

## 1. Performance and Scalability

### Ottimizzazioni Critiche implementate nel Codice:
1.  **Struttura Dati In-Place nel Minimax**: Nel modulo [minimax.py](../pefforza/agent/minimax.py), l'operazione di posizionamento della pedina simula il posizionamento modificando la matrice originale (`board[row, col] = player`), scende ricorsivamente e rimuove la pedina al ritorno (`board[row, col] = 0`). Questo evita la copia di $6 \times 7$ byte per ciascuno delle migliaia di nodi scansionati al secondo, riducendo drasticamente l'impatto sul Garbage Collector di Python.
2.  **Cashing della scacchiera in Pygame**: Per mitigare i rallentamenti visivi e lo sfarfallio dello schermo (flickering), l'interfaccia grafica Pygame pre-renderizza la scacchiera statica in una superficie off-screen (`_render_board_surface`) ogni volta che una pedina si stabilizza. Durante le animazioni di caduta, Pygame esegue solo il blit bidimensionale della superficie salvata sovrapponendo il cerchio della pedina in caduta a coordinate calcolate. Questo riduce la complessità computazionale del disegno da $O(R \times C)$ a $O(1)$ per frame.
3.  **Ordinamento statico delle mosse**: Il Minimax scansiona le colonne partendo dalla colonna centrale ed allargandosi verso i lati (`[3, 2, 4, 1, 5, 0, 6]`). Essendo il centro la zona più contesa del Forza 4, valutare prima queste mosse permette al potatore alfa-beta di tagliare i rami peggiori molto prima, riducendo i nodi analizzati di oltre il $70\%$.

---

## 2. Known Limitations
1.  **Fattori di illuminazione fissi (HSV statici)**: Le soglie HSV di riconoscimento dei colori sono codificate staticamente in [board_detector.py](../pefforza/vision/board_detector.py) (`_DEFAULT_RED_RANGES`, `_DEFAULT_YELLOW_RANGE`). Se la stanza in cui si gioca è troppo buia o presenta forti luci al neon azzurre, le pedine potrebbero non venire riconosciute correttamente.
2.  **Calibrazione prospettica manuale rigida**: Se la webcam o il tavolo da gioco subiscono vibrazioni o spostamenti anche minimi dopo la calibrazione, la matrice di omografia prospettica cessa di corrispondere e richiede una ricalibrazione completa da parte dell'utente.
3.  **Latenza dell'inizializzazione del modello PPO**: Il caricamento della libreria `stable_baselines3` all'avvio introduce un ritardo di circa 1-2 secondi dovuto all'importazione pesante del framework PyTorch.
4.  **Addestramento su avversari puramente casuali**: La policy neurale pre-addestrata in `notebook_model.zip` è allenata all'interno del wrapper `SinglePlayerWrapper` che compie mosse casuali per l'avversario. Di conseguenza, pur avendo una buona padronanza delle regole base, il modello neurale risulta meno competitivo rispetto all'agente Negamax `impossible`.

---

## 3. Suggested Improvements

| Priorità | Miglioramento | Perché è importante | File Coinvolti | Rischio |
|:---|:---|:---|:---|:---|
| **P0** | **Calibrazione Automatica dei Colori** | Permette al sistema di campionare automaticamente i valori HSV di Rosso e Giallo esaminando le prime pedine giocate, adattandosi a qualsiasi tipo di illuminazione ambientale. | [board_detector.py](../pefforza/vision/board_detector.py) | Basso |
| **P1** | **Rilevamento Automatico dei Contorni (ArUco / Canny)** | Elimina l'obbligo dei 4 click manuali rilevando i bordi esterni della scacchiera mediante marker ArUco incollati sugli angoli o tracciando i contorni del rettangolo blu del Forza 4. | [board_detector.py](../pefforza/vision/board_detector.py) | Medio |
| **P2** | **Addestramento tramite Self-Play Competitivo** | Permette di addestrare un modello PPO più forte facendolo giocare contro se stesso o contro versioni storiche della sua stessa rete (invece che contro mosse puramente casuali). | [train.py](../pefforza/agent/train.py) | Medio |
| **P3** | **Portabilità Web (ONNX + OpenCV.js)** | Convertire il modello PyTorch salvato in formato ONNX ed esportare la logica in JavaScript, consentendo agli utenti di eseguire l'assistente AR direttamente dal browser del telefono senza installare Python localmente. | Nuovo modulo (esportazione) | Alto |

---

## 4. Glossary

| Termine | Significato | Dove Compare |
|:---|:---|:---|
| **Warping Prospettico** | Trasformazione geometrica che corregge la distorsione di una foto inclinata proiettandola come se fosse stata scattata perpendicolarmente al piano. | `vision/board_detector.py` |
| **Negamax** | Variante semplificata dell'algoritmo Minimax per giochi a somma zero basata sull'uguaglianza $\max(a, b) = -\min(-a, -b)$. | `agent/minimax.py` |
| **Iterative Deepening** | Tecnica di ricerca che esplora l'albero delle mosse a profondità crescenti (1, 2, 3...) arrestandosi non appena scade il limite di tempo e restituendo la migliore mossa calcolata. | `agent/minimax.py` |
| **Tactical Safety Net** | Meccanismo di sicurezza deterministico a un solo livello (1-ply) che forza il blocco di minacce di sconfitta o prende vittorie immediate. | `agent/minimax.py` |
| **PPO** | Proximal Policy Optimization. Algoritmo di Reinforcement Learning per addestrare reti neurali ad associare stati ad azioni ottimali. | `agent/train.py` |
| **Gymnasium** | Fork moderno e standardizzato della libreria OpenAI Gym per la modellazione di ambienti di apprendimento per rinforzo. | `envs/connect4_env.py` |
| **Warp Matrix** | Matrice omografica di dimensione $3 \times 3$ usata da OpenCV per mappare i pixel dell'inquadratura inclinata a quella rettificata. | `vision/board_detector.py` |
