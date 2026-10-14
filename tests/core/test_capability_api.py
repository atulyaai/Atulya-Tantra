"""Exercise capability readiness through the authenticated application API."""
import asyncio

import httpx

from atulya.auth import SESSION_COOKIE
from atulya.server import create_app
from atulya.settings import Settings


def test_capability_api_auth_plugin_toggle_and_owner_isolation(project_temp_dir, monkeypatch):
    from tools.plugins.information import google_api
    monkeypatch.setattr(google_api, 'connection_status', lambda _: {})
    settings = Settings(assistant_name='Atulya', host='127.0.0.1', port=8501,
                        data_dir=project_temp_dir / 'data', models_dir=project_temp_dir / 'models',
                        model_provider='', model_name='', model_base_url='', model_api_key='')
    app = create_app(settings)

    async def exercise():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://localhost') as client:
            assert (await client.get('/api/capabilities')).status_code == 401
            auth = app.state.auth_store
            auth.ensure_user('admin', 'Owner', 'admin')
            client.cookies.set(SESSION_COOKIE, auth.create_session('admin'))
            response = await client.get('/api/capabilities')
            assert response.status_code == 200
            rows = {r['name']: r for r in response.json()['capabilities']}
            assert rows['calculate']['status'] == 'available'
            assert rows['gmail_search']['status'] == 'needs_connection'
            assert all(row['next_step'] for row in rows.values())
            result = await client.post('/api/plugins/online-information', json={'enabled': False})
            assert result.status_code == 200
            rows = {r['name']: r for r in (await client.get('/api/capabilities')).json()['capabilities']}
            assert rows['get_weather']['status'] == 'disabled'
            assert 'get_weather' not in (await client.get('/api/connections')).json()['mcp']['tools']
            auth.ensure_user('audit-user', 'Audit user')
            client.cookies.set(SESSION_COOKIE, auth.create_session('audit-user'))
            assert (await client.get('/api/connections')).status_code == 403
            rows = {r['name']: r for r in (await client.get('/api/capabilities')).json()['capabilities']}
            assert rows['maintenance_check']['status'] == 'needs_connection'
            assert rows['mcp_call_tool']['status'] == 'needs_connection'

    asyncio.run(exercise())
