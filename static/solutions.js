/*
 * solutions.js
 *
 * AJAXes the /list endpoint to build a list of links to solution files.
 */


function load_json(url, continuation) {
  var xobj = new XMLHttpRequest();
  xobj.overrideMimeType("application/json");
  xobj.open("GET", url);
  xobj.onload = function () {
    var successful = (
      xobj.status == 200
   || (xobj.status == 0 && url.startsWith("file://"))
    );
    if (!successful) {
      console.log(
        "XMLHttpRequest failed for URL '" + url + "' with status " + xobj.status
      );
    } else {
      let json;
      try {
        json = JSON.parse(xobj.responseText);
      } catch (e) {
        console.log("XMLHttpRequest for URL '" + url + "' got invalid JSON:");
        console.log(xobj.responseText);
        console.log(e);
      }
      continuation(json);
    }
  }
  xobj.onerror = function () {
    console.log("XMLHttpRequest for URL '" + url + "' crashed.");
  }
  try {
    xobj.send(null);
  } catch (e) {
    console.log("XMLHttpRequest for URL '" + url + "' crashed.");
    console.log(e);
  }
}

function build_solution_links(solutions_map) {
  elem = build_link_list("Solutions", "solution", solutions_map);
  document.getElementById("solution_display").appendChild(elem);
}

function build_link_list(title, prefix, map) {
  var result = document.createElement("details");
  result.setAttribute("open", true);
  var sum = document.createElement("summary");
  result.appendChild(sum);
  sum.innerHTML = title;
  var here = Object.keys(map);
  here.sort();
  for (let key of here) {
    if (map[key] == "F") { // a file: link to it
      link = document.createElement("a");
      link.classList.add("solution_file");
      if (prefix == "") {
        link.href = key;
      } else {
        link.href = prefix + '/' + key;
      }
      link.target = "_" + key;
      link.innerHTML = key;
      result.appendChild(link);
    } else { // a directory: recurse
      if (prefix == "") {
        sub = key;
      } else {
        sub = prefix + "/" + key;
      }
      var entry = build_link_list(key, sub, map[key]);
      result.appendChild(entry);
    }
  }

  return result;
}


// To be run on load:
function setup() {
  load_json("list", build_solution_links);
}
