import json

from fastapi.testclient import TestClient


def test_crud_item(client: TestClient, admin_token_headers: dict[str, str]) -> None:
    # TODO: split and check regular user, admin
    item_in = {
        "type": "blah",
    }
    response = client.post("/items", json=item_in)
    assert response.status_code == 401
    response = client.post("/items", json=item_in, headers=admin_token_headers)
    assert response.status_code == 422

    data = {"info": 3}
    item_in["data"] = json.dumps(data)
    response = client.post("/items", json=item_in, headers=admin_token_headers)
    assert response.status_code == 200
    content = response.json()
    assert content["type"] == item_in["type"]
    assert "create_date" in content
    item_id: int = content["id"]
    expected_create_date = content["create_date"]

    response = client.get("/items", params={"limit": 10}, headers=admin_token_headers)
    assert response.status_code == 200
    content = response.json()
    assert 0 < len(content) <= 10

    response = client.get(f"/items/{item_id}")
    assert response.status_code == 401
    response = client.get(f"/items/{item_id}", headers=admin_token_headers)
    assert response.status_code == 200
    content = response.json()
    assert content["id"] == item_id
    assert content["create_date"] == expected_create_date
    assert content["type"] == item_in["type"]
    assert content["data"] == data

    item_in["type"] = "cool"
    response = client.put(
        f"/items/{item_id}", json=item_in, headers=admin_token_headers
    )
    assert response.status_code == 200
    content = response.json()
    assert content["type"] == item_in["type"]
    content = client.get(f"/items/{item_id}", headers=admin_token_headers).json()
    assert content["type"] == item_in["type"]

    response = client.delete(f"/items/{item_id}")
    assert response.status_code == 401
    response = client.delete(f"/items/{item_id}", headers=admin_token_headers)
    assert response.status_code == 200
    response = client.get(f"/items/{item_id}", headers=admin_token_headers)
    assert response.status_code == 404
