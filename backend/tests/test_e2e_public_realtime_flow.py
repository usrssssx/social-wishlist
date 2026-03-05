from __future__ import annotations

from uuid import uuid4

from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import app


def _random_email() -> str:
    return f'e2e_{uuid4().hex[:10]}@example.com'


def test_e2e_public_contribution_and_reserve_realtime() -> None:
    email = _random_email()
    password = 'secret1234'

    with TestClient(app) as client:
        register_resp = client.post(
            '/api/auth/register',
            json={'email': email, 'password': password, 'name': 'E2E User', 'captcha_token': None},
        )
        assert register_resp.status_code == 200, register_resp.text

        # Mark user as verified directly for E2E smoke (token raw value is not persisted by design).
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
            json={'title': 'E2E Wishlist', 'description': 'flow', 'event_date': None},
            headers=auth_headers,
        )
        assert wishlist_resp.status_code == 200, wishlist_resp.text
        wishlist = wishlist_resp.json()
        share_token = wishlist['share_token']
        wishlist_id = wishlist['id']

        item_contrib_resp = client.post(
            f'/api/wishlists/{wishlist_id}/items',
            json={
                'title': 'Collective Gift',
                'product_url': None,
                'image_url': None,
                'price': 1000,
                'allow_contributions': True,
                'goal_amount': 1000,
            },
            headers=auth_headers,
        )
        assert item_contrib_resp.status_code == 200, item_contrib_resp.text
        contrib_item_id = item_contrib_resp.json()['items'][0]['id']

        item_reserve_resp = client.post(
            f'/api/wishlists/{wishlist_id}/items',
            json={
                'title': 'Reserve Gift',
                'product_url': None,
                'image_url': None,
                'price': 500,
                'allow_contributions': False,
                'goal_amount': None,
            },
            headers=auth_headers,
        )
        assert item_reserve_resp.status_code == 200, item_reserve_resp.text
        reserve_item_id = next(
            item['id']
            for item in item_reserve_resp.json()['items']
            if item['title'] == 'Reserve Gift'
        )

        guest_resp = client.post(
            f'/api/public/w/{share_token}/sessions',
            json={'display_name': 'Guest A', 'captcha_token': None},
        )
        assert guest_resp.status_code == 200, guest_resp.text
        viewer_token = guest_resp.json()['session_token']
        viewer_headers = {'X-Viewer-Token': viewer_token}

        with client.websocket_connect(f'/ws/w/{share_token}') as ws:
            contrib_resp = client.post(
                f'/api/public/w/{share_token}/items/{contrib_item_id}/contributions',
                json={'amount': 200},
                headers=viewer_headers,
            )
            assert contrib_resp.status_code == 200, contrib_resp.text

            contribution_event = ws.receive_json()
            assert contribution_event['type'] == 'item_contribution'
            assert contribution_event['item_id'] == contrib_item_id

            reserve_resp = client.post(
                f'/api/public/w/{share_token}/items/{reserve_item_id}/reserve',
                headers=viewer_headers,
            )
            assert reserve_resp.status_code == 200, reserve_resp.text

            reserve_event = ws.receive_json()
            assert reserve_event['type'] == 'item_reserved'
            assert reserve_event['item_id'] == reserve_item_id
