# Strategia di Test, Gestione Errori e Robustezza

Questo documento illustra come vengono testate le funzionalità di Pefforza, le strategie di gestione degli errori per prevenire crash a runtime e le considerazioni di affidabilità e sicurezza del software.

---

## 1. Testing Strategy
Pefforza adotta una strategia di testing basata su `pytest` con tracciamento della copertura del codice (`pytest-cov`). I test sono progettati in modalità *headless*, escludendo la necessità di videocamere reali o schede audio connesse in CI.

### Esecuzione dei Test
```bash
python -m pytest --cov=pefforza
```

### Tabella dei File di Test e Copertura

| Test file | Area coperta | Cosa verifica | Note |
|:---|:---|:---|:---|
| [tests/test_rules.py](../tests/test_rules.py) | Logica di gioco pura | Correttezza di `check_winner` (orizzontale, verticale, diagonale), rilevazione colonne piene, funzioni di stack e specchiamento prospettico. | Indipendente da librerie pesanti. |
| [tests/test_connect4_env.py](../tests/test_connect4_env.py) | Ambiente Gymnasium | Comportamento del metodo `step()`, penalità per mosse illegali, controllo di fine partita per pareggio o vittoria. | Usa mock e seed preimpostati. |
| [tests/test_board_detector.py](../tests/test_board_detector.py) | Pipeline di visione artificiale | Genera una scacchiera sintetica a blocchi colorati ed assicura che `classify_board_image` la legga perfettamente a diverse risoluzioni. Verifica le confidenze per cella. | Non richiede webcam. |
| [tests/test_minimax.py](../tests/test_minimax.py) | Agente Minimax Negamax | Esegue ricerche a profondità fissa, verifica il funzionamento del time budgeting e dell'approfondimento iterativo senza blocchi. | Verifica la velocità di esecuzione. |
| [tests/test_blocks_threats.py](../tests/test_blocks_threats.py) | Regressione / Sicurezza tattica | Garantisce che gli agenti "medium", "hard" e "impossible" blocchino SEMPRE una minaccia di 3 pedine o prendano una vittoria immediata. | Risolve il bug segnalato sul watchdog. |
| [tests/test_voice.py](../tests/test_voice.py) | Modulo TTS Vocale | Verifica che l'accodamento messaggi, il ciclo di vita del thread worker e lo spegnimento avvengano correttamente senza perdite di risorse. | Imposta il backend su `null` in ambiente CI. |

---

## 2. Error Handling and Edge Cases
Il sistema applica pattern robusti per gestire imprevisti a runtime:

1.  **Fail-Soft Audio**: Il modulo [voice.py](../pefforza/interaction/voice.py) racchiude l'inizializzazione di `pyttsx3` in un blocco `try-except`. Se manca il driver audio del sistema operativo (comune in ambienti server Linux Headless o Docker), viene loggato un avvertimento e sostituito con `NullBackend`. Se un errore avviene durante la riproduzione vocale nel thread separato, il thread disattiva i tentativi successivi (`self._available = False`) ed esce in modo sicuro senza propagare l'errore al thread di gioco.
2.  **Validazione degli input utente**: Sia nella CLI (`get_human_action`) che nella GUI, le mosse inserite dall'utente vengono testate preliminarmente a livello logico. Qualora l'utente provi ad inserire una pedina in una colonna sature, il sistema non invia l'azione a `Connect4Env` (che causerebbe la sconfitta immediata ed il termine dell'episodio), ma mostra una notifica d'errore a schermo invitandolo a ripetere la scelta.
3.  **Sanificazione Mosse IA**: Se a causa di errori numerici o formati non supportati l'agente decisionale (Minimax/Neural) restituisce una colonna non consentita o non presente nell'elenco delle mosse legali, l'entrypoint intercetta l'anomalia e ripiega automaticamente sulla prima mossa legale valida (`action = valid[0]`), salvando la partita.
4.  **Fallback dei Modelli Neurali**: Se l'utente specifica la difficoltà `neural` ma il file `.zip` non esiste o `stable-baselines3` non è installato, il modulo [difficulty.py](../pefforza/agent/difficulty.py) intercetta l'eccezione, logga un warning e restituisce un agente euristico a 1-ply (`heuristic_agent`) in modo che il gioco rimanga giocabile.

---

## 3. Security, Privacy and Reliability
*   **Gestione dei Dati Personali (Privacy)**: La pipeline video OpenCV elabora i dati localmente in tempo reale in memoria RAM. **Nessun frame o registrazione visiva viene caricato su server esterni o salvato su disco**, ad eccezione dello snapshot manuale `vision_debug.png` salvato esplicitamente dall'utente premendo il tasto `[s]` in fase di diagnosi.
*   **Dipendenze Rischiose**: Il caricamento dei modelli tramite PyTorch e Stable-Baselines3 sfrutta il modulo standard `zipfile` e non prevede l'esecuzione di codice Python arbitrario non controllato (a differenza del caricamento tramite pickle insicuro).
*   **Prevenzione dei Crash**: L'interazione vocale e il rendering grafico avvengono su contesti isolati. Eventuali eccezioni di rendering sollevate da Pygame a causa di ridimensionamento improvviso della finestra vengono intercettate rilasciando i driver audio e video correttamente alla chiusura del processo tramite blocchi `finally: pygame.quit()`.
