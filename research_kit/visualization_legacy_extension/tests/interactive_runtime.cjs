// Execute the real embedded JavaScript in an instrumented DOM; no browser/network.
const fs=require('fs'),vm=require('vm'),assert=require('assert'),crypto=require('crypto').webcrypto;
async function main(){
 const h=fs.readFileSync(process.argv[2],'utf8'),svg=h.match(/<svg[\s\S]*?<\/svg>/)[0];
 const state={search:{value:''},group:{value:''},clear:{},download:{},status:{},saved:[]};
 const make=(id,g)=>({dataset:{object:id,group:g},classes:new Set(),attrs:{},handlers:{},classList:{toggle(k,v){if(v)this.owner.classes.add(k);else this.owner.classes.delete(k);}},setAttribute(k,v){this.attrs[k]=v;},removeAttribute(k){delete this.attrs[k];},addEventListener(k,v){this.handlers[k]=v;}});
 const nodes=[...svg.matchAll(/<g data-object="([^"]+)" data-group="([^"]+)"/g)].map(m=>{let n=make(m[1],m[2]);n.classList.owner=n;return n;});
 const selectors={'#search':state.search,'#group':state.group,'#clear':state.clear,'#download':state.download,'#status':state.status};
 for(const x of [state.search,state.group])x.addEventListener=(k,v)=>x[k]=v;
 let serial='';const blobs=new Map();let counter=0;
 const document={querySelectorAll:()=>nodes,querySelector:q=>q==='svg'?{cloneNode(){serial=svg.replace(/<g data-object="([^"]+)" data-group="([^"]+)"/g,(match,id,g)=>match+' class="'+[...nodes.find(n=>n.dataset.object===id&&n.dataset.group===g).classes].join(' ')+'"');return {querySelectorAll:()=>nodes.map(n=>({...n,removeAttribute(){}}))};}}:selectors[q],createElement:()=>({click(){state.saved.push({name:this.download,blob:blobs.get(this.href)});}})};
 const sandbox={document,Blob,TextEncoder,Uint8Array,crypto,XMLSerializer:class{serializeToString(){return serial;}},URL:{createObjectURL:b=>{let u='blob:'+counter++;blobs.set(u,b);return u;},revokeObjectURL:()=>{}},setTimeout:()=>0};
 vm.runInNewContext(h.match(/<script>([\s\S]*?)<\/script>/)[1],sandbox,{timeout:1000});
 assert(nodes.length>0);const first=nodes[0],second=nodes.find(n=>n.dataset.object!==first.dataset.object);
 first.handlers.click();assert(nodes.filter(n=>n.dataset.object===first.dataset.object).every(n=>n.classes.has('selected')));
 second.handlers.keydown({key:'Enter',preventDefault(){}});assert(second.attrs['aria-pressed']==='true');
 state.search.value='Cell_00';state.search.input();state.group.value=first.dataset.group;state.group.change();
 await state.download.onclick();assert(state.saved.length===2);const scope=JSON.parse(await state.saved[1].blob.text());
 assert.deepEqual([...scope.selected_ids].sort(),[first.dataset.object,second.dataset.object].sort());
 assert(scope.matching_ids.length>0&&scope.matching_ids.length<scope.all_ids.length);assert(scope.coordinates_and_scales_changed===false);
 const exported=await state.saved[0].blob.text();assert(exported.includes('class="selected"'));assert(exported.includes('class="dim'));
 assert(scope.svg_sha256===require('crypto').createHash('sha256').update(exported).digest('hex'));
 state.clear.onclick();assert(nodes.every(n=>!n.classes.has('selected')));
 console.log(JSON.stringify({state:'EMBEDDED_JS_DOM_BEHAVIOR_PASS',object_instances:nodes.length,selection_sync:true,keyboard_toggle:true,scope_svg_hash_matched:true,filters_tested:true,real_browser_download_tested:false}));
}
main().catch(e=>{console.error(e);process.exitCode=1;});
