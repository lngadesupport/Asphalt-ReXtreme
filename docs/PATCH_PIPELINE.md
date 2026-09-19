# Patch pipeline

The ReXtreme patcher is deliberately conservative.

## Rules

1. Every patched source file must match an exact SHA-256.
2. Every byte patch must define both the expected original bytes and replacement bytes.
3. The patcher refuses unknown files/builds.
4. A backup is created before the first write.
5. Offsets are never committed until verified against the target build.

## Current target

- Package: `A278AB0D.AsphaltXtreme`
- Version: `1.7.3.8`
- Architecture: `x86`

The initial manifest is intentionally empty until the uploaded build can be fully inventoried.

## Planned first patch groups

- offline startup / dead service bypasses;
- ad-gate removal for local content;
- local save/profile behavior;
- repeat-race payout normalization;
- paid-game economy conversion;
- modern video/camera options.

## Dry run

Once hashes are filled in:

```powershell
py tools/patcher.py "D:\Games\Asphalt Xtreme Extracted" --dry-run
```

A real patch run uses the same command without `--dry-run`.
