$.postJSON = function(url, data, callback) {
    $.post(url, data, callback, "json");
}

$(document).ready(function() {
    $('a.external').attr('target','new');
    $('.delete').click(function(l) {
        if (!confirm('Are you sure you want to delete this entry?')) {
            return
        }
        var entry = $(this).parents('.entry');
        $.postJSON('/delete', {key: entry.attr('id')}, function(data) {
            if (data.success) {
                entry.slideUp();
            }
        });
    });
    $('.deletecomment').click(function(l) {
        if (!confirm('Are you sure you want to delete this item?')) {
            return
        }
        var comment = $(this).parents('.entry');
        $.postJSON('/deleteitem', {key: comment.attr('id')}, function(data) {
            if (data.success) {
                comment.slideUp();
            }
        });
    });

    $('.reply').click(function(l) {
        cid = $(this).attr("cid")
        to_url = "/comment/" + cid
        to_title = "comment #" + cid
        $("input[name='to_url']").val(to_url);
        $("input[name='to_title']").val(to_title);
        $("textarea")[0].focus();

    });

});

function toggle(button) {
    if (button.className == "open-button") {
        jQuery(button).parent().next().slideUp(function() {
            jQuery(button).removeClass().addClass("closed-button");
        }).removeClass().addClass('closed month_entries');
    } else {
        jQuery(button).parent().next().slideDown(function() {
            jQuery(button).removeClass().addClass("open-button");
        }).removeClass().addClass('open month_entries');
    }
}

function togglemenu() {
    var x = document.getElementById("menu");
    var y = document.getElementById('toggle');
    if (x.className === "pure-menu pure-menu-horizontal") {
        x.className += " responsive";
        y.className += ' x';
    } else {
        x.className = "pure-menu pure-menu-horizontal";
        y.className = 'icon';
    }
}