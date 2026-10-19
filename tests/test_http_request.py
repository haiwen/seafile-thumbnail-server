import unittest

from seafile_thumbnail.http_request import HTTPRequest


def build_request(cookie_header):
    return HTTPRequest(
        method='GET',
        path=b'/thumbnail/8492b372-3402-4d25-aa12-65f07f61777a/create/',
        query_string=b'',
        headers=[(b'cookie', cookie_header.encode())],
    )


class ParseCookiesTest(unittest.TestCase):

    def test_parses_valid_cookie_header(self):
        request = build_request('sessionid=abc123; foo=bar')
        self.assertEqual(request.cookies, {'sessionid': 'abc123', 'foo': 'bar'})

    def test_keeps_sessionid_when_header_contains_invalid_cookie_name(self):
        request = build_request('session 1=1944238106823118; sessionid=abc123')
        self.assertEqual(request.cookies.get('sessionid'), 'abc123')

    def test_keeps_sessionid_when_invalid_cookie_name_follows_it(self):
        request = build_request('sessionid=abc123; session 1=1944238106823118')
        self.assertEqual(request.cookies.get('sessionid'), 'abc123')

    def test_keeps_other_valid_cookies_alongside_invalid_one(self):
        request = build_request('foo=bar; session 1=1944238106823118; sessionid=abc123')
        self.assertEqual(request.cookies, {'foo': 'bar', 'sessionid': 'abc123'})

    def test_does_not_take_sessionid_from_quoted_value(self):
        request = build_request('sessionid=abc123; foo="a; sessionid=bogus; b"')
        self.assertEqual(request.cookies, {
            'sessionid': 'abc123',
            'foo': 'a; sessionid=bogus; b',
        })

    def test_does_not_take_sessionid_from_leading_quoted_value(self):
        request = build_request('foo="a; sessionid=bogus; b"; sessionid=abc123')
        self.assertEqual(request.cookies, {
            'foo': 'a; sessionid=bogus; b',
            'sessionid': 'abc123',
        })

    def test_preserves_escaped_quote_in_quoted_value(self):
        request = build_request('foo="quoted\\"x"; sessionid=abc123')
        self.assertEqual(request.cookies, {
            'foo': 'quoted"x',
            'sessionid': 'abc123',
        })


if __name__ == '__main__':
    unittest.main()
