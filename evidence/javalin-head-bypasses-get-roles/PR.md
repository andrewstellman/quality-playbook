A HEAD request with no HEAD route is answered by the GET route, but it was given the static-file handler's roles (none), so a `beforeMatched` role check never saw the GET route's roles and the HEAD got a 200. It now gets the GET route's roles. The test in `TestContextRouteRoles` expects the same 401 for HEAD as for GET.

Reported to @tipsy by email on 20 Oct. Found with the Quality Playbook, an AI code-review tool I maintain; I reproduced it and reviewed the fix myself.
