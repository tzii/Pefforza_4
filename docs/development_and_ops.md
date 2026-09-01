# Flusso di Sviluppo, Esempi ed Estensioni

Questo documento è una guida pratica destinata agli sviluppatori che desiderano installare il progetto localmente, comprendere l'esecuzione passo dopo passo e aggiungere nuove funzionalità al sistema Pefforza.

---

## 1. Build, Run and Development Workflow

### Prerequisiti
*   Python 3.10, 3.11, 3.12, o 3.13.
*   Un compilatore C/C++ non è strettamente necessario (PyTorch e OpenCV sono distribuiti tramite ruote precompilate su PyPI).

### Configurazione Ambiente

```bash
# 1. Clonare il repository e creare il virtual environment
python -m venv .venv

# 2. Attivare il virtual environment
# Su Windows (PowerShell / CMD)
.venv\Scripts\activate
# Su macOS / Linux
source .venv/bin/activate

# 3. Installazione in modalità editabile con strumenti di sviluppo
pip install -e ".[dev]"
```

### Comandi di Esecuzione e Test

```bash
# Eseguire i test di unità con copertura
python -m pytest --cov=pefforza

# Controllare il codice con il linter ruff
python -m ruff check .

# Formattare il codice secondo le linee guida
python -m ruff format --check .

# Avviare la modalità grafica Pygame con difficoltà Impossible
python play_gui.py --difficulty impossible

# Avviare la diagnostica della webcam
python -m pefforza.vision.diagnose --camera 0
```

---

## 2. End-to-End Example
Seguiamo il tracciamento completo di una raccomandazione mossa in modalità realtà aumentata con [play_physical.py](../play_physical.py) (l'AI gioca come Giallo, l'Umano come Rosso):

1.  **Input Iniziale**: L'utente preme la barra spaziatrice `[SPACE]` davanti al feed video.
2.  **Lettura Webcam**: Il modulo `play_physical.py` acquisisce il frame corrente `frame` a risoluzione nativa (es. $1280 \times 720$). Specchia l'immagine per comodità visiva dell'utente (`cv2.flip(frame, 1)`).
3.  **Warping**: `BoardDetector.process_frame` prende il frame, applica la matrice prospettica ricavata in fase di calibrazione e genera un'immagine raddrizzata di dimensioni $700 \times 600$ pixel.
4.  **Classificazione Visiva**: `classify_board_image` esamina ogni singola cella. Trova pedine rosse nelle colonne 2, 3 e 4 sulla riga inferiore. Trova pedine gialle nelle colonne 1 e 5. Produce la griglia visiva:
    ```
    [[0,0,0,0,0,0,0],
     [0,0,0,0,0,0,0],
     [0,0,0,0,0,0,0],
     [0,0,0,0,0,0,0],
     [0,0,0,0,0,0,0],
     [0,2,1,1,1,2,0]]
    ```
5.  **Adattamento Prospettico**: L'IA gioca come Giallo (ID visivo = 2). La griglia viene convertita tramite `swap_perspective` in modo che l'agente neurale veda le pedine Gialle come `1` (Self) e Rosse come `2` (Opponent).
6.  **Valutazione Decisionale**: La griglia normalizzata viene passata all'agente neurale (o minimax). Il motore rileva che l'avversario (Rosso) ha tre pedine in fila (colonne 2, 3, 4) e che la colonna 1 e la colonna 5 sono le uniche difese legali per prevenire la vittoria immediata dell'avversario. Il sistema seleziona la colonna 5 (0-indexed).
7.  **Inversione specchio**: OpenCV visualizza l'immagine specchiata. L'azione 5 viene convertita in coordinate speculari: `mirrored_col = (7 - 1) - 5 = 1` (seconda colonna).
8.  **Output Finale**:
    *   **Visivo**: Viene disegnata una freccia rosa che punta verso la colonna 2 sul monitor dell'utente.
    *   **Audio**: Il sintetizzatore vocale offline annuncia: *"Putting in column 2. Too easy."*

---

## 3. Extension Guide

### Aggiunta di un nuovo backend vocale (es. Piper o Cloud TTS API)
Per integrare un nuovo sintetizzatore vocale:
1.  Aprire il file [pefforza/interaction/voice.py](../pefforza/interaction/voice.py).
2.  Creare una nuova classe che eredita dall'interfaccia `TTSBackend`:
    ```python
    class CloudTTSBackend(TTSBackend):
        def __init__(self, api_key: str) -> None:
            self.api_key = api_key
            # Inizializzazione SDK client
        
        def speak(self, text: str) -> None:
            # Chiamata API sincrona o streaming audio locale
            pass
            
        def close(self) -> None:
            # Rilascio connessioni
            pass
    ```
3.  Modificare il metodo `VoiceEngine._resolve_backend` per istanziare la nuova classe in base a una variabile d'ambiente o di configurazione:
    ```python
    if os.environ.get("PEFFORZA_TTS_BACKEND") == "cloud":
        return CloudTTSBackend(api_key=os.environ["TTS_API_KEY"])
    ```

### Aggiunta di un nuovo livello di difficoltà decisionale
Per integrare un nuovo algoritmo di IA (es. Monte Carlo Tree Search - MCTS):
1.  Sviluppare l'algoritmo all'interno di un nuovo file `pefforza/agent/mcts.py` definendo un callable con firma `Agent = Callable[[Board, int, list[int]], int]`.
2.  Aprire il file [pefforza/agent/difficulty.py](../pefforza/agent/difficulty.py).
3.  Registrare la nuova difficoltà all'interno del dizionario `DIFFICULTIES`:
    ```python
    "mcts": Difficulty(
        "mcts",
        "Monte Carlo Tree Search con 1000 simulazioni per turno.",
        lambda seed=None: mcts_agent(simulations=1000, seed=seed),
    )
    ```
4.  La nuova difficoltà sarà automaticamente disponibile sia nei menu CLI che in quelli GUI Pygame.
