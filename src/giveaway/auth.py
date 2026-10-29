"""로컬 PC에서 1회 실행해 YouTube refresh token을 발급받는다 (loopback OAuth)."""
import http.server
import threading
import urllib.parse
import webbrowser

import httpx

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
SCOPE = "https://www.googleapis.com/auth/youtube.force-ssl"
PORT = 8765


def run(client_id: str, client_secret: str) -> str:
    redirect = f"http://127.0.0.1:{PORT}"
    result: dict = {}
    done = threading.Event()

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            result["code"] = (q.get("code") or [""])[0]
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write("인증 완료. 터미널로 돌아가세요.".encode())
            done.set()

        def log_message(self, *a):
            pass

    server = http.server.HTTPServer(("127.0.0.1", PORT), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    url = AUTH_URL + "?" + urllib.parse.urlencode({
        "client_id": client_id, "redirect_uri": redirect, "response_type": "code",
        "scope": SCOPE, "access_type": "offline", "prompt": "consent"})
    print("브라우저에서 아래 주소로 로그인하세요 (자동으로 열리지 않으면 복사):\n" + url)
    webbrowser.open(url)
    done.wait(timeout=300)
    server.shutdown()
    if not result.get("code"):
        raise SystemExit("인증 코드를 받지 못했습니다")
    resp = httpx.post(TOKEN_URL, data={
        "code": result["code"], "client_id": client_id, "client_secret": client_secret,
        "redirect_uri": redirect, "grant_type": "authorization_code"})
    resp.raise_for_status()
    token = resp.json().get("refresh_token")
    if not token:
        raise SystemExit("refresh_token이 없습니다. Google 계정의 앱 접근 권한을 삭제한 뒤 다시 시도하세요")
    return token
