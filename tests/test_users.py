# coding: utf-8

import base64
from flask import json
from zerqu.models import User
from ._base import TestCase


def b64encode(text):
    # TODO: compatible
    return base64.b64encode(text)

auth_header = {
    'Authorization': 'Basic %s' % b64encode('ios:secret')
}


class TestCreateUser(TestCase):
    def test_create_user_forbidden(self):
        rv = self.client.post('/api/users')
        assert rv.status_code == 403

    def test_create_user_success(self):
        rv = self.client.post('/api/users', data=json.dumps({
            'username': 'createuser',
            'email': 'createuser@gmail.com',
            'password': 'test-password',
        }), content_type='application/json', headers=auth_header)
        assert rv.status_code == 201
        data = json.loads(rv.data)
        user = User.cache.filter_first(username='createuser')
        expected = {'status': 'ok', 'data': dict(user)}
        assert data == json.loads(json.dumps(expected))

        # can't register with the same email address
        rv = self.client.post('/api/users', data=json.dumps({
            'username': 'createuser2',
            'email': 'createuser@gmail.com',
            'password': 'test-password',
        }), content_type='application/json', headers=auth_header)
        assert rv.status_code == 400
        assert b'error_form' in rv.data

    def test_create_user_error_form(self):
        rv = self.client.post('/api/users', data=json.dumps({
            'username': 'createuser',
            'password': 'test-password',
        }), content_type='application/json', headers=auth_header)
        assert rv.status_code == 400
        assert b'error_form' in rv.data

        rv = self.client.post('/api/users', data=json.dumps({
            'username': 'zerqu',
            'password': 'test-password',
        }), content_type='application/json', headers=auth_header)
        assert rv.status_code == 400
        assert b'registered' in rv.data


class TestCurrentUser(TestCase):
    def test_current_authenticated_user(self):
        rv = self.client.get('/api/user')
        assert rv.status_code == 401


class TestListUsers(TestCase):
    def test_list_without_parameters(self):
        rv = self.client.get('/api/users')
        assert rv.status_code == 200

    def test_list_with_before(self):
        rv = self.client.get('/api/users?before=2')
        value = json.loads(rv.data)
        assert len(value['data']) == 1

    def test_list_with_after(self):
        rv = self.client.get('/api/users?after=1')
        value = json.loads(rv.data)
        for item in value['data']:
            assert item['id'] != 1