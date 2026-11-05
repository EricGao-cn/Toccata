use serde::Deserialize;
use std::path::PathBuf;

/// 全部字段可选，缺省走 Default。
#[derive(Debug, Clone, Deserialize)]
#[serde(default)]
pub struct Config {
    pub idle_gap_secs: u64,
    pub trailing_grace_secs: u64,
    pub flush_interval_secs: u64,
    pub flush_batch_size: usize,
    pub db_path: Option<String>,
    pub socket_path: Option<String>,
}

#[cfg(all(test, feature = "personal-distribution"))]
mod personal_tests {
    use super::Config;

    #[test]
    fn personal_database_and_socket_ignore_legacy_redirects() {
        let config = Config {
            db_path: Some("/tmp/old-toccata.db".into()),
            socket_path: Some("/tmp/old-toccata.sock".into()),
            ..Config::default()
        };
        assert!(Config::data_dir().ends_with("Library/Application Support/Toccata-Personal"));
        assert_eq!(config.db_path(), Config::data_dir().join("toccata.db"));
        assert_eq!(
            config.socket_path(),
            Config::data_dir().join("toccata.sock")
        );
    }

    #[test]
    fn linked_personal_paths_are_rejected() {
        use std::os::unix::fs::symlink;
        let root = std::env::temp_dir().canonicalize().unwrap().join(format!(
            "toccata-personal-links-{}-{}",
            std::process::id(),
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap()
                .as_nanos()
        ));
        std::fs::create_dir_all(root.join("data")).unwrap();
        let data = root.join("data");
        let original = root.join("original.sqlite");
        std::fs::write(&original, b"synthetic").unwrap();
        assert!(Config::validate_personal_dir(&data).is_ok());
        symlink(&original, data.join("tasks.sqlite")).unwrap();
        assert!(Config::validate_personal_dir(&data).is_err());
        std::fs::remove_file(data.join("tasks.sqlite")).unwrap();
        std::fs::hard_link(&original, data.join("toccata.db")).unwrap();
        assert!(Config::validate_personal_dir(&data).is_err());
        std::fs::remove_file(data.join("toccata.db")).unwrap();
        std::fs::write(root.join(".data.maintenance.pending.json"), b"pending").unwrap();
        assert!(Config::validate_personal_dir(&data).is_err());
        symlink(&data, root.join("alias")).unwrap();
        assert!(Config::validate_personal_dir(&root.join("alias")).is_err());
        std::fs::remove_dir_all(root).unwrap();
    }
}

impl Default for Config {
    fn default() -> Self {
        Self {
            idle_gap_secs: 60,
            trailing_grace_secs: 5,
            flush_interval_secs: 2,
            flush_batch_size: 500,
            db_path: None,
            socket_path: None,
        }
    }
}

impl Config {
    /// ~/Library/Application Support/Toccata/
    pub fn data_dir() -> PathBuf {
        #[cfg(feature = "personal-distribution")]
        {
            return Self::personal_data_dir();
        }
        #[cfg(not(feature = "personal-distribution"))]
        {
            if let Some(path) = std::env::var_os("TOCCATA_DATA_DIR").filter(|path| !path.is_empty())
            {
                return PathBuf::from(path);
            }
            let home = std::env::var("HOME").unwrap_or_else(|_| "/tmp".to_string());
            PathBuf::from(home).join("Library/Application Support/Toccata")
        }
    }

    #[cfg(feature = "personal-distribution")]
    fn personal_data_dir() -> PathBuf {
        let home = std::env::var("HOME").expect("Personal distribution requires HOME");
        let root = PathBuf::from(home).join("Library/Application Support/Toccata-Personal");
        Self::validate_personal_dir(&root)
            .expect("Personal data path must be independent without links");
        root
    }

    #[cfg(feature = "personal-distribution")]
    fn validate_personal_dir(root: &std::path::Path) -> std::io::Result<()> {
        use std::os::unix::fs::MetadataExt;
        if let (Some(parent), Some(name)) = (root.parent(), root.file_name()) {
            let pending = parent.join(format!(
                ".{}.maintenance.pending.json",
                name.to_string_lossy()
            ));
            match std::fs::symlink_metadata(pending) {
                Ok(_) => {
                    return Err(std::io::Error::new(
                        std::io::ErrorKind::WouldBlock,
                        "Personal maintenance recovery required",
                    ))
                }
                Err(error) if error.kind() == std::io::ErrorKind::NotFound => {}
                Err(error) => return Err(error),
            }
        }
        let mut paths: Vec<PathBuf> = root.ancestors().map(|p| p.to_path_buf()).collect();
        for name in [
            "config.json",
            "toccata.sock",
            "toccata.lock",
            "tasks.sqlite",
            "toccata.db",
            "daily-notes",
            "tasks.sqlite-wal",
            "tasks.sqlite-shm",
            "toccata.db-wal",
            "toccata.db-shm",
        ] {
            paths.push(root.join(name));
        }
        for path in paths {
            match std::fs::symlink_metadata(path) {
                Ok(metadata)
                    if metadata.file_type().is_symlink()
                        || (metadata.is_file() && metadata.nlink() > 1) =>
                {
                    return Err(std::io::Error::new(
                        std::io::ErrorKind::InvalidInput,
                        "Linked personal data path rejected",
                    ));
                }
                Ok(_) => {}
                Err(error) if error.kind() == std::io::ErrorKind::NotFound => {}
                Err(error) => return Err(error),
            }
        }
        Ok(())
    }

    pub fn load() -> Self {
        let path = Self::data_dir().join("config.json");
        match std::fs::read_to_string(&path) {
            Ok(text) => match serde_json::from_str::<Config>(&text) {
                Ok(cfg) => cfg,
                Err(e) => {
                    eprintln!("[toccata-core] 配置文件 {path:?} 解析失败（{e}），使用默认配置");
                    Config::default()
                }
            },
            Err(_) => Config::default(), // 文件不存在属正常情况
        }
    }

    pub fn db_path(&self) -> PathBuf {
        #[cfg(feature = "personal-distribution")]
        {
            return Self::personal_data_dir().join("toccata.db");
        }
        #[cfg(not(feature = "personal-distribution"))]
        {
            self.db_path
                .as_ref()
                .map(PathBuf::from)
                .unwrap_or_else(|| Self::data_dir().join("toccata.db"))
        }
    }

    pub fn socket_path(&self) -> PathBuf {
        #[cfg(feature = "personal-distribution")]
        {
            return Self::personal_data_dir().join("toccata.sock");
        }
        #[cfg(not(feature = "personal-distribution"))]
        {
            self.socket_path
                .as_ref()
                .map(PathBuf::from)
                .unwrap_or_else(|| Self::data_dir().join("toccata.sock"))
        }
    }
}
