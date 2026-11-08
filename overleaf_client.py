import base64
import http.cookiejar
import io
import json
import mimetypes
import os
import re
import socket
import ssl
import sys
import time
import urllib.request
import uuid
import zipfile
from pathlib import Path

PROJECT_ID = "6af054a70e2efc15383d3c22"
ROOT_DIR = Path(__file__).resolve().parent
COOKIE_FILE = ROOT_DIR / ".olauth"

IGNORE_NAMES = {
    ".git",
    ".github",
    ".gitignore",
    ".olauth",
    "overleaf_client.py",
    "sync.ps1",
    "__pycache__",
    "overleaf_downloaded.pdf",
}


def get_cookie() -> str:
    if not COOKIE_FILE.exists():
        raise RuntimeError("No se encontro .olauth con la cookie overleaf_session2")
    val = COOKIE_FILE.read_text(encoding="utf-8").strip()
    return val.removeprefix("overleaf_session2=")


def get_session_and_tree():
    cookie_val = get_cookie()
    cj = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
    opener.addheaders = [
        ("Cookie", f"overleaf_session2={cookie_val}"),
        ("User-Agent", "Mozilla/5.0"),
    ]

    html = opener.open(f"https://www.overleaf.com/project/{PROJECT_ID}").read().decode("utf-8")
    m = re.search(r'<meta\s+name="ol-csrfToken"\s+content="([^"]+)"', html)
    if not m:
        raise RuntimeError("Cookie invalida o caducada (no se encontro ol-csrfToken)")
    csrf = m.group(1)

    cookies_dict = {c.name: c.value for c in cj}
    cookies_dict["overleaf_session2"] = cookie_val
    cookie_header = "; ".join(f"{k}={v}" for k, v in cookies_dict.items())

    t = int(time.time() * 1000)
    hs_resp = opener.open(f"https://www.overleaf.com/socket.io/1/?projectId={PROJECT_ID}&t={t}")
    for c in cj:
        cookies_dict[c.name] = c.value
    cookie_header = "; ".join(f"{k}={v}" for k, v in cookies_dict.items())
    sid = hs_resp.read().decode("utf-8").split(":")[0]

    ctx = ssl.create_default_context()
    ssl_sock = ctx.wrap_socket(
        socket.create_connection(("www.overleaf.com", 443)),
        server_hostname="www.overleaf.com",
    )
    ws_key = base64.b64encode(os.urandom(16)).decode("ascii")
    upgrade_req = (
        f"GET /socket.io/1/websocket/{sid}?projectId={PROJECT_ID} HTTP/1.1\r\n"
        f"Host: www.overleaf.com\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
        f"Sec-WebSocket-Key: {ws_key}\r\nSec-WebSocket-Version: 13\r\n"
        f"Origin: https://www.overleaf.com\r\nCookie: {cookie_header}\r\nUser-Agent: Mozilla/5.0\r\n\r\n"
    )
    ssl_sock.sendall(upgrade_req.encode("utf-8"))
    header_resp = b""
    while not header_resp.endswith(b"\r\n\r\n"):
        ch = ssl_sock.recv(1)
        if not ch:
            break
        header_resp += ch

    def ws_recv(s):
        b1, b2 = s.recv(2)
        length = b2 & 0x7F
        if length == 126:
            length = int.from_bytes(s.recv(2), "big")
        elif length == 127:
            length = int.from_bytes(s.recv(8), "big")
        data = b""
        while len(data) < length:
            data += s.recv(length - len(data))
        return data.decode("utf-8", errors="replace")

    msg = ""
    for _ in range(5):
        frame = ws_recv(ssl_sock)
        if "joinProjectResponse" in frame:
            msg = frame
            break
    ssl_sock.close()

    payload = json.loads(msg.split("5:::", 1)[1])
    root_folder = payload["args"][0]["project"]["rootFolder"][0]
    return cookie_header, csrf, root_folder


def ensure_folder(cookie_header: str, csrf: str, root_folder: dict, rel_parts: list[str]) -> str:
    curr = root_folder
    for part in rel_parts:
        found = None
        for f in curr.get("folders", []):
            if f["name"] == part:
                found = f
                break
        if found is None:
            body = json.dumps({"parent_folder_id": curr["_id"], "name": part}).encode("utf-8")
            req = urllib.request.Request(
                f"https://www.overleaf.com/project/{PROJECT_ID}/folder",
                data=body,
                headers={
                    "Cookie": cookie_header,
                    "User-Agent": "Mozilla/5.0",
                    "Content-Type": "application/json",
                    "X-Csrf-Token": csrf,
                },
            )
            new_f = json.loads(urllib.request.urlopen(req).read().decode("utf-8"))
            new_f.setdefault("folders", [])
            curr.setdefault("folders", []).append(new_f)
            curr = new_f
        else:
            curr = found
    return curr["_id"]


def upload_file(cookie_header: str, csrf: str, root_folder: dict, local_path: Path):
    rel = local_path.relative_to(ROOT_DIR)
    folder_id = ensure_folder(cookie_header, csrf, root_folder, list(rel.parts[:-1]))
    fname = rel.name
    content = local_path.read_bytes()
    mime = mimetypes.guess_type(fname)[0] or "application/octet-stream"
    boundary = "----WebKitFormBoundary" + uuid.uuid4().hex

    parts = [
        f'--{boundary}\r\nContent-Disposition: form-data; name="name"\r\n\r\n{fname}\r\n'.encode("utf-8"),
        f'--{boundary}\r\nContent-Disposition: form-data; name="qqfile"; filename="{fname}"\r\nContent-Type: {mime}\r\n\r\n'.encode("utf-8")
        + content
        + f"\r\n--{boundary}--\r\n".encode("utf-8"),
    ]
    body = b"".join(parts)

    req = urllib.request.Request(
        f"https://www.overleaf.com/project/{PROJECT_ID}/upload?folder_id={folder_id}",
        data=body,
        headers={
            "Cookie": cookie_header,
            "User-Agent": "Mozilla/5.0",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "X-Csrf-Token": csrf,
        },
    )
    resp = json.loads(urllib.request.urlopen(req).read().decode("utf-8"))
    if not resp.get("success"):
        raise RuntimeError(f"Error al subir {rel}: {resp}")
    print(f"[OK] Subido a Overleaf: {rel.as_posix()}")


def pull():
    cookie_val = get_cookie()
    req = urllib.request.Request(
        f"https://www.overleaf.com/project/{PROJECT_ID}/download/zip",
        headers={
            "Cookie": f"overleaf_session2={cookie_val}",
            "User-Agent": "Mozilla/5.0",
        },
    )
    data = urllib.request.urlopen(req).read()
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        zf.extractall(ROOT_DIR)
    print("[OK] Descargado y actualizado desde Overleaf.")


def push(targets: list[str]):
    cookie_header, csrf, root_folder = get_session_and_tree()
    if targets:
        files = [ (ROOT_DIR / t).resolve() for t in targets ]
    else:
        files = []
        for p in ROOT_DIR.rglob("*"):
            if p.is_file() and not any(part in IGNORE_NAMES for part in p.relative_to(ROOT_DIR).parts) and not p.name.endswith(('.docx', '.pdf')):
                files.append(p)
    for f in files:
        upload_file(cookie_header, csrf, root_folder, f)


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "pull"
    if cmd == "pull":
        pull()
    elif cmd == "push":
        push(sys.argv[2:])
    else:
        print("Uso: python overleaf_client.py [pull | push [archivos...]]")
        sys.exit(1)
