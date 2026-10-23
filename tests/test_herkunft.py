import pytest

from app import app, _herkunft_pruefen
from models import CompanySettings, db

FREMD = {'Sec-Fetch-Site': 'cross-site', 'Origin': 'https://boese.example'}


@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.app_context():
        row = CompanySettings.query.get('iban')
        vorher = row.value if row else None
    with app.test_client() as c:
        yield c
    with app.app_context():
        row = CompanySettings.query.get('iban')
        if vorher is None and row:
            db.session.delete(row)
        elif vorher is not None:
            row.value = vorher
        db.session.commit()


def _iban():
    with app.app_context():
        return CompanySettings.get('iban')


def _post(client, iban, headers=None, **kw):
    return client.post('/settings/company', data={'iban': iban}, headers=headers or {}, **kw)


def test_fremde_seite_kann_iban_nicht_tauschen(client):
    vorher = _iban()
    r = _post(client, 'AT00 BOESE', FREMD)
    assert r.status_code == 403
    assert _iban() == vorher


def test_ohne_pruefung_waere_der_post_durchgegangen(client):
    funcs = app.before_request_funcs[None]
    funcs.remove(_herkunft_pruefen)
    try:
        r = _post(client, 'AT00 BOESE', FREMD)
        assert r.status_code in (200, 302)
        assert _iban() == 'AT00 BOESE'
    finally:
        funcs.append(_herkunft_pruefen)


@pytest.mark.parametrize('headers', [
    {'Sec-Fetch-Site': 'same-site'},
    {'Origin': 'null'},
    {'Origin': 'https://boese.example'},
    {'Origin': 'http://localhost:3000'},
    {'Origin': 'https://localhost'},
])
def test_weitere_fremde_herkunft_abgewiesen(client, headers):
    assert _post(client, 'AT00 X', headers).status_code == 403


@pytest.mark.parametrize('headers', [
    {},
    {'Sec-Fetch-Site': 'same-origin', 'Origin': 'http://localhost'},
    {'Origin': 'http://localhost'},
])
def test_eigene_herkunft_und_scripts_erlaubt(client, headers):
    assert _post(client, 'AT00 0000', headers).status_code in (200, 302)


def test_fremder_host_abgewiesen_dns_rebinding(client):
    assert client.get('/', base_url='http://boese.example').status_code == 403
    assert client.get('/', base_url='http://localhost:5000').status_code == 200


def test_kaputter_host_ist_fremd_statt_absturz():
    from app import _lokaler_host
    assert _lokaler_host('[::1') is False
    assert _lokaler_host('[::1]:5000') is True
    assert _lokaler_host('localhost.:5000') is False


def test_reflektierte_ansicht_landet_nicht_im_js(client):
    body = client.get("/content-calendar?view=x'};window.__k1=1;x={a:'").get_data(as_text=True)
    assert '__k1' not in body


def test_links_von_aussen_bleiben_offen(client):
    assert client.get('/', headers={'Sec-Fetch-Site': 'cross-site'}).status_code == 200


def test_nur_selbst_einbettbar(client):
    r = client.get('/')
    assert r.headers['X-Frame-Options'] == 'SAMEORIGIN'
    assert "frame-ancestors 'self'" in r.headers['Content-Security-Policy']
    assert r.headers['X-Content-Type-Options'] == 'nosniff'
