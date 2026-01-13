"use strict";

window.addEventListener("load", function () {
    const formsets = this.document.querySelectorAll(".deleteable")
        .forEach(attachDeleteHandler);
});

window.addEventListener("load", function () {
    this.document.querySelectorAll("a.fieldset-add").forEach(attachFieldsetHandler);
});

function attachFieldsetHandler(link) {
    const template = document.getElementById(link.getAttribute("template"));
    const total = document.getElementById(link.getAttribute("counter"));
    const parentnode = document.getElementById(link.getAttribute("parentnode"));

    if (!(template || total || parentnode)) { return; }

    const templatenode = Array.from(template.content.childNodes).filter(
        node => !((node.nodeType == Node.TEXT_NODE && !node.textContent.trim()))
    )[0];

    link.addEventListener("click", function () {
        const newempty = document.importNode(templatenode, true);
        newempty.classList.add("invisible")

        // Increment the form counter that Django uses internally
        const prefix = parseInt(total.value)
        total.value = prefix + 1;

        newempty.querySelectorAll("a, label, input, select, textarea, template")
            .forEach(node => {
                Array.from(node.attributes)
                    .filter(a => a.specified)
                    .forEach(a => a.value = a.value.replace("__prefix__", prefix));
            });

        // Attach handlers
        attachDeleteHandler(newempty);
        newempty.querySelectorAll("a.fieldset-add").forEach(attachFieldsetHandler);

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

    link.addEventListener("click", function () {
        checkbox.checked = true;
        formset.addEventListener("transitionend", function () {
            this.classList.add("hidden");
        });
        formset.classList.add("invisible");
    });
}

window.addEventListener("load", function () {
    this.document.querySelectorAll("form:not([disabled]) table.trigger-list tbody").forEach(el => {
        Sortable.create(el, {
            group: "triggerlists",
            forceFallback: true,
            handle: ".trigger-handle",
            onEnd: ev => {
                // First, update active status based on data attribute of table
                const status = ev.item.closest("table.trigger-list").getAttribute("data-trigger-active") == "active";
                let input = ev.item.querySelector(".field.active input[type='checkbox']");

                this.window.setTimeout(function () {
                    // This is a hack: it seems like something is overriding changes to
                    // the checked property after this callback runs. If we set it
                    // in a timeout it doesn't get overridden.
                    input.checked = status;
                }, 100);

                // Secondly, reassign priorities to each item
                const trs = ev.to.querySelectorAll("tr:not(.empty-list)")
                trs.forEach((node, i) => {
                    const priority = node.querySelector(".field.priority input[type='number']");
                    if (priority) {
                        priority.value = trs.length - i;
                        priority.dispatchEvent(new Event("change"))
                    }
                });
            },
        });
    });

    this.document.querySelectorAll("form:not([disabled]) table.trigger-list .trigger-handle").forEach(el => {
        el.classList.remove("hidden");
    });

    this.document.querySelectorAll("table.trigger-list .field.priority input, table.trigger-list .field.active").forEach(el => {
        el.classList.add("hidden");
    });
});

window.addEventListener("load", function () {
    // This little guy mirrors the value of <input> - allowing us to hide the input (and set it programatically)
    // but provide user feedback on its current value. We use this when setting the trigger priority.
    this.document.querySelectorAll("[data-mirror-input]").forEach(el => {
        const source = this.document.querySelector(el.getAttribute("data-mirror-input"));

        if (source) {
            el.textContent = source.value;
            source.addEventListener("change", function () {
                el.textContent = source.value;
            });
        }
    });
});
