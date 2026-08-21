from httpx import AsyncClient


async def test_health_is_open_and_reports_a_reachable_database(client: AsyncClient) -> None:
    response = await client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
