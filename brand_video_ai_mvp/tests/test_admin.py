"""Admin API tests."""

from conftest import auth_headers, register

def test_admin_protection_metrics_and_system_prompts(client):
    user_token = register(client, "normal@example.com", "normaluser")["access_token"]
    admin_token = register(client, "admin@example.com", "adminuser")["access_token"]

    assert client.get("/api/admin/metrics", headers=auth_headers(user_token)).status_code == 403
    assert client.get("/api/system-prompts", headers=auth_headers(user_token)).status_code == 403

    metrics = client.get("/api/admin/metrics", headers=auth_headers(admin_token))
    assert metrics.status_code == 200
    assert metrics.json()["total_users"] == 2
    assert client.get("/api/system-prompts", headers=auth_headers(admin_token)).status_code == 200


def test_admin_user_actions_log_changes(client):
    user = register(client, "managed@example.com", "manageduser")
    admin = register(client, "admin@example.com", "adminuser")
    admin_headers = auth_headers(admin["access_token"])

    updated = client.patch(
        f"/api/admin/users/{user['user']['id']}",
        headers=admin_headers,
        json={"is_active": False, "role": "admin", "email_verified": True},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["is_active"] is False
    assert updated.json()["role"] == "admin"
    assert updated.json()["email_verified"] is True

    logs = client.get("/api/admin/action-logs", headers=admin_headers)
    assert logs.status_code == 200
    assert any(log["action"] == "update_user" and log["target_id"] == str(user["user"]["id"]) for log in logs.json())


