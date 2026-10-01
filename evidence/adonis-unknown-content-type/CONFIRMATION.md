BUG-028: response.type() writes "Content-Type: false" for unknown types; extension-less/unknown-extension downloads get it. CONFIRMED.
Claim: response.download('/path/LICENSE') or 'data.unknownext', or response.type('.nope').send('x') -> header `content-type: false`. Expected: downloads fall back to application/octet-stream; type() with an unresolvable value sets no header (or octet-stream).
Mechanism: src/response.ts:766-771 type() does this.header('Content-Type', mime.contentType(type)); mime-types returns false; header() skips only null/undefined; #castHeaderValue stringifies to "false". streamFileForDownload calls this.type(extname(filePath)) at line 504.
Doc: v6-docs_basics_response.md:90 "the download method automatically sets the content-type and the content-length headers." RFC 9110 §8.3 media-type is type/subtype.
Tests: none for unknown/empty extensions; type() test uses 'plain/text' (must keep working: contentType accepts any string with a slash).
Pushback: which fallback where (no header vs octet-stream); state it explicitly.
