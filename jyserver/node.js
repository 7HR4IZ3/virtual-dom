PyProxy = (_class) => {
  let proxy = new Proxy(
    (_class),
    {
      get: function (target, property) {
        // console.log("get called");
        if (target[property]) {
        	return target[property]
        }
        return target.__getattr__?.bind(target)(property);
      },
      set: function (target, property, value) {
        if (target[property]) {
        	target[property] = value;
        	return true
        }
        return target.__setattr__?.bind(target)(property, value);
      },
      ownKeys: function (target) {
        console.log("own_keys called");
        return target.__ownkeys__?.bind(target)(prop);
      },
      deleteProperty: function (target, prop) {
        // to intercept property deletion
        console.log("delete called");
        return target.__delattr__?.bind(target)(prop);
      },
      has: function (target, prop) {
        console.log("has called");
        return target.__hasattr__?.bind(target)(prop);
      },
      apply: function (target, _thisArg, args) {
        console.log("apply called");
        return target.__call__?.bind(target)(...args);
      },
      construct: function (target, args) {
        console.log("new called");
        return target.__construct__?.bind(target)(...args);
      },
      getPrototypeOf: function(target) {
        console.log("get prototype called");
        return Object.prototype;
      },
      defineProperty: function(target, property, attribute) {
        console.log("define called");
        return true;
      }
    }
  );
  return proxy;
};

// a = PyProxy();
// a.name;
// a.age = "Yes";
// "yes" in a
// delete a.name
// a()
// new a

class PythonProxy {
	__getattr__(name) {
		console.log("Get attribute", name, typeof name)
	}

	__setattr__(name, value) {
		this[name] = value;
	}
}

let a = PyProxy(new PythonProxy());

// a = new py();
a.name;
a.age = "Yes";
console.log(a.age)
"yes" in a
delete a.name

