(() => {
  const dialog = document.getElementById("music-dialog"), list = document.getElementById("music-queue");
  const status = document.getElementById("music-status");
  let player, selected, apiPromise;
  async function api(path, options={}) {
    const response = await fetch(path, {...options,headers:{"Content-Type":"application/json"}});
    const body = await response.json();
    if (!response.ok) throw new Error(typeof body.detail === "string" ? body.detail : "Music request failed");
    return body;
  }
  function youtubeApi() {
    if (window.YT?.Player) return Promise.resolve();
    if (!apiPromise) apiPromise = new Promise((resolve,reject) => {
      const timeout = setTimeout(()=>reject(new Error("YouTube player could not load. Check connectivity.")),15000);
      window.onYouTubeIframeAPIReady = () => { clearTimeout(timeout); resolve(); };
      const script = document.createElement("script"); script.src="https://www.youtube.com/iframe_api";
      script.onerror=()=>{clearTimeout(timeout);reject(new Error("YouTube player unavailable"));}; document.head.append(script);
    });
    return apiPromise;
  }
  async function receipt(state,error="") {
    if (!selected) return;
    try { await api(`/api/music/${selected.id}/receipt`,{method:"POST",body:JSON.stringify({state,error})}); }
    catch (err) { status.textContent=`Playback status could not sync: ${err.message}`; }
  }
  async function play(track) {
    if (!/^[A-Za-z0-9_-]{11}$/.test(track.video_id)) return;
    try {
      if (selected && selected.id !== track.id) { player?.pauseVideo(); await receipt("paused"); }
      selected=track; status.textContent="Loading player…";
      await youtubeApi();
      if (player) { player.loadVideoById(track.video_id); return; }
      player = new YT.Player("music-player",{height:"270",width:"100%",videoId:track.video_id,
        playerVars:{playsinline:1,origin:location.origin},events:{
          onReady:event=>{status.textContent="Tap Play in the video to listen.";receipt("ready");event.target.playVideo();},
          onAutoplayBlocked:()=>{status.textContent="Your browser requires a tap: press Play in the video.";},
          onStateChange:event=>{
            const states={1:"playing",2:"paused",0:"ended"};
            if (states[event.data]) {status.textContent=`Player: ${states[event.data]}. Sound depends on your phone volume.`;receipt(states[event.data]);}
          },
          onError:event=>{const error=`YouTube playback error ${event.data}. This video may restrict embedding or be unavailable.`;status.textContent=error;receipt("failed",error);}
        }});
    } catch (error) {status.textContent=error.message;await receipt("failed",error.message);}
  }
  async function refresh() {
    try {
      const data=await api("/api/music"); list.replaceChildren();
      if (!data.tracks.length) list.textContent="No queued music. Paste a YouTube video link below or ask Atulya to queue one.";
      for (const track of data.tracks) {
        const row=document.createElement("div"),label=document.createElement("span"),button=document.createElement("button");
        label.textContent=`${track.title} · ${track.state}`;button.textContent="Play here";button.addEventListener("click",()=>play(track));
        const remove=document.createElement("button");remove.textContent="Remove";
        remove.addEventListener("click",async()=>{
          try {if(selected?.id===track.id)player?.stopVideo();await api(`/api/music/${track.id}/receipt`,{method:"POST",body:JSON.stringify({state:"cancelled"})});await refresh();}
          catch(error){status.textContent=error.message;}
        });
        if(track.state!=="cancelled") {row.append(label,button,remove);list.append(row);}
      }
    } catch(error){status.textContent=error.message;}
  }
  document.getElementById("quick-music")?.addEventListener("click",()=>{dialog.showModal();refresh();});
  document.getElementById("close-music").addEventListener("click",()=>dialog.close());
  dialog.addEventListener("close",()=>{player?.pauseVideo();});
  document.getElementById("music-form").addEventListener("submit",async event=>{
    event.preventDefault();const input=document.getElementById("music-url");
    try {await api("/api/music",{method:"POST",body:JSON.stringify({url:input.value})});input.value="";await refresh();}
    catch(error){status.textContent=error.message;}
  });
  setInterval(()=>{if(dialog.open&&!document.hidden)refresh();},5000);
})();
