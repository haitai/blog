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

    var b=jQuery("#yui-main > .yui-b"),
    d=jQuery("#sidebar");
    if(b.length){
        var e=jQuery('<div id="collapsible-arrow">'),
        i=jQuery('<div id="collapsible">'),
        k=function(o){
            var p=d.offset(),eo=p.left+12;
            if(d.is(":hidden")){
                e.css({left:"auto",right:"12px",top:(o.pageY||o.clientY)+"px"})}
            else
                e.css({left:eo+"px",top:(o.pageY||o.clientY)+"px"})};

        b.css("position","relative").append(i);
        jQuery(document.body).append(e);
        jQuery.browser.msie&&jQuery.browser.version<7&&b.css("right","-5px");
        b.is(".skip-collapsible")||i.mouseover(function(o){
            i.addClass("hover");
            if(d.is(":hidden")){
                i.css("right","0");e.addClass("collapsed")}
            else e.removeClass("collapsed");
                e.show();k(o)})
        .mousemove(function(o){k(o)}).mouseout(function(){
            i.removeClass("hover");
            i.css("right","");
            e.hide()}).click(function(){
                e.hide();i.removeClass("hover").css("right","");d.toggle();
                if(d.is(":visible")){
                    b.css("margin-right","24.0769em");
                    jQuery.browser.msie&&jQuery.browser.version<7&&b.css("right","");
                    }
                else{
                    b.css("margin-right","0");
                    jQuery.browser.msie&&jQuery.browser.version<7&&b.css("right","")}});
        /*i.height("100%"b.height())*/}

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