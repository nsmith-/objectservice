from fastapi.testclient import TestClient


def test_crud_item(client: TestClient) -> None:
    data = {
        "id": 1,
        "type": "blah",
    }
    response = client.post("/items", json=data)
    assert response.status_code == 200
    content = response.json()
    assert content["id"] == data["id"]
    assert content["type"] == data["type"]
    assert "create_date" in content
    expected_create_date = content["create_date"]

    response = client.get("/items/1")
    assert response.status_code == 200
    content = response.json()
    assert content["id"] == data["id"]
    assert content["type"] == data["type"]
    assert content["create_date"] == expected_create_date

    response = client.get("/items/2")
    assert response.status_code == 404

    # TODO: update
    # TODO: delete
