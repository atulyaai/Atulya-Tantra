const test = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const path = require('node:path');

function element() {
  return {listeners:{},children:[],textContent:'',open:false,
    addEventListener(name, fn) { this.listeners[name]=fn; },
    append(...nodes) { this.children.push(...nodes); },
    replaceChildren(...nodes) { this.children=nodes; },
    showModal() { this.open=true; }, close() { this.open=false; },
  };
}
async function flush() { for(let i=0;i<8;i++) await new Promise(resolve=>setImmediate(resolve)); }

function playerHarness() {
  const ids=new Map(), receipts=[], intervals=[];
  for(const id of ['music-dialog','music-queue','music-status','music-player','quick-music','close-music','music-form','music-url']) ids.set(id,element());
  const track={id:'one',video_id:'M7lc1UVf-VE',title:'Test',state:'queued'};
  let events, video=track.video_id, state=1;
  const player={loadVideoById(id){video=id;},pauseVideo(){state=2;},stopVideo(){state=0;},playVideo(){state=1;},getVideoData(){return {video_id:video};},getPlayerState(){return state;}};
  const YT={Player:function(_id,options){events=options.events;return player;}};
  const sandbox={window:{YT},YT,document:{getElementById:id=>ids.get(id),createElement:element,head:element(),hidden:false},
    location:{origin:'https://test.invalid'},AbortController,setTimeout,clearTimeout,
    setInterval(fn,ms){intervals.push({fn,ms});},
    async fetch(url,options={}) {
      if(url==='/api/music') return {ok:true,json:async()=>({tracks:[track]})};
      const body=JSON.parse(options.body);receipts.push(body);track.state=body.state;
      return {ok:true,json:async()=>({updated:true})};
    },
  };
  vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../../webui/music.js'),'utf8'),sandbox);
  return {ids,receipts,intervals,player,get events(){return events;},setVideo(id){video=id;},track};
}

test('player receipts come from state events and heartbeats; stale video events are ignored',async()=>{
  const h=playerHarness();
  h.ids.get('quick-music').listeners.click();await flush();
  h.ids.get('music-queue').children[0].children[1].listeners.click();await flush();
  assert.equal(h.receipts.length,0,'Queue selection alone must not report playback');
  h.events.onReady({target:h.player});await flush();
  h.events.onStateChange({target:h.player,data:1});await flush();
  assert.deepEqual(h.receipts.map(r=>r.state),['ready','playing']);
  h.intervals.find(i=>i.ms===15000).fn();await flush();
  assert.equal(h.receipts.at(-1).state,'playing');
  const count=h.receipts.length;h.setVideo('old-video');
  h.events.onStateChange({target:h.player,data:0});await flush();
  assert.equal(h.receipts.length,count,'Prior track event must not finish the selected track');
});

test('removal clears selected track before late player callbacks',async()=>{
  const h=playerHarness();
  h.ids.get('quick-music').listeners.click();await flush();
  const row=h.ids.get('music-queue').children[0];
  row.children[1].listeners.click();await flush();
  await row.children[2].listeners.click();await flush();
  assert.equal(h.receipts.at(-1).state,'cancelled');
  const count=h.receipts.length;
  h.events.onStateChange({target:h.player,data:0});
  h.intervals.find(i=>i.ms===15000).fn();await flush();
  assert.equal(h.receipts.length,count);
});
