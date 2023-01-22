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

  return "//" + path;
}

function get_element_index(node) {
  var temp = [];
  var parentChildrens = node.parentElement?.children || [];
  var childrenNr = node.parentElement.children?.length || 0;

  for (var i = 0; i <= childrenNr; i++) {
    if (typeof parentChildrens[i] !== "undefined") {
      if (parentChildrens[i].tagName.toLowerCase() == node.localName) {
        temp.push(parentChildrens[i]);
      }
    }
  }

  return temp;
}
