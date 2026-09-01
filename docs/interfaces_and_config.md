# Interfacce Pubbliche, Configurazione e Dipendenze

Questo modulo documenta tutte le interfacce disponibili per interagire con il sistema Pefforza (CLI/GUI), i parametri di configurazione configurabili e l'elenco delle librerie software necessarie.

---

## 1. API / CLI / Public Interface
Il sistema viene controllato principalmente mediante interfacce a riga di comando (CLI).

### Comandi CLI Principali

| Comando | Scopo | Argomenti Chiave | Implementazione |
|:---|:---|:---|:---|
| `python play_cli.py` | Gioca una partita in modalità testuale | `--difficulty` (easy, medium, hard, impossible, neural)<br>`--voice` (abilita TTS)<br>`--model` (percorso modello neurale) | [play_cli.py](../play_cli.py) |
| `python play_gui.py` | Gioca una partita con interfaccia Pygame | `--difficulty`<br>`--no-animate` (disabilita animazioni)<br>`--seed` (riproducibilità) | [play_gui.py](../play_gui.py) |
| `python play_physical.py` | Assistente AR su telecamera on-demand | `--ai-color` (red, yellow)<br>`--camera` (indice video device) | [play_physical.py](../play_physical.py) |
| `python main.py` | Assistente AR continuo in tempo reale | `--camera`<br>`--no-voice` (disabilita TTS) | [main.py](../main.py) |
| `python -m pefforza.vision.diagnose` | Strumento live di calibrazione e diagnostica visiva | `--camera`<br>`--flip` (specchia feed video) | [pefforza/vision/diagnose.py](../pefforza/vision/diagnose.py) |
| `python -m pefforza.agent.train` | Addestra una nuova policy PPO RL | `--timesteps` (step per ciclo)<br>`--iterations` (numero iterazioni) | [pefforza/agent/train.py](../pefforza/agent/train.py) |
| `python -m pefforza.agent.evaluate` | Valuta la win-rate di un modello in batch | `--opponent` (random, heuristic, minimax, self, model)<br>`--games` (numero partite) | [pefforza/agent/evaluate.py](../pefforza/agent/evaluate.py) |

---

## 2. Configuration and Environment
Le configurazioni di Pefforza possono essere definite sia tramite parametri CLI a runtime che mediante variabili d'ambiente.

### Tabella delle Configurazioni

| Impostazione | Dove si trova | Default | Obbligatorio | Descrizione |
|:---|:---|:---|:---|:---|
| `PEFFORZA_TTS_BACKEND` | Variabile d'ambiente | (Vuoto - usa pyttsx3) | No | Se impostata su `null`, forza l'uso di `NullBackend` disattivando il sintetizzatore vocale offline. |
| `ROWS` | [pefforza/constants.py](../pefforza/constants.py) | `6` | Sì | Numero di righe della scacchiera. Modificabile solo da codice. |
| `COLS` | [pefforza/constants.py](../pefforza/constants.py) | `7` | Sì | Numero di colonne della scacchiera. Modificabile solo da codice. |
| `WIN_LENGTH` | [pefforza/constants.py](../pefforza/constants.py) | `4` | Sì | Numero di pedine consecutive necessarie per vincere. |
| `DEFAULT_MODEL_PATH` | [pefforza/constants.py](../pefforza/constants.py) | `pefforza/agent/models/notebook_model.zip` | Sì | Percorso relativo del modello neurale precaricato. |

---

## 3. Dependencies and External Services
Il progetto riduce al minimo l'uso di API cloud esterne per garantire il pieno funzionamento in locale senza connessione internet.

### Tabella delle Dipendenze Principali

| Dependency | Usage | Files | Importance | Conseguenza se rimossa |
|:---|:---|:---|:---|:---|
| `opencv-python` | Elaborazione video, calibrazione prospettica, overlays e classificazione colore HSV | `vision/board_detector.py`, `diagnose.py`, `play_physical.py`, `main.py` | Critica | Nessun supporto per telecamera fisica o realtà aumentata. Rimangono utilizzabili solo CLI e GUI Pygame. |
| `stable-baselines3` | Fornisce la classe `PPO` per inferenza e addestramento RL | `agent/difficulty.py`, `train.py`, `evaluate.py`, `main.py` | Alta | La difficoltà `neural` e i comandi di addestramento sollevano eccezioni; la CLI/GUI ripiega sull'agente euristico. |
| `gymnasium` | Fornisce l'interfaccia standard per ambienti a rinforzo | `envs/connect4_env.py`, `agent/train.py` | Alta | Impossibile addestrare l'agente tramite Reinforcement Learning. |
| `pygame` | Visualizzazione grafica, rendering eventi input e animazioni delle pedine | `play_gui.py` | Alta | L'interfaccia grafica Pygame non si avvia. Rimane attiva la modalità CLI. |
| `pyttsx3` | Motore di sintesi vocale offline per la narrazione delle partite | `interaction/voice.py` | Media | Nessun feedback sonoro o vocale durante il gioco (fall-soft garantito). |
| `numpy` | Calcolo matematico efficiente, mascheramento delle matrici di gioco | Utilizzato ovunque in tutto il package | Critica | Il sistema cessa di funzionare completamente; tutte le matrici di gioco si basano su array NumPy. |
