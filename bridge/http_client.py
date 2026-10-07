"""Bounded official-API requests with raw source capture."""
import json
import time
import ipaddress
import socket
import os
from urllib.parse import urlsplit, urljoin
import requests
from evidence import throttle, trace_response


def _public_url(url):
    parsed = urlsplit(url)
    if parsed.scheme != "https" or parsed.username or parsed.password or not parsed.hostname:
        raise ValueError("Use HTTPS without embedded credentials")
    if parsed.hostname == "localhost" or parsed.hostname.endswith((".localhost", ".local", ".internal", ".home.arpa")):
        raise ValueError("Local endpoints are not supported")
    try:
        literal = ipaddress.ip_address(parsed.hostname)
    except ValueError:
        literal = None
    if literal is not None and not literal.is_global:
        raise ValueError("Private/reserved IP literals are not supported")
    addresses = socket.getaddrinfo(parsed.hostname, parsed.port or 443, type=socket.SOCK_STREAM)
    # Opt in only when a trusted DNS proxy returns synthetic addresses.
    # Private IP literals and local hostnames remain rejected above.
    if any(not ipaddress.ip_address(item[4][0]).is_global for item in addresses) and os.environ.get("BIOMNI_TRUST_DNS_PROXY") != "1":
        raise ValueError("Only public HTTPS endpoints are supported; review your DNS proxy configuration")
    return parsed


def request(url, method="GET", params=None, payload=None, limit_bytes=30_000_000):
    from privacy_ext import enforce_outbound
    enforce_outbound({'url':url,'parameters':params or {},'payload':payload or {}})
    parsed = _public_url(url)
    if parsed.hostname == "eutils.ncbi.nlm.nih.gov":
        throttle("ncbi", 0.36)
    headers = {"User-Agent": "CodexBiomniDirect/2.0", "Accept": "application/json, application/xml, */*"}
    if payload is not None:
        if len(json.dumps(payload)) > 2_000_000:
            raise ValueError("Request payload exceeds 2 MB")
        headers["Content-Type"] = "application/json"
    response = None
    # Environment credentials and netrc are never attached implicitly.
    session = requests.Session()
    session.trust_env = False
    def body(current):
        chunks, size = [], 0
        for chunk in current.iter_content(65536):
            size += len(chunk)
            if size > limit_bytes:
                raise ValueError(f"Response exceeds {limit_bytes} bytes; narrow the query")
            chunks.append(chunk)
        return b"".join(chunks)
    try:
        for attempt in range(3):
            for redirect in range(6):
                response = session.request(method, url, params=params, json=payload, headers=headers, timeout=(10, 40), stream=True, allow_redirects=False)
                if response.status_code not in {301, 302, 303, 307, 308}:
                    break
                destination = urljoin(response.url, response.headers.get("Location", ""))
                status = response.status_code
                response.close()
                _public_url(destination)
                url, params = destination, None
                if status in {301, 302, 303}:
                    method, payload = "GET", None
            else:
                raise ValueError("Too many redirects")
            # Retry only known HTTP failures of read-only GETs. Unknown writes and connection exceptions are never retried.
            if method == "GET" and response.status_code in {429, 500, 502, 503, 504} and attempt < 2:
                trace_response(response, body(response))
                response.close()
                time.sleep(2 * (attempt + 1))
                continue
            raw = body(response)
            source = trace_response(response, raw)
            if response.status_code >= 400:
                raise RuntimeError(f"HTTP {response.status_code}: {response.url}; {raw[:400].decode('utf8', errors='replace')}")
            return raw, source
    finally:
        if response is not None:
            response.close()
        session.close()


def get_json(url, params=None):
    return json.loads(request(url, params=params)[0])


def graphql(url, query, variables=None):
    import re
    if not isinstance(query, str) or re.search(r"\bmutation\b", query, re.I):
        raise ValueError("Only read-only GraphQL queries are supported")
    data = json.loads(request(url, "POST", payload={"query": query, "variables": variables or {}})[0])
    if data.get("errors"):
        return {"success": False, "errors": data["errors"], "data": data.get("data")}
    return {"success": True, "data": data.get("data")}
