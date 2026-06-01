# Apollo Guidance Computer — Software Version History

Source: Virtual AGC project (ibiblio.org/apollo)
Gathered: 2026-04-12

## Command Module Software Lineage

The CM software evolved through three major families:

### Block I (pre-Apollo 7)
- **Solarium** — Early Block I development
- **Sundisk** — Block I test versions
- **Sundial** — Block I flight software (Apollo 4-6 unmanned missions)
- **Sunspot** — Late Block I variant

### Block II — Colossus Family ("Colossus 1")
- **Colossus 237** — Apollo 8 (first crewed lunar orbit)
- **Colossus 249** (Colossus 1A) — Apollo 9 (Earth orbit LM test)

### Block II — Comanche Family ("Colossus 2")
- **Comanche 044** — Development version (known P30/P40 interface bug)
- **Comanche 045/2** — Apollo 10 (lunar orbit LM test)
- **Comanche 051** — Pre-Apollo 11 development
- **Comanche 055** — **Apollo 11** (first lunar landing) ← THIS REPO
- **Comanche 067** — Apollo 12
- **Comanche 072** (Manche72R3) — Apollo 13

### Block II — Artemis Family ("Colossus 3")
- **Artemis 071** — Development (known P15 sign bug)
- **Artemis 072** — Apollo 15-17 (J-missions with extended stays)

## Lunar Module Software Lineage

### Precursors
- **Retread 44, 50** — Early LM development
- **Aurora 12, 88** — LM checkout and test software (included full self-test suite)
- **Sunburst 37, 120** — LM development versions
- **Sundance 306** — Pre-Luminary LM software

### Luminary Family
- **Luminary 069** — Apollo 10 (lunar orbit test, first LM descent to 50,000 feet)
- **Luminary 099 Rev 1** — **Apollo 11** (first lunar landing) ← THIS REPO
- **Luminary 116** — Apollo 12
- **Luminary 131 Rev 1** — Apollo 13 (LM used as lifeboat)
- **Luminary 178** — Apollo 14
- **Luminary 210** — Apollo 15-17 (common J-mission version)

## Key Version Differences

### Comanche 055 vs Earlier Versions
- Added R-2 lunar potential model (absent in Comanche 051)
- Fixed P30/P40 interface bug from Comanche 044
- Contained the specific code that handled the 1201/1202 alarms during landing

### Luminary 099 vs Earlier Versions
- Refined landing guidance equations (P63/P64/P66)
- Improved restart protection for powered descent
- Contains the BURN_BABY_BURN master ignition routine

## Known Issues in This Version

### Apollo 11 Flight Anomalies
1. **1201/1202 Executive overflow alarms** during powered descent — caused by rendezvous radar stealing CPU cycles. Software handled correctly by shedding low-priority tasks.
2. **Rendezvous radar left in wrong mode** — crew procedure issue, not software bug, but it triggered the CPU overload above.

### Known Code Quirks
- Source code contains comments from the original programmers, including humor ("BURN_BABY_BURN", "PINBALL_GAME_BUTTONS_AND_LIGHTS")
- Memory was extremely tight — the programmers used extensive tricks to save words
- Some modules have hand-optimized instruction sequences that sacrifice readability for space
