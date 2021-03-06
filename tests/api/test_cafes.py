# coding: utf-8

import random
from flask import json
from zerqu.models import Cafe, CafeTopic, CafeMember
from zerqu.models import db, User, Topic
from ._base import TestCase


class CafeMixin(object):
    def create_cafes(self, num=30):
        for i in range(num):
            permission = random.choice([
                Cafe.PERMISSION_PUBLIC,
                Cafe.PERMISSION_APPROVE,
                Cafe.PERMISSION_MEMBER,
            ])
            status = random.choice(list(Cafe.STATUSES.keys()))
            name = u'%s-%d' % (random.choice(['foo', 'bar']), i)
            user_id = random.choice([1, 2])
            item = Cafe(
                name=name, slug=name, user_id=user_id,
                permission=permission, status=status,
            )
            db.session.add(item)
        db.session.commit()


class TestListCafes(TestCase, CafeMixin):
    def test_list_cafes(self):
        self.create_cafes()
        rv = self.client.get('/api/cafes')
        assert rv.status_code == 200
        value = json.loads(rv.data)
        assert len(value['data']) == 20
        assert value['cursor']

        rv = self.client.get('/api/cafes?count=40')
        assert rv.status_code == 200
        value = json.loads(rv.data)
        assert not value['cursor']

    def test_list_cafes_with_login(self):
        headers = self.get_authorized_header()
        self.create_cafes()
        rv = self.client.get('/api/cafes', headers=headers)
        assert rv.status_code == 200
        assert b'following' in rv.data


class TestCreateCafe(TestCase):
    def test_no_permission(self):
        user = User(username='demo', email='demo@gmail.com')
        user.role = 1
        db.session.add(user)
        db.session.commit()
        self.app.config['ZERQU_CAFE_CREATOR_ROLE'] = 4
        headers = self.get_authorized_header(
            user_id=user.id, scope='cafe:write',
        )
        rv = self.client.post('/api/cafes', headers=headers)
        assert rv.status_code == 403

    def get_creator_headers(self):
        user = User(username='demo', email='demo@gmail.com')
        user.status = 1
        user.role = 9
        self.app.config['ZERQU_CAFE_CREATOR_ROLE'] = 1
        db.session.add(user)
        db.session.commit()
        headers = self.get_authorized_header(
            user_id=user.id, scope='cafe:write',
        )
        return headers

    def test_create_cafe(self):
        headers = self.get_creator_headers()
        data = json.dumps({
            'name': 'hello-world',
            'slug': 'hello-world',
            'permission': 'public',
        })
        rv = self.client.post('/api/cafes', headers=headers, data=data)
        assert rv.status_code == 201


class TestUpdateCafe(TestCase, CafeMixin):
    def get_prepared_data(self, cafe_user=1):
        self.create_cafes(10)
        user = User.query.get(1)
        cafe = Cafe.query.filter_by(user_id=cafe_user).first()
        headers = self.get_authorized_header(user.id, scope='cafe:write')
        return cafe, headers

    def test_owner_update_cafe_name(self):
        cafe, headers = self.get_prepared_data(1)
        data = json.dumps({'name': 'ABC', 'slug': cafe.slug})
        rv = self.client.post(
            '/api/cafes/%s' % cafe.slug, data=data, headers=headers,
        )
        assert rv.status_code == 200
        assert cafe.name == 'ABC'

    def test_owner_update_cafe_slug(self):
        cafe, headers = self.get_prepared_data(1)
        data = json.dumps({'slug': 'a-b-c', 'name': cafe.name})
        rv = self.client.post(
            '/api/cafes/%s' % cafe.slug, data=data, headers=headers,
        )
        assert rv.status_code == 200
        data = json.loads(rv.data)
        assert data['slug'] == 'a-b-c'
        assert cafe.slug == 'a-b-c'

    def test_owner_update_cafe_no_change(self):
        cafe, headers = self.get_prepared_data(1)
        data = json.dumps({'slug': cafe.slug, 'name': cafe.name})
        rv = self.client.post(
            '/api/cafes/%s' % cafe.slug, data=data, headers=headers,
        )
        assert rv.status_code == 200

    def test_admin_update_cafe_no_permission(self):
        cafe, headers = self.get_prepared_data(2)
        data = json.dumps({'name': 'A'})
        rv = self.client.post(
            '/api/cafes/%s' % cafe.slug, data=data, headers=headers,
        )
        assert rv.status_code == 403

    def add_membership(self, cafe):
        m = CafeMember(user_id=1, cafe_id=cafe.id, role=CafeMember.ROLE_ADMIN)
        db.session.add(m)
        db.session.commit()

    def test_admin_update_cafe_name(self):
        # Add membership
        cafe, headers = self.get_prepared_data(2)
        self.add_membership(cafe)
        data = json.dumps({'name': 'ABC', 'slug': cafe.slug})
        rv = self.client.post(
            '/api/cafes/%s' % cafe.slug, data=data, headers=headers,
        )
        assert rv.status_code == 200
        assert cafe.name == 'ABC'

    def test_admin_update_cafe_slug(self):
        cafe, headers = self.get_prepared_data(2)
        self.add_membership(cafe)
        data = json.dumps({'slug': 'a-b-c', 'name': cafe.name})
        rv = self.client.post(
            '/api/cafes/%s' % cafe.slug, data=data, headers=headers,
        )
        assert rv.status_code == 200
        data = json.loads(rv.data)
        assert data['slug'] != 'a-b-c'
        assert cafe.slug != 'a-b-c'


class TestViewCafe(TestCase, CafeMixin):
    def test_not_found(self):
        rv = self.client.get('/api/cafes/notfound')
        assert rv.status_code == 404

    def test_view_cafe(self):
        self.create_cafes(2)
        cafe = Cafe.query.get(1)

        rv = self.client.get('/api/cafes/%s' % cafe.slug)
        value = json.loads(rv.data)
        assert 'user' in value

    def test_view_cafe_with_login(self):
        headers = self.get_authorized_header(user_id=6)
        self.create_cafes(2)
        cafe = Cafe.query.get(1)

        rv = self.client.get('/api/cafes/%s' % cafe.slug, headers=headers)
        value = json.loads(rv.data)
        assert 'permission' in value
        assert not value['permission'].get('admin')

    def test_view_cafe_with_membership(self):
        headers = self.get_authorized_header(user_id=1)
        member = CafeMember(user_id=1, cafe_id=1, role=CafeMember.ROLE_ADMIN)
        db.session.add(member)
        self.create_cafes(2)
        cafe = Cafe.query.get(1)

        rv = self.client.get('/api/cafes/%s' % cafe.slug, headers=headers)
        value = json.loads(rv.data)
        assert 'permission' in value
        assert value['permission']['write']
        assert value['permission']['admin']


class TestCafeMembers(TestCase, CafeMixin):

    def create_membership(self, permission, total):
        item = Cafe(
            name=u'hello', slug='hello', user_id=2,
            permission=permission
        )
        db.session.add(item)
        db.session.commit()

        for i in range(total):
            username = 'demo-%d' % i
            user = User(username=username, email='%s@gmail.com' % username)
            db.session.add(user)
            db.session.commit()
            member = CafeMember(cafe_id=item.id, user_id=user.id)
            member.role = random.choice([
                CafeMember.ROLE_VISITOR,
                CafeMember.ROLE_SUBSCRIBER,
                CafeMember.ROLE_MEMBER,
                CafeMember.ROLE_ADMIN,
            ])
            db.session.add(member)
        db.session.commit()

    def test_join_public_cafe(self):
        item = Cafe(
            name=u'hello', slug='hello', user_id=2,
            permission=Cafe.PERMISSION_PUBLIC,
        )
        db.session.add(item)
        db.session.commit()

        url = '/api/cafes/hello/users'
        headers = self.get_authorized_header(scope='user:subscribe')
        rv = self.client.post(url, headers=headers)
        assert rv.status_code == 204

        headers = self.get_authorized_header(scope='user:subscribe', user_id=2)
        rv = self.client.post(url, headers=headers)
        assert rv.status_code == 204

    def test_visitor_join_cafe(self):
        item = Cafe(
            name=u'hello', slug='hello', user_id=2,
            permission=Cafe.PERMISSION_PUBLIC,
        )
        db.session.add(item)
        # create a visitor membership
        db.session.add(CafeMember(cafe_id=1, user_id=1))
        db.session.commit()

        url = '/api/cafes/hello/users'
        headers = self.get_authorized_header(scope='user:subscribe')
        rv = self.client.post(url, headers=headers)
        assert rv.status_code == 204

    def test_leave_cafe(self):
        self.create_cafes(2)
        cafe = Cafe.query.get(2)

        url = '/api/cafes/%s/users' % cafe.slug
        headers = self.get_authorized_header(scope='user:subscribe')
        rv = self.client.delete(url, headers=headers)
        assert rv.status_code == 404

        item = CafeMember(cafe_id=2, user_id=1)
        db.session.add(item)
        db.session.commit()
        rv = self.client.delete(url, headers=headers)
        assert rv.status_code == 204

    def test_list_public_cafe_users(self):
        total = 60
        self.create_membership(Cafe.PERMISSION_PUBLIC, total)

        url = '/api/cafes/hello/users'
        rv = self.client.get(url)
        assert rv.status_code == 200

        value = json.loads(rv.data)
        assert 'pagination' in value
        assert value['pagination']['total'] == total
        assert value['pagination']['next'] == 2
        assert value['pagination']['prev'] is None

        url = '/api/cafes/hello/users?page=3'
        rv = self.client.get(url)
        value = json.loads(rv.data)
        assert value['pagination']['prev'] == 2

        rv = self.client.get('/api/cafes/hello/users?page=-1')
        assert rv.status_code == 400
        rv = self.client.get('/api/cafes/hello/users?page=10')
        assert rv.status_code == 400
        rv = self.client.get('/api/cafes/hello/users?perpage=1')
        assert rv.status_code == 400


class TestCafeTopics(TestCase):
    def test_list_cafe_topics(self):
        item = Cafe(
            name=u'hello', slug='hello', user_id=1,
            permission=Cafe.PERMISSION_PUBLIC
        )
        db.session.add(item)
        db.session.commit()

        user_ids = [o.id for o in User.query.all()]

        for i in range(60):
            t = Topic(
                user_id=random.choice(user_ids),
                title=u'test',
                content=u'',
            )
            db.session.add(t)
            db.session.flush()
            ct = CafeTopic(
                cafe_id=item.id,
                topic_id=t.id,
                user_id=1,
                status=CafeTopic.STATUS_PUBLIC,
            )
            db.session.add(ct)

        db.session.commit()

        rv = self.client.get('/api/cafes/hello/topics')
        assert b'data' in rv.data
