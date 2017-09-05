import os.path
import os

import tornado.web
from tornado.testing import AsyncHTTPTestCase
import msgpack
import numpy as np

from ..server import get_server_handlers
from ..local import LocalCatalog
from ..serializer import MsgPackSerializer


class TestServerV1Base(AsyncHTTPTestCase):
    def get_app(self):
        catalog_file = os.path.join(os.path.dirname(__file__), 'catalog1.yml')
        local_catalog = LocalCatalog(catalog_file)
        handlers = get_server_handlers(local_catalog)
        return tornado.web.Application(handlers)

    def encode(self, msg):
        return msgpack.packb(msg, use_bin_type=True)

    def decode(self, bytestr):
        return msgpack.unpackb(bytestr, encoding='utf-8')


class TestServerV1Info(TestServerV1Base):
    def test_info(self):
        response = self.fetch('/v1/info')
        self.assertEqual(response.code, 200)

        info = self.decode(response.body)

        self.assert_('version' in info)
        self.assertEqual(info['sources'], [
            {'container': 'dataframe',
             'description': 'entry1 full',
             'name': 'entry1',
             'user_parameters': []},
            {'container': 'dataframe',
             'description': 'entry1 part',
             'name': 'entry1_part',
             'user_parameters': [{'allowed': ['1', '2'],
                                  'default': '1',
                                  'description': 'part of filename',
                                  'name': 'part',
                                  'type': 'str'},
                                ]
            },
        ])


class TestServerV1Source(TestServerV1Base):
    def make_post_request(self, msg, expected_status=200):
        request = self.encode(msg)
        response = self.fetch('/v1/source', method='POST', body=request,
            headers={'Content-type': 'application/vnd.msgpack'})
        self.assertEqual(response.code, expected_status)

        responses = []
        unpacker = msgpack.Unpacker(encoding='utf-8')
        unpacker.feed(response.body)

        for msg in unpacker:
            responses.append(msg)

        return responses


    def test_open(self):
        msg = dict(action='open', name='entry1', parameters={})
        resp_msg,  = self.make_post_request(msg)

        self.assertEqual(resp_msg['container'], 'dataframe')
        self.assertEqual(resp_msg['shape'], [8])
        expected_dtype = np.dtype([('name', 'O'), ('score', 'f8'), ('rank', 'i8')])
        actual_dtype = np.dtype([tuple(x) for x in resp_msg['dtype']])
        self.assertEqual(expected_dtype, actual_dtype)

        self.assert_(isinstance(resp_msg['source_id'], str))

    def test_read(self):
        msg = dict(action='open', name='entry1', parameters={})
        resp_msg,  = self.make_post_request(msg)
        source_id = resp_msg['source_id']

        msg2 = dict(action='read', source_id=source_id, accepted_formats=['msgpack'])
        resp_msgs = self.make_post_request(msg2)

        self.assertEqual(len(resp_msgs), 2)
        ser = MsgPackSerializer()
 
        for chunk in resp_msgs:
           self.assertEqual(chunk['format'], 'msgpack')
           self.assertEqual(chunk['container'], 'dataframe')

           data = ser.decode(chunk['data'], container='dataframe')
           self.assertEqual(len(data), 4)

    def test_bad_action(self):
        msg = dict(action='bad', name='entry1')
        response, = self.make_post_request(msg, expected_status=400)
        self.assertIn('bad', response['error'])

    def test_no_format(self):
        msg = dict(action='open', name='entry1', parameters={})
        resp_msg,  = self.make_post_request(msg)
        source_id = resp_msg['source_id']

        msg2 = dict(action='read', source_id=source_id, accepted_formats=['unknown_format'])
        response, = self.make_post_request(msg2, expected_status=400)
        self.assertIn('compatible', response['error'])
