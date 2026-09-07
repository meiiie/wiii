# Computer control isolation — release correction #959

Status: Private transport and owned-input revocation verified locally;
release integration and broader guest isolation remain separate.

The owner narrowed the first official release to Windows on 2026-09-07 and
prioritized revocation of Wiii-scheduled input. The signed-in Computer and its volume
are outside test scope. Use disposable environments only.

## First boundary: Wiii control transport

The old unauthenticated TCP listener on guest loopback accepted semantic
commands from any desktop application. A native display lease check was not
on that path. Replace it with a filesystem Unix socket created by trusted
startup inside a root-owned 0700 temporary directory. Only a host-initiated
root Docker exec may connect; the server also verifies kernel peer credentials.

The listener drops supplementary groups and UID/GID before loading the desktop
session. It becomes non-dumpable so same-UID workloads cannot obtain its open
socket through procfs or ptrace. Desktop applications and every terminal,
browser and Work Plane exec remain UID 10001, without effective capabilities.
Only trusted startup has SETUID/SETGID, not SYS_ADMIN or host networking.
There is no shared bearer secret to recover from the profile, environment,
transcript, application directory or source mount.

Failure to bind, drop privileges, protect descriptors or resolve the desktop
session leaves the Computer unhealthy. It must not fall back to public TCP.
Profile storage and source mounts are unchanged. A new pack identity prevents
silent reuse of the old listener; failed replacement retains the existing
provider rollback behavior.

## Second boundary: revocable Wiii input execution

Pack `semantic-v43` starts with no active input authority. The native seat
service activates an opaque lease through the private transport; every action
must present that exact lease again at execution time, after waiting in the
semantic queue. A stale or revoked lease cannot reactivate itself.

Seat transitions use a separate native mutex, not the mutex held by running
actions. Human takeover and release first cancel provider input, then update
the durable seat. Project revocation, switching, suspend, reset and removal
also enter this barrier before waiting for active work. Ordinary source/Office
work retains its separate Project authority; display handoff does not revoke it.

The provider cancellation route bypasses the action queue. It invalidates the
lease before waiting for the active action to become quiescent. Every CDP send,
native accessibility mutation and app launch checks cancellation at dispatch;
key holds and waits are interruptible. Cleanup releases keys/buttons even when
their press response was lost. Owned stepped-clock workers are terminated and
joined, and paused targets are resumed before acknowledging takeover.

An acknowledgement means the old Wiii input executor is quiescent, including
held-input cleanup. A timeout, mismatched active authority or unconfirmed cleanup
must not return success or enable a new lease. Repeating release can reconcile
an uncertain response without repeating the interrupted action. The action
reports interruption, not rollback: effects already delivered may remain and a
fresh observation is required. Observe itself never grants control.

Native dispatch does not hold the cancellation condition across a potentially
blocking call. Revocation can therefore invalidate the lease and reach its
quiescence deadline while that call is blocked. The active action remains owned
until it exits, so a timeout never acknowledges takeover or permits a new lease.

Profile files, sign-ins and ordinary application processes are preserved. The
standalone semantic `act` CLI is no longer an authority bypass. Tiny scoped
workstation observations preserve their scope when resolving a launcher action;
the cancellation test must not disable stale-state checks to reach dispatch.

## Separate threat boundary

This transport correction alone does not isolate X11, AT-SPI, Chrome DevTools
or arbitrary programs already launched inside the shared guest desktop.
Human takeover stops Wiii's owned input execution, not an application's
independent automation or arbitrary code it already runs. This pilot is a
same-user desktop, not a hostile-application or multi-tenant sandbox. Do not
claim cancellation of all guest programs from the private socket or input lease.

## Verification

- 2026-09-07: eight disposable Linux process tests passed using the production
  control transport and HTTP handler: privileged host request accepted; workload
  connection, directory replacement and procfs descriptor recovery denied.
- Privileged curl explicitly disables automatic config loading before all other
  arguments. An unprivileged workload's curlrc redirects the unprotected control
  read in the negative fixture, but cannot affect the corrected invocation.
  The live native provider also observes successfully with a hostile profile
  curlrc present; the health-check commands use the same protection.
- Actual v41 image built on Docker Desktop 29.7.2. Native Windows live pack
  reconciliation passed: failed replacement rolled back, successful replacement
  preserved a fixture profile marker, four-node semantic observation found
  `app:browser`, terminal identity was UID 10001 and direct socket access failed.
  The fixture container, volume and temporary host directory were removed.
- Guest TCP port 9234 has no listener. Desktop/control worker and terminal
  workloads have UID 10001 and zero effective capabilities.
- Windows: 132 native Neko unit cases passed, one Docker case ignored in that
  suite and then executed separately as above; 114 semantic cases ran with one
  POSIX-only case skipped. CI adds a separate Linux kernel-boundary job.
- 2026-09-07, v42: ten new input-revocation cases passed, including concurrent
  HTTP action/revoke, queued old requests, lost press responses, cleanup failure,
  mismatched authority and timeout reconciliation. Semantic contracts: 114
  passed, one POSIX case skipped on Windows. Eight isolated Linux kernel/private
  transport cases passed on the actual v42 image.
- Native Windows + actual Chrome: a four-step/eight-second input sequence was
  interrupted; every received key-down had a matching key-up. The final run
  stopped after one key pair and acknowledged native takeover in 954 ms. An
  earlier run with duplicate cleanup took 5,645 ms and stopped after two pairs.
  These are individual native-call timings, not UI end-to-end or a latency SLA.
  Both native and provider paths refused subsequent old-lease input; the page
  event log did not change after acknowledgement. The fixture profile marker
  survived. Only the disposable container, volume and temporary directory were
  removed. No signed-in profile or user Computer was reset.
- The first live attempts correctly failed on a scoped-launcher stale-state
  defect before input delivery. Scope preservation was fixed with its own
  regression; stale validation was not weakened to make the takeover test pass.
- Final native Neko suite: 132 passed, two live tests ignored in the ordinary
  suite, five unrelated cases filtered; the takeover live test ran separately
  as above. Clippy passed with warnings denied. The v42 image was rebuilt.
- Unix harness execution is deferred, not a blocker for Windows-only release.
  Installed desktop/real ACP session acceptance is not inferred from these tests.
- The blocked-native-dispatch regression first failed on the previous lock
  placement, then passed after moving dispatch outside the condition. All eleven
  revocation cases passed; an in-flight call may finish after a timeout, but
  subsequent input is refused and only successful reconciliation acknowledges
  quiescence. This does not claim preemption of an arbitrary native OS call.
- Pack v43 was rebuilt and the actual Windows/Chrome takeover passed in
  2,217 ms after two key pairs, with no post-ack input and the fixture profile
  retained (65.81 s total including setup/readback/cleanup). Native serial
  execution passed 132 tests, with two live cases ignored and the takeover
  case executed separately; Clippy passed. An earlier parallel native run had
  four provider startup/process timing failures (128 passes). Serial success
  does not erase those load-sensitive failures or prove an end-to-end SLA.
