class PillManagerPanel extends HTMLElement {
  set hass(hass) { this._hass = hass; this.render(); }
  set narrow(value) { this._narrow = value; this.render(); }
  connectedCallback() { this.render(); }
  async call(type, data = {}) {
    return this._hass.callWS({ type: "pill_manager/" + type, ...data });
  }
  esc(value) {
    return String(value ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
  }
  async refresh() {
    this.data = await this.call("get_data");
    this.render();
  }
  async render() {
    if (!this._hass || this._busy) return;
    if (!this.data) { this._busy = true; try { await this.refresh(); } catch(e) { this.error = e.message; } finally { this._busy = false; } return; }
    const meds = this.data.medications || [];
    this.innerHTML = `
      <style>
        :host{display:block;min-height:100%;background:#f7f8fa;color:#20242b;font-family:var(--paper-font-body1_-_font-family,Arial,sans-serif);direction:rtl}
        *{box-sizing:border-box} .wrap{max-width:1050px;margin:auto;padding:28px 20px 60px}
        header{display:flex;justify-content:space-between;align-items:center;gap:12px;margin-bottom:22px}
        h1{font-size:27px;margin:0 0 5px;font-weight:700} .muted{color:#78818d;font-size:14px}
        button{border:0;border-radius:12px;padding:11px 16px;background:#367b68;color:white;font-weight:600;cursor:pointer}
        button.secondary{background:#e8efec;color:#315f53} button.danger{background:#fce8e6;color:#a13e37}
        .grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(270px,1fr));gap:14px}
        .card{background:white;border:1px solid #e8ebef;border-radius:18px;padding:18px;box-shadow:0 3px 14px #1b28300a}
        .card h2{font-size:18px;margin:0 0 5px} .stock{display:flex;justify-content:space-between;padding:10px 0;border-bottom:1px solid #f0f1f3}
        .stock:last-child{border:0}.pill{display:inline-block;border-radius:20px;background:#edf5f1;color:#367b68;padding:4px 9px;font-size:12px}
        .warn{background:#fff3df;color:#98631c}.empty{text-align:center;padding:44px 20px;color:#7a8490}
        .form{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-top:14px}.form input{min-width:0;width:100%;padding:11px;border:1px solid #dce1e6;border-radius:10px;font:inherit;direction:rtl}
        .form .wide{grid-column:1/-1}.actions{display:flex;gap:8px;flex-wrap:wrap;margin-top:14px}
        .section{margin:28px 0 12px;font-size:19px}.history{display:flex;justify-content:space-between;gap:10px;padding:11px 0;border-bottom:1px solid #eee}
        @media(max-width:520px){.wrap{padding:18px 12px 45px}header{align-items:flex-start}.form{grid-template-columns:1fr}}
      </style>
      <div class="wrap">
        <header><div><h1>ניהול תרופות</h1><div class="muted">מלאי, תזכורות והיסטוריית נטילה</div></div><button id="add">+ תרופה חדשה</button></header>
        ${this.error ? '<div class="card">'+this.esc(this.error)+'</div>' : ''}
        <div class="grid">
          ${meds.map(m => `<article class="card">
            <h2>${this.esc(m.name)}</h2><div class="muted">${(m.strengths||[]).length} סוגי מינון</div>
            ${(m.forecast||[]).map(s=>`<div class="stock"><span>${this.esc(s.strength)}</span><strong>${s.quantity} יח׳ ${s.days_remaining===null?'': '· כ־'+s.days_remaining+' ימים'}</strong></div>`).join('')}
            <div class="actions"><button data-take="${m.id}">סימנתי שלקחתי</button><button class="secondary" data-edit="${m.id}">עריכה</button></div>
          </article>`).join('')}
        </div>
        ${meds.length===0?'<div class="card empty">עדיין לא הוספת תרופות.<br>לחץ על „תרופה חדשה” כדי להתחיל.</div>':''}
        <h2 class="section">היסטוריית נטילה</h2>
        <div class="card">${(this.data.intake||[]).slice().reverse().slice(0,20).map(r=>{const m=meds.find(x=>x.id===r.medication_id);return `<div class="history"><span>${this.esc(m?.name||'תרופה')}</span><span>${this.esc(new Date(r.taken_at).toLocaleString('he-IL'))}</span><strong>${r.doses.map(d=>this.esc(d.quantity)+'× '+this.esc(d.strength)).join(' + ')}</strong></div>`}).join('') || '<div class="empty">אין עדיין רישומי נטילה</div>'}</div>
        <div id="dialog"></div>
      </div>`;
    this.querySelector("#add")?.addEventListener("click",()=>this.medicationForm());
    this.querySelectorAll("[data-edit]").forEach(b=>b.addEventListener("click",()=>this.medicationForm(meds.find(m=>m.id===b.dataset.edit))));
    this.querySelectorAll("[data-take]").forEach(b=>b.addEventListener("click",()=>this.takeForm(meds.find(m=>m.id===b.dataset.take))));
  }
  medicationForm(med) {
    const m=med||{name:"",strengths:[{strength:"",quantity:0}],schedules:[]};
    this.querySelector("#dialog").innerHTML=`<div class="card" style="margin-top:18px"><h2>${med?'עריכת תרופה':'תרופה חדשה'}</h2>
      <div class="form"><input id="name" placeholder="שם התרופה" value="${this.esc(m.name)}">
      <input id="strength" placeholder="חוזק (למשל 25 מ״ג)" value="${this.esc(m.strengths?.[0]?.strength||'')}">
      <input id="qty" type="number" min="0" placeholder="כמות במלאי" value="${m.strengths?.[0]?.quantity||0}">
      <div class="wide muted">בגרסה זו ניתן להתחיל עם חוזק אחד; הוספת אריזות וחוזקים נוספים תגיע בעדכון הבא.</div></div>
      <div class="actions"><button id="save">שמירה</button><button class="secondary" id="cancel">ביטול</button>${med?'<button class="danger" id="delete">מחיקה</button>':''}</div></div>`;
    this.querySelector("#cancel").onclick=()=>this.querySelector("#dialog").innerHTML="";
    this.querySelector("#save").onclick=async()=>{const name=this.querySelector("#name").value.trim(),strength=this.querySelector("#strength").value.trim(),quantity=Number(this.querySelector("#qty").value);if(!name||!strength||!Number.isFinite(quantity)||quantity<0)return alert("יש למלא שם, חוזק וכמות תקינים");await this.call("save_medication",{medication:{...m,name,strengths:[{strength,quantity}],schedules:m.schedules||[]}});await this.refresh();};
    this.querySelector("#delete")?.addEventListener("click",async()=>{if(confirm("למחוק את התרופה?")){await this.call("delete_medication",{medication_id:m.id});await this.refresh();}});
  }
  takeForm(m) {
    if(!m)return;
    this.querySelector("#dialog").innerHTML=`<div class="card" style="margin-top:18px"><h2>אישור נטילה · ${this.esc(m.name)}</h2>
      ${m.strengths.map((s,i)=>`<div class="form"><label>${this.esc(s.strength)} · במלאי ${s.quantity}</label><input type="number" min="0" max="${s.quantity}" value="0" id="dose-${i}"></div>`).join('')}
      <div class="actions"><button id="confirm">אישור שלקחתי</button><button class="secondary" id="cancel">ביטול</button></div></div>`;
    this.querySelector("#cancel").onclick=()=>this.querySelector("#dialog").innerHTML="";
    this.querySelector("#confirm").onclick=async()=>{const doses={};m.strengths.forEach((s,i)=>{const n=Number(this.querySelector("#dose-"+i).value);if(n>0)doses[s.strength]=n;});if(!Object.keys(doses).length)return alert("בחר כמות שנלקחה");try{await this.call("confirm_intake",{medication_id:m.id,doses});await this.refresh();}catch(e){alert("לא ניתן לשמור: "+e.message);}};
  }
}
customElements.define("pill-manager-panel", PillManagerPanel);
