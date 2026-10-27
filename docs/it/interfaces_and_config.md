# Interfacce Pubbliche, Configurazione e Dipendenze

> 🇬🇧 [English version](../interfaces_and_config.md)

Questo modulo documenta tutti i modi di usare Pefforza (CLI/GUI/AR), la
configurazione disponibile e le dipendenze software.

---

## 1. Comandi

Dopo `pip install -e .` (o l'installazione di una wheel) i console script
sono nel `PATH`; gli script nella root funzionano da un checkout dei sorgenti.

| Comando | Scopo | Argomenti principali | Implementazione |
|:---|:---|:---|:---|
| `pefforza-cli` / `python play_cli.py` | Partita testuale nel terminale | `--difficulty` (easy, medium, hard, impossible, neural), `--voice`, `--model`, `--seed` | [play_cli.py](../../pefforza/cli/play_cli.py) |
| `pefforza-gui` / `python play_gui.py` | Partita con Pygame | `--difficulty`, `--no-animate`, `--model`, `--seed` | [play_gui.py](../../pefforza/cli/play_gui.py) |
| `pefforza-physical` / `python play_physical.py` | Assistente AR per scacchiera fisica | `--difficulty`, `--ai-color` (red, yellow), `--camera`, `--watch`, `--stable-frames`, `--voice`/`--no-voice`, `--model`, `--seed` | [play_physical.py](../../pefforza/cli/play_physical.py) |
| `python main.py` | Assistente AR continuo (= `pefforza-physical --watch --voice --ai-color yellow`) | qualsiasi argomento di `pefforza-physical`, es. `--no-voice` | [main.py](../../main.py) |
| `python -m pefforza.vision.diagnose` | Diagnostica visiva live | `--camera`, `--flip` | [diagnose.py](../../pefforza/vision/diagnose.py) |
| `python -m pefforza.agent.evaluate` | Partite, confronto tra livelli, oracolo | `--difficulty`, `--model`, `--opponent` (random, heuristic, minimax, self, model), `--games`, `--oracle`, `--oracle-source` (all, line, random) | [evaluate.py](../../pefforza/agent/evaluate.py) |
| `python -m pefforza.agent.train` | Distillazione dal solver o training PPO | `--teacher`, `--epochs`, `--out`; PPO: `--timesteps`, `--iterations`, `--opponent` (random, heuristic, hard), `--init` | [train.py](../../pefforza/agent/train.py) |
| `python scripts/build_opening_book.py` | Rigenera l'opening book (solver nativo) | `--solver`, `--max-ply` | [script](../../scripts/build_opening_book.py) |
| `python scripts/build_oracle_set.py` | Rigenera l'insieme dell'oracolo | `--solver`, `--seed` | [script](../../scripts/build_oracle_set.py) |
| `python scripts/build_teacher_set.py` | Genera i dati di distillazione | `--solver`, `--games`, `--out` | [script](../../scripts/build_teacher_set.py) |
| `python scripts/benchmark_search.py` | Benchmark dei motori di ricerca | vedi `--help` | [script](../../scripts/benchmark_search.py) |

### Comandi dell'assistente fisico

| Tasto | Effetto |
|:---|:---|
| INVIO / `a` (calibrazione) | Conferma la scacchiera rilevata automaticamente |
| Click del mouse (calibrazione) | Imposta a mano i quattro angoli, in qualsiasi ordine |
| SPAZIO | Analizza la scacchiera corrente (modalità su richiesta) |
| `r` | Azzera il tracciamento (nuova storia) |
| `q` | Esci |

---

## 2. Configurazione e ambiente

| Impostazione | Dove | Default | Descrizione |
|:---|:---|:---|:---|
| `PEFFORZA_TTS_BACKEND` | Variabile d'ambiente | vuota (usa `pyttsx3`) | `null` forza il `NullBackend` silenzioso. |
| `SDL_VIDEODRIVER` | Variabile d'ambiente | default di piattaforma | `dummy` esegue Pygame senza finestra (usato dai test). |
| `ROWS`, `COLS`, `WIN_LENGTH` | [constants.py](../../pefforza/constants.py) | `6`, `7`, `4` | Geometria del tabellone; solo da codice. |
| `DEFAULT_MODEL_PATH` | [constants.py](../../pefforza/constants.py) | `pefforza/agent/models/notebook_model.zip` | Checkpoint neurale incluso. |
| `IMPOSSIBLE_TIME_BUDGET` | [difficulty.py](../../pefforza/agent/difficulty.py) | `3.0` s | Budget del solver oltre l'opening book. |
| `HARD_BITBOARD_DEPTH` | [difficulty.py](../../pefforza/agent/difficulty.py) | `8` | Profondità di ricerca del livello `hard`. |
| `DEFAULT_BOOK_PATH` | [search/book.py](../../pefforza/agent/search/book.py) | `pefforza/agent/data/opening_book.xz` | Book mancante o corrotto: warning e ripiego sulla ricerca. |
| `ColorProfile` | [board_detector.py](../../pefforza/vision/board_detector.py) | bande HSV per luce da interni | Soglie per detector; adattate durante il gioco. |

---

## 3. Dipendenze

Tutto gira in locale; nessun servizio cloud.

| Dipendenza | Uso | Importanza | Se rimossa |
|:---|:---|:---|:---|
| `numpy` | Tutti gli array di gioco, lookup del book | Critica | Non funziona nulla. |
| `opencv-python` | Camera, localizzazione, warp, classificazione HSV, overlay | Critica per l'AR | Niente modalità fisica; CLI e GUI funzionano. |
| `stable-baselines3` (+ PyTorch) | Inferenza e addestramento `PPO` del livello `neural` | Alta | `neural` ripiega sull'euristica; niente addestramento. |
| `gymnasium` | `Connect4Env` | Alta | Nessun ambiente per l'addestramento. |
| `pygame` | Rendering della GUI e animazioni | Alta | Niente GUI; la CLI funziona. |
| `pyttsx3` | Sintesi vocale offline | Media | Niente voce (fail-soft). |

Solo sviluppo: `pytest`, `pytest-cov`, `ruff`, `mypy`. La generazione offline
dei dati richiede inoltre il solver nativo di Pascal Pons (AGPL-3.0); vedi
[scripts/native_solver.py](../../scripts/native_solver.py).
