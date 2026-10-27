# Strategia di Test, Gestione degli Errori e Affidabilità

> 🇬🇧 [English version](../testing_and_reliability.md)

Come vengono testate le funzionalità di Pefforza, come vengono contenuti gli
errori a runtime e le considerazioni di affidabilità e sicurezza del design.

---

## 1. Strategia di test

La suite usa `pytest` con la copertura (`pytest-cov`). Ogni test è
**headless**: non servono webcam, dispositivi audio, display o modelli
addestrati. Pygame gira con il driver SDL "dummy", l'input umano è simulato
e la camera è sostituita da finti oggetti o da scacchiere disegnate nel
codice.

```bash
python -m pytest --cov=pefforza
```

La CI esegue la suite insieme a ruff e mypy su Python 3.10-3.13 (Ubuntu) e
su Windows e macOS, e impone una soglia minima di copertura (`fail_under` in
`pyproject.toml`, un "cricchetto" che può solo salire). Un job separato
costruisce la wheel, la installa in un venv pulito e verifica i console
script, il checkpoint incluso e l'opening book.

### File di test

| File di test | Area | Cosa verifica |
|:---|:---|:---|
| [test_rules.py](../../tests/test_rules.py) | Logica pura | Vittorie in ogni direzione, colonne piene, cambio di prospettiva. |
| [test_connect4_env.py](../../tests/test_connect4_env.py) | Ambiente Gymnasium | `step()`, penalità per mosse illegali, vittorie e pareggi. |
| [test_minimax.py](../../tests/test_minimax.py) | Baseline a matrice | Ricerca a profondità fissa, budget di tempo, iterative deepening. |
| [test_bitboard_search.py](../../tests/test_bitboard_search.py) | Motore `hard` | Test differenziali contro la baseline (stesso punteggio e mossa), con/senza TT, con specchiatura. |
| [test_perfect_solver.py](../../tests/test_perfect_solver.py), [test_exact_agent.py](../../tests/test_exact_agent.py) | Solver esatto | Punteggi esatti, potatura delle minacce, simmetria, garanzie di `solve_root`. |
| [test_opening_book.py](../../tests/test_opening_book.py) | Opening book | Formato, lookup specchiati, file corrotti, **chiusura** (seguendo il proprio book l'IA non ne esce mai prima del ply 17, qualunque cosa giochi l'avversario), integrazione nel livello. |
| [test_oracle.py](../../tests/test_oracle.py) | Oracolo esatto | Insieme ben formato, **ogni mossa del book esattamente ottimale** contro punteggi indipendenti, `impossible` perfetto sul finale, CLI. |
| [test_blocks_threats.py](../../tests/test_blocks_threats.py) | Sicurezza tattica | `medium`, `hard` e `impossible` bloccano sempre un tris o prendono una vittoria immediata. |
| [test_difficulty.py](../../tests/test_difficulty.py), [test_evaluate.py](../../tests/test_evaluate.py), [test_full_game_sim.py](../../tests/test_full_game_sim.py) | Livelli e harness | Registro, ripieghi, partite simulate complete. |
| [test_train.py](../../tests/test_train.py) | Pipeline neurale | Forme della CNN, target del teacher, la distillazione impara, salvataggio/caricamento, wrapper a due colori, PPO di prova. |
| [test_board_detector.py](../../tests/test_board_detector.py) | Classificazione | Scacchiere sintetiche a varie risoluzioni, confidenze. |
| [test_vision_auto.py](../../tests/test_vision_auto.py) | Localizzazione e luce | Scacchiere disegnate in scene disordinate e in prospettiva: angoli trovati entro il 15% di una cella, griglia letta esattamente; scacchiere parziali scartate; la luce fioca rompe le soglie di default e l'adattamento le recupera; le foto reali etichettate in `tests/fixtures/vision/` vengono testate automaticamente. |
| [test_board_validation.py](../../tests/test_board_validation.py) | Validazione | Gravità, conteggi, esiti, transizioni, nuova partita. |
| [test_play_physical.py](../../tests/test_play_physical.py) | Assistente AR | Percorso decisionale, filtro di stabilità, ciclo principale con camera finta. |
| [test_game_loops.py](../../tests/test_game_loops.py) | CLI e GUI | Partite complete end to end, diagnostica del watchdog. |
| [test_cli.py](../../tests/test_cli.py), [test_diagnose.py](../../tests/test_diagnose.py), [test_voice.py](../../tests/test_voice.py) | Entrypoint, diagnostica, voce | Smoke test di `--help`, ciclo diagnostico, ciclo di vita della coda vocale. |

### Misurare il gioco perfetto

Battere avversari più deboli dice poco su un giocatore quasi perfetto, quindi
il livello `impossible` viene valutato contro un **oracolo esatto**: 729
posizioni con il punteggio del solver nativo per ogni colonna
(`pefforza/agent/data/oracle_positions.json`). Per ogni posizione la mossa
dell'agente **conserva il valore** se mantiene l'esito teorico della partita
ed è **esattamente ottimale** se ha anche il punteggio migliore (vittoria più
rapida / sconfitta più lenta):

```bash
python -m pefforza.agent.evaluate --oracle --difficulty impossible
```

Il README riporta i numeri aggiornati per ogni livello.

---

## 2. Gestione degli errori e casi limite

1. **Audio fail-soft**: l'inizializzazione di `pyttsx3` è protetta; senza
   driver audio (comune su Linux headless o Docker) viene registrato un
   warning e la voce si disattiva. Un errore di riproduzione nel worker
   disattiva i tentativi successivi senza raggiungere il thread di gioco.
2. **Validazione dell'input**: CLI e GUI controllano ogni mossa umana prima
   che arrivi a `Connect4Env` (che terminerebbe l'episodio con una penalità)
   e chiedono di ripetere.
3. **Letture della camera non affidabili**: `BoardStateValidator` scarta le
   letture che violano gravità, ordine dei turni, coerenza dell'esito o
   storia, quindi una mano sulla scacchiera non diventa mai una posizione;
   `--watch` richiede inoltre che la lettura resti stabile per più frame.
4. **Adattamento auto-verificato**: le nuove soglie di colore vengono
   adottate solo se riproducono esattamente la lettura validata.
5. **Sanificazione delle mosse dell'IA**: un agente che restituisce una
   colonna illegale viene corretto con una legale; il livello neurale
   esclude già le colonne piene dalla propria policy.
6. **Ripieghi**: un checkpoint `neural` mancante o illeggibile (o
   `stable-baselines3` assente) ripiega sull'euristica; un opening book
   mancante o corrotto registra un warning e il solver esatto gioca
   l'apertura con il suo ripiego tatticamente sicuro; una localizzazione non
   sicura restituisce `None` e l'utente clicca gli angoli.

---

## 3. Sicurezza, privacy e affidabilità

* **Privacy**: il video è elaborato in memoria, in locale. Nessun frame
  viene caricato online o salvato su disco, tranne lo snapshot
  `vision_debug.png` che l'utente salva esplicitamente con `s` nello
  strumento di diagnostica.
* **Caricamento dei modelli**: i checkpoint Stable-Baselines3 sono file zip
  che possono contenere oggetti serializzati con pickle; caricare solo
  checkpoint fidati (quello incluso è prodotto da `scripts/` +
  `pefforza.agent.train` di questo repository). L'opening book è un semplice
  file di array compresso, validato al caricamento.
* **Prevenzione dei crash**: voce e rendering girano in contesti isolati; i
  blocchi `finally` rilasciano camera, finestre e Pygame su ogni percorso
  d'uscita.
* **Supply chain**: la CI fissa le action di terze parti per SHA del commit e
  gira con permessi di sola lettura; le release vengono pubblicate con
  PyPI Trusted Publishing, senza token salvati.
