(() => {
 let ws=null,last=0,retry=null;
 window.rpStatusPushHealthy=()=>!!ws&&ws.readyState===WebSocket.OPEN&&Date.now()-last<2500;
 function connect(){
  clearTimeout(retry);
  const scheme=location.protocol==='https:'?'wss':'ws';
  ws=new WebSocket(`${scheme}://${location.host}/status/ws`);
  ws.onmessage=e=>{try{const m=JSON.parse(e.data);if(!m||!m.type)return;last=Date.now();window.dispatchEvent(new CustomEvent(m.type+'-push',{detail:m.data}));}catch(_){}};
  ws.onclose=()=>{ws=null;retry=setTimeout(connect,1000);};
  ws.onerror=()=>ws.close();
 }
 connect();
})();
