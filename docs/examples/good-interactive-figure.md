# Good interactive figure

The filter tester in the FineWeb Filters tab is a complete interactive figure. It shows how the three new filters in the paper remove pages, and the reader can move each threshold to see the effect. Copy its structure for a new figure.

## Markup

The figure sits in a `.viz` block with a heading, the controls, the output, and two notes. Each slider has a `<label>`, and the default values are the paper's thresholds.

```html
<section class="panel" data-panel="filters" hidden>
  <div>
    <div class="section-title"><h2>New heuristic filters for low quality pages</h2></div>
    <p class="lede" style="margin-top:8px">The authors looked for page statistics that differed between a higher quality and a lower quality version of the same crawl data. They turned three of the statistics into filters and kept each filter after ablations showed better benchmark scores.</p>
  </div>
  <div class="viz">
    <div class="viz-head">
      <div><div class="eyebrow">Interactive filter tester</div><h3>The three new filters applied to example pages</h3></div>
      <div class="controls"><button class="btn small" id="fwReset">Use the paper's thresholds</button></div>
    </div>
    <div class="viz-body">
      <div class="sliders">
        <label for="fwT1">Remove a page if the share of lines that end in punctuation is at most <span class="mono" id="fwT1v"></span><input class="range" type="range" id="fwT1" min="0" max="0.6" step="0.01" value="0.12"></label>
        <label for="fwT2">Remove a page if the share of characters in repeated lines is at least <span class="mono" id="fwT2v"></span><input class="range" type="range" id="fwT2" min="0.02" max="0.6" step="0.01" value="0.1"></label>
        <label for="fwT3">Remove a page if the share of lines shorter than 30 characters is at least <span class="mono" id="fwT3v"></span><input class="range" type="range" id="fwT3" min="0.3" max="1" step="0.01" value="0.67"></label>
      </div>
      <div class="stats"><div class="stat"><b id="fwKept"></b><span>example pages kept</span></div></div>
      <div class="pages" id="fwPages"></div>
      <p class="proto-note">The example pages are written for the demo. The page statistics are computed from the text shown.</p>
      <p class="notice"><b>What to notice:</b> With the paper's thresholds, the filters remove the menu, the product grid, and the forum page, which have little readable text. The poem is also removed, so the filters can remove some good pages along with many bad pages. In the paper, the three filters together removed about 22% of tokens, and the authors kept the thresholds that improved benchmark scores in their ablations.</p>
    </div>
  </div>
</section>
```

The `proto-note` says which values are made up, because the example pages are written for the demo. The "What to notice" note relates the result to the paper, which reports that the filters removed about 22% of tokens.

## Script

The script computes the page statistics from the page text, so the output stays correct for any threshold. Every name starts with the dossier's prefix, e.g., `fwT1` and `FW_PAGES`, because all the dossiers share one script.

```js
function pageStats(x){
  const lines=x.split("\n").map(l=>l.trim()).filter(Boolean), n=lines.length, seen=new Set();
  let dup=0,tot=0;
  lines.forEach(l=>{tot+=l.length; if(seen.has(l)) dup+=l.length; else seen.add(l);});
  return {punct:lines.filter(l=>END_PUNCT.test(l)).length/n, dup:dup/tot, short:lines.filter(l=>l.length<30).length/n};
}
function drawFilters(){
  const t1=+$("#fwT1").value, t2=+$("#fwT2").value, t3=+$("#fwT3").value;
  $("#fwT1v").textContent=t1.toFixed(2); $("#fwT2v").textContent=t2.toFixed(2); $("#fwT3v").textContent=t3.toFixed(2);
  let kept=0;
  $("#fwPages").innerHTML=FW_PAGES.map(pg=>{
    const st=pageStats(pg.x), f1=st.punct<=t1, f2=st.dup>=t2, f3=st.short>=t3, rm=f1||f2||f3;
    if(!rm) kept++;
    return `<div class="page-card${rm?" removed":""}"><div class="page-top"><b>${pg.t}</b><span class="pill ${rm?"warn":"ok"}">${rm?"Removed":"Kept"}</span></div>
      <pre class="code page-text">${esc(pg.x)}</pre>
      <div class="page-stats"><span class="${f1?"fail":""}">Lines ending in punctuation <b class="mono">${st.punct.toFixed(2)}</b></span><span class="${f2?"fail":""}">Characters in repeated lines <b class="mono">${st.dup.toFixed(2)}</b></span><span class="${f3?"fail":""}">Lines under 30 characters <b class="mono">${st.short.toFixed(2)}</b></span></div></div>`;
  }).join("");
  $("#fwKept").textContent=`${kept} of ${FW_PAGES.length}`;
}
["#fwT1","#fwT2","#fwT3"].forEach(id=>$(id).addEventListener("input",drawFilters));
$("#fwReset").onclick=()=>{$("#fwT1").value=0.12;$("#fwT2").value=0.1;$("#fwT3").value=0.67;drawFilters();};
```

## Checklist

- The default values come from the paper, and a reset button sets them again.
- The output is computed from the inputs, and nothing is hard-coded for one setting.
- A `proto-note` marks every made-up value.
- The figure works at 400px width, in light mode and in dark mode.
