from gevent.wsgi import WSGIServer
from app import app

http_server = WSGIServer(('', 5001), app)
http_server.serve_forever()
