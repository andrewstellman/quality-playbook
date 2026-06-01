# HTTPX Official Documentation - Overview

**Source:** https://www.python-httpx.org/
**Accessed:** April 2026

## What is HTTPX?

HTTPX is a modern HTTP client library for Python 3. According to the documentation, it's described as "A next-generation HTTP client for Python." The library provides both synchronous and asynchronous interfaces while supporting HTTP/1.1 and HTTP/2 protocols.

## Key Features

The library builds upon the familiar patterns established by the popular `requests` library while adding several enhancements:

- **Dual API Support**: Offers standard synchronous operations with optional async capabilities for developers needing concurrent requests
- **Protocol Support**: Handles both HTTP/1.1 and the modern HTTP/2 standard
- **Direct Application Integration**: Can send requests directly to WSGI or ASGI applications without network overhead
- **Strict Timeouts**: Implements mandatory timeout configurations across all operations
- **Type Safety**: Fully annotated with Python type hints
- **Comprehensive Testing**: Maintains 100% test coverage

## Standard Capabilities

Beyond modern enhancements, HTTPX includes established HTTP features such as:
- Connection pooling
- Cookie persistence
- SSL verification
- Authentication methods
- Proxy support
- Compressed response handling
- Multipart file uploads

## Installation & Requirements

Installation is straightforward via pip: `pip install httpx`

The library requires Python 3.9 or later. Optional dependencies are available for:
- HTTP/2 support (pip install httpx[http2])
- SOCKS proxies (pip install httpx[socks])
- Advanced compression formats (Brotli, Zstandard)

## Project Statistics

- **Repository**: 1,523 commits on the master branch
- **Community**: 15.2k stars, 1.1k forks
- **License**: BSD-3-Clause
- **Code**: 99.5% Python

## Core Dependencies

- httpcore
- certifi
- idna
- sniffio

## Official Documentation Resources

- **Main site**: https://www.python-httpx.org/
- **QuickStart guide**: https://www.python-httpx.org/quickstart/
- **PyPI package page**: https://pypi.org/project/httpx/
- **GitHub repository**: https://github.com/encode/httpx/
