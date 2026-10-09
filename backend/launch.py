import json
import threading
import webbrowser
from urllib.error import URLError
from urllib.request import urlopen

import uvicorn


def main():
    url = "http://127.0.0.1:8010"
    try:
        with urlopen(url + "/api/health", timeout=1) as response:
            if response.status == 200 and json.load(response).get("application") == "monolit-receivables":
                webbrowser.open(url)
                return
    except (URLError, TimeoutError):
        pass
    timer = threading.Timer(1.5, lambda: webbrowser.open(url))
    timer.daemon = True
    timer.start()
    uvicorn.run("backend.app:app", host="127.0.0.1", port=8010)


if __name__ == "__main__":
    main()
