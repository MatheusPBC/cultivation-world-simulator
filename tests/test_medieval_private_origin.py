import pytest
import httpx

from src.server.medieval.app import create_app


@pytest.mark.parametrize("origin", ["https://vps.tail9afb74.ts.net", "http://100.101.254.17:8123"])
async def test_private_tailnet_origin_is_exact_and_opt_in(monkeypatch, tmp_path, origin):
    monkeypatch.setenv("CWS_OBSERVER_ORIGINS", origin)
    app = create_app(save_dir=lambda: tmp_path)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url=origin) as client:
        assert (await client.get("/api/health")).status_code == 200
        accepted = await client.post("/api/v2/command/pause", json={}, headers={"Origin": origin})
        assert accepted.status_code == 200
        for bad in ("https://evil.example", origin + ".evil.example", "https://other.ts.net", "http://vps.tail9afb74.ts.net"):
            blocked = await client.post("/api/v2/command/pause", json={}, headers={"Origin": bad})
            assert blocked.status_code == 403
        assert (await client.get("/api/health", headers={"Host": "other.ts.net"})).status_code == 400
    monkeypatch.delenv("CWS_OBSERVER_ORIGINS")
    app = create_app(save_dir=lambda: tmp_path)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url=origin) as client:
        assert (await client.get("/api/health")).status_code == 400


@pytest.mark.parametrize("origin", ["http://vps.tail9afb74.ts.net", "http://8.8.8.8", "https://evil.example", "https://*.ts.net", "https://u:p@vps.tail9afb74.ts.net", "https://vps.tail9afb74.ts.net/path"])
def test_private_origin_rejects_non_tailnet_or_non_origin(monkeypatch, tmp_path, origin):
    monkeypatch.setenv("CWS_OBSERVER_ORIGINS", origin)
    with pytest.raises(ValueError, match="private Tailscale"):
        create_app(save_dir=tmp_path)


async def test_both_deployed_private_origins_and_cors(monkeypatch, tmp_path):
    origins = ["http://100.101.254.17:8123", "https://vps.tail9afb74.ts.net"]
    monkeypatch.setenv("CWS_OBSERVER_ORIGINS", ",".join(origins))
    app = create_app(save_dir=lambda: tmp_path)
    for origin in origins:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url=origin) as client:
            assert (await client.post("/api/v2/command/pause", json={}, headers={"Origin": origin})).status_code == 200
            response = await client.options("/api/v2/command/pause", headers={
                "Origin": origin, "Access-Control-Request-Method": "POST"})
            assert response.status_code == 200
            assert response.headers["access-control-allow-origin"] == origin
            blocked = await client.options("/api/v2/command/pause", headers={
                "Origin": "https://evil.example", "Access-Control-Request-Method": "POST"})
            assert blocked.status_code == 400
