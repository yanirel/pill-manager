class PillManagerPanel extends HTMLElement {
  set hass(value) { this._hass = value; if (!this._loaded) this.load(); }
  connectedCallback() { this.load(); }
  async call(command, data = {}) {
    return this._hass.callWS({type: "pill_manager_v2/" + command, ...data});
  }
  esc(value) {
    return String(value ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
  }
  async load(force = false) {
    if (!this._hass || this._loading || (this._loaded && !force)) return;
    this._loading = true;
    try { this.data = await this.call("get_data"); this.error = ""; this._loaded = true; }
    catch (err) { this.error = err.message || String(err); }
    finally { this._loading = false; this.render(); }
  }
  render() {
    if (!this._hass) return;
    const medications = this.data?.medications || [];
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
        .form{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin:13px 0}
        label{display:block;font-size:13px;color:#65707c;margin-bottom:5px}
        input,select,textarea{width:100%;padding:10px;border:1px solid #dce1e6;border-radius:9px;font:inherit;background:white;color:#20242b}
        textarea{min-height:105px;direction:ltr;text-align:left;font-family:monospace}.wide{grid-column:1/-1}
        .product{border:1px solid #edf0f2;border-radius:12px;padding:12px;margin:10px 0}
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
        <div class="grid">
          ${medications.map(m => {
            const products = m.products || [];
            const units = products.reduce((sum,p)=>sum+(p.stock_batches||[]).reduce((s,b)=>s+Number(b.quantity||0),0),0);
            const forecast = m.forecast || {};
            return `<article class="card">
              <div class="line"><h2>${this.esc(m.name)}</h2><span class="tag">${m.regimen?.mode==="prn"?"לפי הצורך":m.regimen?.mode==="phased"?"משטר מדורג":"מינון קבוע"}</span></div>
              <div class="muted">סה״כ ${products.length} סוגי מוצר · ${units.toFixed(1)} יחידות במלאי</div>
              ${products.map(p=>`<div class="stock"><div class="line"><strong>${this.esc(p.name||"מוצר")} · ${p.strength_mg} מ״ג</strong><span>${p.splittable?"ניתן לחצייה":"שלם בלבד"}</span></div>
                ${(p.stock_batches||[]).map(b=>`<div class="batch ${Number(b.quantity)<0?"warn":""}">אצווה: ${this.esc(b.quantity)} יח׳ ${Number(b.quantity)<0?"· יתרת מלאי שלילית — נדרשת בדיקה":""} · התקבלה: ${this.esc(b.received_at||"—")} ${b.expires_on?"· תפוגה: "+this.esc(b.expires_on):""} <button class="secondary" data-adjust="${m.id}" data-product="${p.id}" data-batch="${b.id}" data-quantity="${b.quantity}">תיקון יתרה</button></div>`).join("")}
                <div class="actions"><button class="secondary" data-stock="${m.id}" data-product="${p.id}">הוספת מלאי</button></div></div>`).join("")}
              <div class="stock"><div class="line"><span>תחזית אזילת מלאי</span><strong>${forecast.depletion_date?this.esc(forecast.depletion_date):forecast.reason==="prn"?"לא מחושבת (לפי הצורך)":forecast.error?"לא זמינה":"מעבר לטווח התחזית"}</strong></div></div>
              <div class="actions"><button data-take="${m.id}">אישור נטילה</button><button class="secondary" data-edit="${m.id}">עריכה</button><button class="danger" data-delete="${m.id}">מחיקה</button></div>
            </article>`;
          }).join("")}
        </div>
        ${medications.length===0?'<div class="card empty">עדיין לא הוספת תרופות. לחץ על „הוספת תרופה” כדי להתחיל.</div>':""}
        <div id="editor"></div>
      </div>`;
    this.querySelector("#new").onclick=()=>this.editMedication();
    this.querySelectorAll("[data-edit]").forEach(b=>b.onclick=()=>this.editMedication(medications.find(m=>m.id===b.dataset.edit)));
    this.querySelectorAll("[data-take]").forEach(b=>b.onclick=()=>this.takeMedication(medications.find(m=>m.id===b.dataset.take)));
    this.querySelectorAll("[data-delete]").forEach(b=>b.onclick=()=>this.deleteMedication(b.dataset.delete));
    this.querySelectorAll("[data-stock]").forEach(b=>b.onclick=()=>this.addStock(b.dataset.stock,b.dataset.product));
    this.querySelectorAll("[data-adjust]").forEach(b=>b.onclick=()=>this.adjustStock(b.dataset.adjust,b.dataset.product,b.dataset.batch,b.dataset.quantity));
    this.querySelectorAll("[data-occ-take]").forEach(b=>b.onclick=()=>this.confirmOccurrence(b.dataset.occTake));
    this.querySelectorAll("[data-occ-skip]").forEach(b=>b.onclick=()=>this.skipOccurrence(b.dataset.occSkip));
    const history=(this.data?.intake||[]).filter(x=>["taken","historical"].includes(x.status)).sort((a,b)=>String(b.taken_at).localeCompare(String(a.taken_at))).slice(0,10);
    const root=this.querySelector(".wrap");
    if(history.length){
      const section=document.createElement("section");
      section.className="card section";
      section.innerHTML="<h2>נטילות אחרונות</h2>"+history.map(x=>{const med=(this.data.medications||[]).find(m=>m.id===x.medication_id);return `<div class="stock line"><span>${this.esc(med?.name||"תרופה")} · ${x.actual_dose_mg==null?"מינון לא ידוע":Number(x.actual_dose_mg)+" מ״ג"} ${x.status==="historical"?"· היסטוריה מיובאת":""}</span><span class="muted">${this.esc(x.taken_at||"")}</span></div>`;}).join("");
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
  editMedication(existing) {
    const med=existing?JSON.parse(JSON.stringify(existing)):{
      name:"",products:[{id:crypto.randomUUID(),name:"",strength_mg:25,splittable:true,stock_batches:[]}],
      regimen:{mode:"fixed",fixed_phase:{dose_mg:25,times:["08:00"],weekdays:[0,1,2,3,4,5,6]}}
    };
    const phased=med.regimen?.mode==="phased";
    const phaseDefaults=med.regimen?.phases?.length?med.regimen.phases:[{
      start_date:new Date().toISOString().slice(0,10),duration_days:null,
      dose_mg:med.regimen?.fixed_phase?.dose_mg||25,
      times:med.regimen?.fixed_phase?.times||["08:00"],
      weekdays:med.regimen?.fixed_phase?.weekdays||[0,1,2,3,4,5,6]
    }];
    this.querySelector("#editor").innerHTML=`
      <section class="card editor"><h2>${existing?"עריכת תרופה":"הוספת תרופה"}</h2>
        <div class="form"><div class="wide"><label>שם התרופה</label><input id="med-name" value="${this.esc(med.name)}" placeholder="לדוגמה: תרופה"></div>
          <div><label>סוג משטר</label><select id="mode"><option value="fixed" ${med.regimen?.mode==="fixed"?"selected":""}>מינון קבוע</option><option value="phased" ${phased?"selected":""}>שלבים מדורגים</option><option value="prn" ${med.regimen?.mode==="prn"?"selected":""}>לפי הצורך (PRN)</option></select></div>
          <div id="fixed-dose"><label>מינון יומי במ״ג</label><input id="dose" type="number" min="0.5" step="0.5" value="${med.regimen?.fixed_phase?.dose_mg||25}"></div>
          <div id="fixed-times" class="wide"><label>שעות נטילה (מופרדות בפסיק)</label><input id="times" value="${(med.regimen?.fixed_phase?.times||["08:00"]).join(", ")}"></div>
        </div>
        <div id="phases" style="display:${phased?"block":"none"}">
          <label>שלבי מינון — השלב האחרון ממשיך עד שתעדכן אותו</label>
          <div id="phase-list">${phaseDefaults.map((p,i)=>this.phaseEditor(p,i)).join("")}</div>
          <div class="actions"><button class="secondary" id="add-phase">+ הוספת שלב</button><button class="secondary" id="remove-phase">הסרת השלב האחרון</button></div>
          <div class="muted">השלבים חייבים להיות רצופים. משך שלב נמדד בימים, ושעות וימי נטילה מוגדרים לכל שלב בנפרד.</div>
        </div>
        <h2 class="section">מוצרים וחוזקים</h2><div id="products">${med.products.map((p,i)=>this.productEditor(p,i)).join("")}</div>
        <div class="actions"><button class="secondary" id="add-product">+ הוספת חוזק / מוצר</button></div>
        <div class="actions"><button id="save">שמירה</button><button class="secondary" id="cancel">ביטול</button></div>
        <div id="form-error" class="muted"></div>
      </section>`;
    this.querySelector("#cancel").onclick=()=>this.querySelector("#editor").innerHTML="";
    this.querySelector("#mode").onchange=()=>{const mode=this.querySelector("#mode").value;this.querySelector("#phases").style.display=mode==="phased"?"block":"none";this.querySelector("#fixed-dose").style.display=mode==="fixed"?"block":"none";this.querySelector("#fixed-times").style.display=mode==="fixed"?"block":"none";};
    this.querySelector("#add-product").onclick=()=>{const root=this.querySelector("#products");root.insertAdjacentHTML("beforeend",this.productEditor({id:crypto.randomUUID(),name:"",strength_mg:25,splittable:true,stock_batches:[]},root.children.length));};
    this.querySelector("#add-phase").onclick=()=>this.addPhase();
    this.querySelector("#remove-phase").onclick=()=>{const root=this.querySelector("#phase-list");if(root.children.length>1){root.lastElementChild.remove();root.lastElementChild.querySelector(".phase-duration").value="";}else alert("נדרש לפחות שלב אחד.");};
    this.querySelector("#save").onclick=()=>this.saveMedication(med);
  }
  phaseEditor(phase,index) {
    const weekdays=phase.weekdays||[0,1,2,3,4,5,6];
    const days=["א׳","ב׳","ג׳","ד׳","ה׳","ו׳","ש׳"];
    return `<div class="product phase-row" data-phase-index="${index}">
      <div class="form">
        <div><label>תאריך התחלה</label><input class="phase-start" type="date" value="${this.esc(phase.start_date||new Date().toISOString().slice(0,10))}"></div>
        <div><label>משך השלב בימים (ריק = ללא הגבלה)</label><input class="phase-duration" type="number" min="1" step="1" value="${phase.duration_days??""}" placeholder="ללא הגבלה"></div>
        <div><label>מינון במ״ג</label><input class="phase-dose" type="number" min="0.5" step="0.5" value="${phase.dose_mg||25}"></div>
        <div><label>שעות (מופרדות בפסיק)</label><input class="phase-times" value="${this.esc((phase.times||["08:00"]).join(", "))}"></div>
        <div class="wide"><label>ימי נטילה</label><select class="phase-weekdays" multiple size="2">${days.map((d,i)=>`<option value="${i}" ${weekdays.includes(i)?"selected":""}>${d}</option>`).join("")}</select></div>
      </div>
    </div>`;
  }
  addPhase() {
    const root=this.querySelector("#phase-list");
    const last=root.lastElementChild;
    const duration=Number(last.querySelector(".phase-duration").value||30);
    if(!Number.isInteger(duration)||duration<1)return alert("יש להזין משך שלב תקין לפני הוספת שלב נוסף.");
    const start=last.querySelector(".phase-start").value;
    if(!start)return alert("יש להזין תאריך התחלה לשלב הנוכחי.");
    const nextDate=new Date(start+"T00:00:00");
    nextDate.setDate(nextDate.getDate()+duration);
    const pad=n=>String(n).padStart(2,"0");
    const nextStart=nextDate.getFullYear()+"-"+pad(nextDate.getMonth()+1)+"-"+pad(nextDate.getDate());
    last.querySelector(".phase-duration").value=duration;
    const selected=[...last.querySelector(".phase-weekdays").selectedOptions].map(o=>Number(o.value));
    const phase={
      start_date:nextStart,duration_days:null,
      dose_mg:Number(last.querySelector(".phase-dose").value||25),
      times:last.querySelector(".phase-times").value.split(",").map(x=>x.trim()).filter(Boolean),
      weekdays:selected.length?selected:[0,1,2,3,4,5,6]
    };
    root.insertAdjacentHTML("beforeend",this.phaseEditor(phase,root.children.length));
  }
  productEditor(product,index) {
    return `<div class="product" data-product-index="${index}" data-id="${this.esc(product.id||crypto.randomUUID())}">
      <div class="form"><div><label>שם / תיאור האריזה</label><input class="p-name" value="${this.esc(product.name||"")}" placeholder="למשל טבליות 25 מ״ג"></div>
      <div><label>חוזק לטבליה (מ״ג)</label><input class="p-strength" type="number" min="0.5" step="0.5" value="${product.strength_mg||25}"></div>
      <div><label>מלאי התחלתי (יחידות)</label><input class="p-quantity" type="number" min="0" step="${product.splittable?0.5:1}" value="${(product.stock_batches||[]).reduce((s,b)=>s+Number(b.quantity||0),0)}"></div>
      <div><label>אפשר לחצות?</label><select class="p-split"><option value="true" ${product.splittable?"selected":""}>כן, חצאים מותרים</option><option value="false" ${!product.splittable?"selected":""}>לא</option></select></div></div>
      <div class="muted">מלאי התחלתי נשמר כאצווה חדשה בעת יצירת מוצר.</div></div>`;
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
        else if(quantity>0)batches=[{id:crypto.randomUUID(),quantity,received_at:new Date().toISOString()}];
        return {id,name,strength_mg,splittable,stock_batches:batches};
      });
      if(!products.length)throw new Error("יש להוסיף לפחות מוצר אחד");
      const mode=this.querySelector("#mode").value;
      let regimen={mode};
      if(mode==="fixed"){
        const dose_mg=Number(this.querySelector("#dose").value);
        const times=this.querySelector("#times").value.split(",").map(x=>x.trim()).filter(Boolean);
        regimen={mode:"fixed",fixed_phase:{dose_mg,times,weekdays:[0,1,2,3,4,5,6]}};
      } else if(mode==="phased") {
        const rows=[...this.querySelectorAll(".phase-row")];
        const phases=rows.map(row=>({
          start_date:row.querySelector(".phase-start").value,
          duration_days:row.querySelector(".phase-duration").value===""?null:Number(row.querySelector(".phase-duration").value),
          dose_mg:Number(row.querySelector(".phase-dose").value),
          times:row.querySelector(".phase-times").value.split(",").map(x=>x.trim()).filter(Boolean),
          weekdays:[...row.querySelector(".phase-weekdays").selectedOptions].map(o=>Number(o.value))
        }));
        regimen={mode:"phased",phases};
      }
      await this.call("save_medication",{medication:{...original,name,products,regimen}});
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
    const received=prompt("תאריך קבלה (YYYY-MM-DD)",new Date().toISOString().slice(0,10));
    if(received===null)return;
    const expires=prompt("תאריך תפוגה (YYYY-MM-DD), או להשאיר ריק","");
    if(expires===null)return;
    try{await this.call("add_stock",{medication_id:medicationId,product_id:productId,batch:{quantity:amount,received_at:received,expires_on:expires||null}});await this.load(true);}
    catch(err){alert("לא ניתן להוסיף מלאי: "+err.message);}
  }
  async takeMedication(medication) {
    if (!medication) return;
    const phase = medication.current_phase;
    if (medication.regimen?.mode !== "prn" && !phase) {
      return alert("אין משטר מינון פעיל לתאריך הנוכחי.");
    }
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
    const dateKey = now.getFullYear()+"-"+pad(now.getMonth()+1)+"-"+pad(now.getDate());
    const clock = pad(now.getHours())+":"+pad(now.getMinutes());
    const dueTime = (phase?.times || []).filter(t => t <= clock).sort().reverse()
      .find(t => {
        const id = medication.id + ":" + dateKey + ":" + t;
        return !(this.data?.intake || []).some(x => x.occurrence_id === id && x.status === "taken")
          && !(this.data?.occurrences || []).some(x => x.occurrence_id === id && ["skipped","missed"].includes(x.status));
      });
    const occurrence = dueTime ? medication.id + ":" + dateKey + ":" + dueTime
      : "panel:" + medication.id + ":" + dateKey + ":" + clock;
    try {
      await this._hass.callService("pill_manager", "take_dose", {
        medication_id: medication.id,
        intake_id: occurrence,
        occurrence_id: occurrence,
        actual_dose_mg: Number(dose),
        ...(phase?.dose_mg != null ? {scheduled_dose_mg: phase.dose_mg} : {}),
        taken_at: now.toISOString(),
        source: "panel"
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
