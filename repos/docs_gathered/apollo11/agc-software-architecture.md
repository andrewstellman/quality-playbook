# AGC Software Architecture — Executive, Waitlist, and Program Structure

Source: Virtual AGC project, NASA documentation, community research
Gathered: 2026-04-12

## Real-Time Operating System

The AGC ran a priority-driven, preemptive real-time operating system with two primary scheduling mechanisms: the Executive and the Waitlist.

### Executive

The Executive managed longer-running "jobs" — multi-step computations like guidance equations, navigation updates, and display management. Key characteristics:

- Priority-based scheduling with preemption
- Multiple jobs could be active simultaneously (up to ~7 jobs in the job table)
- Each job had a priority level; highest priority ran first
- Jobs could voluntarily yield CPU via CHANG1/CHANG2 checkpoints
- On overload, the Executive dropped lower-priority jobs to preserve critical functions
- This is what triggered the famous 1201/1202 alarms during Apollo 11's landing — the Executive correctly shed lower-priority tasks when CPU was overloaded by unexpected rendezvous radar interrupts

### Waitlist

The Waitlist managed short, time-critical "tasks" — small routines that needed to execute at precise future times. Key characteristics:

- Timer-driven: tasks scheduled to fire after a specified delay
- Tasks were short (typically a few hundred instructions max)
- Used for periodic operations: autopilot cycles, telemetry updates, display refreshes
- WAITLIST was called with a time delay and a task address
- When the timer expired, the task executed at interrupt level
- Tasks could reschedule themselves for periodic execution

### Interaction Between Executive and Waitlist

- Waitlist tasks ran at interrupt priority (higher than any Executive job)
- A Waitlist task could wake up an Executive job via FINDVAC (allocate a new job) or NOVAC
- Executive jobs used BANKCALL/ISWCALL for cross-bank subroutine calls
- The TWIDDLE routine was a common pattern for scheduling a waitlist task from within a job

## Restart Protection

The AGC had hardware-level restart capability. If the software detected an inconsistent state (via program alarms or watchdog timeout), the computer restarted. To survive restarts:

- Critical state was stored in "restart-protected" erasable memory
- Programs maintained "restart groups" — numbered categories of work
- After restart, the Executive rebuilt the job table from restart group state
- Phase/group tables tracked which phase of which program was executing
- This is why many AGC source files have extensive PHASCHNG (phase change) calls

## Program Alarm System

The AGC could raise numbered alarms to flag error conditions:

| Alarm | Meaning |
|-------|---------|
| 1201 | Executive overflow — no free VAC (variable storage) areas |
| 1202 | Executive overflow — no free core sets for new jobs |
| 1210 | IMU not operating |
| 1211 | IMU not aligned |
| 1302 | Optics CDU fail |
| 1501 | Radar data good but unexpected changes |

The 1201/1202 alarms during Apollo 11's landing were caused by the rendezvous radar sending excessive interrupts while the landing guidance was running. The Executive correctly dropped lower-priority jobs and continued the critical descent guidance.

## Verb/Noun DSKY Interface

The Display and Keyboard (DSKY) used a two-digit Verb + two-digit Noun command system:

- **Verbs** specify actions (display, load, execute, monitor)
- **Nouns** specify data items (time, position, velocity, angles)
- Three 5-digit signed decimal displays (R1, R2, R3)
- Status indicators: PROG, COMP ACTY, UPLINK ACTY, etc.
- Astronaut enters: V06 N36 ENTER → "Display (verb 06) AGC time (noun 36)"

Key verbs:
- V06: Display decimal
- V16: Monitor decimal (continuous update)
- V21: Load component 1
- V25: Load component 1,2 (octal)
- V37: Change program (enter new major mode)
- V50: Please perform (crew action required)

## Major Programs (P-Numbers)

Programs were identified by two-digit numbers entered via V37:

### Command Module (Comanche055)
- P00: CMC idle
- P01-P02: Pre-launch alignment
- P11: Earth orbit insertion monitor
- P15: TLI (Trans-Lunar Injection) monitor
- P20: Rendezvous navigation
- P21: Ground track determination
- P23: Cislunar midcourse navigation
- P30: External delta-V (ground-computed maneuver)
- P40: SPS thrusting (main engine burn)
- P47: Thrust monitor
- P51: IMU orientation determination
- P52: IMU realignment
- P61-P67: Entry guidance programs

### Lunar Module (Luminary099)
- P00: LGC idle
- P06: Power-down program
- P12: Powered ascent guidance
- P20: Rendezvous navigation
- P22: Lunar landmark tracking
- P25: Preferred tracking attitude
- P30: External delta-V
- P40: DPS thrusting (descent engine)
- P41: RCS thrusting
- P42: APS thrusting (ascent engine)
- P47: Thrust monitor
- P51: IMU orientation determination
- P52: IMU realignment
- P57: Lunar surface alignment
- P63: Braking phase guidance (landing)
- P64: Approach phase guidance
- P66: Landing phase (manual with rate-of-descent control)
- P68: Landing confirmation
- P70: DPS abort
- P71: APS abort

## Source Code Organization

Both Comanche055 and Luminary099 are organized as a set of .agc files assembled together by a MAIN.agc organizer. Major source modules include:

### Shared Between CM and LM
- EXECUTIVE.agc — Job scheduling and management
- WAITLIST.agc — Time-delayed task scheduling
- FRESH_START_AND_RESTART.agc — Initialization and restart recovery
- ALARM_AND_ABORT.agc — Program alarm system
- DISPLAY_INTERFACE_ROUTINES.agc — DSKY verb/noun processing
- EXTENDED_VERBS.agc — Additional verb handlers
- INTERPRETER.agc / INTER-BANK_COMMUNICATION.agc — Interpretive language runtime
- CONIC_SUBROUTINES.agc — Orbital mechanics
- DOWN-TELEMETRY_PROGRAM.agc — Ground telemetry
- ERASABLE_ASSIGNMENTS.agc — RAM variable declarations
- FIXED_FIXED_CONSTANT_POOL.agc — Mathematical and physical constants
- UPDATE_PROGRAM.agc — Ground command uplink processing
- PINBALL_GAME_BUTTONS_AND_LIGHTS.agc — DSKY interface logic

### CM-Specific (Comanche055)
- CM_ENTRY_DIGITAL_AUTOPILOT.agc — Atmospheric entry control
- CM_BODY_ATTITUDE.agc — Attitude management
- TVC*.agc — Thrust Vector Control (SPS engine gimbal)
- P11.agc — Earth orbit insertion
- ENTRY_LEXICON.agc — Entry guidance tables

### LM-Specific (Luminary099)
- BURN_BABY_BURN--MASTER_IGNITION_ROUTINE.agc — Engine ignition sequencing
- LUNAR_LANDING_GUIDANCE_EQUATIONS.agc — P63/P64/P66 landing guidance
- ASCENT_GUIDANCE.agc — P12 powered ascent
- SERVICER.agc — Navigation state vector propagation
- LANDING_ANALOG_DISPLAYS.agc — Altitude/velocity displays during landing
- DAPIDLER_PROGRAM.agc — DAP (Digital Autopilot) idle loop
- TRIM_GIMBAL_CONTROL_SYSTEM.agc — DPS engine gimbal trim
- AOTMARK.agc — Alignment Optical Telescope star sighting
- R60_R62.agc — Attitude maneuver routines
- THROTTLE_CONTROL.agc — DPS throttle management
- TJET_LAW.agc — RCS jet selection logic

## Software Development and Quality

- Software developed at MIT Instrumentation Laboratory under Margaret Hamilton's leadership
- Assembled using YUL (later GAP) assembler on Honeywell mainframes
- Extensive simulation testing on ground before ROM manufacture
- ROM manufactured as "core rope" — physically woven wire through/around magnetic cores
- Once manufactured, software was immutable — no patches possible in flight
- Each memory bank had checksums ("bugger words") for validation
- Multi-stage QA: assembly, simulation, electrical test, thermal/vibration validation

## Key Technical Constraints

- Total 36,864 words of ROM — every instruction counted
- Memory was so tight that self-test routines were removed from flight software
- "Uncountable tricks" used to save memory, often at the cost of readability
- Two languages (assembly + interpretive) intermixed to balance speed vs memory
- Bank switching required careful "bank hygiene" to avoid cross-bank bugs
- No floating point — all calculations in fixed-point scaled arithmetic
- 15-bit precision required careful numerical analysis to avoid overflow/underflow
