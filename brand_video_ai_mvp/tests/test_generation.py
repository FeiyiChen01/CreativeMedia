"""AI generation persistence and video job tests."""

from sqlalchemy import select

from conftest import auth_headers, outline_payload, register

def test_generate_outline_and_prompts_persist(client):
    token = register(client, "gen@example.com", "genuser")["access_token"]
    headers = auth_headers(token)

    questionnaire = client.post(
        "/api/questionnaire",
        headers=headers,
        json={
            "brand_name": "Luna Bloom",
            "brand_description": "Modern jewelry",
            "target_audience": "young professionals",
            "video_style": "专业商务风",
            "additional_info": {"campaign": "spring launch"},
        },
    )
    assert questionnaire.status_code == 200
    questionnaire_id = questionnaire.json()["id"]

    outline_response = client.post("/api/generate-outline", headers=headers, json=outline_payload())
    assert outline_response.status_code == 200, outline_response.text
    outline_data = outline_response.json()
    assert outline_data["generated_outline_id"]
    assert outline_data["generation_job_id"]

    prompt_response = client.post(
        "/api/generate-prompts",
        headers=headers,
        json={
            "questionnaire": outline_payload()["questionnaire"],
            "outline": outline_data["outline"],
            "target_tool": "sora-2",
            "generated_outline_id": outline_data["generated_outline_id"],
        },
    )
    assert prompt_response.status_code == 200, prompt_response.text
    prompt_data = prompt_response.json()
    assert prompt_data["generated_prompt_package_id"]

    assert len(client.get("/api/generated/outlines", headers=headers).json()) == 1
    assert len(client.get("/api/generated/prompts", headers=headers).json()) == 1

    from app.models import ApiUsageLog, GeneratedOutline, GeneratedPromptPackage, GenerationJob

    with client.testing_session_local() as db:  # type: ignore[attr-defined]
        outline = db.get(GeneratedOutline, outline_data["generated_outline_id"])
        package = db.get(GeneratedPromptPackage, prompt_data["generated_prompt_package_id"])
        outline_job = db.get(GenerationJob, outline_data["generation_job_id"])
        prompt_job = db.get(GenerationJob, prompt_data["generation_job_id"])
        usage_rows = db.scalars(select(ApiUsageLog)).all()

    assert outline.questionnaire_id == questionnaire_id
    assert package.questionnaire_id == questionnaire_id
    assert package.outline_id == outline.id
    assert outline_job.output_json and "generated_outline_id" in outline_job.output_json
    assert prompt_job.output_json and "generated_prompt_package_id" in prompt_job.output_json
    assert {row.operation for row in usage_rows} >= {"generate_outline", "generate_prompts"}


def test_video_job_create_and_access_control(client):
    owner_token = register(client, "owner@example.com", "owneruser")["access_token"]
    other_token = register(client, "other@example.com", "otheruser")["access_token"]
    admin_token = register(client, "admin@example.com", "adminuser")["access_token"]

    created = client.post(
        "/api/video-jobs",
        headers=auth_headers(owner_token),
        json={"prompt_en": "A clean product shot", "duration_seconds": 4, "scene_number": 1},
    )
    assert created.status_code == 201, created.text
    job_id = created.json()["job_id"]

    owner_status = client.get(f"/api/video-jobs/{job_id}", headers=auth_headers(owner_token))
    assert owner_status.status_code == 200
    assert owner_status.json()["user_id"]

    assert client.get(f"/api/video-jobs/{job_id}", headers=auth_headers(other_token)).status_code == 403
    assert client.get(f"/api/video-jobs/{job_id}", headers=auth_headers(admin_token)).status_code == 200

    from app.main import run_video_generation_job

    run_video_generation_job(job_id)

    from app.models import ApiUsageLog, VideoAsset

    with client.testing_session_local() as db:  # type: ignore[attr-defined]
        asset = db.scalar(select(VideoAsset).where(VideoAsset.generation_job_id == job_id))
        usage = db.scalar(select(ApiUsageLog).where(ApiUsageLog.generation_job_id == job_id))

    assert asset is not None
    assert asset.storage_backend == "local"
    assert usage is not None
    assert usage.operation == "generate_video"


