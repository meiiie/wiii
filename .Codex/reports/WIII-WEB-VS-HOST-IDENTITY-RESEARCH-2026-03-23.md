# Wiii Web vs Host Identity Research - 2026-03-23

## Question

Should Wiii web keep only a minimal canonical role model, such as:

- `platform_admin`
- `user`

while roles like:

- `student`
- `teacher`
- `org_admin`

are treated as host- or workspace-local context instead of global Wiii identity?

## Short Answer

Yes, that is the right direction.

But with one important refinement:

- On **Wiii web**, canonical identity should be minimal:
  - `platform_admin`
  - `user`
- If Wiii itself continues to have multi-tenant org governance, then Wiii may also keep:
  - `organization membership role` for Wiii-native orgs
- Roles like `teacher`, `student`, `LMS admin`, `LMS org admin` should **not** be global Wiii roles.
  - They should live in:
    - `host context`
    - `workspace context`
    - `capability contract`
    - `active host session`

That means:

- Wiii web stays Wiii-first
- LMS iframe/sidebar stays host-aware
- the same human can move between Wiii web and LMS without Wiii's identity being rewritten

## Why This Matches SOTA as of March 23, 2026

### 1. OpenAI Apps: app identity is not the same thing as ChatGPT identity

OpenAI's app model makes a very clear separation:

- ChatGPT remains the assistant
- apps bring their own backend, interface, and permissions
- existing customers can log in to the app and access premium or account-specific features

This is a strong signal that:

- host/app/workspace permissions should be attached to the connected integration
- not promoted into the assistant's global account identity

Source:

- OpenAI, **October 6, 2025**: [Introducing apps in ChatGPT and the new Apps SDK](https://openai.com/index/introducing-apps-in-chatgpt/)

### 2. Anthropic Connectors: Claude stays Claude; permissions come from the connected tool

Anthropic's connectors documentation is even more direct:

- users connect tools to Claude
- Claude can access or modify data **based on the user's permissions inside that connected service**
- connectors are account/workspace scoped

That means:

- Claude does not become a Jira admin globally because you connected Jira
- Claude gains action authority inside the connected workspace, under that workspace's permissions

Sources:

- Anthropic Help, updated over 2 weeks ago: [Connect your tools to unlock a smarter, more capable AI companion](https://support.anthropic.com/en/articles/11817150-connect-your-tools-to-unlock-a-smarter-more-capable-ai-companion)
- Anthropic Help, updated yesterday: [Pre-built integrations using remote MCP](https://support.anthropic.com/en/articles/11176164-pre-built-integrations-using-remote-mcp)
- Anthropic Help: [Browsing and connecting to tools from the directory](https://support.anthropic.com/en/articles/11724452-browsing-and-connecting-to-tools-from-the-directory)

### 3. Anthropic workspace roles are layered, not flattened

Anthropic's own API Console docs separate:

- org-level roles
- workspace-level permissions

and explicitly say workspace roles can grant additional permissions on top of organization roles.

That is very close to the model Wiii should adopt:

- canonical Wiii role
- Wiii org role
- host/workspace role

Source:

- Anthropic Help, updated over 2 weeks ago: [API Console roles and permissions](https://support.anthropic.com/en/articles/10186004-api-console-roles-and-permissions)

### 4. Google: single primary agent + tools is the baseline

Google's current guidance continues to support:

- one main agent
- external tools and systems attached around it
- architecture chosen according to the task

Their January 28, 2026 research also shows multi-agent coordination often hurts sequential tasks.

This supports:

- one canonical Wiii
- multiple host/workspace overlays
- specialized context and tools rather than multiple identity copies

Sources:

- Google Cloud docs: [Single-agent AI system using ADK and Cloud Run](https://docs.cloud.google.com/architecture/single-agent-ai-system-adk-cloud-run)
- Google Research, **January 28, 2026**: [Towards a science of scaling agent systems](https://research.google/blog/towards-a-science-of-scaling-agent-systems-when-and-why-agent-systems-work/)

### 5. MCP Apps and enterprise auth point the same way

The MCP ecosystem now has explicit concepts for:

- interactive UI
- OAuth client credentials
- enterprise-managed authorization

That is another signal that:

- auth and permissions should be first-class integration/session concepts
- not hidden inside one overloaded `role` string

Sources:

- MCP blog, **January 26, 2026**: [MCP Apps - Bringing UI Capabilities To MCP Clients](https://blog.modelcontextprotocol.io/posts/2026-01-26-mcp-apps/)
- MCP docs: [Extension Support Matrix](https://modelcontextprotocol.io/extensions/client-matrix)

### 6. Letta: persistent self is separate from external context

Letta's memory blocks remain one of the clearest formalizations of long-lived agent identity:

- `persona`
- `human`
- other structured blocks

The important architectural lesson is:

- the assistant's self-concept should persist
- external context should be layered into context, not overwrite the self-model

Sources:

- Letta Docs: [Memory blocks (core memory)](https://docs.letta.com/guides/core-concepts/memory/memory-blocks)
- Letta Docs: [Context engineering](https://docs.letta.com/guides/agents/context-engineering)

## Design Conclusion for Wiii

### Canonical identity on Wiii web

Wiii web should model only:

- `platform_role`
  - `platform_admin`
  - `user`
- optionally, Wiii-native organization membership if Wiii itself still has org management:
  - `member`
  - `org_admin`
  - `owner`

It should **not** expose or persist `teacher/student/LMS admin` as global Wiii identity.

### Host-local identity

Inside LMS or any other embedded host, Wiii should receive:

- `host_id`
- `connector_id`
- `host_user_id`
- `host_org_id`
- `host_role`
- `page_type`
- `workflow_stage`
- `capabilities`
- `action surfaces`

This is what should drive behavior inside the iframe/sidebar.

### Wiii web behavior

When a user later visits Wiii web directly:

- they remain the same Wiii user
- Wiii can know they have connected workspaces
- Wiii can optionally activate one workspace context
- but Wiii should not globally "become a teacher"

## Recommended Product Rule

### Wiii Web

Keep it simple:

- `platform_admin` if the account is truly Wiii platform admin
- everyone else = `user`

If Wiii-native org governance remains part of the product, keep that in a separate org-membership layer, not in the primary identity role.

### Embedded LMS sidebar

Use:

- `host_role`
- `capabilities`
- `current page`
- `current workflow`

to decide what Wiii can do.

This means:

- teacher powers are active in the LMS host session
- not in Wiii's permanent self-definition

## Implication for Current Work

Before building a full `connected workspace` UI, the next design decision should be:

### Adopt this identity split formally

- `platform_role`: Wiii-wide authority only
- `organization_role`: Wiii-native org authority only
- `host_role`: external/local host authority only

### Stop promoting host roles into Wiii identity

- `teacher/student/admin/org_admin` from LMS should stop being treated as global account roles

### Keep Wiii's personality singular

This is also the right move for Wiii's "living agent" design:

- Wiii remains one being
- different sites only change what Wiii can see and do
- not who Wiii fundamentally is

That matches the product intuition behind agents like AIRI or Neuro-sama more closely too.

This last point is an inference from product behavior and identity design style, not a formal citation from their engineering docs.

## Revised Build Order

1. Freeze the canonical Wiii web identity model:
   - `platform_admin | user`
   - optional Wiii-native org membership layer
2. Formalize host-local identity:
   - `host_role`
   - `host_org`
   - `capabilities`
   - `page/workflow context`
3. Keep iframe/sidebar behavior host-aware but identity-safe.
4. Only after that, build:
   - connected workspaces
   - host session switching
   - capability-first behavior routing
5. Then deprecate remaining legacy `X-Role` and `users.role` assumptions.

## Final Recommendation

Yes:

- on Wiii web, you should likely keep only `platform_admin` vs `user` as the main identity split
- and treat `teacher/student/org admin` mostly as workspace/host-local context

This is the cleaner, more modern, and more multi-host-correct architecture.

It preserves Wiii as the primary living agent while allowing LMS and future sites to plug into Wiii as contextual surfaces.
