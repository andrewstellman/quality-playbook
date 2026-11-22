module repro

go 1.24

require github.com/spf13/cobra v0.0.0

require (
	github.com/inconshreveable/mousetrap v1.1.0 // indirect
	github.com/spf13/pflag v1.0.9 // indirect
)

replace github.com/spf13/cobra => /home/claude/repro/src/cobra
