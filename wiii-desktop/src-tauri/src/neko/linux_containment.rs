//! Linux local-provider containment via bubblewrap (`bwrap`).
//!
//! Goal: mirror Windows Job Object kill-on-close / killable process-tree
//! semantics as closely as practical for same-UID provider children:
//! - `--die-with-parent` — provider supervisor dies if Wiii dies
//!   (PR_SET_PDEATHSIG). The actual `Command::spawn` MUST run on a
//!   process-lifetime thread (see `spawn_linux_child_on_stable_parent_thread`);
//!   Tokio `spawn_blocking` workers exit after ~10s idle and would otherwise
//!   SIGKILL a live ACP session.
//! - `--unshare-pid --as-pid-1` — provider runs as PID 1 in a new PID
//!   namespace so leftovers are torn down when that leader exits, and killing
//!   the outer `bwrap` supervisor collapses the namespaced tree
//!
//! This is **not** claimed to be perfect escape-proof equivalence to Windows
//! Job Objects (user-namespace / bind-mount edge cases remain). It is the
//! approved Linux enablement path: fail closed when `bwrap` is missing or
//! cannot create the PID namespace.
//!
//! Project sessions retain host filesystem access. Quick Chat additionally
//! mounts the host read-only, with explicit state, scratch and temporary roots.

use std::ffi::{CString, OsString};
use std::io;
use std::path::PathBuf;
use std::process::Command;
#[cfg(test)]
use std::cell::Cell;
#[cfg(test)]
use std::path::Path;

// Thread-local so parallel cargo tests cannot race a process-global force flag.
#[cfg(test)]
thread_local! {
    static FORCE_UNAVAILABLE: Cell<bool> = const { Cell::new(false) };
}

/// Test-only: force the host to report bubblewrap containment as missing.
#[cfg(test)]
pub(crate) fn force_unavailable_for_test(force: bool) {
    FORCE_UNAVAILABLE.with(|flag| flag.set(force));
}

#[cfg(not(test))]
#[allow(dead_code)]
fn force_unavailable_active() -> bool {
    false
}

#[cfg(test)]
fn force_unavailable_active() -> bool {
    FORCE_UNAVAILABLE.with(|flag| flag.get())
}

/// Resolve a canonical `bwrap` binary, or `None` if containment cannot be offered.
pub(crate) fn bwrap_path() -> Option<PathBuf> {
    if force_unavailable_active() {
        return None;
    }
    resolve_bwrap_path_from_env()
}

fn resolve_bwrap_path_from_env() -> Option<PathBuf> {
    let path = std::env::var_os("PATH").unwrap_or_default();
    for directory in std::env::split_paths(&path) {
        if let Some(resolved) = accept_bwrap_candidate(directory.join("bwrap")) {
            return Some(resolved);
        }
    }
    accept_bwrap_candidate(PathBuf::from("/usr/bin/bwrap"))
}

fn accept_bwrap_candidate(candidate: PathBuf) -> Option<PathBuf> {
    let canonical = std::fs::canonicalize(&candidate).ok()?;
    let meta = std::fs::metadata(&canonical).ok()?;
    if meta.is_file() {
        Some(canonical)
    } else {
        None
    }
}

/// True when a usable bubblewrap PID-namespace supervisor is available.
pub(crate) fn containment_available() -> bool {
    if force_unavailable_active() {
        return false;
    }
    static AVAILABLE: std::sync::OnceLock<bool> = std::sync::OnceLock::new();
    *AVAILABLE.get_or_init(probe_bwrap_capability)
}

fn probe_bwrap_capability() -> bool {
    // Use the env lookup directly so test force-flags cannot poison OnceLock.
    let Some(bwrap) = resolve_bwrap_path_from_env() else {
        return false;
    };
    // Capability probe: namespaces must actually work, not merely exist on PATH.
    let mut probe = Command::new(&bwrap);
    probe.args([
        "--unshare-pid",
        "--as-pid-1",
        "--die-with-parent",
        "--dev-bind",
        "/",
        "/",
        "--proc",
        "/proc",
        "--",
        "true",
    ]);
    match probe.output() {
        Ok(output) => output.status.success(),
        Err(_) => false,
    }
}

/// Rewrite the soon-to-be-spawned child so it `exec`s `bwrap` while preserving
/// stdio/cwd/env already configured on `command` (via `pre_exec`).
pub(crate) fn attach_bwrap_supervisor(command: &mut Command) -> io::Result<()> {
    attach_bwrap_supervisor_with_roots(command, None)
}

pub(crate) fn attach_bwrap_supervisor_with_roots(
    command: &mut Command,
    write_roots: Option<&[PathBuf]>,
) -> io::Result<()> {
    use std::os::unix::ffi::OsStrExt;
    use std::os::unix::process::CommandExt;

    let bwrap = bwrap_path().ok_or_else(|| {
        io::Error::new(
            io::ErrorKind::Unsupported,
            unavailable_message(),
        )
    })?;
    let program = command.get_program().to_os_string();
    let program_args: Vec<OsString> = command.get_args().map(|a| a.to_os_string()).collect();

    let mut argv_os: Vec<OsString> = Vec::with_capacity(16 + program_args.len());
    argv_os.push(bwrap.into_os_string());
    argv_os.extend(supervisor_args(write_roots)?);
    argv_os.push(program);
    argv_os.extend(program_args);

    let argv_c: Vec<CString> = argv_os
        .iter()
        .map(|s| {
            CString::new(s.as_bytes()).map_err(|_| {
                io::Error::new(
                    io::ErrorKind::InvalidInput,
                    "provider argv contains interior NUL when wrapping with bwrap",
                )
            })
        })
        .collect::<Result<Vec<_>, _>>()?;

    let image = ExecImage::new(argv_c, child_environment(command)?);

    // std applies `Command::env` only after pre_exec, so the environment is
    // passed explicitly. Everything is built before fork; the child only calls
    // execve and reads errno, both async-signal-safe.
    // SAFETY: pre_exec runs between fork and exec in the child. The closure only
    // reads pointers into `image`'s owned, null-terminated buffers.
    unsafe {
        command.pre_exec(move || Err(image.exec()));
    }
    Ok(())
}

fn supervisor_args(write_roots: Option<&[PathBuf]>) -> io::Result<Vec<OsString>> {
    let mut args: Vec<OsString> = ["--unshare-pid", "--as-pid-1", "--die-with-parent"]
        .into_iter()
        .map(OsString::from)
        .collect();
    if let Some(roots) = write_roots {
        if roots.len() < 3
            || roots
                .iter()
                .any(|root| !root.is_absolute() || !root.is_dir())
        {
            return Err(io::Error::new(
                io::ErrorKind::InvalidInput,
                "Quick Chat requires scratch, state and temp directories",
            ));
        }
        args.extend(
            ["--ro-bind", "/", "/", "--dev", "/dev", "--proc", "/proc"].map(OsString::from),
        );
        for root in roots {
            args.push("--bind".into());
            args.push(root.as_os_str().to_owned());
            args.push(root.as_os_str().to_owned());
        }
    } else {
        args.extend(["--dev-bind", "/", "/", "--proc", "/proc"].map(OsString::from));
    }
    args.push("--".into());
    Ok(args)
}

/// argv/envp for execve, built before fork: null-terminated pointer arrays into
/// the owned strings, whose heap buffers stay put when the struct moves.
struct ExecImage {
    _strings: (Vec<CString>, Vec<CString>),
    argv: Vec<*const libc::c_char>,
    envp: Vec<*const libc::c_char>,
}

// SAFETY: the pointers only reference `_strings`, which the struct owns and
// never mutates.
unsafe impl Send for ExecImage {}
unsafe impl Sync for ExecImage {}

impl ExecImage {
    fn new(argv: Vec<CString>, envp: Vec<CString>) -> Self {
        fn pointers(strings: &[CString]) -> Vec<*const libc::c_char> {
            strings
                .iter()
                .map(|s| s.as_ptr())
                .chain(std::iter::once(std::ptr::null()))
                .collect()
        }
        Self {
            argv: pointers(&argv),
            envp: pointers(&envp),
            _strings: (argv, envp),
        }
    }

    /// Returns only if execve fails.
    fn exec(&self) -> io::Error {
        // SAFETY: both arrays are null-terminated and point into `_strings`.
        unsafe { libc::execve(self.argv[0], self.argv.as_ptr(), self.envp.as_ptr()) };
        io::Error::last_os_error()
    }
}

/// `Command` has no getter for `env_clear()`; its alternate Debug output is the
/// only place std exposes it (as a `clear: true,` line inside `CommandEnv`).
fn env_cleared(command: &Command) -> bool {
    format!("{command:#?}")
        .lines()
        .any(|line| line.trim() == "clear: true,")
}

/// The environment `command` would give its child: the inherited environment
/// (none after `env_clear()`) with the command's own overrides and removals.
fn child_environment(command: &Command) -> io::Result<Vec<CString>> {
    use std::collections::BTreeMap;
    use std::os::unix::ffi::OsStrExt;

    let mut env: BTreeMap<OsString, OsString> = if env_cleared(command) {
        BTreeMap::new()
    } else {
        std::env::vars_os().collect()
    };
    for (key, value) in command.get_envs() {
        match value {
            Some(value) => env.insert(key.to_os_string(), value.to_os_string()),
            None => env.remove(key),
        };
    }
    env.into_iter()
        .map(|(key, value)| {
            let mut entry = key.as_bytes().to_vec();
            entry.push(b'=');
            entry.extend_from_slice(value.as_bytes());
            CString::new(entry).map_err(|_| {
                io::Error::new(
                    io::ErrorKind::InvalidInput,
                    "provider environment contains interior NUL when wrapping with bwrap",
                )
            })
        })
        .collect()
}

pub(crate) fn unavailable_message() -> &'static str {
    "local Neko providers require approved process-tree containment; on Linux install bubblewrap (bwrap) so Wiii can spawn with --unshare-pid/--as-pid-1/--die-with-parent; other Unix hosts remain fail-closed"
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn project_supervisor_argv_is_unchanged() {
        assert_eq!(
            supervisor_args(None).unwrap(),
            [
                "--unshare-pid",
                "--as-pid-1",
                "--die-with-parent",
                "--dev-bind",
                "/",
                "/",
                "--proc",
                "/proc",
                "--",
            ]
            .map(OsString::from)
        );
    }

    #[test]
    fn quick_chat_supervisor_argv_and_write_boundary() {
        let base = std::env::temp_dir().join(format!("wiii-confined-{}", uuid::Uuid::new_v4()));
        std::fs::create_dir(&base).unwrap();
        let roots: Vec<PathBuf> = ["scratch", "state", "tmp"]
            .map(|name| base.join(name))
            .into();
        for root in &roots {
            std::fs::create_dir(root).unwrap();
        }
        let args = supervisor_args(Some(&roots)).unwrap();
        let mut expected: Vec<OsString> = [
            "--unshare-pid",
            "--as-pid-1",
            "--die-with-parent",
            "--ro-bind",
            "/",
            "/",
            "--dev",
            "/dev",
            "--proc",
            "/proc",
        ]
        .map(OsString::from)
        .into();
        for root in &roots {
            expected.extend([
                OsString::from("--bind"),
                root.as_os_str().to_owned(),
                root.as_os_str().to_owned(),
            ]);
        }
        expected.push("--".into());
        assert_eq!(args, expected);
        if containment_available() {
            let mut command = Command::new("/bin/sh");
            command.args(["-c", "printf inside > inside.txt && printf state > \"$1/state.txt\" && printf temp > \"$2/temp.txt\" && ! (printf outside > ../escape.txt) && ! (printf outside > \"$3\") && ! (printf outside > linked.txt)", "sh"])
                .arg(&roots[1]).arg(&roots[2]).arg(base.join("absolute.txt"))
                .current_dir(&roots[0]);
            std::os::unix::fs::symlink(
                base.join("linked-outside.txt"),
                roots[0].join("linked.txt"),
            )
            .unwrap();
            attach_bwrap_supervisor_with_roots(&mut command, Some(&roots)).unwrap();
            assert!(command.status().unwrap().success());
            assert_eq!(
                std::fs::read_to_string(roots[0].join("inside.txt")).unwrap(),
                "inside"
            );
            assert!(!base.join("escape.txt").exists());
            assert!(!base.join("absolute.txt").exists());
            assert!(!base.join("linked-outside.txt").exists());
        }
        assert!(supervisor_args(Some(&[])).is_err());
        let missing = vec![base.join("missing"); 3];
        assert!(supervisor_args(Some(&missing)).is_err());
        std::fs::remove_dir_all(base).unwrap();
    }

    #[test]
    fn required_bwrap_is_usable() {
        if std::env::var("WIII_REQUIRE_BWRAP").as_deref() == Ok("1") {
            assert!(
                probe_bwrap_capability(),
                "WIII_REQUIRE_BWRAP=1 requires bubblewrap with working PID namespaces"
            );
        }
    }

    #[test]
    fn force_unavailable_hides_bwrap() {
        force_unavailable_for_test(true);
        assert!(bwrap_path().is_none());
        assert!(!containment_available());
        force_unavailable_for_test(false);
        // Restore: do not assert presence — some hosts genuinely lack bwrap.
    }

    #[test]
    fn unavailable_message_names_bwrap() {
        assert!(unavailable_message().contains("bubblewrap"));
        assert!(unavailable_message().contains("bwrap"));
    }

    #[test]
    fn child_environment_applies_command_overrides_and_removals() {
        let mut command = Command::new("true");
        command.env("WIII_CONTAINMENT_ENV_TEST", "set").env_remove("PATH");
        let env = child_environment(&command).unwrap();
        assert!(env.iter().any(|e| e.as_bytes() == b"WIII_CONTAINMENT_ENV_TEST=set"));
        assert!(!env.iter().any(|e| e.as_bytes().starts_with(b"PATH=")));
    }

    #[test]
    fn child_environment_honors_env_clear() {
        let mut command = Command::new("true");
        command.env_clear().env("WIII_CONTAINMENT_ENV_TEST", "only");
        assert!(env_cleared(&command));
        let env = child_environment(&command).unwrap();
        assert_eq!(
            env,
            vec![CString::new("WIII_CONTAINMENT_ENV_TEST=only").unwrap()]
        );

        let mut inherited = Command::new("true");
        inherited.env("WIII_CONTAINMENT_ENV_TEST", "clear: true,");
        assert!(!env_cleared(&inherited));
    }

    #[test]
    fn exec_image_is_prebuilt_and_null_terminated() {
        let argv = vec![
            CString::new("/bin/bwrap").unwrap(),
            CString::new("--").unwrap(),
        ];
        let envp = vec![CString::new("K=V").unwrap()];
        let image = ExecImage::new(argv, envp);
        let moved = image;
        assert_eq!(moved.argv.len(), 3);
        assert!(moved.argv[2].is_null());
        assert_eq!(moved.envp.len(), 2);
        assert!(moved.envp[1].is_null());
        let first = unsafe { std::ffi::CStr::from_ptr(moved.argv[0]) };
        assert_eq!(first.to_bytes(), b"/bin/bwrap");
        let env = unsafe { std::ffi::CStr::from_ptr(moved.envp[0]) };
        assert_eq!(env.to_bytes(), b"K=V");
    }

    #[test]
    fn accept_rejects_missing_path() {
        assert!(accept_bwrap_candidate(PathBuf::from("/definitely/missing/bwrap-wiii")).is_none());
    }

    #[test]
    fn accept_resolves_real_bwrap_when_present() {
        let Some(path) = bwrap_path() else {
            return;
        };
        assert!(path.is_absolute());
        assert!(Path::new(&path).is_file());
        // Capability probe (namespaces) is covered by provider spawn/probe tests.
        // Those skip cleanly when the host cannot create a PID namespace.
    }
}
