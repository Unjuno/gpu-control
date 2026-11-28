# Retired GitHub Comment Bridge

The GitHub comment-to-Gateway implementation and its retired CLI, FastAPI
routes, policy and tests have been removed from the active source tree. The
historical implementation remains available in Git history and dated
acceptance records; it is not a supported integration.

The current `project_control/` package and `.github/workflows/project-checks-ci.yml`
own the separate GitHub Project Checks workflow. It does not invoke or depend
on the legacy Gateway. GPU experiments use the authenticated Sites MCP path.
