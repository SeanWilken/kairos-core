import { useState, useEffect } from "react";

const S = `
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&family=Bricolage+Grotesque:wght@500;600;700&display=swap');
*{box-sizing:border-box;margin:0;padding:0;}
:root{
  --bg:#0b0b10;--s1:#101018;--s2:#16161f;--s3:rgba(255,255,255,.03);
  --bdr:rgba(255,255,255,.07);--bdr2:rgba(255,255,255,.14);
  --t:#e4e4e7;--tm:#71717a;--td:#3f3f46;
  --a:#f59e0b;--a2:#fb923c;
  --ok:#4ade80;--err:#f87171;--warn:#fbbf24;--info:#7dd3fc;
  --mono:'IBM Plex Mono',monospace;--head:'Bricolage Grotesque',sans-serif;
}
.w{font-family:var(--mono);color:var(--t);background:var(--bg);}
.inp{width:100%;background:rgba(255,255,255,.04);border:1px solid var(--bdr);border-radius:6px;
  padding:9px 12px;color:var(--t);font-family:var(--mono);font-size:13px;
  outline:none;transition:border-color .18s,box-shadow .18s;-webkit-appearance:none;}
.inp:focus{border-color:var(--a);box-shadow:0 0 0 3px rgba(245,158,11,.1);}
.inp::placeholder{color:var(--td);}
.inp option{background:#16161f;}
.lbl{display:block;font-size:10px;font-weight:500;color:var(--td);
  margin-bottom:5px;letter-spacing:.08em;text-transform:uppercase;}
.card{background:var(--s3);border:1px solid var(--bdr);border-radius:9px;padding:16px;}
.tog{width:36px;height:19px;border-radius:10px;background:rgba(255,255,255,.1);
  cursor:pointer;position:relative;transition:background .18s;flex-shrink:0;}
.tog.on{background:var(--a);}
.tog::after{content:'';width:13px;height:13px;border-radius:50%;background:#fff;
  position:absolute;top:3px;left:3px;transition:left .18s;}
.tog.on::after{left:20px;}
.tag{display:inline-flex;align-items:center;gap:4px;padding:2px 8px;
  background:rgba(245,158,11,.08);border:1px solid rgba(245,158,11,.2);
  border-radius:4px;color:var(--a);font-size:11px;}
.tag-x{background:none;border:none;color:rgba(245,158,11,.5);cursor:pointer;
  font-size:12px;line-height:1;padding:0;}
.tag-x:hover{color:var(--a);}
.btn-a{display:inline-flex;align-items:center;gap:7px;padding:9px 18px;border-radius:6px;
  background:var(--a);color:#0b0b10;font-family:var(--mono);font-size:13px;font-weight:600;
  cursor:pointer;border:none;transition:all .18s;}
.btn-a:hover{background:#fbbf24;transform:translateY(-1px);box-shadow:0 6px 16px rgba(245,158,11,.3);}
.btn-a:disabled{opacity:.35;cursor:not-allowed;transform:none;box-shadow:none;}
.btn-g{display:inline-flex;align-items:center;gap:7px;padding:9px 18px;border-radius:6px;
  background:rgba(255,255,255,.05);border:1px solid var(--bdr);
  color:var(--tm);font-family:var(--mono);font-size:13px;
  cursor:pointer;transition:all .18s;}
.btn-g:hover{background:rgba(255,255,255,.09);color:var(--t);border-color:var(--bdr2);}
.btn-g:disabled{opacity:.3;cursor:not-allowed;}
.chip{padding:5px 12px;border-radius:4px;border:1px solid var(--bdr);
  background:rgba(255,255,255,.03);color:var(--tm);font-size:12px;
  cursor:pointer;transition:all .15s;font-family:var(--mono);}
.chip:hover{border-color:rgba(245,158,11,.35);color:var(--t);}
.chip.sel{border-color:var(--a);background:rgba(245,158,11,.08);color:var(--a);}
.cbox{display:flex;align-items:flex-start;gap:10px;padding:10px 14px;border-radius:7px;
  border:1px solid var(--bdr);background:rgba(255,255,255,.02);
  cursor:pointer;transition:border-color .15s;}
.cbox:hover{border-color:var(--bdr2);}
.cbox.on{border-color:rgba(245,158,11,.3);background:rgba(245,158,11,.04);}
.cbox-sq{width:15px;height:15px;border-radius:3px;flex-shrink:0;margin-top:1px;
  border:1px solid var(--bdr2);background:rgba(255,255,255,.05);
  display:flex;align-items:center;justify-content:center;font-size:9px;
  color:#0b0b10;transition:all .15s;}
.cbox.on .cbox-sq{background:var(--a);border-color:var(--a);}
.divider{height:1px;background:var(--bdr);margin:16px 0;}
.sec{font-size:10px;font-weight:600;color:var(--td);letter-spacing:.09em;text-transform:uppercase;margin-bottom:10px;}
.g2{display:grid;grid-template-columns:1fr 1fr;gap:12px;}
.g3{display:grid;grid-template-columns:1fr 1fr 1fr;gap:10px;}
.scr::-webkit-scrollbar{width:3px;}
.scr::-webkit-scrollbar-track{background:transparent;}
.scr::-webkit-scrollbar-thumb{background:rgba(255,255,255,.07);border-radius:2px;}
.dot{width:7px;height:7px;border-radius:50%;flex-shrink:0;}
.dot.ok{background:var(--ok);box-shadow:0 0 5px rgba(74,222,128,.4);}
.dot.warn{background:var(--warn);box-shadow:0 0 5px rgba(251,191,36,.4);}
.dot.fail{background:var(--err);box-shadow:0 0 5px rgba(248,113,113,.4);}
.dot.skip{background:var(--td);}
.dot.run{background:var(--a);animation:blink .7s infinite;}
.dot.pend{background:var(--td);opacity:.4;}
.badge{display:inline-flex;padding:1px 7px;border-radius:3px;font-size:10px;}
.badge.ok{background:rgba(74,222,128,.1);color:var(--ok);border:1px solid rgba(74,222,128,.18);}
.badge.warn{background:rgba(251,191,36,.1);color:var(--warn);border:1px solid rgba(251,191,36,.18);}
.badge.fail{background:rgba(248,113,113,.1);color:var(--err);border:1px solid rgba(248,113,113,.18);}
.badge.info{background:rgba(245,158,11,.1);color:var(--a);border:1px solid rgba(245,158,11,.18);}
.badge.skip{background:rgba(255,255,255,.05);color:var(--tm);border:1px solid var(--bdr);}
.ftab{padding:5px 12px;border-radius:4px 4px 0 0;font-size:11px;cursor:pointer;
  border:1px solid transparent;color:var(--tm);transition:all .15s;font-family:var(--mono);}
.ftab:hover{color:var(--t);}
.ftab.act{background:rgba(0,0,0,.6);border-color:var(--bdr);border-bottom-color:rgba(0,0,0,.6);color:var(--a);}
.code{background:rgba(0,0,0,.55);border:1px solid var(--bdr);border-radius:7px;padding:14px;
  font-family:var(--mono);font-size:11px;line-height:1.8;color:var(--tm);
  overflow:auto;white-space:pre;}
.warn-box{background:rgba(245,158,11,.06);border:1px solid rgba(245,158,11,.2);
  border-radius:7px;padding:12px 14px;font-size:12px;color:var(--a);line-height:1.5;}
.info-box{background:rgba(125,211,252,.05);border:1px solid rgba(125,211,252,.15);
  border-radius:7px;padding:12px 14px;font-size:12px;color:var(--info);line-height:1.5;}
.ok-box{background:rgba(74,222,128,.05);border:1px solid rgba(74,222,128,.15);
  border-radius:7px;padding:14px 18px;}
@keyframes blink{0%,100%{opacity:1}50%{opacity:.3}}
@keyframes fadeUp{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:translateY(0)}}
.fu{animation:fadeUp .25s ease both;}
@keyframes spin{to{transform:rotate(360deg)}}
.spin{animation:spin .6s linear infinite;display:inline-block;}
`;

const STEPS = [
  {n:'01',s:'Runtime',label:'Runtime Selection'},
  {n:'02',s:'Deploy',label:'Deployment Target'},
  {n:'03',s:'Secrets',label:'Secrets Strategy'},
  {n:'04',s:'RAG',label:'Vector Store'},
  {n:'05',s:'Preflight',label:'Preflight Validation'},
  {n:'06',s:'Artifacts',label:'Artifact Generation'},
  {n:'07',s:'Runtime',label:'Runtime Verify + Docs'},
  {n:'08',s:'Review',label:'Review & Complete'},
];

const API_PROVIDERS = ['openai','anthropic','google','azure_openai','custom'];
const LOCAL_PROVIDERS = ['ollama','lmstudio','custom'];
const INFRA = [
  {id:'core_api',label:'core_api',desc:'Primary application server',required:true},
  {id:'postgres',label:'postgres',desc:'Relational database'},
  {id:'pgvector',label:'pgvector',desc:'Vector extension (requires postgres)'},
  {id:'local_model_runtime',label:'local_model_runtime',desc:'Ollama / LM Studio runtime host'},
  {id:'reverse_proxy',label:'reverse_proxy',desc:'Nginx / Caddy routing layer'},
];

const TARGET_CAPABILITIES = {
  docker_local: {
    maturity: 'mvp',
    tested: true,
    allowed_execution_modes: ['generate_only', 'attempt_automated'],
    artifact_types: ['.env.template', 'docker-compose.yml', 'nginx.conf', 'bootstrap-report.json'],
    disclaimer: 'Docker local is validated end-to-end for the bootstrap baseline.'
  },
  github_actions: {
    maturity: 'experimental',
    tested: false,
    allowed_execution_modes: ['generate_only'],
    artifact_types: ['.env.template', 'github-actions-snippet.yml', 'bootstrap-report.json'],
    disclaimer: 'Generated workflow snippets are experimental and not runtime-certified yet.'
  },
  k8s: {
    maturity: 'experimental',
    tested: false,
    allowed_execution_modes: ['generate_only'],
    artifact_types: ['.env.template', 'k8s-manifests.yaml', 'bootstrap-report.json'],
    disclaimer: 'Generated manifests are experimental and should be reviewed before use.'
  },
  terraform: {
    maturity: 'experimental',
    tested: false,
    allowed_execution_modes: ['generate_only'],
    artifact_types: ['.env.template', 'terraform.tfvars.example', 'bootstrap-report.json'],
    disclaimer: 'Generated Terraform templates are experimental and intended as starting points.'
  }
};

const INIT = {
  tenant_name:'',tenant_type:'company',
  model_modes:['api_provider'],
  connections:[{mode:'api_provider',provider:'openai',endpoint:'https://api.openai.com/v1',model_ref:'gpt-4o-mini',priority:1}],
  deployment_target:'docker_local',execution_mode:'generate_only',
  infra_components:['core_api'],
  secrets_mode:'template_only',storage_target:'env_file',required_keys:[],
  vector_store_mode:'disabled',vector_provider:'pgvector',
  namespace_pattern:'',index_strategy:'flat',vector_endpoint:'',
  check_status:'idle',check_results:[],
  artifacts_applied:false,
  runtime_check_results:[],runtime_check_status:'idle',
  ingest_now:false,doc_files:[],chunking_profile:'recursive_512',embedding_profile:'default',ingest_status:'idle',
  gen_status:'idle',artifacts:[],
  confirmed:false,
};

// ─── Helpers ──────────────────────────────────────────────────────────────────

function Toggle({on,set}){return <div className={`tog${on?' on':''}`} onClick={()=>set(!on)}/>;}
function Field({label,children,style}){return <div style={style}><label className="lbl">{label}</label>{children}</div>;}

function TagInput({values,onChange,placeholder}){
  const [v,sv]=useState('');
  const add=()=>{const t=v.trim();if(t&&!values.includes(t)){onChange([...values,t]);sv('');}};
  return(
    <div>
      {values.length>0&&<div style={{display:'flex',flexWrap:'wrap',gap:5,marginBottom:7}}>
        {values.map(x=><span key={x} className="tag">{x}<button className="tag-x" onClick={()=>onChange(values.filter(i=>i!==x))}>×</button></span>)}
      </div>}
      <div style={{display:'flex',gap:7}}>
        <input className="inp" value={v} onChange={e=>sv(e.target.value)}
          onKeyDown={e=>{if(e.key==='Enter'){e.preventDefault();add();}}}
          placeholder={placeholder||'Type and press Enter'}/>
        <button className="btn-g" style={{padding:'8px 12px',flexShrink:0}} onClick={add}>+</button>
      </div>
    </div>
  );
}

function Cbox({checked,onToggle,label,desc,disabled}){
  return(
    <div className={`cbox${checked?' on':''}`} onClick={()=>!disabled&&onToggle()} style={disabled?{opacity:.5,cursor:'not-allowed'}:{}}>
      <div className="cbox-sq">{checked&&'✓'}</div>
      <div>
        <div style={{fontSize:12,fontWeight:500,fontFamily:'var(--mono)'}}>{label}</div>
        {desc&&<div style={{fontSize:11,color:'var(--tm)',marginTop:2}}>{desc}</div>}
      </div>
      {disabled&&<span className="badge info" style={{marginLeft:'auto',alignSelf:'flex-start',flexShrink:0}}>locked</span>}
    </div>
  );
}

// ─── Step 1: Runtime ──────────────────────────────────────────────────────────

function Step1({d,u}){
  const f=(k,v)=>u({...d,[k]:v});
  const togMode=m=>{
    const n=d.model_modes.includes(m)?d.model_modes.filter(x=>x!==m):[...d.model_modes,m];
    if(n.length===0)return;
    f('model_modes',n);
  };
  const addConn=mode=>{
    const n=[...d.connections,{mode,provider:mode==='api_provider'?'openai':'ollama',endpoint:mode==='api_provider'?'https://api.openai.com/v1':'http://localhost:11434',model_ref:'',priority:d.connections.length+1}];
    f('connections',n);
  };
  const updConn=(i,k,v)=>{const n=[...d.connections];n[i]={...n[i],[k]:v};f('connections',n);};
  const delConn=i=>f('connections',d.connections.filter((_,j)=>j!==i));
  return(
    <div className="fu" style={{display:'flex',flexDirection:'column',gap:18}}>
      <div className="g2">
        <Field label="Tenant Name"><input className="inp" value={d.tenant_name} onChange={e=>f('tenant_name',e.target.value)} placeholder="my-ai-system"/></Field>
        <Field label="Tenant Type">
          <select className="inp" value={d.tenant_type} onChange={e=>f('tenant_type',e.target.value)}>
            <option value="company">company</option><option value="individual">individual</option>
          </select>
        </Field>
      </div>
      <div>
        <label className="lbl">Model Modes (select all that apply)</label>
        <div style={{display:'flex',gap:8}}>
          {['api_provider','local_model'].map(m=><span key={m} className={`chip${d.model_modes.includes(m)?' sel':''}`} onClick={()=>togMode(m)}>{m}</span>)}
        </div>
      </div>
      <div>
        <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:10}}>
          <span className="sec" style={{margin:0}}>Connections</span>
          <div style={{display:'flex',gap:7}}>
            {d.model_modes.includes('api_provider')&&<button className="btn-g" style={{padding:'5px 10px',fontSize:11}} onClick={()=>addConn('api_provider')}>+ api</button>}
            {d.model_modes.includes('local_model')&&<button className="btn-g" style={{padding:'5px 10px',fontSize:11}} onClick={()=>addConn('local_model')}>+ local</button>}
          </div>
        </div>
        <div style={{display:'flex',flexDirection:'column',gap:10}}>
          {d.connections.map((c,i)=>(
            <div key={i} className="card">
              <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:12}}>
                <span style={{fontSize:11,color:c.mode==='api_provider'?'var(--a)':'var(--info)',fontWeight:600,letterSpacing:'.06em'}}>
                  [{c.mode==='api_provider'?'API':'LOCAL'}] CONNECTION {String(i+1).padStart(2,'0')}
                </span>
                {d.connections.length>1&&<button className="btn-g" style={{padding:'3px 9px',fontSize:11}} onClick={()=>delConn(i)}>remove</button>}
              </div>
              <div className="g3">
                <Field label="Provider">
                  <select className="inp" value={c.provider} onChange={e=>updConn(i,'provider',e.target.value)}>
                    {(c.mode==='api_provider'?API_PROVIDERS:LOCAL_PROVIDERS).map(p=><option key={p} value={p}>{p}</option>)}
                  </select>
                </Field>
                <Field label="Endpoint">
                  <input className="inp" value={c.endpoint} onChange={e=>updConn(i,'endpoint',e.target.value)} placeholder="https://…"/>
                </Field>
                <Field label="Model Ref">
                  <input className="inp" value={c.model_ref} onChange={e=>updConn(i,'model_ref',e.target.value)} placeholder="gpt-4o-mini"/>
                </Field>
              </div>
              <div style={{height:10}}/>
              <Field label="Priority (1 = primary)">
                <input type="number" className="inp" value={c.priority} onChange={e=>updConn(i,'priority',parseInt(e.target.value)||1)} min={1} max={10} style={{width:100}}/>
              </Field>
            </div>
          ))}
        </div>
      </div>
      {d.model_modes.includes('api_provider')&&(
        <div className="info-box">
          <div style={{fontWeight:600,marginBottom:4,fontSize:12}}>API Provider detected</div>
          API keys will be collected in Step 3 (Secrets). Only key names — not values — are stored in session config.
        </div>
      )}
      {d.model_modes.includes('local_model')&&(
        <div className="warn-box">
          <div style={{fontWeight:600,marginBottom:4,fontSize:12}}>Local Model detected</div>
          Include <code>local_model_runtime</code> in infra components (Step 2) to scaffold an Ollama service in your deployment artifacts.
        </div>
      )}
    </div>
  );
}

// ─── Step 2: Deployment ────────────────────────────────────────────────────────

function Step2({d,u}){
  const f=(k,v)=>u({...d,[k]:v});
  const togComp=id=>{
    let n=[...d.infra_components];
    if(id==='core_api')return;
    if(n.includes(id)){
      if(id==='postgres'&&n.includes('pgvector'))n=n.filter(x=>x!=='pgvector');
      n=n.filter(x=>x!==id);
    } else {
      if(id==='pgvector'&&!n.includes('postgres'))n=[...n,'postgres'];
      n=[...n,id];
    }
    f('infra_components',n);
  };
  const TARGETS=[{id:'docker_local',label:'docker_local',hint:'docker-compose.yml + .env.template'},{id:'k8s',label:'k8s',hint:'Kubernetes manifests'},{id:'terraform',label:'terraform',hint:'tfvars + HCL modules'},{id:'github_actions',label:'github_actions',hint:'CI/CD pipeline snippet'}];
  const EXEC=[{id:'generate_only',label:'generate_only',desc:'Output files only — no execution'},{id:'attempt_automated',label:'attempt_automated',desc:'Attempt to run scripts automatically'}];
  const selectedCap=TARGET_CAPABILITIES[d.deployment_target] || TARGET_CAPABILITIES.docker_local;

  useEffect(()=>{
    if(!selectedCap.allowed_execution_modes.includes(d.execution_mode)){
      f('execution_mode', selectedCap.allowed_execution_modes[0]);
    }
  },[d.deployment_target, d.execution_mode]);

  return(
    <div className="fu" style={{display:'flex',flexDirection:'column',gap:18}}>
      <div>
        <label className="lbl">Deployment Target</label>
        <div style={{display:'flex',flexDirection:'column',gap:8}}>
          {TARGETS.map(t=>(
            <div key={t.id} className={`cbox${d.deployment_target===t.id?' on':''}`} onClick={()=>f('deployment_target',t.id)}>
              <div className="cbox-sq">{d.deployment_target===t.id&&'✓'}</div>
              <div>
                <div style={{fontSize:12,fontWeight:500,fontFamily:'var(--mono)'}}>{t.label}</div>
                <div style={{fontSize:11,color:'var(--tm)',marginTop:2}}>→ generates {t.hint}</div>
              </div>
              {TARGET_CAPABILITIES[t.id].tested
                ? <span className="badge ok" style={{marginLeft:'auto',alignSelf:'flex-start',flexShrink:0}}>tested</span>
                : <span className="badge info" style={{marginLeft:'auto',alignSelf:'flex-start',flexShrink:0}}>experimental</span>}
            </div>
          ))}
        </div>
      </div>
      <div>
        <label className="lbl">Execution Mode</label>
        <div style={{display:'flex',gap:8}}>
          {EXEC.map(e=>(
            <div
              key={e.id}
              className={`cbox${d.execution_mode===e.id?' on':''}`}
              onClick={()=>selectedCap.allowed_execution_modes.includes(e.id)&&f('execution_mode',e.id)}
              style={{flex:1,opacity:selectedCap.allowed_execution_modes.includes(e.id)?1:.45,cursor:selectedCap.allowed_execution_modes.includes(e.id)?'pointer':'not-allowed'}}
            >
              <div className="cbox-sq">{d.execution_mode===e.id&&'✓'}</div>
              <div>
                <div style={{fontSize:12,fontWeight:500}}>{e.label}</div>
                <div style={{fontSize:11,color:'var(--tm)',marginTop:2}}>{e.desc}</div>
              </div>
            </div>
          ))}
        </div>
      </div>
      {!selectedCap.tested&&(
        <div className="warn-box">
          <b>Experimental target:</b> {selectedCap.disclaimer}
        </div>
      )}
      <div>
        <label className="lbl">Infra Components</label>
        <div style={{display:'flex',flexDirection:'column',gap:8}}>
          {INFRA.map(c=>(
            <Cbox key={c.id} checked={d.infra_components.includes(c.id)} onToggle={()=>togComp(c.id)}
              label={c.label} desc={c.desc} disabled={c.required}/>
          ))}
        </div>
      </div>
      {d.infra_components.includes('pgvector')&&!d.infra_components.includes('postgres')&&(
        <div className="warn-box">pgvector requires postgres — it will be added automatically.</div>
      )}
    </div>
  );
}

// ─── Step 3: Secrets ─────────────────────────────────────────────────────────

function Step3({d,u,data}){
  const f=(k,v)=>u({...d,[k]:v});
  const MODES=[
    {id:'template_only',label:'template_only',desc:'Generate .env.template only — no values collected'},
    {id:'transient_validate_only',label:'transient_validate_only',desc:'Values used for check then discarded'},
    {id:'pipeline_injected',label:'pipeline_injected',desc:'CI/CD injects values at runtime'},
  ];
  const TARGETS=[{id:'env_file',label:'env_file'},{id:'vault',label:'vault (HashiCorp)'},{id:'aws_ssm',label:'aws_ssm'},{id:'github_secrets',label:'github_secrets'}];
  useEffect(()=>{
    const auto=[];
    data.connections.forEach(c=>{
      if(c.mode==='api_provider'){
        const k={'openai':'OPENAI_API_KEY','anthropic':'ANTHROPIC_API_KEY','google':'GOOGLE_AI_API_KEY','azure_openai':'AZURE_OPENAI_API_KEY'}[c.provider];
        if(k&&!auto.includes(k))auto.push(k);
      }
    });
    if(data.infra_components.includes('postgres')&&!auto.includes('POSTGRES_PASSWORD'))auto.push('POSTGRES_PASSWORD');
    if(data.vector_store_mode==='enabled'&&data.vector_provider==='pinecone'&&!auto.includes('PINECONE_API_KEY'))auto.push('PINECONE_API_KEY');
    const merged=[...new Set([...auto,...d.required_keys])];
    if(merged.length!==d.required_keys.length||!merged.every((v,i)=>d.required_keys[i]===v)){
      u({...d,required_keys:merged});
    }
  },[
    data.connections,
    data.infra_components,
    data.vector_store_mode,
    data.vector_provider,
    d.required_keys
  ]);
  return(
    <div className="fu" style={{display:'flex',flexDirection:'column',gap:18}}>
      <div className="warn-box">
        <b>Security policy:</b> Raw secret values are never persisted. This wizard stores only key names (auth_refs). Actual injection happens via your chosen storage target at deploy time.
      </div>
      <div>
        <label className="lbl">Secrets Mode</label>
        <div style={{display:'flex',flexDirection:'column',gap:8}}>
          {MODES.map(m=>(
            <div key={m.id} className={`cbox${d.secrets_mode===m.id?' on':''}`} onClick={()=>f('secrets_mode',m.id)}>
              <div className="cbox-sq">{d.secrets_mode===m.id&&'✓'}</div>
              <div><div style={{fontSize:12,fontWeight:500}}>{m.label}</div>
              <div style={{fontSize:11,color:'var(--tm)',marginTop:2}}>{m.desc}</div></div>
            </div>
          ))}
        </div>
      </div>
      <div className="g2">
        <Field label="Storage Target">
          <select className="inp" value={d.storage_target} onChange={e=>f('storage_target',e.target.value)}>
            {TARGETS.map(t=><option key={t.id} value={t.id}>{t.label}</option>)}
          </select>
        </Field>
      </div>
      <div>
        <label className="lbl">Required Key Names</label>
        <div style={{fontSize:11,color:'var(--tm)',marginBottom:8}}>Auto-populated from your runtime config. Add any additional keys below.</div>
        <TagInput values={d.required_keys} onChange={v=>f('required_keys',v)} placeholder="MY_CUSTOM_KEY"/>
      </div>
    </div>
  );
}

// ─── Step 4: RAG / Vector Store ───────────────────────────────────────────────

function Step4({d,u,data}){
  const f=(k,v)=>u({...d,[k]:v});
  const pgvReq=d.vector_provider==='pgvector'&&(!data.infra_components.includes('postgres')||!data.infra_components.includes('pgvector'));
  return(
    <div className="fu" style={{display:'flex',flexDirection:'column',gap:18}}>
      <div>
        <label className="lbl">Vector Store Mode</label>
        <div style={{display:'flex',gap:8}}>
          {['disabled','enabled'].map(m=>(
            <span key={m} className={`chip${d.vector_store_mode===m?' sel':''}`} onClick={()=>f('vector_store_mode',m)} style={{flex:1,textAlign:'center',padding:'9px 14px'}}>{m}</span>
          ))}
        </div>
      </div>
      {d.vector_store_mode==='enabled'&&(
        <>
          <div>
            <label className="lbl">Provider</label>
            <div style={{display:'flex',gap:8}}>
              {['pgvector','pinecone'].map(p=>(
                <div key={p} style={{display:'flex',alignItems:'center',gap:6}}>
                  <span className={`chip${d.vector_provider===p?' sel':''}`} onClick={()=>f('vector_provider',p)}>{p}</span>
                  {p==='pinecone'&&<span className="badge info">near-term</span>}
                  {p==='pgvector'&&<span className="badge ok">mvp</span>}
                </div>
              ))}
            </div>
          </div>
          {pgvReq&&(
            <div className="warn-box">
              <b>Dependency warning:</b> pgvector requires <code>postgres</code> and <code>pgvector</code> components. Go back to Step 2 to enable them.
            </div>
          )}
          <div className="g2">
            <Field label="Namespace Pattern (optional)">
              <input className="inp" value={d.namespace_pattern} onChange={e=>f('namespace_pattern',e.target.value)} placeholder="{org}-{division}"/>
            </Field>
            <Field label="Index Strategy">
              <select className="inp" value={d.index_strategy} onChange={e=>f('index_strategy',e.target.value)}>
                <option value="flat">flat</option><option value="hnsw">hnsw</option><option value="ivfflat">ivfflat</option>
              </select>
            </Field>
          </div>
          {d.vector_provider==='pinecone'&&(
            <Field label="Pinecone Endpoint (required)">
              <input className="inp" value={d.vector_endpoint} onChange={e=>f('vector_endpoint',e.target.value)} placeholder="https://index.svc.environment.pinecone.io"/>
            </Field>
          )}
        </>
      )}
      {d.vector_store_mode==='disabled'&&(
        <div style={{padding:'24px 0',textAlign:'center',color:'var(--td)',fontSize:12}}>
          Vector store disabled — RAG capabilities will not be available.
        </div>
      )}
    </div>
  );
}

// ─── Step 5: Preflight ────────────────────────────────────────────────────────

function buildPreflightChecks(data){
  const checks=[];

  checks.push({
    name:'tenant_name_present',
    required:true,
    label:'Tenant name present',
    status:data.tenant_name.trim() ? 'pass' : 'fail',
    msg:data.tenant_name.trim() ? 'Tenant name configured.' : 'Provide tenant name in Step 1.'
  });

  checks.push({
    name:'connection_models_present',
    required:true,
    label:'Connection model references',
    status:data.connections.length > 0 && data.connections.every(c=>c.model_ref.trim()) ? 'pass' : 'fail',
    msg:data.connections.length > 0 && data.connections.every(c=>c.model_ref.trim())
      ? 'All connections include model refs.'
      : 'Set model_ref for every connection.'
  });

  checks.push({
    name:'core_api_component_enabled',
    required:true,
    label:'Core API component enabled',
    status:data.infra_components.includes('core_api') ? 'pass' : 'fail',
    msg:data.infra_components.includes('core_api') ? 'core_api selected.' : 'core_api is required.'
  });

  if(data.vector_store_mode==='enabled' && data.vector_provider==='pgvector'){
    const ok = data.infra_components.includes('postgres') && data.infra_components.includes('pgvector');
    checks.push({
      name:'pgvector_dependencies',
      required:true,
      label:'pgvector dependencies',
      status:ok ? 'pass' : 'fail',
      msg:ok ? 'postgres + pgvector components selected.' : 'Enable postgres and pgvector in Step 2.'
    });
  }

  if(data.vector_store_mode==='enabled' && data.vector_provider==='pinecone'){
    checks.push({
      name:'pinecone_endpoint_set',
      required:true,
      label:'Pinecone endpoint configured',
      status:data.vector_endpoint.trim() ? 'pass' : 'fail',
      msg:data.vector_endpoint.trim() ? 'Pinecone endpoint set.' : 'Set Pinecone endpoint in Step 4.'
    });
  }

  checks.push({
    name:'secrets_plan_configured',
    required:true,
    label:'Secrets strategy configured',
    status:data.secrets_mode ? 'pass' : 'fail',
    msg:data.secrets_mode ? 'Secrets strategy selected.' : 'Select secrets strategy in Step 3.'
  });

  return checks;
}

function Step5({d,u,runChecks,totalChecks}){
  const allDone=d.check_status==='done';
  const allReqPassed=d.check_results.filter(r=>r.required).every(r=>r.status==='pass');
  return(
    <div className="fu" style={{display:'flex',flexDirection:'column',gap:18}}>
      <div style={{display:'flex',justifyContent:'space-between',alignItems:'center'}}>
        <div>
          <div style={{fontSize:13,color:'var(--tm)',marginBottom:4}}>Run preflight validation for your selected configuration.</div>
          <div style={{fontSize:11,color:'var(--td)'}}>{totalChecks} config rules will be evaluated</div>
        </div>
        <button className="btn-a" onClick={runChecks} disabled={d.check_status==='running'}>
          {d.check_status==='running'?<><span className="spin">↻</span> Running…</>:'▶ Run Preflight'}
        </button>
      </div>
      {d.check_results.length>0&&(
        <div style={{display:'flex',flexDirection:'column',gap:6}}>
          {d.check_results.map((c,i)=>(
            <div key={i} style={{display:'flex',alignItems:'center',gap:12,padding:'10px 14px',background:'rgba(255,255,255,.02)',border:'1px solid var(--bdr)',borderRadius:7}}>
              <div className={`dot ${c.status||'pend'}`}/>
              <span style={{fontSize:12,flex:1,fontWeight:500}}>{c.label}</span>
              <span style={{fontSize:11,color:'var(--tm)',flex:2}}>{c.msg||'—'}</span>
              {c.status&&<span className={`badge ${c.status}`}>{c.status}</span>}
            </div>
          ))}
        </div>
      )}
      {d.check_status==='idle'&&(
        <div style={{padding:'28px 0',textAlign:'center',color:'var(--td)',fontSize:12}}>
          No preflight run yet. Click ▶ Run Preflight to validate config before generating artifacts.
        </div>
      )}
      {allDone&&(
        <div className={allReqPassed?'ok-box':'warn-box'}>
          <div style={{fontWeight:600,fontSize:13,marginBottom:4,color:allReqPassed?'var(--ok)':'var(--warn)'}}>
            {allReqPassed?'✓ Preflight passed — you may continue':'⚠ Preflight failed — resolve required issues'}
          </div>
          <div style={{fontSize:11,color:'var(--tm)'}}>{d.check_results.filter(r=>r.status==='fail').length} failed · {d.check_results.filter(r=>r.status==='pass').length} passed</div>
        </div>
      )}
    </div>
  );
}

// ─── Step 6: Artifacts ────────────────────────────────────────────────────────

function buildArtifacts(data){
  const targetCap = TARGET_CAPABILITIES[data.deployment_target] || TARGET_CAPABILITIES.docker_local;
  let env='# =====================================\n# .env.template — generated by setup wizard\n# =====================================\n\n# Core\nCORE_API_PORT=8000\nCORE_ENV=development\nCORS_ORIGINS=http://localhost:3000\n\n';
  const apiConns=data.connections.filter(c=>c.mode==='api_provider');
  if(apiConns.length>0){
    env+='# Model Providers\n';
    apiConns.forEach(c=>{
      const k={openai:'OPENAI_API_KEY=',anthropic:'ANTHROPIC_API_KEY=',google:'GOOGLE_AI_API_KEY=',azure_openai:'AZURE_OPENAI_API_KEY=\nAZURE_OPENAI_ENDPOINT=',custom:'CUSTOM_API_KEY='}[c.provider]||`${c.provider.toUpperCase()}_API_KEY=`;
      env+=`${k}\n`;
      if(c.endpoint)env+=`${c.provider.toUpperCase()}_BASE_URL=${c.endpoint}\n`;
    });
    env+='\n';
  }
  if(data.infra_components.includes('postgres')){
    env+='# PostgreSQL\nPOSTGRES_HOST=localhost\nPOSTGRES_PORT=5432\nPOSTGRES_DB=app\nPOSTGRES_USER=app\nPOSTGRES_PASSWORD=\n\n';
  }
  if(data.vector_store_mode==='enabled'&&data.vector_provider==='pinecone'){
    env+='# Pinecone\nPINECONE_API_KEY=\nPINECONE_ENVIRONMENT=\nPINECONE_INDEX=\n\n';
  }

  let compose='version: "3.9"\n\nservices:\n\n  core_api:\n    build: .\n    ports:\n      - "${CORE_API_PORT:-8000}:8000"\n    env_file: .env\n    restart: unless-stopped\n';
  const deps=[];
  if(data.infra_components.includes('postgres')||data.infra_components.includes('pgvector'))deps.push('postgres');
  if(data.infra_components.includes('local_model_runtime'))deps.push('ollama');
  if(deps.length>0)compose+=`    depends_on:\n${deps.map(d=>`      - ${d}`).join('\n')}\n`;
  if(data.infra_components.includes('postgres')||data.infra_components.includes('pgvector')){
    const img=data.infra_components.includes('pgvector')?'pgvector/pgvector:pg16':'postgres:16-alpine';
    compose+=`\n  postgres:\n    image: ${img}\n    environment:\n      POSTGRES_DB: \${POSTGRES_DB}\n      POSTGRES_USER: \${POSTGRES_USER}\n      POSTGRES_PASSWORD: \${POSTGRES_PASSWORD}\n    volumes:\n      - pgdata:/var/lib/postgresql/data\n    ports:\n      - "5432:5432"\n    healthcheck:\n      test: ["CMD-SHELL","pg_isready -U $$POSTGRES_USER"]\n      interval: 10s\n      timeout: 5s\n      retries: 5\n`;
  }
  if(data.infra_components.includes('local_model_runtime')){
    compose+='\n  ollama:\n    image: ollama/ollama:latest\n    ports:\n      - "11434:11434"\n    volumes:\n      - ollama_data:/root/.ollama\n';
  }
  if(data.infra_components.includes('reverse_proxy')){
    compose+='\n  nginx:\n    image: nginx:alpine\n    ports:\n      - "80:80"\n    volumes:\n      - ./nginx.conf:/etc/nginx/conf.d/default.conf\n    depends_on:\n      - core_api\n';
  }
  compose+='\nvolumes:\n';
  if(data.infra_components.includes('postgres')||data.infra_components.includes('pgvector'))compose+='  pgdata:\n';
  if(data.infra_components.includes('local_model_runtime'))compose+='  ollama_data:\n';

  const report=JSON.stringify({
    schema:'bootstrap-report/v0.1',
    generated_at:new Date().toISOString().split('T')[0],
    session:{tenant:data.tenant_name,type:data.tenant_type},
    runtime:{model_modes:data.model_modes,connections:data.connections.map(c=>({mode:c.mode,provider:c.provider,model_ref:c.model_ref,priority:c.priority}))},
    deployment:{target:data.deployment_target,execution_mode:data.execution_mode,components:data.infra_components},
    secrets:{mode:data.secrets_mode,storage_target:data.storage_target,key_count:data.required_keys.length,keys:data.required_keys},
    vector_store:{mode:data.vector_store_mode,provider:data.vector_store_mode==='enabled'?data.vector_provider:null},
    checks:{
      total:data.check_results.length,
      passed:data.check_results.filter(r=>r.status==='pass').length,
      failed:data.check_results.filter(r=>r.status==='fail').length,
      warnings:data.check_results.filter(r=>r.status==='warn').length
    },
    ingest:{enabled:data.ingest_now,files:data.doc_files.length,profile:data.chunking_profile},
  },null,2);

  const files=[{name:'.env.template',type:'env',content:env}];
  if(data.deployment_target==='docker_local') {
    files.push({name:'docker-compose.yml',type:'yaml',content:compose});
    if(data.infra_components.includes('reverse_proxy')) {
      const nginxConf = `server {
  listen 80;

  location / {
    proxy_pass http://core_api:8000;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
  }
}
`;
      files.push({name:'nginx.conf',type:'conf',content:nginxConf});
    }
  }
  if(data.deployment_target==='k8s') {
    const k8sManifest = `# Experimental template: not runtime-certified\n# ${targetCap.disclaimer}\n\napiVersion: v1\nkind: ConfigMap\nmetadata:\n  name: kairos-core-config\ndata:\n  CORE_ENV: "development"\n\n---\napiVersion: apps/v1\nkind: Deployment\nmetadata:\n  name: kairos-core-api\nspec:\n  replicas: 1\n  selector:\n    matchLabels:\n      app: kairos-core-api\n  template:\n    metadata:\n      labels:\n        app: kairos-core-api\n    spec:\n      containers:\n        - name: core-api\n          image: kairos-core:latest\n          ports:\n            - containerPort: 8000\n`;
    files.push({name:'k8s-manifests.yaml',type:'yaml',content:k8sManifest});
  }
  if(data.deployment_target==='terraform') {
    const tfvars = `# Experimental template: not runtime-certified\n# ${targetCap.disclaimer}\n\nproject_name = "${data.tenant_name || 'kairos-core'}"\nenvironment  = "dev"\nregion       = "us-east-1"\ncore_api_port = 8000\nenable_postgres = ${String(data.infra_components.includes('postgres'))}\nenable_pgvector = ${String(data.infra_components.includes('pgvector'))}\n`;
    files.push({name:'terraform.tfvars.example',type:'hcl',content:tfvars});
  }
  if(data.deployment_target==='github_actions') {
    const ghaSnippet = `# Experimental template: not runtime-certified\n# ${targetCap.disclaimer}\n\nname: kairos-core-bootstrap\n\non:\n  workflow_dispatch:\n\njobs:\n  bootstrap:\n    runs-on: ubuntu-latest\n    steps:\n      - uses: actions/checkout@v4\n      - uses: oven-sh/setup-bun@v2\n      - uses: actions/setup-python@v5\n        with:\n          python-version: \"3.12\"\n      - run: bun install\n      - run: python -m venv backend/.venv\n      - run: backend/.venv/bin/python -m pip install -e \"./backend[dev]\"\n      - run: bun run check:backend\n`;
    files.push({name:'github-actions-snippet.yml',type:'yaml',content:ghaSnippet});
  }
  files.push({name:'bootstrap-report.json',type:'json',content:report});
  return files;
}

function Step6({d,u,genArtifacts}){
  const [tab,setTab]=useState(0);
  const targetCap = TARGET_CAPABILITIES[d.deployment_target] || TARGET_CAPABILITIES.docker_local;
  const [transientSecrets, setTransientSecrets] = useState({});

  const withTransientValues = (content) => {
    if(!content || !d.required_keys?.length) return content;
    return d.required_keys.reduce((acc, key) => {
      const val = transientSecrets[key];
      if(!val) return acc;
      const re = new RegExp(`^${key}=.*$`, 'm');
      return re.test(acc) ? acc.replace(re, `${key}=${val}`) : acc;
    }, content);
  };

  const copyCurrent = async () => {
    const current = d.artifacts[tab];
    if(!current) return;
    const content = current.name === '.env.template' ? withTransientValues(current.content) : current.content;
    await navigator.clipboard.writeText(content);
  };

  const downloadFile = (name, content) => {
    const blob = new Blob([content], { type: 'text/plain;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = name;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  const downloadCurrent = () => {
    const current = d.artifacts[tab];
    if(!current) return;
    const content = current.name === '.env.template' ? withTransientValues(current.content) : current.content;
    downloadFile(current.name, content);
  };

  const downloadAll = () => {
    d.artifacts.forEach((file) => {
      const content = file.name === '.env.template' ? withTransientValues(file.content) : file.content;
      downloadFile(file.name, content);
    });
  };
  return(
    <div className="fu" style={{display:'flex',flexDirection:'column',gap:18}}>
      <div style={{display:'flex',justifyContent:'space-between',alignItems:'center'}}>
        <div>
          <div style={{fontSize:13,color:'var(--tm)'}}>Generate deployment artifacts from your configuration.</div>
          <div style={{fontSize:11,color:'var(--td)',marginTop:3}}>Output: {targetCap.artifact_types.join(', ')}</div>
        </div>
        <button className="btn-a" onClick={genArtifacts} disabled={d.gen_status==='generating'||d.gen_status==='done'}>
          {d.gen_status==='generating'?<><span className="spin">↻</span> Generating…</>:d.gen_status==='done'?'✓ Generated':'⚡ Generate Artifacts'}
        </button>
      </div>
      {d.gen_status==='done'&&d.artifacts.length>0&&(
        <div>
          {!targetCap.tested&&<div className="warn-box" style={{marginBottom:10}}>{targetCap.disclaimer}</div>}
          {d.required_keys?.length>0&&(
            <div className="card" style={{marginBottom:10}}>
              <div className="sec">Transient Secret Fill (copy/download only)</div>
              <div style={{fontSize:11,color:'var(--tm)',marginBottom:10}}>Values entered here are not persisted and are only applied during copy/download actions for `.env.template`.</div>
              <div className="g2">
                {d.required_keys.map((key)=> (
                  <Field key={key} label={key}>
                    <input className="inp" type="password" value={transientSecrets[key] || ''} onChange={e=>setTransientSecrets(p=>({...p,[key]:e.target.value}))} />
                  </Field>
                ))}
              </div>
            </div>
          )}
          <div style={{display:'flex',gap:8,marginBottom:10}}>
            <button className="btn-g" onClick={copyCurrent}>copy current</button>
            <button className="btn-g" onClick={downloadCurrent}>download current</button>
            <button className="btn-g" onClick={downloadAll}>download all</button>
          </div>
          <div style={{display:'flex',gap:2,borderBottom:'1px solid var(--bdr)',paddingBottom:0}}>
            {d.artifacts.map((a,i)=><button key={i} className={`ftab${tab===i?' act':''}`} onClick={()=>setTab(i)}>{a.name}</button>)}
          </div>
          <div style={{background:'rgba(0,0,0,.55)',border:'1px solid var(--bdr)',borderTop:'none',borderRadius:'0 0 7px 7px',maxHeight:340,overflow:'auto'}} className="scr">
            <pre style={{fontFamily:'var(--mono)',fontSize:11,lineHeight:1.8,color:'var(--tm)',padding:16,whiteSpace:'pre-wrap',wordBreak:'break-word'}}>
              {d.artifacts[tab]?.name === '.env.template' ? withTransientValues(d.artifacts[tab]?.content) : d.artifacts[tab]?.content}
            </pre>
          </div>
          <div className={`cbox${d.artifacts_applied?' on':''}`} style={{marginTop:10}} onClick={()=>u({...d,artifacts_applied:!d.artifacts_applied})}>
            <div className="cbox-sq">{d.artifacts_applied&&'✓'}</div>
            <div>
              <div style={{fontSize:13,fontWeight:500}}>I have run (or am now running) the generated deployment files.</div>
              <div style={{fontSize:11,color:'var(--tm)',marginTop:2}}>Runtime verification and document bootstrap should happen after deployment attempts.</div>
            </div>
          </div>
          <div style={{fontSize:11,color:'var(--td)',marginTop:6}}>{d.artifacts.length} file(s) generated · ready for download</div>
        </div>
      )}
      {d.gen_status==='idle'&&(
        <div style={{padding:'28px 0',textAlign:'center',color:'var(--td)',fontSize:12}}>
          Click ⚡ Generate Artifacts to produce output files.
        </div>
      )}
    </div>
  );
}

// ─── Step 7: Runtime Verify + Docs ────────────────────────────────────────────

function buildRuntimeChecks(data){
  const checks=[{name:'core_health_endpoint',required:true,label:'Core API health endpoint',hint:'curl http://localhost:8000/v1/health'}];
  if(data.infra_components.includes('postgres')) checks.push({name:'postgres_reachable',required:true,label:'PostgreSQL reachable',hint:'psql -h localhost -p 5432 -U app -d app -c "select 1;"'});
  if(data.infra_components.includes('pgvector')) checks.push({name:'pgvector_extension',required:true,label:'pgvector extension available',hint:'psql -h localhost -p 5432 -U app -d app -c "create extension if not exists vector;"'});
  if(data.connections.some(c=>c.mode==='api_provider')) checks.push({name:'provider_connectivity',required:true,label:'API provider connectivity',hint:'Validate provider auth from your runtime environment'});
  if(data.model_modes.includes('local_model')) checks.push({name:'local_model_endpoint',required:true,label:'Local model endpoint reachable',hint:'curl http://localhost:11434/api/tags'});
  return checks;
}

function Step7({d,u}){
  const f=(k,v)=>u({...d,[k]:v});
  const checks=d.runtime_check_results || [];
  const allReqPassed=checks.length>0 && checks.filter(c=>c.required).every(c=>c.status==='pass');
  const canShowDocs=allReqPassed;
  const fakeFiles=['.rfc/rfc-001.md','docs/architecture.md','docs/api-reference.md'];

  return(
    <div className="fu" style={{display:'flex',flexDirection:'column',gap:18}}>
      <div className="card">
        <div className="sec">Runtime Verification</div>
        <div style={{fontSize:11,color:'var(--tm)',marginBottom:10}}>After running generated files, mark each required runtime check as pass/fail.</div>
        <div style={{display:'flex',flexDirection:'column',gap:8}}>
          {checks.map((c,i)=>(
            <div key={i} style={{display:'grid',gridTemplateColumns:'1fr auto auto',gap:10,alignItems:'center',padding:'10px 12px',border:'1px solid var(--bdr)',borderRadius:7,background:'rgba(255,255,255,.02)'}}>
              <div>
                <div style={{fontSize:12,fontWeight:500}}>{c.label}</div>
                <div style={{fontSize:11,color:'var(--td)',marginTop:2}}>{c.hint}</div>
              </div>
              <button className={`chip${c.status==='pass'?' sel':''}`} onClick={()=>{
                const n=[...checks];
                n[i]={...n[i],status:'pass'};
                f('runtime_check_results',n);
                f('runtime_check_status','done');
              }}>pass</button>
              <button className={`chip${c.status==='fail'?' sel':''}`} onClick={()=>{
                const n=[...checks];
                n[i]={...n[i],status:'fail'};
                f('runtime_check_results',n);
                f('runtime_check_status','done');
              }}>fail</button>
            </div>
          ))}
        </div>
        {checks.length===0&&<div style={{fontSize:12,color:'var(--td)'}}>No runtime checks queued yet. Generate artifacts in Step 6 and continue.</div>}
      </div>

      {!canShowDocs&&<div className="warn-box"><b>Document bootstrap locked:</b> required runtime checks must pass before ingest/upload is available.</div>}

      {canShowDocs&&(
        <div className="card">
          <div className="sec">Document Bootstrap</div>
          <div style={{display:'flex',alignItems:'center',gap:12,marginBottom:12}}>
            <Toggle on={d.ingest_now} set={v=>f('ingest_now',v)}/>
            <div>
              <div style={{fontSize:13,fontWeight:500}}>Bootstrap document corpus now</div>
              <div style={{fontSize:11,color:'var(--tm)',marginTop:2}}>Upload docs to test vector retrieval with your configured runtime.</div>
            </div>
          </div>
          {d.ingest_now&&(
            <>
              <div>
                <label className="lbl">Source Files</label>
                <div style={{border:'1px dashed var(--bdr2)',borderRadius:8,padding:'18px',textAlign:'center',cursor:'pointer',transition:'border-color .15s'}} onClick={()=>f('doc_files',fakeFiles)}>
                  {d.doc_files.length===0
                    ?<span style={{fontSize:12,color:'var(--td)'}}>Click to select files — or drag & drop</span>
                    :<div style={{display:'flex',flexDirection:'column',gap:6,textAlign:'left'}}>
                      {d.doc_files.map((f2,i)=>(
                        <div key={i} style={{display:'flex',alignItems:'center',gap:8,padding:'6px 10px',background:'rgba(255,255,255,.03)',borderRadius:5,border:'1px solid var(--bdr)'}}>
                          <span style={{fontSize:16}}>📄</span>
                          <span style={{fontSize:12,flex:1}}>{f2}</span>
                          <button className="btn-g" style={{padding:'2px 8px',fontSize:11}} onClick={e=>{e.stopPropagation();f('doc_files',d.doc_files.filter(x=>x!==f2));}}>✕</button>
                        </div>
                      ))}
                    </div>
                  }
                </div>
              </div>
              <div className="g2" style={{marginTop:12}}>
                <Field label="Chunking Profile">
                  <select className="inp" value={d.chunking_profile} onChange={e=>f('chunking_profile',e.target.value)}>
                    <option value="recursive_512">recursive_512 (default)</option>
                    <option value="markdown_sections">markdown_sections</option>
                    <option value="sentence_window">sentence_window</option>
                    <option value="fixed_256">fixed_256</option>
                  </select>
                </Field>
                <Field label="Embedding Profile">
                  <select className="inp" value={d.embedding_profile} onChange={e=>f('embedding_profile',e.target.value)}>
                    <option value="default">default (provider default)</option>
                    <option value="text-embedding-3-small">text-embedding-3-small</option>
                    <option value="text-embedding-3-large">text-embedding-3-large</option>
                    <option value="nomic-embed-text">nomic-embed-text (local)</option>
                  </select>
                </Field>
              </div>
              {d.ingest_status==='idle'&&d.doc_files.length>0&&<button className="btn-a" style={{marginTop:12,alignSelf:'flex-start'}} onClick={()=>f('ingest_status','done')}>▶ Run Ingest</button>}
              {d.ingest_status==='done'&&<div className="ok-box" style={{marginTop:12}}><div style={{fontWeight:600,fontSize:13,color:'var(--ok)',marginBottom:4}}>✓ Ingest complete</div><div style={{fontSize:11,color:'var(--tm)'}}>{d.doc_files.length} file(s) ingested · profile: {d.chunking_profile}</div></div>}
            </>
          )}
        </div>
      )}
    </div>
  );
}

// ─── Step 8: Review ────────────────────────────────────────────────────────────

function Step8({d,u,data}){
  const f=(k,v)=>u({...d,[k]:v});
  const targetCap = TARGET_CAPABILITIES[data.deployment_target] || TARGET_CAPABILITIES.docker_local;
  const rows=[
    {label:'Tenant',val:`${data.tenant_name||'—'} (${data.tenant_type})`},
    {label:'Model Modes',val:data.model_modes.join(', ')||'—'},
    {label:'Connections',val:`${data.connections.length} connection(s) configured`},
    {label:'Deploy Target',val:`${data.deployment_target} · ${data.execution_mode}`},
    {label:'Target Maturity',val:`${targetCap.maturity} · ${targetCap.tested ? 'tested' : 'experimental'}`},
    {label:'Infra Components',val:data.infra_components.join(', ')},
    {label:'Secrets Mode',val:`${data.secrets_mode} → ${data.storage_target}`},
    {label:'Required Keys',val:data.required_keys.length?data.required_keys.join(', '):'none'},
    {label:'Vector Store',val:data.vector_store_mode==='enabled'?`${data.vector_provider}${data.namespace_pattern?' · '+data.namespace_pattern:''}`:data.vector_store_mode},
    {label:'Preflight',val:data.check_status==='done'?`${data.check_results.filter(r=>r.status==='pass').length} passed, ${data.check_results.filter(r=>r.status==='fail').length} failed`:'not run'},
    {label:'Runtime Verify',val:data.runtime_check_results.length?`${data.runtime_check_results.filter(r=>r.status==='pass').length} passed, ${data.runtime_check_results.filter(r=>r.status==='fail').length} failed`:'not run'},
    {label:'Doc Bootstrap',val:data.ingest_now?`${data.doc_files.length} files · ${data.chunking_profile}`:'disabled'},
    {label:'Artifacts',val:data.gen_status==='done'?`${data.artifacts.length} files generated`:'not generated'},
  ];
  return(
    <div className="fu" style={{display:'flex',flexDirection:'column',gap:18}}>
      <div className="card">
        <div className="sec">Session Summary</div>
        <div style={{display:'flex',flexDirection:'column',gap:1}}>
          {rows.map((r,i)=>(
            <div key={i} style={{display:'flex',gap:16,padding:'7px 0',borderBottom:i<rows.length-1?'1px solid var(--bdr)':'none'}}>
              <span style={{fontSize:11,color:'var(--td)',width:140,flexShrink:0}}>{r.label}</span>
              <span style={{fontSize:12,color:'var(--tm)',wordBreak:'break-word'}}>{r.val}</span>
            </div>
          ))}
        </div>
      </div>
      {!targetCap.tested&&<div className="warn-box"><b>Experimental target:</b> {targetCap.disclaimer}</div>}
      {data.gen_status!=='done'&&<div className="warn-box"><b>Heads up:</b> Artifacts haven't been generated yet. Go back to Step 6 to generate deployment files.</div>}
      {data.gen_status==='done'&&!data.artifacts_applied&&<div className="warn-box"><b>Run required:</b> return to Step 6 and acknowledge you ran (or are running) the generated deployment files.</div>}
      <div className={`cbox${d.confirmed?' on':''}`} onClick={()=>f('confirmed',!d.confirmed)}>
        <div className="cbox-sq">{d.confirmed&&'✓'}</div>
        <div>
          <div style={{fontSize:13,fontWeight:500}}>I confirm this configuration is correct and ready to bootstrap</div>
          <div style={{fontSize:11,color:'var(--tm)',marginTop:2}}>This will mark the session as <code>completed</code> and optionally generate a handoff token.</div>
        </div>
      </div>
      {d.confirmed&&(
        <div className="ok-box">
          <div style={{fontWeight:700,fontSize:14,color:'var(--ok)',marginBottom:6,fontFamily:'var(--head)'}}>✓ Bootstrap Session Complete</div>
          <div style={{fontFamily:'var(--mono)',fontSize:11,color:'var(--tm)',marginBottom:10}}>BootstrapSession.status = <span style={{color:'var(--ok)'}}>completed</span></div>
          <div style={{display:'flex',gap:8}}>
            <span className="badge ok">completed</span>
            <span className="badge info">{data.tenant_name||'unnamed'}</span>
            <span className="badge skip">{data.deployment_target}</span>
          </div>
        </div>
      )}
    </div>
  );
}

// ─── Right Panel ─────────────────────────────────────────────────────────────

function RightPanel({step,data}){
  const [tab,setTab]=useState(0);
  useEffect(()=>{setTab(0);},[step]);
  const tabs0_3=[
    {label:'runtime',content:JSON.stringify({tenant_name:data.tenant_name,tenant_type:data.tenant_type,model_modes:data.model_modes,connections:data.connections.map(c=>({mode:c.mode,provider:c.provider,model_ref:c.model_ref}))},null,2)},
    {label:'deploy',content:JSON.stringify({deployment_target:data.deployment_target,execution_mode:data.execution_mode,infra_components:data.infra_components},null,2)},
    {label:'secrets',content:JSON.stringify({secrets_mode:data.secrets_mode,storage_target:data.storage_target,required_keys:data.required_keys},null,2)},
    {label:'rag',content:JSON.stringify({vector_store_mode:data.vector_store_mode,vector_provider:data.vector_provider,index_strategy:data.index_strategy},null,2)},
  ].slice(0,step+1);

  if(step<4) return(
    <div style={{height:'100%',display:'flex',flexDirection:'column'}}>
      <div style={{padding:'0 16px',display:'flex',gap:2,borderBottom:'1px solid var(--bdr)',flexShrink:0}}>
        {tabs0_3.map((t,i)=><button key={i} className={`ftab${tab===i?' act':''}`} onClick={()=>setTab(i)}>{t.label}</button>)}
      </div>
      <div style={{flex:1,overflow:'auto',padding:'14px 16px'}} className="scr">
        <div style={{fontSize:10,color:'var(--td)',marginBottom:8,fontFamily:'var(--mono)',letterSpacing:'.06em'}}>// live session config</div>
        <pre style={{fontFamily:'var(--mono)',fontSize:11,lineHeight:1.8,color:'var(--tm)',whiteSpace:'pre-wrap',wordBreak:'break-word'}}>
          {tabs0_3[tab]?.content}
        </pre>
      </div>
    </div>
  );

  if(step===4) return(
    <div style={{height:'100%',display:'flex',flexDirection:'column',padding:'16px'}}>
      <div style={{fontSize:10,color:'var(--td)',marginBottom:12,letterSpacing:'.06em'}}>// check output</div>
      <div style={{flex:1,overflow:'auto',fontFamily:'var(--mono)',fontSize:11,lineHeight:1.8}} className="scr">
        {data.check_results.length===0
          ?<div style={{color:'var(--td)'}}>$ waiting for checks to run...</div>
          :data.check_results.map((c,i)=>(
            <div key={i} style={{display:'flex',gap:8,marginBottom:4}}>
              <span style={{color:c.status==='pass'?'var(--ok)':c.status==='warn'?'var(--warn)':c.status==='fail'?'var(--err)':'var(--td)'}}>
                {c.status==='pass'?'[✓]':c.status==='warn'?'[!]':c.status==='fail'?'[✗]':c.status==='run'?'[…]':'[·]'}
              </span>
              <span style={{color:'var(--t)',flex:1}}>{c.name}</span>
              <span style={{color:'var(--td)'}}>{c.msg||'...'}</span>
            </div>
          ))
        }
        {data.check_status==='done'&&<div style={{color:'var(--ok)',marginTop:8}}>$ done</div>}
      </div>
    </div>
  );

  if(step===5&&data.gen_status==='done') return(
    <div style={{height:'100%',display:'flex',flexDirection:'column'}}>
      <div style={{padding:'0 16px',display:'flex',gap:2,borderBottom:'1px solid var(--bdr)',flexShrink:0}}>
        {data.artifacts.map((a,i)=><button key={i} className={`ftab${tab===i?' act':''}`} onClick={()=>setTab(i)}>{a.name}</button>)}
      </div>
      <div style={{flex:1,overflow:'auto',padding:0}} className="scr">
        <pre style={{fontFamily:'var(--mono)',fontSize:11,lineHeight:1.8,color:'var(--tm)',padding:'14px 16px',whiteSpace:'pre-wrap',wordBreak:'break-word'}}>
          {data.artifacts[tab]?.content}
        </pre>
      </div>
    </div>
  );

  return(
    <div style={{height:'100%',padding:'16px',display:'flex',flexDirection:'column',gap:12,overflow:'auto'}} className="scr">
      <div style={{fontSize:10,color:'var(--td)',letterSpacing:'.06em'}}>// session state</div>
      <pre style={{fontFamily:'var(--mono)',fontSize:11,lineHeight:1.8,color:'var(--tm)',whiteSpace:'pre-wrap',wordBreak:'break-word'}}>
        {JSON.stringify({tenant:data.tenant_name,model_modes:data.model_modes,target:data.deployment_target,components:data.infra_components,secrets:data.secrets_mode,vector:data.vector_store_mode,checks:data.check_status,ingest:data.ingest_now,artifacts:data.gen_status},null,2)}
      </pre>
    </div>
  );
}

// ─── Main Wizard ──────────────────────────────────────────────────────────────

export default function EnvWizard(){
  const [step,setStep]=useState(0);
  const [done,setDone]=useState(new Set());
  const [data,setData]=useState(INIT);
  const [panelOpen,setPanelOpen]=useState(true);
  const upd=k=>v=>setData(p=>({...p,[k]:v}));

  const runChecks=()=>{
    const checks=buildPreflightChecks(data);
    setData(p=>({...p,check_status:'done',check_results:checks}));
  };

  const genArtifacts=()=>{
    setData(p=>({...p,gen_status:'generating'}));
    setTimeout(()=>{
      const artifacts=buildArtifacts(data);
      setData(p=>({...p,gen_status:'done',artifacts}));
    },1400);
  };

  const canContinue=()=>{
    if(step===0)return data.tenant_name.trim()&&data.model_modes.length>0&&data.connections.length>0&&data.connections.every(c=>c.model_ref.trim());
    if(step===1)return data.infra_components.includes('core_api');
    if(step===2)return data.required_keys.length>0||data.secrets_mode==='template_only';
    if(step===4){
      const preflightReady = data.check_status==='done' && data.check_results.filter(r=>r.required).every(r=>r.status==='pass');
      return preflightReady;
    }
    if(step===5)return data.gen_status==='done' && data.artifacts_applied;
    if(step===6){
      const runtimeReady = data.runtime_check_results.length>0 && data.runtime_check_results.filter(r=>r.required).every(r=>r.status==='pass');
      return runtimeReady && (!data.ingest_now || data.ingest_status==='done');
    }
    if(step===7)return data.confirmed;
    return true;
  };

  const goNext=()=>{
    setDone(p=>new Set([...p,step]));
    if(step===5){
      const runtimeChecks=buildRuntimeChecks(data).map(c=>({...c,status:'pend'}));
      setData(p=>({...p,runtime_check_results:runtimeChecks,runtime_check_status:'idle'}));
    }
    if(step<7)setStep(s=>s+1);
  };
  const goPrev=()=>{if(step>0)setStep(s=>s-1);};

  const FORMS=[
    <Step1 key={0} d={{tenant_name:data.tenant_name,tenant_type:data.tenant_type,model_modes:data.model_modes,connections:data.connections}} u={v=>setData(p=>({...p,...v}))}/>,
    <Step2 key={1} d={{deployment_target:data.deployment_target,execution_mode:data.execution_mode,infra_components:data.infra_components}} u={v=>setData(p=>({...p,...v}))}/>,
    <Step3 key={2} d={{secrets_mode:data.secrets_mode,storage_target:data.storage_target,required_keys:data.required_keys}} u={v=>setData(p=>({...p,...v}))} data={data}/>,
    <Step4 key={3} d={{vector_store_mode:data.vector_store_mode,vector_provider:data.vector_provider,namespace_pattern:data.namespace_pattern,index_strategy:data.index_strategy,vector_endpoint:data.vector_endpoint}} u={v=>setData(p=>({...p,...v}))} data={data}/>,
    <Step5 key={4} d={{check_status:data.check_status,check_results:data.check_results}} u={v=>setData(p=>({...p,...v}))} runChecks={runChecks} totalChecks={buildPreflightChecks(data).length}/>,
    <Step6 key={5} d={{gen_status:data.gen_status,artifacts:data.artifacts,deployment_target:data.deployment_target,required_keys:data.required_keys,artifacts_applied:data.artifacts_applied}} u={v=>setData(p=>({...p,...v}))} genArtifacts={genArtifacts}/>,
    <Step7 key={6} d={{runtime_check_results:data.runtime_check_results,runtime_check_status:data.runtime_check_status,ingest_now:data.ingest_now,doc_files:data.doc_files,chunking_profile:data.chunking_profile,embedding_profile:data.embedding_profile,ingest_status:data.ingest_status}} u={v=>setData(p=>({...p,...v}))} />,
    <Step8 key={7} d={{confirmed:data.confirmed}} u={v=>setData(p=>({...p,...v}))} data={data}/>,
  ];

  const ok=canContinue();

  return(
    <div className="w" style={{display:'flex',flexDirection:'column',height:'100vh',overflow:'hidden'}}>
      <style>{S}</style>

      {/* Header */}
      <div style={{display:'flex',alignItems:'center',justifyContent:'space-between',padding:'0 24px',height:52,background:'var(--s1)',borderBottom:'1px solid var(--bdr)',flexShrink:0}}>
        <div style={{display:'flex',alignItems:'center',gap:10}}>
          <div style={{width:26,height:26,borderRadius:5,background:'var(--a)',display:'flex',alignItems:'center',justifyContent:'center',fontSize:13,color:'#0b0b10',fontWeight:700}}>⚙</div>
          <span style={{fontFamily:'var(--head)',fontWeight:700,fontSize:15,letterSpacing:'-.01em'}}>env config</span>
          <span style={{fontSize:10,color:'var(--td)',letterSpacing:'.08em',paddingTop:1}}>WIZARD</span>
        </div>
        <div style={{display:'flex',alignItems:'center',gap:12}}>
          {data.gen_status==='done'&&<span className="badge ok">artifacts ready</span>}
          <button className="btn-g" style={{padding:'5px 12px',fontSize:11}} onClick={()=>setPanelOpen(p=>!p)}>
            {panelOpen?'hide panel':'show panel'}
          </button>
        </div>
      </div>

      {/* Step track */}
      <div style={{background:'var(--s1)',borderBottom:'1px solid var(--bdr)',padding:'10px 16px',flexShrink:0,overflowX:'auto'}}>
        <div style={{display:'flex',alignItems:'center',minWidth:'max-content',gap:0}}>
          {STEPS.map((s,i)=>(
            <div key={i} style={{display:'flex',alignItems:'center',gap:0}}>
              <div style={{display:'flex',flexDirection:'column',alignItems:'center',gap:5,padding:'0 8px',cursor:'pointer',opacity:i>step+1?.5:1,transition:'opacity .2s'}} onClick={()=>setStep(i)}>
                <div style={{width:24,height:24,borderRadius:5,display:'flex',alignItems:'center',justifyContent:'center',fontSize:10,fontWeight:600,transition:'all .2s',
                  background:done.has(i)&&step!==i?'rgba(245,158,11,.15)':step===i?'var(--a)':'rgba(255,255,255,.05)',
                  color:done.has(i)&&step!==i?'var(--a)':step===i?'#0b0b10':'var(--td)',
                  border:done.has(i)&&step!==i?'1px solid rgba(245,158,11,.25)':step===i?'none':'1px solid var(--bdr)'}}>
                  {done.has(i)&&step!==i?'✓':s.n}
                </div>
                <span style={{fontSize:9,color:step===i?'var(--a)':'var(--td)',letterSpacing:'.05em',whiteSpace:'nowrap'}}>{s.s}</span>
              </div>
              {i<STEPS.length-1&&<div style={{width:24,height:1,background:done.has(i)?'rgba(245,158,11,.3)':'var(--bdr)',transition:'background .4s',flexShrink:0}}/>}
            </div>
          ))}
        </div>
      </div>

      {/* Body */}
      <div style={{flex:1,display:'flex',overflow:'hidden'}}>

        {/* Form */}
        <div style={{flex:1,overflow:'auto',padding:'28px 32px',borderRight:panelOpen?'1px solid var(--bdr)':'none'}} className="scr">
          <div style={{marginBottom:22}}>
            <div style={{fontSize:10,color:'var(--a)',letterSpacing:'.1em',marginBottom:6,fontWeight:600}}>STEP {STEPS[step].n}</div>
            <h1 style={{fontFamily:'var(--head)',fontSize:22,fontWeight:700,letterSpacing:'-.02em',marginBottom:4}}>{STEPS[step].label}</h1>
          </div>
          {FORMS[step]}
        </div>

        {/* Right panel */}
        {panelOpen&&(
          <div style={{width:320,flexShrink:0,background:'var(--s1)',overflow:'hidden',display:'flex',flexDirection:'column'}}>
            <div style={{padding:'10px 16px',borderBottom:'1px solid var(--bdr)',flexShrink:0,display:'flex',alignItems:'center',justifyContent:'space-between'}}>
              <span style={{fontSize:10,color:'var(--td)',letterSpacing:'.08em',fontWeight:600}}>CONFIG PANEL</span>
              <span style={{fontSize:10,color:'var(--a)',letterSpacing:'.06em'}}>{STEPS[step].s.toLowerCase()}</span>
            </div>
            <div style={{flex:1,overflow:'hidden'}}>
              <RightPanel step={step} data={data}/>
            </div>
          </div>
        )}
      </div>

      {/* Footer */}
      <div style={{padding:'14px 32px',background:'var(--s1)',borderTop:'1px solid var(--bdr)',display:'flex',justifyContent:'space-between',alignItems:'center',flexShrink:0}}>
        <button className="btn-g" onClick={goPrev} disabled={step===0}>← back</button>
        <div style={{display:'flex',alignItems:'center',gap:10}}>
          {!ok&&step<7&&<span style={{fontSize:11,color:'var(--td)'}}>complete required fields to continue</span>}
          {ok&&step<7&&<span style={{fontSize:11,color:'var(--ok)'}}>✓ ready</span>}
        </div>
        {step<7
          ?<button className="btn-a" onClick={goNext} disabled={!ok}>continue →</button>
          :<button className="btn-a" onClick={()=>{}} disabled={!data.confirmed} style={!data.confirmed?{opacity:.35,cursor:'not-allowed'}:{}}>complete setup ✓</button>
        }
      </div>
    </div>
  );
}
