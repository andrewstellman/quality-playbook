# HTTPX Documentation Collection

This directory contains comprehensive documentation for the HTTPX HTTP client library, gathered from official sources, HTTP RFCs, GitHub discussions, and technical articles.

## Purpose

This documentation collection is designed to support **specification auditing** - comparing actual code behavior against documented intent and standards. It provides:

1. **Official behavioral specifications** from HTTPX documentation
2. **HTTP protocol requirements** from RFC specifications
3. **Design decision rationale** from GitHub discussions
4. **Technical deep dives** into implementation details
5. **Known issues and edge cases** documented by users and maintainers

## Quick Navigation

### Start Here
- **INDEX.md** - Comprehensive index of all documents with key behavioral specs
- **README.md** - This file

### Core HTTPX Features
1. **01_OFFICIAL_DOCS_OVERVIEW.md** - Project overview and scope
2. **02_QUICKSTART_AND_BASIC_API.md** - Basic API and usage
3. **03_ASYNC_SUPPORT.md** - Async/await programming
4. **04_TIMEOUTS.md** - Timeout configuration and behavior
5. **05_CONNECTION_POOLING_AND_CLIENTS.md** - Client configuration
6. **06_TRANSPORT_API.md** - Low-level transport interface
7. **07_AUTHENTICATION.md** - Auth mechanisms
8. **08_HTTP2_SUPPORT.md** - HTTP/2 protocol support
9. **09_PROXIES_AND_SSL.md** - Proxies and SSL/TLS
10. **10_REQUESTS_COMPATIBILITY.md** - Requests library differences
11. **11_EXCEPTIONS_AND_ERROR_HANDLING.md** - Exception types
12. **12_ENVIRONMENT_VARIABLES_AND_LOGGING.md** - Environment and logging

### HTTP Standards and Specifications
- **13_HTTP_SPECIFICATIONS_RFC7230_7235.md** - HTTP/1.1 (RFC 7230-7235)
- **14_HTTP2_SPECIFICATIONS_RFC9113.md** - HTTP/2 (RFC 9113)
- **15_COOKIES_RFC6265.md** - Cookies (RFC 6265)

### Design and Architecture
- **16_GITHUB_DESIGN_DECISIONS.md** - Design decisions from GitHub
- **17_TECHNICAL_ARTICLES_AND_DESIGN.md** - Technical deep dives

## Using This Documentation

### For Auditing Specific Features

1. Find the relevant document in the list above
2. Look for "CRITICAL BEHAVIORS" sections
3. Check "Behavioral Specifications" for exact requirements
4. Cross-reference RFC specifications if protocol-level
5. Review "Known Issues" for edge cases

### For Finding Bugs

1. Identify the feature area (e.g., timeouts, redirects, cookies)
2. Read the comprehensive feature document
3. Check the "Spec Auditor Focus" section for what to verify
4. Look at "Known Issues" for similar problems
5. Cross-reference RFC specifications for protocol requirements

### For Understanding Design Philosophy

Read these documents in order:
1. 01_OFFICIAL_DOCS_OVERVIEW.md
2. 16_GITHUB_DESIGN_DECISIONS.md
3. 17_TECHNICAL_ARTICLES_AND_DESIGN.md

## Key Behavioral Differences from Requests

HTTPX intentionally differs from the Requests library in several important ways:

| Feature | Requests | HTTPX |
|---------|----------|-------|
| Default timeout | None (can hang forever) | 5 seconds |
| Redirect following | Yes, by default | No, requires follow_redirects=True |
| Exception for all non-2xx | No (only 4xx/5xx) | Yes (1xx, 3xx, 4xx, 5xx all raise) |
| GET with body | Allowed | Not allowed |
| File upload mode | Text or binary | Binary mode required |
| Character encoding | Latin-1 | UTF-8 |
| HTTP/2 support | No | Yes |

## Critical Specifications to Verify

When auditing HTTPX code, prioritize these behaviors:

### Must Always Verify
1. **Default timeout is 5 seconds** (not disabled, not None)
2. **HTTPStatusError raised for ALL non-2xx codes** (including 3xx)
3. **GET, DELETE, HEAD, OPTIONS cannot have bodies** (enforced via API)
4. **Authorization header stripped on cross-domain redirects** (security critical)
5. **Connection pooling is transparent** (automatic reuse, single client instance)
6. **HTTP/2 uses single connection per origin** (RFC 9113 requirement)
7. **SSL verification enabled by default** (security critical)

### RFC Compliance Areas
1. **Content-Length/Transfer-Encoding** - Mutual exclusivity required (RFC 7230)
2. **Cookie domain/path matching** - Three conditions per RFC 6265
3. **HTTP/2 connection preface** - Exact 24-byte sequence (RFC 9113)
4. **HTTP/2 frame format** - 9-byte header, correct frame types (RFC 9113)
5. **Persistent connections** - Default in HTTP/1.1 (RFC 7230)

## Document Statistics

- **Total files:** 18 markdown documents
- **Total lines:** ~3,800 lines of documentation
- **Coverage areas:** 12 major feature areas + 3 RFC specifications + 2 design/architecture docs
- **Specificity:** High-level overviews + detailed behavioral specifications + RFC-level requirements

## Sources

This documentation was gathered from:

1. **Official HTTPX Documentation**
   - https://www.python-httpx.org/
   - All major feature pages and guides

2. **IETF RFC Specifications**
   - RFC 7230-7235 (HTTP/1.1)
   - RFC 9113 (HTTP/2)
   - RFC 6265 (Cookies)
   - RFC 9110 (HTTP Semantics - current)

3. **GitHub encode/httpx**
   - Discussions about design decisions
   - Known issues and edge cases
   - Release notes and version history

4. **Technical Articles**
   - Comparisons with Requests and AIOHTTP
   - HTTPCore architecture documentation
   - Design philosophy articles

## Using for Different Roles

### Specification Auditor
1. Start with INDEX.md for behavioral overview
2. Read specific feature documents
3. Check RFC specifications
4. Cross-reference GitHub discussions
5. Focus on "CRITICAL BEHAVIORS" and "Spec Auditor Focus" sections

### Code Reviewer
1. Read relevant feature document
2. Check "Behavioral Specifications" section
3. Verify against RFC if applicable
4. Look for "Known Issues" in the feature area
5. Use "Spec Auditor Focus" for checklist items

### Bug Investigator
1. Identify feature area
2. Read comprehensive feature document
3. Check "Known Issues" section
4. Review GitHub discussions
5. Cross-reference RFC specifications
6. Look for similar reported bugs

### New Developer
1. Start with 01_OFFICIAL_DOCS_OVERVIEW.md
2. Read 02_QUICKSTART_AND_BASIC_API.md
3. Understand design philosophy (17_TECHNICAL_ARTICLES_AND_DESIGN.md)
4. Deep dive into relevant features as needed
5. Always check RFC specifications for protocol requirements

## Document Format

Each document follows a consistent structure:

- **Source and Date** - Where information came from
- **Overview** - High-level explanation
- **Key Topics** - Major areas covered
- **Behavioral Specifications** - Exact required behavior
- **CRITICAL BEHAVIORS** - Must-verify items
- **Known Issues** - Edge cases and problems
- **Spec Auditor Focus** - What to verify in code
- **Important Notes** - Security or other considerations

## Contributing to This Documentation

When adding new information:

1. Identify the relevant document (or create new if needed)
2. Add content to appropriate section
3. Include source URL and access date
4. Update INDEX.md with changes
5. Maintain consistent formatting

## Last Updated

April 2026

---

For detailed specifications and behavioral requirements, see INDEX.md
