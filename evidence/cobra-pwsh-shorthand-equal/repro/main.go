package main

// cobra BUG-018 Mac run: a real CLI built from cobra at the pin (go.mod replace), so PowerShell can call its
// __complete request. Same command shape as the container repro: prog get -o/--output with completions json, yaml.
import "github.com/spf13/cobra"

func main() {
	root := &cobra.Command{Use: "prog", Run: func(*cobra.Command, []string) {}}
	get := &cobra.Command{Use: "get", Run: func(*cobra.Command, []string) {}}
	get.Flags().StringP("output", "o", "", "")
	get.RegisterFlagCompletionFunc("output", func(*cobra.Command, []string, string) ([]string, cobra.ShellCompDirective) {
		return []string{"json", "yaml"}, cobra.ShellCompDirectiveNoFileComp
	})
	root.AddCommand(get)
	root.Execute()
}
