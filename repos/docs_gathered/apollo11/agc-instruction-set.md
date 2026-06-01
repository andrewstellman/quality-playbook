# AGC Instruction Set Reference

Source: Virtual AGC Assembly Language Manual (ibiblio.org/apollo/assembly_language_manual.html)
Gathered: 2026-04-12

## Instruction Encoding

Basic format: `CCC AAAAAAAAAAAA` (3-bit opcode + 12-bit address)

Variants:
- Erasable-only: `CCC QQ AAAAAAAAAA` (10-bit address)
- I/O-only: `CCC PPP AAAAAAAAA` (9-bit address)
- Extracodes: Two-word instructions preceded by EXTEND

## Basic Instructions

| Mnemonic | Octal | Description |
|----------|-------|-------------|
| TC K | 0KKKK | Transfer control to K; save return address in Q |
| CCS K | 1KKKK | Count, Compare, Skip — load diminished absolute value of K, branch 4 ways based on sign |
| DAS K | 2KKKK+1 | Double-precision add: A,L pair added to memory pair at K,K+1 |
| LXCH K | 2KKKK | Exchange L register with erasable K |
| INCR K | 2KKKK | Increment erasable K by 1 |
| ADS K | 2KKKK | Add A to erasable K; result in both A and K |
| CA K | 3KKKK | Clear and Add: load K into A |
| CS K | 4KKKK | Clear and Subtract: load complement of K into A |
| INDEX K | 5KKKK | Add K to the next instruction before executing it |
| DXCH K | 5KKKK+1 | Double exchange: swap A,L with memory pair at K,K+1 |
| TS K | 5KKKK | Transfer A to storage K; branch on overflow |
| XCH K | 5KKKK | Exchange A with erasable K |
| AD K | 6KKKK | Add K to A |
| MASK K | 7KKKK | Bitwise AND of K with A |

## Extracode Instructions (preceded by EXTEND)

| Mnemonic | Octal | Description |
|----------|-------|-------------|
| READ KC | 0KKKK | Read I/O channel KC into A |
| WRITE KC | 0KKKK | Write A to I/O channel KC |
| RAND KC | 0KKKK | Read I/O channel KC AND'd with A |
| WAND KC | 0KKKK | Write A AND'd with channel KC |
| ROR KC | 0KKKK | Read I/O channel KC OR'd with A |
| WOR KC | 0KKKK | Write A OR'd with channel KC |
| RXOR KC | 0KKKK | Read I/O channel KC XOR'd with A |
| DV K | 1KKKK | Divide: A,L pair divided by K; quotient in A, remainder in L |
| BZF K | 1KKKK | Branch to K if A is zero (or positive zero) |
| MSU K | 2KKKK | Modular subtract: A minus K for unsigned counter values |
| QXCH K | 2KKKK | Exchange Q register with erasable K |
| AUG K | 2KKKK | Augment: increment K toward its sign (add +1 or -1) |
| DIM K | 2KKKK | Diminish: decrement absolute value of K toward zero |
| DCA K | 3KKKK+1 | Double Clear and Add: load word pair at K,K+1 into A,L |
| DCS K | 4KKKK+1 | Double Clear and Subtract: load complement of pair into A,L |
| SU K | 6KKKK | Subtract K from A |
| BZMF K | 6KKKK | Branch if A is zero or negative |
| MP K | 7KKKK | Multiply A by K; product in A (high) and L (low) |

## Pseudo-Instructions (Assembler Directives)

| Directive | Description |
|-----------|-------------|
| ERASE | Reserve one word of erasable memory |
| EQUALS | Define a symbol as equal to an address or value |
| = | Same as EQUALS |
| DEC | Define a decimal constant |
| 2DEC | Define a double-precision decimal constant |
| OCT | Define an octal constant |
| 2OCT | Define a double-precision octal constant |
| BANK | Select a memory bank for subsequent code/data |
| SETLOC | Set the assembly location counter |
| BLOCK | Set assembly to a specific block number |
| COUNT | Manage memory-usage counting |
| SBANK= | Set the superbank bit for subsequent fixed-memory references |
| BNKSUM | Compute bank checksum ("bugger word") |
| -CADR | Compute complement of complete address |
| ADRES | Compute a 12-bit address |
| GENADR | Generate a generalized address |
| BBCON | Build a BB (bank) constant |
| 2BCADR | Double-precision bank-complete address |
| FCADR | Fixed-complete address (for TC or INDEX) |
| ECADR | Erasable-complete address |

## Shorthand Aliases

| Alias | Equivalent | Description |
|-------|------------|-------------|
| CAE K | CA K (erasable) | Clear and add from erasable |
| CAF K | CA K (fixed) | Clear and add from fixed |
| NOOP | TCF +1 (or CA A) | No operation |
| DDOUBL | DAS A | Double the A,L double-precision value |
| DTCF | Same as DXCH Z | Double transfer (unconditional branch with L) |
| COM | CS A | Complement A |
| DCOM | DCS A | Double complement A,L |
| DOUBLE | AD A | Double A (single precision) |
| OVSK | TS A | Skip on overflow |
| TCAA | TS Z | Transfer to address in A |
| EXTEND | special | Next instruction is an extracode |
| INHINT | special | Inhibit interrupts |
| RELINT | special | Release (enable) interrupts |
| RESUME | special | Return from interrupt |

## Key Programming Patterns

### Subroutine Call and Return
```
    TC    MYSUB       # Call MYSUB, return addr saved in Q
    # ... continues here after return ...

MYSUB   # ... do work ...
    TC    Q           # Return to caller
```

### Conditional Branch (CCS idiom)
```
    CCS   VALUE       # Test VALUE
    TC    POSITIVE    # VALUE > 0
    TC    PLUSZERO    # VALUE = +0
    TC    NEGATIVE    # VALUE < 0
    TC    MINUSZERO   # VALUE = -0
```

### Overflow-Protected Store
```
    TS    RESULT      # Store A in RESULT; if overflow, skip next
    TC    NOOVERFLOW  # Normal case
    # ... handle overflow here ...
```

### Index Indirect Addressing
```
    INDEX POINTER     # Add contents of POINTER to next instruction
    CA    0           # Effectively: CA (POINTER)
```

### Bank-Safe Calls
```
    TC    BANKCALL    # Utility that handles cross-bank calls
    CADR  TARGET      # Complete address of target routine
```
