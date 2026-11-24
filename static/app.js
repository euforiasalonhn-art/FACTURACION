const pcLabel=id=>'PC '+(Number(id||0)+1);
// La caja identifica la terminal; el ID del turno solo identifica una apertura.
const cashNumber=shift=>Number(shift?.cash_number??(Number(shift?.terminal_id??auth?.terminal?.id??0)+1));
const cashLabel=shift=>'CAJA #'+cashNumber(shift);
function formatCashDate(value){
 if(!value)return '—';
 const raw=String(value),dated=/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?$/.test(raw)?raw+'-06:00':raw;
 const date=new Date(dated);if(Number.isNaN(date.getTime()))return 'FECHA NO DISPONIBLE';
 const parts=new Intl.DateTimeFormat('es-HN',{timeZone:'America/Tegucigalpa',day:'2-digit',month:'long',year:'numeric',hour:'2-digit',minute:'2-digit',second:'2-digit',hour12:true}).formatToParts(date);
 const part=type=>parts.find(p=>p.type===type)?.value||'';
 return part('day')+' '+part('month').toLocaleUpperCase('es')+' '+part('year')+' · '+String(Number(part('hour'))%12||12).padStart(2,'0')+':'+part('minute')+':'+part('second')+' '+part('dayPeriod').replace(/[\s.]/g,'').toUpperCase();
}
const $=id=>document.getElementById(id),esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])),fmt=n=>'L '+(n/100).toLocaleString('es-HN',{minimumFractionDigits:2,maximumFractionDigits:2});
let cashPanelShiftId=null;let categoryOrder=[];let fiscalConfig=null,lastReceiptId=null,commerceConfig={employee:0,senior:0,owner_enabled:false};
let auth=null,loginRole='local',customers=[],nativePrinter=null;
let products=[],branches=[],cart=[],category='',quote=null,report=[],editing=null,saleKey=null,quoteVersion=0;

let receiptHideTimer;
const receiptDialog=document.getElementById('receipt');
function scheduleReceiptClose(delay){clearTimeout(receiptHideTimer);if(receiptDialog.open)receiptHideTimer=setTimeout(()=>receiptDialog.close(),delay)}
new MutationObserver(()=>{
 scheduleReceiptClose(5000);
}).observe(receiptDialog,{attributes:true,attributeFilter:['open']});
for(const event of ['pointerdown','pointermove','click','wheel','scroll','keydown','input','touchstart'])receiptDialog.addEventListener(event,()=>scheduleReceiptClose(300000),{capture:true,passive:true});
receiptDialog.addEventListener('close',()=>clearTimeout(receiptHideTimer));

// Return from secondary screens without changing the current purchase.
const backToMain=document.createElement('button');
backToMain.id='backToMain';backToMain.type='button';backToMain.textContent='← VOLVER · ESC';backToMain.hidden=true;
document.querySelector('main>header').before(backToMain);
function returnToMain(){
 if(!auth?.role||document.querySelector('dialog[open]'))return;
 $('sessionMenu').hidden=true;
 showView(auth.role==='accountant'?'accounting':'pos');
}
backToMain.onclick=returnToMain;
function syncBackToMain(){backToMain.hidden=!auth?.role||!$('pos').hidden||auth.role==='accountant'}
new MutationObserver(syncBackToMain).observe($('pos'),{attributes:true,attributeFilter:['hidden']});
document.addEventListener('keydown',event=>{
 if(event.key!=='Escape'||event.defaultPrevented||document.querySelector('dialog[open]'))return;
 if(auth?.role&&$('pos').hidden&&auth.role!=='accountant'){event.preventDefault();returnToMain()}
});
function toast(s){$('toast').textContent=s;$('toast').hidden=false;setTimeout(()=>$('toast').hidden=true,5000)}
async function api(path,data,method='POST'){
 const meta=document.querySelector('meta[name="pos-token"]');
 for(let attempt=0;attempt<2;attempt++){
  const r=await fetch('/api/'+path,data?{method,headers:{'Content-Type':'application/json','X-POS-Token':meta.content},body:JSON.stringify(data)}:{});const raw=await r.text();let d;
  try{d=JSON.parse(raw)}catch{throw Error('No se pudo calcular o guardar. Revisa la conexión con PC 1 y vuelve a intentar.')}
  if(d.request_token)meta.content=d.request_token;
  if(r.status===403&&d.refresh_token&&attempt===0){const fresh=await fetch('/api/auth/state');const state=await fresh.json();if(state.request_token){meta.content=state.request_token;continue}}
  if(!r.ok){if(d.central_pending)loadPendingSale().catch(()=>{});const error=Error(d.error||'No se pudo completar la operación');error.restartBranch=!!d.restart_branch;throw error}
  return d;
 }
 throw Error('Actualiza la ventana para restablecer la conexión con PC 1.');
}
function handle(fn){return async e=>{try{await fn(e)}catch(err){toast(err.message)}}}
function payload(){return {employee_meal:$('employeeMeal').checked,notes:$('orderNotes').value,order_name:$('orderName').value,service:$('orderService').value,delivery_fee:$('deliveryFee').value,items:cart.map(x=>({id:x.id,quantity:x.quantity})),discount:$('discount').value,discount_type:'PERCENT',discount_profile:$('discountProfile').value,discount_employee_id:discountPerson?.employee_id,discount_beneficiary_name:discountPerson?.name,discount_beneficiary_identity:discountPerson?.identity,special_order:$('specialOrder').checked,branch_id:Number($('branch').value),invoice_type:$('type').value,customer_name:$('type').value==='NORMAL'?'CONSUMIDOR FINAL':$('customerName').value,customer_rtn:$('type').value==='NORMAL'?'':$('rtn').value,purchase_order:$('purchaseOrder').value,exemption_certificate:$('exemptionCertificate').value,sag:$('sag').value}}
function renderProducts(){const excluded=[];const normalize=x=>x.normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase();const sorted=products.filter(p=>!excluded.includes(normalize(p.category))).sort((a,b)=>a.name.localeCompare(b.name,'es',{sensitivity:'base'}));const cats=[...new Set(sorted.map(p=>p.category))].sort((a,b)=>{const ia=categoryOrder.indexOf(a),ib=categoryOrder.indexOf(b);return (ia<0?9999:ia)-(ib<0?9999:ib)||a.localeCompare(b,'es',{sensitivity:'base'})});if(!cats.includes(category))category=cats[0]||'';$('categories').innerHTML=cats.map(c=>`<button data-cat="${esc(c)}" class="${c===category?'active':''}">${esc(c||'Todas las categorías')}</button>`).join('')+`<button type="button" id="orderNotesOpen" data-order-notes aria-haspopup="dialog" aria-controls="orderNotesDialog" class="${$('orderNotes').value.trim()||$('orderName').value.trim()?'has-order-notes':''}">NOTAS${$('orderNotes').value.trim()||$('orderName').value.trim()?' •':''}</button>`;$('catalog').innerHTML=sorted.filter(p=>(!category||p.category===category)&&p.name.toLowerCase().includes($('search').value.toLowerCase())).map(p=>`<button class="product" data-add="${p.id}">${p.image_url?`<img class="product-photo" src="${esc(p.image_url)}" alt="${esc(p.name)}" loading="lazy">`:`<span class="icon">${'SIN FOTO'}</span>`}<b>${esc(p.name)}</b><strong>${p.price?fmt(p.price):'Configurar precio'}</strong></button>`).join('');$('productRows').innerHTML=products.map(p=>`<tr><td class="photo-cell"><button class="photo-button" data-photo="${p.id}" title="Asignar o cambiar foto de ${esc(p.name)}">${p.image_url?`<img src="${esc(p.image_url)}" alt="${esc(p.name)}">`:'📷<span>Agregar foto</span>'}</button>${p.image_url?`<button class="remove-photo" data-remove-photo="${p.id}" aria-label="Quitar foto de ${esc(p.name)}">Quitar foto</button>`:''}</td><td>${esc(p.name)}</td><td>${esc(p.category)}</td><td class="price-cell"><button class="price-button" data-price="${p.id}" title="Un clic para modificar el precio de ${esc(p.name)}">${fmt(p.price)} <span>✎</span></button></td><td>${esc(p.tax_type)}</td><td><button data-edit="${p.id}">Editar</button></td></tr>`).join('')}
async function renderCart(){saleKey=null;$('pay').textContent=$('employeeMeal').checked?'ALIMENTACION DE EMPLEADOS':$('specialOrder').checked?'Registrar consumo sin cobro':'Continuar cobro · F10 →';const version=++quoteVersion;$('cart').innerHTML=cart.length?cart.map(x=>`<div class="cartline"><b><button type="button" data-remove-line="${x.id}" aria-label="Eliminar ${esc(x.name)}">🗑</button> ${esc(x.name)}</b><div class="row"><span>${$('employeeMeal').checked?'1 unidad':`<button data-minus="${x.id}">−</button> ${x.quantity} <button data-plus="${x.id}">+</button>`}</span><strong>${fmt(x.price*x.quantity)}</strong></div></div>`).join(''):'<div class="empty">Tu pedido empieza aquí<br>Selecciona productos del menú</div>';quote=null;$('pay').disabled=true;if(!cart.length){$('companyBenefitNotice').hidden=true;$('totals').innerHTML='<div class="sum total"><span>Total</span><span>L 0.00</span></div>';return}try{const q=await api('quote',payload());if(version!==quoteVersion)return;quote=q;document.querySelectorAll('#cart .cartline').forEach((el,i)=>{if(q.items[i])el.querySelector('strong').textContent=fmt(q.items[i].line_total)});$('companyBenefitNotice').textContent=q.company_benefit?'Beneficio '+q.company_benefit.kind+' · '+q.company_benefit.name:'';$('companyBenefitNotice').hidden=!q.company_benefit;$('totals').innerHTML=($('employeeMeal').checked?[['Valor del menú (referencia)',q.total],['Cobrado',0]]:[['Importe de productos',q.listed_total],['Productos sin descuento',q.no_discount_total||0],['Descuento',-q.discount],['Subtotal neto',q.subtotal],['ISV 15%',q.tax_15],['ISV 18%',q.tax_18],['Envío por cuenta de tercero',q.delivery_fee||0],['Total',q.total]]).filter(([s,n])=>['Total','Cobrado'].includes(s)).map(([s,n])=>`<div class="sum ${['Total','Cobrado'].includes(s)?'total':''}"><span>${s}</span><span>${fmt(n)}</span></div>`).join('');$('pay').disabled=false}catch(e){if(version===quoteVersion){$('totals').textContent=e.message;toast(e.message)}}}
async function loadBranches(){branches=await api('branches');const active=branches.filter(b=>b.active);const old=$('branch').value;$('branch').innerHTML=active.map(b=>`<option value="${b.id}">${esc(b.name)}</option>`).join('');if(old&&active.some(b=>b.id==old))$('branch').value=old;else if(auth&&active.some(b=>b.id==auth.branch.id))$('branch').value=auth.branch.id;else if(active.length)$('branch').value=active[0].id;$('branch').disabled=auth?.role==='local'||auth?.terminal?.remote;const previousAcc=$('accBranch').value;$('accBranch').innerHTML='<option value="all">Todas las sucursales de esta instalación</option>'+active.map(b=>`<option value="${b.id}">${esc(b.name)}</option>`).join('');$('accBranch').value=previousAcc||'all';$('assignedBranch').innerHTML=active.map(b=>`<option value="${b.id}">${esc(b.name)}</option>`).join('');if(auth&&active.some(b=>b.id===auth.branch.id))$('assignedBranch').value=auth.branch.id;$('branchList').innerHTML=branches.map(b=>`<div class="branch-card ${b.active?'':'branch-inactive'}"><b>${esc(b.name)}</b><p>${b.active?'Activa':'Retirada'} · ${esc(b.address)} · RTN ${esc(b.rtn||'sin configurar')} · Próximo número: ${b.next_invoice}</p>${b.active?`<button data-branch-reset="${b.id}" data-branch-name="${esc(b.name)}">Cambiar contraseña</button> <button data-branch-remove="${b.id}" data-branch-name="${esc(b.name)}">Retirar sucursal</button>`:`<button data-branch-restore="${b.id}">Restaurar sucursal</button>`}</div>`).join('');if(auth)auth.branch_options=active.map(b=>({id:b.id,name:b.name}));syncHeaderBranch()}
function applyProducts(data){products=data;cart=cart.map(x=>({...x,...products.find(p=>p.id===x.id),quantity:x.quantity}));renderProducts()}
async function loadProducts(){await loadCategoryOrder();applyProducts(await api('products'))}
async function reports(){const params=new URLSearchParams({branch_id:$('branch').value,start:$('start').value,end:$('end').value,type:$('reportType').value,payment:$('reportPayment').value});report=await api('reports?'+params);$('stats').innerHTML=[['Ventas normales',report.filter(r=>r.status==='EMITIDA'&&r.invoice_type==='NORMAL').reduce((a,r)=>a+(r.sales_total??r.total),0)],['Ventas RTN',report.filter(r=>r.status==='EMITIDA'&&r.invoice_type==='RTN').reduce((a,r)=>a+(r.sales_total??r.total),0)],...['Efectivo','Transferencia','Tarjeta'].map(m=>[m,report.filter(r=>r.status==='EMITIDA').reduce((a,r)=>a+(r.sales_payments?.[m]||0),0)]),['Envíos por cuenta de tercero',report.filter(r=>r.status==='EMITIDA').reduce((a,r)=>a+(r.delivery_fee||0),0)],['Venta de productos',report.filter(r=>r.status==='EMITIDA').reduce((a,r)=>a+(r.sales_total??r.total),0)]].map(([s,n])=>`<div>${s}<strong>${fmt(n)}</strong></div>`).join('');$('reportRows').innerHTML=report.length?report.map(r=>`<tr><td>${esc(r.fiscal_number||('#'+r.number))}</td><td>${esc(r.created_at.replace('T',' '))}<br>${esc(r.terminal_name||'PC 1')}<br>${esc(r.cashier||'')}</td><td>${r.invoice_type}</td><td>${esc(r.customer_name)}<br>${esc(r.customer_rtn)}</td><td>${esc(r.payment_method)}</td><td>${r.status}</td><td>${fmt(r.sales_total??r.total)}${r.delivery_fee?`<br>Envío: ${fmt(r.delivery_fee)}<br>Factura: ${fmt(r.total)}`:''}</td><td><button data-receipt="${r.id}">Ver</button> ${r.status==='EMITIDA'?`<button data-void="${r.id}">Anular</button>`:''}</td></tr>`).join(''):'<tr><td colspan="8">No hay ventas para estos filtros.</td></tr>'}
async function receipt(id,autoPrint=false){$('receiptCopy').disabled=false;lastReceiptId=id;const r=await api('invoices/'+id+'?copy='+$('receiptCopy').value),s=r.snapshot;if(r.receipt_html){$('receiptBody').innerHTML=r.receipt_html;if(!$('receipt').open)$('receipt').showModal();if(autoPrint&&nativePrinter)nativePrinter.autoPrint();return;}$('receiptBody').innerHTML=`<img class="ticket-logo" src="/static/brand/logo.png" alt="FRY Chicken"><h1>FRY CHICKEN</h1><p>${esc(s.branch.name)}<br>${esc(s.branch.address)}<br>RTN emisor: ${esc(s.branch.rtn||'Sin configurar')}</p><b>COMPROBANTE INTERNO #${r.number}</b><p>NO ES FACTURA FISCAL AUTORIZADA<br>${r.invoice_type} · ${r.status}<br>${esc(r.created_at.replace('T',' '))}</p><p>${esc(r.customer_name)}<br>${esc(r.customer_rtn)}</p><table>${s.items.map(x=>`<tr><td>${x.quantity} × ${esc(x.name)}<br>${fmt(x.price)} c/u · ${esc(x.tax_type)}</td><td>${fmt(x.line_total)}</td></tr>`).join('')}</table>${[['Subtotal',r.subtotal],['ISV estimado 15%',r.tax_15],['ISV estimado 18%',r.tax_18],['Descuento',-r.discount],['TOTAL',r.total],['Recibido',r.amount_received],['Cambio',r.amount_received-r.total]].map(([k,v])=>`<div class="sum"><b>${k}</b><span>${fmt(v)}</span></div>`).join('')}<p>Pago: ${esc(r.payment_method)}<br>¡Gracias por tu compra!</p>`;$('receipt').showModal();if(autoPrint&&nativePrinter)nativePrinter.autoPrint()}
document.addEventListener('click',handle(async e=>{const b=e.target.closest('button');if(!b)return;const d=b.dataset;if(d.view){document.body.classList.toggle('pos-screen',d.view==='pos');if(['reports','products','branches','settings','fiscal','meals','backup','terminals','companies'].includes(d.view)&&auth?.role!=='admin')throw Error('Acceso exclusivo del administrador');document.querySelectorAll('.view').forEach(v=>v.hidden=v.id!==d.view);document.querySelectorAll('nav button').forEach(x=>x.classList.toggle('active',x===b));$('title').textContent=b.textContent.slice(2);if(d.view==='pos')requestAnimationFrame(fitSalePanels);if(d.view==='pos')$('title').textContent=branches.find(b=>b.id==$('branch').value)?.name||'Sucursal';if(d.view==='companies')await loadCompanyBenefits();if(d.view==='terminals')await loadTerminalAdmin();if(d.view==='backup')await loadBackupSettings();if(d.view==='goals')await loadGoals();if(d.view==='meals')await loadMeals();if(d.view==='reports')await reports();if(d.view==='branches')await loadBranches();if(d.view==='clients')await loadCustomers();if(d.view==='settings'){fillSettings();await loadNoDiscount();await loadCancellationEmail();await loadEmployees();await loadCommerce();await loadAccountants()};if(d.view==='accounting')await loadAccounting();if(d.view==='cash')await loadCash();if(d.view==='fiscal')await loadFiscal()}if(d.cat!==undefined){category=d.cat;renderProducts()}if(d.add){if($('employeeMeal').checked)throw Error('Selecciona solo el plato y el refresco en Almuerzo de empleado');const p=products.find(x=>x.id==d.add);if(!p.price)throw Error('Configura el precio en Productos y precios');const x=cart.find(x=>x.id===p.id);if(x)x.quantity++;else cart.push({...p,quantity:1});await renderCart()}if(d.plus||d.minus){if($('employeeMeal').checked)throw Error('El almuerzo solo permite una unidad de cada producto');const x=cart.find(x=>x.id==(d.plus||d.minus));x.quantity+=d.plus?1:-1;cart=cart.filter(x=>x.quantity>0);await renderCart()}if(d.price)await editPrice(b,Number(d.price));if(d.photo){photoProduct=Number(d.photo);$('rowPhoto').value='';$('rowPhoto').click()}if(d.removePhoto&&confirm('¿Quitar la foto del producto?')){applyProducts(await api('products/'+d.removePhoto+'/photo',{},'DELETE'));toast('Foto eliminada')}if(d.edit){clearPhotoPreview();editing=Number(d.edit);const p=products.find(p=>p.id===editing);for(const key of ['name','category','tax_type'])$('productForm').elements[key].value=p[key];$('productForm').elements.price.value=p.price/100;$('productForm').scrollIntoView()}if(d.receipt)await receipt(d.receipt);if(d.void&&confirm('¿Anular este comprobante? Se conservarán el registro y su número.')){const reason=prompt('Motivo de anulación:');if(!reason)return;await api('invoices/'+d.void+'/void',{reason});await reports()}}));
$('search').oninput=renderProducts;$('type').onchange=()=>{$('customer').hidden=$('type').value!=='RTN'};$('discountProfile').onchange=handle(openDiscountPerson);$('specialOrder').onchange=handle(async()=>{if($('specialOrder').checked){$('employeeMeal').checked=false;$('mealFields').hidden=true;document.body.classList.remove('employee-meal-mode');cart=[]}await renderCart()});$('discountType').onchange=()=>{$('discount').value=0;$('discountProfile').value='NONE';renderCart()};$('clear').onclick=handle(async()=>{if(cart.length&&confirm('¿Vaciar el pedido?')){cart=[];resetOrderFields();resetDiscountPerson();await renderCart()}});
$('pay').onclick=handle(async()=>{if(!quote)return;if(!await ensureBackup())return;if(!await requireCash(false))return;if($('employeeMeal').checked){await saveMeal();return}if($('specialOrder').checked){await saveSpecial();return}if($('type').value==='RTN'&&(!$('customerName').value.trim()||!/^\d{14}$/.test($('rtn').value)))throw Error('Completa nombre y RTN de 14 dígitos');$('payTotal').textContent=fmt(quote.total);beginPayment();saleKey=saleKey||crypto.randomUUID();$('payment').showModal()});
let committedPayment={payCash:0,payTransfer:0,payCard:0,received:0},manualReceived=false,paymentInvalid=new Set();
function beginPayment(){committedPayment={payCash:0,payTransfer:0,payCard:0,received:quote.total};manualReceived=false;paymentInvalid.clear();$('method').value='Efectivo';for(const id of ['payCash','payTransfer','payCard'])$(id).value='0.00';$('received').value=(quote.total/100).toFixed(2);$('paymentError').textContent='';change()}
function paymentAmounts(){const m=$('method').value;return m==='Mixto'?{Efectivo:committedPayment.payCash,Transferencia:committedPayment.payTransfer,Tarjeta:committedPayment.payCard}:{Efectivo:m==='Efectivo'?quote.total:0,Transferencia:m==='Transferencia'?committedPayment.payTransfer:0,Tarjeta:m==='Tarjeta'?committedPayment.payCard:0}}
function paymentFields(){return $('method').value==='Mixto'?['payCash','payTransfer','payCard','received']:$('method').value==='Tarjeta'?['payCard']:$('method').value==='Transferencia'?['payTransfer']:['received']}
function paymentIsValid(){if(!quote||paymentInvalid.size)return false;const p=paymentAmounts();return p.Efectivo+p.Transferencia+p.Tarjeta===quote.total&&(!p.Efectivo||committedPayment.received>=p.Efectivo)}
function change(){
 if(!quote)return;const m=$('method').value,mixed=m==='Mixto',p=paymentAmounts(),applied=p.Efectivo+p.Transferencia+p.Tarjeta;
 $('mixedFields').hidden=m==='Efectivo';for(const [id,method] of [['payCash','Efectivo'],['payTransfer','Transferencia'],['payCard','Tarjeta']])$(id).closest('label').hidden=!mixed&&m!==method;
 $('receivedLabel').hidden=!mixed&&m!=='Efectivo';$('received').disabled=false;
 $('paymentHint').textContent=mixed?'Digita cuánto se pagó con cada medio. La suma debe ser igual al total.':m==='Efectivo'?'Digita el efectivo que entregó el cliente. El programa calcula el cambio.':'Digita el monto pagado con '+m.toLowerCase()+'. Debe ser igual al total. Si combina medios de pago, selecciona Mixto.';
 const remaining=quote.total-applied;$('paymentBalance').textContent='MONTO REGISTRADO: '+fmt(applied)+(remaining>0?' · FALTA: '+fmt(remaining):remaining<0?' · EXCEDE EL TOTAL: '+fmt(-remaining):' · MONTO COMPLETO');
 $('change').hidden=!p.Efectivo;$('change').textContent=committedPayment.received>=p.Efectivo?'CAMBIO: '+fmt(committedPayment.received-p.Efectivo):'FALTA EFECTIVO: '+fmt(p.Efectivo-committedPayment.received);$('confirmPay').disabled=!paymentIsValid();
}
function commitPayment(id,format=true){const raw=$(id).value.trim();if($(id).validity.badInput||!/^(?:\d+(?:\.\d{0,2})?)?$/.test(raw)||!Number.isFinite(Number(raw))||Number(raw)>100000000){paymentInvalid.add(id);$('paymentError').textContent='Ingresa un importe válido, con un máximo de dos decimales.';$('confirmPay').disabled=true;return false}paymentInvalid.delete(id);committedPayment[id]=Math.round(Number(raw||0)*100);if(format)$(id).value=(committedPayment[id]/100).toFixed(2);if(id==='received')manualReceived=true;if(id==='payCash'&&!manualReceived){committedPayment.received=committedPayment.payCash;$('received').value=(committedPayment.received/100).toFixed(2)}$('paymentError').textContent='';change();return true}
for(const id of ['payCash','payTransfer','payCard','received']){$(id).oninput=()=>commitPayment(id,false);$(id).onblur=()=>commitPayment(id);$(id).onkeydown=e=>{if(e.key==='Enter'){e.preventDefault();if(commitPayment(id)){const fields=paymentFields();const next=fields[fields.indexOf(id)+1];if(next)$(next).focus();else $('confirmPay').focus()}}}}
$('method').onchange=()=>{manualReceived=false;paymentInvalid.clear();for(const id of ['payCash','payTransfer','payCard']){committedPayment[id]=0;$(id).value='0.00'}const m=$('method').value;committedPayment.received=m==='Efectivo'?quote.total:0;$('received').value=(committedPayment.received/100).toFixed(2);if(m==='Tarjeta')$('payCard').value='';if(m==='Transferencia')$('payTransfer').value='';$('paymentError').textContent='';change();$(paymentFields()[0]).focus()};
$('cancelPay').onclick=()=>$('payment').close();$('confirmPay').onclick=handle(async()=>{if(!paymentIsValid()){$('paymentError').textContent='Digita el monto cobrado. Los pagos deben completar el total; revisa también el efectivo recibido.';return}$('confirmPay').disabled=true;try{const r=await api('invoices',{...payload(),request_id:saleKey,payment_method:$('method').value,payment_entry_version:2,amount_received:paymentAmounts().Efectivo?$('received').value:'0.00',payments:Object.fromEntries(Object.entries(paymentAmounts()).map(([k,v])=>[k,(v/100).toFixed(2)]))});if(auth.terminal?.remote)await api('local-pending/ack',{invoice_id:r.id});$('payment').close();await sendKitchen(r.kitchen_id,true);resetOrderFields();cart=[];discountPerson=null;$('discount').value=0;$('discountProfile').value='NONE';await renderCart();await loadBranches();$('receiptCopy').value='ORIGINAL';await receipt(r.id,true);await loadCustomers();await loadFiscal();await loadGoals(true)}catch(err){$('paymentError').textContent=err.message}finally{$('confirmPay').disabled=quote?!paymentIsValid():false}});$('closeReceipt').onclick=()=>$('receipt').close();
$('productForm').onsubmit=handle(async e=>{e.preventDefault();$('saveProduct').disabled=true;try{const data=await upload('products'+(editing?'/'+editing:''),new FormData(e.target),editing?'PATCH':'POST');applyProducts(data);editing=null;e.target.reset();clearPhotoPreview();await renderCart();toast('Producto guardado')}finally{$('saveProduct').disabled=false}});$('cancelEdit').onclick=()=>{editing=null;$('productForm').reset();clearPhotoPreview()};$('branchForm').onsubmit=handle(async e=>{e.preventDefault();await api('branches',Object.fromEntries(new FormData(e.target)));e.target.reset();auth=await api('auth/state');await loadBranches();await loadFiscal();toast('Perfil de sucursal creado. Ya puede ingresar con su nombre y contraseña.')});$('loadReports').onclick=handle(reports);$('branch').onchange=handle(async()=>{resetOrderFields();await loadGoals(true);if(cart.length){cart=[];await renderCart();toast('Pedido vaciado al cambiar de punto de venta')}await loadFiscal();if(!$('pos').hidden)$('title').textContent=branches.find(b=>b.id==$('branch').value)?.name||'Sucursal';if(!$('accounting').hidden)await loadAccounting();if(!$('cash').hidden)await loadCash();if(!$('reports').hidden)await reports();if(cart.length)await renderCart()});
$('csv').onclick=()=>{const rows=[['Número fiscal / interno','Fecha','Tipo','Cliente','RTN','Forma de pago','Estado','Terminal','Empleado','Venta productos L','Envío tercero L','Total factura L'],...report.map(r=>[r.fiscal_number||r.number,r.created_at,r.invoice_type,r.customer_name,r.customer_rtn,r.payment_method,r.status,r.terminal_name||'PC 1',r.cashier||'',((r.sales_total??r.total)/100).toFixed(2),((r.delivery_fee||0)/100).toFixed(2),(r.total/100).toFixed(2)])];const csv='\ufeff'+rows.map(r=>r.map(v=>'"'+String(v).replace(/^[=+@-]/,"'$&").replaceAll('"','""')+'"').join(',')).join('\r\n');const url=URL.createObjectURL(new Blob([csv],{type:'text/csv;charset=utf-8'})),a=document.createElement('a');a.href=url;a.download='ventas.csv';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000)};

function showView(id){if(id==='pos')requestAnimationFrame(fitSalePanels);document.body.classList.toggle('pos-screen',id==='pos');document.querySelectorAll('.view').forEach(v=>v.hidden=v.id!==id);document.querySelectorAll('nav [data-view]').forEach(b=>b.classList.toggle('active',b.dataset.view===id));$('title').textContent={pos:branches.find(b=>b.id==$('branch').value)?.name||'Sucursal',settings:'Configuración',clients:'Clientes RTN',fiscal:'Facturación y CAI',accounting:'Contabilidad',cash:'Caja y turnos',password:'Mi contraseña'}[id]||'Administración'}
let localLoginStage='BRANCH',employeePromptGeneration=0,employeePromptBranch=null;
function openLogin(role){employeePromptGeneration++;document.body.classList.remove('branch-preview');if($('employeeWelcome').open)$('employeeWelcome').close();localLoginStage='BRANCH';$('loginBranchSelect').disabled=false;$('loginBackBranch').hidden=true;loginRole=role;$('loginPassword').closest('label').firstChild.textContent=role==='local'?'Contraseña de la sucursal':'Contraseña';$('loginPassword').autocomplete=role==='local'?'off':'current-password';$('loginTitle').textContent={admin:'AJUSTES',local:'Acceso a sucursal',accountant:'CONTABILIDAD'}[role];$('emailLabel').hidden=role==='local';$('loginEmail').required=role!=='local';$('branchLoginLabel').hidden=role!=='local';$('loginBranchSelect').innerHTML=(auth?.branch_options||[]).map(b=>`<option value="${b.id}">${esc(b.name)}</option>`).join('');$('emailLabel').firstChild.textContent=role==='accountant'?'Correo de contabilidad':'Correo de ajustes';$('loginSwitch').textContent=role==='admin'?'Volver a sucursal':'⚙ AJUSTES';$('loginAccountant').textContent=role==='accountant'?'Volver a sucursal':'CONTABILIDAD';$('loginBranch').textContent=role==='accountant'?'Cuenta creada por el administrador de esta instalación.':role==='local'?(auth?.branch_options?.length?'Paso 1 de 2: selecciona tu sucursal e ingresa la contraseña del local.':'El administrador debe crear el perfil de sucursal primero.'):auth?.setup_required?'Primera vez: ingresa como administrador para configurar el sistema.':'';$('loginPassword').value='';$('loginError').textContent='';$('loginCancel').hidden=!auth?.role;if(!$('login').open)$('login').showModal();$('loginPassword').focus()}
async function loadCustomers(){customers=await api('customers');$('savedCustomer').innerHTML='<option value="">Nuevo cliente</option>'+customers.map(c=>`<option value="${esc(c.rtn)}">${esc(c.name)} · ${esc(c.rtn)}</option>`).join('');$('clientRows').innerHTML=customers.map(c=>`<tr><td>${esc(c.name)}</td><td>${esc(c.rtn)}</td></tr>`).join('')}
function fillSettings(){$('settingsForm').elements.email.value=auth.email;$('assignedBranch').value=auth.branch.id}
async function afterLogin(){document.body.classList.remove('branch-preview');paintCentral();resetOrderFields();$('cashierCurrentLabel').innerHTML='CAJERO: <span>'+esc(auth.cashier?.name||'ADMINISTRADOR')+'</span>';refreshClockStatus();document.body.classList.toggle('admin-user',auth?.role==='admin');document.body.classList.toggle('accountant-user',auth?.role==='accountant');document.body.classList.remove('locked');document.body.classList.toggle('branch-user',auth.role==='local');$('localLogout').hidden=!['admin','local'].includes(auth.role);document.querySelectorAll('[data-admin]').forEach(x=>x.hidden=auth.role!=='admin');document.querySelectorAll('[data-accounting]').forEach(x=>x.hidden=!['admin','accountant'].includes(auth.role));document.querySelectorAll('[data-accountant]').forEach(x=>x.hidden=auth.role!=='accountant');document.querySelectorAll('[data-cash]').forEach(x=>x.hidden=auth.role==='accountant');document.querySelector('[data-view="pos"]').hidden=auth.role==='accountant';cart=[];discountPerson=null;$('discount').value=0;$('discountProfile').value='NONE';
 if(auth.role==='accountant'&&auth.must_change){showView('password');$('passwordNote').textContent='Antes de consultar datos, cambia la contraseña temporal.';return}
 await loadBranches();if(auth.role==='accountant'){showView('accounting');await loadAccounting();return}await loadCustomers();if(!branches.some(b=>b.active)){showView(auth.role==='admin'?'branches':'pos');if(auth.role==='admin')toast('Crea una sucursal para comenzar.');return}await loadFiscal();await loadCommerce();await loadProducts();await loadGoals(true);await refreshBackup(true);await renderCart();showView(auth.role==='admin'&&auth.setup_required?'settings':'pos');if(auth.role==='admin'){fillSettings();await loadAccountants()}if(nativePrinter)nativePrinter.status(v=>$('printerStatus').textContent=v);if(!$('pos').hidden)await requireCash(true);if(auth.terminal?.remote)await loadPendingSale()}
$('gear').onclick=()=>{if(auth?.role==='admin'){showView('settings');fillSettings();loadCommerce();loadAccountants()}else openLogin('admin')};
$('loginAccountant').onclick=()=>openLogin(loginRole==='accountant'?'local':'accountant');
$('loginSwitch').onclick=()=>openLogin(loginRole==='admin'?'local':'admin');$('loginCancel').onclick=()=>$('login').close();$('login').addEventListener('cancel',e=>{if(!auth?.role)e.preventDefault()});
$('loginForm').onsubmit=async e=>{e.preventDefault();const submit=$('loginSubmit');if(submit.disabled)return;submit.disabled=true;try{const d=await api('auth/login',{role:loginRole,stage:loginRole==='local'?localLoginStage:undefined,email:$('loginEmail').value,branch_id:Number($('loginBranchSelect').value),password:loginRole!=='local'||localLoginStage==='BRANCH'?$('loginPassword').value:undefined,employee_code:loginRole==='local'&&localLoginStage==='EMPLOYEE'?$('loginPassword').value:undefined});$('loginPassword').value='';if(d.next_step==='EMPLOYEE'){await showEmployeeWelcome(d);return}auth=d;$('login').close();await afterLogin()}catch(err){if(err.restartBranch&&loginRole==='local')openLogin('local');$('loginPassword').value='';$('loginError').textContent=err.message;$('loginPassword').focus()}finally{submit.disabled=false}};
$('loginBackBranch').onclick=()=>openLogin('local');
$('loginBranchSelect').addEventListener('change',()=>{localLoginStage='BRANCH';$('loginPassword').value='';$('loginError').textContent=''})

const logOut=handle(async()=>{if(auth?.role==='local'){const state=await api('cash/exit-check');if(!state.can_exit){toast('Debes cuadrar la caja antes de cerrar sesión.');await openCashClose();return}}if(cart.length&&!confirm('Hay una compra sin terminar. ¿Descartarla y cerrar sesión?'))return;await api('auth/logout',{});for(const id of ['cashStartDialog','cashEndDialog'])if($(id).open)$(id).close();$('sessionMenu').hidden=true;$('terminalCreatedKey').value='';$('terminalKeyResult').hidden=true;noDiscountRows=[];$('noDiscountProducts').innerHTML='';auth=await api('auth/state');cart=[];document.body.classList.remove('branch-user','accountant-user');$('localLogout').hidden=true;document.body.classList.add('locked');showView('pos');openLogin('local')});$('logout').onclick=logOut;$('menuLogout').onclick=logOut;
$('settingsForm').onsubmit=handle(async e=>{e.preventDefault();const data=Object.fromEntries(new FormData(e.target));auth=await api('admin/config',data);e.target.reset();await afterLogin();toast('Configuración guardada. El local abrirá con la sucursal asignada.')});
$('clientForm').onsubmit=handle(async e=>{e.preventDefault();await api('customers',Object.fromEntries(new FormData(e.target)));e.target.reset();await loadCustomers();toast('RTN guardado')});
$('savedCustomer').onchange=()=>{const c=customers.find(c=>c.rtn===$('savedCustomer').value);$('customerName').value=c?.name||'';$('rtn').value=c?.rtn||''};
$('printerSetup').onclick=()=>{if(nativePrinter)nativePrinter.configure();else toast('Para configurar la impresora abre INICIAR.bat o desktop_main.py')};
if(typeof QWebChannel!=='undefined'&&typeof qt!=='undefined')new QWebChannel(qt.webChannelTransport,channel=>{nativePrinter=channel.objects.printer;nativePrinter.message.connect(toast);nativePrinter.changed.connect(v=>$('printerStatus').textContent=v)});
handle(async()=>{auth=await api('auth/state');if(auth.role)await afterLogin();else openLogin('local')})();

let photoProduct=null,previewUrl=null,priceEditor=null;
async function upload(path,data,method='POST'){const response=await fetch('/api/'+path,{method,headers:{'X-POS-Token':document.querySelector('meta[name="pos-token"]').content},body:data});const result=await response.json();if(!response.ok)throw Error(result.error||'No se pudo guardar la foto');return result}
function clearPhotoPreview(){if(previewUrl)URL.revokeObjectURL(previewUrl);previewUrl=null;$('photoPreview').hidden=true;$('photoPreview').removeAttribute('src');$('productPhoto').value=''}
$('productPhoto').onchange=()=>{if(previewUrl)URL.revokeObjectURL(previewUrl);const file=$('productPhoto').files[0];if(file&&file.size>8*1024*1024){clearPhotoPreview();toast('La foto no puede superar 8 MB');return}previewUrl=file?URL.createObjectURL(file):null;$('photoPreview').hidden=!file;if(file)$('photoPreview').src=previewUrl};
$('rowPhoto').onchange=handle(async()=>{const file=$('rowPhoto').files[0];if(!file)return;if(file.size>8*1024*1024)throw Error('La foto no puede superar 8 MB');const id=photoProduct;const data=new FormData();data.append('photo',file);applyProducts(await upload('products/'+id+'/photo',data));toast('Foto guardada')});
async function editPrice(button,id){
 if(auth?.role!=='admin')throw Error('Solo el administrador puede cambiar precios');
 if(priceEditor&&!(await priceEditor.commit()))return;
 const product=products.find(p=>p.id===id);const cell=document.querySelector(`[data-price="${id}"]`)?.closest('td');if(!cell)return;
 const input=document.createElement('input');input.type='number';input.min='0';input.max='100000000';input.step='0.01';input.value=(product.price/100).toFixed(2);input.className='inline-price';input.setAttribute('aria-label','Precio de '+product.name);cell.replaceChildren(input);input.focus();input.select();
 let canceled=false,pending=null,saving=false;
 const editor={commit(){if(canceled)return Promise.resolve(true);if(saving)return pending||Promise.resolve(false);
 if(!input.value.trim()||!input.checkValidity()){toast('Introduce un precio válido con hasta 2 decimales');input.focus();return Promise.resolve(false)}
 if(Number(input.value)===product.price/100){canceled=true;priceEditor=null;renderProducts();return Promise.resolve(true)}
 saving=true;input.disabled=true;pending=(async()=>{try{const data=await api('products/'+id,{price:input.value},'PATCH');canceled=true;priceEditor=null;applyProducts(data);await renderCart();toast('Precio guardado');return true}catch(e){input.disabled=false;pending=null;saving=false;toast(e.message);input.focus();return false}})();return pending;
 }};priceEditor=editor;
 input.onblur=()=>{if(!canceled)editor.commit()};input.onkeydown=e=>{if(e.key==='Enter'){e.preventDefault();editor.commit()}if(e.key==='Escape'&&!pending){e.preventDefault();canceled=true;priceEditor=null;renderProducts()}};
}


async function loadFiscal(){const result=await api('fiscal/state?branch_id='+$('branch').value);fiscalConfig=result.config;const f=$('fiscalForm');for(const [key,value] of Object.entries(fiscalConfig)){if(f.elements[key]){if(key==='enabled')f.elements[key].checked=value;else f.elements[key].value=value}}const mode=fiscalConfig.price_mode==='INCLUSIVE'?'Precios con ISV incluido':'Precios antes de ISV';$('fiscalNotice').textContent=result.warning||result.notice||(fiscalConfig.enabled?'FACTURACIÓN CON CAI CONFIGURADO · '+mode:'MODO MUESTRA · Sin autorización CAI configurada · '+mode);$('fiscalStatus').textContent=result.warning||(fiscalConfig.enabled?'Siguiente factura: '+fiscalConfig.establishment+'-'+fiscalConfig.point+'-01-'+String(fiscalConfig.next_number).padStart(8,'0'):'Las muestras no consumen un correlativo fiscal.');}
$('fiscalForm').onsubmit=handle(async e=>{e.preventDefault();const d=Object.fromEntries(new FormData(e.target));d.enabled=e.target.elements.enabled.checked;d.branch_id=Number($('branch').value);await api('admin/fiscal',d);await loadFiscal();await renderCart();toast('Datos de facturación guardados')});
$('receiptCopy').onchange=handle(async()=>{if(lastReceiptId)await receipt(lastReceiptId)});
$('fiscalPreview').onclick=handle(async()=>{if(lastReceiptId){await receipt(lastReceiptId);return}const rows=await api('reports?branch_id='+$('branch').value);if(!rows.length)throw Error('Aún no hay ventas. Guarda una venta en modo muestra para revisar el formato.');await receipt(rows.at(-1).id)});

let accountingData=null;
function accParams(){return new URLSearchParams({branch_id:$('accBranch').value||'all',start:$('accStart').value,end:$('accEnd').value,scope:$('accScope').value,status:$('accStatus').value,type:$('accType').value,payment:$('accPayment').value})}
async function loadAccounting(){if(auth.role==='admin'){await loadAccessStatus();await loadSpecial();}await loadSar();accountingData=await api('accounting?'+accParams());const d=accountingData;$('accWarning').textContent=d.incomplete?d.incomplete+' documentos históricos sin desglose completo; los campos desconocidos se dejan vacíos.':'';$('accStats').innerHTML=[['Emitidas',d.issued],['Anuladas',d.voided],['Ventas de productos',fmt(d.totals.total)],['Envíos por cuenta de tercero',fmt(d.totals.delivery_fee||0)],['Total cobrado con envío',fmt(d.totals.collected_total??d.totals.total)],['ISV 15%',fmt(d.totals.tax_15)],['ISV 18%',fmt(d.totals.tax_18)],['Efectivo cobrado',fmt(d.totals.Efectivo)],['Transferencia',fmt(d.totals.Transferencia)],['Tarjeta',fmt(d.totals.Tarjeta)]].map(([k,v])=>`<div>${k}<strong>${v}</strong></div>`).join('');$('accRows').innerHTML=d.invoices.map(r=>`<tr><td>${esc(r.fiscal_number||'INTERNO-'+r.number)}<br>${esc(r.branch_name)}<br>${esc(r.created_at)}</td><td>${esc(r.customer_name)}<br>${esc(r.customer_rtn)}</td><td>${r.status}</td>${['exempt','exempted','taxable_15','taxable_18','tax_15','tax_18','discount','total'].map(k=>`<td>${r[k]===null?'—':fmt(r[k])}</td>`).join('')}<td><button data-receipt="${r.id}">Ver factura</button></td></tr>`).join('')||'<tr><td colspan="12">No hay documentos para estos filtros.</td></tr>';$('accShifts').innerHTML=d.shifts.map(r=>`<div class="panel"><b>Turno #${r.id} · ${r.status}</b><p>${esc(r.opened_by)} · ${esc(r.opened_at)}</p><p>Inicial ${fmt(r.opening)} · Efectivo cobrado ${fmt(r.payments.Efectivo)} · Entradas ${fmt(r.inputs)} · Salidas ${fmt(r.outputs)} · Esperado ${fmt(r.status==='CERRADA'?r.expected:r.live_expected)} · Contado ${r.counted===null?'—':fmt(r.counted)} · Diferencia ${r.difference===null?'—':fmt(r.difference)}</p>${r.movements.map(m=>`<p>${m.kind} · ${esc(m.concept)} · ${fmt(m.amount)} · ${esc(m.reference)}</p>`).join('')}</div>`).join('')||'<p>No hay turnos en este período.</p>';$('accAudit').textContent=d.audit.map(r=>r.created_at+' · '+r.actor+' · '+r.event+' · '+r.detail).join('\n');$('accClients').textContent=d.customers.map(c=>c.name+' · '+c.rtn).join('\n');$('accFiscal').textContent=d.authorizations.map(a=>a.branch_name+' · '+(a.enabled?'CAI '+a.cai+' · Rango '+a.range_start+' a '+a.range_end+' · Siguiente '+a.next_number+' · Vence '+a.deadline:'Sin autorización activa')).join(' | ');}
$('accLoad').onclick=handle(loadAccounting);$('accBranch').onchange=handle(loadAccounting);
function exportAccounting(kind){const url='/api/accounting/export/'+kind+'?'+accParams();if(kind==='print'){if(nativePrinter)nativePrinter.openReport(location.origin+url);else window.open(url,'_blank');return}const a=document.createElement('a');a.href=url;a.download='';a.click()}
$('accPdf').onclick=()=>exportAccounting('pdf');$('accExcel').onclick=()=>exportAccounting('xlsx');$('accPrint').onclick=()=>exportAccounting('print');
async function loadAccountants(){if(auth?.role!=='admin')return;const rows=await api('admin/accountants');$('accountantsList').innerHTML=rows.map(r=>`<p>${esc(r.email)} · ${r.active?'Activa':'Desactivada'} <button data-account-toggle="${r.id}" data-email="${esc(r.email)}" data-active="${r.active}">${r.active?'Desactivar':'Activar'}</button> <button data-account-reset="${r.id}" data-email="${esc(r.email)}">Restablecer contraseña</button></p>`).join('')||'<p>No hay cuentas de contador creadas.</p>'}
$('accountantForm').onsubmit=handle(async e=>{e.preventDefault();await api('admin/accountants',Object.fromEntries(new FormData(e.target)));e.target.reset();await loadAccountants();toast('Cuenta creada. Entrega la contraseña temporal al contador.')});
document.addEventListener('click',handle(async e=>{const b=e.target.closest('button');if(!b)return;if(b.dataset.accountToggle){await api('admin/accountants/'+b.dataset.accountToggle,{email:b.dataset.email,active:b.dataset.active!=='1'},'PATCH');await loadAccountants()}if(b.dataset.accountReset){const password=prompt('Nueva contraseña temporal (mínimo 8 caracteres):');if(!password)return;await api('admin/accountants/'+b.dataset.accountReset,{email:b.dataset.email,password,active:true},'PATCH');await loadAccountants();toast('Contraseña temporal restablecida')}if(b.dataset.branchReset){const password=prompt('Nueva contraseña para '+b.dataset.branchName+' (mínimo 4 caracteres):');if(!password)return;await api('branches/'+b.dataset.branchReset,{password},'PATCH');await loadBranches();toast('Contraseña de sucursal actualizada')}if(b.dataset.branchRemove&&confirm('¿Retirar '+b.dataset.branchName+'? Solo se permite si no tiene ventas, turnos ni un CAI activo. Los datos de configuración se conservan.')){await api('branches/'+b.dataset.branchRemove,{},'DELETE');auth=await api('auth/state');await loadBranches();toast('Sucursal retirada; ya puedes crear la nueva.')}if(b.dataset.branchRestore){await api('branches/'+b.dataset.branchRestore,{active:true},'PATCH');await loadBranches();toast('Sucursal restaurada')}}));
$('ownPassword').onsubmit=handle(async e=>{e.preventDefault();const d=Object.fromEntries(new FormData(e.target));if(d.password!==d.confirm)throw Error('Las contraseñas no coinciden');await api('auth/password',d);e.target.reset();auth=await api('auth/state');await afterLogin();toast('Contraseña actualizada')});
async function loadCash(){const d=await api('cash?branch_id='+$('branch').value);const r=d.shift;cashPanelShiftId=r?.id||null;$('cashOpen').hidden=!!r;$('cashMove').hidden=!r;$('cashClose').hidden=!r;$('cashStatus').innerHTML=r?cashSummary(r):'<p>No hay turno abierto.</p>'+(d.last_closed?'<h3>Último cierre</h3>'+cashSummary(d.last_closed):'');}
for(const [id,action]of [['cashOpen','open'],['cashMove','movement'],['cashClose','close']])$(id).onsubmit=handle(async e=>{e.preventDefault();if(action==='close'&&!confirm('¿Cerrar el turno con el efectivo contado indicado?'))return;await api('cash',{...Object.fromEntries(new FormData(e.target)),action,shift_id:cashPanelShiftId,branch_id:Number($('branch').value)});e.target.reset();await loadCash();toast('Caja actualizada')});

async function loadCommerce(){await loadCategoryOrder();commerceConfig=await api('commerce');$('specialBox').hidden=!commerceConfig.owner_enabled;if(!commerceConfig.owner_enabled)$('specialOrder').checked=false;for(const [k,v] of Object.entries(commerceConfig)){const el=$('commerceForm').elements[k];if(el){if(el.type==='checkbox')el.checked=!!v;else el.value=v}}$('discount').value=$('discountProfile').value==='NONE'?0:commerceConfig[$('discountProfile').value==='EMPLOYEE'?'employee':'senior'];}
$('commerceForm').onsubmit=handle(async e=>{e.preventDefault();const d=Object.fromEntries(new FormData(e.target));d.owner_enabled=e.target.elements.owner_enabled.checked;await api('commerce',d);e.target.elements.smtp_password.value='';await loadCommerce();toast('Descuentos y correo guardados')});
async function saveSpecial(){const recipient=$('specialRecipient').value.trim();if(!recipient)throw Error('Escribe el nombre del dueño o ejecutivo');if(!confirm('¿Registrar este consumo sin cobro?'))return;$('pay').disabled=true;try{saleKey=saleKey||crypto.randomUUID();const r=await api('special-orders',{...payload(),recipient,request_id:saleKey});await sendKitchen(r.kitchen_id,true);resetOrderFields();$('receiptCopy').disabled=true;lastReceiptId=null;$('receiptBody').innerHTML='<h2>Registro especial #'+r.id+'</h2><p>Sin cobro · '+esc(recipient)+'</p>'+cart.map(it=>'<p>'+it.quantity+' × '+esc(it.name)+'</p>').join('')+'<p>Valor de referencia: '+fmt(quote.total)+'</p><b>Cobrado: L 0.00</b><p>Comprobante interno de consumo</p>';if(!$('receipt').open)$('receipt').showModal();cart=[];$('specialOrder').checked=false;$('specialRecipient').value='';await renderCart();toast(r.email_status==='ENVIADO'?'Registro guardado y correo enviado':'Registro guardado. Correo pendiente; el administrador puede reenviarlo.')}finally{$('pay').disabled=!cart.length}}
async function loadSpecial(){const rows=await api('special-orders');$('specialRows').innerHTML='<p>Total consumos: '+rows.length+' · Valor de referencia: '+fmt(rows.reduce((a,r)=>a+r.snapshot.total,0))+' · Cobrado: L 0.00</p>'+rows.map(r=>'<p>#'+r.id+' · '+esc(r.created_at)+' · '+esc(r.snapshot.branch_name)+' · '+esc(r.recipient)+' · '+fmt(r.snapshot.total)+' · Correo '+esc(r.email_status)+(auth.role==='admin'&&r.email_status!=='ENVIADO'?' <button data-retry-special="'+r.id+'">Reenviar correo</button>':'')+'</p>').join('')}
$('specialLoad').onclick=handle(loadSpecial);$('specialPdf').onclick=()=>{location.href='/api/special-orders/export/pdf'};$('specialExcel').onclick=()=>{location.href='/api/special-orders/export/xlsx'};document.addEventListener('click',handle(async e=>{const b=e.target.closest('[data-retry-special]');if(b){await api('admin/special-orders/'+b.dataset.retrySpecial+'/retry',{});await loadSpecial()}}));

function renderCategoryOrder(){$('categoryOrderList').innerHTML=categoryOrder.map((name,i)=>`<div class="category-sort-row"><span>${i+1}. ${esc(name)}</span><button type="button" data-order-up="${i}" ${i===0?'disabled':''} aria-label="Subir ${esc(name)}">↑ Subir</button><button type="button" data-order-down="${i}" ${i===categoryOrder.length-1?'disabled':''} aria-label="Bajar ${esc(name)}">↓ Bajar</button></div>`).join('')}
async function loadCategoryOrder(){const d=await api('category-order');categoryOrder=d.order;renderCategoryOrder()}
document.addEventListener('click',e=>{const b=e.target.closest('[data-order-up],[data-order-down]');if(!b||auth?.role!=='admin')return;const up=b.dataset.orderUp!==undefined;const i=Number(up?b.dataset.orderUp:b.dataset.orderDown),j=i+(up?-1:1);if(j<0||j>=categoryOrder.length)return;[categoryOrder[i],categoryOrder[j]]=[categoryOrder[j],categoryOrder[i]];renderCategoryOrder()});
$('saveCategoryOrder').onclick=handle(async()=>{const d=await api('category-order',{order:categoryOrder});categoryOrder=d.order;renderCategoryOrder();renderProducts();toast('Orden de categorías guardado')});$('reloadCategoryOrder').onclick=handle(async()=>{await loadCategoryOrder();renderProducts()});
const salesHeader=document.querySelector('main>header');salesHeader.insertBefore($('categories'),salesHeader.children[1]);const headerLogo=salesHeader.querySelector('.header-mark');salesHeader.querySelector('.row').prepend(headerLogo);

const branchDisplay=document.createElement('span');branchDisplay.id='headerBranchName';headerLogo.append(branchDisplay);
function syncHeaderBranch(){branchDisplay.textContent=branches.find(b=>b.id==$('branch').value)?.name||auth?.branch?.name||''}
$('branch').addEventListener('change',syncHeaderBranch);

let cashCurrent=null,cashClosed=null;
function cashSummary(r){const closed=r.status==='CERRADA',row=(label,value)=>`<div class="sum"><span>${label}</span><strong>${fmt(value)}</strong></div>`;return `<p><b>RESPONSABLE ACTUAL: ${esc(auth.cashier?.full_name||'ADMINISTRADOR')}</b><br>Apertura: ${esc(r.opened_by||'Sin identificación histórica')} · ${esc(r.terminal_name||'PC 1')}<br>Cierre: ${esc(r.closed_by||'Pendiente')}</p><p><b>${esc(cashLabel(r))}</b> · ${esc(formatCashDate(r.opened_at))}</p><section class="cash-reconciliation"><h3>Cuadre del efectivo físico</h3>${row('Fondo inicial',r.opening)}${row('Efectivo cobrado (+)',r.payments.Efectivo||0)}${row('Otras entradas de efectivo (+)',r.inputs)}${row('Salidas de efectivo (−)',r.outputs)}${row('Efectivo que debe haber en caja',closed?r.expected:r.live_expected)}${closed?row('Efectivo físico contado',r.counted)+row(r.difference>0?'Sobrante':r.difference<0?'Faltante':'Diferencia · caja cuadrada',Math.abs(r.difference)):''}<small>Tarjetas y transferencias se muestran en sus propios totales. No forman parte del efectivo físico.</small></section><p>Consumos sin cobro: ${r.special_count||0} · Valor de referencia: ${fmt(r.special_value||0)}</p>`}

async function requireCash(always){const d=await api('cash?branch_id='+$('branch').value);cashCurrent=d.shift;if(cashCurrent?.must_close){if($('cashStartDialog').open)$('cashStartDialog').close();showCashClose(cashCurrent);toast('Debes cuadrar la caja anterior antes de vender hoy.');return false}if(cashCurrent&&!always)return true;$('cashStartClerk').textContent='EMPLEADO EN CAJA: '+(auth.cashier?.full_name||'ADMINISTRADOR');$('cashStartTitle').textContent=cashCurrent?'Continuar caja abierta':'Iniciar caja';$('cashStartBranch').textContent='SUCURSAL: '+(branches.find(b=>b.id==$('branch').value)?.name||'').toLocaleUpperCase('es');$('cashOpeningLabel').hidden=!!cashCurrent;$('cashStartForm').elements.opening.required=!cashCurrent;$('cashResumeText').hidden=!cashCurrent;$('cashStartDialog').classList.toggle('cash-resume',!!cashCurrent);$('cashResumeText').innerHTML=cashCurrent?'<div><span>CAJA ABIERTA</span><b>'+esc(cashLabel(cashCurrent))+'</b></div><div><span>APERTURA</span><b>'+esc(formatCashDate(cashCurrent.opened_at))+'</b></div><div><span>FONDO INICIAL</span><b>'+fmt(cashCurrent.opening)+'</b></div><p>CONTINÚA CON ESTA CAJA PARA VENDER.</p>':'';$('cashStartSubmit').textContent=cashCurrent?'Continuar caja':'Iniciar caja';$('cashStartError').textContent='';$('cashStartForm').elements.opening.value='';if(!$('cashStartDialog').open)$('cashStartDialog').showModal();return false}
$('cashStartDialog').addEventListener('cancel',e=>e.preventDefault());$('cashStartLogout').onclick=logOut;$('cashClosedLogout').onclick=logOut;
$('cashStartForm').onsubmit=async e=>{e.preventDefault();$('cashStartSubmit').disabled=true;try{if(!cashCurrent){const d=await api('cash',{action:'open',branch_id:Number($('branch').value),opening:e.target.elements.opening.value});cashCurrent=d.shift}if($('cashStartDialog').open)$('cashStartDialog').close();showView('pos');toast(cashLabel(cashCurrent)+' LISTA PARA VENDER')}catch(err){$('cashStartError').textContent=err.message}finally{$('cashStartSubmit').disabled=false}};
$('localLogout').onclick=()=>{const hidden=!$('sessionMenu').hidden;$('sessionMenu').hidden=hidden;$('localLogout').setAttribute('aria-expanded',String(!hidden))};document.addEventListener('click',e=>{if(!e.target.closest('#sessionMenu,#localLogout')){$('sessionMenu').hidden=true;$('localLogout').setAttribute('aria-expanded','false')}});
function showCashClose(shift){cashCurrent=shift;cashClosed=null;$('cashEndSummary').innerHTML=(shift.must_close?'<p class="cash-day-warning"><b>CAJA DEL '+esc(shift.business_date)+' PENDIENTE DE CUADRE.</b><br>Cuadra esta caja antes de vender en el nuevo día.</p>':'')+cashSummary(shift);$('cashEndForm').hidden=false;$('cashClosedActions').hidden=true;$('cashCounted').value='';$('cashDifference').textContent='';$('cashEndError').textContent='';$('cashEndSubmit').disabled=false;$('cashEndCancel').disabled=!!shift.must_close;if(!$('cashEndDialog').open)$('cashEndDialog').showModal()}
async function openCashClose(){const d=await api('cash?branch_id='+$('branch').value);if(!d.shift){await requireCash(false);return}if(cart.length&&!d.shift.must_close)throw Error('Finaliza o quita los productos de la compra actual antes de cerrar caja');$('sessionMenu').hidden=true;if($('cashStartDialog').open)$('cashStartDialog').close();showCashClose(d.shift)}
$('menuCashClose').onclick=handle(openCashClose);
$('cashEndDialog').addEventListener('cancel',e=>{if(cashCurrent?.must_close)e.preventDefault()});
window.cashExitRequested=handle(async()=>{if(['admin','local'].includes(auth?.role))await openCashClose()});
let checkingShiftDay=false;
async function checkShiftDay(){if(checkingShiftDay||!['admin','local'].includes(auth?.role)||!$('branch').value||document.querySelector('dialog[open]'))return;checkingShiftDay=true;try{const d=await api('cash?branch_id='+$('branch').value);if(d.shift?.must_close)showCashClose(d.shift)}finally{checkingShiftDay=false}}
setInterval(()=>checkShiftDay().catch(()=>{}),15000);

$('cashCounted').oninput=()=>{const value=Number($('cashCounted').value);$('cashDifference').textContent=$('cashCounted').value===''?'':'Diferencia (positivo = sobrante, negativo = faltante): '+fmt(Math.round(value*100)-cashCurrent.live_expected)};
$('cashEndCancel').onclick=()=>$('cashEndDialog').close();$('cashEndForm').onsubmit=async e=>{e.preventDefault();if(!confirmCashCount($('cashCounted').value,cashCurrent.live_expected))return;$('cashEndSubmit').disabled=true;try{const d=await api('cash',{action:'close',branch_id:Number($('branch').value),shift_id:cashCurrent.id,counted:$('cashCounted').value});cashClosed=d.last_closed;cashCurrent=null;$('cashEndSummary').innerHTML=cashSummary(cashClosed)+'<p>Cierre guardado.</p>';$('cashEndForm').hidden=true;$('cashClosedActions').hidden=false}catch(err){$('cashEndError').textContent=err.message}finally{$('cashEndSubmit').disabled=false}};
const cashClosePrintKeys={};
async function printCashClosure(id,explicitCopy=false){const key=cashClosePrintKeys[id]||(cashClosePrintKeys[id]=crypto.randomUUID());let copy=explicitCopy;if(copy&&!confirm('Revisa el papel. ¿Imprimir una COPIA del cierre?'))return;let result=await api('cash/'+id+'/print',{request_id:key,copy});if(result.needs_copy){if(!confirm(result.message)){delete cashClosePrintKeys[id];return}result=await api('cash/'+id+'/print',{request_id:key,copy:true})}delete cashClosePrintKeys[id];toast(result.state==='UNCERTAIN'?'Envío dudoso. Revisa el papel antes de pedir una copia.':result.state==='SPOOLED'?'Este cierre ya se envió. Comprueba el papel de la impresora de caja.':'Cierre enviado a la cola de la impresora de caja. Espera el papel para tomar la foto.');return result}
$('cashDownload').onclick=handle(async()=>{if(!cashClosed)return;$('cashDownload').disabled=true;try{await printCashClosure(cashClosed.id)}finally{$('cashDownload').disabled=false}});$('cashNew').onclick=handle(async()=>{$('cashEndDialog').close();await requireCash(true)});

const clockBox=document.createElement('span');clockBox.id='hondurasClock';clockBox.innerHTML='<span id="hondurasDate"></span><span id="hondurasTime"></span><span id="hondurasValidation">HORA DE LA PC · SIN VALIDAR</span>';headerLogo.prepend(clockBox);
const hnDate=new Intl.DateTimeFormat('es-HN',{timeZone:'America/Tegucigalpa',day:'2-digit',month:'long',year:'numeric'}),hnTime=new Intl.DateTimeFormat('es-HN',{timeZone:'America/Tegucigalpa',hour:'2-digit',minute:'2-digit',second:'2-digit',hour12:true});
function tickClock(){const now=new Date();$('hondurasDate').textContent=hnDate.format(now).replace(/ de /g,' ').toLocaleUpperCase('es');$('hondurasTime').textContent=hnTime.format(now)}
async function refreshClockStatus(){try{const s=await api('clock');const el=$('hondurasValidation');el.className=s.status==='VALIDADA'?'clock-ok':s.status==='DESAJUSTADA'?'clock-warn':'';el.textContent=s.status==='VALIDADA'?'HORA VALIDADA CON GOOGLE':s.status==='DESAJUSTADA'?'REVISAR RELOJ DE LA PC':'HORA DE LA PC · SIN VALIDAR';el.title=s.status==='DESAJUSTADA'?'Diferencia respecto a Google: '+s.offset_seconds+' segundos. Ajusta la fecha y hora en Windows.':s.checked_at?'Última comprobación: '+hnDate.format(new Date(s.checked_at*1000))+' '+hnTime.format(new Date(s.checked_at*1000)):'Pendiente de conexión con time.google.com'}catch{const el=$('hondurasValidation');if(el){el.className='';el.textContent='HORA DE LA PC · SIN VALIDAR'}}}
tickClock();setInterval(tickClock,1000);setInterval(refreshClockStatus,30000);

const catalogArea=document.querySelector('#pos>.catalog'),saleToolbar=document.createElement('div');saleToolbar.className='sale-toolbar';catalogArea.prepend(saleToolbar);
const discountChoice=$('discountProfile').closest('label'),discountAmount=$('discount').closest('label');discountChoice.classList.add('toolbar-discount');discountAmount.classList.add('toolbar-percent');saleToolbar.append(discountChoice,discountAmount);
const buyerLabel=document.createElement('label');buyerLabel.className='toolbar-buyer';buyerLabel.append(document.createTextNode('CLIENTE'));buyerLabel.append($('type'));saleToolbar.append(buyerLabel);$('type').options[0].textContent='CONSUMIDOR FINAL';$('type').options[1].textContent='CLIENTE CON RTN';
const searchLabel=document.createElement('label');searchLabel.className='toolbar-search';searchLabel.append(document.createTextNode('BUSCAR'));searchLabel.append($('search'));saleToolbar.append(searchLabel);$('search').placeholder='Buscar producto…';saleToolbar.after($('customer'));$('customer').classList.add('customer-toolbar');
function fitSalePanels(){if($('pos').hidden)return;const top=$('pos').getBoundingClientRect().top;const height=Math.max(310,window.innerHeight-Math.max(0,top)-32);$('pos').style.setProperty('--sale-height',height+'px')}
window.addEventListener('resize',fitSalePanels);new ResizeObserver(()=>requestAnimationFrame(fitSalePanels)).observe(salesHeader);requestAnimationFrame(fitSalePanels);

async function loadSar(){const d=await api('accounting/sar?'+accParams());$('sarStats').innerHTML=[['VENTA GRAVADA 15 % SIN ISV',d.gravado_15],['VENTA GRAVADA 18 % SIN ISV',d.gravado_18],['TOTAL VENTA GRAVADA SIN IMPUESTO',d.total_gravado_sin_impuesto]].map(([label,value])=>'<div>'+label+'<strong>'+fmt(value)+'</strong></div>').join('');$('sarWarning').textContent=d.rows.length+' facturas emitidas · '+d.anuladas_excluidas+' anuladas excluidas.'+(d.incompletos?' '+d.incompletos+' documentos sin desglose: no se suman; consulta su respaldo.':'')+(d.rows.some(r=>!r.documento_fiscal)?'':'')+'';$('sarRows').innerHTML=d.rows.map(r=>'<tr><td>'+esc(r.fecha)+'</td><td>'+esc(r.sucursal)+'</td><td>'+esc(r.factura)+'</td><td>'+esc(r.cliente)+'<br>'+esc(r.rtn)+'<br>'+esc(r.pago)+'</td>'+['gravado_15','gravado_18','total_gravado_sin_impuesto'].map(k=>'<td>'+(r[k]===null?'NO DISPONIBLE':fmt(r[k]))+'</td>').join('')+'</tr>').join('')||'<tr><td colspan="7">No hay facturas emitidas para los filtros seleccionados.</td></tr>'}
$('sarLoad').onclick=handle(loadSar);function exportSar(kind){const a=document.createElement('a');a.href='/api/accounting/sar/export/'+kind+'?'+accParams();a.download='';a.click()}$('sarPdf').onclick=()=>exportSar('pdf');$('sarExcel').onclick=()=>exportSar('xlsx');
let cancellationInvoice=null,cancellationExpires=0,cancellationRefresh=false;
$('menuCancelInvoice').onclick=()=>{$('sessionMenu').hidden=true;cancellationInvoice=null;$('cancelOrderNumber').value='';$('cancelInvoiceReason').value='';$('cancelInvoiceCode').value='';$('cancelInvoiceDetail').textContent='';$('cancelInvoiceError').textContent='';$('confirmCancelInvoice').disabled=true;$('cancelInvoiceDialog').showModal()};
$('closeCancelInvoice').onclick=()=>$('cancelInvoiceDialog').close();
$('cancelOrderNumber').oninput=()=>{cancellationInvoice=null;$('confirmCancelInvoice').disabled=true;$('cancelInvoiceDetail').textContent=''};
$('findCancelInvoice').onclick=async()=>{try{cancellationInvoice=null;$('confirmCancelInvoice').disabled=true;$('cancelInvoiceError').textContent='';const r=await api('cancellation/find',{branch_id:Number($('branch').value),number:Number($('cancelOrderNumber').value)});cancellationInvoice=r;$('cancelInvoiceDetail').textContent='ORDEN #'+r.number+' · '+r.customer_name+' · '+fmt(r.total)+' · '+r.created_at+' · '+r.status;$('confirmCancelInvoice').disabled=r.status!=='EMITIDA'}catch(e){$('cancelInvoiceError').textContent=e.message}};
$('confirmCancelInvoice').onclick=async()=>{if(!cancellationInvoice)return;const b=$('confirmCancelInvoice');b.disabled=true;try{await api('cancellation/confirm',{branch_id:Number($('branch').value),number:cancellationInvoice.number,invoice_id:cancellationInvoice.id,reason:$('cancelInvoiceReason').value,code:$('cancelInvoiceCode').value.trim()});$('cancelInvoiceDialog').close();toast('Factura anulada. Se conserva en el historial y se excluye de las ventas vigentes.');cancellationInvoice=null}catch(e){$('cancelInvoiceError').textContent=e.message;b.disabled=false}};
async function refreshCancellationCode(){if(cancellationRefresh)return;cancellationRefresh=true;try{const r=await api('admin/cancellation-code');if(auth?.role!=='admin')return;$('cancellationCode').textContent=r.used?'UTILIZADO':r.code;cancellationExpires=performance.now()+r.remaining*1000;$('cancellationCodeBox').hidden=false}catch(e){$('cancellationCodeBox').hidden=true;cancellationExpires=0;toast(e.message)}finally{cancellationRefresh=false}}
$('showCancellationCode').onclick=refreshCancellationCode;
setInterval(()=>{if(auth?.role!=='admin'){$('totpEnrollment').hidden=true;$('totpQr').removeAttribute('src');for(const id of ['totpSecret','totpUri','totpVerify','totpAdminPassword'])$(id).value='';$('cancellationCodeBox').hidden=true;$('cancellationCode').textContent='';cancellationExpires=0;return}if(!cancellationExpires)return;const remaining=Math.max(0,Math.ceil((cancellationExpires-performance.now())/1000));$('cancellationProgress').value=remaining;$('cancellationTime').textContent='TIEMPO RESTANTE: '+Math.floor(remaining/60)+':'+String(remaining%60).padStart(2,'0');if(!remaining)refreshCancellationCode()},250);

$('totpSetup').onclick=async()=>{try{const r=await api('admin/cancellation-totp/setup',{current_password:$('totpAdminPassword').value});$('totpQr').src=r.qr;$('totpSecret').value=r.secret;$('totpUri').value=r.uri;$('totpVerify').value='';$('totpEnrollment').hidden=false;$('totpEnrollment').scrollIntoView({block:'start',behavior:'smooth'});$('totpMessage').textContent='Clave preparada. Confirma un código antes de activar.'}catch(e){$('totpMessage').textContent=e.message}};
$('totpActivate').onclick=async()=>{try{await api('admin/cancellation-totp/activate',{current_password:$('totpAdminPassword').value,code:$('totpVerify').value.trim()});$('totpEnrollment').hidden=true;$('totpQr').removeAttribute('src');for(const id of ['totpSecret','totpUri','totpVerify','totpAdminPassword'])$(id).value='';$('totpMessage').textContent='TOTP ACTIVADO. Cada código autoriza una anulación; luego debes esperar el siguiente intervalo.';await refreshCancellationCode()}catch(e){$('totpMessage').textContent=e.message}};
let discountPerson=null,employeeAdminRows=[];
function resetDiscountPerson(){discountPerson=null;$('discountProfile').value='NONE';$('discount').value=0;$('discountPersonName').value='';$('discountPersonIdentity').value='';$('discountEmployee').innerHTML=''}
async function openDiscountPerson(){discountPerson=null;const kind=$('discountProfile').value;if(kind==='NONE'){resetDiscountPerson();await renderCart();return}$('discount').value=0;$('pay').disabled=true;$('employeeDiscountFields').hidden=kind!=='EMPLOYEE';$('otherDiscountFields').hidden=kind==='EMPLOYEE';$('discountPersonName').value='';$('discountPersonIdentity').value='';$('discountPersonError').textContent='';try{if(kind==='EMPLOYEE'){const rows=await api('employees');$('discountEmployee').innerHTML='<option value="">Selecciona un empleado</option>'+rows.map(r=>'<option value="'+r.id+'">'+esc(r.name)+'</option>').join('')}if(!$('discountPersonDialog').open)$('discountPersonDialog').showModal()}catch(e){resetDiscountPerson();await renderCart();throw e}}
$('discountPersonApply').onclick=async()=>{try{const kind=$('discountProfile').value;if(kind==='EMPLOYEE'){if(!$('discountEmployee').value)throw Error('Selecciona un empleado registrado');discountPerson={employee_id:Number($('discountEmployee').value)}}else{const name=$('discountPersonName').value.trim(),identity=$('discountPersonIdentity').value.replace(/[\s-]/g,'');if(name.length<3||!/^\d{13}$/.test(identity))throw Error('Ingresa nombre completo e identidad de 13 dígitos');discountPerson={name,identity}}if(cart.length)await api('quote',payload());$('discount').value=commerceConfig[kind==='EMPLOYEE'?'employee':'senior'];$('discountPersonDialog').close();$('discountPersonName').value='';$('discountPersonIdentity').value='';await renderCart()}catch(e){discountPerson=null;$('discountPersonError').textContent=e.message}};
$('discountPersonCancel').onclick=()=>{resetDiscountPerson();$('discountPersonDialog').close();renderCart()};$('discountPersonDialog').addEventListener('cancel',()=>{resetDiscountPerson();renderCart()});
async function loadEmployees(){if(auth?.role!=='admin')return;employeeAdminRows=await api('admin/employees');$('employeeRows').innerHTML=employeeAdminRows.map(r=>'<tr><td>'+esc(r.name)+'</td><td>'+esc(r.identity)+'</td><td>'+esc(r.has_code?(r.first_name+' '+r.first_surname+' · Código asignado'):'Sin código de acceso')+'</td><td>'+(r.active?'Activo':'Inactivo')+(r.active_session?'<br>En uso: '+esc(r.active_session.pc)+(r.active_session.open_cash?' · Caja abierta':''):'')+'</td><td>'+(r.active_session?'<button data-release-employee-session="'+r.id+'" '+(r.active_session.open_cash?'disabled':'')+'>Liberar sesión</button> ':'')+'<button data-edit-employee="'+r.id+'">Editar</button></td></tr>').join('')||'<tr><td colspan="4">No hay empleados registrados.</td></tr>'}
$('employeeReload').onclick=handle(loadEmployees);$('employeeNew').onclick=()=>{$('employeeForm').reset();$('employeeForm').elements.id.value=''};
$('employeeForm').onsubmit=handle(async e=>{e.preventDefault();const f=$('employeeForm');await api('admin/employees',{id:f.elements.id.value?Number(f.elements.id.value):null,name:f.elements.name.value,identity:f.elements.identity.value,first_name:f.elements.first_name.value,first_surname:f.elements.first_surname.value,access_code:f.elements.access_code.value,active:f.elements.active.checked});f.reset();f.elements.id.value='';await loadEmployees();toast('Empleado guardado')});
document.addEventListener('click',e=>{const b=e.target.closest('[data-edit-employee]');if(!b||auth?.role!=='admin')return;const r=employeeAdminRows.find(r=>r.id===Number(b.dataset.editEmployee));if(!r)return;const f=$('employeeForm');for(const k of ['id','name','identity','first_name','first_surname'])f.elements[k].value=r[k]||'';f.elements.access_code.value='';f.elements.active.checked=!!r.active;f.scrollIntoView({block:'center'})});
$('discountHistoryLoad').onclick=handle(async()=>{const rows=await api('admin/discount-beneficiaries');$('discountHistoryRows').innerHTML=rows.map(r=>'<tr><td>#'+r.number+' · '+esc(r.branch_name)+'<br>'+esc(r.created_at)+'</td><td>'+esc(r.profile==='EMPLOYEE'?'Empleado':'Tercera edad')+'</td><td>'+esc(r.name)+'</td><td>'+esc(r.identity)+'</td><td>'+esc(r.status)+'</td></tr>').join('')||'<tr><td colspan="5">No hay descuentos identificados registrados.</td></tr>'});
setInterval(()=>{if(auth?.role!=='admin'){employeeAdminRows=[];$('employeeRows').innerHTML='';$('discountHistoryRows').innerHTML='';$('employeeForm').reset();$('employeeForm').elements.id.value=''}if(!auth||document.body.classList.contains('locked')){discountPerson=null;$('discountPersonName').value='';$('discountPersonIdentity').value='';if($('discountPersonDialog').open)$('discountPersonDialog').close()}},250);

function selectSettingsTab(key){if(auth?.role!=='admin')return;if(key==='exclusions')loadNoDiscount().catch(e=>{$('noDiscountMessage').textContent=e.message});document.querySelectorAll('[data-settings-tab]').forEach(b=>{const active=b.dataset.settingsTab===key;b.classList.toggle('active',active);b.setAttribute('aria-selected',String(active));b.tabIndex=active?0:-1});document.querySelectorAll('.settings-section').forEach(p=>p.hidden=p.id!=='settingsPanel-'+key)}
document.querySelectorAll('[data-settings-tab]').forEach(b=>{b.onclick=()=>selectSettingsTab(b.dataset.settingsTab);b.onkeydown=e=>{const tabs=[...document.querySelectorAll('[data-settings-tab]')];let index=tabs.indexOf(b);if(e.key==='ArrowRight')index=(index+1)%tabs.length;else if(e.key==='ArrowLeft')index=(index-1+tabs.length)%tabs.length;else if(e.key==='Home')index=0;else if(e.key==='End')index=tabs.length-1;else return;e.preventDefault();selectSettingsTab(tabs[index].dataset.settingsTab);tabs[index].focus()}});

async function loadCancellationEmail(){const d=await api('admin/cancellation-email');$('cancellationEmail').value=d.email;$('cancellationEmailNote').textContent=d.smtp_ready?'Se utiliza el servidor de correo de Descuentos y correo.':'Configura el servidor y el remitente en Descuentos y correo. Los avisos quedarán pendientes hasta poder enviarse.'}
$('saveCancellationEmail').onclick=handle(async()=>{await api('admin/cancellation-email',{email:$('cancellationEmail').value});await loadCancellationEmail();toast('Correo de anulaciones guardado')});
async function loadCancellationEmails(){const rows=await api('admin/cancellation-emails');$('cancellationEmailRows').innerHTML=rows.map(r=>'<tr><td>#'+r.number+' · '+esc(r.branch_name)+'</td><td>'+esc(r.email_to)+'</td><td>'+esc(r.status)+'</td><td>'+esc(r.sent_at||'—')+'</td><td>'+esc(r.error||'')+'</td></tr>').join('')||'<tr><td colspan="5">No hay avisos de anulación registrados.</td></tr>'}
$('loadCancellationEmails').onclick=handle(loadCancellationEmails);$('retryCancellationEmails').onclick=handle(async()=>{await api('admin/cancellation-emails/retry',{});toast('Reintento solicitado. Consulta los envíos para actualizar su estado.');await loadCancellationEmails()});
function applyTheme(theme){document.documentElement.dataset.theme=theme;try{localStorage.setItem('fry-theme',theme)}catch(e){}for(const id of ['themeToggle','loginThemeToggle']){const b=$(id);b.textContent=theme==='dark'?'☀':'☾';b.title=theme==='dark'?'Modo claro':'Modo oscuro';b.setAttribute('aria-label',b.title);b.setAttribute('aria-pressed',String(theme==='dark'))}}
for(const id of ['themeToggle','loginThemeToggle'])$(id).onclick=()=>{const theme=document.documentElement.dataset.theme==='dark'?'light':'dark';applyTheme(theme);api('theme',{theme}).catch(e=>toast(e.message))};applyTheme(document.documentElement.dataset.theme||'light');
let noDiscountRows=[];
async function loadNoDiscount(){if(auth?.role!=='admin')return;if(noDiscountRows.some(r=>r.excluded!==r.savedExcluded))return;noDiscountRows=(await api('admin/no-discount')).map(r=>({...r,savedExcluded:r.excluded}));const previous=$('noDiscountCategory').value;const categories=[...new Set(noDiscountRows.map(r=>r.category))].sort((a,b)=>a.localeCompare(b,'es'));$('noDiscountCategory').value=categories.includes(previous)?previous:(categories[0]||'');$('noDiscountCategories').innerHTML=categories.map(c=>'<button type="button" data-exclusion-category="'+esc(c)+'">'+esc(c)+'</button>').join('');renderNoDiscount()}
function renderNoDiscount(){document.querySelectorAll('[data-exclusion-category]').forEach(b=>b.classList.toggle('active',b.dataset.exclusionCategory===$('noDiscountCategory').value));const rows=noDiscountRows.filter(r=>r.category===$('noDiscountCategory').value).sort((a,b)=>a.name.localeCompare(b.name,'es'));$('noDiscountProducts').innerHTML=rows.map(r=>'<label class="exclusion-product"><input type="checkbox" data-no-discount="'+r.id+'" '+(r.excluded?'checked':'')+'><span>'+esc(r.name)+'</span><b>'+(r.excluded?'SIN DESCUENTO':'Descuento permitido')+'</b></label>').join('')||'<p>No hay productos en esta categoría.</p>'}
$('noDiscountCategory').onchange=renderNoDiscount;
$('noDiscountProducts').addEventListener('change',e=>{const el=e.target.closest('[data-no-discount]');if(!el)return;const row=noDiscountRows.find(r=>r.id===Number(el.dataset.noDiscount));row.excluded=el.checked?1:0;renderNoDiscount();const count=noDiscountRows.filter(r=>r.excluded!==r.savedExcluded).length;$('noDiscountSaved').textContent=count?'CAMBIOS SIN GUARDAR: '+count+'. Pulsa GUARDAR CAMBIOS para aplicarlos.':'Sin cambios pendientes.';$('noDiscountMessage').textContent='';});
$('saveNoDiscount').onclick=handle(async()=>{const button=$('saveNoDiscount');button.disabled=true;$('noDiscountProducts').style.pointerEvents='none';try{const changes=noDiscountRows.filter(r=>r.excluded!==r.savedExcluded).map(r=>({id:r.id,excluded:!!r.excluded}));await api('admin/no-discount',{changes});for(const r of noDiscountRows)r.savedExcluded=r.excluded;await loadNoDiscount();const marked=noDiscountRows.filter(r=>r.excluded).length;$('noDiscountSaved').textContent='GUARDADO CORRECTAMENTE. '+marked+' productos SIN DESCUENTO. Sus marcas ya están aplicadas.';toast('Productos sin descuento guardados correctamente');await renderCart()}catch(e){$('noDiscountSaved').textContent='NO SE PUDO CONFIRMAR EL GUARDADO: '+e.message;throw e}finally{button.disabled=false;$('noDiscountProducts').style.pointerEvents=''}});
window.addEventListener('beforeunload',e=>{if(auth?.role==='admin'&&noDiscountRows.some(r=>r.excluded!==r.savedExcluded)){e.preventDefault();e.returnValue='Hay productos sin guardar'}});
let reprintInvoice=null,reprintTimer=null,reprintVersion=0;
$('menuReprint').onclick=()=>{$('sessionMenu').hidden=true;reprintInvoice=null;reprintVersion++;$('reprintNumber').value='';$('reprintTotal').textContent='TOTAL: —';$('reprintStatus').textContent='Ingresa el número para consultar.';$('reprintPrint').disabled=true;$('reprintDialog').showModal();$('reprintNumber').focus()};
async function findReprint(){const version=++reprintVersion,number=$('reprintNumber').value.trim();reprintInvoice=null;$('reprintPrint').disabled=true;$('reprintTotal').textContent='TOTAL: —';if(!number){$('reprintStatus').textContent='Ingresa el número para consultar.';return}$('reprintStatus').textContent='Buscando factura…';try{const r=await api('invoice-reprint?'+new URLSearchParams({number,branch_id:$('branch').value}));if(version!==reprintVersion)return;reprintInvoice={...r,search:number};$('reprintTotal').textContent='TOTAL: '+fmt(r.total);$('reprintStatus').textContent=(r.fiscal_number||'ORDEN #'+r.number)+' · '+r.status;$('reprintPrint').disabled=false}catch(e){if(version===reprintVersion)$('reprintStatus').textContent=e.message}}
$('reprintNumber').oninput=()=>{reprintInvoice=null;reprintVersion++;$('reprintPrint').disabled=true;clearTimeout(reprintTimer);reprintTimer=setTimeout(findReprint,350)};$('reprintNumber').onkeydown=e=>{if(e.key==='Enter'){e.preventDefault();clearTimeout(reprintTimer);findReprint()}};
$('reprintCancel').onclick=()=>{clearTimeout(reprintTimer);reprintVersion++;reprintInvoice=null;$('reprintDialog').close()};$('reprintDialog').addEventListener('cancel',()=>{clearTimeout(reprintTimer);reprintVersion++;reprintInvoice=null});
$('reprintPrint').onclick=async()=>{if(!reprintInvoice||reprintInvoice.search!==$('reprintNumber').value.trim())return;$('reprintPrint').disabled=true;try{const id=reprintInvoice.id;await api('invoice-reprint/'+id+'/request',{});$('receiptCopy').value='COPIA';await receipt(id,false);$('reprintDialog').close();requestAnimationFrame(()=>{if(nativePrinter)nativePrinter.request_print();else window.print()})}catch(e){$('reprintStatus').textContent=e.message;$('reprintPrint').disabled=false}};

document.getElementById('noDiscountCategories').onclick=e=>{const b=e.target.closest('[data-exclusion-category]');if(b){$('noDiscountCategory').value=b.dataset.exclusionCategory;renderNoDiscount()}};

// Keep the compact appearance control immediately before the session menu.
const headerActions=$('themeToggle').parentElement;headerActions.append($('themeToggle'),$('localLogout'),$('sessionMenu'));

/* Intercambio de catálogo completo. El archivo conserva fotos, precios, impuestos y exclusiones. */
$('exportProducts').onclick=handle(async()=>{const response=await fetch('/api/admin/products-export',{headers:{'X-POS-Token':document.querySelector('meta[name="pos-token"]').content}});if(!response.ok){const body=await response.json().catch(()=>({}));throw Error(body.error||'No se pudo exportar el catálogo')}const url=URL.createObjectURL(await response.blob()),link=document.createElement('a');link.href=url;link.download='FRYChickenPOS-productos.json';link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);toast('Catálogo JSON descargado')});
$('importProducts').onclick=()=>{$('catalogJsonFile').value='';$('catalogJsonFile').click()};
$('catalogJsonFile').onchange=handle(async()=>{const file=$('catalogJsonFile').files[0];if(!file)return;if(file.size>80*1024*1024)throw Error('El archivo JSON supera 80 MB');let document;try{document=JSON.parse(await file.text())}catch{throw Error('El archivo no contiene un JSON válido')}const total=Array.isArray(document.productos)?document.productos.length:0;if(!confirm('Se sustituirá el catálogo actual por '+total+' productos del archivo seleccionado. ¿Deseas continuar?'))return;$('importProducts').disabled=true;try{const result=await api('admin/products-import',document);applyProducts(result.products);await loadCategoryOrder();category='';renderProducts();cart=[];await renderCart();toast('Catálogo importado correctamente: '+result.count+' productos')}finally{$('importProducts').disabled=false;$('catalogJsonFile').value=''}});

// Comandas, alimentación de empleados y metas por sucursal (v39).
let kitchenCurrent=null,goalData=[],mealData=[],pendingGoalKeys=[];
function resetOrderFields(){for(const id of ['orderNotes','orderName'])$(id).value='';syncOrderNotesButton();$('orderService').value='COMER AQUI';$('deliveryFee').value='0';paintService();$('employeeMeal').checked=false;$('mealFields').hidden=true;$('mealCost').value='0';document.body.classList.remove('employee-meal-mode');kitchenCurrent=null}
$('kitchenPrinterSetup').onclick=()=>{if(nativePrinter)nativePrinter.configureKitchen();else toast('Abre INICIAR.bat para seleccionar la impresora de cocina')};
$('employeeMeal').onchange=handle(async()=>{const enabled=$('employeeMeal').checked;if(cart.length&&!confirm('¿Vaciar el pedido actual para cambiar de modalidad?')){$('employeeMeal').checked=!enabled;return}cart=[];$('mealFields').hidden=!enabled;document.body.classList.toggle('employee-meal-mode',enabled);if(enabled){$('specialOrder').checked=false;resetDiscountPerson();const [rows,menu]=await Promise.all([api('employees'),api('employee-menu')]);employeeMealMenu=menu;$('mealEmployee').innerHTML='<option value="">Selecciona un empleado</option>'+rows.map(r=>`<option value="${r.id}">${esc(r.name)}</option>`).join('');for(const [id,kind] of [['mealDish','DISH'],['mealDrink','DRINK']])$(id).innerHTML='<option value="">Selecciona '+(kind==='DISH'?'un plato':'un refresco')+'</option>'+menu.filter(r=>r.kind===kind).map(r=>`<option value="${r.id}">${esc(r.name)}</option>`).join('');if(!menu.some(r=>r.kind==='DISH')||!menu.some(r=>r.kind==='DRINK'))toast('El administrador debe autorizar al menos un plato y un refresco en Almuerzos de empleados.')}await renderCart()});
$('menuMeal').onclick=handle(async()=>{$('sessionMenu').hidden=true;showView('pos');$('employeeMeal').checked=true;await $('employeeMeal').onchange();$('mealFields').scrollIntoView({block:'nearest'})});
async function saveMeal(){const employee_id=Number($('mealEmployee').value);if(!employee_id)throw Error('Selecciona el empleado que recibe el almuerzo');if(!confirm('¿Registrar este almuerzo gratis, sin factura ni CAI?'))return;$('pay').disabled=true;try{saleKey=saleKey||crypto.randomUUID();const r=await api('employee-meals',{...payload(),employee_id,cost:$('mealCost').value,request_id:saleKey});await sendKitchen(r.kitchen_id,true);cart=[];resetOrderFields();resetDiscountPerson();await renderCart();toast('Almuerzo guardado como alimentación de empleado. Cobrado: L 0.00.');await openKitchen(r.kitchen_id)}finally{$('pay').disabled=!cart.length}}
async function sendKitchen(id,automatic=false){if(!id)return;try{const r=await api('kitchen-orders/'+id);if(nativePrinter)nativePrinter.printHtml(r.html,'kitchen',automatic);else if(automatic)toast('Pedido guardado. Abre la aplicación de escritorio para imprimir automáticamente en cocina.')}catch(e){toast('Pedido guardado. Comanda pendiente: '+e.message)}}
async function openKitchen(id){const r=await api('kitchen-orders/'+id);kitchenCurrent=r;$('kitchenPreview').innerHTML=r.html;$('kitchenPrint').disabled=false;if(!$('kitchenDialog').open)$('kitchenDialog').showModal()}
async function loadKitchen(){const rows=await api('kitchen-orders?branch_id='+$('branch').value);$('kitchenRows').innerHTML=rows.map(r=>`<p><button data-kitchen="${r.id}">Orden #${r.id}</button> ${esc(r.created_at.slice(0,19).replace('T',' '))} · ${esc({SALE:'Venta',MEAL:'Almuerzo',SPECIAL:'Consumo interno'}[r.kind])}</p>`).join('')||'<p>No hay comandas registradas.</p>'}
$('menuKitchen').onclick=handle(async()=>{$('sessionMenu').hidden=true;kitchenCurrent=null;$('kitchenPreview').innerHTML='';$('kitchenPrint').disabled=true;await loadKitchen();$('kitchenDialog').showModal()});
$('kitchenRefresh').onclick=handle(loadKitchen);$('kitchenClose').onclick=()=>$('kitchenDialog').close();$('kitchenPrint').onclick=()=>{if(!kitchenCurrent)return;if(nativePrinter)nativePrinter.printHtml(kitchenCurrent.html,'kitchen',false);else toast('Abre INICIAR.bat para imprimir en la impresora de cocina')};
async function loadMeals(){if(auth?.role!=='admin')return;const previous=$('mealBranch').value;$('mealBranch').innerHTML='<option value="all">Todas las sucursales</option>'+branches.map(b=>`<option value="${b.id}">${esc(b.name)}</option>`).join('');$('mealBranch').value=previous||'all';const p=new URLSearchParams({branch_id:$('mealBranch').value,start:$('mealStart').value,end:$('mealEnd').value});mealData=await api('employee-meals?'+p);$('mealStats').innerHTML=[['Almuerzos',mealData.length],['Gasto de alimentación',fmt(mealData.reduce((a,r)=>a+r.cost,0))],['Costo pendiente',mealData.filter(r=>!r.cost).length],['Cobrado',fmt(0)]].map(([k,v])=>`<div>${k}<strong>${v}</strong></div>`).join('');$('mealRows').innerHTML=mealData.map(r=>`<tr><td>${esc(r.created_at)}<br>${esc(r.branch_name)}</td><td>${esc(r.recipient)}</td><td>${r.snapshot.items.map(x=>`${x.quantity} × ${esc(x.name)}`).join('<br>')}</td><td>${r.cost?fmt(r.cost):'Pendiente'} <button data-meal-cost="${r.id}">Costo</button></td><td>L 0.00</td><td><button data-kitchen="${r.kitchen_id}">Ver comanda</button></td></tr>`).join('')||'<tr><td colspan="6">Sin almuerzos en este período.</td></tr>'}
$('mealsRefresh').onclick=handle(loadMeals);
$('mealsCsv').onclick=()=>{const rows=[['Fecha','Sucursal','Empleado','Costo gasto L','Cobrado L','Productos','Notas'],...mealData.map(r=>[r.created_at,r.branch_name,r.recipient,r.cost/100,0,r.snapshot.items.map(x=>x.quantity+' x '+x.name).join('; '),r.snapshot.notes])];const csv='\ufeff'+rows.map(row=>row.map(x=>'"'+String(x??'').replace(/^[=+@-]/,"'$&").replace(/"/g,'""')+'"').join(',')).join('\r\n');const u=URL.createObjectURL(new Blob([csv],{type:'text/csv;charset=utf-8'}));const a=document.createElement('a');a.href=u;a.download='Almuerzos-empleados.csv';a.click();setTimeout(()=>URL.revokeObjectURL(u),1000)};
function goalKey(r){return 'fry-goal:'+r.id+':'+r.revision+':'+(auth.cashier?.id||auth.role)}
function goalDisplayedSales(r){return Math.min(Number(r.sales)||0,Number(r.target)||0)}
function goalValue(r,n){return r.goal_type==='PRODUCT'?Number(n||0).toLocaleString('es-HN')+' UNIDADES':fmt(n)}
function goalProductCaption(r){return r.goal_type==='PRODUCT'?'<p>PRODUCTO: '+esc(r.product_name)+'</p>':''}
function paintGoalProducts(){
 const select=$('goalProduct');if(!select)return;const old=select.value,option=select.selectedOptions[0];
 select.innerHTML='<option value="">SELECCIONA EL PRODUCTO</option>'+products.filter(p=>p.active!==false&&p.active!==0).map(p=>'<option value="'+p.id+'">'+esc(p.name)+'</option>').join('');
 if(old&&!products.some(p=>String(p.id)===old)&&option)select.add(new Option(option.textContent,old));select.value=old;
 updateGoalFormMode();
}
function updateGoalFormMode(){
 const product=$('goalKind')?.value==='PRODUCT';if(!$('goalProduct'))return;
 $('goalProductLabel').hidden=!product;$('goalProduct').required=product;$('goalProduct').disabled=!product;
 const input=$('goalForm').elements.target;input.min=product?'1':'0.01';input.step=product?'1':'0.01';input.parentElement.firstChild.nodeValue=product?'CANTIDAD DE UNIDADES':'META DE VENTAS (L)';
}
function currentBranchGoals(){return goalData.filter(r=>r.active&&Number(r.branch_id)===Number($('branch').value))}
function updateGoalIndicator(){
 const button=$('goalIndicator');if(!button)return;
 const rows=currentBranchGoals(),reached=rows.filter(r=>r.reached).length;
 button.hidden=!['admin','local'].includes(auth?.role)||!reached;
 button.setAttribute('aria-label','METAS: '+reached+' CUMPLIDAS Y '+(rows.length-reached)+' PENDIENTES');
 button.title='VER METAS CUMPLIDAS Y PENDIENTES';
 if($('goalOverview').open)paintGoalOverview();
}
function paintGoalOverview(){
 const rows=currentBranchGoals();
 $('goalOverviewRows').innerHTML=[['🥳 METAS CUMPLIDAS',rows.filter(r=>r.reached)],['METAS PENDIENTES',rows.filter(r=>!r.reached)]].map(([title,goals])=>'<section><h3>'+title+'</h3>'+ (goals.map(r=>'<article class="goal-overview-card"><b>'+esc(r.title)+'</b>'+goalProductCaption(r)+'<p>'+esc(r.start)+' AL '+esc(r.end)+'</p><progress max="100" value="'+Math.min(100,Math.max(0,Number(r.progress)||0))+'" aria-label="AVANCE"></progress><p>'+goalValue(r,goalDisplayedSales(r))+' / '+goalValue(r,r.target)+' · '+esc(r.progress)+'%</p><p>'+(r.reached?'CUMPLIDA':'FALTAN '+goalValue(r,r.remaining))+'</p></article>').join('')||'<p>NINGUNA</p>')+'</section>').join('');
}
async function loadGoals(notify=false){if(!['admin','local'].includes(auth?.role))return;goalData=await api('goals');if(auth.role==='admin'&&!products.length)await loadProducts();paintGoalProducts();const old=$('goalBranch').value;$('goalBranch').innerHTML=branches.filter(b=>b.active).map(b=>`<option value="${b.id}">${esc(b.name)}</option>`).join('');$('goalBranch').value=old||$('branch').value;$('goalAdmin').hidden=auth.role!=='admin';$('goalRows').innerHTML=goalData.map(r=>`<div class="panel goal-card"><h3>${esc(r.title)} ${!r.active?'(Inactiva)':''}</h3>${goalProductCaption(r)}<p>${esc(r.branch_name)} · ${r.start} al ${r.end} · ${esc(r.period_status)}</p><progress max="100" value="${r.progress}" aria-label="Avance de ${esc(r.title)}"></progress><p><b>${r.progress}% · ${goalValue(r,goalDisplayedSales(r))} / ${goalValue(r,r.target)}</b><br>${r.reached?'¡Meta alcanzada!':'Faltan '+goalValue(r,r.remaining)}</p>${auth.role==='admin'?`<button data-goal-edit="${r.id}">Editar meta</button>`:''}</div>`).join('')||'<p>No hay metas asignadas.</p>';updateGoalIndicator()}
$('menuGoals').onclick=handle(async()=>{$('sessionMenu').hidden=true;showView('goals');await loadGoals()});$('goalsRefresh').onclick=handle(()=>loadGoals(true));
$('goalForm').onsubmit=handle(async e=>{e.preventDefault();const d=Object.fromEntries(new FormData(e.target));d.branch_id=Number(d.branch_id);d.active=e.target.elements.active.checked;await api('goals',d);e.target.reset();await loadGoals(true);toast('Meta guardada')});$('goalReset').onclick=()=>$('goalForm').reset();
function acknowledgeGoals(){pendingGoalKeys.forEach(k=>localStorage.setItem(k,'1'));pendingGoalKeys=[]}
$('goalNoticeClose').onclick=()=>{acknowledgeGoals();$('goalNotice').close()};$('goalNotice').addEventListener('cancel',acknowledgeGoals);
document.addEventListener('click',handle(async e=>{const b=e.target.closest('button');if(!b)return;if(b.dataset.kitchen)await openKitchen(b.dataset.kitchen);if(b.dataset.goalEdit){const r=goalData.find(x=>x.id==b.dataset.goalEdit),f=$('goalForm');for(const k of ['id','branch_id','title','start','end'])f.elements[k].value=r[k];$('goalKind').value=r.goal_type||'SALES';paintGoalProducts();if(r.product_id&&!$('goalProduct').querySelector('option[value="'+r.product_id+'"]'))$('goalProduct').add(new Option(r.product_name,r.product_id));$('goalProduct').value=r.product_id||'';updateGoalFormMode();f.elements.target.value=r.goal_type==='PRODUCT'?r.target:r.target/100;f.elements.active.checked=!!r.active;f.scrollIntoView({block:'nearest'})}}));
setInterval(()=>{if(['admin','local'].includes(auth?.role))loadGoals(true).catch(()=>{})},30000);

document.addEventListener('click',handle(async e=>{const b=e.target.closest('[data-meal-cost]');if(!b)return;const r=mealData.find(x=>x.id==b.dataset.mealCost);const cost=prompt('Costo real del almuerzo (L):',r.cost/100);if(cost===null)return;await api('admin/employee-meals/'+r.id+'/cost',{cost});await loadMeals()}));

// Respaldo remoto confirmado y autorización temporal (v40).
let backupState=null,backupRefreshing=false;
function backupMessage(s){if(!s?.enabled)return 'El respaldo remoto todavía no está activado.';const emergency=(s.override_until||0)*1000>Date.now();const last=s.last_invoice;return (s.online?'RESPALDO CONECTADO':emergency?'SIN CONEXIÓN · VENTAS EN EMERGENCIA':'SIN CONEXIÓN · FACTURACIÓN BLOQUEADA')+(emergency?' · EMERGENCIA AUTORIZADA HASTA '+new Date(s.override_until*1000).toLocaleTimeString():'')+'\n'+(last?'Última factura confirmada: '+(last.fiscal_number||last.number)+' · '+last.created_at:'Todavía no hay una factura confirmada.')+(s.confirmed_at?'\nConfirmación: '+new Date(s.confirmed_at).toLocaleString():'')+(!s.online&&s.error?'\n'+s.error:'')}
async function refreshBackup(check=false){if(!['admin','local'].includes(auth?.role))return null;if(backupRefreshing)return backupState;backupRefreshing=true;try{backupState=await api('network-backup/'+(check?'check':'status'),check?{}:undefined);const text=backupMessage(backupState);$('backupBanner').hidden=!backupState.enabled;$('backupBannerText').textContent=text;$('backupBanner').style.whiteSpace='pre-wrap';$('backupBanner').classList.toggle('backup-offline',backupState.enabled&&!backupState.online);$('backupAdminStatus').textContent=text;$('backupDialogStatus').textContent=text;return backupState}finally{backupRefreshing=false}}
async function ensureBackup(){const s=await refreshBackup(true);if(s?.enabled&&!s.online&&(s.override_until||0)*1000<=Date.now()){if(!$('backupDialog').open)$('backupDialog').showModal();return false}return true}
async function loadBackupSettings(){const cfg=await api('admin/network-backup');$('networkBackupForm').elements.enabled.checked=cfg.enabled;$('networkBackupForm').elements.url.value=cfg.url;$('networkBackupForm').elements.fallback_url.value=cfg.fallback_url||'';$('networkBackupForm').elements.key.value='';$('backupInstance').textContent='Identificador de esta instalación: '+cfg.instance;await refreshBackup(true)}
$('networkBackupForm').onsubmit=handle(async e=>{e.preventDefault();const d=Object.fromEntries(new FormData(e.target));d.enabled=e.target.elements.enabled.checked;await api('admin/network-backup',d);e.target.elements.key.value='';await refreshBackup(false);toast('Configuración de respaldo guardada')});
async function openBackupDialog(){await refreshBackup(false);$('backupEmergencyError').textContent='';if(!$('backupDialog').open)$('backupDialog').showModal()}
$('menuBackup').onclick=handle(async()=>{$('sessionMenu').hidden=true;await openBackupDialog()});$('backupBannerOpen').onclick=handle(openBackupDialog);$('backupEmergencyAdmin').onclick=handle(openBackupDialog);
$('backupCheck').onclick=handle(()=>refreshBackup(true));$('backupRetry').onclick=handle(()=>refreshBackup(true));$('backupDialogClose').onclick=()=>$('backupDialog').close();
$('backupEmergencyForm').onsubmit=async e=>{e.preventDefault();const button=e.target.querySelector('button');button.disabled=true;try{await api('network-backup/emergency',Object.fromEntries(new FormData(e.target)));e.target.reset();await refreshBackup(false);$('backupDialog').close();toast('Emergencia autorizada por 30 minutos. Las ventas se guardarán localmente si no hay conexión.')}catch(err){$('backupEmergencyError').textContent=err.message}finally{button.disabled=false}};
setInterval(()=>{if(['admin','local'].includes(auth?.role))refreshBackup(true).catch(()=>{})},15000);

$('discoverBackup').onclick=handle(async()=>{const rows=await api('admin/network-backup/discover',{key:$('networkBackupForm').elements.key.value});if(!rows.length)throw Error('No se encontró un receptor con esa clave. Revisa red, firewall y receptor encendido.');if(rows.length>1)throw Error('Se encontró más de un receptor. Configura la dirección manualmente.');$('networkBackupForm').elements.url.value=rows[0].url;toast('Receptor encontrado: '+rows[0].name+'. Pulsa Guardar y comprobar.')});

// Menú gratuito administrado (v42): dos selecciones de una unidad.
let employeeMealMenu=[],employeeMenuAdminRows=[];
async function selectEmployeeMeal(){const dish=employeeMealMenu.find(x=>x.id==$('mealDish').value&&x.kind==='DISH'),drink=employeeMealMenu.find(x=>x.id==$('mealDrink').value&&x.kind==='DRINK');cart=dish&&drink?[{...dish,quantity:1},{...drink,quantity:1}]:[];await renderCart()}
$('mealDish').onchange=handle(selectEmployeeMeal);$('mealDrink').onchange=handle(selectEmployeeMeal);
async function loadEmployeeMenuAdmin(){employeeMenuAdminRows=await api('admin/employee-menu');$('mealMenuAdmin').innerHTML='<table><thead><tr><th>Producto</th><th>Categoría</th><th>Autorización</th></tr></thead><tbody>'+employeeMenuAdminRows.map(r=>`<tr><td>${esc(r.name)}</td><td>${esc(r.category)}</td><td><select data-meal-menu="${r.id}"><option value="">No gratuito</option><option value="DISH" ${r.kind==='DISH'?'selected':''}>Plato gratuito</option><option value="DRINK" ${r.kind==='DRINK'?'selected':''}>Refresco gratuito</option></select></td></tr>`).join('')+'</tbody></table>';$('mealMenuSave').disabled=false}
$('mealMenuLoad').onclick=handle(loadEmployeeMenuAdmin);
$('mealMenuSave').onclick=handle(async()=>{const products=[...document.querySelectorAll('[data-meal-menu]')].filter(el=>el.value).map(el=>({id:Number(el.dataset.mealMenu),kind:el.value}));await api('admin/employee-menu',{products});toast('Menú gratuito guardado: solo un plato y un refresco por almuerzo.');await loadEmployeeMenuAdmin()});

// Modalidad de preparación y envío separado (v43).
function paintService(){document.querySelectorAll('[data-service]').forEach(b=>{const active=b.dataset.service===$('orderService').value;b.classList.toggle('active',active);b.setAttribute('aria-pressed',String(active))});$('deliverySummary').hidden=$('orderService').value!=='PARA ENVIO';$('deliverySummary').textContent='PARA ENVÍO · '+fmt(Math.round(Number($('deliveryFee').value||0)*100))+' (se cobra aparte de los productos)'}
document.addEventListener('click',handle(async e=>{const b=e.target.closest('[data-service]');if(!b)return;if(b.dataset.service==='PARA ENVIO'){$('deliveryAmount').value=$('orderService').value==='PARA ENVIO'?$('deliveryFee').value:'';$('deliveryError').textContent='';$('deliveryDialog').showModal();$('deliveryAmount').focus();return}$('orderService').value=b.dataset.service;$('deliveryFee').value='0';paintService();await renderCart()}));
$('deliveryCancel').onclick=()=>$('deliveryDialog').close();
$('deliveryForm').onsubmit=handle(async e=>{e.preventDefault();const input=$('deliveryAmount');if(!input.checkValidity()){input.reportValidity();return}const value=Number(input.value);if(!Number.isFinite(value)||value<0)throw Error('Precio de envío inválido');if(value>0&&($('employeeMeal').checked||$('specialOrder').checked)){$('deliveryError').textContent='El envío con cobro debe registrarse en una venta, separado del consumo gratis.';return}$('orderService').value='PARA ENVIO';$('deliveryFee').value=input.value;$('deliveryDialog').close();paintService();await renderCart()});
paintService();

// Terminales, impresión central y recuperación de cobros (v44).
let terminalAdminRows=[],terminalEmployeeRows=[],centralReprintKeys={};
function paintCentral(){const t=auth?.terminal||{id:0,name:'PC 1'};$('centralBanner').textContent=t.remote?t.name+' · Facturación e impresión en PC 1':'PC 1 · Servidor del local y cola central de impresión';$('menuPending').hidden=!t.remote}
async function loadTerminalAdmin(){const [rows,staff,primary,info]=await Promise.all([api('admin/terminals'),api('employees'),api('admin/primary-employees'),api('admin/central-info')]);terminalAdminRows=rows;terminalEmployeeRows=staff;$('centralAddresses').textContent='Direcciones posibles de PC 1: '+info.addresses.map(ip=>'http://'+ip+':'+info.port).join(' · ');$('terminalBranch').innerHTML=branches.filter(b=>b.active).map(b=>`<option value="${b.id}">${esc(b.name)}</option>`).join('');$('primaryStaff').innerHTML=staff.map(e=>`<label><span><input type="checkbox" data-primary-employee="${e.id}" ${(primary.employee_ids===null||primary.employee_ids.includes(e.id))?'checked':''}> ${esc(e.name)}</span></label>`).join('');renderTerminalStaff([]);$('terminalRows').innerHTML=rows.map(r=>`<div class="panel"><b>${pcLabel(r.id)} · ${r.active?'Activa':'Retirada'}</b><p>${r.employee_ids.map(id=>esc(staff.find(e=>e.id===id)?.name||'Empleado #'+id)).join(', ')}</p><button data-edit-terminal="${r.id}">Editar permisos / renovar clave</button>${r.open_shift?`<p>Turno #${r.open_shift.id} · ${esc(r.open_shift.opened_by)}</p><button data-terminal-close="${r.id}">Cerrar este turno como administrador</button>`:''}</div>`).join('')||'<p>No hay terminales adicionales.</p>';await loadPrintJobs()}
function renderTerminalStaff(ids){$('terminalStaff').innerHTML=terminalEmployeeRows.map(e=>`<label><span><input type="checkbox" data-terminal-employee="${e.id}" ${ids.includes(e.id)?'checked':''}> ${esc(e.name)}</span></label>`).join('')}
$('terminalNew').onclick=()=>{$('terminalForm').reset();renderTerminalStaff([]);$('terminalKeyResult').hidden=true};
$('terminalForm').onsubmit=handle(async e=>{e.preventDefault();const d=Object.fromEntries(new FormData(e.target));d.branch_id=Number(d.branch_id);d.employee_ids=[...document.querySelectorAll('[data-terminal-employee]:checked')].map(el=>Number(el.dataset.terminalEmployee));d.active=e.target.elements.active.checked;d.rotate_key=e.target.elements.rotate_key.checked;const r=await api('admin/terminals',d);e.target.reset();await loadTerminalAdmin();$('terminalKeyResult').hidden=!r.key;if(r.key){$('terminalCreatedId').value=r.id;$('terminalCreatedKey').value=r.key}toast('Terminal guardada. Sus empleados deberán iniciar sesión de nuevo.')});
$('terminalCopyKey').onclick=handle(async()=>{await navigator.clipboard.writeText($('terminalCreatedKey').value);toast('Clave copiada')});
$('primaryStaffSave').onclick=handle(async()=>{const employee_ids=[...document.querySelectorAll('[data-primary-employee]:checked')].map(e=>Number(e.dataset.primaryEmployee));await api('admin/primary-employees',{employee_ids});toast('Permisos de PC 1 guardados')});
const printStateLabels={PENDING:'EN COLA',PAUSED:'PAUSADA',CLAIMED:'PREPARANDO',SPOOLING:'ENVIANDO',SPOOLED:'ENVIADO A IMPRESIÓN',UNCERTAIN:'DUDOSO · REVISAR PAPEL',FAILED:'NO ENVIADO',CANCELLED:'CANCELADA'};
function printRows(rows){return rows.map(r=>`<div class="panel"><b>#${r.id} · ${r.source_kind==='CASH_CLOSE'?'Cierre de caja':r.role==='cash'?'Factura':'Comanda'} ${r.source_kind==='CASH_CLOSE'?esc('CAJA #'+(Number(r.terminal_id||0)+1)+' · Turno #'+r.source_id):esc(r.document_number||r.source_id)} · ${r.is_copy?'COPIA':'ORIGINAL'}</b><p>${esc(printStateLabels[r.state]||r.state)} · ${esc(pcLabel(r.terminal_id))}<br>${esc(r.last_error)}</p>${auth.role==='admin'&&['PAUSED','FAILED'].includes(r.state)?`<button data-release-job="${r.id}">Enviar documento pendiente</button>`:''}${['SPOOLED','UNCERTAIN','FAILED'].includes(r.state)?r.source_kind==='CASH_CLOSE'?((auth.role==='admin'||r.terminal_id===auth.terminal?.id)?`<button data-close-copy="${r.source_id}">Solicitar copia del cierre</button>`:''):`<button data-copy-role="${r.role}" data-copy-source="${r.source_id}">Solicitar copia</button>`:''}</div>`).join('')||'<p>No hay documentos en la cola.</p>'}
async function loadPrintJobs(){const rows=await api('printing/jobs');$('printJobRows').innerHTML=printRows(rows);$('localPrintJobs').innerHTML=printRows(rows)}
async function queueCentralCopy(role,source){const key=role+':'+source;centralReprintKeys[key]=centralReprintKeys[key]||crypto.randomUUID();const r=await api('printing/reprint',{role,source_id:Number(source),request_id:centralReprintKeys[key]});delete centralReprintKeys[key];toast(r.is_copy?'Copia enviada a la cola central de PC 1':'El documento original está en la cola central de PC 1')}
window.requestCentralReprint=handle(async role=>{const source=role==='cash'?lastReceiptId:kitchenCurrent?.id;if(!source||(role==='cash'&&!$('receipt').open)||(role==='kitchen'&&!$('kitchenDialog').open))throw Error('Abre el documento que quieres reimprimir');await queueCentralCopy(role,source)});
$('menuPrintJobs').onclick=handle(async()=>{$('sessionMenu').hidden=true;await loadPrintJobs();$('printJobsDialog').showModal()});$('printJobsClose').onclick=()=>$('printJobsDialog').close();$('printJobsRefresh').onclick=handle(loadPrintJobs);
document.addEventListener('click',handle(async e=>{const b=e.target.closest('button');if(!b)return;if(b.dataset.editTerminal){const r=terminalAdminRows.find(x=>x.id==b.dataset.editTerminal),f=$('terminalForm');for(const k of ['id','name','branch_id'])f.elements[k].value=r[k];f.elements.active.checked=!!r.active;f.elements.rotate_key.checked=false;renderTerminalStaff(r.employee_ids);$('terminalKeyResult').hidden=true;f.scrollIntoView({block:'nearest'})}if(b.dataset.releaseJob){await api('admin/printing/jobs/'+b.dataset.releaseJob+'/release',{});await loadPrintJobs()}if(b.dataset.copyRole&&confirm('Comprueba primero el papel. ¿Solicitar una COPIA de este documento?')){await queueCentralCopy(b.dataset.copyRole,b.dataset.copySource);await loadPrintJobs()}}));
async function loadPendingSale(){if(!auth?.terminal?.remote)return;const d=await api('local-pending');if(!d.pending)return;$('pendingSaleStatus').textContent='Hay un cobro sin confirmar: '+d.request_id+'. Consulta su resultado antes de crear una venta nueva.';if(!$('pendingSaleDialog').open)$('pendingSaleDialog').showModal()}
$('menuPending').onclick=handle(async()=>{$('sessionMenu').hidden=true;await loadPendingSale()});$('pendingSaleClose').onclick=()=>$('pendingSaleDialog').close();
async function completeRecoveredSale(id){await api('local-pending/ack',{invoice_id:id});if($('payment').open)$('payment').close();$('pendingSaleDialog').close();cart=[];saleKey=null;resetOrderFields();resetDiscountPerson();await renderCart();await receipt(id,false);toast('Se recuperó la misma factura. Su impresión está en la cola central.')}
$('pendingSaleCheck').onclick=handle(async()=>{const r=await api('local-pending/result');if(r.found){await completeRecoveredSale(r.invoice.id);return}if(r.processing){$('pendingSaleStatus').textContent='PC 1 todavía está procesando el cobro. Espera y consulta otra vez.';return}$('pendingSaleStatus').textContent='No hay una factura guardada con ese identificador. Puedes reintentar el mismo cobro o cancelarlo.'});
$('pendingSaleRetry').onclick=handle(async()=>{if(!confirm('¿Reintentar exactamente el cobro original con su mismo identificador?'))return;const r=await api('local-pending/retry',{});await completeRecoveredSale(r.id)});
$('pendingSaleCancel').onclick=handle(async()=>{if(!confirm('Se comprobará que no existe factura. ¿Cancelar este cobro pendiente?'))return;await api('local-pending/cancel',{});$('pendingSaleDialog').close();if($('payment').open)$('payment').close();saleKey=null;toast('Pendiente cancelado; no se generó una factura.')});
setInterval(()=>{if(auth?.role&&(!$('terminals').hidden||$('printJobsDialog').open))loadPrintJobs().catch(()=>{})},5000);

document.addEventListener('click',handle(async e=>{const b=e.target.closest('[data-terminal-close]');if(!b)return;const r=terminalAdminRows.find(x=>x.id==b.dataset.terminalClose);const counted=prompt('Efectivo contado (L) para cerrar el turno de '+r.name+':');if(counted===null)return;if(!confirm('¿Confirmar el cierre definitivo de '+r.name+' con L '+counted+' contados?'))return;await api('admin/terminals/'+r.id+'/cash-close',{shift_id:r.open_shift.id,counted});await loadTerminalAdmin();toast('Turno cerrado con auditoría del administrador.')}));

// Acceso a notas junto a las categorías (v45).
function syncOrderNotesButton(){const button=$('orderNotesOpen');if(!button)return;const filled=!!($('orderNotes').value.trim()||$('orderName').value.trim());button.classList.toggle('has-order-notes',filled);button.textContent=filled?'NOTAS •':'NOTAS'}
document.addEventListener('click',e=>{if(!e.target.closest('[data-order-notes]'))return;if(!$('orderNotesDialog').open)$('orderNotesDialog').showModal();$('orderNotes').focus()});
$('orderNotesForm').onsubmit=e=>{e.preventDefault();syncOrderNotesButton();$('orderNotesDialog').close()};
$('orderNotesClose').onclick=()=>{syncOrderNotesButton();$('orderNotesDialog').close()};
$('orderNotesDialog').addEventListener('close',syncOrderNotesButton);

// Pantalla compacta (v46).
document.addEventListener('click',handle(async e=>{const b=e.target.closest('[data-remove-line]');if(!b)return;if($('employeeMeal').checked){for(const id of ['mealDish','mealDrink'])if($(id).value===b.dataset.removeLine)$(id).value=''}cart=cart.filter(x=>x.id!==Number(b.dataset.removeLine));await renderCart()}));
document.addEventListener('keydown',e=>{if(e.repeat)return;if(e.key==='F10'){e.preventDefault();if(!$('pos').hidden&&!document.querySelector('dialog[open]')&&!$('pay').disabled)$('pay').click()}if(e.key==='F11'){e.preventDefault();if($('payment').open&&!document.querySelector('dialog[open]:not(#payment)')){const input=document.activeElement;if(paymentFields().includes(input?.id))commitPayment(input.id);if(paymentIsValid())$('confirmPay').click();else $('paymentError').textContent='Digita los montos completos antes de confirmar la venta.'}}});
const pcTag=document.createElement('small');pcTag.id='pcTag';$('localLogout').parentElement.append(pcTag);$('centralBanner').hidden=true;
const paintCentralOriginal=paintCentral;paintCentral=function(){paintCentralOriginal();$('centralBanner').hidden=true;const n=auth?.terminal?.remote?auth.terminal.id+1:1;pcTag.textContent='PC '+n};

let companyBenefitRows=[];
function companyBenefitChoices(selected=[]){$('companyBenefitProducts').innerHTML=products.map(p=>`<label><span><input type="checkbox" data-benefit-product="${p.id}" ${selected.includes(p.id)?'checked':''}> ${esc(p.category)} · ${esc(p.name)}</span></label>`).join('')}
async function loadCompanyBenefits(){if(!products.length)await loadProducts();companyBenefitRows=await api('admin/company-benefits');companyBenefitChoices();$('companyBenefitRows').innerHTML=companyBenefitRows.map(r=>`<div class="panel"><b>${esc(r.name)}</b> · ${esc(r.rtn)} · ${r.kind} · ${r.active?'Activa':'Inactiva'}<p>${r.products.length} productos autorizados · Revisión ${r.revision}</p><button type="button" data-edit-benefit="${r.id}">Editar autorización</button>${r.has_photo?`<a href="/api/admin/company-benefits/${r.id}/photo" target="_blank" rel="noopener">Ver foto</a>`:''}</div>`).join('')||'<p>No hay empresas registradas.</p>'}
$('companyBenefitNew').onclick=()=>{$('companyBenefitForm').reset();$('companyBenefitForm').elements.id.value='';companyBenefitChoices()};
document.addEventListener('click',e=>{const b=e.target.closest('[data-edit-benefit]');if(!b)return;const r=companyBenefitRows.find(r=>r.id==b.dataset.editBenefit),f=$('companyBenefitForm');f.reset();for(const k of ['id','name','rtn','kind'])f.elements[k].value=r[k];f.elements.active.checked=!!r.active;companyBenefitChoices(r.products);f.scrollIntoView({block:'start'})});
$('companyBenefitForm').onsubmit=handle(async e=>{e.preventDefault();const f=e.target,d=Object.fromEntries(new FormData(f));d.active=f.elements.active.checked;d.remove_photo=f.elements.remove_photo.checked;d.products=[...document.querySelectorAll('[data-benefit-product]:checked')].map(x=>Number(x.dataset.benefitProduct));const file=f.elements.photo.files[0];delete d.photo;if(file){if(file.size>8*1024*1024)throw Error('La foto supera 8 MB');d.photo=await new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(reader.result.split(',')[1]);reader.onerror=()=>reject(Error('No se pudo leer la foto'));reader.readAsDataURL(file)})}await api('admin/company-benefits',d);f.reset();f.elements.id.value='';await loadCompanyBenefits();await loadCustomers();toast('Autorización guardada')});
let companyQuoteTimer;
for(const id of ['rtn','customerName'])$(id).addEventListener('input',()=>{clearTimeout(companyQuoteTimer);companyQuoteTimer=setTimeout(()=>renderCart(),350)});
for(const id of ['savedCustomer','type'])$(id).addEventListener('change',()=>renderCart());
$('pay').textContent='Continuar cobro · F10 →';$('confirmPay').textContent='Confirmar venta · F11';

const companyBenefitNotice=document.createElement('small');companyBenefitNotice.id='companyBenefitNotice';companyBenefitNotice.hidden=true;$('cart').before(companyBenefitNotice);

function employeeGreeting(hour=new Date().getHours()){return hour>=5&&hour<12?'Buenos días':hour>=12&&hour<18?'Buenas tardes':'Buenas noches'}
async function showEmployeeWelcome(d){
 const generation=++employeePromptGeneration;employeePromptBranch=d.branch.id;localLoginStage='EMPLOYEE';
 $('login').close();document.body.classList.add('locked','branch-user','branch-preview');document.body.classList.remove('admin-user');
 auth={...auth,role:null,branch:d.branch};branches=[{...d.branch,active:true}];$('branch').innerHTML=`<option value="${d.branch.id}">${esc(d.branch.name)}</option>`;
 categoryOrder=d.category_order||[];cart=[];applyProducts(d.products);showView('pos');$('cashierCurrentLabel').textContent='';$('pay').disabled=true;$('localLogout').hidden=true;
 document.querySelectorAll('[data-admin]').forEach(x=>x.hidden=true);await renderCart();
 await new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)));
 await new Promise(resolve=>setTimeout(resolve,1000));if(generation!==employeePromptGeneration)return;
 $('employeeWelcomeGreeting').textContent=employeeGreeting();$('employeeWelcomeBranch').textContent=d.branch.name;$('employeeWelcomeCode').value='';$('employeeWelcomeError').textContent='';$('employeeWelcome').showModal();$('employeeWelcomeCode').focus();
}
$('employeeWelcomeForm').onsubmit=async e=>{e.preventDefault();const submit=$('employeeWelcomeSubmit');if(submit.disabled)return;submit.disabled=true;try{const result=await api('auth/login',{role:'local',stage:'EMPLOYEE',branch_id:employeePromptBranch,employee_code:$('employeeWelcomeCode').value});$('employeeWelcomeCode').value='';auth=result;$('employeeWelcome').close();document.body.classList.remove('branch-preview');await afterLogin()}catch(err){$('employeeWelcomeCode').value='';if(err.restartBranch){document.body.classList.add('locked');openLogin('local');$('loginError').textContent=err.message}else{$('employeeWelcomeError').textContent=err.message;$('employeeWelcomeCode').focus()}}finally{submit.disabled=false}};
$('employeeWelcomeBack').onclick=()=>{document.body.classList.add('locked');openLogin('local')};
$('employeeWelcome').addEventListener('cancel',e=>{e.preventDefault();$('employeeWelcomeBack').click()});

async function loadAccessStatus(){if(auth?.role!=='admin')return;const d=await api('accounting/access-status');$('accessSyncStatus').textContent=d.state+(d.last_success?' · Última confirmación: '+d.last_success:'')+(d.pending?' · Eventos pendientes: '+d.pending:'')+(d.error?' · '+d.error:'')+(d.size_warning?' · '+d.size_warning:'');$('accessSyncPath').textContent='Archivo en PC 1: '+(d.path||'pendiente');$('accessSyncNow').hidden=auth.role!=='admin'}
$('accessSyncNow').onclick=handle(async()=>{await api('admin/access-sync',{});toast('Sincronización de Access solicitada. Espera la confirmación del estado.');await loadAccessStatus()});
setInterval(()=>{if(auth?.role&&!$('accounting').hidden)loadAccessStatus().catch(()=>{})},10000);

document.addEventListener('click',handle(async e=>{const b=e.target.closest('[data-release-employee-session]');if(!b||auth?.role!=='admin')return;if(!confirm('¿Liberar la sesión de este empleado? Tendrá que iniciar sesión otra vez. La caja debe estar cerrada.'))return;await api('admin/employees/'+Number(b.dataset.releaseEmployeeSession)+'/release-session',{});await loadEmployees();toast('Sesión liberada. El empleado ya puede ingresar en otra PC.')}));

document.addEventListener('click',handle(async e=>{const b=e.target.closest('[data-close-copy]');if(!b)return;await printCashClosure(Number(b.dataset.closeCopy),true);await loadPrintJobs()}));

// Ajustes de caja V64.
$('orderName').closest('label').hidden=true;
$('orderName').value='';
$('employeeMeal').closest('label').hidden=true;
const deliveryButtons=document.createElement('div');deliveryButtons.className='delivery-presets';
deliveryButtons.innerHTML=[5,10,20,30,40,50,60,70,80,90,100].map(n=>`<button type="button" data-delivery-add="${n}">L ${n}</button>`).join('')+'<button type="button" data-delivery-reset>Limpiar</button>';
$('deliveryAmount').readOnly=true;$('deliveryAmount').after(deliveryButtons);
let selectedDeliveryAmounts=new Set(),deliveryBaseAmount=0;
const deliverySelections=new Map();
function paintDeliveryAmounts(){
 for(const b of deliveryButtons.querySelectorAll('[data-delivery-add]')){const active=selectedDeliveryAmounts.has(Number(b.dataset.deliveryAdd));b.classList.toggle('active',active);b.setAttribute('aria-pressed',String(active))}
}
function restoreDeliveryAmounts(){
 const value=Number($('deliveryAmount').value||0),saved=deliverySelections.get(value);
 if(saved){selectedDeliveryAmounts=new Set(saved.amounts);deliveryBaseAmount=saved.base}
 else{
  const values=[...deliveryButtons.querySelectorAll('[data-delivery-add]')].map(b=>Number(b.dataset.deliveryAdd)).sort((a,b)=>b-a);
  function find(index,left){if(left===0)return [];if(index===values.length||left<0)return null;const taken=find(index+1,left-values[index]);return taken===null?find(index+1,left):[values[index],...taken]}
  const amounts=find(0,value);selectedDeliveryAmounts=new Set(amounts||[]);deliveryBaseAmount=amounts?0:value;
 }
 paintDeliveryAmounts();
}
deliveryButtons.addEventListener('click',e=>{
 const b=e.target.closest('button');if(!b)return;
 if(b.hasAttribute('data-delivery-reset')){selectedDeliveryAmounts.clear();deliveryBaseAmount=0}
 else{const amount=Number(b.dataset.deliveryAdd);if(!Number.isFinite(amount))return;if(selectedDeliveryAmounts.has(amount))selectedDeliveryAmounts.delete(amount);else selectedDeliveryAmounts.add(amount)}
 const total=deliveryBaseAmount+[...selectedDeliveryAmounts].reduce((sum,n)=>sum+n,0);$('deliveryAmount').value=String(total);
 deliverySelections.set(total,{amounts:[...selectedDeliveryAmounts],base:deliveryBaseAmount});paintDeliveryAmounts();
});
new MutationObserver(()=>{if($('deliveryDialog').open)restoreDeliveryAmounts()}).observe($('deliveryDialog'),{attributes:true,attributeFilter:['open']});
const printerMissing=document.createElement('dialog');printerMissing.id='printerMissing';printerMissing.innerHTML='<h2>FAVOR CONECTAR LA IMPRESORA</h2><div class="row"><button id="retryMissingPrinter" class="primary">REINTENTAR</button><button id="cancelMissingPrinter">CANCELAR</button></div>';document.body.append(printerMissing);
$('cancelMissingPrinter').onclick=()=>printerMissing.close();
$('retryMissingPrinter').onclick=handle(async()=>{await queueCentralCopy('cash',lastReceiptId);printerMissing.close()});
setInterval(async()=>{if(!auth?.role||!lastReceiptId||!$('receipt').open||printerMissing.open)return;try{const jobs=await api('printing/jobs');if(jobs.some(j=>j.role==='cash'&&j.source_id===lastReceiptId&&['FAILED','PAUSED'].includes(j.state)))printerMissing.showModal()}catch{}},3000);

$('receiptCopy').closest('label').hidden=true;
const copyBox=document.createElement('div');copyBox.className='panel';copyBox.innerHTML='<h3>EJEMPLARES EN IMPRESORA DE CAJA</h3><label><select id="cashCopyMode"><option value="false">Solo ORIGINAL</option><option value="true">ORIGINAL y COPIA</option></select></label><button type="button" id="saveCashCopyMode">Guardar ejemplares</button><p id="cashCopySaved" role="status"></p>';
$('printerSetup').before(copyBox);
document.addEventListener('click',handle(async e=>{if(e.target.closest('[data-settings-tab="printer"]')){$('cashCopyMode').value=String((await api('admin/cash-receipt-copy')).copy)}}));
$('saveCashCopyMode').onclick=handle(async()=>{await api('admin/cash-receipt-copy',{copy:$('cashCopyMode').value==='true'});$('cashCopySaved').textContent='Ejemplares guardados para las próximas facturas.'});

// Selector único de acceso a ajustes y contabilidad.
const accessMenu=document.createElement('dialog');accessMenu.id='accessMenu';accessMenu.innerHTML='<h2>SELECCIONA EL ACCESO</h2><div class="row"><button type="button" id="accessSettings">⚙ AJUSTES</button><button type="button" id="accessAccounting">CONTABILIDAD</button><button type="button" id="accessBack">VOLVER</button></div>';document.body.append(accessMenu);
$('loginSwitch').textContent='⚙ AJUSTES';$('loginAccountant').hidden=true;
$('loginSwitch').onclick=()=>{if(!accessMenu.open)accessMenu.showModal()};
$('accessSettings').onclick=()=>{accessMenu.close();openLogin('admin')};
$('accessAccounting').onclick=()=>{accessMenu.close();openLogin('accountant')};
$('accessBack').onclick=()=>accessMenu.close();
const originalOpenAccess=openLogin;openLogin=function(role){originalOpenAccess(role);$('loginSwitch').textContent='⚙ AJUSTES';$('loginAccountant').hidden=true};

// Actualizar este identificador en cada nueva versión publicada.
const APP_VERSION='v.107';
const goalTargetLabel=$('goalForm').elements.target.parentElement;
const goalKindLabel=document.createElement('label');goalKindLabel.innerHTML='TIPO DE META<select name="goal_type" id="goalKind"><option value="SALES">IMPORTE DE VENTAS</option><option value="PRODUCT">UNIDADES DE UN PRODUCTO</option></select>';
const goalProductLabel=document.createElement('label');goalProductLabel.id='goalProductLabel';goalProductLabel.innerHTML='PRODUCTO<select name="product_id" id="goalProduct"></select>';
goalTargetLabel.before(goalKindLabel,goalProductLabel);
$('goalKind').onchange=()=>{$('goalForm').elements.target.value='';updateGoalFormMode()};
$('goalForm').addEventListener('reset',()=>queueMicrotask(updateGoalFormMode));paintGoalProducts();
const companyBenefitOption=document.createElement('label');companyBenefitOption.id='companyBenefitOption';companyBenefitOption.hidden=true;
companyBenefitOption.innerHTML='<span><input type="checkbox" id="applyCompanyBenefit"> APLICAR EXENCIÓN / EXONERACIÓN AUTORIZADA DE LA EMPRESA</span>';
$('customer').append(companyBenefitOption);
const payloadBeforeBenefitOptIn=payload;
payload=function(){return {...payloadBeforeBenefitOptIn(),apply_company_benefit:$('type').value==='RTN'&&$('applyCompanyBenefit').checked}};
function resetCompanyBenefitChoice(){
 $('applyCompanyBenefit').checked=false;companyBenefitOption.hidden=$('type').value!=='RTN';$('companyBenefitNotice').hidden=true;
}
for(const id of ['type','savedCustomer','customerName','rtn'])$(id).addEventListener(id==='customerName'||id==='rtn'?'input':'change',()=>{resetCompanyBenefitChoice();if(cart.length)renderCart()});
$('applyCompanyBenefit').onchange=()=>{if(cart.length)renderCart()};
const resetOrderBeforeBenefitOptIn=resetOrderFields;
resetOrderFields=function(){resetOrderBeforeBenefitOptIn();resetCompanyBenefitChoice()};
const goalOverview=document.createElement('dialog');goalOverview.id='goalOverview';
goalOverview.innerHTML='<h2>METAS DE LA SUCURSAL</h2><div id="goalOverviewRows"></div><div class="row"><button type="button" id="goalOverviewClose">CERRAR</button></div>';
document.body.append(goalOverview);$('goalOverviewClose').onclick=()=>goalOverview.close();
const goalIndicator=document.createElement('button');goalIndicator.id='goalIndicator';goalIndicator.type='button';goalIndicator.textContent='🥳';goalIndicator.hidden=true;
$('hondurasClock').append(goalIndicator);
goalIndicator.onclick=handle(async()=>{await loadGoals();paintGoalOverview();if(!goalOverview.open)goalOverview.showModal()});
// El indicador se oculta inmediatamente al cerrar sesión o cambiar de perfil.
new MutationObserver(updateGoalIndicator).observe(document.body,{attributes:true,attributeFilter:['class']});
// Los medios de pago se muestran aparte del cuadre del efectivo físico.
// Se instala al terminar de cargar las personalizaciones del resumen.
queueMicrotask(()=>{
 const previous=cashSummary;
 cashSummary=function(r){
  const box=document.createElement('div');box.innerHTML=previous(r);
  const section=box.querySelector('.cash-reconciliation');
  if(section){
   const rows=[['VENTAS DE PRODUCTOS DEL TURNO',r.sales||0],['FONDO INICIAL',r.opening],...Object.entries(r.payments).filter(([,n])=>n>0).map(([label,n])=>[label==='Efectivo'?'EFECTIVO COBRADO (+)':label.toLocaleUpperCase('es'),n]),['TOTAL COBRADO',Object.values(r.payments).reduce((a,n)=>a+n,0)]];
   if(r.mixed_total>0)rows.push(['PAGOS MIXTOS (YA INCLUIDOS POR MEDIO)',r.mixed_total]);
   if(r.inputs)rows.push(['OTRAS ENTRADAS DE EFECTIVO (+)',r.inputs]);if(r.outputs)rows.push(['SALIDAS DE EFECTIVO (−)',r.outputs]);
   rows.push(['EFECTIVO QUE DEBE HABER EN CAJA',r.status==='CERRADA'?r.expected:r.live_expected]);
   if(r.status==='CERRADA')rows.push(['EFECTIVO FÍSICO CONTADO',r.counted],[r.difference>0?'SOBRANTE':r.difference<0?'FALTANTE':'DIFERENCIA · CAJA CUADRADA',Math.abs(r.difference)]);
   section.innerHTML='<h3>RESUMEN DE CIERRE</h3>'+rows.map(([label,n])=>'<div class="sum"><span>'+esc(label)+'</span><strong>'+fmt(n)+'</strong></div>').join('');
  }
  if(r.correction){const note=document.createElement('p');note.textContent='CIERRE RECTIFICADO · '+formatCashDate(r.correction.at)+' · '+r.correction.reason;box.append(note)}
  return box.innerHTML;
 };
});
const correctionDialog=document.createElement('dialog');correctionDialog.id='cashCorrectionDialog';
correctionDialog.innerHTML='<h2>RECTIFICAR CIERRE</h2><form id="cashCorrectionForm"><label>CIERRE<select id="correctionShift" required></select></label><p id="correctionInfo"></p><label>EFECTIVO FÍSICO CONTADO CORRECTO (L)<input id="correctionCounted" type="text" inputmode="decimal" required></label><label>MOTIVO<textarea id="correctionReason" minlength="5" maxlength="300" required></textarea></label><label>CÓDIGO DEL AUTENTICADOR DEL ADMINISTRADOR<input id="correctionCode" inputmode="numeric" pattern="[0-9]{6}" maxlength="6" autocomplete="off" required></label><p id="correctionError" role="alert"></p><div class="row"><button type="button" id="correctionCancel">CANCELAR</button><button class="primary" id="correctionSave">GUARDAR RECTIFICACIÓN</button></div></form>';
document.body.append(correctionDialog);
let correctionRows=[];
function showCorrectionInfo(){const r=correctionRows.find(r=>r.id===Number($('correctionShift').value));if(!r)return;$('correctionInfo').textContent='ESPERADO: '+fmt(r.expected)+' · CONTADO REGISTRADO: '+fmt(r.counted);$('correctionCounted').value=(r.counted/100).toFixed(2)}
async function openCashCorrection(preferred){
 $('sessionMenu').hidden=true;correctionRows=await api('cash/corrections?branch_id='+$('branch').value);
 if(preferred&&!correctionRows.some(r=>r.id===preferred.id))correctionRows.unshift(preferred);
 if(!correctionRows.length){toast('No hay cierres guardados para rectificar');return}
 $('correctionShift').innerHTML=correctionRows.map(r=>'<option value="'+r.id+'">'+esc(cashLabel(r)+' · '+formatCashDate(r.closed_at||r.opened_at))+'</option>').join('');
 if(preferred)$('correctionShift').value=preferred.id;
 showCorrectionInfo();$('correctionReason').value='';$('correctionCode').value='';$('correctionError').textContent='';correctionDialog.showModal();
}
$('correctionShift').onchange=showCorrectionInfo;$('correctionCancel').onclick=()=>correctionDialog.close();
$('cashCorrectionForm').onsubmit=async e=>{
 e.preventDefault();const r=correctionRows.find(r=>r.id===Number($('correctionShift').value));if(!r)return;
 $('correctionSave').disabled=true;
 try{const d=await api('cash/'+r.id+'/correct',{counted:$('correctionCounted').value.replace(/,/g,''),previous_counted:r.counted,reason:$('correctionReason').value,code:$('correctionCode').value});cashClosed=d.shift;correctionDialog.close();$('cashEndSummary').innerHTML=cashSummary(cashClosed);$('cashEndForm').hidden=true;$('cashClosedActions').hidden=false;if(!$('cashEndDialog').open)$('cashEndDialog').showModal();toast('CIERRE RECTIFICADO Y REGISTRADO')}
 catch(error){$('correctionError').textContent=error.message}
 finally{$('correctionSave').disabled=false;$('correctionCode').value=''}
};
for(const [parent,id,label] of [[$('cashClosedActions'),'rectifyClosedCash','RECTIFICAR CIERRE'],[$('sessionMenu'),'menuCorrectCash','CORREGIR CIERRE'],[$('cashStatus').parentElement,'panelCorrectCash','RECTIFICAR CIERRE']]){
 const button=document.createElement('button');button.type='button';button.id=id;button.textContent=label;button.onclick=handle(()=>openCashCorrection(id==='rectifyClosedCash'?cashClosed:null));parent.append(button);
}
const startupVersion=document.createElement('small');
startupVersion.id='startupVersion';
startupVersion.textContent=APP_VERSION;
$('login').append(startupVersion);
function syncStartupVersion(){startupVersion.hidden=!!auth?.role||loginRole!=='local'}
new MutationObserver(syncStartupVersion).observe($('loginTitle'),{childList:true,characterData:true,subtree:true});
new MutationObserver(syncStartupVersion).observe($('login'),{attributes:true,attributeFilter:['open']});
syncStartupVersion();

// Apartados de auditoría exclusivos de ajustes.
const accountingAdminNodes=[];
let specialSection=false;
for(const node of Array.from($('accounting').querySelector('.panel').children)){
 if(node.tagName==='H2'&&node.textContent.includes('Registro especial'))specialSection=true;
 if(node.id==='accStats')specialSection=false;
 if(specialSection||['accFiscal','accShifts','accessSyncStatus','accessSyncPath'].includes(node.id)||node.tagName==='DETAILS'||node.tagName==='H2'&&/Autorización|Turnos/.test(node.textContent))accountingAdminNodes.push(node);
}
function hideAccountingAudit(){for(const node of accountingAdminNodes)node.hidden=auth?.role!=='admin'}
new MutationObserver(hideAccountingAudit).observe($('accounting'),{attributes:true,attributeFilter:['hidden']});
hideAccountingAudit();

document.querySelector('aside footer').replaceChildren(document.createTextNode('●'));
document.querySelector('aside footer').style.color='#71ddb0';
const accessStatusBox=$('accessSyncStatus')?.closest('.panel');if(accessStatusBox)accessStatusBox.style.display='none';

const ownerReportBox=document.createElement('section');ownerReportBox.className='panel';ownerReportBox.innerHTML='<h2>REPORTES</h2><div class="row"><select id="ownerReportKind"><option value="ventas">Detalle de ventas por pago</option><option value="productos">Ventas por producto</option><option value="cierre">Cierre de caja</option></select><button id="ownerReportLoad">Consultar</button><button data-owner-export="pdf">PDF</button><button data-owner-export="xlsx">Excel</button><button data-owner-export="print">Imprimir</button></div><p>Se aplican los filtros superiores de sucursal y fechas.</p><div class="scroll" id="ownerReportResult"></div>';
$('accounting').querySelector('.panel').append(ownerReportBox);
function ownerReportParams(){const p=accParams();p.set('status','EMITIDA');return p}
$('ownerReportLoad').onclick=handle(async()=>{const d=await api('accounting/owner-report/'+$('ownerReportKind').value+'?'+ownerReportParams());$('ownerReportResult').innerHTML='<h3>'+esc(d.title)+'</h3><table><thead><tr>'+d.headers.map(x=>'<th>'+esc(x)+'</th>').join('')+'</tr></thead><tbody>'+d.rows.map(r=>'<tr>'+r.map(x=>'<td>'+esc(x)+'</td>').join('')+'</tr>').join('')+'</tbody></table>'});
document.addEventListener('click',e=>{const b=e.target.closest('[data-owner-export]');if(!b)return;const p=ownerReportParams();p.set('format',b.dataset.ownerExport);location.href='/api/accounting/owner-report/'+$('ownerReportKind').value+'?'+p});
new MutationObserver(()=>{const option=$('ownerReportKind').querySelector('[value="cierre"]');option.hidden=auth?.role!=='admin';if(auth?.role!=='admin'&&$('ownerReportKind').value==='cierre')$('ownerReportKind').value='ventas'}).observe($('accounting'),{attributes:true,attributeFilter:['hidden']});

// El valor visible usa miles; el valor enviado conserva el importe decimal.
const openingAmount=$('cashStartForm').elements.opening;
openingAmount.type='text';openingAmount.inputMode='decimal';
openingAmount.addEventListener('focus',formatOpeningAmount);
function formatOpeningAmount(){
 const raw=openingAmount.value.replace(/,/g,'');
 if(!/^\d*(\.\d{0,2})?$/.test(raw))return;
 const before=openingAmount.value.slice(0,openingAmount.selectionStart??0).replace(/,/g,'').length;
 const parts=raw.split('.');
 openingAmount.value=parts[0].replace(/\B(?=(\d{3})+(?!\d))/g,',')+(parts.length>1?'.'+parts[1]:'');
 let position=0,count=0;
 while(position<openingAmount.value.length&&count<before){if(openingAmount.value[position]!==',')count++;position++}
 openingAmount.setSelectionRange(position,position);
}
openingAmount.addEventListener('input',formatOpeningAmount);
openingAmount.addEventListener('blur',()=>{const raw=openingAmount.value.replace(/,/g,'');if(raw&&Number.isFinite(Number(raw)))openingAmount.value=Number(raw).toLocaleString('en-US',{maximumFractionDigits:2});});
$('cashStartForm').addEventListener('submit',event=>{const raw=openingAmount.value.replace(/,/g,'').trim();if(!/^\d+(\.\d{0,2})?$/.test(raw)||Number(raw)>100000000){event.preventDefault();event.stopImmediatePropagation();$('cashStartError').textContent='Ingresa un importe válido con hasta dos decimales.';return}openingAmount.value=raw},true);

$('cashDifference').hidden=true;
for(const node of $('cashEndDialog').querySelectorAll('p,small')){
 if(node.textContent.trim()==='Cuenta únicamente billetes y monedas. No sumes tarjetas ni transferencias.')node.hidden=true;
}

// Presentación del cierre: la caja corresponde a la terminal, el ID sigue siendo del turno.
const originalCashSummary=cashSummary;
cashSummary=function(row){
 const container=document.createElement('div');container.innerHTML=originalCashSummary(row);
 for(const node of container.querySelectorAll('small'))if(node.textContent.includes('Tarjetas y transferencias'))node.remove();
 for(const node of container.querySelectorAll('p')){
  if(node.textContent.startsWith('Consumos sin cobro:')){node.remove();continue}
  if(node.textContent.includes('RESPONSABLE ACTUAL:')){
   node.classList.add('cash-responsible');
   node.innerHTML=node.innerHTML.replace(/\s*\[Empleado #\d+\]/g,'').replace(/(PC \d+)(?: · PC \d+)+/g,'$1');
  }
  const label=node.querySelector('b');
  if(label&&/^CAJA #/.test(label.textContent))label.textContent=cashLabel(row);
 }
 return container.innerHTML;
};
const closeHeading=$('cashEndDialog').querySelector('h2');closeHeading.textContent='CIERRE DE CAJA';closeHeading.classList.add('cash-close-heading');

const cashSummaryBeforeLabels=cashSummary;
cashSummary=function(row){
 const wrapper=document.createElement('div');wrapper.innerHTML=cashSummaryBeforeLabels(row);
 const responsible=wrapper.querySelector('.cash-responsible');
 if(responsible){
  const walker=document.createTreeWalker(responsible,NodeFilter.SHOW_TEXT);const nodes=[];
  while(walker.nextNode())nodes.push(walker.currentNode);
  for(const node of nodes){
   const pattern=/(RESPONSABLE ACTUAL:|Apertura:|Cierre:)/g;
   if(!pattern.test(node.textContent))continue;
   const fragment=document.createDocumentFragment();
   for(const part of node.textContent.split(pattern)){
    if(/^(RESPONSABLE ACTUAL:|Apertura:|Cierre:)$/.test(part)){const label=document.createElement('span');label.className='cash-role-label';label.textContent=part.toUpperCase();fragment.append(label)}
    else fragment.append(document.createTextNode(part));
   }
   node.replaceWith(fragment);
  }
 }
 return wrapper.innerHTML;
};

function lockAccountantDocuments(){
 const limited=auth?.role==='accountant';
 for(const option of $('accScope').options)option.hidden=limited&&option.value!=='fiscal';
 $('accScope').disabled=limited;
 if(limited)$('accScope').value='fiscal';
}
new MutationObserver(lockAccountantDocuments).observe($('accounting'),{attributes:true,attributeFilter:['hidden']});
lockAccountantDocuments();

const purgeTests=document.createElement('section');purgeTests.className='panel';purgeTests.innerHTML='<h3>FACTURAS DE PRUEBA</h3><p>Elimina los comprobantes sin número fiscal y sus comandas. Se crea un respaldo antes de continuar. Los cierres históricos guardados conservan sus importes originales.</p><button type="button" id="deleteTestInvoices">ELIMINAR TODAS LAS FACTURAS DE PRUEBA</button><p id="deleteTestsStatus" role="status"></p>';
$('settingsPanel-general').append(purgeTests);
$('deleteTestInvoices').onclick=handle(async()=>{const confirmation=prompt('Esta acción elimina todas las facturas de prueba de esta instalación. Escribe ELIMINAR PRUEBAS para confirmar:');if(confirmation!=='ELIMINAR PRUEBAS')return;$('deleteTestInvoices').disabled=true;try{const r=await api('admin/delete-test-invoices',{confirmation});$('deleteTestsStatus').textContent=r.count+' FACTURAS DE PRUEBA ELIMINADAS. RESPALDO GUARDADO.';cart=[];await renderCart()}finally{$('deleteTestInvoices').disabled=false}});

function confirmCashCount(value,expected){
 const counted=Math.round(Number(String(value).replace(/,/g,''))*100);
 if(!Number.isFinite(counted)||counted<0){toast('Ingresa un monto válido');return false}
 return confirm('REVISA EL CIERRE\nEFECTIVO ESPERADO: '+fmt(expected)+'\nEFECTIVO CONTADO: '+fmt(counted)+'\nDIFERENCIA: '+fmt(counted-expected)+'\n¿CONFIRMAS ESTOS IMPORTES?');
}
const summaryBeforeSales=cashSummary;
cashSummary=function(row){
 const content=document.createElement('div');content.innerHTML=summaryBeforeSales(row);
 const heading=content.querySelector('.cash-reconciliation h3');
 if(heading){const sales=document.createElement('div');sales.className='sum';sales.innerHTML='<span>VENTAS DE PRODUCTOS DEL TURNO</span><strong>'+fmt(row.sales||0)+'</strong>';heading.before(sales)}
 return content.innerHTML;
};
const countedField=$('cashCounted');countedField.type='text';countedField.inputMode='decimal';
countedField.addEventListener('input',()=>{const raw=countedField.value.replace(/,/g,'');if(!/^\d*(\.\d{0,2})?$/.test(raw))return;const parts=raw.split('.');countedField.value=parts[0].replace(/\B(?=(\d{3})+(?!\d))/g,',')+(parts.length>1?'.'+parts[1]:'')});
$('cashEndForm').addEventListener('submit',()=>{countedField.value=countedField.value.replace(/,/g,'')},true);

const resetSalesPanel=document.createElement('section');resetSalesPanel.className='panel';resetSalesPanel.innerHTML='<h3>RESET DE VENTAS</h3><p>Elimina todas las facturas de venta, incluidas las fiscales, y sus comandas. Crea un respaldo previo. Los correlativos y los cierres históricos se conservan.</p><button type="button" id="resetAllSales" style="background:#b5242c;color:white;font-weight:900">RESET TODAS LAS VENTAS</button><p id="resetSalesStatus" role="status"></p>';
$('settingsPanel-general').append(resetSalesPanel);
$('resetAllSales').onclick=handle(async()=>{const confirmation=prompt('Se eliminarán TODAS las ventas, incluidas las facturas fiscales. Escribe RESET TODAS LAS VENTAS para confirmar:');if(confirmation!=='RESET TODAS LAS VENTAS')return;$('resetAllSales').disabled=true;try{const r=await api('admin/reset-sales',{confirmation});cart=[];await renderCart();$('resetSalesStatus').textContent=r.count+' VENTAS ELIMINADAS. RESPALDO GUARDADO.'}finally{$('resetAllSales').disabled=false}});

// Solo facturación fiscal disponible.
purgeTests.remove();
$('accScope').innerHTML='<option value="fiscal">FACTURAS FISCALES CON CAI</option>';
$('accScope').value='fiscal';$('accScope').disabled=true;
const fiscalEnabled=$('fiscalForm').elements.enabled;
if(fiscalEnabled){fiscalEnabled.closest('label').hidden=true;$('fiscalForm').addEventListener('submit',()=>{fiscalEnabled.checked=true},true)}

// Catálogo oficial de WooCommerce y categorías elegidas por ajustes.
const wooTab=document.createElement('button');wooTab.type='button';wooTab.textContent='WOOCOMMERCE';wooTab.dataset.settingsTab='woocommerce';wooTab.id='settingsTab-woocommerce';wooTab.setAttribute('role','tab');wooTab.setAttribute('aria-controls','settingsPanel-woocommerce');
document.querySelector('.settings-tabs').append(wooTab);
const wooPanel=document.createElement('div');wooPanel.id='settingsPanel-woocommerce';wooPanel.className='settings-section';wooPanel.hidden=true;wooPanel.setAttribute('role','tabpanel');
wooPanel.innerHTML='<h2>CATÁLOGO WOOCOMMERCE</h2><form id="wooForm" class="stack"><label>Dirección de la tienda HTTPS<input name="url" type="url" placeholder="https://frychickenhn.com" required></label><label>Consumer key<input name="key" type="password" autocomplete="new-password" placeholder="ck_… · vacío para conservar"></label><label>Consumer secret<input name="secret" type="password" autocomplete="new-password" placeholder="cs_… · vacío para conservar"></label><label><span><input name="enabled" type="checkbox"> SINCRONIZAR AUTOMÁTICAMENTE CADA 5 MINUTOS</span></label><label>Impuestos por clase de WooCommerce (JSON)<textarea name="tax_map" rows="3">{"":"15"}</textarea></label><small>La clave vacía representa la clase estándar. Ejemplo: {"":"15","tasa-18":"18"}. Los precios se toman tal como aparecen en WooCommerce. Configura en Facturación y CAI si incluyen ISV.</small><div class="row"><button class="primary">GUARDAR CONEXIÓN Y SELECCIÓN</button><button type="button" id="wooGetCategories">CONSULTAR CATEGORÍAS</button><button type="button" id="wooSync">SINCRONIZAR AHORA</button></div><h3>CATEGORÍAS VISIBLES</h3><p>Marca las categorías que deseas vender y guarda la selección. Si un producto tiene varias, se usa la primera seleccionada según el orden de la tienda.</p><div id="wooCategories" class="exclusion-products"></div><p id="wooStatus" role="status"></p></form>';
document.querySelector('.settings-shell').append(wooPanel);
let wooCategoryCache=[],wooSelected=[];
function paintWooCategories(){ $('wooCategories').innerHTML=wooCategoryCache.map(c=>'<label class="exclusion-product"><input type="checkbox" value="'+c.id+'" '+(wooSelected.includes(c.id)?'checked':'')+'><span>'+esc(c.name)+'</span></label>').join('') }
async function loadWoo(){const d=await api('admin/woocommerce');const form=$('wooForm');form.elements.url.value=d.url||'';form.elements.enabled.checked=!!d.enabled;form.elements.tax_map.value=JSON.stringify(d.tax_map||{'':'15'});wooSelected=d.categories||[];wooCategoryCache=d.category_cache||[];paintWooCategories();$('wooStatus').textContent=(d.last_success?'ÚLTIMA SINCRONIZACIÓN: '+new Date(d.last_success).toLocaleString('es-HN')+' · '+d.count+' PRODUCTOS':'CONEXIÓN PENDIENTE')+(d.error?' · '+d.error:'')}
wooTab.addEventListener('click',handle(async()=>{selectSettingsTab('woocommerce');await loadWoo();await pollWooProgress()}));
const wooBottom=document.createElement('div');wooBottom.className='woo-save-area';wooBottom.innerHTML='<button type="submit" class="primary" id="wooSave">GUARDAR</button><strong id="wooSaved" role="status"></strong><progress id="wooProgress" max="100" value="0" hidden></progress><p id="wooProgressDetail" role="status"></p>';
$('wooCategories').after(wooBottom);wooBottom.append($('wooStatus'));
let wooFinishedSeen='',wooWasRunning=false,wooPolling=false;
async function pollWooProgress(){
 if(auth?.role!=='admin'||wooPolling)return;
 wooPolling=true;
 try{
  const d=await api('admin/woocommerce/progress');
  $('wooSync').disabled=!!d.running;
  $('wooProgress').hidden=!d.running&&!d.finished_at;
  if(d.total){$('wooProgress').max=d.total;$('wooProgress').value=d.processed}else $('wooProgress').removeAttribute('value');
  if(d.running){wooWasRunning=true;$('wooProgressDetail').textContent=d.phase+' · '+d.processed+' / '+d.total+' PRODUCTOS REVISADOS · '+d.images+' IMÁGENES DESCARGADAS';}
  else if(d.finished_at){
   $('wooProgressDetail').textContent=d.error?'ERROR: '+d.error:'DESCARGA COMPLETA: '+(d.count||0)+' PRODUCTOS · '+d.images+' IMÁGENES DESCARGADAS · '+(d.skipped||0)+' OMITIDOS';
   if(d.image_errors?.length)$('wooProgressDetail').textContent+=' · IMÁGENES PENDIENTES: '+d.image_errors.length+' · '+d.image_errors.slice(0,3).join(' | ');
   if(d.image_errors?.length)$('wooProgressDetail').textContent+=' · IMÁGENES PENDIENTES: '+d.image_errors.length+' · '+d.image_errors.slice(0,3).join(' | ');
   if(wooFinishedSeen!==d.finished_at){wooFinishedSeen=d.finished_at;if(!d.error){await loadProducts();if(cart.length)await renderCart();if(wooWasRunning)toast('CATÁLOGO ACTUALIZADO CORRECTAMENTE')}wooWasRunning=false;}
  }
 }finally{wooPolling=false}
}
async function startWooDownload(){
 const d=await api('admin/woocommerce/sync',{});wooWasRunning=true;
 $('wooProgressDetail').textContent=d.started?'DESCARGA INICIADA. PUEDES SEGUIR UTILIZANDO EL SISTEMA.':'LA DESCARGA SIGUE EN CURSO.';
 await pollWooProgress();
}
$('wooForm').onsubmit=handle(async e=>{
 e.preventDefault();const form=e.target;let taxMap;
 try{taxMap=JSON.parse(form.elements.tax_map.value)}catch{throw Error('El mapa de impuestos debe ser JSON válido')}
 const categories=[...$('wooCategories').querySelectorAll('input:checked')].map(x=>Number(x.value));
 $('wooSave').disabled=true;$('wooSaved').textContent='GUARDANDO…';
 try{
  await api('admin/woocommerce',{url:form.elements.url.value,key:form.elements.key.value,secret:form.elements.secret.value,enabled:form.elements.enabled.checked,categories,tax_map:taxMap});
  form.elements.key.value='';form.elements.secret.value='';wooSelected=categories;
  $('wooSaved').textContent='GUARDADO CORRECTAMENTE';toast('CATEGORÍAS Y CONEXIÓN GUARDADAS');
  if(categories.length&&form.elements.enabled.checked)await startWooDownload();
  else $('wooProgressDetail').textContent=categories.length?'ACTIVA LA SINCRONIZACIÓN PARA DESCARGAR LOS PRODUCTOS.':'CONSULTA Y SELECCIONA LAS CATEGORÍAS, LUEGO PRESIONA GUARDAR.';
 }catch(error){$('wooSaved').textContent='NO SE PUDO COMPLETAR: '+error.message;throw error}
 finally{$('wooSave').disabled=false}
});
$('wooGetCategories').onclick=handle(async()=>{wooSelected=[...$('wooCategories').querySelectorAll('input:checked')].map(x=>Number(x.value));const d=await api('admin/woocommerce/categories');wooCategoryCache=d.categories;paintWooCategories();$('wooSaved').textContent='SELECCIONA LAS CATEGORÍAS Y PRESIONA GUARDAR';});
$('wooSync').onclick=handle(startWooDownload);
$('wooCategories').addEventListener('change',()=>{$('wooSaved').textContent='CAMBIOS PENDIENTES: PRESIONA GUARDAR'});
setInterval(()=>{if(auth?.role==='admin')pollWooProgress().catch(()=>{})},1500);
$('productForm').hidden=true;$('importProducts').hidden=true;
document.querySelector('#products .panel>p').textContent='PRODUCTOS, PRECIOS E IMÁGENES SINCRONIZADOS DESDE WOOCOMMERCE. CONFIGURA LA CONEXIÓN Y LAS CATEGORÍAS EN AJUSTES → WOOCOMMERCE.';
const renderWooProducts=renderProducts;renderProducts=function(){renderWooProducts();for(const button of $('productRows').querySelectorAll('button')){button.disabled=true;button.style.cursor='default'}if(!products.length)$('catalog').innerHTML='<p>CATÁLOGO PENDIENTE. CONFIGURA WOOCOMMERCE Y SINCRONIZA LAS CATEGORÍAS DESDE AJUSTES.</p>'};
setInterval(()=>{if(auth?.role&&auth.role!=='accountant')loadProducts().then(()=>{if(cart.length)return renderCart()}).catch(()=>{})},60000);
