class PillManagerPanel extends HTMLElement {
  set hass(value) {
    this._hass = value;
    if (!this._subscribed && value?.connection?.subscribeEvents) {
      this._subscribed = true;
      value.connection.subscribeEvents(() => this.load(true), "pill_manager_v2_updated")
        .then(unsubscribe => {
          if (this.isConnected) this._unsubscribeEvents = unsubscribe;
          else unsubscribe();
        })
        .catch(() => { this._subscribed = false; });
    }
    if (!this._loaded) this.load();
  }
  connectedCallback() { this.load(); }
  disconnectedCallback() {
    this._unsubscribeEvents?.();
    this._unsubscribeEvents = null;
    this._subscribed = false;
  }
  async call(command, data = {}) {
    return this._hass.callWS({type: "pill_manager_v2/" + command, ...data});
  }
  esc(value) {
    return String(value ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
  }
  todayLocal() {
    const d=new Date(), pad=n=>String(n).padStart(2,"0");
    return d.getFullYear()+"-"+pad(d.getMonth()+1)+"-"+pad(d.getDate());
  }
  async load(force = false) {
    if (!this._hass || (this._loaded && !force)) return;
    // Never replace the DOM while the user is editing a medication. Reminder
    // events can arrive while the editor is open and would otherwise erase it.
    if (force && this._editorOpen) { this._refreshPending = true; return; }
    if (this._loading) { if (force) this._refreshPending = true; return; }
    this._loading = true;
    try { this.data = await this.call("get_data"); this.error = ""; this._loaded = true; }
    catch (err) { this.error = err.message || String(err); }
    finally {
      this._loading = false;
      // A refresh can already be in flight when the user opens the editor.
      // Never replace the panel DOM while the editor is mounted.
      if (this._editorOpen) {
        this._refreshPending = true;
        return;
      }
      this.render();
      if (this._refreshPending) {
        this._refreshPending = false;
        this.load(true);
      }
    }
  }
  render() {
    if (!this._hass) return;
    // The editor owns its draft state. A reminder/event refresh must never
    // replace its DOM, even if the panel is temporarily detached/reconnected.
    if (this._editorOpen) { this._refreshPending = true; return; }
    const medications = this.data?.medications || [];
    const now = new Date();
    const monthStart = new Date(now.getFullYear(), now.getMonth()+(this._calendarOffset||0), 1);
    const monthLength = new Date(monthStart.getFullYear(), monthStart.getMonth()+1, 0).getDate();
    const monthOffset = (monthStart.getDay()+6)%7; // Monday-first, matching Python weekday()
    const monthLabel = new Intl.DateTimeFormat("he-IL",{month:"long",year:"numeric"}).format(monthStart);
    const calendarCells = Array.from({length:monthOffset},()=>'<div class="cal-empty"></div>');
    for(let day=1;day<=monthLength;day++){
      const date=new Date(monthStart.getFullYear(),monthStart.getMonth(),day);
      const dateKey=monthStart.getFullYear()+"-"+String(monthStart.getMonth()+1).padStart(2,"0")+"-"+String(day).padStart(2,"0");
      const weekday=(date.getDay()+6)%7;
      const planned=[];
      for(const med of medications){
        const regimen=med.regimen||{};
        let phase=null;
        if(regimen.mode==="fixed") phase=regimen.fixed_phase;
        else if(regimen.mode==="phased") phase=(regimen.phases||[]).find(p=>{
          if(!p.start_date||p.start_date>dateKey)return false;
          if(p.duration_days==null)return true;
          const end=new Date(p.start_date+"T00:00:00");end.setDate(end.getDate()+Number(p.duration_days)-1);
          const endKey=end.getFullYear()+"-"+String(end.getMonth()+1).padStart(2,"0")+"-"+String(end.getDate()).padStart(2,"0");
          return dateKey<=endKey;
        });
        if(phase&&(phase.weekdays||[0,1,2,3,4,5,6]).includes(weekday)){
          const times=(phase.times||[]).join(", ");
          planned.push('<div class="cal-dose">'+this.esc(med.name)+' · '+Number(phase.dose_mg||0)+' מ״ג'+(times?' <span>'+this.esc(times)+'</span>':'')+'</div>');
        }
      }
      calendarCells.push('<div class="cal-day '+(dateKey===this.todayLocal()?'cal-today':'')+'"><strong>'+day+'</strong>'+(planned.length?planned.join(""):'<span class="cal-none">—</span>')+'</div>');
    }
    this.innerHTML = `
      <style>
        :host{display:block;min-height:100%;background:#f7f8fa;color:#20242b;font-family:Arial,sans-serif;direction:rtl}
        *{box-sizing:border-box}.wrap{max-width:1100px;margin:auto;padding:26px 18px 60px}
        header{display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:22px}
        h1{font-size:27px;margin:0 0 5px}.muted{color:#77818d;font-size:13px}
        button{border:0;border-radius:11px;padding:10px 15px;background:#367b68;color:white;font-weight:600;cursor:pointer}
        button.secondary{background:#e9efec;color:#315f53}button.danger{background:#fbe9e7;color:#a13e37}
        .grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(290px,1fr));gap:14px}
        .card{background:white;border:1px solid #e7eaee;border-radius:17px;padding:17px;box-shadow:0 3px 12px #1b283008}
        h2{font-size:18px;margin:0 0 8px}.stock{padding:10px 0;border-bottom:1px solid #eef0f2}
        .stock:last-child{border:0}.line{display:flex;justify-content:space-between;gap:10px}
        .tag{display:inline-block;border-radius:20px;background:#edf5f1;color:#367b68;padding:4px 9px;font-size:12px}
        .warn{background:#fff2dd;color:#94601b}.actions{display:flex;gap:8px;flex-wrap:wrap;margin-top:13px}
        .empty{text-align:center;padding:42px;color:#7b8490}.editor{margin-top:18px}
        .calendar-card{margin-bottom:16px}.calendar{display:grid;grid-template-columns:repeat(7,minmax(0,1fr));gap:5px}
        .cal-head{text-align:center;color:#77818d;font-size:12px;padding:5px 0}
        .cal-day{min-height:76px;background:#f8faf9;border:1px solid #edf0ee;border-radius:9px;padding:6px;min-width:0}
        .cal-day>strong{font-size:13px}.cal-today{border:2px solid #367b68;background:#f0f7f3}
        .cal-dose{font-size:10px;line-height:1.35;margin-top:4px;overflow-wrap:anywhere;color:#315f53}
        .cal-dose span{display:block;color:#77818d}.cal-none{display:block;color:#c0c5ca;font-size:11px;margin-top:8px}
        .cal-empty{min-height:76px}@media(max-width:540px){.cal-day{min-height:62px;padding:4px}.cal-dose{font-size:9px}}
        .form{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin:13px 0}
        label{display:block;font-size:13px;color:#65707c;margin-bottom:5px}
        input,select,textarea{width:100%;padding:10px;border:1px solid #dce1e6;border-radius:9px;font:inherit;background:white;color:#20242b}
        textarea{min-height:105px;direction:ltr;text-align:left;font-family:monospace}.wide{grid-column:1/-1}
        .product,.phase-editor{border:1px solid #edf0f2;border-radius:12px;padding:12px;margin:10px 0}
        .batch{font-size:13px;color:#66717d;margin-top:5px}.section{margin:24px 0 10px}
        @media(max-width:540px){.wrap{padding:17px 11px}.form{grid-template-columns:1fr}header{align-items:flex-start}}
      </style>
      <div class="wrap">
        <header><div><h1>ניהול תרופות</h1><div class="muted">ניהול תרופות, אריזות, אצוות מלאי ומשטרי מינון</div></div><button id="new">+ הוספת תרופה</button></header>
        ${this.error ? `<div class="card">${this.esc(this.error)}</div>` : ""}
        ${this.data?.migration?.legacy_v1_imported ? `
          <section class="card" style="margin-bottom:14px">
            <h2>ייבוא נתונים מהגרסה הקודמת הושלם</h2>
            <div class="muted">יובאו ${Number(this.data.migration.imported_medications||0)} תרופות ו-${Number(this.data.migration.imported_history_records||0)} רשומות היסטוריה. הנתונים המקוריים נשמרו ללא שינוי.</div>
            ${(this.data.migration.warnings||[]).map(w=>`<div class="batch warn">${this.esc(w)}</div>`).join("")}
          </section>` : ""}
        ${(this.data?.occurrences||[]).filter(o=>["pending","missed_pending"].includes(o.status)).length ? `
          <section class="card" style="margin-bottom:14px">
            <h2>מנות שממתינות לאישור</h2>
            ${(this.data.occurrences||[]).filter(o=>["pending","missed_pending"].includes(o.status)).map(o=>`
              <div class="stock">
                <div class="line"><strong>${this.esc(o.medication_name||"תרופה")} · ${Number(o.dose_mg||0)} מ״ג</strong><span class="tag ${o.status==="missed_pending"?"warn":""}">${o.status==="missed_pending"?"באיחור":"ממתינה"}</span></div>
                <div class="muted">מועד מתוכנן: ${this.esc(o.scheduled_at||"—")}</div>
                <div class="actions"><button data-occ-take="${this.esc(o.occurrence_id)}">לקחתי</button><button class="secondary" data-occ-skip="${this.esc(o.occurrence_id)}">דלג</button></div>
              </div>`).join("")}
          </section>` : ""}

        <section class="card calendar-card">
          <div class="line"><h2>לוח הטיפול · ${this.esc(monthLabel)}</h2><div class="actions"><button class="secondary" id="cal-prev">‹ חודש קודם</button><button class="secondary" id="cal-next">חודש הבא ›</button></div></div>
          <div class="calendar">
            ${["ב׳","ג׳","ד׳","ה׳","ו׳","ש׳","א׳"].map(d=>'<div class="cal-head">'+d+'</div>').join("")}
            ${calendarCells.join("")}
          </div>
        </section>
        <div class="grid">
          ${medications.map(m => {
            const products = m.products || [];
            const units = products.reduce((sum,p)=>sum+(p.stock_batches||[]).reduce((s,b)=>s+Number(b.quantity||0),0),0);
            const forecast = m.forecast || {};
            return `<article class="card">
              <div class="line"><h2>${this.esc(m.name)}</h2><span class="tag">${m.regimen?.mode==="prn"?"לפי הצורך":m.regimen?.mode==="phased"?"משטר מדורג":"מינון קבוע"}</span></div>
              <div class="muted">סה״כ ${products.length} סוגי מוצר · ${units.toFixed(1)} יחידות במלאי</div>
              ${products.map(p=>{
                const pUnits=(p.stock_batches||[]).reduce((sum,b)=>sum+Number(b.quantity||0),0);
                return `<div class="stock"><div class="line"><strong>${this.esc(p.name||"אריזה")} · ${p.strength_mg} מ״ג</strong><span>${pUnits} טבליות במלאי</span></div>
                  <div class="muted">${p.splittable?"ניתן לחצייה":"טבליות שלמות בלבד"}</div>
                  ${(p.stock_batches||[]).map(b=>`<div class="batch ${Number(b.quantity)<0?"warn":""}">אצווה: ${this.esc(b.quantity)} יח׳ ${Number(b.quantity)<0?"· יתרת מלאי שלילית — נדרשת בדיקה":""} · התקבלה: ${this.esc(b.received_at||"—")} ${b.expires_on?"· תפוגה: "+this.esc(b.expires_on):""} <button class="secondary" data-adjust="${m.id}" data-product="${p.id}" data-batch="${b.id}" data-quantity="${b.quantity}">תיקון יתרה</button></div>`).join("")}
                  <div class="actions"><button class="secondary" data-stock="${m.id}" data-product="${p.id}">הוספת מלאי לחוזק הזה</button></div></div>`;
              }).join("")}
              <div class="stock"><div class="line"><span>תחזית אזילת מלאי</span><strong>${forecast.depletion_date?this.esc(forecast.depletion_date):forecast.reason==="prn"?"לא מחושבת (לפי הצורך)":forecast.error?"לא זמינה":"מעבר לטווח התחזית"}</strong></div></div>
              <div class="actions"><button data-take="${m.id}">אישור נטילה</button><button class="secondary" data-add-strength="${m.id}">+ הוספת חוזק</button><button class="secondary" data-edit="${m.id}">עריכת תרופה</button><button class="danger" data-delete="${m.id}">מחיקה</button></div>
            </article>`;
          }).join("")}
        </div>
        ${medications.length===0?'<div class="card empty">עדיין לא הוספת תרופות. לחץ על „הוספת תרופה” כדי להתחיל.</div>':""}
        <div id="editor"></div>
      </div>`;
    this.querySelector("#new").onclick=()=>this.editMedication();
    this.querySelector("#cal-prev").onclick=()=>{this._calendarOffset=(this._calendarOffset||0)-1;this.render();};
    this.querySelector("#cal-next").onclick=()=>{this._calendarOffset=(this._calendarOffset||0)+1;this.render();};
    this.querySelectorAll("[data-edit]").forEach(b=>b.onclick=()=>this.editMedication(medications.find(m=>m.id===b.dataset.edit)));
    this.querySelectorAll("[data-add-strength]").forEach(b=>b.onclick=()=>this.editMedication(medications.find(m=>m.id===b.dataset.addStrength),true));
    this.querySelectorAll("[data-take]").forEach(b=>b.onclick=()=>this.takeMedication(medications.find(m=>m.id===b.dataset.take)));
    this.querySelectorAll("[data-delete]").forEach(b=>b.onclick=()=>this.deleteMedication(b.dataset.delete));
    this.querySelectorAll("[data-stock]").forEach(b=>b.onclick=()=>this.addStock(b.dataset.stock,b.dataset.product));
    this.querySelectorAll("[data-adjust]").forEach(b=>b.onclick=()=>this.adjustStock(b.dataset.adjust,b.dataset.product,b.dataset.batch,b.dataset.quantity));
    this.querySelectorAll("[data-occ-take]").forEach(b=>b.onclick=()=>this.confirmOccurrence(b.dataset.occTake));
    this.querySelectorAll("[data-occ-skip]").forEach(b=>b.onclick=()=>this.skipOccurrence(b.dataset.occSkip));
    this.querySelectorAll("[data-undo]").forEach(b=>b.onclick=()=>this.undoIntake(b.dataset.undo));
    const history=(this.data?.intake||[]).filter(x=>["taken","historical","undone"].includes(x.status)).sort((a,b)=>String(b.taken_at).localeCompare(String(a.taken_at))).slice(0,10);
    const root=this.querySelector(".wrap");
    if(history.length){
      const section=document.createElement("section");
      section.className="card section";
      section.innerHTML="<h2>נטילות אחרונות</h2>"+history.map(x=>{const med=(this.data.medications||[]).find(m=>m.id===x.medication_id);return `<div class="stock"><div class="line"><span>${this.esc(med?.name||"תרופה")} · ${x.actual_dose_mg==null?"מינון לא ידוע":Number(x.actual_dose_mg)+" מ״ג"} ${x.status==="historical"?"· היסטוריה מיובאת":x.status==="undone"?"· בוטלה":""}</span><span class="muted">${this.esc(x.taken_at||"")}</span></div>${x.status==="taken"?`<div class="actions"><button class="secondary" data-undo="${this.esc(x.id)}">ביטול נטילה</button></div>`:""}</div>`;}).join("");
      section.querySelectorAll("[data-undo]").forEach(b=>b.onclick=()=>this.undoIntake(b.dataset.undo));
      root.appendChild(section);
    }
  }
  async confirmOccurrence(occurrenceId) {
    const occurrence=(this.data?.occurrences||[]).find(x=>x.occurrence_id===occurrenceId);
    if(!occurrence)return;
    try{
      await this._hass.callService("pill_manager","take_dose",{
        medication_id:occurrence.medication_id,intake_id:occurrenceId,occurrence_id:occurrenceId,
        actual_dose_mg:Number(occurrence.dose_mg),scheduled_dose_mg:Number(occurrence.dose_mg),
        taken_at:new Date().toISOString(),source:"panel"
      });
      await this.load(true);
    }catch(err){alert("לא ניתן לאשר נטילה: "+(err.message||err));}
  }
  async undoIntake(intakeId) {
    if(!confirm("לבטל את רישום הנטילה ולהחזיר את הכמות למלאי?"))return;
    try{
      await this._hass.callService("pill_manager","undo_dose",{intake_id:intakeId});
      await this.load(true);
    }catch(err){alert("לא ניתן לבטל את הנטילה: "+(err.message||err));}
  }
  async skipOccurrence(occurrenceId) {
    const occurrence=(this.data?.occurrences||[]).find(x=>x.occurrence_id===occurrenceId);
    if(!occurrence)return;
    try{
      await this._hass.callService("pill_manager","skip_dose",{
        medication_id:occurrence.medication_id,occurrence_id:occurrenceId,updated_at:new Date().toISOString()
      });
      await this.load(true);
    }catch(err){alert("לא ניתן לדלג על המנה: "+(err.message||err));}
  }
  editMedication(existing, addStrength = false) {
    this._editorOpen = true;
    const med=existing?JSON.parse(JSON.stringify(existing)):{
      name:"",products:[{id:crypto.randomUUID(),name:"",strength_mg:25,splittable:true,stock_batches:[]}],
      regimen:{mode:"phased",phases:[{start_date:this.todayLocal(),duration_days:null,dose_mg:25,times:["08:00"],weekdays:[0,1,2,3,4,5,6]}]}
    };
    const phased=med.regimen?.mode==="phased";
    const phaseDefaults=med.regimen?.phases?.length?med.regimen.phases:[{
      start_date:this.todayLocal(),duration_days:null,
      dose_mg:med.regimen?.fixed_phase?.dose_mg||25,
      times:med.regimen?.fixed_phase?.times||["08:00"],
      weekdays:med.regimen?.fixed_phase?.weekdays||[0,1,2,3,4,5,6]
    }];
    this.querySelector("#editor").innerHTML=`
      <section class="card editor"><h2>${existing?"עריכת תרופה":"הוספת תרופה"}</h2>
        <div class="form"><div class="wide"><label>שם התרופה</label><input id="med-name" value="${this.esc(med.name)}" placeholder="לדוגמה: תרופה"></div>
          <div><label>איך לנהל את תוכנית הנטילה?</label><select id="mode"><option value="phased" ${phased?"selected":""}>תקופות ותאריכים</option><option value="fixed" ${med.regimen?.mode==="fixed"?"selected":""}>מינון קבוע ללא תאריך סיום</option><option value="prn" ${med.regimen?.mode==="prn"?"selected":""}>לפי הצורך (PRN)</option></select></div>
          <div id="fixed-dose"><label>מינון לכל נטילה במ״ג</label><input id="dose" type="number" min="0.5" step="0.5" value="${med.regimen?.fixed_phase?.dose_mg||25}"></div>
          <div id="fixed-times" class="wide"><label>שעות נטילה (מופרדות בפסיק)</label><input id="times" value="${(med.regimen?.fixed_phase?.times||["08:00"]).join(", ")}"></div>
          <div id="fixed-weekdays" class="wide"><label>ימי נטילה</label><select id="weekdays" multiple size="2">${["ב׳","ג׳","ד׳","ה׳","ו׳","ש׳","א׳"].map((d,i)=>`<option value="${i}" ${(med.regimen?.fixed_phase?.weekdays||[0,1,2,3,4,5,6]).includes(i)?"selected":""}>${d}</option>`).join("")}</select></div>
        </div>
        <div id="phases" style="display:${phased?"block":"none"}">
          <label>תוכנית לפי תקופות — בחר לכל תקופה תאריך התחלה וסיום, מינון, שעות וימי נטילה. השארת תאריך הסיום ריק פירושה שהתקופה ממשיכה עד שתעדכן אותה.</label>
          <div id="phase-list">${phaseDefaults.map((p,i)=>this.phaseEditor(p,i)).join("")}</div>
          <div class="actions"><button class="secondary" id="add-phase">+ הוספת שלב</button><button class="secondary" id="remove-phase">הסרת השלב האחרון</button></div>
          <div class="muted">אפשר להגדיר תקופות נפרדות עם הפסקות ביניהן, אך לא תקופות חופפות. שעות וימי נטילה מוגדרים לכל תקופה בנפרד.</div>
        </div>
        <h2 class="section">מינונים ומלאי לפי אריזה</h2><div id="products">${med.products.map((p,i)=>this.productEditor(p,i,true)).join("")}</div>
        <div class="actions"><button class="secondary" id="add-product">+ הוספת אריזה / חוזק</button></div>
        <div class="actions"><button id="save">שמירה</button><button class="secondary" id="cancel">ביטול</button></div>
        <div id="form-error" class="muted"></div>
      </section>`;
    this.querySelector("#cancel").onclick=()=>{this._editorOpen=false;this.querySelector("#editor").innerHTML="";if(this._refreshPending){this._refreshPending=false;this.load(true);}};
    this.querySelector("#mode").onchange=()=>{const mode=this.querySelector("#mode").value;this.querySelector("#phases").style.display=mode==="phased"?"block":"none";this.querySelector("#fixed-dose").style.display=mode==="fixed"?"block":"none";this.querySelector("#fixed-times").style.display=mode==="fixed"?"block":"none";};
    this.querySelector("#add-product").onclick=()=>{const root=this.querySelector("#products");root.insertAdjacentHTML("beforeend",this.productEditor({id:crypto.randomUUID(),name:"",strength_mg:25,splittable:true,stock_batches:[]},root.children.length));};
    this.querySelector("#add-phase").onclick=()=>this.addPhase();
    this.querySelector("#remove-phase").onclick=()=>{const root=this.querySelector("#phase-list");if(root.children.length>1){root.lastElementChild.remove();root.lastElementChild.querySelector(".phase-end").value="";}else alert("נדרש לפחות שלב אחד.");};
    this.querySelector("#save").onclick=()=>this.saveMedication(med);
    if(addStrength)this.querySelector("#add-product").click();
  }
  phaseEditor(phase,index) {
    const weekdays=phase.weekdays||[0,1,2,3,4,5,6];
    const days=["ב׳","ג׳","ד׳","ה׳","ו׳","ש׳","א׳"];
    const startDate=phase.start_date||this.todayLocal();
    let endDate="";
    if(phase.duration_days!=null){
      const d=new Date(startDate+"T00:00:00");
      d.setDate(d.getDate()+Number(phase.duration_days)-1);
      const pad=n=>String(n).padStart(2,"0");
      endDate=d.getFullYear()+"-"+pad(d.getMonth()+1)+"-"+pad(d.getDate());
    }
    return `<div class="phase-row phase-editor" data-phase-index="${index}">
      <div class="line"><strong>תקופה ${index+1}</strong><span class="muted">מינון לפי תאריכים</span></div>
      <div class="form">
        <div><label>מתאריך</label><input class="phase-start" type="date" value="${this.esc(startDate)}"></div>
        <div><label>עד תאריך (ריק = ממשיך ללא הגבלה)</label><input class="phase-end" type="date" value="${this.esc(endDate)}"></div>
        <div><label>מינון בכל נטילה (מ״ג)</label><input class="phase-dose" type="number" min="0.5" step="0.5" value="${phase.dose_mg||25}"></div>
        <div><label>שעות נטילה (פסיק בין שעות)</label><input class="phase-times" value="${this.esc((phase.times||["08:00"]).join(", "))}"></div>
        <div class="wide"><label>באילו ימים לקחת?</label><select class="phase-weekdays" multiple size="2">${days.map((d,i)=>`<option value="${i}" ${weekdays.includes(i)?"selected":""}>${d}</option>`).join("")}</select></div>
      </div>
    </div>`;
  }
  addPhase() {
    const root=this.querySelector("#phase-list");
    const last=root.lastElementChild;
    const start=last.querySelector(".phase-start").value;
    const end=last.querySelector(".phase-end").value;
    if(!start||!end)return alert("כדי להוסיף תקופה נוספת, יש לבחור תאריך התחלה ותאריך סיום לתקופה הנוכחית.");
    const startDate=new Date(start+"T00:00:00");
    const endDate=new Date(end+"T00:00:00");
    if(Number.isNaN(startDate.getTime())||Number.isNaN(endDate.getTime())||endDate<startDate)
      return alert("תאריך הסיום חייב להיות אחרי תאריך ההתחלה.");
    const duration=Math.round((Date.UTC(endDate.getFullYear(),endDate.getMonth(),endDate.getDate())-Date.UTC(startDate.getFullYear(),startDate.getMonth(),startDate.getDate()))/86400000)+1;
    const nextDate=new Date(endDate);
    nextDate.setDate(nextDate.getDate()+1);
    const pad=n=>String(n).padStart(2,"0");
    const nextStart=nextDate.getFullYear()+"-"+pad(nextDate.getMonth()+1)+"-"+pad(nextDate.getDate());
    const selected=[...last.querySelector(".phase-weekdays").selectedOptions].map(o=>Number(o.value));
    const phase={
      start_date:nextStart,duration_days:null,
      dose_mg:Number(last.querySelector(".phase-dose").value||25),
      times:last.querySelector(".phase-times").value.split(",").map(x=>x.trim()).filter(Boolean),
      weekdays:selected.length?selected:[0,1,2,3,4,5,6]
    };
    last.querySelector(".phase-end").value=end;
    root.insertAdjacentHTML("beforeend",this.phaseEditor(phase,root.children.length));
  }
  productEditor(product,index,isExisting=false) {
    return `<div class="product" data-product-index="${index}" data-id="${this.esc(product.id||crypto.randomUUID())}">
      <div class="form"><div><label>שם האריזה (למשל: 30 טבליות)</label><input class="p-name" value="${this.esc(product.name||"")}" placeholder="למשל טבליות 25 מ״ג"></div>
      <div><label>חוזק של כל טבליה (מ״ג)</label><input class="p-strength" type="number" min="0.5" step="0.5" value="${product.strength_mg||25}"></div>
      <div><label>${isExisting?"כמות קיימת (לשינוי השתמש בכפתור הוספת מלאי בכרטיס)":"כמות טבליות שיש לך"}</label><input class="p-quantity" type="number" min="0" step="${product.splittable?0.5:1}" value="${(product.stock_batches||[]).reduce((s,b)=>s+Number(b.quantity||0),0)}" ${isExisting?"readonly":""}></div>
      <div><label>אפשר לחצות?</label><select class="p-split"><option value="true" ${product.splittable?"selected":""}>כן, חצאים מותרים</option><option value="false" ${!product.splittable?"selected":""}>לא</option></select></div></div>
      <div class="muted">${isExisting?"המלאי הקיים מוצג לקריאה בלבד כדי לשמור על היסטוריית הנטילות. אפשר להוסיף מלאי מכרטיס התרופה.":"הכמות תתווסף למלאי של התרופה בחוזק הזה."}</div></div>`;
  }
  async saveMedication(original) {
    const error=this.querySelector("#form-error");
    try {
      const name=this.querySelector("#med-name").value.trim();
      if(!name)throw new Error("יש להזין שם תרופה");
      const products=[...this.querySelectorAll(".product")].map(el=>{
        const id=el.dataset.id;
        const name=el.querySelector(".p-name").value.trim();
        const strength_mg=Number(el.querySelector(".p-strength").value);
        const quantity=Number(el.querySelector(".p-quantity").value);
        const splittable=el.querySelector(".p-split").value==="true";
        if(!Number.isFinite(strength_mg)||strength_mg<=0||!Number.isFinite(quantity)||quantity<0)throw new Error("יש לבדוק חוזק וכמות מלאי");
        let batches=(original.products||[]).find(p=>p.id===id)?.stock_batches||[];
        const previous=(original.products||[]).find(p=>p.id===id);
        if(previous){const total=batches.reduce((s,b)=>s+Number(b.quantity||0),0);if(Math.abs(total-quantity)>0.0001)throw new Error("לשינוי מלאי קיים השתמש בכפתור „הוספת מלאי”; אין לשנות אותו במסך העריכה.");}
        else if(quantity>0)batches=[{id:crypto.randomUUID(),quantity,received_at:this.todayLocal()}];
        return {id,name,strength_mg,splittable,stock_batches:batches};
      });
      if(!products.length)throw new Error("יש להוסיף לפחות מוצר אחד");
      const mode=this.querySelector("#mode").value;
      let regimen={mode};
      if(mode==="fixed"){
        const dose_mg=Number(this.querySelector("#dose").value);
        const times=this.querySelector("#times").value.split(",").map(x=>x.trim()).filter(Boolean);
        const weekdays=[...this.querySelector("#weekdays").selectedOptions].map(o=>Number(o.value));
        if(!weekdays.length)throw new Error("יש לבחור לפחות יום נטילה אחד");
        regimen={mode:"fixed",fixed_phase:{dose_mg,times,weekdays}};
      } else if(mode==="phased") {
        const rows=[...this.querySelectorAll(".phase-row")];
        const phases=rows.map(row=>({
          start_date:row.querySelector(".phase-start").value,
          duration_days:(()=>{const start=row.querySelector(".phase-start").value;const end=row.querySelector(".phase-end").value;if(!end)return null;const a=new Date(start+"T00:00:00"),b=new Date(end+"T00:00:00");return Math.round((Date.UTC(b.getFullYear(),b.getMonth(),b.getDate())-Date.UTC(a.getFullYear(),a.getMonth(),a.getDate()))/86400000)+1;})(),
          dose_mg:Number(row.querySelector(".phase-dose").value),
          times:row.querySelector(".phase-times").value.split(",").map(x=>x.trim()).filter(Boolean),
          weekdays:[...row.querySelector(".phase-weekdays").selectedOptions].map(o=>Number(o.value))
        }));
        regimen={mode:"phased",phases};
      }
      await this.call("save_medication",{medication:{...original,name,products,regimen}});
      this._editorOpen=false;
      this.querySelector("#editor").innerHTML="";
      this._refreshPending=false;
      await this.load(true);
    } catch(err) { error.textContent=err.message||String(err); }
  }
  async adjustStock(medicationId, productId, batchId, currentQuantity) {
    const quantity = prompt("מהי יתרת המלאי הנכונה באצווה זו?", currentQuantity);
    if (quantity === null) return;
    const amount = Number(quantity);
    if (!Number.isFinite(amount)) return alert("יש להזין מספר תקין");
    const reason = prompt("סיבת תיקון המלאי:");
    if (!reason?.trim()) return;
    try {
      await this._hass.callService("pill_manager", "adjust_stock", {medication_id: medicationId, product_id: productId, batch_id: batchId, quantity: amount, reason: reason.trim(), event_id: crypto.randomUUID(), created_at: new Date().toISOString()});
      await this.load(true);
    } catch (err) { alert("לא ניתן לתקן מלאי: " + (err.message || err)); }
  }
  async addStock(medicationId,productId) {
    const quantity=prompt("כמה יחידות להוסיף למלאי?");
    if(quantity===null)return;
    const amount=Number(quantity);
    if(!Number.isFinite(amount)||amount<=0)return alert("יש להזין כמות חיובית");
    const received=prompt("תאריך קבלה (YYYY-MM-DD)",this.todayLocal());
    if(received===null)return;
    const expires=prompt("תאריך תפוגה (YYYY-MM-DD), או להשאיר ריק","");
    if(expires===null)return;
    try{await this.call("add_stock",{medication_id:medicationId,product_id:productId,batch:{quantity:amount,received_at:received,expires_on:expires||null}});await this.load(true);}
    catch(err){alert("לא ניתן להוסיף מלאי: "+err.message);}
  }
  async takeMedication(medication) {
    if (!medication) return;
    const phase = medication.current_phase;
    const plannedDose = phase?.dose_mg;
    const entered = prompt(
      phase ? "המינון המתוכנן הוא "+plannedDose+" מ״ג. אפשר לשנות כאן רק עבור הנטילה הזו; המשטר לא ישתנה." : "כמה מ״ג נלקחו בפועל?",
      plannedDose == null ? "" : String(plannedDose)
    );
    if (entered === null) return;
    const dose = Number(entered);
    if (!Number.isFinite(dose) || dose <= 0 || Math.abs(dose*2-Math.round(dose*2))>1e-7) {
      return alert("יש להזין מינון חיובי בכפולות של 0.5 מ״ג.");
    }

    const now = new Date();
    const pad = value => String(value).padStart(2, "0");
    const localDate = d => d.getFullYear()+"-"+pad(d.getMonth()+1)+"-"+pad(d.getDate());
    const localTime = d => pad(d.getHours())+":"+pad(d.getMinutes());
    const enteredAt = prompt("תאריך ושעת הנטילה (YYYY-MM-DDTHH:MM). אפשר להשאיר את הזמן הנוכחי.",localDate(now)+"T"+localTime(now));
    if (enteredAt === null) return;
    const takenAt = new Date(enteredAt);
    if (Number.isNaN(takenAt.getTime()) || takenAt.getTime() > now.getTime()) {
      return alert("יש להזין תאריך ושעה תקינים שאינם בעתיד.");
    }

    const dateKey = localDate(takenAt);
    const clock = localTime(takenAt);
    const isToday = dateKey === localDate(now);
    const dueTime = isToday ? (phase?.times || []).filter(t => t <= clock).sort().reverse()
      .find(t => {
        const id = medication.id + ":" + dateKey + ":" + t;
        return !(this.data?.intake || []).some(x => x.occurrence_id === id && x.status === "taken")
          && !(this.data?.occurrences || []).some(x => x.occurrence_id === id && ["skipped","missed"].includes(x.status));
      }) : null;
    const occurrence = dueTime ? medication.id + ":" + dateKey + ":" + dueTime : null;
    const intakeId = occurrence || "manual:" + medication.id + ":" + takenAt.getTime();
    try {
      await this._hass.callService("pill_manager", "take_dose", {
        medication_id: medication.id,
        intake_id: intakeId,
        ...(occurrence ? {occurrence_id: occurrence} : {}),
        actual_dose_mg: dose,
        ...(isToday && phase?.dose_mg != null ? {scheduled_dose_mg: phase.dose_mg} : {}),
        taken_at: takenAt.toISOString(),
        source: isToday ? "panel" : "backdated_panel"
      });
      await this.load(true);
    } catch (err) {
      alert("לא ניתן לאשר נטילה: " + (err.message || err));
    }
  }
  async deleteMedication(id) {
    if(!confirm("למחוק את התרופה? היסטוריית נטילות קיימת מונעת מחיקה."))return;
    try{await this.call("delete_medication",{medication_id:id});await this.load(true);}
    catch(err){alert("לא ניתן למחוק: "+err.message);}
  }
}
customElements.define("pill-manager-panel",PillManagerPanel);
