import urllib.parse
from http.cookies import CookieError, SimpleCookie

import seafile_thumbnail.settings as settings


class HTTPRequest(object):
    def __init__(self, **scope):
        self.__dict__.update(scope)
        self.parse()

    def parse(self):
        self.parse_headers()
        self.parse_cookies()
        self.parse_url()
        self.parse_query_dict()

    def parse_headers(self):
        raw_headers = self.headers
        headers = {}
        for item in raw_headers:
            k = item[0].decode().lower()
            v = item[1].decode()
            if k in headers:
                headers[k].append(v)
            else:
                headers[k] = [v]
        self.headers = headers

    def parse_cookies(self):
        cookies = {}
        if self.headers.get('cookie'):
            cookie_string = self.headers.get('cookie')[0]
            # A single malformed pair (e.g. a name containing a space) makes
            # SimpleCookie reject the whole header, dropping every cookie
            # including sessionid. Parse each pair on its own so one bad cookie
            # cannot invalidate the rest.
            for chunk in self._split_cookie_header(cookie_string):
                try:
                    parsed = SimpleCookie(chunk.strip())
                except CookieError:
                    continue
                for morsel in parsed.values():
                    cookies[morsel.key] = morsel.value
        self.cookies = cookies

    @staticmethod
    def _split_cookie_header(cookie_string):
        """Split a Cookie header on ';' that appear outside double quotes.

        A quoted value may legally contain ';' and text that looks like another
        cookie pair; splitting naively on every ';' would turn that text into a
        real cookie and let it override a valid one such as sessionid.
        Backslash-escaped characters inside quotes are kept as-is.
        """
        chunks = []
        current = []
        in_quote = False
        escaped = False
        for char in cookie_string:
            if escaped:
                current.append(char)
                escaped = False
            elif in_quote and char == '\\':
                current.append(char)
                escaped = True
            elif char == '"':
                in_quote = not in_quote
                current.append(char)
            elif char == ';' and not in_quote:
                chunks.append(''.join(current))
                current = []
            else:
                current.append(char)
        chunks.append(''.join(current))
        return chunks

    def parse_url(self):
        if settings.SITE_ROOT == '/':
            self.url = self.path
        else:
            self.url = '/' + self.path[len(settings.SITE_ROOT):].lstrip('/')

    def parse_query_dict(self):
        query_string = self.query_string.decode()
        self.query_dict = urllib.parse.parse_qs(query_string)
