/*
* Common report item functionality goes here.
* */
// toggle plus and minus icons in panels
const updateToggle = toggle => {
    $(toggle).toggleClass('fa-plus').toggleClass('fa-minus');
};

function getNodeState(collapse) {
    let currIcon = 'fa-plus', targetIcon = 'fa-minus';
    let currState = 'tree-collapsed', targetState = 'tree-expanded';
    let targetDisplay = '';
    if (collapse) {
        currIcon = 'fa-minus';
        targetIcon = 'fa-plus';
        currState = 'tree-expanded';
        targetState = 'tree-collapsed';
        targetDisplay = 'none';
    }
    return {currIcon, targetIcon, currState, targetState, targetDisplay}
}

function updateNodeState(node, state) {
    if ($(node).hasClass('tree-parent')) {
        const toggleDiv = $(node).find('.sub-tree-toggle');
        const {currIcon, targetIcon, currState, targetState} = state;
        $(toggleDiv).removeClass(currIcon).addClass(targetIcon);
        $(node).removeClass(currState).addClass(targetState);
    }
}

function getChildren(treeId, nodeId) {
    return Array.from($(`#${treeId}`).find(`[data-parent="${nodeId}"]`));
}

function getDescendants(treeId, nodeId) {
    let descendants = [];
    if ($(`#${nodeId}`).hasClass('tree-parent')) {
        let children = getChildren(treeId, nodeId);
        children.forEach((child) => {
            descendants.push(child);
            descendants = descendants.concat(getDescendants(treeId, child.id));
        });
    }
    return descendants;
}

function isAnyParentCollapsed(node) {
    const parentId = $(node).attr("data-parent");
    // root element
    if (parentId === "0") {
        return false;
    } else {
        const parent = document.getElementById(parentId);
        return $(parent).hasClass('tree-collapsed') ? true : isAnyParentCollapsed(parent);
    }
}

function treeToggleAll(treeId, collapse) {
    const rootNodes = getChildren(treeId, 0);
    rootNodes.forEach((root) => {
        // update root state first
        const state = getNodeState(collapse);
        updateNodeState(root, state);
        // update descendants
        const descendants = getDescendants(treeId, root.id);
        descendants.forEach((desc) => {
            updateNodeState(desc, state);
            // toggle display
            desc.style.display = state.targetDisplay;
        });
    });
}

function toggleSubtree(treeId, currNodeId, collapse) {
    const currNode = document.getElementById(currNodeId);
    const state = getNodeState(collapse);
    // toggle icon and state
    updateNodeState(currNode, state);
    // toggle display
    const descendants = getDescendants(treeId, currNodeId);
    descendants.forEach((desc) => {
        const descState = getNodeState(isAnyParentCollapsed(desc));
        desc.style.display = descState.targetDisplay;
    });
}

function expandSubtree(currNode) {
    const treeId = $(currNode).attr("data-tree");
    toggleSubtree(treeId, currNode.id, false);
}

$(document).ready(function () {
    $('.sub-tree-toggle').click(function (e) {
        // get the target to toggle
        const currNodeId = $(this).attr("data-target-node");
        const currNode = document.getElementById(currNodeId);
        const treeId = $(currNode).attr("data-tree");
        const collapse = $(currNode).hasClass('tree-expanded');
        toggleSubtree(treeId, currNodeId, collapse);
    });

    //tree expand/collapse
    $('.tree-collapse-all').click(function (e) {
        const treeId = $(this).attr("data-target-tree");
        treeToggleAll(treeId, true);
    });
    $('.tree-expand-all').click(function (e) {
        const treeId = $(this).attr("data-target-tree");
        treeToggleAll(treeId, false);
    });
});