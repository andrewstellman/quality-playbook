`enableBasicAuth` only installs a before-handler, and WebSocket upgrades don't run before-handlers, so an upgrade without credentials is accepted. The plugin now runs the same check in `wsBeforeUpgrade`, and the KDoc no longer says WebSocket upgrades are excluded. The test in `TestWsUpgrade` expects a 401 for an upgrade without credentials.

This builds on __PR028__, so that one should go in first.

Reported to @tipsy by email on 20 Oct. Found with the Quality Playbook, an AI code-review tool I maintain; I reproduced it and reviewed the fix myself.
