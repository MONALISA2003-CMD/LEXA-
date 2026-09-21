
"use client";

import { useEffect, useMemo, useState } from "react";
import {
  advanceWorkflow, createBusinessTransaction, createPartyRelationship, createWorkflowDefinition, createWorkflowInstance,
  getBusinessCapabilities, getBusinessConfiguration, getBusinessContext, getBusinessTransactions, getPartyRelationships,
  getTransactionTypes, getWorkflowDefinitions, getWorkflowInstances, putBusinessConfiguration, setBusinessCapability,
  transitionBusinessTransaction, type BusinessCapability, type BusinessConfiguration, type BusinessContext, type BusinessTransaction,
  type PartyRelationship, type TransactionType, type WorkflowDefinition, type WorkflowInstance,
} from "../../lib/api";

function short(id:string){return id.slice(0,8)+"…";}
function pretty(value:unknown){return JSON.stringify(value,null,2);}

export default function BusinessEnginePage(){
  const [capabilities,setCapabilities]=useState<BusinessCapability[]>([]);
  const [configuration,setConfiguration]=useState<BusinessConfiguration[]>([]);
  const [relationships,setRelationships]=useState<PartyRelationship[]>([]);
  const [types,setTypes]=useState<TransactionType[]>([]);
  const [transactions,setTransactions]=useState<BusinessTransaction[]>([]);
  const [definitions,setDefinitions]=useState<WorkflowDefinition[]>([]);
  const [instances,setInstances]=useState<WorkflowInstance[]>([]);
  const [context,setContext]=useState<BusinessContext|null>(null);
  const [message,setMessage]=useState("");
  const [busy,setBusy]=useState(false);
  const [configKey,setConfigKey]=useState("default.branch_code");
  const [configValue,setConfigValue]=useState("MAIN");
  const [relationshipFrom,setRelationshipFrom]=useState("");
  const [relationshipTo,setRelationshipTo]=useState("");
  const [relationshipType,setRelationshipType]=useState("CUSTOMER_CONTACT");
  const [txType,setTxType]=useState("ORDER");
  const [txReference,setTxReference]=useState("");
  const [txParty,setTxParty]=useState("");
  const [txAmount,setTxAmount]=useState("0");
  const [workflowCode,setWorkflowCode]=useState("ORDER_APPROVAL");
  const [workflowName,setWorkflowName]=useState("Order approval workflow");
  const [workflowEntityId,setWorkflowEntityId]=useState("");
  const [workflowDefId,setWorkflowDefId]=useState("");
  const [contextType,setContextType]=useState("party");
  const [contextId,setContextId]=useState("");

  async function refresh(){
    setBusy(true); setMessage("");
    try{
      const [c,cf,r,t,tx,w,i]=await Promise.all([
        getBusinessCapabilities(),getBusinessConfiguration(),getPartyRelationships(),getTransactionTypes(),getBusinessTransactions(),getWorkflowDefinitions(),getWorkflowInstances()
      ]);
      setCapabilities(c);setConfiguration(cf);setRelationships(r);setTypes(t);setTransactions(tx);setDefinitions(w);setInstances(i);
      if(!workflowDefId && w[0])setWorkflowDefId(w[0].id);
      if(!txType && t[0])setTxType(t[0].code);
    }catch(e){setMessage(e instanceof Error?e.message:"Unable to load the Business Engine.");}
    finally{setBusy(false);}
  }
  useEffect(()=>{void refresh();},[]);
  const activeCapabilities=useMemo(()=>capabilities.filter(x=>x.enabled).length,[capabilities]);
  async function run(fn:()=>Promise<unknown>,success:string){try{await fn();setMessage(success);await refresh();}catch(e){setMessage(e instanceof Error?e.message:"Action failed.");}}

  return <main className="workspace-shell" style={{minHeight:"100vh"}}>
    <header className="workspace-header" style={{position:"sticky",top:0,zIndex:5}}>
      <div><span className="workspace-breadcrumb">LEXA · Business Engine</span><h1>Universal business engine</h1><p>Configuration, relationships, transactions, workflows and contextual business information.</p></div>
      <div className="header-actions"><a className="button button-soft" href="/">Workspace</a><button className="button button-dark" onClick={refresh}>{busy?"Refreshing…":"Refresh"}</button></div>
    </header>
    <div className="workspace-content">
      {message&&<div className="alert" role="status">{message}</div>}
      <section className="cards-grid" style={{marginBottom:24}}>{[
        ["Capabilities",activeCapabilities], ["Configurations",configuration.length], ["Relationships",relationships.length], ["Transaction types",types.length], ["Transactions",transactions.length], ["Workflow definitions",definitions.length], ["Workflow runs",instances.length]
      ].map(([label,value])=><article className="location-card" key={String(label)}><span className="tag">ENGINE</span><strong style={{display:"block",fontSize:28,marginTop:8}}>{value}</strong><small>{label}</small></article>)}</section>

      <section className="split-panel">
        <div className="command-form"><p className="eyebrow">BUSINESS CONFIGURATION</p><h3>Control the workspace without schema changes</h3><p>Capabilities and configuration values let LEXA adapt the same kernel to different businesses.</p>
          {capabilities.slice(0,6).map(c=><div className="workflow-row" key={c.id}><div><strong>{c.name}</strong><small>{c.code}</small></div><button onClick={()=>void run(()=>setBusinessCapability(c.code,{enabled:!c.enabled,configuration:c.configuration}),`${c.code} ${c.enabled?"disabled":"enabled"}`)}>{c.enabled?"Disable":"Enable"}</button></div>)}
          <div className="form-grid"><label>Config key<input value={configKey} onChange={e=>setConfigKey(e.target.value)} /></label><label>Value<input value={configValue} onChange={e=>setConfigValue(e.target.value)} /></label></div>
          <button className="primary" onClick={()=>void run(()=>putBusinessConfiguration(configKey,{value:configValue,value_type:"STRING"}),"Configuration saved.")}>Save configuration</button>
        </div>
        <div className="workflow-list"><p className="eyebrow">CONFIGURATION</p>{configuration.length?configuration.map(c=><div className="workflow-row" key={c.id}><div><strong>{c.config_key}</strong><small>v{c.version} · {c.value_type}</small></div><code>{String(c.value_json)}</code></div>):<div className="empty-inline">No custom configuration yet.</div>}</div>
      </section>

      <section className="split-panel" style={{marginTop:24}}>
        <form className="command-form" onSubmit={e=>{e.preventDefault();if(!relationshipFrom||!relationshipTo)return;void run(()=>createPartyRelationship({from_party_id:relationshipFrom,to_party_id:relationshipTo,relationship_type:relationshipType}),"Party relationship created.");}}>
          <p className="eyebrow">PARTY RELATIONSHIPS</p><h3>Connect business actors</h3><p>Customers, suppliers, contacts and other parties can be related without duplicating identities.</p>
          <label>From party ID<input value={relationshipFrom} onChange={e=>setRelationshipFrom(e.target.value)} required /></label><label>To party ID<input value={relationshipTo} onChange={e=>setRelationshipTo(e.target.value)} required /></label><label>Relationship type<input value={relationshipType} onChange={e=>setRelationshipType(e.target.value)} required /></label><button className="primary">Create relationship</button>
        </form>
        <div className="workflow-list"><p className="eyebrow">RELATIONSHIP MAP</p>{relationships.length?relationships.slice(0,10).map(r=><div className="workflow-row" key={r.id}><div><strong>{r.from_party_name||short(r.from_party_id)} → {r.to_party_name||short(r.to_party_id)}</strong><small>{r.relationship_type}</small></div><span className="status good">{r.status}</span></div>):<div className="empty-inline">No relationships yet.</div>}</div>
      </section>

      <section className="split-panel" style={{marginTop:24}}>
        <form className="command-form" onSubmit={e=>{e.preventDefault();if(!txReference||!txType)return;void run(()=>createBusinessTransaction({transaction_type:txType,reference:txReference,party_id:txParty||null,lines:txAmount!=="0"?[{line_type:"MISC",description:"Business transaction line",quantity:1,unit_price:txAmount}]:[]}),"Transaction created.");setTxReference("");}}>
          <p className="eyebrow">TRANSACTION ENGINE</p><h3>Create a universal transaction</h3><p>One lifecycle supports quotations, orders, fulfillment, invoices and custom business transactions.</p>
          <label>Type<select value={txType} onChange={e=>setTxType(e.target.value)}>{types.map(t=><option value={t.code} key={t.id}>{t.code} · {t.name}</option>)}</select></label><label>Reference<input value={txReference} onChange={e=>setTxReference(e.target.value)} placeholder="ORD-1001" required /></label><label>Party ID<input value={txParty} onChange={e=>setTxParty(e.target.value)} placeholder="optional" /></label><label>Total line amount<input type="number" step="0.01" value={txAmount} onChange={e=>setTxAmount(e.target.value)} /></label><button className="primary">Create transaction</button>
        </form>
        <div className="workflow-list"><p className="eyebrow">TRANSACTION PIPELINE</p>{transactions.length?transactions.slice(0,10).map(t=><div className="workflow-row" key={t.id}><div><strong>{t.reference}</strong><small>{t.transaction_type} · {t.status}</small></div><div className="row-actions">{t.status!=="COMPLETED"&&t.status!=="CANCELLED"&&<button onClick={()=>void run(()=>transitionBusinessTransaction(t.id,t.status==="DRAFT"?"CONFIRMED":"COMPLETED"),`Transaction ${t.reference} advanced.`)}>Advance</button>}<button onClick={()=>{setContextType("transaction");setContextId(t.id);void getBusinessContext("transaction",t.id).then(setContext).catch(e=>setMessage(e instanceof Error?e.message:"Context unavailable."));}}>Context</button></div></div>):<div className="empty-inline">No transactions yet.</div>}</div>
      </section>

      <section className="split-panel" style={{marginTop:24}}>
        <form className="command-form" onSubmit={e=>{e.preventDefault();void run(()=>createWorkflowDefinition({code:workflowCode,name:workflowName,steps:[{id:"",workflow_definition_id:"",step_key:"review",name:"Review",step_type:"APPROVAL",position:1,configuration:{}},{id:"",workflow_definition_id:"",step_key:"complete",name:"Complete",step_type:"ACTION",position:2,configuration:{}}]} as any),"Workflow definition created.");}}>
          <p className="eyebrow">WORKFLOW ENGINE</p><h3>Define a reusable workflow</h3><p>Durable business workflows can be attached to transactions, tasks, parties and other universal objects.</p><label>Code<input value={workflowCode} onChange={e=>setWorkflowCode(e.target.value)} required /></label><label>Name<input value={workflowName} onChange={e=>setWorkflowName(e.target.value)} required /></label><button className="primary">Create workflow</button>
        </form>
        <div className="workflow-list"><p className="eyebrow">WORKFLOWS</p>{definitions.slice(0,8).map(d=><div className="workflow-row" key={d.id}><div><strong>{d.name}</strong><small>{d.code} · {d.steps.length} steps</small></div><div className="row-actions"><button onClick={()=>{setWorkflowDefId(d.id);setWorkflowEntityId(transactions[0]?.id||"");}}>Use</button>{workflowEntityId&&workflowDefId===d.id&&<button onClick={()=>void run(()=>createWorkflowInstance({workflow_definition_id:d.id,entity_type:"transaction",entity_id:workflowEntityId}),"Workflow started.")}>Start</button>}</div></div>)}{!definitions.length&&<div className="empty-inline">No workflow definitions yet.</div>}</div>
      </section>

      <section className="split-panel" style={{marginTop:24}}>
        <div className="command-form"><p className="eyebrow">WORKFLOW EXECUTION</p><h3>Advance active workflows</h3><p>Each step creates a traceable run. Task and approval steps generate work items.</p>{instances.slice(0,8).map(i=><div className="workflow-row" key={i.id}><div><strong>{i.entity_type} · {short(i.entity_id)}</strong><small>{i.status} · {short(i.id)}</small></div><div className="row-actions">{i.status==="RUNNING"&&<button onClick={()=>void run(()=>advanceWorkflow(i.id,{completed_by:"workspace_user"}),"Workflow advanced.")}>Advance</button>}</div></div>)}{!instances.length&&<div className="empty-inline">No workflow instances yet.</div>}</div>
        <div className="command-form"><p className="eyebrow">BUSINESS CONTEXT</p><h3>Inspect the connected view</h3><p>LEXA assembles authorized context from the transactional kernel instead of inventing a separate source of truth.</p><div className="form-grid"><label>Entity type<select value={contextType} onChange={e=>setContextType(e.target.value)}><option value="party">Party</option><option value="transaction">Transaction</option><option value="product">Product</option></select></label><label>Entity ID<input value={contextId} onChange={e=>setContextId(e.target.value)} placeholder="UUID" /></label></div><button className="primary" onClick={()=>{if(!contextId)return;void getBusinessContext(contextType,contextId).then(setContext).catch(e=>setMessage(e instanceof Error?e.message:"Context unavailable."));}}>Load context</button>{context&&<pre style={{marginTop:16,maxHeight:420,overflow:"auto",whiteSpace:"pre-wrap"}}>{pretty(context)}</pre>}</div>
      </section>
    </div>
  </main>
}
