import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import {
  connectManaged,
  disconnectGmailAccount,
  getGoogleCustomAuthConfig,
  getGoogleCustomAuthUrl,
  setGmailDefaultAccount,
  setGmailFilters,
  type GmailAccount,
} from "../../api";
import { ConnectorBadge } from "../../connectors/ConnectorIcon";
import { openExternal } from "../../tauri";
import type { DetailProps } from "./ConnectorsSection";
import { ToolsDisclosure } from "./ToolsDisclosure";
import { FOOT, GRP, GRP_H, PILL_ACCENT, ROW, TAG_ACCENT, TAG_WARN, XBTN } from "./ui";

// The Gmail detail page (UX-DECISIONS §21): connected mailboxes (multi-account,
// Default badge, per-account disconnect) + "Never show agents" privacy filters.
// Adding an account launches managed OAuth DIRECTLY — Gmail has one connect mode,
// so no modal (the pill-modal is only for ≥2-mode connectors like Slack).

const LABEL = "text-ui text-muted w-24 shrink-0";

export function GmailDetail({ c, cloud, slack: _slack, onChanged }: DetailProps) {
  const { t } = useTranslation();
  const [busy, setBusy] = useState(false);
  const accounts = (c.accounts ?? []) as GmailAccount[]; // email-keyed (pre-generic-layer shape)

  const addAccount = async () => {
    setBusy(true);
    const res = await connectManaged("gmail"); // completes in the system browser; the poll picks it up
    if (res?.authorize_url) {
      openExternal(res.authorize_url);
    }
    setTimeout(() => setBusy(false), 2500);
  };

  return (
    <div data-testid="gmail-detail">
      <div className="flex items-center gap-3.5 mb-5">
        <ConnectorBadge connector={c} size={44} title="Gmail" />
        <div className="min-w-0 flex-1">
          <h2 className="text-title font-semibold tracking-tight leading-tight">Gmail</h2>
          <div className="text-ui text-muted flex items-center gap-1.5">
            {c.connected ? (
              <>
                <span className="w-2 h-2 rounded-full bg-ok" />
                <span data-testid="gmail-status">
                  {t("connector.account_count", { count: accounts.length })}
                </span>
              </>
            ) : (
              <span>{t("connector.not_connected")}</span>
            )}
          </div>
        </div>
        <button
          className={PILL_ACCENT + (c.managed_paused ? " opacity-50" : "")}
          data-testid="add-account-btn"
          onClick={addAccount}
          disabled={busy || !cloud?.signed_in || c.managed_paused}
          title={
            c.managed_paused
              ? t("gmail.coming_soon_title")
              : cloud?.signed_in
                ? ""
                : t("cloud.sign_in_first")
          }
        >
          {c.managed_paused ? t("gmail.add_account_coming_soon") : busy ? t("cloud.check_browser") : t("gmail.add_account")}
        </button>
      </div>

      {!c.connected && (
        <div className={GRP}>
          <div className={ROW + " text-ui text-muted"}>
            {t("gmail.setup_blurb")}
            {cloud?.signed_in ? "" : " " + t("gmail.requires_cloud")}
          </div>
        </div>
      )}

      {accounts.length > 0 && (
        <>
          <div className={GRP_H + " !mt-0"}>{t("gmail.accounts")}</div>
          <div className={GRP} data-testid="gmail-accounts">
            {accounts.map((a) => (
              <AccountRow key={a.email} a={a} onChanged={onChanged} />
            ))}
          </div>
        </>
      )}

      <CustomGoogleAuthSection onChanged={onChanged} />

      <FiltersGroup c={c} onChanged={onChanged} />

      <ToolsDisclosure c={c} onChanged={onChanged} />
      <div className={FOOT + " mt-2"}>
        {t("gmail.filters_foot")}
      </div>
    </div>
  );
}

function AccountRow({ a, onChanged }: { a: GmailAccount; onChanged: () => void }) {
  const { t } = useTranslation();
  const [busy, setBusy] = useState(false);
  return (
    <div className={ROW} data-testid={`gmail-account-${a.email}`}>
      <span className="min-w-0 flex-1 flex items-center gap-2">
        <span className="text-ui font-medium truncate">{a.email}</span>
        {a.default && <span className={TAG_ACCENT}>{t("connector.default")}</span>}
        {a.needs_reauth && <span className={TAG_WARN}>{t("gmail.sign_in_again")}</span>}
      </span>
      {!a.default && (
        <button
          className="text-meta text-muted hover:text-ink shrink-0"
          data-testid={`gmail-make-default-${a.email}`}
          onClick={async () => {
            await setGmailDefaultAccount(a.email);
            onChanged();
          }}
        >
          {t("connector.make_default")}
        </button>
      )}
      <button
        className={XBTN}
        title={t("gmail.disconnect_mailbox_title")}
        data-testid={`gmail-disconnect-${a.email}`}
        disabled={busy}
        onClick={async () => {
          setBusy(true);
          await disconnectGmailAccount(a.email);
          setBusy(false);
          onChanged();
        }}
      >
        ×
      </button>
    </div>
  );
}

function FiltersGroup({ c, onChanged }: Pick<DetailProps, "c" | "onChanged">) {
  const { t } = useTranslation();
  const filters = c.filters ?? { senders: [], labels: [] };
  return (
    <>
      <div className={GRP_H}>{t("gmail.never_show_agents")}</div>
      <div className={GRP} data-testid="gmail-filters">
        <ChipListRow
          label={t("gmail.senders")}
          testid="gmail-filter-senders"
          placeholder={t("gmail.senders_placeholder")}
          values={filters.senders}
          onSave={async (senders) => {
            await setGmailFilters({ senders });
            onChanged();
          }}
        />
        <ChipListRow
          label={t("gmail.labels")}
          testid="gmail-filter-labels"
          placeholder={t("gmail.labels_placeholder")}
          values={filters.labels}
          onSave={async (labels) => {
            await setGmailFilters({ labels });
            onChanged();
          }}
        />
      </div>
      <div className={FOOT}>
        {t("gmail.filters_foot_inner")}
      </div>
    </>
  );
}

function ChipListRow({
  label,
  testid,
  placeholder,
  values,
  onSave,
}: {
  label: string;
  testid: string;
  placeholder: string;
  values: string[];
  onSave: (next: string[]) => Promise<void>;
}) {
  const { t } = useTranslation();
  const [draft, setDraft] = useState("");
  const add = async () => {
    const v = draft.trim();
    if (!v) return;
    setDraft("");
    await onSave([...values, v]);
  };
  return (
    <div className={ROW} data-testid={testid}>
      <span className={LABEL}>{label}</span>
      <span className="min-w-0 flex-1 flex flex-wrap items-center gap-1.5">
        {values.map((v) => (
          <span
            key={v}
            className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full bg-paper border border-line text-ui"
          >
            {v}
            <button
              className={XBTN}
              title={t("common.remove")}
              onClick={() => onSave(values.filter((x) => x !== v))}
            >
              ×
            </button>
          </span>
        ))}
        <input
          className="flex-1 min-w-[140px] bg-transparent text-ui outline-none placeholder:text-faint"
          placeholder={placeholder}
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") add();
          }}
          onBlur={() => draft.trim() && add()}
        />
      </span>
    </div>
  );
}

function CustomGoogleAuthSection({ onChanged }: { onChanged: () => void }) {
  const [clientId, setClientId] = useState("");
  const [clientSecret, setClientSecret] = useState("");
  const [redirectUri, setRedirectUri] = useState("http://127.0.0.1:8765/v1/connectors/gmail/oauth/callback");
  const [hasSecret, setHasSecret] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [copied, setCopied] = useState(false);
  const [showSettings, setShowSettings] = useState(false);
  const [showGuide, setShowGuide] = useState(false);

  useEffect(() => {
    getGoogleCustomAuthConfig()
      .then((res) => {
        if (res.client_id) setClientId(res.client_id);
        if (res.has_secret) setHasSecret(true);
        if (res.redirect_uri) setRedirectUri(res.redirect_uri);
      })
      .catch(() => {});
  }, []);

  const handleAuthorize = async () => {
    setError("");
    if (!clientId.trim()) {
      setError("Please provide Google Client ID.");
      return;
    }
    if (!clientSecret.trim() && !hasSecret) {
      setError("Please provide Google Client Secret.");
      return;
    }
    setBusy(true);
    try {
      const res = await getGoogleCustomAuthUrl(clientId.trim(), clientSecret.trim());
      if (res.ok && res.authorize_url) {
        openExternal(res.authorize_url);
        // Poll every 2s for 30s to catch newly added account
        let count = 0;
        const timer = setInterval(() => {
          count++;
          onChanged();
          if (count >= 15) clearInterval(timer);
        }, 2000);
      } else {
        setError(res.error || "Failed to initialize Google authorization.");
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Connection error to GastroWorker server.";
      setError(msg);
    } finally {
      setTimeout(() => setBusy(false), 2500);
    }
  };

  const copyUri = () => {
    navigator.clipboard.writeText(redirectUri);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const isConfigured = Boolean(clientId.trim() && (clientSecret.trim() || hasSecret));

  return (
    <div className="mt-6 rounded-xl2 border border-line bg-panel p-4" data-testid="gmail-custom-oauth">
      <div className="flex items-center gap-2 mb-1.5">
        <span className="text-[14px] font-semibold">Google OAuth (Direct Client)</span>
        <span className="text-[11px] px-2 py-0.5 rounded-full bg-accentSoft text-accent font-medium">
          {isConfigured ? "Env Configured" : "Bypass Cloud"}
        </span>
      </div>
      <p className="text-[13px] text-muted mb-3.5 leading-relaxed">
        Sign in to Gmail using your own Google OAuth client credentials (loaded from environment), bypassing GastroWorker Cloud CASA review restrictions.
      </p>

      {/* Main Action Bar */}
      <div className="flex flex-wrap items-center gap-3 mb-3">
        <button
          type="button"
          className="px-5 py-2 rounded-full bg-accent text-white text-[13px] font-medium hover:bg-accentStrong disabled:opacity-50 cursor-pointer shadow-sm flex items-center gap-1.5"
          onClick={handleAuthorize}
          disabled={busy}
          data-testid="gmail-custom-auth-btn"
        >
          <span>↗</span>
          <span>{busy ? "Opening Google..." : "Sign in with Google"}</span>
        </button>

        <button
          type="button"
          className="text-[12px] text-muted hover:text-ink underline cursor-pointer"
          onClick={() => setShowSettings(!showSettings)}
          data-testid="gmail-custom-toggle-settings"
        >
          {showSettings ? "Hide Settings" : "Configure Credentials & Redirect URI"}
        </button>
      </div>

      {error && (
        <div className="text-[12px] text-danger bg-danger/10 p-2.5 rounded-lg border border-danger/20 mb-3">
          {error}
        </div>
      )}

      {/* Settings Panel (collapsible or expanded if not configured) */}
      {(showSettings || !isConfigured) && (
        <div className="space-y-3 pt-2 border-t border-line">
          {/* Redirect URI copy box */}
          <div className="bg-paper p-3 rounded-lg border border-line text-[12px]">
            <div className="text-muted font-medium mb-1">Authorized Redirect URI for Google Cloud Console:</div>
            <div className="flex items-center gap-2">
              <code className="font-mono text-ink bg-panel px-2 py-1 rounded border border-line flex-1 select-all overflow-x-auto text-[11.5px]">
                {redirectUri}
              </code>
              <button
                type="button"
                className="px-3 py-1 text-[12px] font-medium rounded border border-line bg-panel hover:bg-paper cursor-pointer shrink-0"
                onClick={copyUri}
              >
                {copied ? "✓ Copied" : "Copy"}
              </button>
            </div>
          </div>

          <div>
            <label className="block text-[12px] font-medium text-muted mb-1">Google Client ID (GOOGLE_CLIENT_ID)</label>
            <input
              type="text"
              className="w-full px-3 py-2 text-[13px] bg-paper rounded-lg border border-line outline-none focus:border-accent font-mono text-ink"
              placeholder="e.g. 123456789-abcdef.apps.googleusercontent.com"
              value={clientId}
              onChange={(e) => setClientId(e.target.value)}
              data-testid="gmail-custom-client-id"
            />
          </div>

          <div>
            <label className="block text-[12px] font-medium text-muted mb-1">Google Client Secret (GOOGLE_CLIENT_SECRET)</label>
            <input
              type="password"
              className="w-full px-3 py-2 text-[13px] bg-paper rounded-lg border border-line outline-none focus:border-accent font-mono text-ink"
              placeholder={hasSecret ? "•••••••••••••••• (Configured from environment)" : "e.g. GOCSPX-..."}
              value={clientSecret}
              onChange={(e) => setClientSecret(e.target.value)}
              data-testid="gmail-custom-client-secret"
            />
          </div>

          <div>
            <button
              type="button"
              className="text-[12px] text-muted hover:text-ink underline cursor-pointer"
              onClick={() => setShowGuide(!showGuide)}
            >
              {showGuide ? "Hide Setup Guide" : "View Google Cloud Console Setup Guide"}
            </button>
          </div>

          {showGuide && (
            <div className="p-3.5 bg-paper rounded-lg border border-line text-[12px] text-muted space-y-1.5 leading-relaxed">
              <div className="font-semibold text-ink">Setup Steps in Google Cloud Console:</div>
              <ol className="list-decimal list-inside space-y-1 pl-1">
                <li>Go to <a href="https://console.cloud.google.com/" target="_blank" rel="noreferrer" className="text-accent underline">Google Cloud Console</a> and create or select a project.</li>
                <li>Navigate to <b>APIs & Services</b> &gt; <b>Enabled APIs & services</b>, click <b>Enable APIs and Services</b>, search for and enable <b>Gmail API</b>.</li>
                <li>Navigate to <b>OAuth consent screen</b>, choose <b>External</b>, and add your email under <b>Test users</b>.</li>
                <li>Navigate to <b>Credentials</b> &gt; <b>Create Credentials</b> &gt; <b>OAuth client ID</b>.</li>
                <li>Set Application type to <b>Web application</b>.</li>
                <li>Under <b>Authorized redirect URIs</b>, add: <code className="bg-panel px-1 py-0.5 rounded border border-line select-all">{redirectUri}</code>.</li>
                <li>Save credentials in <code>.env</code> or enter Client ID and Client Secret above, then click <b>Sign in with Google</b>.</li>
              </ol>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
