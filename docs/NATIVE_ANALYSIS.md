# Native Windows build analysis

If the ChatGPT runtime cannot mount the large multipart archive, the same build inventory can be produced locally with **Windows PowerShell only**.

No Python is required.

## Run

Open PowerShell in the repository folder and run:

```powershell
powershell -ExecutionPolicy Bypass -File .\\tools\\analyze_build.ps1 -GameDir "D:\\Path\\To\\Asphalt Xtreme"
```

The script is read-only. It does not launch or modify the game.

It creates `analysis-output\\` with:

- `summary.txt` — package identity, executable entry point and binary hashes;
- `inventory.csv` — complete extracted-file inventory;
- `binary-hashes.csv` — SHA-256 for EXE/DLL files;
- `keyword-hits.txt` — text/config files containing network, ad, economy or graphics keywords.

These small reports can be shared without re-uploading the full game package.

The first binary patch manifest remains empty until the exact hashes and original byte sequences have been verified.
