import httpx
import pytest

from src.server.medieval.app import create_app


@pytest.mark.asyncio
async def test_observatory_is_one_consistent_published_snapshot(tmp_path):
    app = create_app(save_dir=lambda: tmp_path)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver") as client:
        assert (await client.get("/api/v2/query/observatory")).status_code == 409
        await client.post("/api/v2/command/create", json={"seed": 73})
        await client.post("/api/v2/command/step", json={})
        reply = await client.get("/api/v2/query/observatory")
        assert reply.status_code == 200
        body = reply.json()
        data = body["data"]
        assert data["status"]["day"] == data["world"]["day"] == 30
        assert len(data["society"]["characters"]) == 12
        assert data["map"]["settlements"] == data["society"]["settlements"]
        assert sum(g["count"] for g in data["society"]["population_groups"]) == data["world"]["population"] == 10900
        assert all(m["updated_day"] == 30 for m in data["economy"]["markets"])
        assert len(data["economy"]["payrolls"]) == 4
        assert all(p["day"] == 30 for p in data["economy"]["payrolls"])
        assert sum(p["gross"] for p in data["economy"]["payrolls"]) > 0
        assert len(data["governance"]["tax_policies"]) == 3
        assert body["revision"] == (await client.get("/api/v2/query/status")).json()["revision"]
        assert len(data["governance"]["objectives"]) == 15
        assert len(data["governance"]["plans"]) == 15
        assert len(data["economy"]["expansions"]) == 2
        assert all(p["stage"] == "waiting" for p in data["economy"]["expansions"])
        food_goals = {o["id"] for o in data["governance"]["objectives"] if o["kind"] == "maintain_food_reserve"}
        assert all(p["stage"] == "satisfied" for p in data["governance"]["plans"] if p["objective_id"] in food_goals)
        assert any(p["stage"] == "await_delivery" for p in data["governance"]["plans"] if p["objective_id"] not in food_goals)
        governance = await client.get("/api/v2/query/governance")
        assert governance.status_code == 200
        assert governance.json()["data"] == data["governance"]
        research = await client.get("/api/v2/query/research")
        assert research.status_code == 200
        assert research.json()["data"] == data["research"]
        assert {p["technology_id"] for p in data["research"]["projects"]} == {"irrigation", "metallurgy"}
        assert all(p["completed_units"] == 0 for p in data["research"]["projects"])
        assert data["research"]["knowledge"] == []


@pytest.mark.asyncio
async def test_serves_only_medieval_bundle_and_does_not_mask_missing_api(tmp_path):
    frontend = tmp_path / "frontend"
    frontend.mkdir()
    app = create_app(save_dir=lambda: tmp_path / "saves", frontend_dir=frontend)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver") as client:
        assert (await client.get("/")).status_code == 503
        (frontend / "index.html").write_text("<html>old cultivation app</html>", encoding="utf-8")
        assert (await client.get("/")).status_code == 503
        (frontend / "index.html").write_text('<html><meta name="mws-product" content="medieval-world-simulator">Atlas</html>', encoding="utf-8")
        assets = frontend / "web_static"
        assets.mkdir()
        (assets / "app.js").write_text("const medieval = true;", encoding="utf-8")
        response = await client.get("/")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
        assert (await client.get("/web_static/app.js")).text == "const medieval = true;"
        assert (await client.get("/api/v2/query/missing")).status_code == 404
        assert (await client.get("/web_static/missing.js")).status_code == 404
        assert (await client.get("/web_static/%2e%2e/index.html")).status_code == 404
