from __future__ import annotations

from uuid import uuid4

from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import app


def _random_email() -> str:
    return f'delete_{uuid4().hex[:10]}@example.com'


def test_e2e_account_deletion_removes_user_data() -> None:
    email = _random_email()
    password = 'secret1234'

    with TestClient(app) as client:
        register_resp = client.post(
            '/api/auth/register',
            json={'email': email, 'password': password, 'name': 'Delete User', 'captcha_token': None},
        )
        assert register_resp.status_code == 200, register_resp.text

        sync_db_url = get_settings().sync_database_url().replace('postgresql+psycopg://', 'postgresql://', 1)
        import psycopg

        with psycopg.connect(sync_db_url) as conn:
            with conn.cursor() as cur:
                cur.execute('UPDATE users SET email_verified = true WHERE email = %s', (email,))
            conn.commit()

        login_resp = client.post(
            '/api/auth/login',
            json={'email': email, 'password': password, 'captcha_token': None},
        )
        assert login_resp.status_code == 200, login_resp.text
        auth_token = login_resp.json()['access_token']
        auth_headers = {'Authorization': f'Bearer {auth_token}'}

        wishlist_resp = client.post(
            '/api/wishlists',
            json={'title': 'Delete Flow', 'description': 'test', 'event_date': None},
            headers=auth_headers,
        )
        assert wishlist_resp.status_code == 200, wishlist_resp.text
        share_token = wishlist_resp.json()['share_token']

        delete_resp = client.request(
            'DELETE',
            '/api/auth/me',
            json={'password': password, 'confirm_phrase': 'DELETE'},
            headers=auth_headers,
        )
        assert delete_resp.status_code == 200, delete_resp.text

        me_resp = client.get('/api/auth/me', headers=auth_headers)
        assert me_resp.status_code == 401

        public_resp = client.get(f'/api/public/w/{share_token}')
        assert public_resp.status_code == 404
