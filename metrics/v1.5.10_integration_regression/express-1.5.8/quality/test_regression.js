'use strict'

/*
 * Regression tests for bugs confirmed in Phase 3 code review.
 * See quality/BUGS.md. Each test asserts the DESIRED CORRECT behavior and is
 * marked it.skip("BUG-NNN: ...") until quality/patches/BUG-NNN-fix.patch lands;
 * the skip is the earliest syntactic guard for Mocha (per references/review_protocols.md).
 *
 * Run from the project root with the project's mocha. This file lives one level
 * below test/, so express is required as '../..'.
 */

var assert = require('node:assert')
var express = require('../..')
var request = require('supertest')

describe('quality regression (Phase 3)', function () {

  // BUG-001 — lib/request.js:309-314
  it.skip("BUG-001: req.protocol ignores an empty leading X-Forwarded-Proto element — unskip after applying quality/patches/BUG-001-fix.patch", function (done) {
    var app = express()
    app.enable('trust proxy')
    app.use(function (req, res) {
      res.json({ protocol: req.protocol, secure: req.secure })
    })
    request(app)
      .get('/')
      .set('X-Forwarded-Proto', ', https')
      .expect(200)
      .end(function (err, res) {
        if (err) return done(err)
        // Desired: the first NON-EMPTY token wins → https, secure true.
        assert.strictEqual(res.body.protocol, 'https')
        assert.strictEqual(res.body.secure, true)
        done()
      })
  })

  // BUG-002 — lib/response.js:759-766
  it.skip("BUG-002: res.cookie sub-second maxAge serializes Max-Age=0 — unskip after applying quality/patches/BUG-002-fix.patch", function (done) {
    var app = express()
    app.use(function (req, res) {
      res.cookie('flash', '1', { maxAge: 500 }).end()
    })
    request(app)
      .get('/')
      .expect(200)
      .end(function (err, res) {
        if (err) return done(err)
        var setCookie = String(res.headers['set-cookie'])
        // Desired: a future-Expires cookie must not also carry Max-Age=0.
        assert.ok(!/Max-Age=0(\b|;|$)/.test(setCookie),
          'Set-Cookie must not contain Max-Age=0 for a future Expires: ' + setCookie)
        done()
      })
  })

  // BUG-003 — lib/response.js:841,846-847
  it.skip("BUG-003: res.redirect emits literal 'undefined' for an unassigned in-range status — unskip after applying quality/patches/BUG-003-fix.patch", function (done) {
    var app = express()
    app.use(function (req, res) {
      res.redirect(310, '/destination')
    })
    request(app)
      .get('/')
      .set('Accept', 'text/plain')
      .expect(310)
      .end(function (err, res) {
        if (err) return done(err)
        // Desired: body is human-readable, never the literal "undefined".
        assert.ok(!/undefined/.test(res.text),
          'redirect body must not contain the literal "undefined": ' + res.text)
        done()
      })
  })

  // BUG-004 — lib/response.js:137-143 vs :150-153 (parity REQ-006)
  it.skip("BUG-004: res.send charset differs between string and Buffer bodies — unskip after applying quality/patches/BUG-004-fix.patch", function (done) {
    var stringType
    var bufferType

    var appString = express()
    appString.use(function (req, res) {
      res.set('Content-Type', 'text/plain; charset=iso-8859-1')
      res.send('plain string body')
    })

    request(appString)
      .get('/')
      .expect(200)
      .end(function (err, res) {
        if (err) return done(err)
        stringType = res.headers['content-type']

        var appBuffer = express()
        appBuffer.use(function (req, res) {
          res.set('Content-Type', 'text/plain; charset=iso-8859-1')
          res.send(Buffer.from('plain buffer body'))
        })

        request(appBuffer)
          .get('/')
          .expect(200)
          .end(function (err2, res2) {
            if (err2) return done(err2)
            bufferType = res2.headers['content-type']
            // Desired: string-body and Buffer-body responses advertise the same
            // charset for the identical pre-set Content-Type.
            assert.strictEqual(stringType, bufferType,
              'string vs Buffer send must advertise the same charset: ' +
              stringType + ' !== ' + bufferType)
            done()
          })
      })
  })

  // BUG-005 — lib/utils.js:89-120
  it.skip("BUG-005: acceptParams splits quoted ';' and does not clamp q — unskip after applying quality/patches/BUG-005-fix.patch", function () {
    // normalizeType is the public-ish entry that drives acceptParams.
    var utils = require('../../lib/utils')
    var parsed = utils.normalizeType('text/html;x="a;b";q=0.5')
    // Desired: quoted ';' is not split mid-value; q parses to 0.5.
    assert.strictEqual(parsed.params.x, 'a;b',
      'quoted value must not be split at the inner ";": got ' + JSON.stringify(parsed.params.x))
    assert.strictEqual(parsed.quality, 0.5)

    // Desired: out-of-range q is clamped to [0,1].
    var clamped = utils.normalizeType('text/html;q=5')
    assert.ok(clamped.quality <= 1 && clamped.quality >= 0,
      'q must be clamped to [0,1]: got ' + clamped.quality)
  })

  // BUG-006 — lib/request.js:424-427,444-458,383-394 (parity REQ-007)
  it.skip("BUG-006: req.host/hostname/subdomains undefined for trusted leading-comma X-Forwarded-Host — unskip after applying quality/patches/BUG-006-fix.patch", function (done) {
    var app = express()
    app.enable('trust proxy')
    app.set('subdomain offset', 2)
    app.use(function (req, res) {
      res.json({
        host: req.host,
        hostname: req.hostname,
        subdomains: req.subdomains
      })
    })
    request(app)
      .get('/')
      .set('X-Forwarded-Host', ',sub.example.com')
      .expect(200)
      .end(function (err, res) {
        if (err) return done(err)
        // Desired: the present authority resolves; never undefined/[].
        assert.strictEqual(res.body.hostname, 'sub.example.com')
        assert.deepStrictEqual(res.body.subdomains, ['sub'])
        done()
      })
  })

})
