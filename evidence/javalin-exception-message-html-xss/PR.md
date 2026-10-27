When the client accepts HTML, `HttpResponseExceptionMapper` serves the exception's message and details as `text/html` without escaping them, so request data put into a message is reflected as HTML. The HTML response is now escaped; plain-text and JSON responses are unchanged. The test in `TestHttpResponseExceptions` checks that `<script>` comes back escaped.

Reported to @tipsy by email on 20 Oct. Found with the Quality Playbook, an AI code-review tool I maintain; I reproduced it and reviewed the fix myself.
