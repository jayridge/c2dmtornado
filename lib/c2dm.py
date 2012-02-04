from tornado import ioloop, httpclient
import settings
import logging
import urllib
import time
import functools
from collections import deque
from MemcachePool import mc


MAX_PAYLOAD_BYTES = 1024

class c2dm:
    def __init__(self, loop=None):
        self.ioloop = loop or ioloop.IOLoop.instance()
        self.http_client = httpclient.AsyncHTTPClient(io_loop=self.ioloop)
        self.http_client.configure("tornado.curl_httpclient.CurlAsyncHTTPClient")
        self._token = None
        self.write_queue = deque()
        self.started = time.time()
        self.stats = { 
            'notifications':0,
            'notifications_ok':0,
            'invalid_registration':0,
            'quota_exceeded':0,
            'client_login_failed':0,
            'unavailable':0,
        }   
        self.get_token()

    def get_stats(self):
        stats = self.stats.copy()
        stats['queue_len'] = len(self.write_queue)
        stats['uptime'] = time.time() - self.started
        return stats

    def get_token(self):
        if not self._token:
            login = settings.get('login')
            url = settings.get('login_url') + "?" + urllib.urlencode(login, doseq=1)
            http_client = httpclient.HTTPClient()
            response = http_client.fetch(url, connect_timeout=5, request_timeout=5)
            logging.info("fetched client token for %s (code:%d, seconds:%d)" % (
                login.get("Email"), response.code, response.request_time))
            if response.error:
                logging.exception("fetch failed", response.error)
            if response.body:
                items = response.body.split('\n')
                self._token = items[2].split('=')[1].strip()
        return self._token

    def clear_token(self):
        self._token = None

    def push(self, registration_id, collapse_key, delay_while_idle=None, extra={}):
        flagged = mc.get(registration_id)
        if flagged:
            self.stats['invalid_registration'] += 1
            return False

        data = {'registration_id': registration_id, 'collapse_key': collapse_key}
        for k, v in extra.items():
            data['data.'+k] = v
        if delay_while_idle:
            data['delay_while_idle'] = ""
        data = urllib.urlencode(data, doseq=1)
        if len(data) > MAX_PAYLOAD_BYTES:
            raise ValueError, u"max payload(%d) exceeded: %d" % (MAX_PAYLOAD_BYTES, len(data))
        self.write_queue.append(dict(registration_id=registration_id, payload=data))
        self.ioloop.add_callback(self.push_one)
        return True

    def send(self, data):
        self.stats['notifications'] += 1
        headers = {'Authorization': 'GoogleLogin auth=' + self.get_token()}
        self.http_client.fetch(settings.get('c2dm_url'),
            functools.partial(self._finish_send, data=data),
            follow_redirects=False, method="POST", body=data.get('payload'),
            validate_cert=False, headers=headers, connect_timeout=10, request_timeout=10)

    def _finish_send(self, response, data):
        if response.error:
            logging.exception("send failed", response.error)
        else:
            if response.code == 200:
                body = response.buffer.getvalue()
                retvals = {}
                items = response.body.split('\n')
                for item in items: 
                    pair = item.split('=')
                    if len(pair) == 2:
                        retvals[pair[0].strip()] = pair[1].strip()
                if 'id' in retvals:
                    self.stats['notifications_ok'] += 1
                    logging.info("sent(%s): %s", retvals.get('id'), data.get('payload'))
                elif 'Error' in retvals:
                    err = retvals.get('Error')
                    logging.warning("%s: %s", err, data.get('payload'))
                    if err == 'InvalidRegistration' or err == 'NotRegistered':
                        mc.set(data.get('registration_id'), int(time.time()))
                        self.stats['invalid_registration'] += 1
                    elif err == 'QuotaExceeded':
                        self.stats['quota_exceeded'] += 1
                        self.write_queue.appendleft(data)
            elif response.code == 401:
                self.stats['client_login_failed'] += 1
                self.clear_token()
                self.write_queue.appendleft(data)
            elif response.code == 503:
                self.stats['unavailable'] += 1
                self.write_queue.appendleft(data)

    def push_one(self):
        if len(self.write_queue):
            data = self.write_queue.popleft()
            try:
                self.send(data)
            except:
                self.write_queue.appendleft(data)
                return False
            return True
        return False


