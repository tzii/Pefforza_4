# Architettura di Sistema e Flusso dei Dati

Questo documento analizza l'architettura generale di **Pefforza**, il ciclo di vita dell'esecuzione per ciascun entrypoint e il percorso dettagliato che compiono i dati dall'input hardware all'output dell'utente.

---

## 1. High-Level Architecture
L'architettura del sistema Pefforza segue un modello modulare disaccoppiato in cui i moduli di interazione e visione comunicano con il motore logico e decisionale attraverso strutture dati standardizzate (principalmente array NumPy 2D).

```mermaid
flowchart TD
    User["Giocatore Umano"] <--> EntryPoint["Entrypoint di Gioco (GUI / CLI / AR)"]
    
    subgraph Video["Pipeline Video (OpenCV)"]
        Cam["Webcam Stream"] --> Detector["BoardDetector (Calibrazione + Warp)"]
        Detector --> Classifier["HSV Cell Classifier"]
    end
    
    subgraph Logic["Regole & Stato"]
        Env["Gymnasium Environment (Connect4Env)"] <--> Rules["rules.py (Pure Game Logic)"]
    end
    
    subgraph Engine["Motore Decisionale (IA)"]
        Difficulty["difficulty.py (Registry)"] --> Decision["Negamax / PPO Model"]
        Decision --> SafetyNet["Tactical Safety Net (1-ply)"]
    end
    
    subgraph Speech["Sintesi Vocale"]
        Voice["VoiceEngine"] --> Queue["Threaded Queue Worker"]
        Queue --> TTS["pyttsx3 / Null Backend"]
    end

    EntryPoint --> Cam
    Classifier -- "Matrice 6x7" --> EntryPoint
    EntryPoint --> Env
    Env -- "Osservazione Normalizzata" --> Engine
    Engine -- "Mossa Suggerita" --> EntryPoint
    EntryPoint --> Voice
```

### Dettaglio dei blocchi architetturali:
1.  **Entrypoint (Livello di Orchestrazione)**: Riceve gli input utente (clic del mouse, tastiera o coordinate dei corner visivi), coordina i componenti, avvia il ciclo di gioco e disegna le informazioni sullo schermo (Pygame o OpenCV).
2.  **Vision Pipeline**: Rileva la scacchiera fisica a 4 punti. Esegue una trasformazione di prospettiva lineare per correggere l'inquadratura ottenendo un'immagine rettangolare pulita da analizzare cella per cella.
3.  **Core Game Logic**: Mantiene lo stato formale della partita (tabellone $6 \times 7$), applica la fisica della gravità del Forza 4 e decide se c'è un vincitore o un pareggio. L'ambiente Gymnasium fa da wrapper per l'addestramento dell'agente neurale.
4.  **Decision Engine**: Seleziona la colonna migliore in cui inserire la pedina. Riceve lo stato normalizzato del tabellone e utilizza l'agente opportuno a seconda della difficoltà scelta. Applica sempre la `tactical_safety_net` per garantire mosse sensate e prive di errori immediati.
5.  **Interaction Engine**: Un'architettura basata su thread produttore-consumatore. Il thread principale invia frasi testuali da pronunciare alla coda decodificata da un daemon worker, impedendo che le chiamate sincrone di `pyttsx3` blocchino il frame rate del gioco.

---

## 2. Main Execution Flow
Il flusso di esecuzione varia in base all'entrypoint. Analizziamo in dettaglio il flusso per l'assistente visivo continuo ([main.py](../main.py)):

```mermaid
sequenceDiagram
    autonumber
    actor U as Utente
    participant M as main.py (Orchestratore)
    participant BD as BoardDetector
    participant V as VoiceEngine
    participant RL as Agent (PPO / Minimax)

    M->>V: Inizializza VoiceEngine()
    V-->>M: Start Daemon Thread & pyttsx3 Backend
    M->>BD: Inizializza BoardDetector()
    M->>BD: calibrate(cap)
    BD->>U: Apri finestra e richiedi 4 click (TL, TR, BR, BL)
    U-->>BD: Click sui 4 angoli
    BD-->>M: Salva Matrice di Trasformazione Prospettica (Matrix)
    
    loop Ciclo Principale
        M->>BD: process_frame(frame)
        BD->>BD: Warp immagine prospettica
        BD->>BD: Analizza celle in HSV (0=Vuoto, 1=Rosso, 2=Giallo)
        BD-->>M: Ritorna Griglia (6x7) e Immagine Warped
        
        M->>M: Calcola numero pedine Rosse (Umano) e Gialle (AI)
        alt Turno dell'AI (Rosso > Giallo)
            M->>M: swap_perspective (se AI gioca Giallo)
            M->>RL: predict(model_input) / select_move()
            RL->>RL: Applica Tactical Safety Net (1-ply win/block check)
            RL-->>M: Ritorna Colonna Decisionale
            M->>BD: draw_move(frame, col) [Disegna Freccia]
            alt Non ancora annunciato verbalmente
                M->>V: play_move_commentary(col, confidence)
                V-->>U: Pronuncia "Putting in column X..."
            end
        else Turno dell'Umano
            M->>M: Resetta flag annunciatore
        end
        M->>U: Mostra feed OpenCV a video con AR overlays
    end
```

### Ciclo di vita dei singoli Entrypoint:
*   **play_cli.py**: Inizializza l'ambiente `Connect4Env`, avvia un ciclo `while not (terminated or truncated)`. Chiede l'input all'utente su console tramite validazione (`get_human_action`). Per l'IA, calcola il tempo di pensiero, invia il comando TTS per la mossa e chiama `env.step()`.
*   **play_gui.py**: Avvia l'interfaccia Pygame. Nel ciclo principale gestisce gli eventi `MOUSEMOTION` (sposta l'anteprima della pedina rossa in alto) e `MOUSEBUTTONDOWN` (rilascia la pedina). Esegue una sequenza di animazione interpolata quadratica prima di aggiornare lo stato di gioco interno. Se il turno è dell'IA, mostra lo stato "AI thinking..." ed esegue l'agente. Dispone del *Watchdog* integrato che scrive su `watchdog.log` in caso di mancate parate tattiche del motore di gioco.
*   **play_physical.py**: Permette all'utente di giocare a turni assistiti. Il flusso rimane in attesa di comandi da tastiera. Premendo la barra spaziatrice `[SPACE]`, la webcam cattura un fotogramma, estrae lo stato attuale del tabellone tramite `process_frame` del `BoardDetector`, verifica lo stato di vittoria ed esegue una singola predizione del modello visualizzando una freccia persistente sulla colonna raccomandata.

---

## 3. Data Flow
Il viaggio dei dati all'interno del sistema Pefforza segue un ciclo lineare in cui i dati analogici (video) vengono convertiti in matrici digitali discrete, manipolati e infine restituiti come output visivi o vocali.

```mermaid
flowchart LR
    FrameIn["1. Web Camera Frame (BGR Image)"] --> Warp["2. Perspective Transform (3x3 Matrix)"]
    Warp --> Crop["3. Warped Image (Rectangular 700x600)"]
    Crop --> HSV["4. HSV Color Masking (Red/Yellow Filters)"]
    HSV --> Classify["5. Fill-Ratio Threshold Comparison"]
    Classify --> GridView["6. Vision Grid (6x7 np.int8: Red=1, Yellow=2)"]
    GridView --> PerspSwap["7. Perspective Swap (Agent Perspective: Self=1, Opponent=2)"]
    PerspSwap --> AgentLogic["8. Decision Engine (Minimax / PPO)"]
    AgentLogic --> RecCol["9. Recommended Column (0-6 Integer)"]
    RecCol --> OutputAR["10. Graphical Overlay (Arrow at Column Center)"]
    RecCol --> OutputVoice["11. Thread-safe TTS Notification (Audio Playback)"]
```

### Struttura e passaggi della pipeline dati:
1.  **Input Video**: Frame grezzo acquisito via OpenCV in spazio BGR.
2.  **Omografia prospettica**: L'immagine viene proiettata tramite omografia prospettica per rettificare la scacchiera fisica a una dimensione uniforme di $700 \times 600$ pixel.
3.  **Filtraggio HSV**: La scacchiera rettificata viene convertita in HSV. Vengono estratti due canali maschera: uno per il Rosso (con due intervalli per gestire il wrap del colore sull'asse H) e uno per il Giallo.
4.  **Misura della confidenza**: Per ciascuna delle 42 celle ($6 \times 7$), viene calcolata la frazione di pixel attivi nella maschera. Se supera il $30\%$ (`_FILL_THRESHOLD`), la cella viene etichettata con il rispettivo colore.
5.  **Normalizzazione dell'agente**: Lo stato visivo identifica il Rosso con `1` e il Giallo con `2`. Per essere compreso dal modello addestrato (che assume sempre di essere il giocatore `1`), lo stato passa attraverso `rules.swap_perspective` qualora l'IA stia giocando come giallo (secondo giocatore).
6.  **Decisione e Output**: L'azione restituita (ID colonna) viene invertita se la telecamera è stata specchiata a schermo, disegnando una freccia indicativa sopra la colonna bersaglio e inviando il testo audio al thread vocale.
