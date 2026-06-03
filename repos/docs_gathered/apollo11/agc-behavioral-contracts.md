# AGC Behavioral Contracts — Spec-Derived Requirements

Source: OASIS-style behavioral extraction from NASA documentation, Virtual AGC project, and AGC source code comments.
Gathered: 2026-04-12

These contracts capture the key behavioral guarantees that the AGC software must uphold, derived from NASA specifications and the physical constraints of the Apollo spacecraft. They are organized by subsystem for use in quality review.

## Executive Scheduling Contracts

1. The Executive MUST service the highest-priority ready job before any lower-priority job.
2. The Executive MUST support at least 7 simultaneous jobs in the core set table.
3. When all core sets are occupied and a new job is requested, the Executive MUST raise alarm 1202 and shed the lowest-priority job.
4. When all VAC areas are occupied and a new job is requested, the Executive MUST raise alarm 1201.
5. Executive job priorities MUST be non-zero positive integers; priority 0 indicates an empty core set slot.
6. A job that calls CHANG1/CHANG2 MUST yield the CPU to any higher-priority job that has become ready.

## Waitlist Contracts

7. A Waitlist task MUST execute within one timer tick (10ms) of its scheduled time, subject to interrupt latency.
8. Waitlist tasks MUST NOT exceed approximately 3ms of execution time to avoid blocking other time-critical operations.
9. The Waitlist MUST support at least 8 pending tasks simultaneously.
10. A Waitlist task MUST execute at interrupt priority level, higher than any Executive job.

## Restart Protection Contracts

11. After a hardware restart, the Executive MUST reconstruct the job table from restart group/phase tables.
12. Every critical computation MUST call PHASCHNG before modifying state that would be inconsistent on restart.
13. Restart groups MUST be numbered 1-6; phase values encode both the restart point and the priority.
14. A restart MUST NOT lose accumulated navigation state (state vectors, IMU alignment).

## Program Alarm Contracts

15. When a program alarm is raised, the DSKY MUST display the alarm code and set the PROG indicator.
16. Alarm 1201 (no VAC areas) and 1202 (no core sets) MUST NOT abort the current critical program; the Executive MUST shed lower-priority work instead.
17. The crew MUST be able to acknowledge and clear alarms via DSKY verb commands.

## DSKY Interface Contracts

18. A Verb-Noun command MUST be echoed on the DSKY display before execution.
19. Verb 37 (change program) MUST terminate the current major mode before starting the new one.
20. Monitor verbs (V16, V46) MUST update the display registers periodically without blocking the Executive.
21. Extended verbs (V40-V99) MUST be dispatched through the EXTENDED_VERBS module.

## Navigation and Guidance Contracts

22. The state vector propagation (Servicer) MUST run at a fixed 2-second cycle during powered flight.
23. Guidance equations MUST use double-precision arithmetic for position and velocity.
24. Conic subroutines MUST handle both elliptical and hyperbolic trajectories.
25. IMU gimbal angles MUST be read from CDU counters at the start of each navigation cycle, not mid-cycle.

## Digital Autopilot (DAP) Contracts

26. The DAP MUST execute at a fixed rate (100ms cycle for LM, variable for CM entry).
27. RCS jet selection MUST minimize propellant usage while meeting attitude rate and deadband requirements.
28. DPS throttle commands MUST be rate-limited to avoid structural loads on the descent stage.
29. The DAP MUST switch between coasting and powered-flight modes based on engine on/off state.

## Lunar Landing Guidance Contracts (LM-specific)

30. P63 (braking phase) MUST maintain the commanded descent trajectory within targeting constraints.
31. P64 (approach phase) MUST allow crew redesignation of the landing point via hand controller.
32. P66 (landing phase) MUST provide manual rate-of-descent control while maintaining horizontal velocity damping.
33. The transition from P63 to P64 MUST occur at a specified altitude gate (approximately 7,000 feet).
34. The transition from P64 to P66 MUST be crew-commanded (not automatic).
35. Engine shutdown after touchdown MUST be triggered by the lunar contact probe signal.

## Memory and Banking Contracts

36. Cross-bank subroutine calls MUST use BANKCALL, SWCALL, or equivalent bank-safe calling conventions.
37. The bank registers (EB, FB, BB) MUST be saved and restored across interrupt service routines.
38. Interpretive code MUST NOT be used inside interrupt handlers or Waitlist tasks (too slow).
39. Fixed memory checksums ("bugger words") MUST produce correct bank sums for all 36 banks.

## Telemetry Contracts

40. Downlink telemetry MUST transmit the current state vector, program status, and alarm state at the specified downlink rate.
41. Uplink commands (via UPDATE_PROGRAM) MUST be validated before modifying navigation state.

## Integration and Cross-Module Contracts

42. The Interpreter MUST correctly handle interleaving with basic assembly code (RESUME/EXIT conventions).
43. FINDVAC (allocate new Executive job) MUST be callable from both Executive jobs and Waitlist tasks.
44. The PIPA (accelerometer) counters MUST be read and zeroed atomically to prevent data loss during navigation.
45. The Master Ignition Routine MUST coordinate engine arm, ullage, ignition, and throttle-up in the correct sequence with appropriate timing delays.
