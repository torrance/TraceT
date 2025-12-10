"use strict";

window.addEventListener("load", function() {
    var nodes = this.document.querySelectorAll("fieldset.deleteable");

    for (var i = 0; i < nodes.length; i += 1) {
        attachDeleteHandler(nodes[i]);
    }
});

window.addEventListener("load", function() {
    var links = this.document.querySelectorAll("a.fieldset-add");
    for (var i = 0; i < links.length; i += 1) {
        attachFieldsetHandler(links[i]);
    }
});

window.addEventListener("load", function() {
    var inputs = this.document.querySelectorAll(".overrideable-lock");
    for (var i; i < inputs.length; i += 1) {
        attachLockHandler(inputs[i]);
    }
});

function attachFieldsetHandler(link) {
    var emptytemplate = document.getElementById(link.getAttribute("template"));
    var total = document.getElementById(link.getAttribute("counter"));

    link.addEventListener("click", function() {
        var newempty = emptytemplate.cloneNode(true);
        newempty.classList.add("invisible")
        newempty.id = ""

        // Increment the form counter that Django uses internally
        var prefix = parseInt(total.value)
        total.value = prefix + 1;

        var nodes = newempty.querySelectorAll("label, input, select, textarea");
        for (var i = 0; i < nodes.length; i +=1) {
            var node = nodes[i];
            if (node.getAttribute("id")) {
                node.setAttribute("id", node.getAttribute("id").replace("__prefix__", prefix));
            };
            if (node.getAttribute("name")) {
                node.setAttribute("name", node.getAttribute("name").replace("__prefix__", prefix));
            };
            if (node.getAttribute("for")) {
                node.setAttribute("for", node.getAttribute("for").replace("__prefix__", prefix));
            };
        };

        attachDeleteHandler(newempty);
        var links = newempty.querySelectorAll("a.fieldset-add");
        for (var i = 0; i < links.length; i += 1) {
            attachFieldsetHandler(links[i]);
        }

        var ul = link.closest("ul");
        ul.parentNode.insertBefore(newempty, ul);
        newempty.classList.remove("hidden");
        newempty.focus(); // A cludge to trigger a redraw and allow the opacity transition to show
        newempty.classList.remove("invisible");
    });
}

function attachDeleteHandler(fieldset) {
    fieldset.querySelector("div.field.DELETE").style.display = "none";

    var del = document.createElement("div");
    del.classList.add("delete-button");

    fieldset.insertBefore(del, fieldset.childNodes[0]);

    del.onclick = function() {
        var fieldset = this.closest("fieldset");
        var checkbox = fieldset.querySelector("div.field.DELETE input[type=checkbox]");
        checkbox.checked = true;

        fieldset.focus();
        fieldset.addEventListener("transitionend", function() {
            console.log("End of transition!");
            this.classList.add("hidden");
        });

        fieldset.classList.add("invisible");
    };
}
