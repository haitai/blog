// ----------------------------------------------------------------------------
// markItUp!
// ----------------------------------------------------------------------------
// Copyright (C) 2008 Jay Salvat
// http://markitup.jaysalvat.com/
// ----------------------------------------------------------------------------
// Html tags
// http://en.wikipedia.org/wiki/html
// ----------------------------------------------------------------------------
// Basic set. Feel free to add more tags
// ----------------------------------------------------------------------------
mySettings = {
	onShiftEnter:	{keepDefault:false, replaceWith:'<br />\n'},
	onCtrlEnter:	{keepDefault:false, openWith:'\n<p>', closeWith:'</p>\n'},
	onTab:			{keepDefault:false, openWith:'	 '},
	markupSet: [
		{name:'Heading 1', key:'1', openWith:'<h1(!( class="[![Class]!]")!)>', closeWith:'</h1>', placeHolder:'Your title here...' },
		{name:'Heading 2', key:'2', openWith:'<h2(!( class="[![Class]!]")!)>', closeWith:'</h2>', placeHolder:'Your title here...' },
		{name:'Heading 3', key:'3', openWith:'<h3(!( class="[![Class]!]")!)>', closeWith:'</h3>', placeHolder:'Your title here...' },
		{name:'Heading 4', key:'4', openWith:'<h4(!( class="[![Class]!]")!)>', closeWith:'</h4>', placeHolder:'Your title here...' },
		{name:'Heading 5', key:'5', openWith:'<h5(!( class="[![Class]!]")!)>', closeWith:'</h5>', placeHolder:'Your title here...' },
		{name:'Heading 6', key:'6', openWith:'<h6(!( class="[![Class]!]")!)>', closeWith:'</h6>', placeHolder:'Your title here...' },
		{name:'Paragraph [Ctrl+Enter]', openWith:'<p(!( class="[![Class]!]")!)>', closeWith:'</p>\n' },
	
		{separator:'---------------' },
		{name:'Bold', key:'B', openWith:'(!(<strong>|!|<b>)!)', closeWith:'(!(</strong>|!|</b>)!)' },
		{name:'Italic', key:'I', openWith:'(!(<em>|!|<i>)!)', closeWith:'(!(</em>|!|</i>)!)' },
		{name:'Stroke through', key:'S', openWith:'<del>', closeWith:'</del>' },
		
		{separator:'---------------' },
		{name:'Ul', openWith:'<ul>\n', closeWith:'</ul>\n' },
		{name:'Ol', openWith:'<ol>\n', closeWith:'</ol>\n' },
		{name:'Li', openWith:'<li>', closeWith:'</li>' },
		{separator:'---------------' },
		{name:'Picture', key:'P', replaceWith:'<img src="[![Source:!:http://]!]" alt="[![Alternative text]!]" />' },
		{name:'Link', key:'L', openWith:'<a href="[![Link:!:http://]!]"(!( title="[![Title]!]")!)>', closeWith:'</a>', placeHolder:'Your text to link...' },
		{separator:'---------------' },
		{name:'Clean', className:'clean', replaceWith:function(markitup) { return markitup.selection.replace(/<(.*?)>/g, "") } },
				{name:'Next line', className:"br", 
		openWith:'<br/>'},			
		{name:'Encode Html special chars',
			className:"encodechars", 
			replaceWith:function(markItUp) { 
				container = document.createElement('div');
				container.appendChild(document.createTextNode(markItUp.selection));
				return container.innerHTML; 
			}
		},
		{name:'Table',
					openWith:'<table>',
					closeWith:'</table>',
					placeHolder:"<tr><(!(td|!|th)!)></(!(td|!|th)!)></tr>",
					className:'table' 
				},
		{name:'Tr',
					openWith:'<tr>',
					closeWith:'</tr>',
					placeHolder:"<(!(td|!|th)!)></(!(td|!|th)!)>",
					className:'table-col'
				},
		{name:'Td/Th',
					openWith:'<(!(td|!|th)!)>', 
					closeWith:'</(!(td|!|th)!)>',
					className:'table-row' 
				},
		{name:'Date of the Day', 
			className:"dateoftheday", 
			replaceWith:function(h) { 
				date = new Date()
				weekday = ["Sunday","Monday","Tuesday","Wednesday","Thursday","Friday","Saturday"];
				monthname = ["January","February","March","April","May","June","July","August","September","October","November","December"];
				D = weekday[date.getDay()];
				d = date.getDate();
				m = monthname[date.getMonth()];
				y = date.getFullYear();
				h = date.getHours();
				i = date.getMinutes();
				s = date.getSeconds();
				return (D +" "+ d + " " + m + " " + y + " " + h + ":" + i + ":" + s);
			}
		},		
		{name:'Blockquote', className:"blockquote", key:'Q',
openWith:'<blockquote>', closeWith:'</blockquote>\n' },
		{name:'Code snippet', className:"postcode", 
		openWith:'<pre class="prettyprint">', closeWith:'</pre>\n' },
		{name:'Read more', className:"readmore", key:'M',
				openWith:'<!--more--><a name="more"></a>\n'},
		{name:'Preview', className:'preview', call:'preview' }
	]
}