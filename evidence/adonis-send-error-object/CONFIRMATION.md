BUG-014: Error objects sent as a response body serialize to "{}" JSON. CONFIRMED.
Claim: response.send(new Error('boom')) -> 200 application/json body "{}"; expected "Error: boom" as text/plain.
Doc: v6-docs_basics_response.md:319 "Regular expressions and error objects are converted to a string by calling the toString method." and :331 "The content type is set to text/plain for everything else."; :328 limits application/json to "arrays and objects".
Mechanism: src/response.ts:307-316 writeBody handles RegExp and Date only; Error falls through to serializeJSON; own props non-enumerable -> {}.
Tests: none for Error or RegExp send. No duplicate.
Pushback: maintainers could fix docs instead; decide toJSON precedence for Error subclasses; severity LOW.
