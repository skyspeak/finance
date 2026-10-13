"""Shared phone-layout rules for the desk, map and backtest pages.

Inserted verbatim (not via str.format) into each builder's <style> and before
</body>, so the braces here are literal CSS/JS braces.

  CSS  - grid children may shrink (a wide table inside a 1fr column used to push
         the page sideways), wide tables keep their first column pinned while
         the rest scrolls, the smallest labels grow to a readable size, nested
         scroll boxes fit within the screen, and tables marked
         class="stack" turn into one block per row.
  JS   - any container with data-mcollapse="N" shows only its first N children
         on a phone, with a "Show all" button for the rest.
"""

BREAK = 640

CSS = """
.cols>*,.cols2>*,.cols3>*,.grid>*{min-width:0}
@media (max-width:%(w)dpx){
  body{font-size:15px}
  th{font-size:10.5px}
  td{font-size:12.5px}
  .sub,.lede{font-size:13px}
  .chip,.sl,.ist,.tag,.etype,.dirl,.ipo-w,.leg .act,.tstats span,.hs span{font-size:10px}
  .tmeta{font-size:11.5px}
  .grid,.ipg{grid-template-columns:minmax(0,1fr)}
  .lrow{grid-auto-flow:row;grid-auto-columns:auto;overflow-x:visible}
  .lcol{min-width:0}
  .scroll{max-height:70vh}
  .scroll table th:first-child,.scroll table td:first-child,
  .cmx table th:first-child,.cmx table td:first-child{position:sticky;left:0;z-index:1;background:var(--bg)}
  table.stack thead{display:none}
  table.stack,table.stack tbody,table.stack tr,table.stack td{display:block;width:auto}
  table.stack tr{padding:11px 12px;border-bottom:1px solid var(--line)}
  table.stack td{border:0;padding:2px 0;text-align:left;position:static}
  [data-mcollapse].mc-closed>.mc-hide{display:none !important}
  .mc-more{display:block;width:100%%;margin-top:12px;padding:13px;font:600 12.5px 'JetBrains Mono',monospace;
    color:var(--acc);background:var(--pan);border:1px solid var(--line);border-radius:9px;cursor:pointer}
}
""" % {"w": BREAK}

JS = """<script>
(function(){
  if(!window.matchMedia||!matchMedia('(max-width:%(w)dpx)').matches) return;
  document.querySelectorAll('[data-mcollapse]').forEach(function(c){
    var n=parseInt(c.getAttribute('data-mcollapse'),10), kids=Array.prototype.slice.call(c.children);
    if(!(n>0) || kids.length<=n+1) return;
    kids.slice(n).forEach(function(k){k.classList.add('mc-hide')});
    c.classList.add('mc-closed');
    var b=document.createElement('button');
    b.className='mc-more'; b.type='button';
    b.textContent='Show all '+kids.length+' \\u2193';
    b.addEventListener('click',function(){c.classList.remove('mc-closed'); b.remove();});
    c.parentNode.insertBefore(b,c.nextSibling);
  });
})();
</script>""" % {"w": BREAK}
