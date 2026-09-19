# Premium Economy Design

The default Asphalt ReXtreme Offline Edition economy should behave like a traditional paid racing game, not a free-to-play service.

## Core principles

- No real-money purchases.
- No premium-currency purchases.
- No rewarded-ad gates.
- No energy/fuel system that prevents continued play.
- No timers whose purpose is to sell skips.
- No login streaks or server-dependent daily rewards required for progression.
- Every car, upgrade and event that exists in the target build should be obtainable through offline play.
- Progression should reward racing skill and career completion rather than repetitive grinding.
- A fresh Premium save must be able to reach and complete the end of the offline career without needing exploits, purchases, advertisements or unreasonable grinding.
- **Race rewards never diminish because a race has already been completed or repeated.** The same performance in the same event must always produce the same base payout.

## Default mode: Premium

The default economy is **Premium**.

### Currency

Keep one primary gameplay currency where practical.

If the original build uses multiple currencies:
- normal race currency remains earnable through play;
- premium-only currency costs should be converted to normal progression, direct unlock conditions, or offline rewards;
- no currency should require a store purchase or advertisement.

Exact conversion values must be derived from the real 1.7.3.8 data rather than guessed.

### Repeatable race rewards

All normal offline races remain repeatable sources of currency.

Rules:
- no first-win-only reduction to the normal race payout;
- no diminishing returns after repeated completions;
- no daily payout cap;
- no cooldown before a race can pay again;
- no hidden penalty for farming the same event;
- no server-side reward validation required;
- the player's position, difficulty/performance bonuses and other legitimate race modifiers may affect the payout, but **repeat count may not**.

Example target behavior:

```
Race A — 1st place = 4,000 credits
1st completion  -> 4,000
2nd completion  -> 4,000
10th completion -> 4,000
50th completion -> 4,000
```

This gives the player freedom to replay a favorite race whenever extra money is needed without the game progressively punishing them.

### Career completion guarantee

The economy must be balanced around a complete fresh-save playthrough.

For each career tier/chapter we will calculate:

```
guaranteed normal earnings
+ reasonable optional replay earnings
>= required car purchases
+ required upgrade costs
+ progression expenses
```

Design targets:
- normal career completion should fund the majority of required progression;
- a player making sensible purchases should never reach a mandatory event with no realistic way to continue;
- optional replaying can accelerate progression or correct poor spending choices;
- repeating races must always remain a reliable recovery path;
- no single mandatory car or upgrade should require excessive repetition of one event;
- 100% completion should be achievable entirely offline.

### Cars

Baseline Premium-mode vehicle pricing target:

```
ReXtreme car price = original car price × 0.80
```

That is a default **20% reduction** from the original 1.7.3.8 price.

Examples:

```
Original 10,000  -> ReXtreme 8,000
Original 50,000  -> ReXtreme 40,000
Original 125,000 -> ReXtreme 100,000
```

Rules:
- apply the 20% reduction before final balancing;
- preserve meaningful progression between vehicle classes/tiers;
- retain career/event unlock conditions where they improve progression;
- cars that originally require premium currency must be converted to normal offline progression or normal credits;
- if a specific car remains a progression bottleneck after the 20% reduction, it may receive an additional targeted adjustment;
- if the reduction makes a very cheap starter car meaningless, that individual price may be rounded sensibly rather than following the multiplier mechanically.

Cars should be unlocked through one or more of:
- career progression;
- event completion;
- class/tier progression;
- achievement-style milestones;
- reasonable credit purchase after the related tier is reached.

A player should not need to repeat the same race excessively just to afford the next required car.

### Upgrades

Upgrades retain meaningful progression but use reasonable in-game costs.

Targets:
- early upgrades should be affordable after normal career play;
- later upgrades may require additional races, but not free-to-play-style grinding;
- no upgrade timer;
- no premium-currency skip;
- no ad requirement;
- mandatory performance-rating gates must always be financially reachable from offline play.

### Events and gates

If an event is blocked only by:
- an advertisement;
- an unavailable online service;
- a real-money purchase;
- an artificial wait timer;

the ReXtreme offline logic should replace that requirement with an offline progression condition or direct availability.

Skill/progression requirements may remain when they improve the game.

## Optional mode: Sandbox

For testing and players who want unrestricted access, ReXtreme can also provide a separate **Sandbox** profile:

- unlimited local currency;
- zero-cost upgrades;
- all locally present cars/content unlocked;
- no effect on Premium-mode saves.

Sandbox is not the default game balance.

## Save separation

Premium and Sandbox should use separate profile/save identifiers so that switching modes cannot accidentally destroy normal progression.

## Balance workflow

Before setting final values:
1. extract vehicle prices, upgrade costs, event payouts and unlock conditions from build 1.7.3.8;
2. apply the initial 0.80 vehicle-price multiplier;
3. map the complete career progression;
4. identify any original first-win, repeat-reward, cooldown, daily-cap or server-validation logic;
5. calculate expected income versus required spending per tier;
6. simulate a fresh save from the first event through career completion;
7. rebalance progression bottlenecks and price outliers;
8. verify repeated events always retain their full intended payout;
9. play-test fresh saves with conservative, average and completionist spending patterns.

The goal is a complete paid-game progression curve, not simply multiplying rewards or setting every value to zero.
