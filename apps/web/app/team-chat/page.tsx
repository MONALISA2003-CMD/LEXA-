"use client";

import { FormEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { AppShell } from "../../components/app-shell";
import { ApiError, createTeamConversation, getBranches, getTeamConversations, getTeamMessages, markTeamConversationRead, sendTeamMessage, type Branch, type TeamConversation, type TeamMessage, userFacingError } from "../../lib/api";

function relativeTime(value?: string | null) {
  if (!value) return "No messages yet";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Recently";
  const seconds = Math.max(0, Math.round((Date.now() - date.getTime()) / 1000));
  if (seconds < 60) return "Just now";
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
  return new Intl.DateTimeFormat("en-UG", { day: "numeric", month: "short" }).format(date);
}
function exactTime(value: string) {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : new Intl.DateTimeFormat("en-UG", { dateStyle: "medium", timeStyle: "short" }).format(date);
}

export default function TeamChatPage() {
  const [conversations, setConversations] = useState<TeamConversation[]>([]);
  const [branches, setBranches] = useState<Branch[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [messages, setMessages] = useState<TeamMessage[]>([]);
  const [loadState, setLoadState] = useState<"loading" | "ready" | "error">("loading");
  const [messagesState, setMessagesState] = useState<"loading" | "ready" | "error">("loading");
  const [error, setError] = useState("");
  const [draftTitle, setDraftTitle] = useState("");
  const [draftBranch, setDraftBranch] = useState("");
  const [messageText, setMessageText] = useState("");
  const [showCreate, setShowCreate] = useState(false);
  const [creating, setCreating] = useState(false);
  const [sending, setSending] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const endRef = useRef<HTMLDivElement | null>(null);
  const activeConversation = useMemo(() => conversations.find(item => item.id === activeId) || null, [conversations, activeId]);

  const loadConversations = useCallback(async (quiet = false) => {
    if (!quiet) setLoadState("loading");
    try {
      const [items, branchItems] = await Promise.all([getTeamConversations(), getBranches().catch(() => [] as Branch[])]);
      setConversations(items);
      setBranches(branchItems.filter(branch => branch.status === "ACTIVE"));
      setActiveId(current => current && items.some(item => item.id === current) ? current : (items[0]?.id ?? null));
      setLoadState("ready");
      setError("");
    } catch (e) {
      setLoadState("error");
      setError(userFacingError(e, "Team conversations could not be loaded. Refresh to try again."));
    }
  }, []);

  const loadMessages = useCallback(async (conversationId: string, quiet = false) => {
    if (!quiet) setMessagesState("loading");
    try {
      const items = await getTeamMessages(conversationId, 100);
      setMessages(items);
      setMessagesState("ready");
      void markTeamConversationRead(conversationId).catch(() => undefined);
      setConversations(current => current.map(item => item.id === conversationId ? { ...item, unread_count: 0 } : item));
      setError("");
    } catch (e) {
      setMessagesState("error");
      setError(userFacingError(e, "Messages could not be loaded. Your saved conversation has not been changed."));
    }
  }, []);

  useEffect(() => { void loadConversations(); }, [loadConversations]);
  useEffect(() => {
    const timer = window.setInterval(() => {
      if (document.visibilityState === "visible") void loadConversations(true);
    }, 20000);
    const onVisible = () => { if (document.visibilityState === "visible") void loadConversations(true); };
    document.addEventListener("visibilitychange", onVisible);
    return () => { window.clearInterval(timer); document.removeEventListener("visibilitychange", onVisible); };
  }, [loadConversations]);
  useEffect(() => {
    if (!activeId) { setMessages([]); setMessagesState("ready"); return; }
    void loadMessages(activeId);
    const timer = window.setInterval(() => {
      if (document.visibilityState === "visible") void loadMessages(activeId, true);
    }, 12000);
    return () => window.clearInterval(timer);
  }, [activeId, loadMessages]);
  useEffect(() => { endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" }); }, [messages.length, activeId]);

  async function submitConversation(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const title = draftTitle.trim();
    if (!title || creating) return;
    setCreating(true); setError("");
    try {
      const created = await createTeamConversation({ title, branch_id: draftBranch || null });
      setDraftTitle(""); setDraftBranch(""); setShowCreate(false);
      await loadConversations(true);
      setConversations(current => [created, ...current.filter(item => item.id !== created.id)]);
      setActiveId(created.id);
    } catch (e) {
      setError(userFacingError(e, "The conversation could not be created. Check your access and try again."));
    } finally { setCreating(false); }
  }

  async function submitMessage(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!activeId || !messageText.trim() || sending) return;
    const body = messageText.trim();
    setSending(true); setError("");
    try {
      const sent = await sendTeamMessage(activeId, body);
      setMessages(current => [...current.filter(item => item.id !== sent.id), sent].slice(-100));
      setMessageText("");
      setConversations(current => current.map(item => item.id === activeId ? { ...item, latest_message: sent.body, latest_sender_name: sent.sender_name, latest_sender_user_id: sent.sender_user_id, last_message_at: sent.created_at, unread_count: 0 } : item).sort((a,b) => new Date(b.last_message_at || b.created_at).getTime() - new Date(a.last_message_at || a.created_at).getTime()));
    } catch (e) {
      setError(userFacingError(e, e instanceof ApiError && e.status === 403 ? "You do not have permission to send messages here." : "The message was not confirmed. Refresh the conversation before retrying."));
    } finally { setSending(false); }
  }

  return <AppShell title="Team chat" eyebrow="TEAM WORKSPACE">
    <div className="workspace team-chat-page">
      <div className="workspace-header team-chat-heading">
        <div><span className="workspace-breadcrumb">LEXA · COLLABORATION</span><h1>Team chat</h1><p>Keep sales, stock, purchasing and customer handovers connected inside your business.</p></div>
        <div className="header-actions"><button className="button button-soft" type="button" disabled={refreshing} onClick={async () => { setRefreshing(true); await loadConversations(); if (activeId) await loadMessages(activeId); setRefreshing(false); }}>{refreshing ? "Refreshing…" : "Refresh"}</button><button className="button button-dark" type="button" onClick={() => setShowCreate(v => !v)}>{showCreate ? "Cancel" : "New conversation"}</button></div>
      </div>
      {error && <div className="inline-message" role="alert">{error}</div>}
      {showCreate && <form className="workspace-section team-chat-create" onSubmit={submitConversation}>
        <div><span className="section-label">START A THREAD</span><h2>New team conversation</h2><p>Use a clear subject so teammates can find this discussion later.</p></div>
        <label>Conversation title<input value={draftTitle} onChange={e => setDraftTitle(e.target.value)} required maxLength={160} placeholder="e.g. Friday stock count handover" /></label>
        <label>Branch scope<select value={draftBranch} onChange={e => setDraftBranch(e.target.value)}><option value="">Whole business</option>{branches.map(branch => <option key={branch.id} value={branch.id}>{branch.name}</option>)}</select><small>Branch conversations are visible only to team members assigned to that branch.</small></label>
        <button type="submit" className="button button-dark" disabled={creating || !draftTitle.trim()}>{creating ? "Creating…" : "Create conversation"}</button>
      </form>}

      <section className="team-chat-layout" aria-label="Team conversations">
        <aside className="workspace-section team-chat-list">
          <div className="team-chat-list-head"><div><span className="section-label">YOUR TEAM</span><h2>Conversations</h2></div><span className="team-chat-count">{conversations.length}</span></div>
          {loadState === "loading" && <p className="empty-inline" role="status">Loading conversations…</p>}
          {loadState === "error" && <div className="empty-state"><strong>Conversations unavailable</strong><p>Your saved messages have not been changed.</p><button type="button" className="button button-soft" onClick={() => void loadConversations()}>Retry</button></div>}
          {loadState === "ready" && conversations.length === 0 && <div className="team-chat-empty"><span aria-hidden="true">◌</span><strong>Start your first team thread</strong><p>Discuss a handover, supplier delivery, customer follow-up or stock issue without leaving LEXA.</p><button type="button" className="button button-soft" onClick={() => setShowCreate(true)}>Create conversation</button></div>}
          <div className="team-chat-conversation-items">{conversations.map(item => <button type="button" key={item.id} onClick={() => setActiveId(item.id)} className={`team-chat-conversation ${activeId === item.id ? "selected" : ""}`} aria-current={activeId === item.id ? "true" : undefined}>
            <span className="team-chat-avatar" aria-hidden="true">{item.title.trim().slice(0,1).toUpperCase()}</span><span className="team-chat-conversation-main"><strong>{item.title}</strong><small>{item.branch_name || "Whole business"} · {relativeTime(item.last_message_at || item.created_at)}</small><span>{item.latest_message ? `${item.latest_sender_name || "Team member"}: ${item.latest_message}` : "No messages yet"}</span></span>{Number(item.unread_count) > 0 && <b className="team-chat-unread">{Number(item.unread_count) > 99 ? "99+" : item.unread_count}</b>}
          </button>)}</div>
        </aside>

        <section className="workspace-section team-chat-thread" aria-label={activeConversation ? activeConversation.title : "Conversation messages"}>
          {!activeConversation ? <div className="team-chat-empty team-chat-thread-empty"><span aria-hidden="true">↗</span><strong>Good conversations keep work moving</strong><p>Select a thread or create a new one to send your team a message.</p></div> : <>
            <header className="team-chat-thread-head"><div><span className="section-label">{activeConversation.branch_name || "WHOLE BUSINESS"}</span><h2>{activeConversation.title}</h2><p>Messages are saved with your workspace and follow its access rules.</p></div><span className="team-chat-live-label"><i /> Updates every 12 seconds</span></header>
            <div className="team-chat-messages" aria-live="polite" aria-relevant="additions text">
              {messagesState === "loading" && <p className="empty-inline" role="status">Loading messages…</p>}
              {messagesState === "error" && <div className="empty-state"><strong>Messages unavailable</strong><button type="button" className="button button-soft" onClick={() => void loadMessages(activeConversation.id)}>Retry</button></div>}
              {messagesState === "ready" && messages.length === 0 && <div className="team-chat-empty"><span aria-hidden="true">✳</span><strong>This thread is ready</strong><p>Send the first message. Keep customer details limited to what your teammates need.</p></div>}
              {messages.map(message => <article key={message.id} className={`team-chat-message ${message.is_mine ? "mine" : ""}`}><div className="team-chat-message-meta"><strong>{message.is_mine ? "You" : message.sender_name}</strong><time dateTime={message.created_at} title={exactTime(message.created_at)}>{relativeTime(message.created_at)}</time></div><p>{message.body}</p></article>)}
              <div ref={endRef} />
            </div>
            <form className="team-chat-composer" onSubmit={submitMessage}><label htmlFor="team-chat-message">Message your team</label><textarea id="team-chat-message" value={messageText} onChange={e => setMessageText(e.target.value)} maxLength={4000} rows={3} placeholder="Write a useful update or handover…" /><div className="team-chat-composer-footer"><span>{messageText.length}/4000 · Avoid passwords or payment credentials.</span><button className="button button-dark" type="submit" disabled={sending || !messageText.trim()}>{sending ? "Sending…" : "Send message"}</button></div></form>
          </>}
        </section>
      </section>
      <p className="team-chat-note">This is internal LEXA collaboration, not customer-facing WhatsApp or SMS. External messaging providers can be connected later through verified credentials and consent controls.</p>
    </div>
  </AppShell>;
}
