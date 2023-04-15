/*
This is the Javascript code that gets injected into the HTML
page.

server            
	Proxy class for asynchronous execution of commands
	on the server. This class does not return a value.

app               
	Proxy class that for synchronous exection. Will
	return a value. However, if used while a page
	update is in progress, it will fail.

Other functions used internally:

evalBrowser()    
	Queries the server for any pending commands. If
	there are no pending commands, the connection
	is kept open by the server until a pending
	command is issued, or a timeout. At the end of
	the query, the function gets scheduled for execution
	again. We schedule it instead of calling so we
	don't overflow the stack.

sendFromBrowserToServer(e, q) 
	Evaluate expression `e` and then send the results
	to the server. This is used by the server to
	resolve Javascript statements.

sendErrorToServer(e)
	Send a client expcetion to the server for error
	handling.

closeBrowserWindow()
	Called when a page is terminated so server can
	stop processing it.
*/

if (typeof UID === "undefined") {
  UID = "COOKIE";
}
if (typeof PAGEID === "undefined") {
  PAGEID = "COOKIE";
}

var ws = new WebSocket("ws://localhost:8080/_process_srv0");
let tasks = [];

function send(message) {
  if (ws.readyState == ws.OPEN) {
    try {
      ws.send(message);
    } catch (err) {
      tasks.push(() => {
        ws.send(message);
      });
    }
  } else if (ws.readyState == ws.CLOSED || ws.readyState == ws.CLOSING) {
    console.log("WebSocket Closed.");
  } else {
    tasks.push(() => {
      send(message);
    });
  }
}

let intervalId = setInterval(() => {
  if (tasks) {
    for (let index = 0; index < tasks.length; index++) {
      let task = tasks.shift();
      task && task();
    }
  }
}, 1);

recieve = (message) => {
  return new Promise((resolve, reject) => {
    let formerOnMessage = ws.onmessage;
    ws.onmessage = function (ev) {
      resolve(ev.data || "{}");
      ws.onmessage = formerOnMessage;
    };
    message && send(message);
  });
};

ws.onmessage = function (ev) {
  let response = ev.data;
  console.log("response:", response);
  if (response) {
    let is_json = true;
    let result;


    try {
      result = JSON.parse(response);
    } catch (err) {
      is_json = false;
    }

    if (!is_json) {
      try {
        //console.log("Next async task", request.responseText) // DEBUG
        eval(response);
        // setTimeout(evalBrowser, 1);
      } catch (e) {
        console.log("ERROR", e.message); // DEBUG
        setTimeout(() => {
          sendErrorToServer(response, e.message);
          //   evalBrowser();
        }, 1);
      }
    } else {
      if (result.error) {
        console.log("ERROR", result["error"]);
        throw result["error"];
        // return null;
      }
      if (result["type"] == "expression") {
        return eval(result["expression"]);
      } else {
        return result["value"];
      }
    }
  }
};

ws.onerror = (ev) => {
  console.log("ERROR async: ", ev.data);
};

function evalBrowser() {
  send(JSON.stringify({ session: PAGEID, task: "next" }));
}
function sendFromBrowserToServer(expression, query) {
  var value;
  var error = "";
  try {
    //console.log("Evaluate", query, expression) // DEBUG
    value = eval(expression);
    //console.log("Result", value)
  } catch (e) {
    value = 0;
    error = e.message + ": '" + expression + "'";
    console.log("ERROR", query, error);
  }
  send(
    JSON.stringify({
      session: PAGEID,
      task: "state",
      value: value,
      query: query,
      error: error,
    })
  );
}
function sendErrorToServer(expr, e) {
  send(
    JSON.stringify({ session: PAGEID, task: "error", error: e, expr: expr })
  );
}

let formatters = {
  int: (prop, x) => new Number(x.value),
  str: (prop, x) => new String(x.value),
  list: (prop, x) => new Array(x.value),
  dict: (prop, x) => x,
  set: (prop, x) => new Set(x.value),
  function: (prop, x) => {
    return function (...args) {
      return send(
        JSON.stringify({
          session: PAGEID,
          task: "async",
          function: prop,
          args: args,
        })
      );
    };
  },
  method: (prop, x) => {
    return function (...args) {
      return send(
        JSON.stringify({
          session: PAGEID,
          task: "async",
          function: prop,
          args: args,
        })
      );
    };
  },
  callable_proxy: (prop, x) => {
    return function (...args) {
      return new Promise((resolve, reject) => {
        function get_result(response) {
          console.log(x, response);
          if (response.error) {
            reject(response.error);
          }
          let formatter = formatters[response.type];
          if (response.location) {
            resolve(PyProxy(response));
          } else if (formatter) {
            resolve(formatter(property, response));
          }
          reject("No attribute name: " + prop);
        }

        recieve(
          JSON.stringify({
            session: PAGEID,
            task: "call_proxy",
            target: x.location,
            args: args,
          })
        ).then((result) => {
          console.log("Res", result);
          get_result(JSON.parse(result));
        });
      });
    };
  },
};

function closeBrowserWindow() {
  send(JSON.stringify({ session: PAGEID, task: "unload" }));
}
var server = new Proxy(
  {},
  {
    get(target, property) {
      return new Promise((resolve, reject) => {
        function get_result(response) {
          let formatter = formatters[response.type];
          if (response.location) {
            return PyProxy(response);
          } else if (formatter) {
            return formatter(property, response);
          }
        	return undefined;
        }

        recieve(
          JSON.stringify({
            session: PAGEID,
            task: "attribute",
            item: property,
          })
        ).then((result) => {
          result = get_result(JSON.parse(result));
		  if (result == undefined) {
			if (property !== "then") {
				reject("No attribute name: " + property)
			}
		  } else {
			resolve(result)
		  }
        });
      });
    },
  }
);
function handleApp(property, args) {
  send(
    JSON.stringify({
      session: PAGEID,
      task: "run",
      block: true,
      function: property,
      args: args,
    })
  );
}
function handleAppProperty(property) {
  send(
    JSON.stringify({
      session: PAGEID,
      task: "get",
      block: true,
      expression: property,
    })
  );
}
function handleAppSetProperty(property, value) {
  send(
    JSON.stringify({
      session: PAGEID,
      task: "set",
      property: property,
      value: value,
    })
  );
  return value;
}
app = new Proxy(
  {},
  {
    get: function (target, prop) {
      return handleAppProperty(prop);
    },
    set: function (target, prop, value) {
      return handleAppSetProperty(prop, value);
    },
  }
);

function PyProxy(res) {
  let proxy = new Proxy(
    {},
    {
      get(target, property) {
        return new Promise((resolve, reject) => {
          function get_result(response) {
            if (response.error) {
              reject(response.error);
            }
            let formatter = formatters[response.type];
            if (response.location) {
               return PyProxy(response);
            } else if (formatter) {
               return formatter(property, response);
            }
            return undefined;
          }

          recieve(
            JSON.stringify({
              session: PAGEID,
              task: "get_proxy_attribute",
              prop: property,
              target: res.location,
            })
          ).then((result) => {
			result = get_result(JSON.parse(result));
			if (result == undefined) {
				if (property !== "then") {
					reject("No attribute name: " + property)
				}
			} else {
				resolve(result)
			}
		  });
        });
      },
      set(target, property, value) {
        return new Promise((resolve, reject) => {
          recieve(
            JSON.stringify({
              session: PAGEID,
              task: "set_proxy_attribute",
              prop: property,
              target: res.location,
              value: value,
            })
          ).then((result) => resolve(JSON.parse(result).value));
        });
      },
      ownKeys(target) {
        return new Promise((resolve, reject) => {
          recieve(
            JSON.stringify({
              session: PAGEID,
              task: "get_proxy_attributes",
              target: res.location,
            })
          ).then((result) => {
            resolve(Object.keys(JSON.parse(result).value));
          });
        });
      },
      deleteProperty(target, prop) {
        // to intercept property deletion
        return new Promise((resolve, reject) => {
          recieve(
            JSON.stringify({
              session: PAGEID,
              task: "delete_proxy_attribute",
              prop: property,
              target: res.location,
              value: prop,
            })
          ).then((result) => resolve(JSON.parse(result).value));
        });
      },
      has(target, prop) {
        return new Promise((resolve, reject) => {
          recieve(
            JSON.stringify({
              session: PAGEID,
              task: "has_proxy_attribute",
              prop: property,
              target: res.location,
              value: prop,
            })
          ).then((result) => resolve(JSON.parse(result).value));
        });
      },
      apply(target, thisArg, args) {
        return new Promise((resolve, reject) => {
          function get_result(response) {
            if (response.error) {
              reject(response.error);
            }
            let formatter = formatters[response.type];
            if (response.location) {
              resolve(PyProxy(response));
            } else if (formatter) {
              resolve(formatter(property, response));
            }
            reject("No attribute name: " + property);
          }

          recieve(
            JSON.stringify({
              session: PAGEID,
              task: "call_proxy",
              target: res.location,
              args: args,
            })
          ).then((result) => get_result(JSON.parse(result)));
        });
      },
    }
  );
  return proxy;
}

window.addEventListener("beforeunload", () => {
  closeBrowserWindow();
});

ws.onopen = () => {
  while (tasks.length < 1 && ws.readyState == 1) {
    clearInterval(intervalId);
    return null;
  }
};

function xpath_generator(e) {
  var node = e;

  var temp_one = get_element_index(node);
  var last_node_index = Array.prototype.indexOf.call(temp_one, node);

  if (temp_one.length == 1) {
    var path = "/" + node.localName;
  } else if (temp_one.length > 1) {
    last_node_index = last_node_index + 1;
    var path = "/" + node.localName + "[" + last_node_index + "]";
  }

  while (node != document.html && node.parentNode !== null) {
    node = node.parentNode;

    /* When loop reaches the last element of the dom (body)*/
    if (node.localName == "body") {
      var current = "/body";
      path = current + path;
      break;
    }

    /* if the node has id attribute and is not the last element */
    if (node.id != "" && node.localName != "body") {
      var current = "/" + node.localName + "[@id='" + node.id + "']";
      path = current + path;
      break;
    }

    /* if the node has class attribute and has no id attribute or is not the last element */
    if (node.id == "" && node.localName != "body") {
      if (node.parentNode !== null) {
        var temp = get_element_index(node);
        var node_index = Array.prototype.indexOf.call(temp, node);

        if (temp.length == 1) {
          var current = "/" + node.localName;
        } else if (temp.length > 1) {
          node_index = node_index + 1;
          var current = "/" + node.localName + "[" + node_index + "]";
        }
      }
    }

    path = current + path;
  }

  return "/" + path;
}

function get_element_index(node) {
  var temp = [];
  var parentChildrens = node.parentElement?.children || [];
  var childrenNr = node.parentElement?.children.length || 0;

  for (var i = 0; i <= childrenNr; i++) {
    if (typeof parentChildrens[i] !== "undefined") {
      if (parentChildrens[i].tagName.toLowerCase() == node.localName) {
        temp.push(parentChildrens[i]);
      }
    }
  }

  return temp;
}

var m = [];
var observer = new MutationObserver((mutations) => {
  for (const mutation of mutations) {
    m.push({
      addedNodes: ELementsToList(mutation.addedNodes),
      attributeName: mutation.attributeName,
      attributeNamespace: mutation.attributeNamespace,
      nextSibling: ELementToDict(mutation.nextSibling),
      oldValue: mutation.oldValue,
      previousSibling: ELementToDict(mutation.previousSibling),
      removedNodes: ELementsToList(mutation.removedNodes),
      target: xpath_generator(mutation.target),
      type: mutation.type,
    });
  }
  send(
    JSON.stringify({
      session: PAGEID,
      task: "update_dom",
      modifications: m,
    })
  );
});

function ELementToDict(element) {
  if (element?.nodeType === 1) {
    return html2json(element.outerHTML);
  }
  return {};
}

function ELementsToList(elements) {
  let ret = [];
  elements.forEach((item) => {
    ret.push(ELementToDict(item));
  });
  return ret;
}
