//! App-managed working folders for conversations without a user-selected project.
//! This is a working-directory choice, not an operating-system sandbox grant.
use serde::Serialize;
use std::{fs, path::Path};
use tauri::Manager;

#[derive(Serialize)]
#[serde(rename_all = "camelCase")]
pub struct QuickChatWorkspace {
    path: String,
    name: String,
    kind: &'static str,
}

fn create_private_directory(path: &Path) -> Result<(), String> {
    #[cfg(unix)]
    let result = {
        use std::os::unix::fs::DirBuilderExt;
        fs::DirBuilder::new().mode(0o700).create(path)
    };
    #[cfg(not(unix))]
    let result = fs::create_dir(path);
    result.map_err(|error| format!("Không tạo được thư mục chat: {error}"))
}

fn create_workspace(data_dir: &Path) -> Result<QuickChatWorkspace, String> {
    let data_dir = data_dir.canonicalize().map_err(|error| error.to_string())?;
    let parent = data_dir.join("quick-chats");
    match fs::symlink_metadata(&parent) {
        Ok(metadata) if metadata.file_type().is_symlink() || !metadata.is_dir() => {
            return Err("Thư mục chat không hợp lệ. Không dùng liên kết thay cho thư mục riêng.".into());
        }
        Ok(_) => {}
        Err(error) if error.kind() == std::io::ErrorKind::NotFound => create_private_directory(&parent)?,
        Err(error) => return Err(error.to_string()),
    }
    let root = parent.join(uuid::Uuid::new_v4().to_string());
    create_private_directory(&root)?;
    Ok(QuickChatWorkspace {
        path: super::files::display_workspace_path(&root),
        name: "Chat riêng".into(),
        kind: "scratch" ,
    })
}

#[tauri::command]
pub fn neko_create_quick_chat_workspace(app: tauri::AppHandle) -> Result<QuickChatWorkspace, String> {
    let data_dir = app.path().app_local_data_dir().map_err(|error| error.to_string())?;
    create_workspace(&data_dir)
}

#[cfg(target_os = "linux")]
pub(crate) fn confined_write_roots(
    data_dir: &Path,
    requested: &Path,
    canonical: &Path,
    home: &Path,
    scratch_requested: bool,
) -> Result<Option<Vec<std::path::PathBuf>>, String> {
    let parent = data_dir
        .canonicalize()
        .map_err(|error| error.to_string())?
        .join("quick-chats");
    if !scratch_requested && !requested.starts_with(&parent) && !canonical.starts_with(&parent) {
        return Ok(None);
    }
    if parent.canonicalize().map_err(|error| error.to_string())? != parent
        || canonical.parent() != Some(parent.as_path())
        || !canonical.is_dir()
    {
        return Err("Thư mục Quick Chat không hợp lệ.".into());
    }
    let state = home
        .canonicalize()
        .map_err(|error| error.to_string())?
        .join(".neko-core");
    let temp = canonical.join(".tmp");
    for root in [&state, &temp] {
        match fs::symlink_metadata(root) {
            Ok(meta) if meta.file_type().is_symlink() || !meta.is_dir() => {
                return Err("Thư mục ghi Quick Chat không hợp lệ.".into());
            }
            Ok(_) => {}
            Err(error) if error.kind() == std::io::ErrorKind::NotFound => {
                create_private_directory(root)?
            }
            Err(error) => return Err(error.to_string()),
        }
    }
    Ok(Some(vec![canonical.to_path_buf(), state, temp]))
}

#[cfg(test)]
mod tests {
    use super::*;
    #[cfg(target_os = "linux")]
    #[test]
    fn confinement_admits_only_managed_roots_and_private_writable_directories() {
        let base = std::env::temp_dir().join(format!("wiii-quick-policy-{}", uuid::Uuid::new_v4()));
        fs::create_dir(&base).unwrap();
        let project = base.join("project");
        fs::create_dir(&project).unwrap();
        assert!(
            confined_write_roots(&base, &project, &project, &base, false)
                .unwrap()
                .is_none()
        );
        assert!(confined_write_roots(&base, &project, &project, &base, true).is_err());
        let workspace = create_workspace(&base).unwrap();
        let scratch = Path::new(&workspace.path);
        let roots = confined_write_roots(&base, scratch, scratch, &base, true)
            .unwrap()
            .unwrap();
        assert_eq!(
            roots,
            vec![
                scratch.to_path_buf(),
                base.join(".neko-core"),
                scratch.join(".tmp")
            ]
        );
        assert!(confined_write_roots(&base, scratch, &project, &base, true).is_err());
        let nested = scratch.join("nested");
        fs::create_dir(&nested).unwrap();
        assert!(confined_write_roots(&base, &nested, &nested, &base, true).is_err());
        fs::remove_dir(&roots[1]).unwrap();
        std::os::unix::fs::symlink(&project, &roots[1]).unwrap();
        assert!(confined_write_roots(&base, scratch, scratch, &base, true).is_err());
        fs::remove_file(&roots[1]).unwrap();
        fs::remove_dir(&roots[2]).unwrap();
        std::os::unix::fs::symlink(&project, &roots[2]).unwrap();
        assert!(confined_write_roots(&base, scratch, scratch, &base, true).is_err());
        fs::remove_dir_all(base).unwrap();
    }
    #[test]
    fn creates_distinct_empty_folders_beneath_app_data() {
        let base = std::env::temp_dir().join(format!("wiii-quick-chat-{}", uuid::Uuid::new_v4()));
        fs::create_dir(&base).unwrap();
        let a = create_workspace(&base).unwrap();
        let b = create_workspace(&base).unwrap();
        assert_ne!(a.path, b.path);
        assert!(Path::new(&a.path).starts_with(base.canonicalize().unwrap()));
        assert_eq!(fs::read_dir(&a.path).unwrap().count(), 0);
        assert_eq!(a.kind, "scratch");
        #[cfg(unix)] {
            use std::os::unix::fs::PermissionsExt;
            assert_eq!(fs::metadata(&a.path).unwrap().permissions().mode() & 0o777, 0o700);
        }
        fs::remove_dir_all(base).unwrap();
    }
    #[cfg(unix)]
    #[test]
    fn rejects_redirected_chat_parent() {
        let base = std::env::temp_dir().join(format!("wiii-quick-chat-{}", uuid::Uuid::new_v4()));
        fs::create_dir(&base).unwrap();
        std::os::unix::fs::symlink(std::env::temp_dir(), base.join("quick-chats")).unwrap();
        assert!(create_workspace(&base).is_err());
        fs::remove_dir_all(base).unwrap();
    }
}
