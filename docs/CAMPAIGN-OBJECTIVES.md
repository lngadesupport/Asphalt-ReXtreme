# Campaign Objectives

Campaign Edition owns career objective evaluation.

The original engine still produces raw race metrics, but it does not decide Campaign stars, rewards or progression.

Runtime catalog:

`_PACKAGE_PHASE5\CampaignObjectives.dat`

## Data model

Each objective is keyed by:

`event_id + objective_index`

An objective contains:

- metric;
- comparison;
- threshold;
- star value;
- flags.

Supported raw metrics currently include:

- placement;
- finish time;
- drift distance;
- airtime;
- nitro time;
- cars wrecked;
- environment wrecked;
- wreck count;
- flat spins;
- barrel rolls;
- obstacles broken;
- all-in nitro count;
- nitro chain count;
- normal nitro count.

Comparisons:

- less than or equal;
- greater than or equal;
- equal.

## Authority boundary

The final post-race path is:

```text
preserved race engine
      |
      | raw metrics only
      v
CampaignRaceMetrics
      |
      v
CampaignObjectives.dat
      |
      +--> evaluate objectives
      +--> calculate Campaign stars
      |
      v
Campaign event rewards/progression
      |
      v
CampaignSave.dat
```

The adapter must not submit stars calculated by the original online/career synchronization layer.

## Binary evidence used for the adapter

The original client contains a race telemetry structure with independently verified fields:

- `race_time_player`;
- `m_drifted`;
- `time_air`;
- `time_in_nitro`;
- obstacle-break count;
- flat-jump/spin count;
- barrel-roll count;
- nitro counters;
- wrecked cars/environment;
- wreck count.

A separate Career telemetry producer at `0x00F0E070` proves:

- event id is obtained through `0x00CBFC20`;
- placement is a 1..7 value before conversion by `0x00F66D20`;
- original star booleans are separately available, but Campaign Edition does not use them as authority.

The original star booleans are useful only as reverse-engineering validation while Campaign objective data is reconstructed.

## Final command

The intended adapter uses `CAMPAIGN_OP_FINISH_EVENT_RACE_METRICS`.

It passes a pointer to `CampaignRaceMetrics` through the generic Campaign command gateway.

Campaign Core:

1. validates the active race session;
2. evaluates the Campaign objective catalog;
3. derives stars;
4. records the event result;
5. calculates local rewards;
6. advances progression;
7. persists atomically;
8. rejects duplicate session payout.

The older command that accepts precomputed stars remains only for compatibility/testing and is not the target production adapter.
