---
id: com.argo.github
name: GitHub
version: "1.0.0"
description: Manage GitHub repositories, issues, and PRs via GitHub REST API
author: argo
tool_refs: [http_fetch, http_post]
tools: []
triggers: [github, repo, issue, pr, pull request, ci]
---

Auth: Authorization: Bearer {ARGO_GITHUB_TOKEN}, Accept: application/vnd.github.v3+json, X-GitHub-Api-Version: 2022-11-28

## Instructions

- list_repos: GET https://api.github.com/user/repos?affiliation=owner&sort=pushed&per_page=30
- list_issues: GET https://api.github.com/repos/{owner}/{repo}/issues?state=open&per_page=20
- create_issue: POST https://api.github.com/repos/{owner}/{repo}/issues body {"title":"...","body":"...","labels":["..."],"assignees":["..."]}
- list_prs: GET https://api.github.com/repos/{owner}/{repo}/pulls?state=open&sort=created&direction=desc
- get_pr: GET https://api.github.com/repos/{owner}/{repo}/pulls/{number}
- create_pr_comment: POST https://api.github.com/repos/{owner}/{repo}/issues/{number}/comments body {"body":"..."}
- get_runs: GET https://api.github.com/repos/{owner}/{repo}/actions/runs?per_page=10
- list_releases: GET https://api.github.com/repos/{owner}/{repo}/releases?per_page=10
- merge_pr: PUT https://api.github.com/repos/{owner}/{repo}/pulls/{number}/merge body {"merge_method":"squash","commit_title":"..."}