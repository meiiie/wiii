# Computer image boundary

This is the optional Linux Computer pilot, not a standalone agent API or a
multi-tenant sandbox. The desktop native `NekoComputerService` owns Project
grants, environment routing, leases, durable request IDs and unknown outcomes.
`DockerComputerProvider` invokes these private adapters only after that gate.

The semantic HTTP endpoint binds only to guest loopback. It is reached through
`docker exec` into the environment selected by the native provider; port 9234
must not be published. The Work Plane bridge is a one-request stdin/stdout
process, not a public service. Its `optimistic_idempotent` descriptor describes
the end-to-end native contract, not independent replay protection in this
Python process. Do not connect a harness directly to either adapter.

The native integration must retain these tests before enabling the image:

- `work_plane_replays_completed_transactions_without_a_display_lease`
- `work_plane_lost_response_is_unknown_and_never_reexecutes_the_effect`
- environment/Project grant rejection and semantic lease cleanup tests

One control request runs at a time; event long-polls and health checks remain
independent. Observations redact protected control contents. Protected Project
paths are excluded from enumeration, direct reads and mutations.

Browser control actions re-read the observed scope before checking its version;
an old locator cache cannot authorize a mutation. Generic browser `invoke`
reports dispatch completion but leaves the task effect unverified: background
animations, arbitrary new tabs and global DOM changes are not action evidence.
The caller must observe again and must not automatically repeat the mutation.
Typed adapter readback remains the route to confirmed task-level outcomes.

The panel and desktop use the same managed launchers and persistent profile.
Event gaps are computed per consumer cursor, not globally when the ring wraps.

## Pilot trust limitation

Project path checks reject traversal and existing symlinks, but do not provide
an atomic no-follow guarantee against a concurrent process replacing a parent
directory. Guest applications run under the same OS user and already share its
Project/profile authority; this image does not isolate mutually hostile guest
applications. Do not mount untrusted concurrently modified worktrees or run
untrusted software in a signed-in Computer. Multi-tenant/cloud deployment and
claims of adversarial filesystem confinement require descriptor-relative I/O
and staged Office writes first. This remains an explicit hardening gap, not a
passed security test.

The image alone does not prove native authority or live application behavior.
Protocol fixtures do not replace installer, account or end-to-end acceptance.
