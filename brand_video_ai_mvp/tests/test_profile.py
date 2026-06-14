"""Profile and avatar tests."""

from conftest import auth_headers, login, register

def test_profile_get_update_and_change_password(client):
    token = register(client, "profile@example.com", "profileuser")["access_token"]
    headers = auth_headers(token)

    profile = client.get("/api/profile", headers=headers)
    assert profile.status_code == 200
    assert profile.json()["email"] == "profile@example.com"

    updated = client.put(
        "/api/profile",
        headers=headers,
        json={
            "email": "profile-updated@example.com",
            "username": "profileuser2",
            "full_name": "Profile User",
            "company_name": "Acme",
        },
    )
    assert updated.status_code == 200
    assert updated.json()["email"] == "profile-updated@example.com"
    assert updated.json()["username"] == "profileuser2"
    assert updated.json()["display_name"] == "Profile User"
    assert updated.json()["display_company_name"] == "Acme"
    assert updated.json()["email_verified"] is False

    changed = client.post(
        "/api/profile/change-password",
        headers=headers,
        json={
            "current_password": "Passw0rd!",
            "new_password": "Changed1!",
            "new_password_confirm": "Changed1!",
        },
    )
    assert changed.status_code == 200
    assert client.post("/api/auth/login", json={"email": "profile@example.com", "password": "Changed1!"}).status_code == 401
    assert login(client, "profile-updated@example.com", "Changed1!")["access_token"]


def test_profile_update_rejects_duplicate_email(client):
    first = register(client, "first-profile@example.com", "firstprofile")
    register(client, "second-profile@example.com", "secondprofile")

    response = client.put(
        "/api/profile",
        headers=auth_headers(first["access_token"]),
        json={"email": "second-profile@example.com"},
    )

    assert response.status_code == 400
    assert response.json()["error_code"] == "EMAIL_TAKEN"


def test_profile_avatar_upload_accepts_images_only(client):
    token = register(client, "avatar@example.com", "avataruser")["access_token"]
    headers = auth_headers(token)

    rejected = client.post(
        "/api/profile/avatar",
        headers=headers,
        files={"file": ("avatar.gif", b"gif", "image/gif")},
    )
    assert rejected.status_code == 400
    assert rejected.json()["error_code"] == "INVALID_IMAGE_TYPE"

    uploaded = client.post(
        "/api/profile/avatar",
        headers=headers,
        files={"file": ("avatar.webp", b"webp", "image/webp")},
    )
    assert uploaded.status_code == 200, uploaded.text
    first_url = uploaded.json()["url"]
    assert "/avatar-" in first_url
    assert first_url.endswith(".webp")

    uploaded_again = client.post(
        "/api/profile/avatar",
        headers=headers,
        files={"file": ("avatar.webp", b"new-webp", "image/webp")},
    )
    assert uploaded_again.status_code == 200, uploaded_again.text
    second_url = uploaded_again.json()["url"]
    assert second_url != first_url
    assert "/avatar-" in second_url
    assert second_url.endswith(".webp")

    profile = client.get("/api/profile", headers=headers)
    assert profile.status_code == 200
    assert profile.json()["avatar_url"] == second_url


