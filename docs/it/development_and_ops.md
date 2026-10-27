# Flusso di Sviluppo, Esempi ed Estensioni

> 🇬🇧 [English version](../development_and_ops.md)

Guida pratica per chi vuole installare Pefforza in locale, seguire una mossa
dall'inizio alla fine ed estendere il sistema.

---

## 1. Build, esecuzione e sviluppo

### Prerequisiti

* Python 3.10, 3.11, 3.12 o 3.13.
* Non serve un compilatore C/C++: PyTorch e OpenCV sono distribuiti come
  wheel precompilate. (Per rigenerare i dati inclusi serve una build del
  solver nativo - vedi
  [CONTRIBUTING.md](../../CONTRIBUTING.md#regenerating-bundled-data).)

### Configurazione dell'ambiente

```bash
python -m venv .venv
# Windows (PowerShell / CMD)
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

pip install -e ".[dev]"
```

### Esecuzione e test

```bash
# Controlli di qualità (la CI esegue gli stessi)
python -m ruff check .
python -m ruff format --check .
python -m mypy
python -m pytest --cov=pefforza

# Giocare
pefforza-gui --difficulty impossible
pefforza-physical --watch --voice

# Valutare un livello con l'oracolo esatto
python -m pefforza.agent.evaluate --oracle --difficulty impossible

# Diagnostica della webcam
python -m pefforza.vision.diagnose --camera 0
```

---

## 2. Esempio end-to-end

Una raccomandazione dell'assistente AR su richiesta
(`pefforza-physical --ai-color yellow --difficulty impossible`; l'IA gioca il
giallo, l'umano il rosso):

1. **Calibrazione**: la scacchiera viene evidenziata automaticamente dal
   reticolo dei suoi fori; l'utente preme INVIO.
2. **Input**: dopo che la mossa umana è atterrata, l'utente preme SPAZIO.
3. **Lettura della webcam**: `play_physical` acquisisce il frame (es.
   1280 x 720) e lo specchia (`cv2.flip(frame, 1)`) così lo schermo si
   comporta come uno specchio.
4. **Warping**: `BoardDetector.process_frame` applica l'omografia della
   calibrazione e produce un'immagine raddrizzata di 700 x 600.
5. **Classificazione**: `classify_board_image` legge ogni cella con il
   profilo colore corrente (eventualmente adattato). In coordinate dello
   schermo trova pedine rosse nelle colonne 2, 3 e 4 della riga in basso e
   gialle nella colonna 1 e sopra la colonna 3:
   ```
   [[0,0,0,0,0,0,0],
    [0,0,0,0,0,0,0],
    [0,0,0,0,0,0,0],
    [0,0,0,0,0,0,0],
    [0,0,0,2,0,0,0],
    [0,2,1,1,1,0,0]]
   ```
6. **Validazione**: la gravità è rispettata, il rosso ha 3 pedine e il giallo
   2 (muove il giallo) e la lettura segue legalmente l'ultimo stato
   accettato: viene accettata e le soglie di colore vengono riadattate.
7. **Prospettiva**: l'IA gioca il giallo (id visivo 2), quindi
   `swap_perspective` trasforma il giallo in `1` (self) e il rosso in `2`
   (avversario).
8. **Decisione**: il rosso minaccia di completare la riga in basso nella
   colonna 5 dello schermo (la colonna 1 è già bloccata dal giallo). La
   tactical safety net vede la minaccia immediata e restituisce la colonna
   5 - la stessa mossa del solver esatto, perché ogni altra mossa perde
   subito.
9. **Traduzione dello specchio**: la freccia viene disegnata sulla colonna 5
   del feed specchiato; per l'umano la raccomandazione viene tradotta con
   `physical_col`: `(7 - 1) - 5 = 1`, cioè la colonna fisica **2**.
10. **Output**: una freccia magenta indica la colonna sullo schermo, la
    console stampa `AI (YELLOW, impossible) recommends physical column 2` e,
    con `--voice`, la sintesi vocale dice *"Putting in column 2"*.

---

## 3. Guida alle estensioni

### Un nuovo backend vocale (es. Piper o un TTS cloud)

1. Aprire [pefforza/interaction/voice.py](../../pefforza/interaction/voice.py).
2. Creare una sottoclasse di `TTSBackend`:
   ```python
   class CloudTTSBackend(TTSBackend):
       def __init__(self, api_key: str) -> None:
           self.api_key = api_key  # creare qui il client SDK

       def speak(self, text: str) -> None: ...  # chiamata API sincrona o streaming audio locale

       def close(self) -> None: ...  # rilascio delle connessioni
   ```
3. Selezionarla in `VoiceEngine._resolve_backend`, ad esempio da una
   variabile d'ambiente:
   ```python
   if os.environ.get("PEFFORZA_TTS_BACKEND") == "cloud":
       return CloudTTSBackend(api_key=os.environ["TTS_API_KEY"])
   ```
   Restare fail-soft: un'eccezione deve disattivare la voce, mai far cadere
   il gioco.

### Un nuovo livello di difficoltà (es. MCTS)

1. Implementare l'agente in `pefforza/agent/mcts.py` come callable
   `Agent = Callable[[Board, int, list[int]], int]`.
2. Registrarlo in `DIFFICULTIES` in
   [pefforza/agent/difficulty.py](../../pefforza/agent/difficulty.py):
   ```python
   "mcts": Difficulty(
       "mcts",
       "Monte Carlo Tree Search, 1000 simulazioni per mossa.",
       lambda seed=None: tactical_safety_net(mcts_agent(simulations=1000, seed=seed)),
   )
   ```
3. Il livello è subito disponibile in CLI, GUI e assistente AR, e si può
   valutare con `python -m pefforza.agent.evaluate --oracle --difficulty
   mcts`.

### Un checkpoint neurale migliore

1. Generare i dati teacher con il solver nativo
   (`scripts/build_teacher_set.py`) o riusare un `.npz` esistente.
2. Distillare: `python -m pefforza.agent.train --teacher teacher.npz
   --epochs 12 --out candidato.zip`; opzionalmente fare fine-tuning con PPO
   tramite `--init`.
3. Confrontarlo con l'oracolo e in partite dirette prima di sostituire
   `pefforza/agent/models/notebook_model.zip`:
   ```bash
   python -m pefforza.agent.evaluate --oracle --model candidato.zip
   python -m pefforza.agent.evaluate --model candidato.zip --opponent model \
       --opponent-model pefforza/agent/models/notebook_model.zip --games 200
   ```

### Foto reali della webcam per i test di regressione

Salvare un frame come `tests/fixtures/vision/<nome>.png` con un
`<nome>.json` che contiene `{"grid": [[...6 righe da 7...]]}` (e
opzionalmente `"corners"`); la suite verificherà su di esso localizzazione
automatica e classificazione.
