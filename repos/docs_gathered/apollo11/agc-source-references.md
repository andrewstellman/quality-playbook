# Apollo 11 AGC — Source References

Gathered: 2026-04-12

## Primary Documentation Sources

### Virtual AGC Project
- **Home**: http://www.ibiblio.org/apollo/
- **Assembly Language Manual**: http://www.ibiblio.org/apollo/assembly_language_manual.html
- **Luminary Documentation**: http://www.ibiblio.org/apollo/Luminary.html
- **Colossus Documentation**: http://www.ibiblio.org/apollo/Colossus.html
- **Developer Guide**: http://www.ibiblio.org/apollo/developer.html
- **Beginner's Guide**: http://www.ibiblio.org/apollo/ForDummies.html

### NASA Technical Documents
- **R-700**: Apollo Guidance, Navigation and Control — comprehensive system description (http://www.ibiblio.org/apollo/Documents/R-700.pdf)
- **AGC4 Memo #9**: AGC Information Series technical memo (http://www.ibiblio.org/apollo/hrst/archive/1689.pdf)
- **AGC Brochure**: Overview of the AGC hardware and capabilities (http://www.ibiblio.org/apollo/Documents/agc_brochure.pdf)

### Original Source Scans
- **Luminary 099 scans**: http://www.ibiblio.org/apollo/ScansForConversion/Luminary099/
- **Comanche 055 scans**: http://www.ibiblio.org/apollo/ScansForConversion/Comanche055/

### GitHub Repository
- **Apollo-11**: https://github.com/chrislgarry/Apollo-11 (transcribed source code)
- **Virtual AGC**: https://github.com/rburkey2005/virtualagc (emulator and tools)

## Repo Structure

```
Apollo-11/
├── Comanche055/           # Command Module AGC software (65,348 lines)
│   ├── MAIN.agc           # Assembly organizer (includes all modules)
│   ├── EXECUTIVE.agc      # Job scheduler
│   ├── WAITLIST.agc       # Time-delayed task scheduler
│   └── ... (60+ .agc files)
├── Luminary099/           # Lunar Module AGC software (64,838 lines)
│   ├── MAIN.agc           # Assembly organizer
│   ├── EXECUTIVE.agc      # Job scheduler
│   ├── WAITLIST.agc       # Time-delayed task scheduler
│   └── ... (70+ .agc files)
├── README.md
├── CONTRIBUTING.md
└── LICENSE.md
```

## Assembler

The yaYUL assembler (part of Virtual AGC) can assemble the source code:
- Source: https://github.com/rburkey2005/virtualagc
- The assembler produces binary images compatible with the AGC hardware emulator
- Bank checksums in assembled output must match original checksums for validation

## Community Research
- CCS Working Group analysis: http://wg.criticalcodestudies.com/index.php?p=/discussion/18/
- Detailed AGC operation article: https://nexttechworld.com/pc-notebook/apollo-guidance-computer-agc-operation/
