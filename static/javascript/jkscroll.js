/**************************************
JKScroll
Version: v0.1
Author: Vian Ma
Email: doomvan@163.com
**************************************/

//will not scroll left or right by default
var SCROLL_LEFT_RIGHT_WIDTH = 0;

//scroll up/down 100 pixels by default
var SCROLL_DOWN_UP_HEIGHT = 100;

function scrollDown() {
	window.scrollBy(SCROLL_LEFT_RIGHT_WIDTH, SCROLL_DOWN_UP_HEIGHT)
}

function scrollUp() {
	window.scrollBy(SCROLL_LEFT_RIGHT_WIDTH, -SCROLL_DOWN_UP_HEIGHT)
}

function scrollToHead() {
	window.scrollTo(0, 0);
}

function scrollToEnd() {
	//a hack, no need to handle too many kinds of browsers' feature
	//just scroll to a very long distance
	window.scrollTo(0, 99999999);
}

function scroll(e) {
	var keynum;
	var keychar;
	
	//IE / None-IE
	keynum = window.event ? e.keyCode : e.which;
	keychar = String.fromCharCode(keynum).toUpperCase();
	
	//dispatch
	switch (keychar) {
		case 'J':
			scrollDown();
			break;
		case 'K':
			scrollUp();
			break;
		case 'H':
			scrollToHead();
			break;
		case 'L':
			scrollToEnd();
			break;
	}
}

//register event
window.onload = function() {
	var element = document.body;
	if (element.addEventListener) {
		//Firefox, W3C, etc.
		element.addEventListener("keydown", scroll, false);
	} else {
		//IE
		element.attachEvent("onkeydown", scroll);
	}
}