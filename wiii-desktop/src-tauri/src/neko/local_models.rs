//! The user's explicit local model settings, in Neko's canonical user config.
//! This is not a general filesystem/JSON interface or an encrypted secret vault.

use serde::{Deserialize, Serialize};
use serde_json::{json, Map, Value};
use sha2::{Digest, Sha256};
use std::fs::{self, File, OpenOptions};
use std::io::{Read, Write};
use std::path::{Path, PathBuf};
use uuid::Uuid;

const MAX_CONFIG_BYTES: u64 = 2 * 1024 * 1024;
const CONNECTION_FIELDS: [&str; 6] = [
    "provider",
    "base_url",
    "model",
    "api_key",
    "key_env",
    "key_env_fallbacks",
];
const READ_ERROR: &str =
    "Chưa đọc được cấu hình mô hình trên máy này. Cấu hình cũ được giữ nguyên.";
const CONFIG_ERROR: &str =
    "Cấu hình mô hình hiện tại không hợp lệ. Wiii giữ nguyên, không ghi đè tệp cũ.";
const SAVE_ERROR: &str =
    "Chưa lưu được mô hình trên máy này. Cấu hình cũ được giữ nguyên; hãy thử lại.";

#[derive(Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct LocalModelPreset {
    pub id: &'static str,
    pub label: &'static str,
    pub provider: &'static str,
    pub base_url: &'static str,
    pub model: &'static str,
    pub requires_key: bool,
    pub custom_endpoint: bool,
    #[serde(skip)]
    key_env: &'static str,
}

#[derive(Serialize)]
#[serde(rename_all = "camelCase")]
pub struct LocalModelStatus {
    pub configured: bool,
    pub presets: Vec<LocalModelPreset>,
}

// Do not derive Debug/Serialize: this request contains the newly entered key.
#[derive(Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct SaveLocalModelRequest {
    pub preset_id: String,
    pub model: String,
    pub base_url: Option<String>,
    pub api_key: String,
}

#[derive(Serialize)]
#[serde(rename_all = "camelCase")]
pub struct SavedLocalModel {
    pub profile_id: String,
    pub model: String,
    pub provider: String,
}

pub fn presets() -> Vec<LocalModelPreset> {
    [
        (
            "openai",
            "OpenAI",
            "openai_compat",
            "https://api.openai.com/v1",
            "gpt-4o-mini",
            "OPENAI_API_KEY",
        ),
        (
            "claude",
            "Claude",
            "anthropic",
            "https://api.anthropic.com",
            "claude-sonnet-5",
            "ANTHROPIC_API_KEY",
        ),
        (
            "gemini-api",
            "Google Gemini",
            "openai_compat",
            "https://generativelanguage.googleapis.com/v1beta/openai",
            "gemini-3.5-flash",
            "GEMINI_API_KEY",
        ),
        // The Coding Plan route; never replace this with the pay-per-call preset.
        (
            "zai",
            "Z.ai · GLM Coding Plan",
            "anthropic",
            "https://api.z.ai/api/anthropic",
            "glm-5.3",
            "ZAI_API_KEY",
        ),
        (
            "custom",
            "Máy chủ khác / mô hình trên máy",
            "openai_compat",
            "http://127.0.0.1:11434/v1",
            "",
            "",
        ),
    ]
    .into_iter()
    .map(
        |(id, label, provider, base_url, model, key_env)| LocalModelPreset {
            id,
            label,
            provider,
            base_url,
            model,
            key_env,
            requires_key: id != "custom",
            custom_endpoint: id == "custom",
        },
    )
    .collect()
}

fn is_link(metadata: &fs::Metadata) -> bool {
    if metadata.file_type().is_symlink() {
        return true;
    }
    #[cfg(windows)]
    {
        use std::os::windows::fs::MetadataExt;
        // Includes junctions, not only symbolic links.
        return metadata.file_attributes() & 0x400 != 0;
    }
    #[cfg(not(windows))]
    false
}

fn check_directory(path: &Path) -> Result<bool, String> {
    match fs::symlink_metadata(path) {
        Ok(metadata) => {
            if is_link(&metadata) || !metadata.is_dir() {
                return Err(CONFIG_ERROR.into());
            }
            #[cfg(unix)]
            {
                use std::os::unix::fs::MetadataExt;
                if metadata.uid() != unsafe { libc::geteuid() } || metadata.mode() & 0o022 != 0 {
                    return Err(CONFIG_ERROR.into());
                }
            }
            Ok(true)
        }
        Err(error) if error.kind() == std::io::ErrorKind::NotFound => Ok(false),
        Err(_) => Err(READ_ERROR.into()),
    }
}

fn read_object(path: &Path) -> Result<Map<String, Value>, String> {
    let metadata = match fs::symlink_metadata(path) {
        Ok(metadata) => metadata,
        Err(error) if error.kind() == std::io::ErrorKind::NotFound => return Ok(Map::new()),
        Err(_) => return Err(READ_ERROR.into()),
    };
    if is_link(&metadata) || !metadata.is_file() || metadata.len() > MAX_CONFIG_BYTES {
        return Err(CONFIG_ERROR.into());
    }
    let mut options = OpenOptions::new();
    options.read(true);
    #[cfg(unix)]
    {
        use std::os::unix::fs::OpenOptionsExt;
        options.custom_flags(libc::O_NOFOLLOW);
    }
    let mut bytes = Vec::new();
    options
        .open(path)
        .map_err(|_| READ_ERROR.to_string())?
        .take(MAX_CONFIG_BYTES + 1)
        .read_to_end(&mut bytes)
        .map_err(|_| READ_ERROR.to_string())?;
    if bytes.len() as u64 > MAX_CONFIG_BYTES {
        return Err(CONFIG_ERROR.into());
    }
    let data: Value = serde_json::from_slice(bytes.strip_prefix(b"\xef\xbb\xbf").unwrap_or(&bytes))
        .map_err(|_| CONFIG_ERROR.to_string())?;
    data.as_object().cloned().ok_or_else(|| CONFIG_ERROR.into())
}

fn read_config(home: &Path) -> Result<Map<String, Value>, String> {
    if !check_directory(&home.join(".neko-core"))? {
        return Ok(Map::new());
    }
    read_object(&home.join(".neko-core/config.json"))
}

fn has_text(value: Option<&Value>) -> bool {
    value
        .and_then(Value::as_str)
        .is_some_and(|text| !text.trim().is_empty())
}

fn has_connection(data: &Map<String, Value>) -> bool {
    if has_text(data.get("api_key")) {
        return true;
    }
    if data
        .get("active_profile")
        .and_then(Value::as_str)
        .is_some_and(|id| {
            [
                "chatgpt",
                "gemini",
                "grok",
                "kimi",
                "opencode-account",
                "cline-account",
            ]
            .contains(&id)
        })
    {
        return true;
    }
    data.get("profiles")
        .and_then(Value::as_object)
        .is_some_and(|profiles| {
            profiles.values().any(|profile| {
                has_text(profile.get("api_key"))
                    || (profile.get("auth").and_then(Value::as_str) == Some("none")
                        && has_text(profile.get("base_url")))
                    || profile
                        .get("key_env")
                        .and_then(Value::as_str)
                        .is_some_and(|name| {
                            std::env::var(name).is_ok_and(|value| !value.trim().is_empty())
                        })
            })
        })
}

pub fn status(home: &Path) -> Result<LocalModelStatus, String> {
    let data = read_config(home)?;
    let legacy = read_object(&home.join("neko.json"))?;
    let configured = has_connection(&data)
        || has_connection(&legacy)
        || [
            "NEKO_API_KEY",
            "OPENAI_API_KEY",
            "ANTHROPIC_API_KEY",
            "GEMINI_API_KEY",
            "GOOGLE_API_KEY",
            "ZAI_API_KEY",
            "NVIDIA_API_KEY",
            "BAI_API_KEY",
            "DEEPSEEK_API_KEY",
            "KIMI_API_KEY",
            "MOONSHOT_API_KEY",
            "OPENROUTER_API_KEY",
            "GROQ_API_KEY",
            "XAI_API_KEY",
        ]
        .iter()
        .any(|name| std::env::var(name).is_ok_and(|value| !value.trim().is_empty()));
    Ok(LocalModelStatus {
        configured,
        presets: presets(),
    })
}

fn normalized_url(value: &str) -> Result<String, String> {
    const ERROR: &str = "Địa chỉ mô hình cần HTTPS, hoặc HTTP trên localhost; không kèm khóa, tài khoản hay tham số.";
    if value.len() > 2048 || value.chars().any(char::is_control) {
        return Err(ERROR.into());
    }
    let url = tauri::Url::parse(value.trim()).map_err(|_| ERROR.to_string())?;
    let host = url.host_str().ok_or(ERROR)?;
    let loopback = host == "localhost"
        || host == "[::1]"
        || host == "::1"
        || host
            .parse::<std::net::IpAddr>()
            .is_ok_and(|ip| ip.is_loopback());
    if (url.scheme() != "https" && !(url.scheme() == "http" && loopback))
        || !url.username().is_empty()
        || url.password().is_some()
        || url.query().is_some()
        || url.fragment().is_some()
    {
        return Err(ERROR.into());
    }
    if host == "api.z.ai"
        && !["/api/anthropic", "/api/coding/paas/v4"].contains(&url.path().trim_end_matches('/'))
    {
        return Err("Z.ai cần địa chỉ GLM Coding Plan, không dùng API tính phí theo lượt.".into());
    }
    Ok(url.as_str().trim_end_matches('/').to_string())
}

fn private_permissions(path: &Path) -> Result<(), String> {
    #[cfg(unix)]
    {
        use std::os::unix::fs::PermissionsExt;
        let mode = if path.is_dir() { 0o700 } else { 0o600 };
        fs::set_permissions(path, fs::Permissions::from_mode(mode))
            .map_err(|_| SAVE_ERROR.to_string())?;
    }
    #[cfg(windows)]
    {
        use std::os::windows::ffi::OsStrExt;
        use windows_sys::Win32::Foundation::LocalFree;
        use windows_sys::Win32::Security::Authorization::{
            ConvertStringSecurityDescriptorToSecurityDescriptorW, SDDL_REVISION_1,
        };
        use windows_sys::Win32::Security::{
            SetFileSecurityW, DACL_SECURITY_INFORMATION, PROTECTED_DACL_SECURITY_INFORMATION,
        };
        let sddl: Vec<u16> = "D:P(A;OICI;FA;;;SY)(A;OICI;FA;;;OW)\0"
            .encode_utf16()
            .collect();
        let path: Vec<u16> = path.as_os_str().encode_wide().chain(Some(0)).collect();
        let mut descriptor = std::ptr::null_mut();
        unsafe {
            if ConvertStringSecurityDescriptorToSecurityDescriptorW(
                sddl.as_ptr(),
                SDDL_REVISION_1,
                &mut descriptor,
                std::ptr::null_mut(),
            ) == 0
            {
                return Err(SAVE_ERROR.into());
            }
            let result = SetFileSecurityW(
                path.as_ptr(),
                DACL_SECURITY_INFORMATION | PROTECTED_DACL_SECURITY_INFORMATION,
                descriptor,
            );
            LocalFree(descriptor);
            if result == 0 {
                return Err(SAVE_ERROR.into());
            }
        }
    }
    Ok(())
}

#[cfg(windows)]
fn create_private_file(path: &Path) -> Result<File, String> {
    use std::os::windows::{ffi::OsStrExt, io::FromRawHandle};
    use windows_sys::Win32::Foundation::{LocalFree, GENERIC_WRITE, INVALID_HANDLE_VALUE};
    use windows_sys::Win32::Security::Authorization::{
        ConvertStringSecurityDescriptorToSecurityDescriptorW, SDDL_REVISION_1,
    };
    use windows_sys::Win32::Security::SECURITY_ATTRIBUTES;
    use windows_sys::Win32::Storage::FileSystem::{CreateFileW, CREATE_NEW, FILE_ATTRIBUTE_NORMAL};
    let sddl: Vec<u16> = "D:P(A;;FA;;;SY)(A;;FA;;;OW)\0".encode_utf16().collect();
    let path: Vec<u16> = path.as_os_str().encode_wide().chain(Some(0)).collect();
    let mut descriptor = std::ptr::null_mut();
    unsafe {
        if ConvertStringSecurityDescriptorToSecurityDescriptorW(
            sddl.as_ptr(),
            SDDL_REVISION_1,
            &mut descriptor,
            std::ptr::null_mut(),
        ) == 0
        {
            return Err(SAVE_ERROR.into());
        }
        let attributes = SECURITY_ATTRIBUTES {
            nLength: std::mem::size_of::<SECURITY_ATTRIBUTES>() as u32,
            lpSecurityDescriptor: descriptor,
            bInheritHandle: 0,
        };
        // The private DACL is present at creation, not added after another
        // account could have acquired a readable handle to the temporary file.
        let handle = CreateFileW(
            path.as_ptr(),
            GENERIC_WRITE,
            0,
            &attributes,
            CREATE_NEW,
            FILE_ATTRIBUTE_NORMAL,
            std::ptr::null_mut(),
        );
        LocalFree(descriptor);
        if handle == INVALID_HANDLE_VALUE {
            return Err(SAVE_ERROR.into());
        }
        Ok(File::from_raw_handle(handle))
    }
}

#[cfg(not(windows))]
fn create_private_file(path: &Path) -> Result<File, String> {
    let mut options = OpenOptions::new();
    options.write(true).create_new(true);
    #[cfg(unix)]
    {
        use std::os::unix::fs::OpenOptionsExt;
        options.mode(0o600);
    }
    options.open(path).map_err(|_| SAVE_ERROR.into())
}

fn atomic_save(
    directory: &Path,
    data: &Map<String, Value>,
    original: &Map<String, Value>,
) -> Result<(), String> {
    if !check_directory(directory)? {
        #[cfg(unix)]
        {
            use std::os::unix::fs::DirBuilderExt;
            fs::DirBuilder::new()
                .mode(0o700)
                .create(directory)
                .map_err(|_| SAVE_ERROR.to_string())?;
        }
        #[cfg(not(unix))]
        fs::create_dir(directory).map_err(|_| SAVE_ERROR.to_string())?;
        private_permissions(directory)?;
    }
    let target = directory.join("config.json");
    let temporary = directory.join(format!(".config-{}.tmp", Uuid::new_v4()));
    let result = (|| {
        let mut file = create_private_file(&temporary)?;
        serde_json::to_writer_pretty(&mut file, data).map_err(|_| SAVE_ERROR.to_string())?;
        file.write_all(b"\n").map_err(|_| SAVE_ERROR.to_string())?;
        file.sync_all().map_err(|_| SAVE_ERROR.to_string())?;
        drop(file);
        // Other Neko clients do not share this app's mutex. Refuse a stale
        // snapshot rather than knowingly replacing their intervening changes.
        if &read_object(&target)? != original {
            return Err(SAVE_ERROR.into());
        }
        fs::rename(&temporary, &target).map_err(|_| SAVE_ERROR.to_string())?;
        #[cfg(unix)]
        if let Ok(directory) = File::open(directory) {
            let _ = directory.sync_all();
        }
        Ok(())
    })();
    if result.is_err() {
        let _ = fs::remove_file(&temporary);
    }
    result
}

pub fn save(home: &Path, request: SaveLocalModelRequest) -> Result<SavedLocalModel, String> {
    let preset = presets()
        .into_iter()
        .find(|preset| preset.id == request.preset_id)
        .ok_or("Hãy chọn nhà cung cấp mô hình.")?;
    let model = request.model.trim();
    if model.is_empty()
        || model.len() > 200
        || !model
            .bytes()
            .all(|byte| byte.is_ascii_alphanumeric() || b"-._/:@+".contains(&byte))
    {
        return Err("Hãy nhập mã mô hình, không kèm khoảng trắng hoặc ký tự điều khiển.".into());
    }
    let key = request.api_key.trim();
    if (preset.requires_key && key.is_empty())
        || key.len() > 8192
        || key.chars().any(|ch| ch.is_control() || ch.is_whitespace())
    {
        return Err("Hãy nhập khóa API hợp lệ của nhà cung cấp.".into());
    }
    let base_url = normalized_url(if preset.custom_endpoint {
        request.base_url.as_deref().unwrap_or("")
    } else {
        preset.base_url
    })?;
    let legacy = read_object(&home.join("neko.json"))?;
    if legacy.contains_key("active_profile")
        || legacy.contains_key("profiles")
        || CONNECTION_FIELDS
            .iter()
            .any(|field| legacy.contains_key(*field))
    {
        return Err("Có cấu hình mô hình cũ đang ưu tiên trên máy này. Wiii giữ nguyên để tránh dùng nhầm khóa.".into());
    }
    let mut data = read_config(home)?;
    let original = data.clone();
    if data
        .get("active_profile")
        .is_some_and(|value| !value.is_null() && !value.is_string())
    {
        return Err(CONFIG_ERROR.into());
    }
    if data.get("profiles").is_some_and(|value| !value.is_object()) {
        return Err(CONFIG_ERROR.into());
    }
    let mut profiles = data
        .remove("profiles")
        .and_then(|value| value.as_object().cloned())
        .unwrap_or_default();
    let profile_id = if preset.custom_endpoint {
        let digest = Sha256::digest(format!("{base_url}\n{model}"));
        format!("wiii-custom-{:x}", digest)[..28].to_string()
    } else {
        preset.id.to_string()
    };

    // Migrate unambiguous legacy globals, but never recombine an already
    // scoped connection with another endpoint/key. Core 1.9.5's migration
    // keeps a profile's key while replacing its endpoint; that is not safe.
    if CONNECTION_FIELDS
        .iter()
        .any(|field| data.contains_key(*field))
    {
        let active = data
            .get("active_profile")
            .and_then(Value::as_str)
            .filter(|id| !id.is_empty());
        let mut previous = active.unwrap_or("legacy").to_string();
        if active.is_none() {
            let mut suffix = 2;
            while profiles.contains_key(&previous) {
                previous = format!("legacy-{suffix}");
                suffix += 1;
            }
        }
        let old = profiles
            .entry(previous)
            .or_insert_with(|| json!({}))
            .as_object_mut()
            .ok_or(CONFIG_ERROR)?;
        if CONNECTION_FIELDS
            .iter()
            .any(|field| old.contains_key(*field))
        {
            return Err("Có cấu hình mô hình cũ đang ưu tiên trên máy này. Wiii giữ nguyên để tránh dùng nhầm khóa.".into());
        }
        for field in CONNECTION_FIELDS {
            if let Some(value) = data.remove(field) {
                old.insert(field.into(), value);
            }
        }
    }
    let profile = profiles
        .entry(profile_id.clone())
        .or_insert_with(|| json!({}))
        .as_object_mut()
        .ok_or(CONFIG_ERROR)?;
    if preset.custom_endpoint {
        profile.insert("label".into(), json!("Máy chủ riêng"));
    }
    // An empty key_env would activate Core's broad OPENAI/NVIDIA fallback.
    // Give custom endpoints their own scoped fallback name, even for no-auth
    // local servers, so an unrelated ambient provider key is never borrowed.
    let key_env = if preset.custom_endpoint {
        format!(
            "WIII_{}_API_KEY",
            profile_id.replace('-', "_").to_ascii_uppercase()
        )
    } else {
        preset.key_env.to_string()
    };
    for (field, value) in [
        ("provider", json!(preset.provider)),
        ("base_url", json!(base_url)),
        ("model", json!(model)),
        ("api_key", json!(key)),
        ("key_env", json!(key_env)),
        ("key_env_fallbacks", json!([])),
        (
            "auth",
            json!(if key.is_empty() { "none" } else { "api_key" }),
        ),
    ] {
        profile.insert(field.into(), value);
    }
    data.insert("profiles".into(), Value::Object(profiles));
    data.insert("active_profile".into(), json!(profile_id));
    atomic_save(&home.join(".neko-core"), &data, &original)?;
    Ok(SavedLocalModel {
        profile_id,
        model: model.into(),
        provider: preset.provider.into(),
    })
}

pub fn home_from_environment(
    fallback: impl FnOnce() -> Option<PathBuf>,
) -> Result<PathBuf, String> {
    let home = std::env::var_os("USERPROFILE")
        .filter(|value| !value.is_empty())
        .or_else(|| std::env::var_os("HOME").filter(|value| !value.is_empty()))
        .map(PathBuf::from)
        .or_else(fallback)
        .ok_or(READ_ERROR)?;
    if !home.is_absolute() {
        return Err(READ_ERROR.into());
    }
    Ok(home)
}

#[cfg(test)]
mod tests {
    use super::*;

    struct Home(PathBuf);
    impl Home {
        fn new() -> Self {
            let path = std::env::temp_dir().join(format!("wiii-models-test-{}", Uuid::new_v4()));
            fs::create_dir(&path).unwrap();
            Self(path)
        }
        fn config(&self) -> PathBuf {
            self.0.join(".neko-core/config.json")
        }
        fn put(&self, data: Value) {
            fs::create_dir_all(self.0.join(".neko-core")).unwrap();
            fs::write(self.config(), serde_json::to_vec(&data).unwrap()).unwrap();
        }
        fn data(&self) -> Value {
            serde_json::from_slice(&fs::read(self.config()).unwrap()).unwrap()
        }
    }
    impl Drop for Home {
        fn drop(&mut self) {
            let _ = fs::remove_dir_all(&self.0);
        }
    }

    fn request() -> SaveLocalModelRequest {
        SaveLocalModelRequest {
            preset_id: "zai".into(),
            model: "glm-5.3".into(),
            base_url: None,
            api_key: "unit-test-only-value".into(),
        }
    }

    #[test]
    fn first_save_is_private_canonical_and_returns_no_secret() {
        let home = Home::new();
        let saved = save(&home.0, request()).unwrap();
        assert_eq!(saved.profile_id, "zai");
        let response = serde_json::to_string(&saved).unwrap();
        assert!(!response.contains("unit-test-only-value"));
        assert!(!response.contains("apiKey"));
        let data = home.data();
        assert_eq!(data["active_profile"], "zai");
        assert_eq!(
            data["profiles"]["zai"]["base_url"],
            "https://api.z.ai/api/anthropic"
        );
        assert_eq!(data["profiles"]["zai"]["api_key"], "unit-test-only-value");
        assert!(!data.as_object().unwrap().contains_key("api_key"));
        assert!(status(&home.0).unwrap().configured);
        assert!(!serde_json::to_string(&status(&home.0).unwrap())
            .unwrap()
            .contains("unit-test-only-value"));
        assert_eq!(fs::read_dir(home.0.join(".neko-core")).unwrap().count(), 1);
        #[cfg(unix)]
        {
            use std::os::unix::fs::PermissionsExt;
            assert_eq!(
                fs::metadata(home.config()).unwrap().permissions().mode() & 0o777,
                0o600
            );
            assert_eq!(
                fs::metadata(home.0.join(".neko-core"))
                    .unwrap()
                    .permissions()
                    .mode()
                    & 0o777,
                0o700
            );
        }
    }

    #[test]
    fn switching_provider_preserves_unrelated_config_and_legacy_key_ownership() {
        let home = Home::new();
        home.put(json!({"active_profile":"openai", "provider":"openai_compat", "base_url":"https://api.openai.com/v1", "model":"older", "api_key":"prior-provider-value", "profiles":{"openai":{"temperature":0.4},"other":{"api_key":"other-value"}}, "mcp_servers":{"local":{"command":"keep"}}, "dream_mode":"manual"}));
        save(&home.0, request()).unwrap();
        let data = home.data();
        assert_eq!(
            data["profiles"]["openai"]["api_key"],
            "prior-provider-value"
        );
        assert_eq!(
            data["profiles"]["openai"]["base_url"],
            "https://api.openai.com/v1"
        );
        assert_eq!(data["profiles"]["openai"]["temperature"], 0.4);
        assert_eq!(data["profiles"]["other"]["api_key"], "other-value");
        assert_eq!(data["mcp_servers"]["local"]["command"], "keep");
        assert_eq!(data["dream_mode"], "manual");
        for field in CONNECTION_FIELDS {
            assert!(!data.as_object().unwrap().contains_key(field));
        }
    }

    #[test]
    fn unscoped_legacy_settings_do_not_overwrite_an_existing_legacy_profile() {
        let home = Home::new();
        home.put(json!({"active_profile":null,"api_key":"unscoped-value","profiles":{"legacy":{"api_key":"keep-value"}}}));
        save(&home.0, request()).unwrap();
        let data = home.data();
        assert_eq!(data["profiles"]["legacy"]["api_key"], "keep-value");
        assert_eq!(data["profiles"]["legacy-2"]["api_key"], "unscoped-value");
    }

    #[test]
    fn mixed_legacy_and_scoped_connections_never_rebind_or_drop_either_key() {
        let home = Home::new();
        home.put(json!({"active_profile":"openai", "provider":"openai_compat", "base_url":"https://legacy.example/v1", "api_key":"legacy-only-value", "profiles":{"openai":{"base_url":"https://scoped.example/v1", "api_key":"scoped-only-value"}}}));
        let before = fs::read(home.config()).unwrap();
        assert!(save(&home.0, request()).is_err());
        assert_eq!(fs::read(home.config()).unwrap(), before);
        // A scoped environment-key binding is equally private, even if the
        // profile stores no literal credential.
        home.put(json!({"active_profile":"openai", "base_url":"https://legacy.example/v1", "profiles":{"openai":{"key_env":"OPENAI_API_KEY"}}}));
        let before = fs::read(home.config()).unwrap();
        assert!(save(&home.0, request()).is_err());
        assert_eq!(fs::read(home.config()).unwrap(), before);
    }

    #[test]
    fn malformed_config_is_not_overwritten_and_errors_do_not_reflect_content() {
        let home = Home::new();
        fs::create_dir(home.0.join(".neko-core")).unwrap();
        let original = b"{\"api_key\":\"private-malformed-content";
        fs::write(home.config(), original).unwrap();
        let error = save(&home.0, request()).err().unwrap();
        assert!(!error.contains("private-malformed-content"));
        assert_eq!(fs::read(home.config()).unwrap(), original);
        for data in [
            json!([]),
            json!({"profiles":[]}),
            json!({"active_profile":42}),
        ] {
            home.put(data);
            let before = fs::read(home.config()).unwrap();
            assert!(save(&home.0, request()).is_err());
            assert_eq!(fs::read(home.config()).unwrap(), before);
        }
    }

    #[test]
    fn higher_priority_legacy_config_is_never_silently_replaced() {
        let home = Home::new();
        let bytes = b"{\"active_profile\":\"other\",\"api_key\":\"legacy-value\"}";
        fs::write(home.0.join("neko.json"), bytes).unwrap();
        assert!(save(&home.0, request()).is_err());
        assert_eq!(fs::read(home.0.join("neko.json")).unwrap(), bytes);
        assert!(!home.config().exists());
    }

    #[test]
    fn an_intervening_external_update_is_preserved_instead_of_replaced() {
        let home = Home::new();
        home.put(json!({"dream_mode":"manual"}));
        let original = read_config(&home.0).unwrap();
        home.put(json!({"dream_mode":"off","other":"external-change"}));
        let before = fs::read(home.config()).unwrap();
        assert!(atomic_save(&home.0.join(".neko-core"), &original, &original).is_err());
        assert_eq!(fs::read(home.config()).unwrap(), before);
        assert_eq!(fs::read_dir(home.0.join(".neko-core")).unwrap().count(), 1);
    }

    #[test]
    fn local_no_auth_does_not_borrow_ambient_provider_fallbacks() {
        let home = Home::new();
        let mut draft = request();
        draft.preset_id = "custom".into();
        draft.model = "llama3.2".into();
        draft.base_url = Some("http://127.0.0.1:11434/v1".into());
        draft.api_key.clear();
        let saved = save(&home.0, draft).unwrap();
        let data = home.data();
        let profile = &data["profiles"][&saved.profile_id];
        assert_eq!(profile["api_key"], "");
        assert_eq!(profile["auth"], "none");
        // Core suppresses its broad OpenAI/NVIDIA fallback only when key_env
        // is scoped. It must not point to another provider's variable either.
        assert!(profile["key_env"]
            .as_str()
            .unwrap()
            .starts_with("WIII_WIII_CUSTOM_"));
        assert_eq!(profile["key_env_fallbacks"], json!([]));
    }

    #[test]
    fn validation_rejects_injection_and_pay_per_call_without_creating_config() {
        let home = Home::new();
        for model in ["", "model\nother", "model with space"] {
            let mut draft = request();
            draft.model = model.into();
            assert!(save(&home.0, draft).is_err());
        }
        for key in ["", "value\nheader", "two words"] {
            let mut draft = request();
            draft.api_key = key.into();
            assert!(save(&home.0, draft).is_err());
        }
        for address in [
            "http://example.com/v1",
            "https://key@example.com/v1",
            "https://example.com/v1?api_key=private",
            "https://example.com/v1#key",
            "https://api.z.ai/api/paas/v4",
            "file:///etc/passwd",
        ] {
            assert!(normalized_url(address).is_err());
        }
        for address in [
            "https://example.com/v1",
            "http://localhost:11434/v1",
            "http://[::1]:1234/v1",
            "https://api.z.ai/api/coding/paas/v4",
        ] {
            assert!(normalized_url(address).is_ok());
        }
        assert!(!home.config().exists());
        assert!(!home.0.join(".neko-core").exists());
    }

    #[cfg(unix)]
    #[test]
    fn symlinked_config_or_directory_is_refused_without_touching_its_target() {
        use std::os::unix::fs::symlink;
        let home = Home::new();
        let outside = Home::new();
        outside.put(json!({"api_key":"keep-outside-value"}));
        let before = fs::read(outside.config()).unwrap();
        symlink(outside.0.join(".neko-core"), home.0.join(".neko-core")).unwrap();
        assert!(save(&home.0, request()).is_err());
        fs::remove_file(home.0.join(".neko-core")).unwrap();
        fs::create_dir(home.0.join(".neko-core")).unwrap();
        symlink(outside.config(), home.config()).unwrap();
        assert!(save(&home.0, request()).is_err());
        assert_eq!(fs::read(outside.config()).unwrap(), before);
    }
}
