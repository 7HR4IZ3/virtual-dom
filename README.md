# Virtual Dom
Extension of jyserver supporting proxying javascript and python objects between serverand client browser (unstable)

# Quick Demo
```python
from bottle import Bottle, static_file
from bottle_websocket import GeventWebSocketServer, websocket
from virtual_dom import VirtualDom, BaseContext, Reactive, task, JsObject, LocalStorage, Page, SessionStorage, HTML

dom = VirtualDom()
h = HTML()

HOST = "127.0.0.1"
PORT = 8080

app = Bottle()
# Install plugin to use websocket with bottle
app.install(websocket)

# Server the main process
# dom.websocket is a function that takes the websocket object as the only argument and processes the request
# Websocket object must have a send and receive functions

app.route("/__process_svr0", callback=dom.websocket)

class HomePage(Page):
    def on_client_connected(self, *args):
        self.browser.alert('Hello World')
    
    def count(self):
        c = self.browser.document.querySelector('#count')
        c.innerText = int(c.innerText) + 1
    
    def render(self):
        return h.html(
            h.body(
                h.div("Count: ", h.p(id="count")),
                h.button("Increment", onclick=self.count)
            )
        )

@app.route("/")
def index():
    page = HomePage
    return page.render()

app.run(host=HOST, port=PORT, reloader=True, server=GeventWebSocketServer)
```

Check out https://github.com/7HR4IZ3/virtual-dom-demo for a chat application using virtual dom.
