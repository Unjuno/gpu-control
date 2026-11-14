-- Record whether the one-use plan approval came from the authenticated Site
-- confirmation page or ChatGPT's confirmed MCP write action.
ALTER TABLE human_authorizations
  ADD COLUMN authorization_source TEXT NOT NULL DEFAULT 'site_confirmation'
  CHECK (authorization_source IN ('site_confirmation', 'chatgpt_mcp_write_confirmation'));

PRAGMA foreign_key_check;
