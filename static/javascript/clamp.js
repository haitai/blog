/*
 *	jQuery iclamp.js 1.0
 *
 *	Copyright (c) victory.xiaolong
 *
 *	Licensed under the MIT license.
 */

;(function($){
  'use strict';
  if($.fn.clamp) return;

  $.fn.clamp = function(options){
    if(this.length === 0){
      $.fn.clamp.debug('No element found for "' + this.selector + '".');
      return;
    }
    if(this.length > 1){
      return this.each(function(){
        $(this).clamp(options);
      })
    };

    var $clamp = this;
    var clampLine = options.clamp || 3;
    var clampLineHeight = getLineHeight();
    $clamp.css({
      /*'line-height': clampLineHeight + 'px',*/
      'max-height': clampLine * clampLineHeight + 'px',
      'overflow': 'hidden'
    })
    if(isSupportNativeClamp()) return;


    var $content = $clamp.find('.clamp-ellipsis').css('display', 'block');
    var originText = $content.text().trim();
    var regularText = '';

    if($content.outerHeight() > $clamp.outerHeight()){
      getRegularText(originText, originText);
    }

    function getRegularText(_regularText, _truncationText){
      var _startPos = 0;
      var _endPos = _regularText.length;
      var _middlePos = Math.floor((_startPos + _endPos) / 2);
      var _ellipsisText = _regularText.slice(_startPos, _middlePos);
      _truncationText = _regularText.slice(_middlePos, _endPos);
      $content.text(regularText + _ellipsisText + '...');

      if(_middlePos === 0){
        return;
      }else if($content.outerHeight() > $clamp.outerHeight()){
        getRegularText(_ellipsisText,  _truncationText);
      }else{
        regularText = regularText + _ellipsisText;
        getRegularText(_truncationText, _truncationText);
      }
    }

    // 公共属性_____________________________________________________

    $.fn.clamp.defaults = {
      clamp: 3
    }


    // 辅助函数_____________________________________________________

    function getLineHeight(){
      var lineHeight = $clamp.css('line-height').replace(/px/ig, '');
      if(lineHeight === 'normal'){
        lineHeight = parseInt($clamp.css('font-size').replace(/px/ig, '')) * 1.2;
      }
      return parseInt(lineHeight);
    };

    function isSupportNativeClamp(){
      var supportsNativeClamp = typeof($clamp.css('-webkit-line-clamp')) != 'undefined';
      if(supportsNativeClamp) {
        $clamp.css({
          'display': '-webkit-box',
          'text-overflow': 'ellipsis',
          '-webkit-line-clamp': clampLine.toString(),
          '-webkit-box-orient': 'vertical'
        });
        return true;
      };
      return false;
    }
  };


})(window.jQuery);
