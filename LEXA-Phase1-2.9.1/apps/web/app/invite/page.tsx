export default function InvitePage() {
  return (
    <main className="public-page">
      <section
        className="public-cta"
        style={{ minHeight: "100vh", display: "grid", placeItems: "center" }}
      >
        <div className="command-form" style={{ width: "min(520px, 100%)" }}>
          <span className="section-label">LEXA</span>
          <h2>Workspace invitations are unavailable</h2>
          <p>
            Invitation acceptance is not enabled in this deployment, so this link
            cannot activate a workspace membership.
          </p>
          <p>
            Sign in with an existing account, or contact your workspace
            administrator to arrange access.
          </p>
          <a className="primary" href="/login">Back to sign in</a>
        </div>
      </section>
    </main>
  );
}
