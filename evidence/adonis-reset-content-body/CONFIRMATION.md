BUG-034: status(205).send(body) writes the body; 205 Reset Content not treated as body-less. CONFIRMED.
Claim: response.status(205).send('some body') sends content-length: 9, content-type and the body.
Spec: RFC 9110 §15.3.6 "Since the 205 status code implies that no additional content will be provided, a server MUST NOT generate content in a 205 response." (also allows Content-Length: 0).
Mechanism: src/response.ts:274-285 strips content only for <200, 204, 304 (comment cites RFC 7230 §3.3.2). resetContent() at src/response.ts:1311 already sends send(null,false).
Tests: none pin a 205 body; tests/response.spec.ts:1427 checks resetContent sets status.
Pushback: framing isn't broken (CL is honest); decide strip CL vs CL:0; check Node doesn't fall back to chunked on keep-alive.
