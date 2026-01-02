let devices = [];

async function load() {
  const r = await fetch("/api/devices");
  devices = await r.json();
  render();
}

function render() {
  const f = filter.value;
  const s = search.value.toLowerCase();
  const tb = document.querySelector("tbody");
  tb.innerHTML = "";

  let i = 1, a=0,o=0,of=0;

  for (const d of devices) {
    if (f==="online" && !d.online) continue;
    if (f==="offline" && d.online) continue;
    if (f==="alarms" && d.button===0) continue;
    if (s && !d.id.toLowerCase().includes(s)) continue;

    if (d.online) o++; else of++;
    if (d.button!==0) a++;

    tb.innerHTML += `
      <tr>
        <td>${i++}</td>
        <td>${d.id}</td>
        <td>${d.button}</td>
        <td>${d.battery}%</td>
        <td>${d.last_event||""}</td>
        <td>
          <span class="status-dot ${d.online?"online":"offline"}"></span>
          ${d.online?"Online":"Offline"}
        </td>
        <td>${d.location}</td>
        <td>
          <button onclick="resolve('${d.id}')">OK</button>
          <button onclick="del('${d.id}')">X</button>
        </td>
      </tr>`;
  }

  statAll.innerText = devices.length;
  statOnline.innerText = o;
  statOffline.innerText = of;
  statAlarm.innerText = a;
}

async function addDevice() {
  await fetch("/api/add",{method:"POST",headers:{"Content-Type":"application/json"},
    body:JSON.stringify({id:newId.value,location:newLoc.value})});
  newId.value=""; newLoc.value="";
  load();
}

async function resolve(id){await fetch(`/api/resolve/${id}`,{method:"POST"});load()}
async function del(id){await fetch(`/api/delete/${id}`,{method:"DELETE"});load()}
async function logout(){await fetch("/api/logout",{method:"POST"});location.href="/"}

filter.onchange = render;
search.oninput = render;

load();
setInterval(load,5000);
