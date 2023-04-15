import json
import random
import time

from pathlib import Path

from domonic.dom import *
from domonic import *
from domonic import JSON

from .jyserver import JSchain

with open(f"{Path(__file__).parent.absolute()}/jyserver/wsserver.js") as f:
    JYSERVER = f.read()

JYSERVER_AFTER = """
//observer.observe(document.documentElement, {attributes: true, childList: true, characterData: true, subtree: true});
"""

class Browser:
    document: Document
    console: Console
    alert: function
    JSON: JSON
    event: Event


class Reactive:
    def __init__(self, initial=None, onchange=None):
        self.__onchange =  onchange
        self.initial = initial
    
    def set_onchange(self, onchange):
        self.__onchange =  onchange
        return self
    
    def onchange(self, owner):
        if isinstance(self.__onchange, str):
            onchange = getattr(owner, self.__onchange)
        else:
            onchange = self.__onchange
        if not onchange:
            onchange = getattr(owner, f"on_{self.public_name}_change", None)
        return onchange or (lambda *a: None)

    def __get__(self, obj, objtype=None):
        value = getattr(obj, self.private_name, None)
        return value

    def __set__(self, obj, value):
        initial = getattr(obj, self.private_name, None)
        setattr(obj, self.private_name, value)

        if not (initial is None):
            self.onchange(obj)(initial, value)
    
    def __set_name__(self, owner, name):
        self.public_name = name
        self.private_name = '_' + name

        if self.initial:
            setattr(owner, self.private_name, self.initial)

class LocalStorage(Reactive):
    def __init__(self, default=None, *a, type=str, **kw):
        super().__init__(*a, **kw)
        self.type = type
        self.default = default

    def __get__(self, obj, objtype=None):
        try:
            browser = getattr(obj, "browser", None)
            if browser:
                item = browser.localStorage.getItem(self.public_name).eval()
                return self.type(item) if item else self.default
            else:
                return self.default 
        except Exception as e:
            print(e)
            return self.default

    def __set__(self, obj, value):
        browser = getattr(obj, "browser", None)
        if browser:
            initial = browser.localStorage.getItem(self.public_name)
            browser.localStorage.setItem(self.public_name, value)

            if initial:
                self.onchange(obj)(initial, value)
    
    def __set_name__(self, owner, name):
        self.public_name = name

        if self.initial:
            self.__set__(owner, self.initial)

class SessionStorage(Reactive):
    def __init__(self, default=None, *a, type=str, **kw):
        super().__init__(*a, **kw)
        self.type = type
        self.default = default

    def __get__(self, obj, objtype=None):
        try:
            browser = getattr(obj, "browser", None)
            if browser:
                item = browser.sessionStorage.getItem(self.public_name).eval()
                return self.type(item) if item else self.default
            else:
                return self.default
        except Exception as e:
            print(e)
            return self.default

    def __set__(self, obj, value):
        browser = getattr(obj, "browser", None)
        if browser:
            initial = browser.sessionStorage.getItem(self.public_name)
            browser.sessionStorage.setItem(self.public_name, value)

            if initial:
                self.onchange(obj)(initial, value)
    
    def __set_name__(self, owner, name):
        self.public_name = name

        if self.initial:
            self.__set__(owner, self.initial)

def default_apply(element, value):
    element.innerText = f"{value}"

def bind(element, value=None, apply=None):
    def onchange(initial, current):
        (apply or default_apply)(element, current)
    
    if isinstance(value, Reactive):
        value.set_onchange(onchange)
        return value
    else:
        reactive = Reactive(value, onchange)
        return reactive

class HTML:
    html: HTMLDocument
    body: HTMLBodyElement
    head: HTMLHeadElement
    script: HTMLScriptElement
    style: HTMLStyleElement
    h1: HTMLHeadingElement
    h2: HTMLHeadingElement
    h3: HTMLHeadingElement
    h4: HTMLHeadingElement
    h5: HTMLHeadingElement
    h6: HTMLHeadingElement
    p: HTMLParagraphElement

    def __init__(self, context=None):
        self.context = context
        # self.context.custom_tasks["update_dom"] = self.handle_dom_update
        # self.context.setDom(document)
        self.document: Document = None
        self._main: Element = None

    def handle_child_list(self, added, removed, target):
        try:
            target = self.document.evaluate(target, None, self.document, XPathResult.FIRST_ORDERED_NODE_TYPE)[0]
            for item in added:
                element = self.make_element(item)
                target.appendChild(element)
            for item in removed:
                target.removeChild(self.document.evaluate(item["xpath"], None, self.document, XPathResult.FIRST_ORDERED_NODE_TYPE)[0])
        except:
            pass

    def make_element(self, mod):
        nodetype = mod.pop("type")
        if nodetype== "ElementNode":
            element = document.createElement(mod["nodeName"].lower())
        elif nodetype == "TextNode":
            element = document.createTextNode(mod["data"])
        return element

    def handle_dom_update(self, req):
        mods = req["modifications"]
        for mod in mods:
            if mod["type"] == "childList":
                self.handle_child_list(mod["addedNodes"], mod["removedNodes"], target=mod["target"])

    def __getattr__(self, name):
        target = globals().get(name, None)
        if target:
            def wrapper(*a, **kw) -> Element:
                new = {}
                for (key, value) in kw.items():
                    if not isinstance(value, (str, int, float)):
                        temp_name = getattr(value, "__name__", f"temp_func_{random.randint(0, 100000000)}")

                        if self.context:
                            if temp_name == "<lambda>":
                                temp_name= f"temp_func_{random.randint(0, 100000000)}"
                            if not hasattr(self.context, temp_name):
                                self.context.__register__(temp_name, value)
                        value = """server.%s()"""%temp_name
                    new[key] = value
                # if name == "html":
                #     _page = HtmlPage(html="")
                #     context = self.context

                #     HtmlPage.pageMap[_page.pageid] = context.uid
                #     HtmlPage.pageActive[_page.pageid] = time.time()

                #     tag = target(script("var UID='{}';\nvar PAGEID='{}';\n".format(context.uid, _page.pageid), JYSERVER), *a, script(JYSERVER_AFTER), **new)
                #     self._main = tag
                #     self.document = tag.ownerDocument
                # else:
                tag = target(*a, **new)
                return tag
            return wrapper
        raise AttributeError()
    
    def __call__(self, *a, **kw):
        return self.html(*a, **kw)
