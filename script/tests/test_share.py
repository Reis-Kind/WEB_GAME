"""Public sharing accepts same-origin HTTPS without login."""
import io
from types import SimpleNamespace
import unittest
from unittest.mock import Mock
import server


class SharingTests(unittest.TestCase):
    def handler(self, public=True, origin='https://game.example'):
        handler = object.__new__(server.Handler)
        handler.server = SimpleNamespace(public_share=public)
        handler.headers = {'Host': 'game.example', 'Origin': origin, 'Content-Length': '2'}
        handler.path = '/api/gemini/round'
        handler.rfile = io.BytesIO(b'{}')
        handler.send_json = Mock()
        return handler

    def test_public_https_reaches_validation_without_auth(self):
        handler = self.handler()
        handler.do_POST()
        self.assertEqual(handler.send_json.call_args.args[0], 400)

    def test_other_origin_is_rejected(self):
        handler = self.handler(origin='https://other.example')
        handler.do_POST()
        self.assertEqual(handler.send_json.call_args.args[0], 403)

    def test_local_mode_does_not_accept_https_proxy_origin(self):
        handler = self.handler(public=False)
        handler.do_POST()
        self.assertEqual(handler.send_json.call_args.args[0], 403)

    def test_public_config_without_authorization(self):
        handler = self.handler()
        handler.path = '/api/config'
        handler.do_GET()
        self.assertEqual(handler.send_json.call_args.args[0], 200)


if __name__ == '__main__':
    unittest.main()
