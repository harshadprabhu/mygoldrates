import http.server, os, sys, functools
DOCS = sys.argv[1]; HERE = os.path.dirname(os.path.abspath(__file__))
class H(http.server.SimpleHTTPRequestHandler):
    def translate_path(self, path):
        p = path.split("?",1)[0].split("#",1)[0]
        if p.startswith("/__v/"):
            return os.path.join(HERE, p[5:])
        return super().translate_path(path)
    def log_message(self,*a): pass
http.server.ThreadingHTTPServer(("127.0.0.1", 8765), functools.partial(H, directory=DOCS)).serve_forever()
