# Prestazioni, Limiti, Miglioramenti Futuri e Glossario

> 🇬🇧 [English version](../limitations_and_future.md)

Questo modulo riassume il lavoro sulle prestazioni di Pefforza, i limiti
attuali, la roadmap di miglioramento e un glossario dei termini del progetto.

---

## 1. Prestazioni e scalabilità

1. **Bitboard**: `BitPosition` memorizza una posizione come due interi (sette
   bit per colonna, uno sentinella). Vittorie, minacce e mosse legali sono
   pochi shift e maschere invece di scansioni di array, e questo rende il
   livello `hard` un ordine di grandezza più veloce della baseline a matrice
   a cui è vincolato.
2. **Lookup dell'opening book**: il book è un array ordinato di 533k chiavi
   canoniche (950 KiB compressi, caricato una volta); un lookup è una
   ricerca binaria, quindi i primi 17 ply ricevono risposta in molto meno di
   un millisecondo.
3. **Dimostrazioni alternate alla radice**: oltre il book, `solve_root` dà a
   ogni mossa radice non ancora risolta un budget di nodi che cresce
   geometricamente, così una dimostrazione di vittoria economica non resta
   bloccata dietro confutazioni costose. Sulle linee di gioco dell'oracolo
   la dimostrazione più lenta è scesa da 9,5 s a meno di 3 s.
4. **Transposition table canonica per simmetria**: una posizione e la sua
   speculare condividono un'unica voce di una tabella a dimensione fissa,
   compattata in array di interi paralleli.
5. **Superficie della scacchiera in cache in Pygame**: la scacchiera statica
   viene pre-renderizzata una volta per mossa; le animazioni di caduta
   copiano solo quella superficie più un cerchio per frame, eliminando lo
   sfarfallio.
6. **Ordinamento delle mosse dal centro**: le ricerche provano
   `[3, 2, 4, 1, 5, 0, 6]` (poi per numero di "spot" vincenti), così
   l'alpha-beta taglia presto i rami peggiori.

---

## 2. Limiti noti

1. **Posizioni fuori dal book**: il book copre ogni posizione che l'IA
   `impossible` può raggiungere *quando gioca dalla prima mossa*. Se entra in
   una partita già iniziata (ad esempio su una scacchiera fisica dove
   qualcun altro ha giocato l'apertura), le posizioni poco profonde possono
   non essere dimostrabili entro il budget e la mossa è il ripiego
   tatticamente sicuro: 97-98% di mosse che conservano il valore sulle
   posizioni fuori book dell'oracolo, invece del 100%.
2. **Vittoria più rapida oltre il book**: oltre il ply 17 il solver è
   "debole" (vittoria / pareggio / sconfitta), quindi una partita vinta resta
   sempre vinta ma non sempre per la via più rapida (circa il 73% di mosse
   esattamente ottimali in quella fase).
3. **La visione è testata su scene disegnate**: localizzazione e adattamento
   alla luce sono verificati su scacchiere sintetiche con prospettiva,
   disordine e luce fioca, ma il repository non contiene ancora foto reali
   della webcam (la suite le testa automaticamente quando vengono aggiunte
   in `tests/fixtures/vision/`).
4. **Ipotesi della localizzazione**: la calibrazione automatica si aspetta
   una cornice blu con almeno l'~85% dei fori visibili; occlusioni pesanti o
   un colore insolito della scacchiera richiedono la calibrazione manuale a
   quattro click.
5. **Movimenti di camera o scacchiera**: la matrice prospettica è fissa dopo
   la calibrazione; se la camera o la scacchiera si spostano, riavviare
   l'assistente per ricalibrare.
6. **Il livello neurale è un'imitazione**: la CNN è distillata dalle
   etichette esatte del solver ed è molto più forte della vecchia policy
   PPO, ma non è perfetta (vedi il README per il suo punteggio sull'oracolo)
   e di proposito non è avvolta dalla safety net, così mostra ciò che la
   rete ha davvero imparato.
7. **Avvio del modello**: importare Stable-Baselines3/PyTorch per il livello
   `neural` aggiunge circa 1-2 s all'avvio.

---

## 3. Roadmap

| Priorità | Miglioramento | Perché | File | Rischio |
|:---|:---|:---|:---|:---|
| **P1** | **Foto reali della webcam nei test** | Verificare la visione su luce, riflessi e scacchiere reali, non solo su scene disegnate. | `tests/fixtures/vision/` | Basso |
| **P1** | **Rilocalizzazione continua** | Rilevare i movimenti di camera/scacchiera e rieseguire `locate_board` automaticamente invece di riavviare. | `board_detector.py`, `play_physical.py` | Medio |
| **P2** | **Copertura fuori book** | Aggiungere al book tutte le posizioni fino a ~ply 8, così anche entrare in una partita già iniziata è perfetto. | `scripts/build_opening_book.py`, `book.py` | Basso |
| **P2** | **Soluzione forte oltre il book** | Preferire la vittoria più rapida quando rientra nel budget. | `search/perfect.py` | Medio |
| **P3** | **Gioco perfetto nel browser** | Portare lookup del book e solver nella demo del sito (TypeScript/WASM). | `website/` | Medio |
| **P3** | **Export ONNX** | Eseguire il livello neurale senza PyTorch. | nuovo modulo di export | Medio |

Completati rispetto alla roadmap precedente: calibrazione automatica dei
colori (adattamento alla luce), rilevamento automatico degli angoli della
scacchiera, addestramento neurale guidato dal solver e apertura perfetta.

---

## 4. Glossario

| Termine | Significato | Dove |
|:---|:---|:---|
| **Bitboard** | Posizione codificata come interi, un bit per cella, così le regole diventano operazioni sui bit. | `agent/search/bitboard.py` |
| **Opening book** | Tabella precalcolata di mosse perfette per le posizioni iniziali, generata offline da un solver nativo. | `agent/search/book.py` |
| **Oracolo** | Posizioni con il punteggio esatto di ogni colonna, usate per valutare gli agenti mossa per mossa. | `agent/oracle.py` |
| **Mossa che conserva il valore** | Mossa che mantiene l'esito teorico (una partita vinta resta vinta, una patta resta patta). | `agent/oracle.py` |
| **Mossa esattamente ottimale** | Mossa che conserva il valore e vince nel modo più rapido o perde nel modo più lento. | `agent/oracle.py` |
| **Soluzione debole / forte** | Calcolare solo vittoria/pareggio/sconfitta oppure la distanza esatta dalla fine. | `agent/search/perfect.py` |
| **Transposition table** | Cache dei risultati di ricerca indicizzata per posizione, condivisa tra ordini di mosse diversi. | `agent/search/perfect.py` |
| **Negamax** | Minimax per giochi a somma zero basato su max(a, b) = -min(-a, -b). | `agent/minimax.py`, `agent/search/` |
| **Tactical safety net** | Protezione deterministica a 1 ply: prendi una vittoria immediata, altrimenti blocca una minaccia immediata. | `agent/minimax.py` |
| **Distillazione** | Addestrare una rete a imitare un insegnante più forte (qui le etichette del solver esatto). | `agent/train.py` |
| **PPO** | Proximal Policy Optimization, l'algoritmo di reinforcement learning usato per il fine-tuning. | `agent/train.py` |
| **Gymnasium** | Successore mantenuto di OpenAI Gym, l'API standard per ambienti RL. | `envs/connect4_env.py` |
| **Warp prospettico / omografia** | Trasformazione 3 x 3 che porta la vista inclinata della camera a un rettangolo frontale. | `vision/board_detector.py` |
| **Reticolo dei fori** | Griglia 6 x 7 dei centri dei fori usata per localizzare la scacchiera automaticamente. | `vision/board_detector.py` |
