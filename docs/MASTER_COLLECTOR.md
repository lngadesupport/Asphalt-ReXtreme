# ReXtreme Master Collector

`REXTREME_COLETOR_MASTER.bat` is the single collection entry point for the Asphalt ReXtreme project.

It supersedes the early `ANALISAR_BUILD.bat` and `COLETAR_STAGE2.bat` workflows.

## Purpose

The collector is designed to remain useful throughout the Offline Edition development cycle:

- target build identification;
- complete file inventory and SHA-256 hashes;
- APPX manifest/dependency/capability mapping;
- EXE/DLL version and PE metadata;
- copies of binaries required for private static analysis;
- configuration/economy/network/save candidate collection;
- text keyword scanning;
- EXE/DLL string triage;
- URL/domain discovery;
- imported-DLL candidate discovery;
- Windows/CPU/GPU/runtime context;
- AppX registration status;
- save/profile inventory;
- optional deep save-state snapshot;
- one final ZIP ready to send for analysis.

The collector is **read-only with respect to the game directory**. It does not patch or launch Asphalt Xtreme.

## Modes

### Complete Safe

Default and recommended.

Collects all project-relevant analysis data, key binaries and configuration candidates. Game save/state content is **not copied**; only its file metadata and hashes are inventoried.

### Deep

Includes everything from Complete Safe and also copies small files from the Asphalt Xtreme package's `LocalState`, `RoamingState`, `Settings` and `TempState` directories.

Use Deep only when save/profile reverse engineering is needed.

## Output

Each run creates:

```
collector-output/
├── ReXtreme-Collector-YYYYMMDD-HHMMSS/
│   ├── REPORT_README.txt
│   ├── collector.log
│   ├── reports/
│   │   ├── system-info.txt
│   │   ├── appx-registration.txt
│   │   ├── manifest-summary.txt
│   │   ├── inventory-with-hashes.csv
│   │   ├── binary-metadata.csv
│   │   ├── pe-metadata.csv
│   │   ├── collected-candidates.csv
│   │   ├── text-keyword-hits.tsv
│   │   ├── binary-interesting-strings.tsv
│   │   ├── imported-dll-candidates.tsv
│   │   ├── urls.txt
│   │   ├── domains.txt
│   │   └── save-state-inventory.csv
│   ├── collected/
│   │   ├── binaries/
│   │   └── candidates/
│   └── save-snapshot/        # Deep mode only
├── ReXtreme-Collector-YYYYMMDD-HHMMSS.zip
└── ReXtreme-Collector-YYYYMMDD-HHMMSS.zip.sha256.txt
```

Send the generated ZIP in the project chat. Do not commit it to GitHub because it may contain proprietary game binaries/configuration data.

## Reuse

The BAT remembers the last game directory locally in `collector-last-path.txt`, which is ignored by Git.

Run the same collector again after patches, launcher changes, save-format changes or compatibility tests. The timestamped output makes before/after comparisons possible.
