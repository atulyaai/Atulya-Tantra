import { GmailOAuth } from "mcp-gmail";

const clientId = process.env.GOOGLE_CLIENT_ID;
const clientSecret = process.env.GOOGLE_CLIENT_SECRET;
const port = Number(process.env.GMAIL_OAUTH_PORT || "3000");

if (!clientId || !clientSecret) {
  console.error("Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET before running this script.");
  process.exit(1);
}

const oauth = new GmailOAuth({
  clientId,
  clientSecret,
});

const tokens = await oauth.authorize({
  port,
  scopes: [
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/gmail.settings.basic",
  ],
});

if (!tokens?.refresh_token) {
  console.error("OAuth finished, but no refresh token was returned. Revoke the app grant and retry with offline access.");
  process.exit(1);
}

console.log(`GMAIL_REFRESH_TOKEN=${tokens.refresh_token}`);
