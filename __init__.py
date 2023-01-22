import json
import functools
from bottle import abort
from bottle_websocket import WebSocketError
from gevent import Greenlet

from .html import HTML, Browser, Reactive, bind
from .jyserver import ClientContext

class BaseContext:
    browser: Browser

    def __init__(self):
        self.__customs = {}

    @property
    def customs(self):
        return self.__customs
    
    def __getattr__(self, name):
        if name in self.__customs:
            def wrapper(*a, **kw):
                return self.__customs[name](self.browser, *a, **kw)
            return wrapper
        raise AttributeError
    
    def __register__(self, name, func):
        self.__customs[name] = func

def task(func):
    '''
    Decorator wraps the function in a separate thread for concurrent
    execution.
    '''
    @functools.wraps(func)
    def wrapper(*args):
        server_thread = Greenlet(func, *args)
        server_thread.start()
    return wrapper

class VirtualDom:
    def __init__(self, app=None, context=None):
        self.client = ClientContext(context or BaseContext)
        self.context = self.client.obj

        self.HTML = HTML(self.client)
        if app:
            app.route("/_process_srv0", callback=self.websocket)
    
    def websocket(self, socket):
        if not socket:
            abort(400, 'Expected WebSocket request.')
        while True:
            try:
                message = socket.receive()
                if message:
                    self.client.setSocket(socket)
                    result = self.client.processCommand(json.loads(message))
                    if result and ((result.startswith("{") and result.endswith("}")) or (result.startswith("[") and result.endswith("]"))):
                        result = result.replace("'", '"')
                    socket.send(result or "")
                socket.send("")
            except WebSocketError as e:
                break

virtualdom = VirtualDom()
