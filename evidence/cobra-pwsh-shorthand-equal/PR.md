Title: powershell: complete values for shorthand flags with an equal sign

The generated PowerShell completion script only recognizes `--flag=value`, so a shorthand flag with an equal sign gets no completions.

With a flag `-o`/`--output` whose completion function returns `json` and `yaml`, in PowerShell 7.7:

- `prog get -o=<TAB>`: no completions
- `prog get --output=<TAB>`: `--output=json`, `--output=yaml`

This changes the check from `-Like "--*=*"` to `-Like "-*=*"`, as the bash completion script does (`[[ ${cur} == -*=* ]]`). With the change, `prog get -o=<TAB>` gives `-o=json`, `-o=yaml`.

Found by Quality Playbook (https://github.com/andrewstellman/quality-playbook) and reviewed by me.
