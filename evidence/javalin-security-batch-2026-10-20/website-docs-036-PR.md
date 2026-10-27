`beforeMatched` does not run for WebSocket upgrade requests, so a role check written as the access-management section shows does not apply to `ws` endpoints. This adds a note there with a short `wsBeforeUpgrade` example that checks `ctx.routeRoles()`.

As discussed with @tipsy by email. Found with the Quality Playbook, an AI code-review tool I maintain; Claude wrote the change, and I reviewed it.
