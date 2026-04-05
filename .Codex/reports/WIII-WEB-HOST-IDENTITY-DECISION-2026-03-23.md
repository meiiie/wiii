# Wiii Web vs Host Identity Decision - 2026-03-23

## Executive Summary
- The right production direction is:
  - **Wiii web global identity stays minimal**
  - **host roles stay host-local**
  - **LMS remains a plugin/workspace surface, not the source of Wiii's selfhood**
- For the **Wiii web product**, the safest and cleanest primary identity model is:
  - `platform_role = user | platform_admin`
- Roles such as:
  - `student`
  - `teacher`
  - `lms_admin`
  - `lms_org_admin`
  should **not** be global Wiii roles.
- If Wiii itself continues to support organization governance on its own website, then that should live in a **separate Wiii-native org membership layer**, not inside the primary global role string.

## Direct Answer

### Should Wiii web only know `platform_admin` vs `user`?
- **Yes, as the primary global identity model, that is the correct target.**

### Should `teacher`, `student`, and host-side `org_admin` be treated as user on Wiii web?
- **Yes, globally.**
- Those roles should remain:
  - connector-scoped
  - workspace-scoped
  - host-session-scoped
  - capability-scoped

### Important refinement
- If Wiii web still offers **Wiii-native organization management** for org owners/admins, then keep:
  - `organization_role = member | org_admin | owner`
- But keep it as a **secondary authorization layer**, not as the main identity of the user.
- In other words:
  - Wiii is still one being
  - the user is still one canonical principal
  - host/workspace roles modify permissions and context, not personhood

## Why This Matches SOTA

### 1. OpenAI: the assistant stays the assistant; apps bring capabilities and permissions
- OpenAI's current model is explicit that apps are connected into ChatGPT as external capabilities:
  - apps can provide interactive UI
  - apps can search/reference external data
  - apps can take actions on behalf of the user
- But permissions are managed at the app/workspace layer, not by rewriting the user's core ChatGPT identity.
- OpenAI also separates:
  - workspace admin/owner permissions
  - RBAC roles for tool access
  - per-app and sometimes per-action access

Key evidence:
- OpenAI Help, updated 3 days ago:
  - `Apps let you work with external tools and information... some apps provide in-chat interactive experiences, while others securely connect to your services and data`  
  Source: <https://help.openai.com/en/articles/11487775-apps-in-chatgpt>
- Same article:
  - `Some apps may be able to take actions... apps request confirmation from you before proceeding with external actions`
  - `Enterprise/Edu admins can configure the actions an app is allowed to take, for their workspace`
  Source: <https://help.openai.com/en/articles/11487775-apps-in-chatgpt>
- OpenAI Help, updated yesterday:
  - workspace owners/admins enable apps
  - RBAC assigns app access by role
  - end users still authenticate with each app themselves before first use
  Source: <https://help.openai.com/en/articles/11509118-admin-controls-security-and-compliance-in-connectors-enterprise-edu-and-team/>
- OpenAI Help, updated 2 months ago:
  - `Existing roles (Member, Admin, Owner) only govern workspace-management rights`
  - custom RBAC controls end-user access to tools/features separately
  Source: <https://help.openai.com/en/articles/11750701>

Conclusion:
- OpenAI's pattern supports:
  - minimal principal identity
  - separate workspace/admin roles
  - separate app/action permissions
- This maps strongly to:
  - Wiii global identity
  - Wiii-native org governance
  - host-local capability overlays

### 2. Anthropic: Claude stays Claude; connected services act under the user's permissions in that service
- Anthropic's current connector docs are even more aligned with the user's intuition here.
- Claude can:
  - access apps/services
  - retrieve data
  - take actions inside connected services
- But that authority is based on the user's permissions in the connected service.
- Anthropic also separates:
  - Claude Console org roles
  - workspace-level permissions
  - connector access and authentication

Key evidence:
- Anthropic Help, updated this week:
  - `Connectors let Claude access your apps and services, retrieve your data, and take actions within connected services`
  - `Connectors work across Claude, Claude Desktop, Claude Code, and the API`
  Source: <https://support.claude.com/en/articles/11176164-use-connectors-to-extend-claude-s-capabilities>
- Same article:
  - when connecting a service, the user is granting Claude permission to act `based on your account permissions`
  Source: <https://support.claude.com/en/articles/11176164-use-connectors-to-extend-claude-s-capabilities>
- Anthropic Help, updated this week:
  - organization owners enable connectors for the team
  - individual users still authenticate themselves
  - access permissions are enforced at the user level
  Source: <https://support.claude.com/en/articles/11176164-use-connectors-to-extend-claude-s-capabilities>
- Anthropic Help, updated over a week ago:
  - local desktop extensions vs remote connectors are explicitly different surfaces
  - remote connectors are for shared/cloud/team workspaces
  Source: <https://support.claude.com/en/articles/11725091-when-to-use-desktop-and-web-connectors>
- Anthropic Help, updated this week:
  - `Organization-level roles serve as a baseline, while Workspace roles can grant additional permissions`
  Source: <https://support.claude.com/en/articles/10186004-claude-console-roles-and-permissions>

Conclusion:
- Anthropic is effectively using a layered model:
  - assistant identity
  - org baseline permissions
  - workspace-specific permissions
  - connector-scoped user authentication
- That is very close to the architecture Wiii should adopt.

### 3. Google: start with one strong agent and attach tools/context around it
- Google Cloud's reference architecture uses a **single-agent** baseline with MCP/tool access.
- Google Research's January 28, 2026 study also shows that multi-agent coordination can hurt sequential workflows.

Key evidence:
- Google Cloud Architecture Center:
  - `This document provides a reference architecture to help you design a single-agent AI system`
  - the agent uses MCP to access multiple sources/tools
  Source: <https://docs.cloud.google.com/architecture/single-agent-ai-system-adk-cloud-run>
- Google Research, January 28, 2026:
  - multi-agent setups improve parallel tasks
  - but degrade sequential ones
  - `every multi-agent variant ... degraded performance by 39-70%` on sequential reasoning tasks
  Source: <https://research.google/blog/towards-a-science-of-scaling-agent-systems-when-and-why-agent-systems-work/>

Conclusion:
- Wiii should stay one canonical agent.
- Hosts/workspaces should be layered around that agent.
- We should not create identity fragmentation by letting each host define a new "kind of Wiii account".

### 4. Anthropic context engineering + Letta memory blocks both support a layered-self model
- Anthropic's context engineering guidance says modern agent quality comes from curating the full context state, not just prompt wording.
- Letta's memory model keeps persona and human memory as persistent, structured context blocks that stay visible to the agent.

Key evidence:
- Anthropic Engineering:
  - context engineering is about curating the whole context state, including tools, MCP, external data, and message history
  Source: <https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents>
- Letta Docs:
  - memory blocks persist across interactions
  - `persona` and `human` are canonical examples
  - blocks can be read-only or shared
  Source: <https://docs.letta.com/guides/core-concepts/memory/memory-blocks>

Conclusion:
- Wiii's selfhood should remain persistent and layered.
- Host context should be injected as structured context/capability state, not as a rewrite of identity.

### 5. MCP Apps confirms the plugin-host model for rich UI
- MCP Apps formalizes interactive UI as tools returning UI rendered inside the host.
- This supports the idea that LMS is a **host/plugin surface** and Wiii remains the trusted central agent.

Key evidence:
- MCP Apps blog, January 26, 2026:
  - tools can return interactive UI
  - host renders the UI in a sandboxed iframe
  - user interaction and tool calls stay auditable and approval-aware
  Source: <https://blog.modelcontextprotocol.io/posts/2026-01-26-mcp-apps/>
- MCP extension matrix:
  - authorization extensions and UI extensions are explicit, opt-in layers
  Source: <https://modelcontextprotocol.io/extensions/client-matrix>

Conclusion:
- LMS sidebar is the right shape:
  - Wiii remains the main agent
  - LMS provides a host surface, permissions, context, and action bridge

## Product Decision for Wiii

## 1. Canonical Wiii identity on Wiii web
- Primary global identity should be:
  - `platform_role = user | platform_admin`

This means:
- `platform_admin` is only for true Wiii platform operators
- everyone else is just `user` at the platform identity layer

This is the cleanest model for:
- Wiii web
- future multi-host expansion
- protecting Wiii's identity as one living agent

## 2. Wiii-native organization authority is separate
- If Wiii itself continues to support:
  - org admin dashboards
  - org settings
  - org-level governance
  - org-level capability policy
then keep:
  - `organization_role = member | org_admin | owner`

But:
- do **not** surface this as the primary role identity
- do **not** mix it with host roles
- do **not** let it change Wiii's persona framing

This is a governance layer, not a selfhood layer.

## 3. Host roles are overlays, not identity
- For LMS and future hosts, use:
  - `host_id`
  - `connector_id`
  - `host_user_id`
  - `host_org_id`
  - `host_role`
  - `page_type`
  - `workflow_stage`
  - `capabilities`
  - `action_surfaces`

Examples:
- In LMS sidebar:
  - `host_role=teacher`
  - `page_type=course_editor`
  - `workflow_stage=review_outline`
- On Wiii web:
  - same canonical Wiii user
  - no active LMS page context unless explicitly connected/selected

## 4. Right sidebar remains the correct posture for LMS
- The current `right sidebar embedded operator` direction is still correct.
- LMS should not feel like "a second Wiii identity".
- It should feel like:
  - Wiii is here
  - Wiii understands this page
  - Wiii knows what this host allows
  - Wiii can act through approved host actions

This is closer to:
- ChatGPT apps
- Claude connectors
- MCP apps
than to a hard LMS-native assistant clone.

## 5. Connected workspaces should be built after the role split is frozen
- We should **not** rush `connected_workspaces / host_session` as a first-class product model before identity semantics are fully frozen.
- Otherwise we risk encoding the wrong abstraction into storage and UI.

The right order is:
1. Freeze the identity split.
2. Freeze authorization boundaries.
3. Freeze host capability semantics.
4. Then build connected workspaces UX on top.

## Recommended Architecture

## Layer 1 — Canonical Principal
- One human user across:
  - Wiii web
  - LMS
  - future hosts
- Never becomes globally `teacher` or `student`

Fields:
- `user_id`
- `platform_role`
- basic profile/auth identities

## Layer 2 — Wiii-native Org Membership
- Optional, if Wiii's own org management remains a product surface

Fields:
- `organization_id`
- `organization_role`
- org-scoped permissions/policies

## Layer 3 — Connected Workspace / Connector Grant
- A durable record that user X connected host Y/workspace Z

Fields:
- `connector_id`
- `host_id`
- `host_workspace_id`
- `host_account_id`
- `granted_capabilities`
- auth metadata / token health
- sync metadata / last seen

This is not yet the live page/session.

## Layer 4 — Host Session
- Ephemeral runtime overlay for an active embedded or connected host context

Fields:
- `host_role`
- `page_type`
- `workflow_stage`
- `selection`
- `editable_scope`
- `entity_refs`
- `action surfaces`

This layer drives:
- prompt overlay
- skill selection
- action tools
- safety behavior

## What Should Change In The Current Wiii Plan

### Keep
- Identity V2 compatibility direction
- capability-first host behavior
- right sidebar embedded operator
- preview -> confirm -> apply
- host action audit

### Change
- Stop thinking of `teacher/student/org_admin` as future global roles to preserve anywhere in Wiii web identity
- Do **not** make `connected_workspaces` the source of identity semantics
- Do **not** continue designing around legacy `users.role`
- Do **not** let LMS org admin map upward into Wiii platform admin

### New formal decision
- `platform_role` becomes the only primary global role field worth exposing prominently in Wiii web:
  - `user`
  - `platform_admin`

## Revised Production Build Order

## Phase 0 — Freeze the role model
- Officially declare:
  - `platform_role` = `user | platform_admin`
  - `organization_role` = Wiii-native org governance only
  - `host_role` = connector/host/session-only
- Update design docs and reports first

## Phase 1 — Finish compatibility hardening
- Keep current compatibility layer
- Continue replacing legacy platform-admin checks with `is_platform_admin(...)`
- Ensure no LMS host role can elevate to platform admin

## Phase 2 — Persistence cleanup
- Remove `users.role` as the source of truth
- Persist:
  - `platform_role`
  - Wiii-native org memberships
- Keep legacy role only as compatibility/fallback

## Phase 3 — Connector grant model
- Create a durable model for:
  - connected workspaces
  - connector grants
  - auth state
  - capability baselines
- This should be durable but separate from live page/session context

## Phase 4 — Host session model
- Formalize active host session as runtime context
- This is where:
  - `teacher/student`
  - current page
  - current lesson
  - current editable scope
  live

## Phase 5 — Wiii web UX
- Add a `Connected workspaces` concept on Wiii web
- But present it as:
  - where Wiii can work
  - what systems are connected
  - what workspace is currently active
- not as:
  - "your identity has changed into teacher"

## Phase 6 — Legacy cleanup
- Retire:
  - legacy `X-Role` assumptions
  - analytics/admin paths that still think `users.role` is the truth
  - prompt branches keyed on platform role strings that really mean host role

## Concrete Recommendation For The Repository Right Now
- Do **not** implement `connected_workspaces / host_session` next as the headline feature.
- Instead, next architectural move should be:
  - freeze the identity semantics in docs
  - align code and APIs to the new contract
  - then build workspace/session models on top

### Immediate next implementation target
- `P3A — Role Semantics Freeze`
  - audit all remaining platform/global uses of `role`
  - stop exposing teacher/student/admin as meaningful Wiii-web identity concepts
  - keep org governance separate

### Only after that
- `P3B — Connected Workspace Registry`
- `P3C — Host Session Runtime`

## Final Judgment
- The user's intuition is correct.
- On **Wiii web**, primary identity should basically be:
  - `platform_admin`
  - `user`
- `teacher`, `student`, and LMS-side admin roles should remain host-local overlays.
- If Wiii needs its own org governance, keep that as a separate scoped authorization layer.
- This is the most SOTA, least identity-distorting, and most multi-host-correct path for Wiii.

## Sources
- OpenAI Help: Apps in ChatGPT  
  <https://help.openai.com/en/articles/11487775-apps-in-chatgpt>
- OpenAI Help: Admin Controls, Security, and Compliance in apps  
  <https://help.openai.com/en/articles/11509118-admin-controls-security-and-compliance-in-connectors-enterprise-edu-and-team/>
- OpenAI Help: RBAC  
  <https://help.openai.com/en/articles/11750701>
- OpenAI Help: Developer mode, and MCP apps in ChatGPT  
  <https://help.openai.com/en/articles/12584461>
- OpenAI: Introducing apps in ChatGPT and the new Apps SDK  
  <https://openai.com/index/introducing-apps-in-chatgpt/>
- OpenAI: A practical guide to building agents  
  <https://openai.com/business/guides-and-resources/a-practical-guide-to-building-ai-agents/>
- Anthropic Help: Use connectors to extend Claude's capabilities  
  <https://support.claude.com/en/articles/11176164-use-connectors-to-extend-claude-s-capabilities>
- Anthropic Help: When to use desktop and web connectors  
  <https://support.claude.com/en/articles/11725091-when-to-use-desktop-and-web-connectors>
- Anthropic Help: Claude Console Roles and Permissions  
  <https://support.claude.com/en/articles/10186004-claude-console-roles-and-permissions>
- Anthropic Help: Use the Connectors Directory to extend Claude's capabilities  
  <https://support.claude.com/en/articles/11724452-use-the-connectors-directory-to-extend-claude-s-capabilities>
- Anthropic Engineering: Effective context engineering for AI agents  
  <https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents>
- Google Cloud Architecture Center: Single-agent AI system using ADK and Cloud Run  
  <https://docs.cloud.google.com/architecture/single-agent-ai-system-adk-cloud-run>
- Google Research: Towards a science of scaling agent systems  
  <https://research.google/blog/towards-a-science-of-scaling-agent-systems-when-and-why-agent-systems-work/>
- MCP Blog: MCP Apps - Bringing UI Capabilities To MCP Clients  
  <https://blog.modelcontextprotocol.io/posts/2026-01-26-mcp-apps/>
- MCP Docs: Extension Support Matrix  
  <https://modelcontextprotocol.io/extensions/client-matrix>
- Letta Docs: Memory blocks (core memory)  
  <https://docs.letta.com/guides/core-concepts/memory/memory-blocks>
