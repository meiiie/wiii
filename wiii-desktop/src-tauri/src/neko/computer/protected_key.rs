use std::fs::OpenOptions;
use std::io::{Read, Write};
use std::path::Path;
use uuid::Uuid;

pub(crate) fn random_nonce() -> [u8; 24] {
    let first = Uuid::new_v4();
    let second = Uuid::new_v4();
    let mut nonce = [0_u8; 24];
    nonce[..16].copy_from_slice(first.as_bytes());
    nonce[16..].copy_from_slice(&second.as_bytes()[..8]);
    nonce
}

#[cfg(windows)]
fn protect(key: &[u8; 32], purpose: &str) -> Result<Vec<u8>, String> {
    use windows_sys::Win32::Foundation::LocalFree;
    use windows_sys::Win32::Security::Cryptography::{
        CryptProtectData, CRYPTPROTECT_UI_FORBIDDEN, CRYPT_INTEGER_BLOB,
    };
    let mut input_bytes = key.to_vec();
    let input = CRYPT_INTEGER_BLOB {
        cbData: input_bytes.len() as u32,
        pbData: input_bytes.as_mut_ptr(),
    };
    let mut output = CRYPT_INTEGER_BLOB::default();
    let success = unsafe {
        CryptProtectData(
            &input,
            std::ptr::null(),
            std::ptr::null(),
            std::ptr::null(),
            std::ptr::null(),
            CRYPTPROTECT_UI_FORBIDDEN,
            &mut output,
        )
    };
    if success == 0 {
        return Err(format!(
            "protect {purpose} key failed: {}",
            std::io::Error::last_os_error()
        ));
    }
    let protected =
        unsafe { std::slice::from_raw_parts(output.pbData, output.cbData as usize) }.to_vec();
    unsafe { LocalFree(output.pbData.cast()) };
    Ok(protected)
}

#[cfg(windows)]
fn unprotect(stored: &[u8], purpose: &str) -> Result<[u8; 32], String> {
    use windows_sys::Win32::Foundation::LocalFree;
    use windows_sys::Win32::Security::Cryptography::{
        CryptUnprotectData, CRYPTPROTECT_UI_FORBIDDEN, CRYPT_INTEGER_BLOB,
    };
    let mut input_bytes = stored.to_vec();
    let input = CRYPT_INTEGER_BLOB {
        cbData: input_bytes.len() as u32,
        pbData: input_bytes.as_mut_ptr(),
    };
    let mut output = CRYPT_INTEGER_BLOB::default();
    let success = unsafe {
        CryptUnprotectData(
            &input,
            std::ptr::null_mut(),
            std::ptr::null(),
            std::ptr::null(),
            std::ptr::null(),
            CRYPTPROTECT_UI_FORBIDDEN,
            &mut output,
        )
    };
    if success == 0 {
        return Err(format!(
            "unprotect {purpose} key failed: {}",
            std::io::Error::last_os_error()
        ));
    }
    let plaintext =
        unsafe { std::slice::from_raw_parts(output.pbData, output.cbData as usize) }.to_vec();
    unsafe { LocalFree(output.pbData.cast()) };
    plaintext
        .as_slice()
        .try_into()
        .map_err(|_| format!("{purpose} key has an invalid length"))
}

#[cfg(not(windows))]
fn protect(key: &[u8; 32], _purpose: &str) -> Result<Vec<u8>, String> {
    Ok(key.to_vec())
}

#[cfg(not(windows))]
fn unprotect(stored: &[u8], purpose: &str) -> Result<[u8; 32], String> {
    stored
        .try_into()
        .map_err(|_| format!("{purpose} key has an invalid length"))
}

fn read(path: &Path, purpose: &str) -> Result<[u8; 32], String> {
    let file =
        std::fs::File::open(path).map_err(|error| format!("open {purpose} key failed: {error}"))?;
    let mut stored = Vec::new();
    file.take(16 * 1024)
        .read_to_end(&mut stored)
        .map_err(|error| format!("read {purpose} key failed: {error}"))?;
    if stored.is_empty() || stored.len() >= 16 * 1024 {
        return Err(format!("{purpose} key has an invalid length"));
    }
    unprotect(&stored, purpose)
}

fn create(path: &Path, purpose: &str) -> Result<[u8; 32], String> {
    let first = Uuid::new_v4();
    let second = Uuid::new_v4();
    let mut key = [0_u8; 32];
    key[..16].copy_from_slice(first.as_bytes());
    key[16..].copy_from_slice(second.as_bytes());
    let mut options = OpenOptions::new();
    options.write(true).create_new(true);
    #[cfg(unix)]
    {
        use std::os::unix::fs::OpenOptionsExt;
        options.mode(0o600);
    }
    let mut file = options
        .open(path)
        .map_err(|error| format!("create {purpose} key failed: {error}"))?;
    let stored = protect(&key, purpose)?;
    file.write_all(&stored)
        .and_then(|_| file.sync_all())
        .map_err(|error| format!("persist {purpose} key failed: {error}"))?;
    Ok(key)
}

pub(crate) fn load_or_create(path: &Path, purpose: &str) -> Result<[u8; 32], String> {
    match read(path, purpose) {
        Ok(key) => Ok(key),
        Err(_) if !path.exists() => match create(path, purpose) {
            Ok(key) => Ok(key),
            Err(_) if path.exists() => read(path, purpose),
            Err(error) => Err(error),
        },
        Err(error) => Err(error),
    }
}
