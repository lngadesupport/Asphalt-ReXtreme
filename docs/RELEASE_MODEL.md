# Release model

## Asphalt ReXtreme Offline Edition

This is the first and primary target.

### User experience

The intended end-user flow is:

1. Obtain/own a compatible original Asphalt Xtreme Windows build.
2. Run the ReXtreme importer once.
3. The importer verifies the source build and creates an independent ReXtreme installation.
4. From then on, launch `AsphaltReXtreme.exe` and play offline.

Normal gameplay must not require:
- an active Internet connection;
- Gameloft/Netflix services;
- ad servers;
- a community backend;
- Python or developer tools;
- command-line arguments;
- manual configuration editing.

### Default Offline profile

The Offline Edition should ship with an easy preservation-focused profile:
- offline services only;
- local saves;
- ad-dependent local actions made available offline;
- preservation economy enabled;
- free/local upgrades enabled;
- modern display/input defaults.

Where possible, power users can disable individual preservation conveniences in `ReXtreme.ini`.

## Asphalt ReXtreme Online Edition

A later, separate release track.

It may add a community backend, lobbies and multiplayer, but must not become a dependency of the Offline Edition. Offline saves/configuration should remain usable without the online client/server components.

## Repository vs release package

GitHub stores only project-owned code, patch descriptions, tools and documentation.

The project does **not** publish original proprietary game assets or binaries. The importer creates the playable ReXtreme directory from files supplied by the user from a compatible legitimate copy.
