import json
import functools
from bottle import abort, request
from geventwebsocket.exceptions import WebSocketError
from gevent import Greenlet

from .html import *
from .jyserver import *

UNDEFINED = object()


def builder(func=None, **kwargs) -> JSFunc:
    def wrapper(func):
        return JSFunc(func, kwargs)
    return wrapper(func) if func else wrapper


class BaseContext:
    browser: type[JSchain | Browser]

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
        return name


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


class Page(BaseContext):
    dom = None
    path = "/__process_svr0"

    def __init__(self, socket=None, dom=None, path=None):
        super().__init__()

        # self.HTML = HTML(self)
        self.client = ClientContext(self, verbose=False)
        self.dom = self.dom or dom
        self.mode = "websocket"
        self.socket = socket
        if socket:
            self.client.setSocket(socket)
        self.path = self.path or path
        self.HTML = HTML(self)

    def __init_subclass__(cls, dom=None, namespace=None, path=None, **kw):
        super().__init_subclass__(**kw)
        if namespace:
            cls.namespace = namespace

        dom = dom or getattr(cls, "dom", None)
        if dom:
            cls.dom = dom
            cls.dom.register(cls, namespace)

        path = path or getattr(cls, "path", None)
        if path:
            cls.path = path

    def __call__(self, *args, **kwds):
        return self.render(*args, **kwds)

    @property
    def deps(self):
        return [
            f"const NAMESPACE = '{self.namespace}';",
            ["/static/socket.io.min.js"],
            JYSERVER,
            f'const client = new ClientContext(window.location.host + "{self.path}");\nclient.connect();\nconst server = client.server;'
        ]

    def html(self):
        return ""

    def render(self, *a, mode="websocket", **kw):
        self.mode = self.mode or mode
        return f"{''.join(str(script(x)) if isinstance(x, str) else str(script(src=x[0])) for x in self.deps)}{self.html(*a, **kw)}"

    def __str__(self):
        return self.render()


class VirtualDom:
    def __init__(self, app=None, context=None, use_global_client=False, path="/__process_svr0"):
        self.base_context = context or BaseContext()
        self.global_client = use_global_client
        self.path = path

        self.Page = Page
        self.Page.dom = self
        self.Page.path = path

        self.client = None

        self.namespaces = {}

        if self.global_client:
            self.client = ClientContext(self.base_context, verbose=True)
            self.context = self.client.obj

        self.HTML = HTML(self.client)
        if app:
            app.route("/__process_svr0", callback=self.websocket)

        @self.register
        class Node(Page):
            pass

    def register(self, context=None, name=None):

        def main(context, name):
            if issubclass(context, Page):
                context = context()

            assert isinstance(context, Page)

            name = name or getattr(context, "namespace", None) or (
                context.__class__.__name__).lower()
            self.namespaces[name] = context
            setattr(context, "namespace", name)

            return context
        return main(context, name) if context else main

    def websocket(self, socket):
        if not socket:
            abort(400, 'Expected WebSocket request.')

        while True:
            try:
                message = socket.receive()
                if message:
                    temp_message: dict = json.loads(message)
                    print("Message:", temp_message)

                    page: Page = self.namespaces.get(
                        temp_message.pop("namespace", None))

                    if not page:
                        break

                    page.client.setSocket(socket)

                    result = page.client.processCommand(
                        json.loads(message, cls=page.client.decoder))
                    if result:
                        result = result.replace("'", '"')
                    print("Response:", result)
                    socket.send(result or "")
                else:
                    socket.send("")
            except WebSocketError:
                break
            except Exception as e:
                raise e
                # print(e)
                continue
            finally:
                pass

    def socketio(self):
        from socketio import Server, WSGIApp
        io = Server(async_mode="gevent")
        app = WSGIApp(io, socketio_path="")

        @io.event
        def message(ev, msg):
            # print(msg)
            if msg:
                temp_message: dict = json.loads(msg)

                page: Page = self.namespaces.get(
                    temp_message.pop("namespace", None))

                if not page:
                    pass

                page.client.setSocketIo(io)

                result = page.client.processCommand(
                    json.loads(msg, cls=page.client.decoder))
                if result:
                    result = result.replace("'", '"')
                print("Message:", temp_message, "\nResponse:", result)
                io.emit("message", result or "")
            else:
                io.emit("message", "")

        return app


virtualdom = VirtualDom()
