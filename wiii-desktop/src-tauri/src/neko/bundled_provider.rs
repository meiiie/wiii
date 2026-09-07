use serde::Deserialize;
use sha2::{Digest, Sha256};
use std::{
    collections::HashMap,
    fs, io,
    path::{Path, PathBuf},
    sync::OnceLock,
};

static RESOURCE_DIR: OnceLock<PathBuf> = OnceLock::new();
const LOCK: &str = include_str!("../../neko-bundle.lock.json");

#[derive(Deserialize)]
struct Artifact {
    size: u64,
    sha256: String,
}

#[derive(Deserialize)]
struct BundleLock {
    artifacts: HashMap<String, Artifact>,
}

pub fn initialize(resource_dir: PathBuf) -> Result<(), io::Error> {
    RESOURCE_DIR
        .set(resource_dir)
        .map_err(|_| io::Error::other("Neko resource directory already initialized"))
}

pub fn program() -> Result<Option<PathBuf>, io::Error> {
    let Some(resource_dir) = RESOURCE_DIR.get() else {
        return if cfg!(feature = "bundled-neko") {
            Err(io::Error::other(
                "Neko bundle resource directory is unavailable",
            ))
        } else {
            Ok(None)
        };
    };
    let os = match std::env::consts::OS {
        "windows" => "windows",
        "macos" => "macos",
        "linux" => "linux",
        _ => "unsupported",
    };
    let arch = match std::env::consts::ARCH {
        "x86_64" => "x64",
        "aarch64" => "arm64",
        _ => "unsupported",
    };
    let lock: BundleLock = serde_json::from_str(LOCK).map_err(io::Error::other)?;
    let resolved = resolve_bundle(
        resource_dir,
        os,
        lock.artifacts.get(&format!("{os}-{arch}")),
    )?;
    if resolved.is_none() && cfg!(feature = "bundled-neko") {
        return Err(io::Error::other(
            "Neko bundle is missing; repair Wiii installation",
        ));
    }
    Ok(resolved)
}

fn resolve_bundle(
    resource_dir: &Path,
    os: &str,
    expected: Option<&Artifact>,
) -> Result<Option<PathBuf>, io::Error> {
    let directory = resource_dir.join("runtime").join("neko");
    let metadata = match fs::symlink_metadata(&directory) {
        Ok(metadata) => metadata,
        Err(error) if error.kind() == io::ErrorKind::NotFound => return Ok(None),
        Err(error) => return Err(error),
    };
    if !metadata.is_dir() || metadata.file_type().is_symlink() {
        return Err(io::Error::other(
            "Neko bundle directory is invalid; repair Wiii installation",
        ));
    }
    let expected = expected.ok_or_else(|| io::Error::other("Neko bundle target is unsupported"))?;
    if !directory.join("bundle.json").is_file() {
        return Err(io::Error::other(
            "Neko bundle preparation is incomplete; repair Wiii installation",
        ));
    }
    let program = directory.join(if os == "windows" { "neko.exe" } else { "neko" });
    let metadata = fs::symlink_metadata(&program)?;
    if !metadata.is_file() || metadata.file_type().is_symlink() || metadata.len() != expected.size {
        return Err(io::Error::other(
            "Neko bundle is incomplete or damaged; repair Wiii installation",
        ));
    }
    let mut file = fs::File::open(&program)?;
    let mut digest = Sha256::new();
    io::copy(&mut file, &mut digest)?;
    if format!("{:x}", digest.finalize()) != expected.sha256 {
        return Err(io::Error::other(
            "Neko bundle checksum mismatch; repair Wiii installation",
        ));
    }
    Ok(Some(program))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn bundled_build_requires_resource_initialization() {
        if cfg!(feature = "bundled-neko") {
            assert!(program().is_err());
        } else {
            assert!(program().unwrap().is_none());
        }
    }

    #[test]
    fn missing_bundle_allows_legacy_discovery_but_partial_or_corrupt_never_does() {
        let root = std::env::temp_dir().join(format!("wiii-bundle-test-{}", uuid::Uuid::new_v4()));
        let directory = root.join("runtime/neko");
        let expected = Artifact {
            size: 3,
            sha256: format!("{:x}", Sha256::digest(b"abc")),
        };
        assert_eq!(
            resolve_bundle(&root, "windows", Some(&expected)).unwrap(),
            None
        );
        fs::create_dir_all(&directory).unwrap();
        assert!(resolve_bundle(&root, "windows", Some(&expected)).is_err());
        fs::write(directory.join("bundle.json"), b"{}").unwrap();
        fs::write(directory.join("neko.exe"), b"bad").unwrap();
        assert!(resolve_bundle(&root, "windows", Some(&expected)).is_err());
        fs::write(directory.join("neko.exe"), b"abc").unwrap();
        assert_eq!(
            resolve_bundle(&root, "windows", Some(&expected)).unwrap(),
            Some(directory.join("neko.exe"))
        );
        assert!(resolve_bundle(&root, "windows", None).is_err());
        fs::rename(&root, root.with_extension("renamed")).unwrap();
        let moved = root.with_extension("renamed");
        assert!(resolve_bundle(&moved, "windows", Some(&expected))
            .unwrap()
            .is_some());
        fs::remove_dir_all(&moved).unwrap();
    }

    #[test]
    fn release_lock_contains_valid_targets_and_hashes() {
        let lock: BundleLock = serde_json::from_str(LOCK).unwrap();
        for target in [
            "windows-x64",
            "linux-x64",
            "linux-arm64",
            "macos-x64",
            "macos-arm64",
        ] {
            let artifact = &lock.artifacts[target];
            assert!(artifact.size > 0 && artifact.size < 128 * 1024 * 1024);
            assert_eq!(artifact.sha256.len(), 64);
            assert!(artifact.sha256.bytes().all(|byte| byte.is_ascii_hexdigit()));
        }
    }
}
