"use strict";

window.addEventListener("load", function() {
    const formsets = this.document.querySelectorAll(".deleteable");

    for (let i = 0; i < formsets.length; i += 1) {
        attachDeleteHandler(formsets[i]);
    }
});

window.addEventListener("load", function() {
    const links = this.document.querySelectorAll("a.fieldset-add");
    for (let i = 0; i < links.length; i += 1) {
        attachFieldsetHandler(links[i]);
    }
});

function attachFieldsetHandler(link) {
    const template = document.getElementById(link.getAttribute("template"));
    const total = document.getElementById(link.getAttribute("counter"));
    const parentnode = document.getElementById(link.getAttribute("parentnode"));

    if (!(template || total || parentnode)) { return; }

    const templatenode = Array.from(template.content.childNodes).filter(
        node => !((node.nodeType == Node.TEXT_NODE && !node.textContent.trim()))
    )[0];

    link.addEventListener("click", function() {
        const newempty = document.importNode(templatenode, true);
        console.log(newempty);
        newempty.classList.add("invisible")

        // Increment the form counter that Django uses internally
        const prefix = parseInt(total.value)
        total.value = prefix + 1;

        const nodes = newempty.querySelectorAll("label, input, select, textarea");
        for (let i = 0; i < nodes.length; i +=1) {
            const node = nodes[i];
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

        parentnode.appendChild(newempty);
        newempty.classList.remove("hidden");
        newempty.focus(); // A cludge to trigger a redraw and allow the opacity transition to show
        newempty.classList.remove("invisible");
    });
}

function attachDeleteHandler(formset) {
    const checkbox = formset.querySelector(".field-DELETE input[type='checkbox']");
    if (!checkbox) { return; }

    const label = formset.querySelector("label[for='" + checkbox.id + "']");
    if (label) { label.classList.add("hidden"); }

    const link = document.createElement("a");
    link.innerHTML = "<span>Delete</span>"
    link.classList.add("delete-formset");

    checkbox.parentNode.insertBefore(link, checkbox);
    checkbox.classList.add("hidden");

    link.addEventListener("click", function() {
        checkbox.checked = true;
        formset.addEventListener("transitionend", function() {
            this.classList.add("hidden");
        });
        formset.classList.add("invisible");
    });
}
