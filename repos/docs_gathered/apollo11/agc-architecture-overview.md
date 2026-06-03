# Apollo Guidance Computer — Architecture Overview

Source: Virtual AGC project (ibiblio.org/apollo), NASA documentation, and community research.
Gathered: 2026-04-12

## Hardware Summary

- **CPU**: Block II AGC, 15-bit word, 1's complement arithmetic
- **Clock**: 2.048 MHz reference, 1.024 MHz internal
- **Instruction time**: 10–100 microseconds per operation
- **RAM**: 2,048 words (erasable core memory, ~4 KB)
- **ROM**: 36,864 words (core rope memory, ~74 KB)
- **I/O**: Channel-based peripheral interface (DSKY, IMU, radar, engines)

## CPU Registers (Memory-Mapped)

| Address | Name | Function |
|---------|------|----------|
| 00 | A | 16-bit accumulator; primary register for arithmetic |
| 01 | L | 16-bit lower product register for double-precision ops |
| 02 | Q | 16-bit return address storage for procedure calls |
| 03 | EB | Erasable bank register (3 bits select banks E0-E7) |
| 04 | FB | Fixed bank register (5 bits + superbank bit) |
| 05 | Z | 12-bit program counter |
| 06 | BB | Combined EB/FB register |
| 07 | — | Hardwired to zero |
| 20-23 | CYR, SR, CYL, EDOP | "Editing" registers with auto-shift behavior on access |
| 24-31 | TIME1-TIME6 | Timer/counter registers (10ms increments) |
| 32-44 | CDU/PIPA/RHC | Spacecraft orientation and acceleration counters |

## Memory Map

- **Unswitched Erasable** (0000-1377 octal): Directly accessible, includes CPU registers
- **Switched Erasable** (1400-1777): 8 banks (E0-E7), selected via EB register
- **Common Fixed** (2000-3777): 36 banks, selected via FB register + superbank bit
- **Fixed-Fixed** (4000-7777): Directly addressable read-only memory
- **I/O Channels** (000-777): Peripheral interface (DSKY, radar, IMU, engines)

## Data Formats

- **Single-precision**: 15-bit magnitude + sign (1's complement). The 16th bit normally copies the 15th; overflow makes them opposites.
- **Double-precision**: Two adjacent 15-bit words, 28-bit combined magnitude
- **Triple-precision**: Three words, 42-bit magnitude
- **CDU/counters**: Unsigned 2's complement (0 to 32767)

## Bank Switching

The 12-bit address field in instructions can only address 4K words directly. To access the full 36 banks of fixed memory and 8 banks of erasable memory, the AGC uses bank switching via the EB, FB, and BB registers plus a superbank bit on I/O channel 7. Strict "bank hygiene" programming conventions enforce correct calling across bank boundaries.

## Overflow and Interrupt Handling

- The 16th bit of A, L, and Q detects arithmetic overflow
- Overflow blocks interrupts until cleared
- 11 interrupt types triggered by counter overflow or external events
- Interrupt vector table at address 4000 (octal)
- Handlers must manually save A, L, Q registers to ARUPT, LRUPT, QRUPT

## Two Programming Languages

1. **Assembly Language ("Basic")**: One CPU instruction per line. Direct hardware control.
2. **Interpretive Language**: Higher-level, two instructions packed per word. Interpreted at runtime by the "Interpreter" program. Slower but far more memory-efficient. Critical for guidance equations.

Both languages are freely intermixed throughout the source code.
