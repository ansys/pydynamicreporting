$(document).ready(function () {
    // show/hide panel templates
    $(".panel-expander").click(function (e) {
        // get the target to toggle
        let templateDiv = $(this).attr("data-target-panel");
        // toggle
        $(templateDiv).toggle();
        // toggle plus and minus icons in panels
        updateToggle(this);
    });

    // regenerate elements in target tab, when switching tabs.
    $('a[data-toggle="tab"]').on('show.bs.tab', function (e) {
        const target = e.target.getAttribute('href');
        const panzooms = $(`${target} .panzoom-div`);
        panzooms.each(function () {
            const parentId = $(this).attr("data-parent-id");
            // not always available
            if (window[`panZoomUI_${parentId}`].initPanzoom) {
                const section = $(this).attr("data-section-name");
                // re-init panzoom
                window[`panZoomUI_${parentId}`].initPanzoom(section, true);
            }
        });
    });

    /*listen to anchor clicks, find the hidden element and go up ancestors.
    - if it's inside a tab, activate
    - if it's inside a panel, show
    - if it's inside a tree, expand */
    $('#report_root').on('click', '.toc_root a, a.nexus-link, a.nexus-anchor', function (e) {
        const targetNode = document.querySelector(this.getAttribute('href'));
        // if it's an actual link, exit
        if (!targetNode) {
            return;
        }
        // don't jump to the anchor yet.
        e.preventDefault();
        let parent = targetNode.parentNode;
        let loadQueue = new Queue();
        let loadTracker = new Map();
        while (parent.id !== "report_root") {
            // check if its hidden
            const $parent = $(parent);
            if ($parent.css("display") === "none" || $parent.css("visibility") === "collapse") {
                // unhide it
                const guid = baseUtils.getUniqueId();
                if ($parent.hasClass("tab-pane")) {
                    loadQueue.enqueue(guid);
                    loadTracker.set(guid, false);
                    const nav = $(`a.nav-link[href='#${parent.id}']`);
                    const setLoaded = (event) => {
                        loadTracker.set(guid, true);
                        $(event.currentTarget).off("shown.bs.tab", setLoaded);
                    };
                    // this is async so wait for it.
                    nav.on("shown.bs.tab", setLoaded);
                    nav.tab("show");
                } else if ($parent.hasClass("card-body")) {
                    loadQueue.enqueue(guid);
                    $parent.show();
                    loadTracker.set(guid, true);
                    const expander = $(`.panel-expander[data-target-panel="#${parent.id}"]`);
                    updateToggle(expander);
                } else if ($parent.hasClass("tree-row")) {
                    loadQueue.enqueue(guid);
                    let grandParentId = $parent.attr("data-parent");
                    while (grandParentId !== '0') {
                        const grandParent = document.getElementById(grandParentId);
                        expandSubtree(grandParent);
                        grandParentId = $(grandParent).attr("data-parent");
                    }
                    loadTracker.set(guid, true);
                }
            }
            // move up
            parent = parent.parentNode;
        }

        while (!loadQueue.isEmpty()) {
            const divGuid = loadQueue.peek();
            if (loadTracker.get(divGuid))
                loadQueue.dequeue();
        }

        // scroll
        const nav = $("#main_navbar_container");
        const extraOffset = 15;
        const nodePos = $(targetNode).offset().top - extraOffset;
        let offset = nav.length > 0 ? nodePos - nav.height() : nodePos;
        $('html, body').animate({scrollTop: offset}, 1000);
    });
});