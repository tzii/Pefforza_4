# Pefforza 4 Project Presentation

La presentazione viene generata da:

```powershell
node scripts/build_presentation.js
```

Output predefinito:

```text
presentation/Pefforza4_Project_Presentation.pptx
```

Per scegliere un percorso diverso:

```powershell
node scripts/build_presentation.js --out presentation/Pefforza4_Project_Presentation.pptx
```

Per generare anche le anteprime PNG usate per il controllo visivo:

```powershell
node scripts/build_presentation.js --preview-dir outputs/presentation-preview
```

## Requisiti

- Node.js 20 o successivo.
- Il runtime locale Codex con `@oai/artifact-tool` disponibile.
- Font Windows `Bahnschrift` e `Segoe UI`; PowerPoint applica un fallback se non sono installati.

Lo script non richiede webcam, modello caricato in memoria o dipendenze Python
del progetto. Tutti i diagrammi e i mockup sono costruiti con elementi
PowerPoint editabili.
