# Output, encryption, file loading, and the virtual file system

This file covers the modules that move bytes in and out of a document:
the output sink, the FileSaver bridge, the encryption layer, the dynamic
file loader, and the in-memory virtual file system.

## doc.output

`output(type, options)` is the single sink for finished bytes. Supported
`type` values (per `types/index.d.ts`):

- `undefined` / `'datauristring'` / `'dataurlstring'` — base64 data URI.
- `'arraybuffer'` — raw `ArrayBuffer`.
- `'blob'` — `Blob` with MIME `application/pdf`.
- `'bloburi'` / `'bloburl'` — a `URL` for an object URL.
- `'pdfobjectnewwindow'` / `'pdfjsnewwindow'` / `'dataurlnewwindow'` —
  opens the document in a new window; returns the `Window` handle.
- `'dataurl'` / `'datauri'` — navigates the current location to the URI.

With no arguments `output()` returns the raw PDF string.

## save and FileSaver

`save(filename, options)` builds on `output('blob')`. With
`{returnPromise: true}` it returns a `Promise<void>`; otherwise it
returns the chainable jsPDF instance. `src/libs/FileSaver.js` is a
vendored eligrey FileSaver. The Node bundle replaces this with
`fs.writeFileSync`.

## Encryption

`src/libs/pdfsecurity.js` implements the PDF Standard Security Handler
v1 revision 2 (40-bit RC4). The constructor is
`PDFSecurity(permissions, userPassword, ownerPassword, fileId)`.
Permissions accept `"print"`, `"modify"`, `"copy"`, `"annot-forms"`.
Owner and user passwords are padded to 32 bytes using the specification
padding string and run through MD5 to derive the document encryption
key; RC4 then produces a per-object key when the core writes a stream
or string. Encryption is opted into via
`options.encryption = {userPassword, ownerPassword, userPermissions}`;
`internal.getEncryptor(objectId)` returns a per-object function so
plugins that write their own objects participate automatically.

## Virtual file system

`src/modules/vfs.js` adds an in-memory file table at `internal.vFS`,
exposed via `addFileToVFS(name, content)`, `existsFileInVFS(name)`, and
`getFileFromVFS(name)`. The vFS is the standard delivery mechanism for
TTF fonts: callers fetch the font, place it in the vFS, then call
`addFont(name, family, style)`, which reads the binary back during
embedding. The `fontconverter/` tool emits code that lands new fonts
directly in the vFS at startup.

## File loading

`src/modules/fileloading.js` provides `loadFile(url, sync?, callback?)`.
The browser bundle uses `XMLHttpRequest` with a binary-string
`responseType`; the Node bundle uses `fs.readFileSync` / `fs.readFile`.
`loadImageFile` is aliased to `loadFile`. With `sync` omitted or
`true`, the function returns contents directly; with `sync` `false`, it
invokes `callback(data)` after the load.

## PubSub events and compression

`internal.events` is the lifecycle bus. Topics include `putResources`,
`postPutResources`, `addPage`, `putPage`, `addFonts`, `putFont`,
`putXobjectDict`, `putCatalog`. The PubSub implementation exposes
`subscribe(topic, callback, once?)`, `unsubscribe(token)`,
`publish(topic, ...args)`, `getTopics()`; each subscriber runs with
`this` bound to the jsPDF instance. Content streams then flow through
`src/modules/filters.js`: `FlateEncode` (default when
`options.compress` is true), `ASCIIHexEncode`, `ASCII85Encode`,
`LZWDecode`, `RunLengthEncode`. Compression is delegated to `fflate`.
