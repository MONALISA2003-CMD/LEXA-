"use client";

import { useEffect, useState } from "react";
import {
  createKernelParty, createKernelResource, createKernelService, createKernelTask,
  getKernelParties, getKernelResources, getKernelServices, getKernelSummary, getKernelTasks,
  type KernelParty, type KernelResource, type KernelService, type KernelSummary, type KernelTask,
} from "../../lib/api";

function short(id:string){return `${id.slice(0,8)}…`;}

export default function KernelPage(){
  const [summary,setSummary]=useState<KernelSummary|null>(null);
  const [parties,setParties]=useState<KernelParty[]>([]);
  const [services,setServices]=useState<KernelService[]>([]);
  const [resources,setResources]=useState<KernelResource[]>([]);
  const [tasks,setTasks]=useState<KernelTask[]>([]);
  const [message,setMessage]=useState("");
  const [busy,setBusy]=useState(false);
  const [partyName,setPartyName]=useState("");
  const [partyType,setPartyType]=useState<'PERSON'|'ORGANIZATION'>('PERSON');
  const [serviceName,setServiceName]=useState("");
  const [serviceCode,setServiceCode]=useState("");
  const [resourceName,setResourceName]=useState("");
  const [resourceCode,setResourceCode]=useState("");
  const [resourceType,setResourceType]=useState("GENERAL");
  const [taskTitle,setTaskTitle]=useState("");

  async function refresh(){
    setBusy(true);setMessage("");
    try{
      const [s,p,sv,r,t]=await Promise.all([getKernelSummary(),getKernelParties(),getKernelServices(),getKernelResources(),getKernelTasks()]);
      setSummary(s);setParties(p);setServices(sv);setResources(r);setTasks(t);
    }catch(e){setMessage(e instanceof Error?e.message:"Unable to load Business Kernel.");}
    finally{setBusy(false);}
  }
  useEffect(()=>{void refresh();},[]);

  async function run(action:()=>Promise<unknown>,success:string){
    try{await action();setMessage(success);await refresh();}
    catch(e){setMessage(e instanceof Error?e.message:"Action failed.");}
  }

  return <main className="workspace-shell" style={{minHeight:"100vh"}}>
    <header className="workspace-header" style={{position:"sticky",top:0,zIndex:5}}>
      <div><span className="workspace-breadcrumb">LEXA · Business Kernel</span><h1>Universal business foundation</h1><p>Parties, services, resources and work objects shared across industry packs.</p></div>
      <div className="header-actions"><a className="button button-soft" href="/">Workspace</a><button className="button button-dark" onClick={refresh}>{busy?"Refreshing…":"Refresh"}</button></div>
    </header>

    <div className="workspace-content">
      {message&&<div className="alert" role="status">{message}</div>}
      <section className="cards-grid" style={{marginBottom:24}}>
        {['parties','services','resources','assets','documents','transactions','payments','tasks','cases','projects','contracts'].map(k=><article className="location-card" key={k}><span className="tag">KERNEL</span><strong style={{display:'block',fontSize:28,marginTop:8}}>{summary?.counts?.[k]??0}</strong><small>{k.replaceAll('_',' ')}</small></article>)}
      </section>

      <section className="split-panel">
        <form className="command-form" onSubmit={e=>{e.preventDefault();if(!partyName.trim())return;void run(()=>createKernelParty({party_type:partyType,display_name:partyName.trim()}),"Party created.");setPartyName("");}}>
          <div><p className="eyebrow">PARTIES</p><h3>Create a universal party</h3><p>Use one identity for customers, suppliers, employees and other relationships.</p></div>
          <label>Type<select value={partyType} onChange={e=>setPartyType(e.target.value as 'PERSON'|'ORGANIZATION')}><option value="PERSON">Person</option><option value="ORGANIZATION">Organization</option></select></label>
          <label>Display name<input value={partyName} onChange={e=>setPartyName(e.target.value)} required /></label>
          <button className="primary">Create party</button>
        </form>
        <div className="workflow-list"><p className="eyebrow">RECENT PARTIES</p>{parties.length?parties.slice(0,8).map(p=><div className="workflow-row" key={p.id}><div><strong>{p.display_name}</strong><small>{p.party_type} · {short(p.id)}</small></div><span className="status good">{p.status}</span></div>):<div className="empty-inline">No parties yet.</div>}</div>
      </section>

      <section className="split-panel" style={{marginTop:24}}>
        <form className="command-form" onSubmit={e=>{e.preventDefault();if(!serviceName||!serviceCode)return;void run(()=>createKernelService({name:serviceName,code:serviceCode}),"Service created.");setServiceName("");setServiceCode("");}}>
          <div><p className="eyebrow">SERVICES</p><h3>Define a business service</h3><p>Services work alongside products and can power later capability packs.</p></div>
          <label>Name<input value={serviceName} onChange={e=>setServiceName(e.target.value)} required /></label>
          <label>Code<input value={serviceCode} onChange={e=>setServiceCode(e.target.value)} required /></label>
          <button className="primary">Create service</button>
        </form>
        <div className="workflow-list"><p className="eyebrow">SERVICES</p>{services.length?services.slice(0,8).map(s=><div className="workflow-row" key={s.id}><div><strong>{s.name}</strong><small>{s.code}</small></div><span className="status good">{s.status}</span></div>):<div className="empty-inline">No services yet.</div>}</div>
      </section>

      <section className="split-panel" style={{marginTop:24}}>
        <form className="command-form" onSubmit={e=>{e.preventDefault();if(!resourceName||!resourceCode)return;void run(()=>createKernelResource({resource_type:resourceType,name:resourceName,code:resourceCode}),"Resource created.");setResourceName("");setResourceCode("");}}>
          <div><p className="eyebrow">RESOURCES</p><h3>Create an operational resource</h3><p>Rooms, vehicles, machines, people and other capacity can share this model.</p></div>
          <label>Type<input value={resourceType} onChange={e=>setResourceType(e.target.value)} required /></label>
          <label>Name<input value={resourceName} onChange={e=>setResourceName(e.target.value)} required /></label>
          <label>Code<input value={resourceCode} onChange={e=>setResourceCode(e.target.value)} required /></label>
          <button className="primary">Create resource</button>
        </form>
        <div className="workflow-list"><p className="eyebrow">RESOURCES</p>{resources.length?resources.slice(0,8).map(r=><div className="workflow-row" key={r.id}><div><strong>{r.name}</strong><small>{r.resource_type} · {r.code}</small></div><span className="status neutral">{r.status}</span></div>):<div className="empty-inline">No resources yet.</div>}</div>
      </section>

      <section className="split-panel" style={{marginTop:24}}>
        <form className="command-form" onSubmit={e=>{e.preventDefault();if(!taskTitle.trim())return;void run(()=>createKernelTask({title:taskTitle.trim()}),"Task created.");setTaskTitle("");}}>
          <div><p className="eyebrow">WORK</p><h3>Create an operational task</h3><p>Tasks provide a universal work object for later workflows and agents.</p></div>
          <label>Task title<input value={taskTitle} onChange={e=>setTaskTitle(e.target.value)} required /></label>
          <button className="primary">Create task</button>
        </form>
        <div className="workflow-list"><p className="eyebrow">TASKS</p>{tasks.length?tasks.slice(0,8).map(t=><div className="workflow-row" key={t.id}><div><strong>{t.title}</strong><small>{t.priority} · {short(t.id)}</small></div><span className="status neutral">{t.status}</span></div>):<div className="empty-inline">No tasks yet.</div>}</div>
      </section>
    </div>
  </main>
}
