# Computer control isolation — release correction #959

Status: In progress; not a closed security finding or release acceptance.

The owner approved completing the remaining runtime corrections before the
official Windows/Linux/macOS release. The signed-in Computer and its volume
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

## Remaining boundary — do not conflate with the first

This transport correction alone does not isolate X11, AT-SPI, Chrome DevTools
or arbitrary programs already launched inside the shared guest desktop.
Human takeover of Wiii does not by itself stop an application's independent
automation. #959 remains open until those control surfaces are addressed or
a different explicitly approved execution boundary is implemented. Do not
describe a private socket as a hostile-application sandbox.

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
- Separate retained-automation and takeover tests are mandatory before #959
  can close. Current Windows host packaging does not prove Unix harness support.
