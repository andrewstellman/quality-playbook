When no username and password are configured, `BasicAuthPlugin` compares a request's missing credentials with the missing configuration (`null == null`) and lets the request through. It now rejects every request when either value is missing. The test in `TestRequest` registers the plugin without credentials and expects a 401.

Reported to @tipsy by email on 20 Oct. Found with the Quality Playbook, an AI code-review tool I maintain; I reproduced it and reviewed the fix myself.
