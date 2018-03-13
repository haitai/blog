var btns=document.querySelectorAll('.btn');for(var i=0;i<btns.length;i++){btns[i].addEventListener('mouseleave',clearTooltip);btns[i].addEventListener('blur',clearTooltip);}
function clearTooltip(e){e.currentTarget.setAttribute('class','pure-button btn copybutton');e.currentTarget.removeAttribute('aria-label');}
function showTooltip(elem,msg){elem.setAttribute('class','pure-button btn copybutton tooltipped tooltipped-s');elem.setAttribute('aria-label',msg);}

var copys=document.querySelectorAll('.copy');for(var i=0;i<copys.length;i++){copys[i].addEventListener('mouseleave',clearTooltip1);copys[i].addEventListener('blur',clearTooltip1);}
function clearTooltip1(e){e.currentTarget.setAttribute('class','buttonsm buttonhide copy');e.currentTarget.removeAttribute('aria-label');}
function showTooltip1(elem,msg){elem.setAttribute('class','buttonsm buttonhide copy tooltipped tooltipped-w');elem.setAttribute('aria-label',msg);}

function fallbackMessage(action){var actionMsg='';var actionKey=(action==='cut'?'X':'C');if(/iPhone|iPad/i.test(navigator.userAgent)){actionMsg='No support :(';}
else if(/Mac/i.test(navigator.userAgent)){actionMsg='Press ⌘-'+actionKey+' to '+action;}
else{actionMsg='Press Ctrl-'+actionKey+' to '+action;}
return actionMsg;}
