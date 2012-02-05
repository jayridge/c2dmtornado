import sys
import tornado.options
import tornado.web
from tornado.escape import utf8
import settings
from settings import options, env
import logging
import simplejson as json
from lib.MemcachePool import mc
from lib.c2dm import c2dm


class BaseHandler(tornado.web.RequestHandler):
    def get_int_argument(self, name, default=None):
        value = self.get_argument(name, default=default)
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    def error(self, status_code=500, status_txt=None, data=None):
        """write an api error in the appropriate response format"""
        self.api_response(status_code=status_code, status_txt=status_txt, data=data)

    def api_response(self, data, status_code=200, status_txt="OK"):
        """write an api response in json"""
        self.set_header("Content-Type", "application/json; charset=utf-8")
        self.finish(json.dumps(dict(data=data, status_code=status_code, status_txt=status_txt)) + "\n")


class PushHandler(BaseHandler):
    def get(self):
        registration_id = utf8(self.get_argument("registration_id"))
        collapse_key = self.get_argument("collapse_key", settings.get("collapse_key"))
        data = {}
        for k, v in self.request.arguments.items():
            if k not in ['registration_id', 'collapse_key']:
                data[k] = v

        status = 'ERROR'
        code = 500 
        resp = {'queued':False, 'exception':None}
        try:
            resp['queued'] = _c2dm.push(registration_id, collapse_key, extra=data)
            if resp['queued']:
                status = 'OK'
                code = 200 
            self.api_response(resp, status_code=code, status_txt=status)
        except Exception as e:
            self.error(status_code=500, status_txt=status, data=str(e))


class FlushHandler(BaseHandler):
    def get(self):
        registration_id = utf8(self.get_argument("registration_id"))
        try:
            mc.delete(registration_id)
            self.api_response(dict(registration_id=registration_id))
        except Exception as e:
            self.error(status_code=500, status_txt='ERROR', data=str(e))


class StatsHandler(BaseHandler):
    def get(self):
        self.api_response(_c2dm.get_stats())


if __name__ == "__main__":
    tornado.options.define("port", default=8888, help="Listen on port", type=int)
    tornado.options.define("Email", default=None, help="Google client email", type=str)
    tornado.options.define("Passwd", default=None, help="Google client password", type=str)
    tornado.options.define("source", default=None, help="C2DM source", type=str)
    tornado.options.parse_command_line()
    ''' allow sensitive data to be passed on cmd line ( so everyone can see it w ps ) '''
    for key in ['Email', 'Passwd', 'source']:
        if key in tornado.options.options and tornado.options.options[key].value():
            options.get(env())['login'][key] = tornado.options.options[key].value()

    logging.getLogger().setLevel(settings.get('logging_level'))

    # the global c2dm
    _c2dm = c2dm()

    application = tornado.web.Application([
        (r"/push", PushHandler),
        (r"/stats", StatsHandler),
        (r"/flush", FlushHandler),
    ], debug=(env() == 'dev'))
    application.listen(tornado.options.options.port)
    tornado.ioloop.IOLoop.instance().start()
