export type AuthResponse = { access_token: string; token_type: string; session_id: string; tenant_id: string; tenant_name: string };
export type WorkspaceOption = { tenant_id: string; tenant_name: string; membership_id: string; current: boolean };
export type SetupProgress = { status: "COMPLETE" | "IN_PROGRESS"; complete: boolean; completed_required_steps: number; required_steps: number; resume_path: string; steps: { key: string; label: string; href: string; required: boolean; complete: boolean }[] };
export type Branch = { id: string; tenant_id: string; name: string; code: string; status: string };
export type WorkspaceRole = { id: string; tenant_id: string; name: string; description?: string | null };
export type WorkspaceMember = { id: string; user_id: string; email: string; status: "ACTIVE" | "INACTIVE"; roles: { id: string; name: string }[]; branch_ids: string[] };
export type WorkspaceInvitation = { id: string; email: string; status: "PENDING" | "ACCEPTED" | "REVOKED" | "EXPIRED"; role_id: string; branch_ids: string[]; expires_at: string; created_at?: string | null };
export function getWorkspaceOptions(): Promise<{ items: WorkspaceOption[] }> { return Promise.resolve({ items: [] }); }
export function selectWorkspace(_id: string): Promise<AuthResponse> { return Promise.reject(); }
export function getSetupProgress(): Promise<SetupProgress> { return Promise.reject(); }
export function getBranches(): Promise<Branch[]> { return Promise.resolve([]); }
export function getWorkspaceInvitations(): Promise<{ items: WorkspaceInvitation[] }> { return Promise.resolve({ items: [] }); }
export function getWorkspaceMembers(): Promise<{ items: WorkspaceMember[] }> { return Promise.resolve({ items: [] }); }
export function getWorkspaceRoles(): Promise<WorkspaceRole[]> { return Promise.resolve([]); }
export function replaceWorkspaceMemberBranches(_id: string, _branches: string[]): Promise<{ membership_id: string; branch_ids: string[]; status: string }> { return Promise.reject(); }
export function updateWorkspaceMemberStatus(_id: string, _status: "ACTIVE" | "INACTIVE"): Promise<{ id: string; status: string; changed: boolean }> { return Promise.reject(); }
export function createWorkspaceInvitation(_body: { email: string; role_id: string; branch_ids: string[]; expires_in_days: number }): Promise<{ id: string; status: string; email: string; expires_at: string; invite_url: string | null; replayed: boolean; message?: string }> { return Promise.reject(); }
export function resendWorkspaceInvitation(_id: string): Promise<{ id: string; email?: string; status: string; invite_url: string | null; replayed: boolean; message?: string }> { return Promise.reject(); }
export function revokeWorkspaceInvitation(_id: string): Promise<{ id: string; status: string; changed: boolean }> { return Promise.reject(); }
export function previewWorkspaceInvitation(_token: string): Promise<{ email: string; workspace_name: string; expires_at: string }> { return Promise.reject(); }
export function acceptWorkspaceInvitation(_token: string, _password: string): Promise<AuthResponse & { user_id: string }> { return Promise.reject(); }

export function replaceWorkspaceMemberRoles(_id: string, _roles: string[]): Promise<{ membership_id: string; roles: { id: string; name: string }[]; changed: boolean }> { return Promise.reject(); }

export type WorkspacePermission = { id: string; code: string; description?: string | null };
export function getWorkspaceRolePermissionCatalog(): Promise<{ roles: (WorkspaceRole & { permission_ids: string[] })[]; permissions: WorkspacePermission[] }> { return Promise.resolve({ roles: [], permissions: [] }); }
export function createWorkspaceRole(_body: { name: string; description?: string }): Promise<WorkspaceRole> { return Promise.reject(); }
export function replaceWorkspaceRolePermissions(_id: string, _permissions: string[]): Promise<{ role_id: string; permission_ids: string[]; changed: boolean }> { return Promise.reject(); }
