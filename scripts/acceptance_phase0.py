import httpx
import sys

with httpx.Client(base_url="http://127.0.0.1:8000", timeout=10) as client:
    if "--database-unavailable" in sys.argv:
        for path, status in [("/api/v1/health/live", 200), ("/api/v1/health/ready", 503), ("/api/v1/demo/event", 503)]:
            response = client.get(path)
            assert response.status_code == status, (path, response.text)
            print(f"PASS outage {path}: {status}")
        raise SystemExit(0)
    for path, status in [("/api/v1/health/live", 200), ("/api/v1/health/ready", 200),
                         ("/api/v1/demo/event", 200), ("/does-not-exist", 404)]:
        response = client.get(path)
        assert response.status_code == status, (path, response.status_code, response.text)
        assert response.headers["x-request-id"]
        body = response.json()
        if path.endswith("/event"):
            assert body["demo"] is True and body["id"] == "demo-event-ml-workshop"
        if status == 404:
            assert body["error"]["request_id"] == response.headers["x-request-id"]
        print(f"PASS {path}: {status}")
print("Phase 0 live API acceptance passed")
