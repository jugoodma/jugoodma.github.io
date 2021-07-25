console.log("Welcome, traveler.");

function sortTags(key) {
    let sortKey = null;
    if (key == 0) {
        // alphabetic
        sortKey = function(a,b) {
            function strcmp(a,b) {   
                return (a<b?-1:(a>b?1:0));  
            }
            return strcmp(a.textContent,b.textContent);
        };
    } else if (key == 1) {
        // numeric
        sortKey = function(a,b) {
            return parseInt(a.getAttribute('data-count')) - parseInt(b.getAttribute('data-count'));
        };
    } else {
        return;
    }
    // https://stackoverflow.com/a/8837300
    let ul = document.getElementById('tag-list');
    let new_ul = ul.cloneNode(false);
    let lis = [];
    for (var i = ul.childNodes.length; i--;) {
        if (ul.childNodes[i].nodeName === 'LI')
            lis.push(ul.childNodes[i]);
    }
    lis.sort(sortKey);
    for (var i = 0; i < lis.length; i++)
        new_ul.appendChild(lis[i]);
    ul.parentNode.replaceChild(new_ul, ul);
}
let list = document.querySelectorAll(".tag-sort-option"); // document-ordered
for (var i = list.length; i--;) { // reverse
    list[i].onchange = (function(k) { return function(){sortTags(k)}; })(i); // gotta use IIFE to create closure to save value of 'i'
}

function updatePosts(tag,hide) {
    // console.log(tag,hide);
    let list = document.querySelectorAll("#posts > li");
    for ( var i = list.length; i--; ) {
        // tag delimiter == |
        // TODO -- fix this lmao
        if (list[i].getAttribute('data-tags').split("|").includes(tag)) {
            if (hide)
                list[i].style.visibility = "hidden";
            else
                list[i].style.visibility = "visible";
        }
        // yea lmao make this nicer
        // we could remove/add things to update the list indices (for display instead of visibile)
        // but also gotta save the state of selected tags for better filtering
    }
}
list = document.querySelectorAll("#tag-list > li");
for (var i = list.length; i--;) {
    list[i].onclick = function(e) {
        let hide = e.target.classList.contains("active");
        if (hide)
            e.target.classList.remove("active")
        else
            e.target.classList.add("active")
        updatePosts(e.target.getAttribute("data-tag"),hide);
    };
}
