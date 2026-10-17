// "Send to Off the Clock": a bookmarklet (a bookmark whose address is a little script). You tap it while a
// Bunnings product page is open in YOUR browser, with your store chosen; it reads the product details that
// page already loaded - including your store's price and stock, which the app itself can't see (plants are
// sold regionally) - and opens Off the Clock's Supplies page with them in the address (after #, so they
// never leave your devices). Nothing is fetched from Bunnings by it; the app saves only when you press Save.
//
// Where the details are: Bunnings' pages are Next.js - the product is in the page props' dehydratedState
// queries ("retail-product", "product-retail-price" for the store, "product-fulfilment" for its stock,
// "product-aisle-item-location" for its aisle and bay). After
// moving around their site without reloading, the first page's __NEXT_DATA__ is stale, so the router's
// current props are read first, then the page's __NEXT_DATA__ (the global - but an element with that id is
// also a global, so only if it holds data - or its script tag); the product's
// item number must match the address, else: reload and retry.

// The script, readable. `app` = this app's address as the browser that copies the button sees it.
export function buttonScript(app) {
  return `(function(){
var A=${JSON.stringify(app)};
function fail(m){alert('Off the Clock: '+m);}
try{
var m=location.href.match(/_p(\\d{4,10})/);
if(location.hostname.indexOf('bunnings.com.au')<0||!m){fail('open a Bunnings product page first, then tap this.');return;}
var r=window.next&&window.next.router,c=r&&r.components&&r.components[r.route];
var w=window.__NEXT_DATA__,el=document.getElementById('__NEXT_DATA__'),nd=(w&&w.props)?w:(el&&el.textContent?JSON.parse(el.textContent):null);
var pp=(c&&c.props&&c.props.pageProps&&c.props.pageProps.dehydratedState&&c.props.pageProps)||(nd&&nd.props&&nd.props.pageProps)||{};
var q=(pp.dehydratedState&&pp.dehydratedState.queries)||[];
function g(k){for(var i=0;i<q.length;i++){if(q[i].queryKey&&q[i].queryKey[0]===k)return q[i];}return null;}
var P=g('retail-product'),R=g('product-retail-price'),F=g('product-fulfilment'),L=g('product-aisle-item-location');
var p=P&&P.state&&P.state.data;
if(!p||String(p.itemNumber)!==m[1]){fail('this page changed since it loaded - reload it, then tap again.');return;}
var pr=(R&&R.state&&R.state.data)||{},fu=(F&&F.state&&F.state.data)||{};
var u=(pp.initialState&&pp.initialState.global&&pp.initialState.global.userData)||{},st=u.appliedStore||{};
var code=(R&&R.queryKey&&R.queryKey[2])||st.name||'';
var im=(p.images||[]),img=im.filter(function(i){return i.imageType==='PRIMARY';})[0]||im[0]||{};
var ip=fu.inStorePickUpData||{},ld=(L&&L.state&&L.state.data)||[],wh=[];
(Array.isArray(ld)?ld:[ld]).forEach(function(x){((x&&x.inStoreLocations)||[]).forEach(function(s){wh.push({aisle:s.aisle,bay:s.bay});});});
var d={v:1,url:location.origin+location.pathname,item:String(p.itemNumber),name:p.name,brand:p.manufacturer,
rating:p.averageRating,reviews:p.numberOfReviews,weight:p.weight,
categories:(p.allCategories||[]).map(function(x){return x.displayName;}),
description:((p.feature||{}).description||'').slice(0,1500),how_to:(p.installationInformation||'').slice(0,2000),
image:img.url||img.thumbnailUrl||'',price:pr.priceAvailable?pr.value:null,store_code:String(code),
store_name:String(st.name)===String(code)?st.displayName:'',
stock:{in_store:fu.availableInStore,color:ip.inStoreStockColor,msg:ip.inStoreStockMsg},where:wh.slice(0,3)};
window.open(A+'/gardening/supplies#bunnings='+encodeURIComponent(JSON.stringify(d)),'_blank');
}catch(e){fail('couldn\\'t read this page ('+e.message+').');}
})()`
}

// The bookmark's address: javascript: + the script on one line, %-encoded so any browser keeps it intact.
export const buttonHref = (app) => `javascript:${encodeURIComponent(buttonScript(app).replace(/\n/g, ''))}`

// What the button put after # on the Supplies page, or null.
export function readSent(hash) {
  const m = /^#bunnings=(.+)$/.exec(hash || '')
  if (!m) return null
  try {
    const d = JSON.parse(decodeURIComponent(m[1]))
    return d && typeof d === 'object' && d.v === 1 ? d : null
  } catch {
    return null
  }
}
