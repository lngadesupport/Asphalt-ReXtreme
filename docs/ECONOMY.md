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

## Default mode: Premium

The default economy is **Premium**.

### Currency

Keep one primary gameplay currency where practical.

If the original build uses multiple currencies:
- normal race currency remains earnable through play;
- premium-only currency costs should be converted to normal progression, direct unlock conditions, or offline rewards;
- no currency should require a store purchase or advertisement.

Exact conversion values must be derived from the real 1.7.3.8 data rather than guessed.

### Cars

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
- no ad requirement.

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
2. map the complete career progression;
3. calculate expected income versus required spending per tier;
4. rebalance outliers;
5. play-test a fresh save from start to finish.

The goal is a complete paid-game progression curve, not simply multiplying rewards or setting every value to zero.
