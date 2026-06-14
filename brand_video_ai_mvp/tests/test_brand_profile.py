"""Brand Profile API tests."""

from conftest import auth_headers, register

def test_brand_profile_requires_login(client):
    assert client.get("/api/brand-profile").status_code == 401
    assert client.post(
        "/api/brand-profile",
        json={
            "company_name": "No Auth Co",
            "industry": "Retail",
            "brand_description": "No auth",
            "brand_tone": "Friendly",
            "use_logo_in_prompt": False,
        },
    ).status_code == 401


def test_brand_profile_create_update_and_user_scope(client):
    first = register(client, "brand-one@example.com", "brandone")
    second = register(client, "brand-two@example.com", "brandtwo")
    first_headers = auth_headers(first["access_token"])
    second_headers = auth_headers(second["access_token"])

    created = client.post(
        "/api/brand-profile",
        headers=first_headers,
        json={
            "company_name": "Luna Bloom",
            "industry": "Jewelry",
            "brand_description": "Modern sustainable jewelry",
            "brand_tone": "Luxury",
            "use_logo_in_prompt": True,
        },
    )
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["company_name"] == "Luna Bloom"
    assert body["brand_name"] == "Luna Bloom"
    assert body["industry"] == "Jewelry"
    assert body["brand_tone"] == "Luxury"
    assert body["use_logo_in_prompt"] is False

    second_get = client.get("/api/brand-profile", headers=second_headers)
    assert second_get.status_code == 200
    assert second_get.json() is None

    updated = client.put(
        "/api/brand-profile",
        headers=first_headers,
        json={
            "company_name": "Luna Bloom Studio",
            "industry": "Luxury Retail",
            "brand_description": "Premium jewelry and styling",
            "brand_tone": "Professional",
            "use_logo_in_prompt": False,
        },
    )
    assert updated.status_code == 200, updated.text
    updated_body = updated.json()
    assert updated_body["id"] == body["id"]
    assert updated_body["company_name"] == "Luna Bloom Studio"
    assert updated_body["video_style"] == "Professional"

    first_get = client.get("/api/brand-profile", headers=first_headers)
    assert first_get.status_code == 200
    assert first_get.json()["company_name"] == "Luna Bloom Studio"


def test_brand_profile_logo_upload_accepts_images_only_and_enables_logo_prompt(client):
    token = register(client, "logo@example.com", "logouser")["access_token"]
    headers = auth_headers(token)

    created = client.post(
        "/api/brand-profile",
        headers=headers,
        json={
            "company_name": "Logo Co",
            "industry": "Education",
            "brand_description": "Teaches founders",
            "brand_tone": "Educational",
            "use_logo_in_prompt": False,
        },
    )
    assert created.status_code == 201

    rejected = client.post(
        "/api/brand-profile/logo",
        headers=headers,
        files={"file": ("notes.txt", b"hello", "text/plain")},
    )
    assert rejected.status_code == 400
    assert rejected.json()["error_code"] == "INVALID_IMAGE_TYPE"

    uploaded = client.post(
        "/api/brand-profile/logo",
        headers=headers,
        files={"file": ("logo.png", b"\x89PNG\r\n\x1a\nfake", "image/png")},
    )
    assert uploaded.status_code == 200, uploaded.text
    assert "/brand-logo-" in uploaded.json()["logo_url"]
    assert uploaded.json()["logo_url"].endswith(".png")

    updated = client.put(
        "/api/brand-profile",
        headers=headers,
        json={
            "company_name": "Logo Co",
            "industry": "Education",
            "brand_description": "Teaches founders",
            "brand_tone": "Educational",
            "use_logo_in_prompt": True,
        },
    )
    assert updated.status_code == 200
    assert updated.json()["use_logo_in_prompt"] is True


