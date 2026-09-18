def test_register_and_login(client):
    # 1. Register a new user
    reg_res = client.post(
        "/api/v1/auth/register",
        json={
            "email": "candidate@example.com",
            "password": "Password123!",
            "full_name": "Software Engineer Candidate"
        }
    )
    assert reg_res.status_code == 201
    user_data = reg_res.json()
    assert user_data["email"] == "candidate@example.com"
    assert "id" in user_data

    # 2. Login with valid credentials
    login_res = client.post(
        "/api/v1/auth/login",
        data={
            "username": "candidate@example.com",
            "password": "Password123!"
        }
    )
    assert login_res.status_code == 200
    token_data = login_res.json()
    assert "access_token" in token_data
    assert token_data["token_type"] == "bearer"

    # 3. Test /me endpoint with Bearer token
    headers = {"Authorization": f"Bearer {token_data['access_token']}"}
    me_res = client.get("/api/v1/auth/me", headers=headers)
    assert me_res.status_code == 200
    assert me_res.json()["email"] == "candidate@example.com"


def test_login_invalid_password(client):
    res = client.post(
        "/api/v1/auth/login",
        data={
            "username": "candidate@example.com",
            "password": "WrongPassword!"
        }
    )
    assert res.status_code == 401
