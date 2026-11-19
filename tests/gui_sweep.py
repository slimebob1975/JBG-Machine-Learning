"""300j: a systematic walk through the web GUI (helper for the native sweep test).

Visits every tab and view, in Swedish and English, with and without an open
project, and returns the findings: server errors, untranslated texts on
Swedish pages, and internal links that lead nowhere."""
import re
from html import unescape

from JBGWebUI import LANGUAGE_COOKIE, _load_catalog

LINK = re.compile(r'href="(/ui[^"#]*)"')


def visible_text(page: str) -> str:
    # The run log (<pre>) is the engine's own output, not translated on purpose.
    page = re.sub(r"<(script|style|pre)[^>]*>.*?</\1>", " ", page, flags=re.S)
    page = re.sub(r"<[^>]+>", "\n", page)
    return unescape(page)


def untranslated(text: str, catalog: dict) -> list:
    """English texts from the catalogue that appear untranslated on a Swedish page."""
    lines = {line.strip() for line in text.splitlines() if line.strip()}
    found = []
    for english, swedish in catalog.items():
        if english == swedish or len(english) < 12 or " " not in english:
            continue
        if english in lines or any(english in line and swedish not in line
                                   for line in lines if len(line) < 400):
            found.append(english)
    return found


def sweep(client, pages, *, open_project=None) -> list:
    catalog = _load_catalog("sv")
    findings, links = [], set()
    for language in ("sv", "en"):
        client.cookies.set(LANGUAGE_COOKIE, language, path="/")
        for path in pages:
            response = client.get(path, follow_redirects=False)
            if response.status_code >= 400:
                findings.append(f"{language} {path}: HTTP {response.status_code}")
                continue
            if response.status_code != 200:
                continue
            page = response.text
            if "Traceback" in page or "Internal Server Error" in page:
                findings.append(f"{language} {path}: error text in page")
            links.update(LINK.findall(page))
            if language == "sv":
                for english in untranslated(visible_text(page), catalog):
                    findings.append(f"sv {path}: untranslated: {english[:80]}")
    client.cookies.set(LANGUAGE_COOKIE, "sv", path="/")
    for link in sorted(links):
        status = client.get(unescape(link), follow_redirects=False).status_code
        if status >= 400:
            findings.append(f"link {link}: HTTP {status}")
    return sorted(set(findings))


def browser_sweep(app, pages, cookies) -> list:
    """300j: the same pages in a real browser (Playwright, when installed):
    script errors and requests that fail. Returns [] without Playwright."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return []
    import socket
    import threading
    import time

    import uvicorn
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.time() + 15
    while not server.started and time.time() < deadline:
        time.sleep(0.05)
    base, findings = f"http://127.0.0.1:{port}", []
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            context = browser.new_context()
            context.add_cookies([{"name": k, "value": v, "url": base} for k, v in cookies.items()])
            page = context.new_page()
            current = {"path": ""}
            page.on("pageerror", lambda error: findings.append(
                f"browser {current['path']}: script error: {str(error)[:120]}"))
            page.on("console", lambda message: findings.append(
                f"browser {current['path']}: console {message.type}: {message.text[:120]}")
                if message.type == "error" else None)
            page.on("response", lambda response: findings.append(
                f"browser {current['path']}: {response.status} {response.url[len(base):][:100]}")
                if response.status >= 400 else None)
            for path in pages:
                current["path"] = path
                page.goto(base + path, wait_until="networkidle")
            browser.close()
    finally:
        server.should_exit = True
        thread.join(timeout=10)
    return sorted(set(findings))
